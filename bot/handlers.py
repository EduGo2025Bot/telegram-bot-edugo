# bot/handlers.py
import os, tempfile, asyncio, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from bot.qa_generator import build_qa_from_text, extract_text

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "שלחו לי PDF / DOCX / PPTX ואייצר לכם שאלות רב-ברירה ונכון/לא-נכון 📚"
    )

async def doc_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    # מגבלת גודל (20MB)
    if doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("👎 הקובץ גדול מדי (מעל 20MB).")
        return

    with tempfile.TemporaryDirectory() as tmp:
        path = await doc.get_file().download_to_drive(custom_path=tmp)
        text = extract_text(path)
        if not text.strip():
            await update.message.reply_text("לא הצלחתי לחלץ טקסט מהקובץ 🤔")
            return
        qas = build_qa_from_text(text)
    await send_questions(update, qas)

async def send_questions(update: Update, qas):
    for q in qas:
        buttons = []
        for opt in q["options"]:
            cb = opt.split(".")[0].strip() if q["type"] == "multiple" else opt
            buttons.append(InlineKeyboardButton(cb, callback_data=cb))
        buttons.append(InlineKeyboardButton("דלג ⏭️", callback_data="skip"))
        await update.message.reply_text(
            q["question"],
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([buttons]),
        )

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, doc_received))
