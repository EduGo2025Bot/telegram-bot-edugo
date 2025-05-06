import os
import asyncio
import json
import random
from pathlib import Path

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
TOKEN = os.environ["TOKEN"]                       # מגיע ב-Render כ-Env-Var
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"

# ---------- טעינת שאלות ----------
QUESTIONS = json.loads(Path(__file__).with_name("questions.json")
                       .read_text(encoding="utf-8"))

# ---------- Telegram & Flask ----------
flask_app   = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()

user_state: dict[int, dict] = {}                  # זיכרון שאלה אחרונה

# ---------- כלי עזר ----------
def build_keyboard(opts: list[str]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(o[0], callback_data=o[0]) for o in opts]
    row.append(InlineKeyboardButton("דלג ⏭️", callback_data="skip"))
    return InlineKeyboardMarkup([row])

async def send_question_by_chat(bot, chat_id: int):
    q = random.choice(QUESTIONS)
    user_state[chat_id] = q
    text = q["question"] + "\n\n" + "\n".join(q["options"])
    await bot.send_message(chat_id, text, reply_markup=build_keyboard(q["options"]))

# ---------- Handlers ----------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_question_by_chat(ctx.bot, update.effective_chat.id)

async def on_press(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id, data = query.message.chat_id, query.data

    # דילוג
    if data == "skip":
        await query.edit_message_reply_markup(None)      # מסיר כפתורים ישנים
        await send_question_by_chat(ctx.bot, chat_id)
        return

    q = user_state.get(chat_id)
    if not q:
        await query.edit_message_text("שלח ‎/start כדי להתחיל")
        return

    correct = q["correct"]
    if data == correct:
        await query.edit_message_text("✅ תשובה נכונה!")
    else:
        await query.edit_message_text(f"❌ טעות. התשובה הנכונה היא: {correct}")

    # שולח מיד שאלה חדשה
    await send_question_by_chat(ctx.bot, chat_id)

application.add_handler(CommandHandler(["start", "question"], cmd_start))
application.add_handler(CallbackQueryHandler(on_press))

# ---------- Flask ↔ Telegram ----------
@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    upd = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(upd))
    return "ok", 200

# ---------- רישום Webhook באתחול ----------
async def init():
    await application.bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    await application.initialize()

asyncio.run(init())
