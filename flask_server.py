from threading import Thread
import time
import requests

from flask import Flask
from flask import request


app = Flask('')


@app.route('/')
def home():
    return "I'm alive"


def run():
    app.run(host='0.0.0.0', port=80)


def keep_alive():
    t = Thread(target=run)
    t.start()
