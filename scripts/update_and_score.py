import json
import os
import re
import requests
from bs4 import BeautifulSoup
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

for week in data['weeks']:
    event_id = week['espnEventId']
    print(f"--- Processing Week {week['week']} (Event ID: {event_id}) ---")
    
    m_score = None
    o_score = None
    is_completed = False

    # METHOD 1: Direct Web Scrape of ESPN Game Page (Bypasses API IP Blocks)
    web_url = f"https://www.espn.com/college-football/game/_/gameId/{event_id}"
    try:
        page_res = requests.get(web_url, headers=headers, timeout=10)
        print(f"HTML Web Page Response Code: {page_res.status_code}")
        
        if page_res.status_code == 200:
            soup = BeautifulSoup(page_res.text, 'html.parser')
            
            # Check for Final / Game Finished status in HTML header
            status_elem = soup.find(class_=re.compile('Gamestrip__Status|game-status|status-detail'))
            status_text = status_elem.get_text() if status_elem else ""
            print(f"Web Page Game Status Text: '{status_text}'")

            if 'Final' in status_text or 'COMPLETED' in status_text.upper():
                is_completed = True

            # Extract Scores from HTML
            scores = soup.find_all(class_=re.compile('Gamestrip__Score|score'))
            teams = soup.find_all(class_=re.compile('Gamestrip__Team|team-name'))
            
            if len(scores) >= 2 and len(teams) >= 2:
                team1_name = teams[0].get_text()
                team1_score = int(scores[0].get_text().strip())
                team2_score = int(scores[1].get_text().strip())

                if 'Michigan' in team1_name and 'Western' not in team1_name:
                    m_score = team1_score
                    o_score = team2_score
                else:
                    m_score = team2_score
                    o_score = team1_score

                print(f"Extracted Scores via Web Scrape -> Michigan: {m_score}, Opponent: {o_score}")
    except Exception as e:
        print(f"Web Scrape method failed: {e}")

    # METHOD 2: API Fallback (If Web Scrape didn't get scores)
    if m_score is None:
        api_url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={event_id}"
        try:
            api_res = requests.get(api_url, headers=headers, timeout=10)
            print(f"API Fallback Response Code: {api_res.status_code}")
            if api_res.status_code == 200:
                res = api_res.json()
                header = res.get('header', {})
                competitions = header.get('competitions', [{}])[0]
                status_type = competitions.get('status', {}).get('type', {}).get('state')
                
                if status_type == 'post':
                    is_completed = True
                    competitors = competitions.get('competitors', [])
                    mich = next(c for c in competitors if 'Michigan' in c.get('team', {}).get('displayName', '') and 'Western' not in c.get('team', {}).get('displayName', ''))
                    opp = next(c for c in competitors if 'Michigan' not in c.get('team', {}).get('displayName', '') or 'Western' in c.get('team', {}).get('displayName', ''))
                    m_score = int(mich.get('score', 0))
                    o_score = int(opp.get('score', 0))
        except Exception as e:
            print(f"API method failed: {e}")

    # Process scoring if game is completed and scores were extracted
    if is_completed and m_score is not None and not week['gameFinished']:
        print("Game is finished! Scoring picks...")
        
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

# Save JSON state
with open('data.json', 'r+') as f:
    f.seek(0)
    json.dump(data, f, indent=2)
    f.truncate()

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
