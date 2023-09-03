import copy

import pygsheets
import re
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
                             "google spreadsheet URL here"),
)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
global time, phone, name


class ActionState(StatesGroup):
    phone = State()
    name = State()
    time = State()
    table_id = State()
    booking = State()
    show_bookings = State()
    cancel_booking = State()
    finish_cancel = State()


def menu_builder():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        types.KeyboardButton("Забронировать стол"),
        types.KeyboardButton("Мои записи"),
        types.KeyboardButton("Контакты"),
    ]
    keyboard.row(buttons[0])
    keyboard.row(buttons[1], buttons[2])
    return keyboard


def button_builder(amount, available_time):
    buttons = []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(amount):
        buttons.append(types.KeyboardButton(available_time[i]))
    for i in range(0, amount, 2):
        try:
            markup.row(buttons[i], buttons[i + 1])
        except:
            markup.row(buttons[i])
    exitbtn = types.KeyboardButton("Выйти")
    markup.row(exitbtn)
    return markup


@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message):
    keyboard = menu_builder()
    await message.answer("Привет, {0.first_name}!\nЗдесь ты можешь забронировать стол в KIKS".format(
        message.from_user), reply_markup=keyboard)


# Админ панель
@dp.message_handler(content_types="text", text="Очистить записи")
async def clear_bookings(message: types.Message):
    if message.chat.username == "DNK21":
        await message.answer("Записи очищены")
        googlesheet_client: pygsheets.client.Client = bot.google_table._get_googlesheet_client()
        wks: pygsheets.Spreadsheet = bot.google_table._get_googlesheet_by_url(googlesheet_client)
        for i in range(2, 7):
            wks.update_value((i, 4), "")
            wks.update_value((i, 5), "")
            wks.update_value((i, 7), "")
            wks.update_value((i, 6), "Доступно")
        for i in range(9, 14):
            wks.update_value((i, 4), "")
            wks.update_value((i, 5), "")
            wks.update_value((i, 7), "")
            wks.update_value((i, 6), "Доступно")
        for i in range(16, 21):
            wks.update_value((i, 4), "")
            wks.update_value((i, 5), "")
            wks.update_value((i, 7), "")
            wks.update_value((i, 6), "Доступно")
        for i in range(23, 28):
            wks.update_value((i, 4), "")
            wks.update_value((i, 5), "")
            wks.update_value((i, 7), "")
            wks.update_value((i, 6), "Доступно")


# Начало блока бронирования стола
@dp.message_handler(lambda message: message.text == "Забронировать стол")
async def menu_booking(message: types.Message, state: FSMContext):
    reply_markup = types.ReplyKeyboardRemove()
    menu_booking_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu_booking_markup.row(types.KeyboardButton("Стол 1"),
                            types.KeyboardButton("Стол 2"))
    menu_booking_markup.row(types.KeyboardButton("Стол 3"),
                            types.KeyboardButton("Стол 4"))
    menu_booking_markup.row(types.KeyboardButton("Выйти"))
    await message.answer("Вы можете нажать на любой стол и узнать свободное время:", reply_markup=menu_booking_markup)
    await state.set_state(ActionState.table_id)


@dp.message_handler(state=ActionState.table_id)
async def table_time(message: types.Message, state: FSMContext):
    if message.text == "Стол 1" or message.text == "Стол 2" or message.text == "Стол 3" or message.text == "Стол 4":
        await state.update_data(table_id=message.text)
        data = await state.get_data()
        table_id = data.get("table_id")
        await bot.send_message(message.from_user.id, "Подождите секунду, идет поиск свободного времени...")
        available_time = get_available_time(table_id)
        if len(available_time) == 0:
            await bot.send_message(message.from_user.id, "К сожалению, все столы заняты")
            await state.finish()
        else:
            markup = button_builder(len(available_time), available_time)
            await message.answer("Нажмите на кнопку, чтобы выбрать время", reply_markup=markup)
            await state.set_state(ActionState.time)
    elif message.text == "Выйти":
        await state.finish()
        await message.answer("Вы вышли из меню бронирования", reply_markup=menu_builder())
    else:
        await state.finish()
        await message.answer("Что-то пошло не по плану... Попробуй еще раз.", reply_markup=menu_builder())


@dp.message_handler(state=ActionState.time)
async def get_time(message: types.Message, state: FSMContext):
    reply_markup = types.ReplyKeyboardRemove()
    available_times = ["12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00", "16:00-17:00", "17:00-18:00"]
    await state.update_data(time=message.text)
    if message.text == "Выйти":
        await state.finish()
        keyboard = menu_builder()
        await message.answer("Вы вышли в главное меню", reply_markup=keyboard)
    elif message.text in available_times:
        data = await state.get_data()
        time = data.get("time")
        await message.answer(f"Вы выбрали время: {time}. Напишите свое имя", reply_markup=reply_markup)
        await state.set_state(ActionState.name)
    else:
        await state.finish()
        await message.answer("Неверный ввод. Попробуйте еще раз", reply_markup=menu_builder())


