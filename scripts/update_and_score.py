import json
import os
import requests
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

# Standard browser headers to bypass ESPN 403 restrictions
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

for week in data['weeks']:
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={week['espnEventId']}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        res = response.json()

        header = res.get('header', {})
        competitions = header.get('competitions', [{}])[0]
        status = competitions.get('status', {}).get('type', {}).get('state')

        # Extract DraftKings odds spread
        if 'pickcenter' in res:
            for provider in res['pickcenter']:
                if provider.get('provider', {}).get('name') == 'draftkings':
                    week['spread'] = provider.get('spread', {}).get('pointSpread', {}).get('american')

        # Score the game if finished and not yet processed
        if status == 'post' and not week['gameFinished']:
            competitors = competitions.get('competitors', [])
            mich = next(c for c in competitors if 'Michigan' in c['team']['displayName'])
            opp = next(c for c in competitors if 'Michigan' not in c['team']['displayName'])

            m_score = int(mich.get('score', 0))
            o_score = int(opp.get('score', 0))

            mich_won = m_score > o_score
            spread_val = float(week.get('spread', -26.5))
            mich_covered = (m_score - o_score) + spread_val > 0

            week['michiganWon'] = mich_won
            week['michiganCovered'] = mich_covered
            week['gameFinished'] = True
            updated = True

            # Calculate scores for each player
            for pid, pick in week['picks'].items():
                pts = 0
                if pick['winPick'] == mich_won:
                    pts += 1
                if pick['coverPick'] == mich_covered:
                    pts += 1
                pick['pointsAwarded'] = pts

    except Exception as e:
        print(f"Error checking week {week['week']}: {e}")

# Save updated JSON state
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Send Resend notification email if game scores were updated
if updated and resend.api_key:
    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": "dieguitosoto@gmail.com",
        "subject": "〽️ Michigan Football Pool Chart Updated!",
        "html": f"<p>The scores for the recent Michigan game have been processed!</p><p>Check out the updated leaderboard line chart here: <a href='https://dieguitosoto.github.io/michigan-pool'>View Chart</a></p>"
    })
