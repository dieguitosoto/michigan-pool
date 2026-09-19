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

raw_content = ""
try:
    # Fetch main schedule page
    res_html = requests.get("https://mgoblue.com/sports/football/schedule", headers=headers, timeout=15)
    if res_html.status_code == 200:
        raw_content += res_html.text

    # Fetch mobile/text schedule endpoint as fallback
    res_text = requests.get("https://mgoblue.com/sports/football/schedule/text", headers=headers, timeout=15)
    if res_text.status_code == 200:
        raw_content += "\n" + res_text.text
except Exception as e:
    print(f"Error fetching MGoBlue schedule page: {e}")

for week in data['weeks']:
    if week['gameFinished']:
        print(f"Week {week['week']} ({week['opponent']}) already processed.")
        continue

    opponent = week['opponent']
    print(f"--- Processing Week {week['week']}: Michigan vs {opponent} ---")

    m_score = None
    o_score = None
    is_completed = False

    if raw_content:
        # Locate game section associated with the opponent
        opp_escaped = re.escape(opponent)
        
        # Look for explicit win/loss patterns tied to opponent
        patterns = [
            # Pattern 1: Oklahoma ... W, 17-10 or Oklahoma ... L, 10-17
            rf'{opp_escaped}.*?\b([WL])\b\s*,\s*(\d{{1,3}})\s*-\s*(\d{{1,3}})',
            # Pattern 2: Oklahoma ... Win, 17, to, 10 or Loss, 10, to, 17
            rf'{opp_escaped}.*?\b(Win|Loss)\b\s*,\s*(\d{{1,3}})\s*,\s*to\s*,\s*(\d{{1,3}})',
            # Pattern 3: W 17-10 vs Oklahoma or L 10-17 vs Oklahoma
            rf'\b([WL])\b\s*(\d{{1,3}})\s*-\s*(\d{{1,3}}).*?{opp_escaped}'
        ]

        for pat in patterns:
            match = re.search(pat, raw_content, re.IGNORECASE | re.DOTALL)
            if match:
                groups = match.groups()
                outcome = groups[0].upper()
                s1, s2 = int(groups[1]), int(groups[2])
                
                is_completed = True
                if outcome in ['W', 'WIN']:
                    m_score, o_score = max(s1, s2), min(s1, s2)
                else:
                    m_score, o_score = min(s1, s2), max(s1, s2)
                
                print(f"Matched Score -> Michigan: {m_score}, {opponent}: {o_score}")
                break

    # Process scoring logic if game is completed
    if is_completed and m_score is not None and not week['gameFinished']:
        print("Calculating points for pool participants...")
        
        mich_won = m_score > o_score
        spread_val = float(week.get('spread', 0))
        
        # Cover logic: Michigan Score - Opponent Score + Spread > 0
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
