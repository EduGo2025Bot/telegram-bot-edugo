# app.py  –  Flask + python-telegram-bot webhook
import os, typing as t
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, AIORateLimiter
from bot.handlers import register_handlers
from bot.keep_alive import launch_keep_alive

TOKEN  = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]

app = Flask(__name__)

application = (
    Application.builder()
    .token(TOKEN)
    .rate_limiter(AIORateLimiter())
    .build()
)

# רישום כל ה-handlers
register_handlers(application)
launch_keep_alive(application)

# ניתן להריץ לוקלית ב-Polling לצורך בדיקות
if __name__ == "__main__":
    application.run_polling()

# --- קטע שרץ ב-Render בלבד – הגדרת webhook ---
@app.before_first_request
def _init_webhook() -> None:
    if os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        host = os.environ["RENDER_EXTERNAL_HOSTNAME"]
        url  = f"https://{host}/webhook/{SECRET}"
        application.bot.delete_webhook(drop_pending_updates=True)
        application.bot.set_webhook(url=url)

@app.post(f"/webhook/{SECRET}")
def telegram_webhook():
    if request.headers.get("content-type") == "application/json":
        update = Update.de_json(request.json, application.bot)
        application.update_queue.put_nowait(update)
        return {"ok": True}
    abort(403)
