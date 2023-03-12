from typing import Union, List, Dict, Callable
import os
import asyncio
import aioschedule
import re
import enum

import requests
from aiogram import Bot, Dispatcher, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from aiogram.utils.exceptions import (
    MessageToDeleteNotFound,
    ChatNotFound,
    BotKicked,
    BotBlocked,
    BadRequest,
    MessageCantBeDeleted
)

from replit import db
from replit.database.database import ObservedDict

from flask_server import keep_alive
from utils import FlatOfferParser, RentData


class DBKeys(enum.Enum):
    OTHER: str = "other"
    REQUEST_URL: str = "rent_url"


class BotCommands(enum.Enum):
    START: str = "start"
    CLEAR: str = "clear"


class BotCommandsTemplates(enum.Enum):
    START: str = fr"/{BotCommands.START.value}"
    CLEAR: str = fr"/{BotCommands.CLEAR.value}"


KEYBOARD = ReplyKeyboardMarkup(resize_keyboard=True)
CLEAR_BTN = KeyboardButton(BotCommandsTemplates.CLEAR.value)
KEYBOARD.add(CLEAR_BTN)

CLEAR_REPEATING_IN_MINUTES: int = 120
PARSE_DATA_REPEATING_IN_MINUTES: int = 20
API_TOKEN: str = os.environ["API_TOKEN"]
URL_REGEX = r"^(?:(?:http|ftp)s?://)?" + \
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|" + \
            r"localhost|" + \
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})" + \
            r"(?::\d+)?" + \
            r"(?:/?|[/?]\S+)$"

BOT = Bot(token=API_TOKEN)
DP = Dispatcher(BOT)


def check_pattern(pattern: str, message: str) -> bool:
    return re.fullmatch(pattern, message, re.IGNORECASE) is not None


def is_not_included_request_url(chat_id: str, p_request_url: str) -> bool:
    stash = db[chat_id][DBKeys.REQUEST_URL.value]
    return not any(p_request_url == request_url for _, request_url in stash.items())


def is_url(message: str) -> bool:
    return check_pattern(URL_REGEX, message)


def is_valid_url(url: str) -> bool:
    response = requests.get(url)
    return response.ok


def get_default_stash() -> Dict[str, Dict]:
    return {
        DBKeys.OTHER.value: {},
        DBKeys.REQUEST_URL.value: {},
    }


def add_info(chat_id: Union[int, str], message_id: Union[int, str],
             text: str, stash_key: str = DBKeys.OTHER.value) -> None:
    str_chat_id = str(chat_id)
    str_message_id = str(message_id)
    user_stash = db.get(
        str_chat_id,
        get_default_stash()
    )
    user_stash[stash_key][str_message_id] = text


async def send_message(chat_id: Union[int, str], text: str, stash_key: str = DBKeys.OTHER.value) -> None:
    try:
        message = await BOT.send_message(chat_id=chat_id, text=text, reply_markup=KEYBOARD)
        add_info(chat_id, message.message_id, text, stash_key)
    except BadRequest:
        ...


def hidden_chat_check(message: str):
    def outer_wrapper(function):
        async def wrapper(chat_id: int, *args, **kwargs) -> None:
            try:
                await send_message(chat_id, message)
                await function(chat_id, *args, **kwargs)
            except (ChatNotFound, BotKicked, BotBlocked):
                del db[chat_id]

        return wrapper

    return outer_wrapper


async def welcome(chat_id: int) -> None:
    welcome_message = "Привет! Меня зовут Бро-бот. Могу помочь в поиске квартир."
    await send_message(chat_id, welcome_message)


async def delete_messages(stash: ObservedDict, chat_id: str, filter_: Callable = lambda x: False) -> None:
    messages_to_pop = set()

    for message_id, message in stash.items():
        if filter_(message):
            continue

        try:
            await BOT.delete_message(chat_id, message_id)
        except (MessageToDeleteNotFound, MessageCantBeDeleted) as exc:
            if isinstance(exc, MessageCantBeDeleted):
                break

        messages_to_pop.add(message_id)

    for message_id in messages_to_pop:
        try:
            del stash[message_id]
        except KeyError:
            ...


@hidden_chat_check("Начинаю удаление мусора.")
async def clear_by_id(chat_id: int) -> None:
    str_user_id = str(chat_id)
    await delete_messages(db[str_user_id][DBKeys.OTHER.value], str_user_id)
    await delete_messages(
        db[str_user_id][DBKeys.REQUEST_URL.value],
        str_user_id,
        lambda msg: is_url(msg) and is_valid_url(msg))


@hidden_chat_check("Начинаю поиск новой информации. Если сообщений нет, то новая информация отсутствует.")
async def send_rent_data(user: str, rent_data_list: List[RentData]) -> None:
    for rent_data in rent_data_list:
        if is_not_included_request_url(user, rent_data.URL):
            await send_message(user, rent_data.URL, DBKeys.REQUEST_URL.value)


async def schedule_clear_rubbish(*args, **kwargs) -> None:
    for user in db.keys():
        await clear_by_id(user)


async def schedule_send_rent_data(*args, **kwargs) -> None:
    rent_data_parser = FlatOfferParser()
    rent_data_list = list(rent_data_parser())

    for user in db.keys():
        await send_rent_data(user, rent_data_list)


@DP.message_handler(commands=[BotCommands.START.value, BotCommands.CLEAR.value])
async def handler(message: Message):
    user = message.chat.id
    message_text = message.text
    add_info(user, message.message_id, message_text)

    if check_pattern(BotCommandsTemplates.START.value, message_text):
        await welcome(user)
    elif check_pattern(BotCommandsTemplates.CLEAR.value, message_text):
        await clear_by_id(user)


async def scheduler() -> None:
    aioschedule.every(PARSE_DATA_REPEATING_IN_MINUTES).minutes.do(schedule_send_rent_data)
    aioschedule.every(CLEAR_REPEATING_IN_MINUTES).minutes.do(schedule_clear_rubbish)

    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


async def on_startup(dp: Dispatcher) -> None:
    asyncio.create_task(scheduler())


def print_db():
    for chat_id, sub_stash in db.items():
        print(chat_id)
        for stash_key, sub_stash in sub_stash.items():
            print("\t", stash_key)
            for message_id, message in sub_stash.items():
                print('\t\t', f"{message_id} : {message}")


if __name__ == "__main__":
    keep_alive()
    executor.start_polling(DP, on_startup=on_startup, skip_updates=True)
