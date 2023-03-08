import logging
import time
import os

import telebot
from flask_server import keep_alive

from utils import FlatOfferParser


# TODO: WRITE YOUR BOT


if __name__ == "__main__":
    API_TOKEN = "YOUR BOT LOGIC"
    bot = telebot.TeleBot(API_TOKEN)

    # TODO: USE YOUR BOT LOGIC

    keep_alive()
    bot.polling(none_stop=True, interval=0)
