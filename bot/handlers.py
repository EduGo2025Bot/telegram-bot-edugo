# bot/handlers.py  –  לוגיקת הבוט, סינון קבצים, Rate-limit, שליחת שאלות
import os, tempfile, logging
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    constants,
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.qa_generator import build_qa_from_text, extract_text, pick_from_bank

# ─────────────────────────────  הגדרות  ─────────────────────────────
MAX_FILE_MB     = 5                          # משקל מקסימלי לקובץ (MB)
ALLOWED_TYPES   = {".pdf", ".docx", ".pptx"} # סיומות מותרים
DAILY_LIMIT     = 3                          # כמה קבצים מותר למשתמש ביום
MAX_QUESTIONS   = 6                          # כמה שאלות נשלחות בכל פעם

# ─────────────  Rate-limit בזיכרון  ─────────────
_user_usage: dict[int, list[datetime]] = defaultdict(list)

def _allowed(user_id: int) -> bool:
    now = datetime.utcnow()
    _user_usage[user_id] = [
        t for t in _user_usage[user_id] if now - t < timedelta(days=1)
    ]
    if len(_user_usage[user_id]) >= DAILY_LIMIT:
        return False
    _user_usage[user_id].append(now)
    return True

# ─────────────  /start – תפריט ראשוני  ─────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [KeyboardButton("🗂️ שאלות מהמַאגר"),
         KeyboardButton("📄 העלאת קובץ")]
    ]
    msg = (
        "שלום! בחר כיצד תרצה להתאמן:\n"
        "• 🗂️ – שליפה אקראית מהמַאגר המובנה\n"
        "• 📄 – העלאת PDF / DOCX / PPTX (≤5 MB, ≤20 עמודים)\n"
        f"*** ניתן להעלות עד {DAILY_LIMIT} קבצים ביום לכל משתמש ***"
    )
    await update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True),
    )

# ─────────────  טיפול בבחירה מהתפריט  ─────────────
async def menu_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text.startswith("🗂️"):
        qas = pick_from_bank(MAX_QUESTIONS)
        await send_questions(update, qas)
    elif text.startswith("📄"):
        await update.message.reply_text("שלח עכשיו קובץ ואפיק ממנו שאלות.")
    else:
        await update.message.reply_text("לא זיהיתי את הבחירה, נסה שוב /start.")

# ─────────────  קובץ שהתקבל  ─────────────
async def doc_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    uid = update.effective_user.id

    # Rate-limit
    if not _allowed(uid):
        await update.message.reply_text("הגעת למכסה היומית (3 קבצים). נסה שוב מחר 🙂")
        return

    # משקל וסיומת
    if doc.file_size > MAX_FILE_MB * 1024 * 1024:
        await update.message.reply_text("הקובץ גדול מדי (>5 MB).")
        return
    ext = Path(doc.file_name).suffix.lower()
    if ext not in ALLOWED_TYPES:
        await update.message.reply_text("פורמט לא נתמך (PDF / DOCX / PPTX בלבד).")
        return

    # הורדה זמנית
    with tempfile.TemporaryDirectory() as tmp:
        path = await doc.get_file().download_to_drive(custom_path=tmp)
        text = extract_text(path)
        if not text.strip():
            await update.message.reply_text("לא הצלחתי לחלץ טקסט מהקובץ 🤔")
            return
        qas = build_qa_from_text(text, MAX_QUESTIONS)

    await send_questions(update, qas)

# ─────────────  שליחת שאלות עם כפתורים  ─────────────
async def send_questions(update: Update, qas):
    for q in qas:
        buttons = [
            InlineKeyboardButton(
                opt.split(".")[0].strip() if q["type"] == "multiple" else opt,
                callback_data=opt.split(".")[0].strip() if q["type"] == "multiple" else opt,
            )
            for opt in q["options"]
        ]
        buttons.append(InlineKeyboardButton("דלג ⏭️", callback_data="skip"))
        await update.message.reply_text(
            q["question"],
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([buttons]),
        )

# ─────────────  רישום ה-handlers  ─────────────
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_choice))
    app.add_handler(MessageHandler(filters.Document.ALL, doc_received))