@dp.message_handler(state=ActionState.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    data = await state.get_data()
    name = data.get("name")
    await message.answer(f" {name}, напиши свой телефон!")
    await state.set_state(ActionState.phone)


@dp.message_handler(state=ActionState.phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    if check_phone(message.text):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(types.KeyboardButton("Да"), types.KeyboardButton("Нет"))
        await message.reply(f"Подтвердите запись?", reply_markup=markup)
        await state.set_state(ActionState.booking)
    else:
        await message.answer("Неверный ввод. Попробуйте еще раз")


@dp.message_handler(state=ActionState.booking)
async def finish_booking(message: types.Message, state: FSMContext):
    reply_markup = types.ReplyKeyboardRemove()
    if message.text == "Да":
        data = await state.get_data()
        time = data.get("time")
        phone = data.get("phone")
        name = data.get("name")
        table = data.get("table_id")
        table_id = int(table[-1])
        tg_id = message.from_user.username
        if book_table(time, phone, name, tg_id, table_id):
            await state.finish()
            keyboard = menu_builder()
            await message.reply("Вы успешно записались!", reply_markup=keyboard)
        else:
            await state.finish()
            keyboard = menu_builder()
            await message.answer("Что-то пошло не по плану... Попробуй снова!", reply_markup=keyboard)
    else:
        await message.reply("Запись не создана", reply_markup=reply_markup)
        await state.finish()
        keyboard = menu_builder()
        await message.answer("Вы вышли в главное меню", reply_markup=keyboard)


# Начало "Мои записи"
@dp.message_handler(lambda message: message.text == "Мои записи")
async def check_bookings(message: types.Message):
    reply_markup = types.ReplyKeyboardRemove()
    bookings_markup = types.InlineKeyboardMarkup(resize_keyboard=True)
    bookings_markup.add(types.InlineKeyboardButton("Мои брони", callback_data="show_recs"),
                        types.InlineKeyboardButton("Отменить бронь", callback_data="cancel_recs"),
                        types.InlineKeyboardButton("Выйти", callback_data="exit_recs"))
    await message.answer("Что вы хотите сделать?", reply_markup=reply_markup)
    await message.answer("Выберите действие:", reply_markup=bookings_markup)


@dp.callback_query_handler(lambda c: c.data == "show_recs")
async def show_recs(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ActionState.show_bookings)
    await call.message.answer("Вы можете ввести свой номер телефона и посмотреть ваши бронирования:")


@dp.callback_query_handler(lambda c: c.data == "cancel_recs")
async def cancel_recs(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ActionState.cancel_booking)
    await call.message.answer("Вы можете ввести свой номер телефона и отменить бронирование:")


@dp.callback_query_handler(lambda c: c.data == "exit_recs")
async def exit_recs(call: types.CallbackQuery, state: FSMContext):
    keyboard = menu_builder()
    await call.message.answer("Вы вышли в главное меню", reply_markup=keyboard)
    await state.finish()


@dp.message_handler(state=ActionState.show_bookings)
async def show_bookings(message: types.Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    await message.reply("Подождите, идет поиск...")
    data = await state.get_data()
    tg_id = message.from_user.username
    phone_number = data.get("phone_number")
    if check_phone(phone_number):
        bookings = show_bookings(phone_number, tg_id)
        if len(bookings) == 0:
            await message.answer("У вас нет бронирований")
        else:
            text = "Ваши бронирования:\n"
            for booking in bookings:
                text += booking
            await message.answer(text)
        await state.finish()
        await message.answer("Вы вышли в главное меню", reply_markup=menu_builder())
    else:
        await message.answer("Неверный формат номера телефона")
        await state.finish()
        keyboard = menu_builder()
        await message.answer("Попробуй снова", reply_markup=keyboard)


@dp.message_handler(state=ActionState.cancel_booking)
async def cancel_booking(message: types.Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    await message.reply("Подождите, идет поиск...")
    data = await state.get_data()
    tg_id = message.from_user.username
    phone_number = data.get("phone_number")
    if check_phone(phone_number):
        bookings = show_bookings(phone_number, tg_id)
        if len(bookings) == 0:
            await state.finish()
            await message.answer("У вас нет бронирований", reply_markup=menu_builder())
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for i in range(len(bookings)):
                markup.add(types.KeyboardButton(bookings[i]))
            await message.answer("Выберите бронирование, которое хотите отменить", reply_markup=markup)
            await state.set_state(ActionState.finish_cancel)
    else:
        await message.answer("Неверный формат номера телефона :(")
        await state.finish()
        await message.answer("Попрубуйте снова", reply_markup=menu_builder())


@dp.message_handler(state=ActionState.finish_cancel)
async def finish_cancel(message: types.Message, state: FSMContext):
    reply_markup = types.ReplyKeyboardRemove()
    await state.update_data(booking=message.text)
    data = await state.get_data()
    if data.get("booking") is None:
        await state.finish()
        await message.answer("Отмена операции", reply_markup=menu_builder())
    else:
        await message.answer("Отменяем...")
        tg_id = message.from_user.username
        data = await state.get_data()
        table_num = data.get("booking").split()[0] + " " + data.get("booking").split()[1]
        time_rec = data.get("booking").split()[3]
        if cancel_booking(time_rec, tg_id, table_num):
            await state.finish()
            await message.answer("Бронирование отменено!", reply_markup=menu_builder())
        else:
            await state.finish()
            await message.answer("Что-то пошло не по плану, попробуй снова.", reply_markup=menu_builder())


# Конец обработчиков "Мои записи"

# Начало блока "Контакты"
@dp.message_handler(lambda message: message.text == "Контакты")
async def contacts(message: types.Message):
    await message.answer("--------------------------------\n "
                         "Здесь должны быть контакты \n"
                         "--------------------------------")


# Конец блока "Контакты"

def get_available_time(table_id):
    time_col = 3
    is_available_col = 6
    googlesheet_client: pygsheets.client.Client = bot.google_table._get_googlesheet_client()
    wks: pygsheets.Spreadsheet = bot.google_table._get_googlesheet_by_url(googlesheet_client)
    try:
        available_time = []
        table_cell = wks.find(table_id)
        rows = [cell.row for cell in table_cell]
        for row in rows:
            if wks.cell((row, is_available_col)).value == "Доступно":
                available_time.append(wks.cell((row, time_col)).value)
    except:
        return []
    return available_time


def book_table(time, phone, name, tg_id, table_id):
    table_num_col = 2
    phone_col = 4
    name_col = 5
    is_available_col = 6
    tg_id_col = 7
    table_cell = []
    googlesheet_client: pygsheets.client.Client = bot.google_table._get_googlesheet_client()
    wks: pygsheets.Spreadsheet = bot.google_table._get_googlesheet_by_url(googlesheet_client)
    try:
        find_cell = wks.find(time)
        table_cell.append(find_cell[table_id - 1])
        rows = [cell.row for cell in table_cell]
        for row in rows:
            if wks.get_value((row, is_available_col)) == "Доступно":
                wks.update_value((row, phone_col), phone)
                wks.update_value((row, name_col), name)
                wks.update_value((row, is_available_col), "Занято")
                wks.update_value((row, tg_id_col), tg_id)
                return True
    except:
        return False
    return True


def show_bookings(phone, tg_id):
    table_num_col = 2
    time_col = 3
    tg_id_col = 7
    googlesheet_client: pygsheets.client.Client = bot.google_table._get_googlesheet_client()
    wks: pygsheets.Spreadsheet = bot.google_table._get_googlesheet_by_url(googlesheet_client)
    bookings_text = []
    try:
        find_cell = wks.find(phone)
        rows = [cell.row for cell in find_cell]
        for row in rows:
            if wks.get_value((row, tg_id_col)) == tg_id:
                bookings_text.append(
                    wks.get_value((row, table_num_col)) + " " + "-" + " " + wks.get_value((row, time_col)) + "\n")
        return bookings_text
    except:
        return bookings_text


def cancel_booking(booking, tg_id, table_num):
    phone_col = 4
    name_col = 5
    is_available_col = 6
    tg_id_col = 7
    googlesheet_client: pygsheets.client.Client = bot.google_table._get_googlesheet_client()
    wks: pygsheets.Spreadsheet = bot.google_table._get_googlesheet_by_url(googlesheet_client)
    try:
        find_table = wks.find(table_num)
        find_cell = wks.find(booking)
        table_rows = [cell.row for cell in find_table]
        rows = [cell.row for cell in find_cell]
        for row in rows:
            for table_row in table_rows:
                if row == table_row and wks.get_value((row, tg_id_col)) == tg_id:
                    wks.update_value((row, phone_col), "")
                    wks.update_value((row, name_col), "")
                    wks.update_value((row, is_available_col), "Доступно")
                    wks.update_value((row, tg_id_col), "")
                    return True
    except:
        return False
    return True


def check_phone(number):
    phone_num = re.sub(r'\b\D', '', number)
    clear_phone = re.sub(r'[\ \(]?', '', phone_num)
    if re.findall(r'^[\+7|8]*?\d{10}$', clear_phone) or re.match(r'^\w+[\.]?(\w+)*\@(\w+\.)*\w{2,}$', number):
        return bool(number)
    else:
        return False


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
