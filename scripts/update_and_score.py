import json
import os
import requests
import re
import resend
from datetime import datetime, timezone

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False
today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

# Map team names to common MGoBlue schedule abbreviations
ALIASES = {
    "UTEP": ["UTEP", "UT El Paso", "El Paso"],
    "Michigan State": ["Michigan State", "MSU"],
    "Penn State": ["Penn State", "PSU"],
    "Ohio State": ["Ohio State", "OSU"]
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}

html_content = ""
try:
    res = requests.get("https://mgoblue.com/sports/football/schedule", headers=headers, timeout=15)
    if res.status_code == 200:
        html_content = res.text
except Exception as e:
    print(f"Error fetching MGoBlue schedule page: {e}")

for week in data['weeks']:
    if week['gameFinished']:
        print(f"Week {week['week']} ({week['opponent']}) already processed.")
        continue

    game_date_str = week.get('date')
    if game_date_str and game_date_str > today_str:
        print(f"Skipping Week {week['week']} ({week['opponent']}): Scheduled for {game_date_str} (Today is {today_str}).")
        continue

    opponent = week['opponent']
    print(f"--- Processing Week {week['week']}: Michigan vs {opponent} ---")

    m_score = None
    o_score = None
    is_completed = False

    if html_content:
        search_names = ALIASES.get(opponent, [opponent])
        for name in search_names:
            match = re.search(rf'{re.escape(name)}[\s\S]*?\b([WL])\b\s*,\s*(\d{{1,3}})\s*-\s*(\d{{1,3}})', html_content, re.IGNORECASE)
            if match:
                outcome, score1, score2 = match.groups()
                s1, s2 = int(score1), int(score2)
                is_completed = True
                
                if outcome.upper() == 'W':
                    m_score, o_score = max(s1, s2), min(s1, s2)
                else:
                    m_score, o_score = min(s1, s2), max(s1, s2)
                
                print(f"MGoBlue Matched Result ({name}) -> Michigan: {m_score}, {opponent}: {o_score}")
                break

    if is_completed and m_score is not None and not week['gameFinished']:
        print("Calculating points for pool participants...")
        
        mich_won = m_score > o_score
        spread_val = float(week.get('spread', 0))
        mich_covered = (m_score - o_score) + spread_val > 0

        print(f"Result -> Final: {m_score}-{o_score} | Michigan Won: {mich_won} | Michigan Covered ({spread_val}): {mich_covered}")

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

# Save updated JSON database
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
    print(f"Resend Response: {email_res}")
else:
    print(f"Email skipped. updated={updated}, api_key_present={bool(resend.api_key)}")
