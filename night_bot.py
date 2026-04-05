import os
import json
import requests
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
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

def get_todays_questions(sheet):
    today = datetime.now().strftime("%d-%m-%Y")
    all_rows = sheet.get_all_values()
    todays = []
    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) >= 12 and row[0] == today and row[1] == "Morning":
            todays.append({
                "row_index": i,
                "Date": row[0], "Status": row[1], "Subject": row[2],
                "Question_EN": row[3], "Question_BN": row[4],
                "OptionA": row[5], "OptionB": row[6],
                "OptionC": row[7], "OptionD": row[8],
                "Answer": row[9], "Explanation_EN": row[10],
                "Explanation_BN": row[11],
                "Difficulty": row[14] if len(row) > 14 else "Medium"
            })
    return todays

def get_encouragement(total_votes):
    if total_votes >= 100:
        return "🔥 Amazing participation today! You all are unstoppable!"
    elif total_votes >= 50:
        return "💪 Great effort today! Keep pushing forward!"
    elif total_votes >= 20:
        return "📚 Good participation! Invite your friends to join!"
    else:
        return "🌱 Every attempt counts! Share this with your study group!"

def update_status(sheet, todays_questions):
    today = datetime.now().strftime("%d-%m-%Y")
    all_rows = sheet.get_all_values()
    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) >= 2 and row[0] == today and row[1] == "Morning":
            sheet.update_cell(i, 2, "Night")
            print(f"Updated row {i} to Night")

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload)
    print("Message status:", r.status_code)
    print("Response:", r.text[:200])

def main():
    print("Starting Night Bot...")
    today = datetime.now().strftime("%d-%m-%Y")

    sheet = get_sheet()
    print("Sheet connected!")

    todays_questions = get_todays_questions(sheet)
    print(f"Found {len(todays_questions)} questions")

    if not todays_questions:
        send_message("⚠️ আজকের প্রশ্নের উত্তর পাওয়া যায়নি।")
        return

    difficulty = todays_questions[0].get("Difficulty", "Medium")
    difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}

    subjects = [
        "📚 History / ইতিহাস",
        "⚖️ Polity / রাষ্ট্রবিজ্ঞান",
        "🔬 Science / বিজ্ঞান"
    ]

    message = (
        f"💡 <b>Answers &amp; Explanations — Today's Challenge</b>\n"
        f"{difficulty_emoji.get(difficulty,'🟡')} Difficulty: <b>{difficulty}</b>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
    )

    for i, q in enumerate(todays_questions):
        answer_letter = q.get("Answer", "")
        option_map = {
            "A": q.get("OptionA",""), "B": q.get("OptionB",""),
            "C": q.get("OptionC",""), "D": q.get("OptionD","")
        }
        correct_option = option_map.get(answer_letter, "")
        subject = subjects[i] if i < len(subjects) else f"Q{i+1}"

        message += f"<b>Ans {i+1}: {subject}</b>\n"
        message += f"✅ <b>{answer_letter}) {correct_option}</b>\n\n"
        message += f"📖 <b>Explanation:</b>\n{q.get('Explanation_EN','')}\n\n"
        message += f"📖 <b>ব্যাখ্যা:</b>\n{q.get('Explanation_BN','')}\n\n"
        message += "━━━━━━━━━━━━━━━━\n\n"

    encouragement = get_encouragement(50)
    message += f"🎯 {encouragement}\n\n"

    message += (
        "🏆 <b>Crack Any Competitive Exam with Gyan Mukut!</b>\n\n"
        "Whether it is State PSC, SSC, or Railways —\n"
        "selection requires perfect strategy and consistency.\n\n"
        "✅ Smart Study Materials\n"
        "✅ Weekly Mock Tests\n\n"
        "📍 <b>For Online Course:</b>\n"
        "📱 WhatsApp: <b>8902078070 / 9749347019</b>"
    )

    send_message(message)
    update_status(sheet, todays_questions)
    print("✅ Night Bot completed!")

main()
