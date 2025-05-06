import os, asyncio, json, random
from pathlib import Path
from telegram.error import RetryAfter, TelegramError
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ---------- הגדרות בסיס ----------
TOKEN = os.environ["TOKEN"]
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"

# ---------- טעינת שאלות ----------
QUESTIONS = json.loads(Path(__file__).with_name("questions.json")
                       .read_text(encoding="utf-8"))

# ---------- Telegram & Flask ----------
flask_app   = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()
user_state: dict[int, dict] = {}        # שאלה אחרונה לכל צ'אט

# ---------- כלי-עזר ----------
def build_keyboard(opts: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for o in opts:
        # אם יש פורמט "א. ..." → callback = האות לפני הנקודה; אחרת הטקסט המלא
        cb = o.split(".")[0].strip() if ". " in o else o
        buttons.append(InlineKeyboardButton(o, callback_data=cb))
    buttons.append(InlineKeyboardButton("דלג ⏭️", callback_data="skip"))
    return InlineKeyboardMarkup([buttons])

async def send_question(bot, chat_id: int):
    q = random.choice(QUESTIONS)
    user_state[chat_id] = q
    txt = q["question"] + "\n\n" + "\n".join(q["options"])
    await bot.send_message(chat_id, txt, reply_markup=build_keyboard(q["options"]))

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
    await q.edit_message_reply_markup(None)            # נועל כפתורים ישנים

    if data == "skip":                                 # דילוג
        await send_question(ctx.bot, chatId)
        return

    current = user_state.get(chatId)
    if not current:                                   # בטיחות
        await send_feedback(ctx.bot, chatId, "שלח ‎/start כדי להתחיל.")
        return

    correct = current["correct"]
    if data == correct:
        await send_feedback(ctx.bot, chatId, "✅ תשובה נכונה!")
    else:
        await send_feedback(ctx.bot, chatId, f"❌ טעות. התשובה הנכונה היא: {correct}")

    await send_question(ctx.bot, chatId)               # שאלה חדשה מיד

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
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
    except TelegramError:
        pass
    for _ in range(3):
        try:
            await application.bot.set_webhook(WEBHOOK_URL)
            break
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
    await application.initialize()

asyncio.run(init())
