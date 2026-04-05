import os
import json
import requests
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

def get_sheet():
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    scopes = ["https://spreadsheets.google.com/feeds",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
    return sheet

def get_week_data(sheet):
    all_rows = sheet.get_all_values()
    week_rows = []
    for row in all_rows[1:]:
        if len(row) >= 12 and row[0] and row[1] == "Night":
            week_rows.append({
                "Date": row[0],
                "Subject": row[2],
                "Question_EN": row[3],
                "TotalVotes": int(row[12]) if len(row) > 12 and row[12] else 0,
                "CorrectVotes": int(row[13]) if len(row) > 13 and row[13] else 0,
                "Difficulty": row[14] if len(row) > 14 else "Medium"
            })
    return week_rows[-21:]

def generate_weekly_summary(week_data):
    subject_stats = {}
    total_votes = 0

    for row in week_data:
        subj = row["Subject"]
        if subj not in subject_stats:
            subject_stats[subj] = {"total": 0, "correct": 0, "count": 0}
        subject_stats[subj]["total"] += row["TotalVotes"]
        subject_stats[subj]["correct"] += row["CorrectVotes"]
        subject_stats[subj]["count"] += 1
        total_votes += row["TotalVotes"]

    stats_text = ""
    for subj, stats in subject_stats.items():
        acc = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        stats_text += f"{subj}: {acc:.0f}% accuracy, {stats['total']} total votes\n"

    prompt = f"""You are Gyan Mukut's AI educator. Write a weekly performance summary for a Telegram channel.

This week's data:
{stats_text}
Total participation this week: {total_votes} votes

Write a motivating weekly report in BILINGUAL format (English + Bengali) that:
1. Celebrates participation
2. Highlights strongest subject
3. Identifies weakest subject needing more focus
4. Gives one specific study tip
5. Motivates for next week

Keep it under 200 words total. Use emojis. Be warm and encouraging.
Return only the message text, no JSON, no backticks."""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You write warm, bilingual motivational messages for students."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 600,
        "temperature": 0.8
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers, json=body, timeout=30
    )
    print("Groq status:", response.status_code)
    if response.status_code != 200:
        print("Groq error:", response.text)
        return "সাপ্তাহিক রিপোর্ট এই সপ্তাহে পাওয়া যায়নি। Weekly summary unavailable this week."
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=payload)
    print("Telegram status:", r.status_code)
    print("Telegram response:", r.text[:200])

def main():
    print("Starting Weekly Report Bot...")

    sheet = get_sheet()
    print("Sheet connected!")

    week_data = get_week_data(sheet)
    print(f"Found {len(week_data)} rows to analyse")

    if not week_data:
        print("No data found for this week!")
        send_message(
            "📊 <b>Gyan Mukut Weekly Report</b>\n\n"
            "এই সপ্তাহে এখনও পর্যাপ্ত ডেটা নেই।\n"
            "Not enough data yet for this week.\n\n"
            "Keep participating daily! 💪"
        )
        return

    print("Generating AI weekly summary...")
    summary = generate_weekly_summary(week_data)

    message = (
        "📊 <b>Gyan Mukut Weekly Performance Report</b>\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"{summary}\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "🏆 <b>Keep going! Success is near!</b>\n\n"
        "📱 WhatsApp: <b>8902078070 / 9749347019</b>"
    )

    send_message(message)
    print("✅ Weekly report sent successfully!")

main()
