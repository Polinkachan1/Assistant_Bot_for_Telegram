import re
import telebot
from telebot import types
from data.db_session import global_init, create_session
from data.notes import Notes
from data.users import Users
from geopy import geocoders
from config import token, api_key, conditions
import requests
from threading import Thread
from datetime import date
from schedule_service import (
    pending,
    add_reminder,
    cancel_job,
)

bot = telebot.TeleBot(token)


def main() -> None:
    global_init('db/notes.db')

    check_reminders()
    th = Thread(target=pending)
    th.start()
    bot.polling(none_stop=True, interval=0)


@bot.message_handler(commands=['start'])
def start(message) -> None:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    edit_button = types.KeyboardButton('✏️ Редактировать список дел')
    settings_button = types.KeyboardButton('⚙️ Настройки')
    markup.add(edit_button, settings_button)
    img = open('data/logo.jpg', 'rb')
    bot.send_photo(message.chat.id, img)
    bot.send_message(message.chat.id, 'Привет ✌', reply_markup=markup)


@bot.message_handler(commands=['return_to_menu'])
def return_to_menu(message) -> None:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    edit_button = types.KeyboardButton('✏️ Редактировать список дел')
    settings_button = types.KeyboardButton('⚙️ Настройки')
    markup.add(edit_button, settings_button)
    bot.send_message(message.chat.id, 'Выберите любой пункт меню', reply_markup=markup)


@bot.message_handler(commands=['send_all_notes'])
def send_all_notes(message) -> None:
    all_notes = get_all_notes(message.chat.id)
    if len(all_notes) > 0:
        for i, note in enumerate(all_notes):
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton('➖  Удалить'.format(message.from_user),
                                           callback_data=f'{message.chat.id} delete {note[0]};{message.message_id + i}')
            )
            bot.send_message(message.chat.id, f'{note[0]}', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, f'Заметок нет')


@bot.message_handler(content_types=['text'])
def handle_replies(message) -> None:
    if not is_already_existing_user(message.chat.id):
        add_user(message.chat.id, False)
    if message.text == '✏️ Редактировать список дел':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        delete_button = types.KeyboardButton('➖  Удалить заметку')
        add_button = types.KeyboardButton('➕  Добавить заметку')
        markup.add(delete_button, add_button)
        bot.send_message(message.chat.id, f'Что именно вы хотите сделать?', reply_markup=markup)

    elif message.text == '⚙️ Настройки':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        weather_button = types.KeyboardButton('🌩️ Ежедневный прогноз погоды')
        markup.add(weather_button)
        bot.send_message(message.chat.id, 'Что вы хотите настроить?', reply_markup=markup)

    elif message.text == '➖  Удалить заметку':
        send_all_notes(message)

    elif message.text == '➕  Добавить заметку':
        bot.send_message(message.chat.id, 'Напишите текст заметки')
        bot.register_next_step_handler(message, handle_note_text_message)

    elif message.text == '🌩️ Ежедневный прогноз погоды':
        city, time = get_city_and_time(message.chat.id)
        markup = types.InlineKeyboardMarkup()
        weather_inline_yes = types.InlineKeyboardButton('✅ Да', callback_data=f'{message.chat.id} Yes')
        weather_inline_no = types.InlineKeyboardButton('❌ Нет', callback_data=f'{message.chat.id} No')
        markup.add(weather_inline_yes, weather_inline_no)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        city_button = types.KeyboardButton('🏙️️️ Изменить город')
        time_button = types.KeyboardButton('🕓️️ Изменить время')
        keyboard.add(city_button, time_button)
        bot.send_message(message.chat.id, 'Вы хотите ежедневно получать прогноз погоды?'.format(message.from_user),
                         reply_markup=markup)
        bot.send_message(message.chat.id, f'''Выбранный город: {city}
Время: {time}''', reply_markup=keyboard)

    elif message.text == '🏙️️️ Изменить город':
        bot.send_message(message.chat.id, 'Введите название города')
        bot.register_next_step_handler(message, set_city)

    elif message.text == '🕓️️ Изменить время':
        bot.send_message(message.chat.id, 'Когда вам присылать прогноз погоды?')
        bot.register_next_step_handler(message, set_weather_time)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call) -> None:  # обработка callback
    request = call.data.split('_')[0]
    session = create_session()
    chat_id = request[:10]
    callback = request[11:]

    if callback == 'Yes':
        bot.answer_callback_query(call.id, 'Теперь вы будете получать прогноз погоды')
        user = session.query(Users).filter(Users.chat_id == chat_id).first()
        user.should_send_weather = True

    elif callback == 'No':
        bot.answer_callback_query(call.id, 'Больше вы не будете получать прогноз погоды')
        user = session.query(Users).filter(Users.chat_id == chat_id).first()
        user.should_send_weather = False

    elif callback.startswith('delete'):
        note = callback[7:].split(';')[0]
        delete_note(chat_id, note)
        bot.delete_message(chat_id, int(callback[7:].split(';')[1]) + 1)
        check_reminders()
    session.commit()


def get_weather(city) -> str:  # получение информации о погоде
    geolocator = geocoders.Nominatim(user_agent="telebot")
    latitude = str(geolocator.geocode(city).latitude)
    longitude = str(geolocator.geocode(city).longitude)
    response = requests.get(f'https://api.weather.yandex.ru/v2/forecast/?lat={latitude}&lon={longitude}&lang=ru_RU',
                            headers={"X-Yandex-API-Key": api_key})
    data = response.json()
    day_forecast = data['forecasts'][0]['parts']['day_short']
    return f'''Погода на сегодня: {conditions[day_forecast['condition']]}, 
температура {day_forecast["temp"]} °C, ощущается как {day_forecast['feels_like']} °C, 
скорость ветра {day_forecast['wind_speed']} м/с, вероятность осадков {day_forecast['prec_prob']}%'''


