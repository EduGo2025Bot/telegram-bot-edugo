# # bot/keep_alive.py
# """
# Adds a periodic “typing…” heartbeat so Render’s free instance doesn’t fall asleep.
# Register the callback on the Application *builder* before .build().
# """

# import logging
# import os
# from telegram.constants import ChatAction
# from telegram.ext import Application

# CHAT_ID = os.getenv("KEEP_ALIVE_CHAT")   # may be empty / unset


# async def _heartbeat(app: Application) -> None:
#     """Runs every 14 minutes and sends a chat-action to keep the bot alive."""
#     if not CHAT_ID:
#         return
#     try:
#         await app.bot.send_chat_action(int(CHAT_ID), ChatAction.TYPING)
#         logging.info("Heartbeat sent")
#     except Exception as exc:
#         logging.error("Heartbeat error: %s", exc)


# def add_keep_alive(builder: Application.builder) -> Application.builder:
#     """
#     Inject the heartbeat job into the builder’s post_init list
#     and return the *same* builder so you can chain `.build()`.
#     Call this *before* `.build()`.
#     """
#     if CHAT_ID:
#         builder.post_init(                # <-- method is available on the builder
#             lambda app: app.job_queue.run_repeating(
#                 _heartbeat, interval=14 * 60, first=0
#             )
#         )
#     return builder

# bot/keep_alive.py
from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def launch_keep_alive():
    t = threading.Thread(target=run)
    t.start()

