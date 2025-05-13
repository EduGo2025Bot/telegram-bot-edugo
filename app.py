# app.py  –  Flask + python-telegram-bot webhook
import os, logging
from flask import Flask, request, abort, jsonify
from telegram import Update
from telegram.ext import Application, AIORateLimiter
from bot.handlers import register_handlers
from bot.keep_alive import launch_keep_alive
import asyncio

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]

# Flask app
app = Flask(__name__)

# Telegram bot application
application = (
    Application.builder()
    .token(TOKEN)
    .rate_limiter(AIORateLimiter())
    .build()
)

# Register handlers
register_handlers(application)

# Initialize webhook
if os.getenv("RENDER_EXTERNAL_HOSTNAME"):
    webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook/{SECRET}"
    logger.info(f"Running webhook listener on: {webhook_url}")
    # Listen on 0.0.0.0:<PORT>, Telegram will POST updates to /webhook/<SECRET>
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=f"/webhook/{SECRET}",
        webhook_url=webhook_url,
        drop_pending_updates=True,
    )
else:
    # local dev
    application.run_polling()

# Health check endpoint
@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Bot is running"})

# Webhook endpoint
@app.route(f"/webhook/{SECRET}", methods=["POST"])
def telegram_webhook():
    if request.headers.get("content-type") == "application/json":
        try:
            # Parse update
            update = Update.de_json(request.json, application.bot)
            logger.info(f"Received update: {update.update_id}")
            
            # Process update
            application.update_queue.put_nowait(update)
            return {"ok": True}
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return {"ok": False, "error": str(e)}, 500
    logger.warning("Received non-JSON content")
    abort(403)

# Error handler
@app.errorhandler(404)
def not_found(error):
    return {"ok": False, "error": "Not found"}, 404

# Initialize the application properly
async def init_app():
    await application.initialize()
    await application.start()
    logger.info("Application started")

# When running locally for testing
if __name__ == "__main__":
    # Run in polling mode for local development
    logger.info("Starting bot in polling mode")
    application.run_polling()
else:
    # In production, start the application in webhook mode
    asyncio.run(init_app())