def send_weather(chat_id):
    city = get_city_and_time(chat_id),
    bot.send_message(chat_id, get_weather(city))


def add_note(chat_id, note_text, time, reminder_date) -> None:  # добавление новой заметки
    session = create_session()
    note = Notes(
        chat_id=chat_id,
        note_text=note_text,
        reminder_time=time,
        date=reminder_date
    )
    session.add(note)
    session.commit()
    check_reminders()


def delete_note(chat_id, note_text, reminder_date=str(date.today())) -> None:  # удаление заметки
    if reminder_date == str(date.today()):
        session = create_session()
        session.query(Notes).filter(Notes.chat_id == chat_id, Notes.note_text == note_text).delete()
        session.commit()
    check_reminders()


def get_all_notes(chat_id) -> list:  # получение текста всех заметок пользователя
    session = create_session()
    all_notes = session.query(Notes).filter(Notes.chat_id == chat_id)
    return [(note.note_text, note.reminder_time, note.date) for note in all_notes]


def get_all_chat_ids() -> list:
    session = create_session()
    all_users = session.query(Users)
    return [user.chat_id for user in all_users]


def is_already_existing_note(chat_id, note_text) -> bool:  # проверка существует ли такая заметка
    session = create_session()
    return len(session.query(Notes).filter(Notes.chat_id == chat_id).filter(Notes.note_text == note_text).all()) != 0


def is_already_existing_user(chat_id) -> bool:  # проверка существует ли такой пользователь
    session = create_session()
    return len(session.query(Users).filter(Users.chat_id == chat_id).all()) != 0


def add_user(chat_id, should_send_weather=False, weather_time='07:00') -> None:  # добавление пользователя
    session = create_session()
    user = Users(
        chat_id=chat_id,
        should_send_weather=should_send_weather,
        weather_time=weather_time,
        city='Волгодонск',
    )
    session.add(user)
    session.commit()


def remind(chat_id, note_text, reminder_date):
    if reminder_date == str(date.today()):
        bot.send_message(chat_id, f'Напоминание: {note_text}')
        delete_note(chat_id, note_text)
        return cancel_job()


def check_reminders():
    session = create_session()
    for chat_id in get_all_chat_ids():
        for user in session.query(Users).filter(Users.chat_id == chat_id).all():
            if user.should_send_weather:
                add_reminder(user.weather_time, send_weather, chat_id)

        for note_text, time, reminder_date in get_all_notes(chat_id):
            add_reminder(time, remind, chat_id, note_text, reminder_date)


def set_city(message):  # выбрать город
    session = create_session()
    user = session.query(Users).filter(Users.chat_id == message.chat.id).first()
    user.city = message.text.strip()
    session.commit()
    bot.send_message(message.chat.id, 'Город изменён')


def set_weather_time(message):
    session = create_session()
    user = session.query(Users).filter(Users.chat_id == message.chat.id).first()
    time = message.text.strip()
    user.weather_time = time
    session.commit()
    bot.send_message(message.chat.id, 'Время изменено')
    check_reminders()


def get_city_and_time(chat_id):
    session = create_session()
    user = session.query(Users).filter(Users.chat_id == chat_id).first()
    return user.city, user.weather_time


def handle_note_time_message(message, note_text):
    parts_of_message = message.text.strip().split()
    try:
        time, reminder_date = parse_time_message(message, parts_of_message)

        if not is_already_existing_note(message.chat.id, note_text):
            add_reminder(time, delete_note, message.chat.id, note_text, reminder_date)
            add_note(message.chat.id, note_text, time, reminder_date)
            bot.send_message(message.chat.id, 'Заметка успешно добавлена')
        else:
            bot.send_message(message.chat.id, 'Ошибка: такая заметка уже существует')
    except ValueError:
        bot.send_message(message.chat.id, 'Ошибка: неверный формат ввода')


def handle_note_text_message(message):
    note_text = message.text
    bot.send_message(message.chat.id, 'Когда напомнить о заметке?')
    bot.register_next_step_handler(message, handle_note_time_message, note_text)


time_format = re.compile(r'(?P<hours>\d{1,2})\W(?P<minutes>\d{2})')


def parse_time_message(message, parts_of_message):
    if len(parts_of_message) == 1:
        time = message.text.strip()
        reminder_date = str(date.today())
    elif len(parts_of_message) == 2:
        time, reminder_date = parts_of_message
        if len(reminder_date) == 5:
            reminder_date = f'{str(date.today().year)}-{reminder_date}'
        elif len(reminder_date) == 2:
            month = str(date.today().month)
            if len(month) == 1:
                month = f'0{month}'
            reminder_date = f'{str(date.today().year)}-{month}-{reminder_date}'
        else:
            raise ValueError('Invalid date format')
    else:
        raise ValueError('Invalid date format')
    if not re.fullmatch(time_format, time):
        raise ValueError('Invalid date format')
    match = time_format.search(time)
    hours = int(match.group("hours"))
    minutes = match.group("minutes")
    time = f'{hours:02}:{minutes}'
    return time, reminder_date


main()
