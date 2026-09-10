import json
import os
import requests
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

# Generic browser header
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

for week in data['weeks']:
    event_id = week['espnEventId']
    print(f"--- Processing Week {week['week']} (Event ID: {event_id}) ---")
    
    # Public CDN API endpoint (bypasses 403 IP block)
    url = f"https://site.web.api.espn.com/apis/v2/scoreboard/header?sport=football&league=ncaa&event={event_id}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"HTTP Response Code: {response.status_code}")
        
        if response.status_code == 200:
            res = response.json()
            sports = res.get('sports', [{}])[0]
            leagues = sports.get('leagues', [{}])[0]
            events = leagues.get('events', [{}])[0]
            
            status_summary = events.get('status', {}).get('summary', '')
            status_type = events.get('status', {}).get('type', '')
            print(f"Game Status: {status_summary} (type: {status_type})")

            competitors = events.get('competitors', [])
            
            # Extract Spread Odds if available
            odds_info = events.get('odds', {})
            if odds_info:
                spread_text = odds_info.get('details', '') # e.g. "MICH -26.5"
                print(f"DraftKings Odds Detail: {spread_text}")

            # Determine completion (STATUS_FINAL / COMPLETED / 'Final')
            is_completed = status_type == 'STATUS_FINAL' or 'Final' in status_summary

            if is_completed and not week['gameFinished']:
                print("Game is completed! Calculating player scores...")
                
                mich = next(c for c in competitors if 'Michigan' in c.get('displayName', '') and 'Western' not in c.get('displayName', ''))
                opp = next(c for c in competitors if 'Michigan' not in c.get('displayName', '') or 'Western' in c.get('displayName', ''))

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

# Save updated JSON state
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Dispatch notification email via Resend
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
