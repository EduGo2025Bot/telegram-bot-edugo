
import os, tempfile, logging
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
import re
import random
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from qa_generator import build_qa_from_text, extract_text, pick_from_bank, load_bank

MAX_FILE_MB     = 5
ALLOWED_TYPES   = {".pdf", ".docx", ".pptx"}
DAILY_LIMIT     = 3
MAX_QUESTIONS   = 6

# מבני נתונים
_user_usage: dict[int, list[datetime]] = defaultdict(list)
pending_questions: dict[int, list[dict]] = {}
pending_correct_answers: dict[int, str] = {}
last_question_sent: dict[int, dict] = {}
user_source: dict[int, str] = {}
user_gpt_qas: dict[int, list[dict]] = {}

def _allowed(user_id: int) -> bool:
    now = datetime.utcnow()
    _user_usage[user_id] = [t for t in _user_usage[user_id] if now - t < timedelta(days=1)]
    if len(_user_usage[user_id]) >= DAILY_LIMIT:
        return False
    _user_usage[user_id].append(now)
    return True

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    buttons = [[
        KeyboardButton("🗂️ שאלות מהמַאגר"),
        KeyboardButton("📄 העלאת קובץ")
    ]]
    msg = (
        "שלום! בחר כיצד תרצה להתאמן:\n"
        "• 🗂️ – שליפה אקראית מהמַאגר המובנה\n"
        "• 📄 – העלאת PDF / DOCX / PPTX (≤5 MB, ≤20 עמודים)\n"
        f"*** ניתן להעלות עד {DAILY_LIMIT} קבצים ביום לכל משתמש ***"
    )
    await update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False),
    )

async def menu_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if text.startswith("🗂️"):
        user_source[uid] = "bank"
        qas = random.sample(load_bank(), k=min(MAX_QUESTIONS, len(load_bank())))
        await send_questions(update.message, qas)
    elif text.startswith("📄"):
        user_source[uid] = "gpt"
        await update.message.reply_text("שלח עכשיו קובץ ואפיק ממנו שאלות.")
    else:
        await update.message.reply_text("לא זיהיתי את הבחירה, נסה שוב /start.")

async def doc_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    uid = update.effective_user.id

    if not _allowed(uid):
        await update.message.reply_text("הגעת למכסה היומית (3 קבצים). נסה שוב מחר 🙂")
        return

    if doc.file_size > MAX_FILE_MB * 1024 * 1024:
        await update.message.reply_text("הקובץ גדול מדי (>5 MB).")
        return

    ext = Path(doc.file_name).suffix.lower()
    if ext not in ALLOWED_TYPES:
        await update.message.reply_text("פורמט לא נתמך (PDF / DOCX / PPTX בלבד).")
        return

    try:
        with tempfile.TemporaryDirectory() as tmp:
            filename = os.path.join(tmp, doc.file_name)
            file = await doc.get_file()
            path = await file.download_to_drive(custom_path=filename)
            text = extract_text(path)
            if not text.strip():
                await update.message.reply_text("לא הצלחתי לחלץ טקסט מהקובץ 🤔")
                return

            user_source[uid] = "gpt"
            qas_raw = build_qa_from_text(text, 6)
            qas_all = qas_raw["questions"] if isinstance(qas_raw, dict) else qas_raw
            user_gpt_qas[uid] = qas_all.copy()
            qas = random.sample(user_gpt_qas[uid], k=min(MAX_QUESTIONS, len(user_gpt_qas[uid])))
            await send_questions(update.message, qas)

    except Exception as e:
        print("❌ שגיאה בעיבוד הקובץ:", e)
        await update.message.reply_text("אירעה שגיאה בעיבוד הקובץ 😞")

async def send_questions(message, qas):
    uid = message.from_user.id
    if not isinstance(qas, list) or not qas:
        await message.reply_text("😢 לא הצלחתי להפיק שאלות.")
        return
    pending_questions[uid] = qas[1:]
    correct = qas[0].get("correct") or qas[0].get("answer")
    pending_correct_answers[uid] = str(correct).strip()
    await send_single_question(message, qas[0])

