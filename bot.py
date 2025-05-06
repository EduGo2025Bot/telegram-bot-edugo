# bot.py
import os
import json
import random
import asyncio
import threading
from pathlib import Path

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------- הגדרות ----------
TOKEN = os.environ["TOKEN"]   # חובה להגדיר ENV VAR בשם TOKEN
# Render/OnRender מגדיר את השם של השירות ב-RENDER_SERVICE_NAME
BASE_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com"
).rstrip("/")
WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"

# ---------- Flask + Telegram ----------
flask_app   = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()

# יוצרים לולאת אירועים ייעודית ומשיקים אותה ברקע
event_loop = asyncio.new_event_loop()
asyncio.set_event_loop(event_loop)

def start_event_loop():
    event_loop.run_forever()

threading.Thread(target=start_event_loop, daemon=True).start()

# ---------- שאלות ----------
QUESTIONS = json.loads(
    Path(__file__).with_name("questions.json").read_text(encoding="utf-8")
)
user_state: dict[int, dict] = {}

def build_kbd(opts: list[str]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(o[0], callback_data=o[0]) for o in opts]
    row.append(InlineKeyboardButton("דלג ⏭️", callback_data="skip"))
    return InlineKeyboardMarkup([row])

async def send_question(chat_id: int, bot):
    q = random.choice(QUESTIONS)
    user_state[chat_id] = q
    text = q["question"] + "\n\n" + "\n".join(q["options"])
    await bot.send_message(chat_id, text, reply_markup=build_kbd(q["options"]))

# ---------- Handlers ----------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_question(update.effective_chat.id, ctx.bot)

async def on_press(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    qobj    = update.callback_query
    chat_id = qobj.message.chat_id
    data    = qobj.data
    await qobj.answer()
    # ננעל את הכפתורים של ההודעה הישנה
    await qobj.edit_message_reply_markup(None)

    if data == "skip":
        return await send_question(chat_id, ctx.bot)

    last_q = user_state.get(chat_id)
    if not last_q:
        return await ctx.bot.send_message(chat_id, "שלח ‎/start כדי להתחיל.")

    correct = last_q["correct"]
    if data == correct:
        await ctx.bot.send_message(chat_id, "✅ תשובה נכונה!")
    else:
        await ctx.bot.send_message(chat_id, f"❌ טעות. התשובה הנכונה היא: {correct}")

    # ישר שאלה חדשה
    await send_question(chat_id, ctx.bot)

application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CallbackQueryHandler(on_press))

# ---------- Webhook route ----------
@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook() -> tuple[str,int]:
    payload = request.get_json(force=True)
    update  = Update.de_json(payload, application.bot)
    # שולחים את העדכון לתוך הלולאה שלנו
    asyncio.run_coroutine_threadsafe(
        application.process_update(update),
        event_loop
    )
    return "OK", 200

# ---------- init webhook ----------
async def init_webhook():
    # מנקים קודם webhook קודמים
    await application.bot.delete_webhook(drop_pending_updates=True)
    # רושמים חדש
    await application.bot.set_webhook(WEBHOOK_URL)
    # מאתחלים את ה־Application (handlers וכו')
    await application.initialize()
    print("✅ Webhook registered at", WEBHOOK_URL)

# רושמים את ה־webhook ברקע
asyncio.run_coroutine_threadsafe(init_webhook(), event_loop)
