import json
import os
import requests
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

for week in data['weeks']:
    event_id = week['espnEventId']
    print(f"--- Checking Week {week['week']} (Event ID: {event_id}) ---")
    
    event_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/usa.1/events/{event_id}"
    
    try:
        res = requests.get(event_url, headers=headers, timeout=10).json()
        
        competition = res.get('competitions', [{}])[0]
        status_info = competition.get('status', {})
        status_type = status_info.get('type', {})
        
        state = status_type.get('state')
        status_name = status_type.get('name')
        completed = status_type.get('completed', False)
        
        print(f"Game Status -> state: '{state}', name: '{status_name}', completed: {completed}")

        # Determine completion across multiple ESPN API status variants
        is_finished = completed or state == 'post' or status_name in ['STATUS_FINAL', 'STATUS_FULL_TIME']

        # Fetch spread odds
        odds_ref = competition.get('odds', {}).get('$ref')
        if odds_ref:
            try:
                odds_res = requests.get(odds_ref, headers=headers, timeout=10).json()
                items = odds_res.get('items', [])
                if items:
                    week['spread'] = items[0].get('spread', week.get('spread', -26.5))
                    print(f"Updated Spread: {week['spread']}")
            except Exception as e:
                print(f"Could not fetch odds details: {e}")

        # Force process if testing or if game is marked finished
        if (is_finished or week.get('forceScore', False)) and not week['gameFinished']:
            print("Game is finished! Extracting team scores...")
            competitors = competition.get('competitors', [])
            
            mich_score = 0
            opp_score = 0
            
            for comp in competitors:
                score_ref = comp.get('score', {}).get('$ref')
                team_ref = comp.get('team', {}).get('$ref')
                
                if score_ref and team_ref:
                    team_data = requests.get(team_ref, headers=headers, timeout=10).json()
                    score_data = requests.get(score_ref, headers=headers, timeout=10).json()
                    
                    score_val = int(score_data.get('value', 0))
                    team_name = team_data.get('displayName', '')
                    
                    if 'Michigan' in team_name and 'Western' not in team_name:
                        mich_score = score_val
                    else:
                        opp_score = score_val

            print(f"Scores Extracted -> Michigan: {mich_score}, Opponent: {opp_score}")

            mich_won = mich_score > opp_score
            spread_val = float(week.get('spread', -26.5))
            mich_covered = (mich_score - opp_score) + spread_val > 0

            print(f"Results -> Won: {mich_won}, Covered: {mich_covered}")

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
                print(f"Player {pid} awarded {pts} pts")

    except Exception as e:
        print(f"Error checking week {week['week']}: {e}")

# Save JSON database
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Send Resend Email
if updated and resend.api_key:
    print("Dispatching Resend email...")
    email_res = resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": "dieguitosoto@gmail.com",
        "subject": "〽️ Michigan Football Pool Chart Updated!",
        "html": f"<p>The scores for the recent Michigan game have been processed!</p><p>Check out the updated leaderboard line chart here: <a href='https://dieguitosoto.github.io/michigan-pool'>View Chart</a></p>"
    })
    print(f"Resend Response: {email_res}")
else:
    print(f"Email skipped. updated={updated}, api_key_present={bool(resend.api_key)}")
