import json
import urllib.request
import os
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

for week in data['weeks']:
    # Fetch live game info from ESPN Hidden Endpoint
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={week['espnEventId']}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            header = res.get('header', {})
            competitions = header.get('competitions', [{}])[0]
            status = competitions.get('status', {}).get('type', {}).get('state')

            # Fetch odds
            if 'pickcenter' in res:
                for provider in res['pickcenter']:
                    if provider.get('provider', {}).get('name') == 'draftkings':
                        week['spread'] = provider.get('spread')

            # Process finished game scoring
            if status == 'post' and not week['gameFinished']:
                competitors = competitions.get('competitors', [])
                mich = next(c for c in competitors if 'Michigan' in c['team']['displayName'])
                opp = next(c for c in competitors if 'Michigan' not in c['team']['displayName'])

                m_score = int(mich.get('score', 0))
                o_score = int(opp.get('score', 0))

                mich_won = m_score > o_score
                mich_covered = (m_score - o_score) + week['spread'] > 0

                week['michiganWon'] = mich_won
                week['michiganCovered'] = mich_covered
                week['gameFinished'] = True
                updated = True

                # Score each player
                for pid, pick in week['picks'].items():
                    pts = 0
                    if pick['winPick'] == mich_won:
                        pts += 1
                    if pick['coverPick'] == mich_covered:
                        pts += 1
                    pick['pointsAwarded'] = pts

    except Exception as e:
        print(f"Error checking week {week['week']}: {e}")

# Save updated state
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Send Resend Notification Email if scores were processed
if updated and resend.api_key:
    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": "dieguitosoto@gmail.com",
        "subject": "〽️ Michigan Football Pool Chart Updated!",
        "html": f"<p>The scores for the recent Michigan game have been processed!</p><p>Check out the updated leaderboard line chart here: <a href='https://YOUR_GITHUB_USERNAME.github.io/michigan-pool'>View Chart</a></p>"
    })
