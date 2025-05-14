# """
# Flask + python-telegram-bot (v21+) webhook application for Render
# ——————————————————————————————————————————
# ✓ Registers PTB handlers
# ✓ Adds keep-alive heartbeat
# ✓ Sets webhook only after dispatcher is running
# """

# import os
# import logging
# import asyncio
# from flask import Flask, request, abort
# from telegram import Update
# from telegram.ext import Application, AIORateLimiter

# from bot.handlers import register_handlers
# from bot.keep_alive import add_keep_alive     # <-- new import

# # ────────────────  ENV  ────────────────
# TOKEN  = os.environ["BOT_TOKEN"]
# SECRET = os.environ["WEBHOOK_SECRET"]

# # ───────────────  LOGGING  ─────────────
# logging.basicConfig(
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     level=logging.INFO,
# )
# logger = logging.getLogger(__name__)

# # ───────────────  Flask  ───────────────
# app = Flask(__name__)

# # ─────────  PTB Application  ───────────
# application = (
#     add_keep_alive(                       # inject the heartbeat
#         Application.builder()
#         .token(TOKEN)
#         .rate_limiter(AIORateLimiter())
#     )
#     .build()                              # finally build the Application
# )

# register_handlers(application)

# # ───────────  Dispatcher bg task  ───────────
# async def _run_bot() -> None:
#     await application.initialize()
#     await application.start()

#     # Webhook is set *after* dispatcher is ready
#     host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
#     if host:
#         url = f"https://{host}/webhook/{SECRET}"
#         await application.bot.set_webhook(url=url, drop_pending_updates=True)
#         logger.info("Webhook set → %s", url)

#     logger.info("PTB dispatcher started ✅")

# # start the dispatcher once at boot
# asyncio.get_event_loop().create_task(_run_bot())

# # ────────────  Webhook route  ───────────
# @app.post(f"/webhook/{SECRET}")
# def telegram_webhook():
#     if request.headers.get("content-type") == "application/json":
#         update = Update.de_json(request.get_json(force=True), application.bot)
#         application.update_queue.put_nowait(update)
#         return {"ok": True}
#     abort(403)

# app.py
import os
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram import Update
from bot.handlers import register_handlers
from bot.keep_alive import launch_keep_alive
from dotenv import load_dotenv

load_dotenv()  # Load .env for local development

BOT_TOKEN = os.getenv("BOT_TOKEN")

def main():
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    application = Application.builder().token(BOT_TOKEN).build()
    register_handlers(application)
    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    launch_keep_alive()
    main()

