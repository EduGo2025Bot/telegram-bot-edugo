import logging, os
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackContext

CHAT = os.environ.get("KEEP_ALIVE_CHAT")  # יכול להיות None

def _heartbeat(ctx: CallbackContext) -> None:
    if not CHAT:
        return
    try:
        ctx.bot.send_chat_action(chat_id=int(CHAT), action=ChatAction.TYPING)
        logging.info("Heartbeat sent")
    except Exception as e:
        logging.error(f"Heartbeat error: {e}")

def launch_keep_alive(app: Application) -> None:
    """רושם את ה-Heartbeat כחלק מ-post_init של PTB."""
    if not CHAT:
        return

    async def _register_jobs(_: Application) -> None:
        # עכשיו job_queue קיים ויש לולאת-אירועים
        app.job_queue.run_repeating(_heartbeat, interval=14 * 60, first=0)

    # post_init = פונקציות שרצות אחרי שה-Application הופעל
    app.post_init(_register_jobs)
