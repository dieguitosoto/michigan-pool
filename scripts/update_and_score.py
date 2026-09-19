import json
import os
import requests
import re
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}

# Fetch both standard HTML schedule page and text endpoint from MGoBlue
mgoblue_text = ""
try:
    url_html = "https://mgoblue.com/sports/football/schedule"
    res_html = requests.get(url_html, headers=headers, timeout=15)
    if res_html.status_code == 200:
        mgoblue_text += res_html.text

    url_text = "https://mgoblue.com/sports/football/schedule/text"
    res_text = requests.get(url_text, headers=headers, timeout=15)
    if res_text.status_code == 200:
        mgoblue_text += " " + res_text.text
except Exception as e:
    print(f"Error fetching MGoBlue pages: {e}")

for week in data['weeks']:
    if week['gameFinished']:
        print(f"Week {week['week']} ({week['opponent']}) already processed.")
        continue

    opponent = week['opponent']
    print(f"--- Processing Week {week['week']}: Michigan vs {opponent} ---")

    m_score = None
    o_score = None
    is_completed = False

    if mgoblue_text:
        # Match pattern 1: "W, 17-10" or "L, 10-17"
        pattern1 = rf'{re.escape(opponent)}.*?\b([WL])\b,?\s*(\d{{1,3}})\s*-\s*(\d{{1,3}})'
        # Match pattern 2: "Win , 17 , to , 10" or "Loss , 10 , to , 17"
        pattern2 = rf'{re.escape(opponent)}.*?\b(Win|Loss)\b\s*,\s*(\d{{1,3}})\s*,\s*to\s*,\s*(\d{{1,3}})'

        match1 = re.search(pattern1, mgoblue_text, re.IGNORECASE | re.DOTALL)
        match2 = re.search(pattern2, mgoblue_text, re.IGNORECASE | re.DOTALL)

        if match1:
            outcome, score1, score2 = match1.groups()
            is_completed = True
            s1, s2 = int(score1), int(score2)
            if outcome.upper() == 'W':
                m_score, o_score = max(s1, s2), min(s1, s2)
            else:
                m_score, o_score = min(s1, s2), max(s1, s2)
            print(f"MGoBlue Pattern 1 Match -> Michigan: {m_score}, {opponent}: {o_score}")
        elif match2:
            outcome, score1, score2 = match2.groups()
            is_completed = True
            s1, s2 = int(score1), int(score2)
            if outcome.lower() == 'win':
                m_score, o_score = max(s1, s2), min(s1, s2)
            else:
                m_score, o_score = min(s1, s2), max(s1, s2)
            print(f"MGoBlue Pattern 2 Match -> Michigan: {m_score}, {opponent}: {o_score}")

    # Process scoring logic
    if is_completed and m_score is not None and not week['gameFinished']:
        print("Calculating points for pool participants...")
        
        mich_won = m_score > o_score
        spread_val = float(week.get('spread', 0))
        
        # Michigan Cover Logic: Michigan Score - Opponent Score + Spread > 0
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
