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

def get_all_rows(sheet):
    all_rows = sheet.get_all_values()
    if not all_rows:
        return []
    results = []
    for row in all_rows[1:]:
        if len(row) >= 12 and row[0]:
            row_dict = {
                "Date": row[0], "Status": row[1], "Subject": row[2],
                "Question_EN": row[3], "Question_BN": row[4],
                "OptionA": row[5], "OptionB": row[6],
                "OptionC": row[7], "OptionD": row[8],
                "Answer": row[9], "Explanation_EN": row[10],
                "Explanation_BN": row[11],
                "TotalVotes": int(row[12]) if len(row) > 12 and row[12] else 0,
                "CorrectVotes": int(row[13]) if len(row) > 13 and row[13] else 0,
                "Difficulty": row[14] if len(row) > 14 and row[14] else "Medium"
            }
            results.append(row_dict)
    return results

def analyse_performance(all_rows):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%d-%m-%Y")
    subject_stats = {}
    total_participation = 0
    recent_rows = [r for r in all_rows if r["Status"] in ["Morning","Night"]][-30:]

    for row in recent_rows:
        subj = row["Subject"]
        total = row["TotalVotes"]
        correct = row["CorrectVotes"]
        if subj not in subject_stats:
            subject_stats[subj] = {"total": 0, "correct": 0, "count": 0}
        subject_stats[subj]["total"] += total
        subject_stats[subj]["correct"] += correct
        subject_stats[subj]["count"] += 1
        total_participation += total

    weak_topics = []
    for subj, stats in subject_stats.items():
        if stats["total"] > 0:
            accuracy = (stats["correct"] / stats["total"]) * 100
            if accuracy < 50:
                weak_topics.append(subj)

    avg_participation = total_participation / max(len(recent_rows), 1)

    return {
        "weak_topics": weak_topics,
        "avg_participation": avg_participation,
        "subject_stats": subject_stats
    }

def decide_difficulty(performance):
    weak = performance["weak_topics"]
    avg = performance["avg_participation"]
    if len(weak) >= 2:
        return "Easy", "Many students are struggling — let's build confidence with easier questions today! 💪"
    elif avg > 50:
        return "Hard", "Great participation lately! Time to level up with harder questions! 🔥"
    else:
        return "Medium", "Steady progress! Keeping it balanced today. 📚"

def get_previous_questions(all_rows):
    return [r["Question_EN"] for r in all_rows if r.get("Question_EN")]

