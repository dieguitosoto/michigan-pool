import json
import os
import re
import requests
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

# Realistic browser headers to encourage a full HTML page response
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Upgrade-Insecure-Requests': '1'
}

session = requests.Session()

for week in data['weeks']:
    event_id = week['espnEventId']
    print(f"--- Processing Week {week['week']} (Event ID: {event_id}) ---")
    
    m_score = None
    o_score = None
    is_completed = False

    # Fetch main game page
    web_url = f"https://www.espn.com/college-football/game/_/gameId/{event_id}"
    
    try:
        page_res = session.get(web_url, headers=headers, timeout=15)
        print(f"Game Page Response Code: {page_res.status_code}")
        
        html_content = page_res.text

        # Extract embedded hydrated JSON payload (__espnfcache__ or __INITIAL_STATE__)
        json_match = re.search(r'window\[[\'"]__espnfcache__[\'"]\]\s*=\s*(\{.*?\});</script>', html_content, re.DOTALL)
        
        if not json_match:
            json_match = re.search(r'window\[[\'"]__INITIAL_STATE__[\'"]\]\s*=\s*(\{.*?\});</script>', html_content, re.DOTALL)

        if json_match:
            print("Found embedded hydrated JSON state in HTML!")
            raw_json = json_match.group(1)
            cache_data = json.loads(raw_json)
            
            # Walk the dictionary payload to find game header data
            for key, val in cache_data.items():
                if isinstance(val, dict) and 'header' in val:
                    header = val.get('header', {})
                    competitions = header.get('competitions', [{}])[0]
                    status_info = competitions.get('status', {})
                    state = status_info.get('type', {}).get('state')
                    completed = status_info.get('type', {}).get('completed', False)

                    if completed or state == 'post':
                        is_completed = True

                    competitors = competitions.get('competitors', [])
                    if len(competitors) >= 2:
                        mich = next(c for c in competitors if 'Michigan' in c.get('team', {}).get('displayName', '') and 'Western' not in c.get('team', {}).get('displayName', ''))
                        opp = next(c for c in competitors if 'Michigan' not in c.get('team', {}).get('displayName', '') or 'Western' in c.get('team', {}).get('displayName', ''))
                        
                        m_score = int(mich.get('score', 0))
                        o_score = int(opp.get('score', 0))
                        print(f"Parsed Embedded Scores -> Michigan: {m_score}, Opponent: {o_score}")
                    break
        else:
            print("Embedded JSON script tag not found; scanning raw regex patterns...")
            # Direct RegEx regex fallback on HTML source string
            status_match = re.search(r'"summary"\s*:\s*"Final"', html_content) or re.search(r'"state"\s*:\s*"post"', html_content)
            if status_match:
                is_completed = True

    except Exception as e:
        print(f"Web extraction error: {e}")

    # Fallback to manual trigger for completed games if scraping headers fail
    if week.get('forceComplete', False):
        is_completed = True
        m_score = week.get('testMichScore', 28)
        o_score = week.get('testOppScore', 14)

    # Process scores and update points
    if is_completed and m_score is not None and not week['gameFinished']:
        print("Game is completed! Scoring picks...")
        
        mich_won = m_score > o_score
        spread_val = float(week.get('spread', -26.5))
        mich_covered = (m_score - o_score) + spread_val > 0
        print(f"Outcome -> Won: {mich_won}, Covered: {mich_covered}")

        week['michiganWon'] = mich_won
        week['michiganCovered'] = mich_covered
        week['gameFinished'] = True
        updated = True

        for pid, pick in week['picks'].items():
            pts = 0
            if pick['winPick'] == mich_won:
                pts += 1
            if pick['coverPick'] == mich_covered:
                pts += 1
            pick['pointsAwarded'] = pts
            print(f"Player {pid}: {pts} points awarded")

# Save JSON database
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Send Notification Email
if updated and resend.api_key:
    print("Dispatching Resend email notification...")
    email_res = resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": "dieguitosoto@gmail.com",
        "subject": "〽️ Michigan Football Pool Chart Updated!",
        "html": f"<p>The scores for the recent Michigan game have been processed!</p><p>Check out the updated leaderboard line chart here: <a href='https://dieguitosoto.github.io/michigan-pool'>View Chart</a></p>"
    })
    print(f"Resend API Response: {email_res}")
else:
    print(f"Email skipped. updated={updated}, api_key_present={bool(resend.api_key)}")
