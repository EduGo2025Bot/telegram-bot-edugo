import os, asyncio, json, random
from pathlib import Path
from telegram.error import RetryAfter, TelegramError

from flask import Flask, request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------- הגדרות בסיס ----------
TOKEN = os.environ["TOKEN"]
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"

# ---------- טעינת שאלות ----------
QUESTIONS = json.loads(
    Path(__file__).with_name("questions.json").read_text(encoding="utf-8")
)

# ---------- Telegram & Flask ----------
flask_app   = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()

user_state: dict[int, dict] = {}        # שאלה אחרונה לכל צ'אט

# ---------- כלי-עזר ----------
def build_keyboard(opts: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for o in opts:
        if ". " in o:
            # אופציה של רב־ברירה מסוג "א. טקסט..."
            display = o.split(".")[0].strip()    # רק האות לפני הנקודה
            callback = display                   # שולחים אותה חזרה כ־callback_data
        else:
            # נכון/לא נכון או כל טקסט חופשי אחר
            display = o
            callback = o
        buttons.append(InlineKeyboardButton(text=display, callback_data=callback))

    # תמיד מוסיפים כפתור דילוג
    buttons.append(InlineKeyboardButton("דלג ⏭️", callback_data="skip"))
    # מחזירים שורה אחת של כפתורים
    return InlineKeyboardMarkup([buttons])

async def send_question(bot, chat_id: int):
    q = random.choice(QUESTIONS)
    user_state[chat_id] = q
    text = q["question"] + "\n\n" + "\n".join(q["options"])
    await bot.send_message(chat_id, text, reply_markup=build_keyboard(q["options"]))

async def send_feedback(bot, chat_id: int, text: str):
    await bot.send_message(chat_id, text)

# ---------- Handlers ----------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_question(ctx.bot, update.effective_chat.id)

async def on_press(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    chatId = q.message.chat_id
    data   = q.data
    await q.answer()

    # נועל את הכפתורים בהודעה הישנה (הטקסט נשאר)
    await q.edit_message_reply_markup(None)

    # דילוג → אין פידבק, רק שאלה חדשה
    if data == "skip":
        await send_question(ctx.bot, chatId)
        return

    current = user_state.get(chatId)
    if not current:                       # בטיחות, לא אמור לקרות
        await send_feedback(ctx.bot, chatId, "שלח ‎/start כדי להתחיל.")
        return

    correct = current["correct"]
    if data == correct:
        await send_feedback(ctx.bot, chatId, "✅ תשובה נכונה!")
    else:
        await send_feedback(ctx.bot, chatId, f"❌ טעות. התשובה הנכונה היא: {correct}")

    # מיד שאלה חדשה
    await send_question(ctx.bot, chatId)

application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CallbackQueryHandler(on_press))

# ---------- Flask ↔ Telegram ----------
@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    upd = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(upd))
    return "ok", 200

# ---------- רישום Webhook באתחול ----------
async def init():
    # מנקה Webhook קודמים כדי להימנע מ-RetryAfter
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
    except TelegramError:
        pass

    # רישום עם טיפול ב-RetryAfter (עד 3 ניסיונות)
    for _ in range(3):
        try:
            await application.bot.set_webhook(WEBHOOK_URL)
            break
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)

    await application.initialize()

asyncio.run(init())
