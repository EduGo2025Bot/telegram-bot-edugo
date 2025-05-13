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
    CallbackQueryHandler,
    filters,
)

from bot.qa_generator import build_qa_from_text, extract_text, pick_from_bank

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    logger.info(f"Start command from user {update.effective_user.id}")
    
    try:
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
        logger.info("Start menu sent successfully")
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("אירעה שגיאה, אנא נסה שוב מאוחר יותר.")

# ─────────────  טיפול בבחירה מהתפריט  ─────────────
async def menu_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        logger.warning("Received menu_choice with no text")
        return
        
    text = update.message.text.strip()
    user_id = update.effective_user.id
    logger.info(f"Menu choice from user {user_id}: {text}")
    
    try:
        # טיפול בפקודת start שנשלחה כטקסט רגיל
        if text == "/start":
            await start(update, ctx)
            return
            
        # תפריט ראשי - בחירות
        if "🗂️" in text:
            logger.info(f"User {user_id} selected bank questions")
            await update.message.reply_text("מכין שאלות מהמאגר...")
            qas = pick_from_bank(MAX_QUESTIONS)
            await send_questions(update, qas)
        elif "📄" in text:
            logger.info(f"User {user_id} selected file upload")
            await update.message.reply_text("שלח עכשיו קובץ ואפיק ממנו שאלות.")
        else:
            # לא זוהתה בחירה תקינה
            logger.warning(f"User {user_id} sent unrecognized text: {text}")
            await update.message.reply_text("לא זיהיתי את הבחירה, נסה שוב להקליד /start")
    except Exception as e:
        logger.error(f"Error in menu_choice: {e}")
        await update.message.reply_text("אירעה שגיאה, אנא נסה שוב מאוחר יותר.")

# ─────────────  קובץ שהתקבל  ─────────────
async def doc_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        logger.warning("Received doc_received with no document")
        return
        
    doc = update.message.document
    uid = update.effective_user.id
    logger.info(f"Document received from user {uid}: {doc.file_name}")

    try:
        # Rate-limit
        if not _allowed(uid):
            logger.info(f"User {uid} hit daily limit")
            await update.message.reply_text("הגעת למכסה היומית (3 קבצים). נסה שוב מחר 🙂")
            return

        # משקל וסיומת
        if doc.file_size > MAX_FILE_MB * 1024 * 1024:
            logger.info(f"File too large: {doc.file_size} bytes")
            await update.message.reply_text(f"הקובץ גדול מדי (>{MAX_FILE_MB} MB).")
            return
            
        ext = Path(doc.file_name).suffix.lower()
        if ext not in ALLOWED_TYPES:
            logger.info(f"Unsupported file type: {ext}")
            await update.message.reply_text(f"פורמט לא נתמך ({', '.join(ALLOWED_TYPES)} בלבד).")
            return

        # הורדה זמנית
        with tempfile.TemporaryDirectory() as tmp:
            status_msg = await update.message.reply_text("מעבד את הקובץ...")
            
            # תיקון נתיב הקובץ
            file_path = os.path.join(tmp, doc.file_name)
            file_obj = await doc.get_file()
            await file_obj.download_to_drive(file_path)
            
            logger.info(f"File downloaded to {file_path}")
            text = extract_text(file_path)
            
            if not text or not text.strip():
                logger.warning(f"Could not extract text from file")
                await status_msg.edit_text("לא הצלחתי לחלץ טקסט מהקובץ 🤔")
                return
                
            logger.info(f"Text extracted, length: {len(text)} chars")
            await status_msg.edit_text("מכין שאלות מהקובץ...")
            
            qas = build_qa_from_text(text, MAX_QUESTIONS)
            logger.info(f"Generated {len(qas)} questions")

        await send_questions(update, qas)
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        await update.message.reply_text("אירעה שגיאה בעיבוד הקובץ, אנא נסה שוב מאוחר יותר.")

# ─────────────  מענה על כפתור בשאלה  ─────────────
async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        logger.info(f"Button callback from user {user_id}: {query.data}")
        await query.answer()  # אישור קבלת הלחיצה
        
        user_choice = query.data
        question_text = query.message.text
        
        if user_choice == "skip":
            logger.info(f"User {user_id} skipped question")
            await query.edit_message_text(
                f"{question_text}\n\n⏭️ דילגת על השאלה",
                reply_markup=None
            )
        else:
            # כאן צריך להוסיף לוגיקה לבדיקת התשובה הנכונה
            # כרגע פשוט מציג את הבחירה של המשתמש
            logger.info(f"User {user_id} answered: {user_choice}")
            await query.edit_message_text(
                f"{question_text}\n\nבחרת: {user_choice}",
                reply_markup=None
            )
    except Exception as e:
        logger.error(f"Error in button callback: {e}")
        try:
            await query.edit_message_text(
                f"{question_text}\n\nאירעה שגיאה בעיבוד התשובה.",
                reply_markup=None
            )
        except:
            pass

# ─────────────  שליחת שאלות עם כפתורים  ─────────────
async def send_questions(update: Update, qas):
    user_id = update.effective_user.id
    logger.info(f"Sending {len(qas)} questions to user {user_id}")
    
    try:
        for i, q in enumerate(qas):
            # מסדר את הכפתורים בשורה או בטור לפי סוג השאלה
            if q["type"] == "multiple":
                # שאלות אמריקאיות - כפתור לכל שורה
                keyboard = []
                for opt in q["options"]:
                    # לוקח רק את האות מהאפשרות (א, ב, ג וכו')
                    option_letter = opt.split(".")[0].strip() if "." in opt else opt
                    keyboard.append([InlineKeyboardButton(opt, callback_data=option_letter)])
            else:
                # שאלות נכון/לא נכון - כפתורים באותה שורה
                keyboard = [[
                    InlineKeyboardButton(opt, callback_data=opt)
                    for opt in q["options"]
                ]]
                
            # מוסיף כפתור דילוג
            keyboard.append([InlineKeyboardButton("דלג ⏭️", callback_data="skip")])
            
            # מוסיף מספור לשאלות
            question_text = f"שאלה {i+1}/{len(qas)}:\n{q['question']}"
            
            await update.message.reply_text(
                question_text,
                parse_mode=constants.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        
        logger.info(f"Successfully sent all questions to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending questions: {e}")
        await update.message.reply_text("אירעה שגיאה בשליחת השאלות, אנא נסה שוב מאוחר יותר.")

# ─────────────  רישום ה-handlers  ─────────────
def register_handlers(app):
    logger.info("Registering handlers")
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_choice))
    app.add_handler(MessageHandler(filters.Document.ALL, doc_received))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Handlers registered successfully")
