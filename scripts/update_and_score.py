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
    
    # Use ESPN Core API endpoint to avoid 403 blocks
    event_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/usa.1/events/{event_id}"
    
    try:
        res = requests.get(event_url, headers=headers, timeout=10).json()
        
        # Check game completion status
        competition = res.get('competitions', [{}])[0]
        status_type = competition.get('status', {}).get('type', {})
        is_completed = status_type.get('completed', False)

        # Fetch spread odds if available
        odds_ref = competition.get('odds', {}).get('$ref')
        if odds_ref:
            try:
                odds_res = requests.get(odds_ref, headers=headers, timeout=10).json()
                items = odds_res.get('items', [])
                if items:
                    # Take the first available odds provider spread
                    week['spread'] = items[0].get('spread', week.get('spread', -26.5))
            except Exception as e:
                print(f"Could not fetch odds details: {e}")

        # Score the game if finished and not yet marked finished
        if is_completed and not week['gameFinished']:
            competitors_ref = competition.get('competitors', [])
            
            mich_score = 0
            opp_score = 0
            
            for comp in competitors_ref:
                score_ref = comp.get('score', {}).get('$ref')
                team_ref = comp.get('team', {}).get('$ref')
                
                if score_ref and team_ref:
                    team_data = requests.get(team_ref, headers=headers, timeout=10).json()
                    score_data = requests.get(score_ref, headers=headers, timeout=10).json()
                    
                    score_val = int(score_data.get('value', 0))
                    
                    if 'Michigan' in team_data.get('displayName', '') and 'Western' not in team_data.get('displayName', ''):
                        mich_score = score_val
                    else:
                        opp_score = score_val

            mich_won = mich_score > opp_score
            spread_val = float(week.get('spread', -26.5))
            mich_covered = (mich_score - opp_score) + spread_val > 0

            week['michiganWon'] = mich_won
            week['michiganCovered'] = mich_covered
            week['gameFinished'] = True
            updated = True

            # Assign points to players
            for pid, pick in week['picks'].items():
                pts = 0
                if pick['winPick'] == mich_won:
                    pts += 1
                if pick['coverPick'] == mich_covered:
                    pts += 1
                pick['pointsAwarded'] = pts

    except Exception as e:
        print(f"Error checking week {week['week']}: {e}")

# Save updated JSON database
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Send Resend notification email if game scores were updated
if updated and resend.api_key:
    response = resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": "dieguitosoto@gmail.com",
        "subject": "〽️ Michigan Football Pool Chart Updated!",
        "html": f"<p>The scores for the recent Michigan game have been processed!</p><p>Check out the updated leaderboard line chart here: <a href='https://dieguitosoto.github.io/michigan-pool'>View Chart</a></p>"
    })
    print(f"Resend API Response: {response}")

