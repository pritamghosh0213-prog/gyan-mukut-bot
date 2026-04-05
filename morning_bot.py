import os
import json
import requests
from datetime import datetime
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

def get_previous_questions(sheet):
    try:
        records = sheet.get_all_records()
        previous = []
        for row in records:
            if row.get("Question_EN"):
                previous.append(row["Question_EN"])
        return previous
    except Exception as e:
        print(f"Sheet read error: {e}")
        return []

def generate_mcqs(previous_questions):
    prev_text = "\n".join(previous_questions[-20:]) if previous_questions else "None yet"

    prompt = f"""You are a master educator for Indian competitive exams.

Previously asked questions - DO NOT repeat:
{prev_text}

Generate exactly 3 MCQs:
Q1: Indian History
Q2: Indian Constitution / Polity  
Q3: General Science

STRICT RULES:
- Bilingual: English + Bengali for question and all options
- Return ONLY raw JSON array, no markdown, no backticks, no explanation

JSON format:
[
  {{
    "subject": "History",
    "question_en": "English question?",
    "question_bn": "Bengali question?",
    "option_a_en": "English A",
    "option_a_bn": "Bengali A",
    "option_b_en": "English B",
    "option_b_bn": "Bengali B",
    "option_c_en": "English C",
    "option_c_bn": "Bengali C",
    "option_d_en": "English D",
    "option_d_bn": "Bengali D",
    "answer": "B",
    "explanation_en": "English explanation.",
    "explanation_bn": "Bengali explanation."
  }},
  {{
    "subject": "Political Science",
    "question_en": "...",
    "question_bn": "...",
    "option_a_en": "...", "option_a_bn": "...",
    "option_b_en": "...", "option_b_bn": "...",
    "option_c_en": "...", "option_c_bn": "...",
    "option_d_en": "...", "option_d_bn": "...",
    "answer": "A",
    "explanation_en": "...",
    "explanation_bn": "..."
  }},
  {{
    "subject": "General Science",
    "question_en": "...",
    "question_bn": "...",
    "option_a_en": "...", "option_a_bn": "...",
    "option_b_en": "...", "option_b_bn": "...",
    "option_c_en": "...", "option_c_bn": "...",
    "option_d_en": "...", "option_d_bn": "...",
    "answer": "C",
    "explanation_en": "...",
    "explanation_bn": "..."
  }}
]"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "llama3-8b-8192",
        "messages": [
            {
                "role": "system",
                "content": "You are a JSON generator. Return only valid raw JSON arrays. Never use markdown or backticks."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 3000,
        "temperature": 0.7
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=30
    )
    print("Groq status:", response.status_code)
    print("Groq full response:", response.text[:500])

    if response.status_code != 200:
        raise Exception(f"Groq API failed: {response.status_code} - {response.text}")

    data = response.json()
    raw = data["choices"][0]["message"]["content"].strip()
    print("Raw content:", raw[:300])

    raw = raw.replace("```json", "").replace("```", "").strip()
    start = raw.find("[")
    end = raw.rfind("]") + 1
    raw = raw[start:end]

    mcqs = json.loads(raw)
    print(f"Parsed {len(mcqs)} MCQs successfully")
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
        print(f"Saved to sheet: {mcq['subject']}")

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

def send_poll(question_text, options, q_number):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "question": question_text[:300],
        "options": [opt[:100] for opt in options],
        "is_anonymous": True,
        "type": "regular",
        "allows_multiple_answers": False
    }
    r = requests.post(url, json=payload)
    print(f"Poll {q_number} status:", r.status_code)
    print(f"Poll {q_number} response:", r.text[:200])

def main():
    print("Starting Morning Bot...")
    today = datetime.now().strftime("%d-%m-%Y")

    print("Connecting to Google Sheet...")
    sheet = get_sheet()
    print("Sheet connected!")

    previous = get_previous_questions(sheet)
    print(f"Found {len(previous)} previous questions")

    print("Generating MCQs with Groq...")
    mcqs = generate_mcqs(previous)

    print("Saving to sheet...")
    save_to_sheet(sheet, mcqs, today)

    print("Sending to Telegram...")
    intro = (
        "🌅 <b>Gyan Mukut Daily Challenge</b>\n"
        "🎯 WBCS | SSC CGL | RRB NTPC | State PSC\n"
        "━━━━━━━━━━━━━━━━\n"
        "👇 Vote on all 3 polls below!\n"
        "⏰ Answers tonight at <b>10:00 PM</b>"
    )
    send_message(intro)

    subjects = [
        "📚 History / ইতিহাস",
        "⚖️ Polity / রাষ্ট্রবিজ্ঞান",
        "🔬 Science / বিজ্ঞান"
    ]

    for i, mcq in enumerate(mcqs):
        options = [
            f"A) {mcq['option_a_en']} / {mcq['option_a_bn']}",
            f"B) {mcq['option_b_en']} / {mcq['option_b_bn']}",
            f"C) {mcq['option_c_en']} / {mcq['option_c_bn']}",
            f"D) {mcq['option_d_en']} / {mcq['option_d_bn']}"
        ]
        q_text = f"{subjects[i]}\nQ{i+1}. {mcq['question_en']}\n{mcq['question_bn']}"
        send_poll(q_text, options, i+1)

    print("✅ Morning bot completed successfully!")

main()
