# bot.py  – גרסה יציבה  ✅
import os, asyncio, json, random
from pathlib import Path

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter, TelegramError
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ---------- הגדרות ----------
TOKEN      = os.environ["TOKEN"]                # ה-token מבוטפאדר
BASE_URL   = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"

# ---------- שאלות ----------
QUESTIONS = json.loads(
    Path(__file__).with_name("questions.json").read_text(encoding="utf-8")
)

# ---------- Telegram & Flask ----------
flask_app   = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()
user_state: dict[int, dict] = {}               # שאלה אחרונה לכל צ'אט

# ---------- כלי-עזר ----------
def build_keyboard(opts: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for o in opts:
        cb = o.split(".")[0].strip() if ". " in o else o      # "א. ..." → "א"
        buttons.append(InlineKeyboardButton(o, callback_data=cb))
    buttons.append(InlineKeyboardButton("דלג ⏭️", callback_data="skip"))
    return InlineKeyboardMarkup([buttons])

async def send_question(bot, chat_id: int):
    q = random.choice(QUESTIONS)
    user_state[chat_id] = q
    text = q["question"] + "\n\n" + "\n".join(q["options"])
    await bot.send_message(chat_id, text, reply_markup=build_keyboard(q["options"]))

async def send_feedback(bot, chat_id: int, txt: str):
    await bot.send_message(chat_id, txt)

# ---------- Handlers ----------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_question(ctx.bot, update.effective_chat.id)

async def on_press(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    chatId = q.message.chat_id
    data   = q.data
    await q.answer()
    await q.edit_message_reply_markup(None)          # נועל כפתורים ישנים

    if data == "skip":                               # דילוג
        await send_question(ctx.bot, chatId)
        return

    current = user_state.get(chatId)
    if not current:
        await send_feedback(ctx.bot, chatId, "שלח ‎/start כדי להתחיל.")
        return

    correct = current["correct"]
    if data == correct:
        await send_feedback(ctx.bot, chatId, "✅ תשובה נכונה!")
    else:
        await send_feedback(ctx.bot, chatId, f"❌ טעות. התשובה הנכונה היא: {correct}")

    await send_question(ctx.bot, chatId)             # שאלה חדשה

application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CallbackQueryHandler(on_press))

# ---------- Flask routes ----------
@flask_app.get("/")
def index():
    return "bot alive", 200

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)

    # משתמשים בלולאה שכבר רצה – לא asyncio.run!
    loop = asyncio.get_event_loop()
    loop.create_task(application.process_update(update))

    return "ok", 200

# ---------- רישום Webhook באתחול ----------
async def init():
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
    except TelegramError:
        pass

    for _ in range(3):                       # עד 3 ניסיונות → מטפל ב-RetryAfter
        try:
            await application.bot.set_webhook(WEBHOOK_URL)
            break
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)

    await application.initialize()

# הרצה חד-פעמית בעת עליית ה-worker
asyncio.run(init())
