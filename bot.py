from typing import Union, List
import os
import asyncio
import aioschedule
import re

import requests
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.exceptions import MessageToDeleteNotFound, ChatNotFound, BotKicked, BotBlocked
from replit import db

from flask_server import keep_alive
from utils import FlatOfferParser, RentData


if __name__ == "__main__":
    START_COMMAND = "start"
    CLEAR_COMMAND = "clear"
    START_TEMPLATE = fr"/{START_COMMAND}"
    CLEAR_TEMPLATE = fr"/{CLEAR_COMMAND}"
    KEYBOARD = ReplyKeyboardMarkup()
    CLEAR_BTN = KeyboardButton(f"/{CLEAR_COMMAND}")
    KEYBOARD.add(CLEAR_BTN)

    CLEAR_REPEATING_IN_MINUTES: int = 120
    PARSE_DATA_REPEATING_IN_MINUTES: int = 30
    UNIQUE_USERS_PATH: str = "users.pkl"
    TEXT_PATH: str = "text.pkl"
    API_TOKEN: str = os.environ["API_TOKEN"]
    URL_REGEX = re.compile(
        r'^(?:(?:http|ftp)s?://)?'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    bot = Bot(token=API_TOKEN)
    dp = Dispatcher(bot)


    def print_db():
        for chat_id in db.keys():
            print('\n', chat_id)
            for message_id, message in db[chat_id].items():
                print('\t', f"{message_id} : {message}")


    def add_info(chat_id: Union[int, str], message_id: Union[int, str], text: str) -> None:
        str_chat_id = str(chat_id)
        str_message_id = str(message_id)

        if str_chat_id not in db.keys():
            db[str_chat_id] = {}
        db[str_chat_id][str_message_id] = text


    def is_not_included_message(chat_id: str, message: str) -> bool:
        return not any(message == db[chat_id][key] for key in db[chat_id])


    def is_url(message: str) -> bool:
        return URL_REGEX.fullmatch(message) is not None


    def is_valid_url(url: str) -> bool:
        response = requests.get(url)
        return response.ok


    def check_pattern(pattern: str, message: str) -> bool:
        return re.fullmatch(pattern, message, re.IGNORECASE) is not None


    def hidden_chat_check(message: str):
        def outer_wrapper(function):
            async def wrapper(user: int, *args, **kwargs) -> None:
                try:
                    await send_message(user, message)
                    await function(user, *args, **kwargs)
                except (ChatNotFound, BotKicked, BotBlocked):
                    del db[user]

            return wrapper

        return outer_wrapper


    async def send_message(chat_id: Union[int, str], text: str, reply_markup=None) -> None:
        message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        add_info(chat_id, message.message_id, text)


    async def send_welcome(user: int):
        welcome_message = "Привет! Меня зовут Бро-бот. Могу помочь в поиске квартир."
        await send_message(user, welcome_message, reply_markup=KEYBOARD)


    @hidden_chat_check("Начинаю удаление мусора.")
    async def clear_by_id(user: int) -> None:
        str_user_id = str(user)

        for message_id, message in db[str_user_id].items():
            if is_url(message) and is_valid_url(message):
                continue

            try:
                await bot.delete_message(user, message_id)
            except MessageToDeleteNotFound:
                ...

            try:
                del db[str_user_id][message_id]
            except KeyError:
                ...


    @hidden_chat_check("Начинаю поиск новой информации. Если сообщений нет, то новая информация отсутствует.")
    async def send_rent_data(user: str, rent_data_list: List[RentData]) -> None:
        for rent_data in rent_data_list:
            if is_not_included_message(user, rent_data.URL):
                await send_message(user, rent_data.URL)


    async def schedule_clear_rubbish(*args, **kwargs) -> None:
        for user in db.keys():
            await clear_by_id(user)


    async def schedule_send_rent_data(*args, **kwargs) -> None:
        rent_data_parser = FlatOfferParser()
        rent_data_list = list(rent_data_parser())

        for user in db.keys():
            await send_rent_data(user, rent_data_list)


    @dp.message_handler(commands=[START_COMMAND, CLEAR_COMMAND])
    async def handler(message: types.Message):
        user = message.chat.id
        message_text = message.text
        add_info(user, message.message_id, message_text)

        if check_pattern(START_TEMPLATE, message_text):
            await send_welcome(user)
        elif check_pattern(CLEAR_TEMPLATE, message_text):
            await clear_by_id(user)


    async def scheduler() -> None:
        aioschedule.every(PARSE_DATA_REPEATING_IN_MINUTES).minutes.do(schedule_send_rent_data)
        aioschedule.every(CLEAR_REPEATING_IN_MINUTES).minutes.do(schedule_clear_rubbish)

        while True:
            await aioschedule.run_pending()
            await asyncio.sleep(1)


    async def on_startup(dp: Dispatcher) -> None:
        asyncio.create_task(scheduler())


    keep_alive()
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
