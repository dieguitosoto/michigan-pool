import json
import os
import cloudscraper
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False
scraper = cloudscraper.create_scraper()

for week in data['weeks']:
    event_id = week['espnEventId']
    print(f"--- Processing Week {week['week']} (Event ID: {event_id}) ---")
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={event_id}"
    
    try:
        response = scraper.get(url, timeout=10)
        print(f"HTTP Response Code: {response.status_code}")
        
        if response.status_code == 200:
            res = response.json()
            header = res.get('header', {})
            competitions = header.get('competitions', [{}])[0]
            status_info = competitions.get('status', {})
            state = status_info.get('type', {}).get('state')

            print(f"Game State: {state}")

            # Extract Spread
            if 'pickcenter' in res:
                for provider in res['pickcenter']:
                    if provider.get('provider', {}).get('name') == 'draftkings':
                        week['spread'] = provider.get('spread', week.get('spread', -26.5))
                        print(f"DraftKings Spread: {week['spread']}")

            # Score game if completed (state == 'post') and not yet finished
            if state == 'post' and not week['gameFinished']:
                print("Game is completed! Scoring picks...")
                competitors = competitions.get('competitors', [])
                
                mich = next(c for c in competitors if 'Michigan' in c['team']['displayName'] and 'Western' not in c['team']['displayName'])
                opp = next(c for c in competitors if 'Michigan' not in c['team']['displayName'] or 'Western' in c['team']['displayName'])

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
                    print(f"Player {pid}: {pts} points")

    except Exception as e:
        print(f"Error checking week {week['week']}: {e}")

# Save updated database
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Send Notification Email
if updated and resend.api_key:
    print("Sending Resend email notification...")
    email_res = resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": "dieguitosoto@gmail.com",
        "subject": "〽️ Michigan Football Pool Chart Updated!",
        "html": f"<p>The scores for the recent Michigan game have been processed!</p><p>Check out the updated leaderboard line chart here: <a href='https://dieguitosoto.github.io/michigan-pool'>View Chart</a></p>"
    })
    print(f"Resend API Response: {email_res}")
else:
    print(f"Email skipped. updated={updated}, api_key_present={bool(resend.api_key)}")
