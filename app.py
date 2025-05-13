# app.py  – גרסה מתוקנת וקצרה
import os, asyncio
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, AIORateLimiter
from bot.handlers import register_handlers
# from bot.keep_alive import launch_keep_alive  # אופציונלי

TOKEN  = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]

app = Flask(__name__)

application = (
    Application.builder()
    .token(TOKEN)
    .rate_limiter(AIORateLimiter())
    .build()
)
register_handlers(application)
# launch_keep_alive(application)

# צור/עדכן webhook פעם אחת (קורא ל-API של טלגרם)
asyncio.run(
    application.bot.set_webhook(
        url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook/{SECRET}",
        drop_pending_updates=True,
    )
)

# --- Webhook endpoint ---
@app.post(f"/webhook/{SECRET}")
def telegram_webhook():
    if request.headers.get("content-type") == "application/json":
        update = Update.de_json(request.json, application.bot)
        # קורא ל-handlers בפעימה אחת
        asyncio.run(application.process_update(update))
        return {"ok": True}
    abort(403)
