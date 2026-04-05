import os
import json
import requests
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# === CONFIG ===
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
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

def get_previous_questions(sheet):
    records = sheet.get_all_records()
    previous = []
    for row in records:
        if row.get("Question_EN"):
            previous.append(row["Question_EN"])
    return previous

def generate_mcqs(previous_questions):
    prev_text = "\n".join(previous_questions[-30:]) if previous_questions else "None yet"
    prompt = f"""You are a master educator for Indian competitive exams (WBCS, SSC CGL, CHSL, RRB NTPC, State PSC).

Previously asked questions (DO NOT repeat these or similar topics):
{prev_text}

Generate exactly 3 NEW high-quality MCQs:
- Q1: History (Indian or World)
- Q2: Political Science (Indian Constitution or Polity)
- Q3: General Science (Physics, Chemistry, or Biology)

Rules:
- Each question must be UNIQUE and not repeat any previous topic
- Each question must be strictly BILINGUAL (English + Bengali)
- Each option must be BILINGUAL (English / Bengali)
- Provide correct answer and detailed explanation in both languages

Return ONLY a valid JSON array like this:
[
  {{
    "subject": "History",
    "question_en": "Question in English?",
    "question_bn": "প্রশ্ন বাংলায়?",
    "option_a_en": "Option A English",
    "option_a_bn": "অপশন এ বাংলা",
    "option_b_en": "Option B English",
    "option_b_bn": "অপশন বি বাংলা",
    "option_c_en": "Option C English",
    "option_c_bn": "অপশন সি বাংলা",
    "option_d_en": "Option D English",
    "option_d_bn": "অপশন ডি বাংলা",
    "answer": "A",
    "explanation_en": "Explanation in English.",
    "explanation_bn": "ব্যাখ্যা বাংলায়।"
  }}
]
Return ONLY the JSON array. No extra text."""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 3000,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=body
    )
    print("Claude API status:", response.status_code)
    data = response.json()
    raw = data["content"][0]["text"]
    print("Claude response:", raw[:500])
    mcqs = json.loads(raw)
    return mcqs

def save_to_sheet(sheet, mcqs, today):
    for mcq in mcqs:
        row = [
            today,
            "Morning",
            mcq["subject"],
            mcq["question_en"],
            mcq["question_bn"],
            f"{mcq['option_a_en']} / {mcq['option_a_bn']}",
            f"{mcq['option_b_en']} / {mcq['option_b_bn']}",
            f"{mcq['option_c_en']} / {mcq['option_c_bn']}",
            f"{mcq['option_d_en']} / {mcq['option_d_bn']}",
            mcq["answer"],
            mcq["explanation_en"],
            mcq["explanation_bn"]
        ]
        sheet.append_row(row)
        print(f"Saved: {mcq['subject']}")

def send_poll(question_en, question_bn, options, q_number):
    question_text = f"📝 Q{q_number}. {question_en}\n{question_bn}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "question": question_text[:300],
        "options": options,
        "is_anonymous": True,
        "type": "regular",
        "allows_multiple_answers": False
    }
    r = requests.post(url, json=payload)
    print(f"Poll {q_number} status:", r.status_code)
    print(f"Poll {q_number} response:", r.text[:200])

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=payload)
    print("Message status:", r.status_code)

def main():
    print("Starting Morning Bot...")
    today = datetime.now().strftime("%d-%m-%Y")

    sheet = get_sheet()
    previous = get_previous_questions(sheet)
    print(f"Found {len(previous)} previous questions")

    mcqs = generate_mcqs(previous)
    print(f"Generated {len(mcqs)} MCQs")

    save_to_sheet(sheet, mcqs, today)

    # Send intro message
    intro = (
        "🌅 <b>Gyan Mukut Daily Challenge</b>\n"
        "🎯 Target: WBCS | SSC CGL | RRB NTPC | State PSC\n"
        "━━━━━━━━━━━━━━━━\n"
        "👇 Vote on all 3 polls below!\n"
        "⏰ Answers + Explanations tonight at <b>10:00 PM</b>"
    )
    send_message(intro)

    # Send 3 polls
    subjects = ["📚 History / ইতিহাস",
                "⚖️ Political Science / রাষ্ট্রবিজ্ঞান",
                "🔬 General Science / সাধারণ বিজ্ঞান"]

    for i, mcq in enumerate(mcqs):
        options = [
            f"A) {mcq['option_a_en']} / {mcq['option_a_bn']}",
            f"B) {mcq['option_b_en']} / {mcq['option_b_bn']}",
            f"C) {mcq['option_c_en']} / {mcq['option_c_bn']}",
            f"D) {mcq['option_d_en']} / {mcq['option_d_bn']}"
        ]
        question = f"{subjects[i]}\n{mcq['question_en']}\n{mcq['question_bn']}"
        send_poll(question, "", options, i+1)

    print("Morning bot done!")

main()
