# bot/keep_alive.py
import asyncio, logging, os
from telegram import Bot

BOT  = Bot(os.environ["BOT_TOKEN"])
CHAT = os.environ.get("KEEP_ALIVE_CHAT")

async def _heartbeat():
    while True:
        try:
            await BOT.send_chat_action(chat_id=CHAT, action="typing")
            logging.info("Heartbeat sent")
        except Exception as e:
            logging.error(f"Heartbeat error: {e}")
        await asyncio.sleep(14 * 60)  # 14 דקות

def launch_keep_alive(app):
    if CHAT:
        app.create_task(_heartbeat())
