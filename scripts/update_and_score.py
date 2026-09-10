import json
import os
import requests
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.espn.com',
    'Referer': 'https://www.espn.com/'
})

for week in data['weeks']:
    event_id = week['espnEventId']
    print(f"--- Processing Week {week['week']} (Event ID: {event_id}) ---")
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={event_id}"
    
    try:
        response = session.get(url, timeout=10)
        print(f"HTTP Response Code: {response.status_code}")
        
        if response.status_code == 200:
            res = response.json()
            header = res.get('header', {})
            competitions = header.get('competitions', [{}])[0]
            status_info = competitions.get('status', {})
            state = status_info.get('type', {}).get('state')
            completed = status_info.get('type', {}).get('completed', False)

            print(f"Game State: '{state}', Completed: {completed}")

            # Extract Odds
            if 'pickcenter' in res:
                for provider in res['pickcenter']:
                    if provider.get('provider', {}).get('name') == 'draftkings':
                        week['spread'] = provider.get('spread', week.get('spread', -26.5))
                        print(f"DraftKings Spread: {week['spread']}")

            competitors = competitions.get('competitors', [])
            has_scores = len(competitors) > 0 and 'score' in competitors[0]

            # Process if completed or state is 'post' or scores are present
            if (completed or state == 'post' or has_scores) and not week['gameFinished']:
                print("Game is completed! Calculating player scores...")
                
                mich = next(c for c in competitors if 'Michigan' in c.get('team', {}).get('displayName', '') and 'Western' not in c.get('team', {}).get('displayName', ''))
                opp = next(c for c in competitors if 'Michigan' not in c.get('team', {}).get('displayName', '') or 'Western' in c.get('team', {}).get('displayName', ''))

                m_score = int(mich.get('score', 0))
                o_score = int(opp.get('score', 0))
                print(f"Final Score -> Michigan: {m_score}, Opponent: {o_score}")

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

    except Exception as e:
        print(f"Error checking week {week['week']}: {e}")

# Save JSON state
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
