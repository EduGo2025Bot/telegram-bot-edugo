"""
Flask + python-telegram-bot (v20+) webhook application
------------------------------------------------------
✓ Sets the webhook on cold-start
✓ Starts the PTB dispatcher in a background task
✓ Pushes each incoming update into the queue
"""

import os
import logging
import asyncio
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, AIORateLimiter
from bot.handlers import register_handlers
# from bot.keep_alive import launch_keep_alive   # optional ping thread

# ────────────────────  ENV  ────────────────────
TOKEN  = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]

# ───────────────────  LOGGING  ──────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ────────────────  Flask app  ───────────────────
app = Flask(__name__)

# ────────────  PTB Application  ────────────────
application = (
    Application.builder()
    .token(TOKEN)
    .rate_limiter(AIORateLimiter())
    .build()
)
register_handlers(application)          # ↖ your handlers.py


# ───────────  Run dispatcher bg  ───────────
async def _run_bot() -> None:
    await application.initialize()
    await application.start()
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if host:
        url = f"https://{host}/webhook/{SECRET}"
        await application.bot.set_webhook(url=url, drop_pending_updates=True)
        logger.info("Webhook set → %s", url)
    logger.info("Telegram dispatcher started ✅")

# No _init_webhook() call at module import
asyncio.get_event_loop().create_task(_run_bot())

# ────────────  Webhook route  ─────────────
@app.post(f"/webhook/{SECRET}")
def telegram_webhook():
    if request.headers.get("content-type") == "application/json":
        update = Update.de_json(request.get_json(force=True), application.bot)
        # Dispatcher thread will pick it up:
        application.update_queue.put_nowait(update)
        return {"ok": True}
    abort(403)
