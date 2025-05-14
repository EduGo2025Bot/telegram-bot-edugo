import os, logging, asyncio
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, AIORateLimiter
from bot.handlers import register_handlers
from bot.keep_alive import add_keep_alive

TOKEN  = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

application = (
    add_keep_alive(
        Application.builder()
        .token(TOKEN)
        .rate_limiter(AIORateLimiter())
    )
    .build()
)
register_handlers(application)
launch_keep_alive(application)     # optional heartbeat

async def _run_bot():
    await application.initialize()
    await application.start()
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    if host:
        url = f"https://{host}/webhook/{SECRET}"
        await application.bot.set_webhook(url=url, drop_pending_updates=True)
        logger.info("Webhook set → %s", url)
    logger.info("PTB dispatcher started ✅")

asyncio.get_event_loop().create_task(_run_bot())

@app.post(f"/webhook/{SECRET}")
def telegram_webhook():
    if request.headers.get("content-type") == "application/json":
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
        return {"ok": True}
    abort(403)
