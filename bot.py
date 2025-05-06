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
TOKEN = os.environ["TOKEN"]   # עובר מ-Render כ-Environment Variable

# Render מספק את ה-URL החיצוני במשתנה RENDER_EXTERNAL_URL
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"

# ---------- טעינת השאלות מקובץ JSON ----------
QUESTIONS_PATH = Path(__file__).with_name("questions.json")
QUESTIONS = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))

# ---------- Flask ו-telegram.Application ----------
flask_app = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()

# זיכרון שאלה אחרונה לכל משתמש
user_state: dict[int, dict] = {}

# ---------- פונקציות עזר ----------


def build_keyboard(opts: list[str]) -> InlineKeyboardMarkup:
    """יוצר מקלדת Inline: כל תשובה בשורה + כפתור דילוג בסוף."""
    row = [InlineKeyboardButton(o[0], callback_data=o[0]) for o in opts]
    row.append(InlineKeyboardButton("דלג ⏭️", callback_data="skip"))
    return InlineKeyboardMarkup([row])


async def send_question(target, context: ContextTypes.DEFAULT_TYPE):
    """שולח למשתמש שאלה חדשה ומעדכן user_state."""
    uid = target.effective_user.id
    q = random.choice(QUESTIONS)
    user_state[uid] = q

    text = q["question"] + "\n\n" + "\n".join(q["options"])
    markup = build_keyboard(q["options"])

    if hasattr(target, "message"):  # /start או /question
        await target.message.reply_text(text, reply_markup=markup)
    else:  # CallbackQuery קודם
        await target.callback_query.message.reply_text(text, reply_markup=markup)


# ---------- Handlers ----------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_question(update, context)


async def on_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid, data = query.from_user.id, query.data

    # "דלג"
    if data == "skip":
        await query.edit_message_text("⏭️  שאלה חדשה:")
        await send_question(update, context)
        return

    q = user_state.get(uid)
    if not q:
        await query.edit_message_text("שלח ‎/start כדי להתחיל.")
        return

    correct = q["correct"]
    if data == correct:
        await query.edit_message_text("✅ תשובה נכונה!")
    else:
        await query.edit_message_text(f"❌ טעות. התשובה הנכונה היא: {correct}")

    await send_question(update, context)


application.add_handler(CommandHandler(["start", "question"], cmd_start))
application.add_handler(CallbackQueryHandler(on_press))

# ---------- Flask → Telegram bridge ----------


@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "ok", 200


# ---------- הפעלת ה-Webhook באתחול ----------
async def init():
    # רושם את ה-Webhook (מוחק קודמים אוטומטית)
    await application.bot.set_webhook(WEBHOOK_URL)
    # מאתחל את Application (Persistence וכו')
    await application.initialize()


# רץ פעם אחת בעלייה
asyncio.run(init())
