import pygsheets
from pygsheets.client import Client
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup

import config
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.utils import executor
from loguru import logger
from googlesheet_table import GoogleTable

logger.add(
    config.settings["LOG_FILE"],
    format="{time} {level} {message}",
    level="DEBUG",
    rotation="1 week",
    compression="zip",
)

class KiksBiBot(Bot):
    def __init__(
            self,
            token,
            parse_mode,
            google_table=None,
    ):
        super().__init__(token, parse_mode=parse_mode)
        self._google_table: GoogleTable = google_table

    @property
    def google_table(self):
        return self._google_table


bot = KiksBiBot(
    token=config.settings["TOKEN"],
    parse_mode=types.ParseMode.HTML,
    google_table=GoogleTable("creds.json",
                             "https://docs.google.com/spreadsheets/d/1G1G4KqXXhdy_vEu3Bjj9p1AQHQjmfSBh2wEyVP8jbaw"),
)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
global time, phone, name


class ActionState(StatesGroup):
    phone = State()
    name = State()
    time = State()
    booking = State()
    show_bookings = State()
    cancel_booking = State()
    finish_cancel = State()


def button_builder(amount, available_time):
    buttons = []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(amount):
        buttons.append(types.KeyboardButton(available_time[i]))
        markup.add(buttons[i])
    exitbtn = types.KeyboardButton("Выйти")
    markup.add(exitbtn)
    return markup


@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        types.KeyboardButton("Забронировать стол"),
        types.KeyboardButton("Мои записи"),
        types.KeyboardButton("Контакты"),
    ]
    keyboard.add(*buttons)
    await message.answer("Привет, {0.first_name}!\nЗдесь ты можешь забронировать стол в KIKS".format(
        message.from_user), reply_markup=keyboard)


@dp.message_handler(lambda message: message.text == "Забронировать стол")
async def choose_time(message: types.Message, state: FSMContext):
    await bot.send_message(message.from_user.id, "Выберите подходящее время")
    available_time = bot.google_table.get_available_time()
    markup = button_builder(len(available_time), available_time)
    await message.answer("Нажмите на кнопку, чтобы выбрать время", reply_markup=markup)
    await state.set_state(ActionState.time)


@dp.message_handler(lambda message: message.text == "Мои записи")
async def check_bookings(message: types.Message, state: FSMContext):
    reply_markup = types.ReplyKeyboardRemove()
    bookings_markup = types.InlineKeyboardMarkup(resize_keyboard=True)
    bookings_markup.add(types.InlineKeyboardButton("Показать мои записи", callback_data="show_recs"),
                        types.InlineKeyboardButton("Отменить запись", callback_data="cancel_recs"))
    await message.answer("Что вы хотите сделать?", reply_markup=reply_markup)
    await message.answer("Выберите действие", reply_markup=bookings_markup)


@dp.callback_query_handler(lambda c: c.data == "show_recs")
async def show_recs(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ActionState.show_bookings)
    await call.message.answer("Вы можете ввести свой номер телефона и посмотреть ваши бронирования:")


@dp.callback_query_handler(lambda c: c.data == "cancel_recs")
async def cancel_recs(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ActionState.cancel_booking)
    await call.message.answer("Вы можете ввести свой номер телефона и отменить бронирование:")


