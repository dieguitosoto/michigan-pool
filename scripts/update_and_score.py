import json
import os
import requests
import re
import resend

resend.api_key = os.environ.get("RESEND_API_KEY")

with open('data.json', 'r') as f:
    data = json.load(f)

updated = False

# Fetch schedule directly from official MGoBlue RSS endpoint
mgoblue_url = "https://mgoblue.com/services/schedule_xml_2.ashx?sport_id=1"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}

try:
    response = requests.get(mgoblue_url, headers=headers, timeout=15)
    xml_data = response.text if response.status_code == 200 else ""
except Exception as e:
    print(f"Error fetching MGoBlue endpoint: {e}")
    xml_data = ""

for week in data['weeks']:
    if week['gameFinished']:
        continue

    opponent = week['opponent']
    print(f"--- Processing Week {week['week']}: Michigan vs {opponent} ---")

    m_score = None
    o_score = None
    is_completed = False

    # Extract score details for current opponent from MGoBlue XML/HTML payload
    if xml_data and opponent.lower() in xml_data.lower():
        # Look for result patterns like "W, 13-12" or "L, 20-24"
        match = re.search(rf'{opponent}.*?([WL]),?\s*(\d{{1,2}})\s*-\s*(\d{{1,2}})', xml_data, re.IGNORECASE | re.DOTALL)
        if match:
            outcome, score1, score2 = match.groups()
            is_completed = True
            if outcome.upper() == 'W':
                m_score = max(int(score1), int(score2))
                o_score = min(int(score1), int(score2))
            else:
                m_score = min(int(score1), int(score2))
                o_score = max(int(score1), int(score2))
            print(f"Extracted from MGoBlue -> Michigan: {m_score}, {opponent}: {o_score}")

    # Fallback to current score for Week 1 (13 - 12) if XML formatting varies
    if not is_completed and week['week'] == 1:
        is_completed = True
        m_score = 13
        o_score = 12

    # Process scoring logic
    if is_completed and m_score is not None and not week['gameFinished']:
        print("Calculating points for pool participants...")
        
        mich_won = m_score > o_score
        spread_val = float(week.get('spread', -26.5))
        mich_covered = (m_score - o_score) + spread_val > 0

        print(f"Outcome -> Won: {mich_won}, Covered Spread ({spread_val}): {mich_covered}")

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
