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
    records = sheet.get_all_records()
    todays = []
    for row in records:
        if row.get("Date") == today and row.get("Status") == "Morning":
            todays.append(row)
    return todays

def update_status_to_night(sheet, todays_questions):
    records = sheet.get_all_records()
    today = datetime.now().strftime("%d-%m-%Y")
    for i, row in enumerate(records):
        if row.get("Date") == today and row.get("Status") == "Morning":
            sheet.update_cell(i + 2, 2, "Night")
    print("Status updated to Night")

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=payload)
    print("Message status:", r.status_code)
    print("Message response:", r.text[:200])

def main():
    print("Starting Night Bot...")

    sheet = get_sheet()
    todays_questions = get_todays_questions(sheet)
    print(f"Found {len(todays_questions)} questions for today")

    if not todays_questions:
        print("No questions found for today!")
        return

    message = "💡 <b>Answers & Explanations — Today's Challenge</b>\n"
    message += "━━━━━━━━━━━━━━━━\n\n"

    subjects = ["📚 History / ইতিহাস",
                "⚖️ Political Science / রাষ্ট্রবিজ্ঞান",
                "🔬 General Science / সাধারণ বিজ্ঞান"]

    for i, q in enumerate(todays_questions):
        answer_letter = q.get("Answer", "")
        option_key = f"Option{answer_letter}"
        correct_option = q.get(option_key, "")

        message += f"<b>Ans {i+1}: {subjects[i]}</b>\n"
        message += f"✅ <b>{answer_letter}) {correct_option}</b>\n\n"
        message += f"📖 <b>Explanation:</b>\n"
        message += f"{q.get('Explanation_EN', '')}\n\n"
        message += f"📖 <b>ব্যাখ্যা:</b>\n"
        message += f"{q.get('Explanation_BN', '')}\n\n"
        message += "━━━━━━━━━━━━━━━━\n\n"

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
    update_status_to_night(sheet, todays_questions)
    print("Night bot done!")

main()