@dp.message_handler(state=ActionState.show_bookings)
async def show_bookings(message: types.Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    data = await state.get_data()
    tg_id = message.from_user.username
    phone_number = data.get("phone_number")
    bookings = show_bookings(phone_number, tg_id)
    if len(bookings) == 0:
        await message.answer("У вас нет бронирований")
    else:
        text = "Ваши бронирования:\n"
        for booking in bookings:
            text += booking + "\n"
        await message.answer(text)
    await state.finish()
    await start_handler(message)


@dp.message_handler(state=ActionState.cancel_booking)
async def cancel_booking(message: types.Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    data = await state.get_data()
    tg_id = message.from_user.username
    phone_number = data.get("phone_number")
    bookings = show_bookings(phone_number, tg_id)
    if len(bookings) == 0:
        await message.answer("У вас нет бронирований")
        await state.finish()
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for i in range(len(bookings)):
            markup.add(types.KeyboardButton(bookings[i]))
        await message.answer("Выберите бронирование, которое хотите отменить", reply_markup=markup)
        await state.set_state(ActionState.finish_cancel)

@dp.message_handler(state=ActionState.finish_cancel)
async def finish_cancel(message: types.Message, state: FSMContext):
    reply_markup = types.ReplyKeyboardRemove()
    await state.update_data(booking=message.text)
    data = await state.get_data()
    if data.get("booking") is None:
        await message.answer("Отмена операции", reply_markup=reply_markup)
        await state.finish()
        await start_handler(message)
    else:
        tg_id = message.from_user.username
        data = await state.get_data()
        booking = data.get("booking")
        cancel_booking(booking, tg_id)
        await message.answer("Бронирование отменено", reply_markup=reply_markup)
        await state.finish()
        await start_handler(message)


@dp.message_handler(lambda message: message.text == "Контакты")
async def contacts(message: types.Message):
    await message.answer("Контакты: ... ")
    book_table("12:00-13:00", "+79215562853", "Даня")


@dp.message_handler(state=ActionState.time)
async def get_time(message: types.Message, state: FSMContext):
    reply_markup = types.ReplyKeyboardRemove()
    await state.update_data(time=message.text)
    if message.text == "Выйти":
        await state.finish()
        await start_handler(message)
    else:
        data = await state.get_data()
        time = data.get("time")
        await message.answer(f"Вы выбрали время: {time}. Напишите свое имя", reply_markup=reply_markup)
        await state.set_state(ActionState.name)
        return time


@dp.message_handler(state=ActionState.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    data = await state.get_data()
    name = data.get("name")
    await message.answer(f" {name}, напиши свой телефон!")
    await state.set_state(ActionState.phone)
    return name


@dp.message_handler(state=ActionState.phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()
    phone = data.get("phone")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("Да"), types.KeyboardButton("Нет"))
    await message.answer(f"Подтвердите запись?", reply_markup=markup)
    await state.set_state(ActionState.booking)


@dp.message_handler(state=ActionState.booking)
async def finish_booking(message: types.Message, state: FSMContext):
    reply_markup = types.ReplyKeyboardRemove()
    if message.text == "Да":
        data = await state.get_data()
        time = data.get("time")
        phone = data.get("phone")
        name = data.get("name")
        tg_id = message.from_user.username
        book_table(time, phone, name, tg_id)
        await message.reply("Запись успешно создана", reply_markup=reply_markup)
        await state.finish()
        await start_handler(message)
    else:
        await message.reply("Запись не создана", reply_markup=reply_markup)
        await state.finish()
        await start_handler(message)


def book_table(time, phone, name, tg_id):
    phone_col = 4
    name_col = 5
    is_available_col = 6
    tg_id_col = 7
    googlesheet_client: pygsheets.client.Client = bot.google_table._get_googlesheet_client()
    wks: pygsheets.Spreadsheet = bot.google_table._get_googlesheet_by_url(googlesheet_client)
    try:
        find_cell = wks.find(time)
        rows = [cell.row for cell in find_cell]
        for row in rows:
            if wks.get_value((row, phone_col)) == "":
                wks.update_value((row, phone_col), phone)
                wks.update_value((row, name_col), name)
                wks.update_value((row, is_available_col), "Занято")
                wks.update_value((row, tg_id_col), tg_id)
                return True
    except:
        return False
    return True


def show_bookings(phone, tg_id):
    time_col = 3
    tg_id_col = 7
    googlesheet_client: pygsheets.client.Client = bot.google_table._get_googlesheet_client()
    wks: pygsheets.Spreadsheet = bot.google_table._get_googlesheet_by_url(googlesheet_client)
    bookings = []
    try:
        find_cell = wks.find(phone)
        rows = [cell.row for cell in find_cell]
        for row in rows:
            if wks.get_value((row, tg_id_col)) == tg_id:
                bookings.append(wks.get_value((row, time_col)))
        return bookings
    except:
        return bookings


def cancel_booking(booking, tg_id):
    phone_col = 4
    name_col = 5
    is_available_col = 6
    tg_id_col = 7
    googlesheet_client: pygsheets.client.Client = bot.google_table._get_googlesheet_client()
    wks: pygsheets.Spreadsheet = bot.google_table._get_googlesheet_by_url(googlesheet_client)
    try:
        find_cell = wks.find(booking)
        rows = [cell.row for cell in find_cell]
        for row in rows:
            if wks.get_value((row, tg_id_col)) == tg_id:
                wks.update_value((row, phone_col), "")
                wks.update_value((row, name_col), "")
                wks.update_value((row, is_available_col), "Доступно")
                wks.update_value((row, tg_id_col), "")
                return True
    except:
        return False
    return True


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
