# bot/keep_alive.py  –  גרסה מתוקנת עם JobQueue
import logging, os
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackContext

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT      = os.environ.get("KEEP_ALIVE_CHAT")  # יכול להיות None

# הפונקציה שה-Job Queue תריץ
def _heartbeat(ctx: CallbackContext):
    if not CHAT:
        return
    try:
        ctx.bot.send_chat_action(chat_id=int(CHAT), action=ChatAction.TYPING)
        logging.info("Heartbeat sent")
    except Exception as e:
        logging.error(f"Heartbeat error: {e}")

def launch_keep_alive(app: Application):
    if CHAT:
        # first=0 ⇒ מתחיל מיד; interval=14min
        app.job_queue.run_repeating(_heartbeat, interval=14 * 60, first=0)
