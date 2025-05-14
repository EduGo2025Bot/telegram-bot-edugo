# bot/keep_alive.py
import logging, os
from telegram.constants import ChatAction
from telegram.ext import Application

CHAT = os.getenv("KEEP_ALIVE_CHAT")          # can be empty

async def _heartbeat(app: Application):
    """Send 'typing…' every 14-minutes to keep the dyno awake."""
    if not CHAT:
        return
    try:
        await app.bot.send_chat_action(int(CHAT), ChatAction.TYPING)
        logging.info("Heartbeat sent")
    except Exception as e:
        logging.error("Heartbeat error: %s", e)

def add_keep_alive(builder):
    """Call this *before* .build(); returns the same builder."""
    if CHAT:
        builder.post_init(lambda app: app.job_queue.run_repeating(
            _heartbeat, interval=14 * 60, first=0
        ))
    return builder