async def send_single_question(message, q):
    uid = message.from_user.id
    correct = q.get("correct") or q.get("answer")
    pending_correct_answers[uid] = str(correct).strip()
    last_question_sent[uid] = q

    buttons = []
    qtype = q.get("type", "").lower()

    for idx, opt in enumerate(q["options"]):
        opt = opt.strip()
        if qtype == "multiple":
            match = re.match(r"^([א-ת])\.\s*(.+)", opt)
            if match:
                key = match.group(1).strip()
                text = opt
            else:
                key = chr(ord("א") + idx)
                text = f"{key}. {opt}"
            callback = key
        else:
            text = opt
            callback = opt
        buttons.append(InlineKeyboardButton(text=text, callback_data=callback))

    buttons.append(InlineKeyboardButton("⏭️ דלג", callback_data="skip"))

    await message.reply_text(
        q["question"],
        parse_mode=constants.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[b] for b in buttons]),
    )

async def handle_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    user_answer = query.data.strip()
    current_q = last_question_sent.get(uid)
    correct = (current_q.get("correct") or current_q.get("answer") or "").strip()
    qtype = current_q.get("type", "").lower() if current_q else ""

    # המשך
    if user_answer == "continue_yes":
        source = user_source.get(uid, "bank")

        if source == "gpt" and uid in user_gpt_qas:
            qas_pool = user_gpt_qas[uid]
            if not qas_pool:
                await query.message.reply_text("🎉 אין עוד שאלות מהקובץ שהעלית.")
                return
            qas = random.sample(qas_pool, k=min(MAX_QUESTIONS, len(qas_pool)))
        else:
            qas = random.sample(load_bank(), k=min(MAX_QUESTIONS, len(load_bank())))

        qas = [q for q in qas if "question" in q and "options" in q and isinstance(q["options"], list)]

        if not qas:
            await query.message.reply_text("⚠️ לא נמצאו שאלות תקינות במקור.")
            return

        pending_questions[uid] = qas[1:]
        last_question_sent[uid] = qas[0]
        await send_single_question(query.message, qas[0])
        return

    if user_answer == "continue_no":
        await query.message.reply_text("תודה! נתראה בפעם הבאה 👋")
        return

    # תשובה רגילה
    if user_answer == "skip":
        await query.message.reply_text("⬇️ דילגת על השאלה.")
    elif correct:
        # שלוף את התשובה המלאה מתוך האפשרויות
        full_answer = correct
        if current_q and "options" in current_q:
            for opt in current_q["options"]:
                opt = opt.strip()
                if qtype == "multiple":
                    match = re.match(r"^([א-ת])\.\s*(.+)", opt)
                    if match and match.group(1).strip() == correct:
                        full_answer = opt
                        break
                else:
                    if opt.strip().lower() == correct.lower():
                        full_answer = opt
                        break

        if user_answer == correct:
            await query.message.reply_text("✅ תשובה נכונה!")
        else:
            await query.message.reply_text(f"❌ תשובה שגויה.\nהתשובה הנכונה היא: {full_answer}")
    else:
        await query.message.reply_text("⚠️ לא הצלחתי לבדוק אם התשובה נכונה.")

    # שלח שאלה הבאה אם קיימת
    if pending_questions.get(uid):
        while pending_questions[uid]:
            next_q = pending_questions[uid].pop(0)
            if "question" in next_q and "options" in next_q:
                last_question_sent[uid] = next_q
                await send_single_question(query.message, next_q)
                return

    # סיום סט
    await query.message.reply_text(
        "🎉 סיימת את כל השאלות! רוצה להמשיך עם סט חדש?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ כן", callback_data="continue_yes"),
             InlineKeyboardButton("❌ לא", callback_data="continue_no")]
        ])
    )


def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_choice))
    app.add_handler(MessageHandler(filters.Document.ALL, doc_received))
    app.add_handler(CallbackQueryHandler(handle_answer))