def generate_mcqs(previous_questions, difficulty, weak_topics, performance):
    prev_text = "\n".join(previous_questions[-30:]) if previous_questions else "None yet"
    weak_text = ", ".join(weak_topics) if weak_topics else "None"

    prompt = f"""You are a master educator for Indian competitive exams (WBCS, SSC CGL, RRB NTPC, State PSC).

PERFORMANCE DATA:
- Students are weak in: {weak_text}
- Today's difficulty level decided by AI: {difficulty}
- Average recent participation: {performance['avg_participation']:.0f} votes per question

Previously asked questions - DO NOT repeat:
{prev_text}

YOUR TASK:
Generate exactly 3 NEW MCQs:
Q1: Indian History
Q2: Indian Constitution / Polity
Q3: General Science

DIFFICULTY RULES:
- If Easy: Ask factual, direct questions with obvious wrong options
- If Medium: Ask conceptual questions with tricky options
- If Hard: Ask analytical questions with very close options

FOCUS: If a subject appears in weak topics, make that question slightly easier to rebuild confidence.

STRICT RULES:
- Bilingual: English + Bengali for question and all options
- Return ONLY raw JSON array, no markdown, no backticks

JSON format:
[
  {{
    "subject": "History",
    "question_en": "English question?",
    "question_bn": "Bengali question?",
    "option_a_en": "English A", "option_a_bn": "Bengali A",
    "option_b_en": "English B", "option_b_bn": "Bengali B",
    "option_c_en": "English C", "option_c_bn": "Bengali C",
    "option_d_en": "English D", "option_d_bn": "Bengali D",
    "answer": "B",
    "explanation_en": "English explanation.",
    "explanation_bn": "Bengali explanation."
  }},
  {{
    "subject": "Political Science",
    "question_en": "...", "question_bn": "...",
    "option_a_en": "...", "option_a_bn": "...",
    "option_b_en": "...", "option_b_bn": "...",
    "option_c_en": "...", "option_c_bn": "...",
    "option_d_en": "...", "option_d_bn": "...",
    "answer": "A",
    "explanation_en": "...", "explanation_bn": "..."
  }},
  {{
    "subject": "General Science",
    "question_en": "...", "question_bn": "...",
    "option_a_en": "...", "option_a_bn": "...",
    "option_b_en": "...", "option_b_bn": "...",
    "option_c_en": "...", "option_c_bn": "...",
    "option_d_en": "...", "option_d_bn": "...",
    "answer": "C",
    "explanation_en": "...", "explanation_bn": "..."
  }}
]"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a JSON generator. Return only valid raw JSON arrays. Never use markdown or backticks."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 3000,
        "temperature": 0.7
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers, json=body, timeout=30
    )
    print("Groq status:", response.status_code)
    if response.status_code != 200:
        raise Exception(f"Groq failed: {response.status_code} - {response.text}")
    data = response.json()
    raw = data["choices"][0]["message"]["content"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    start = raw.find("[")
    end = raw.rfind("]") + 1
    raw = raw[start:end]
    mcqs = json.loads(raw)
    print(f"Generated {len(mcqs)} MCQs at {difficulty} difficulty")
    return mcqs

def save_to_sheet(sheet, mcqs, today, difficulty):
    for mcq in mcqs:
        row = [
            today, "Morning", mcq["subject"],
            mcq["question_en"], mcq["question_bn"],
            f"{mcq['option_a_en']} / {mcq['option_a_bn']}",
            f"{mcq['option_b_en']} / {mcq['option_b_bn']}",
            f"{mcq['option_c_en']} / {mcq['option_c_bn']}",
            f"{mcq['option_d_en']} / {mcq['option_d_bn']}",
            mcq["answer"], mcq["explanation_en"], mcq["explanation_bn"],
            0, 0, difficulty
        ]
        sheet.append_row(row)
        print(f"Saved: {mcq['subject']}")

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload)
    print("Message status:", r.status_code)

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

def main():
    print("Starting Agentic Morning Bot...")
    today = datetime.now().strftime("%d-%m-%Y")

    sheet = get_sheet()
    all_rows = get_all_rows(sheet)
    print(f"Loaded {len(all_rows)} historical rows")

    performance = analyse_performance(all_rows)
    print(f"Weak topics: {performance['weak_topics']}")
    print(f"Avg participation: {performance['avg_participation']:.0f}")

    difficulty, difficulty_message = decide_difficulty(performance)
    print(f"AI decided difficulty: {difficulty}")

    previous_questions = get_previous_questions(all_rows)
    mcqs = generate_mcqs(previous_questions, difficulty, performance["weak_topics"], performance)

    save_to_sheet(sheet, mcqs, today, difficulty)

    weak_text = ""
    if performance["weak_topics"]:
        weak_text = f"\n⚠️ Focus area today: <b>{', '.join(performance['weak_topics'])}</b>"

    difficulty_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}
    intro = (
        f"🌅 <b>Gyan Mukut Daily Challenge</b>\n"
        f"🎯 WBCS | SSC CGL | RRB NTPC | State PSC\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{difficulty_emoji.get(difficulty,'🟡')} <b>Today's Level: {difficulty}</b>\n"
        f"🤖 {difficulty_message}"
        f"{weak_text}\n\n"
        f"👇 Vote on all 3 polls below!\n"
        f"⏰ Answers tonight at <b>10:00 PM</b>"
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

    print("✅ Agentic Morning Bot completed!")

main()
