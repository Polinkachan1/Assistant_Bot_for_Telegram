import time

import telebot
from telebot import types
from data.db_session import global_init, create_session
from data.notes import Notes
from data.users import Users
from geopy import geocoders
from config import *
import requests
import schedule
from threading import Thread

bot = telebot.TeleBot(token)

city = 'Волгодонск'
global_init('db/notes.db')
global_init('db/users.db')


@bot.message_handler(commands=['start'])
def start(message) -> None:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    edit_button = types.KeyboardButton('✏️ Редактировать список дел')
    settings_button = types.KeyboardButton('⚙️ Настройки')
    markup.add(edit_button, settings_button)
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
    i = 0
    all_notes = get_all_notes(message.chat.id)
    if len(all_notes) > 0:
        for note in all_notes:
            i += 1
            markup = types.InlineKeyboardMarkup()
            delete_note_inline = types.InlineKeyboardButton('➖  Удалить'.format(message.from_user),
                                                            callback_data=f'{message.chat.id} delete {note[0]};{message.message_id + i}')
            markup.add(delete_note_inline)
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
        add_button = types.KeyboardButton('➕️  Добавить заметку')
        markup.add(delete_button, add_button)
        bot.send_message(message.chat.id, f'Что именно вы хотите сделать?', reply_markup=markup)

    elif message.text == '⚙️ Настройки':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        weather_button = types.KeyboardButton('🌩️ Ежедневный прогноз погоды')
        markup.add(weather_button)
        bot.send_message(message.chat.id, 'Что вы хотите настроить?', reply_markup=markup)

    elif message.text == '➖  Удалить заметку':
        bot.send_message(message.chat.id, 'Чтобы удалить заметку напишите: "удалить  *текст заметки*"')

    elif message.text == '➕️  Добавить заметку':
        bot.send_message(message.chat.id, '''Чтобы добавить заметку напишите: "добавить  *текст заметки* *время*
Например, "добавить помыть посуду 20:30"''')

    elif message.text == '🌩️ Ежедневный прогноз погоды':
        markup = types.InlineKeyboardMarkup()
        weather_inline_yes = types.InlineKeyboardButton('✅ Да', callback_data=f'{message.chat.id} Yes')
        weather_inline_no = types.InlineKeyboardButton('❌ Нет', callback_data=f'{message.chat.id} No')
        markup.add(weather_inline_yes, weather_inline_no)
        bot.send_message(message.chat.id, 'Вы хотите ежедневно получать прогноз погоды?'.format(message.from_user),
                         reply_markup=markup)
        bot.send_message(message.chat.id, '''Чтобы выбрать город, напишите: "город  *название города* "
Чтобы выбрать время получения прогноза погоды, напишите "погода  *время* "
Например, "город Волгодонск" и "погода 7:30"''')

    elif message.text[:5].lower().startswith('город'):  # изменение города пользователя
        global city
        city = message.text[6:].strip()

    elif message.text[:8].lower().startswith('добавить'):  # добавление заметки
        note_text = ' '.join(message.text[9:].strip().split()[:-1])
        time = message.text[9:].strip().split()[-1]
        if not is_already_existing_note(message.chat.id, note_text):
            add_note(message.chat.id, note_text, time)
            bot.send_message(message.chat.id, 'Заметка успешно добавлена')
            schedule.every().day.at(time).do(remind, chat_id=message.chat.id, note_text=note_text)
        else:
            bot.send_message(message.chat.id, 'Ошибка: такая заметка уже существует')

    elif message.text[:7].lower().startswith('удалить'):  # удаление заметки
        note_text = message.text[8:].strip().split()
        if is_already_existing_note(message.chat.id, note_text):
            delete_note(message.chat.id, note_text)
            bot.send_message(message.chat.id, 'Заметка успешно удалена')
        else:
            bot.send_message(message.chat.id, 'Ошибка: такой заметки не существует')

    elif message.text.lower().startswith('погода'):
        session = create_session()
        user = session.query(Users).filter(Users.chat_id == message.chat.id).first()
        time = message.text[7:].strip()
        user.weather_time = time
        session.commit()
    check_reminders()


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call) -> None:  # обработка callback
    request = call.data.split('_')[0]
    session = create_session()
    chat_id = request[:10]
    callback = request[11:]

    if callback == 'Yes':
        bot.answer_callback_query(call.id, 'Теперь вы будете получать прогноз погоды')
        user = session.query(Users).filter(Users.chat_id == chat_id).first()
        user.send_weather = True

    elif callback == 'No':
        bot.answer_callback_query(call.id, 'Больше вы не будете получать прогноз погоды')
        user = session.query(Users).filter(Users.chat_id == chat_id).first()
        user.send_weather = False

    elif callback.startswith('delete'):
        note = callback[7:].split(';')[0]
        delete_note(chat_id, note)
        bot.delete_message(chat_id, callback[7:].split(';')[1])
    session.commit()


def get_weather() -> str:  # получение информации о погоде
    geolocator = geocoders.Nominatim(user_agent="telebot")
    latitude = str(geolocator.geocode(city).latitude)
    longitude = str(geolocator.geocode(city).longitude)
    response = requests.get(f'https://api.weather.yandex.ru/v2/forecast/?lat={latitude}&lon={longitude}&lang=ru_RU',
                            headers={"X-Yandex-API-Key": 'e056937d-4d55-412f-ae71-ec9be10f67af'})
    data = response.json()
    day_forecast = data['forecasts'][0]['parts']['day_short']
    return f'''Погода на сегодня: {conditions[day_forecast['condition']]}, 
температура {day_forecast["temp"]} °C, ощущается как {day_forecast['feels_like']} °C, 
скорость ветра {day_forecast['wind_speed']} м/с, вероятность осадков {day_forecast['prec_prob']}%'''


def send_weather(chat_id):
    bot.send_message(chat_id, get_weather())


def add_note(chat_id, note_text, time) -> None:  # добавление новой заметки
    session = create_session()
    note = Notes(
        chat_id=chat_id,
        note_text=note_text,
        reminder_time=time
    )
    session.add(note)
    session.commit()


def delete_note(chat_id, note_text) -> None:  # удаление заметки
    session = create_session()

    session.query(Notes).filter(Notes.chat_id == chat_id).filter(Notes.note_text == note_text).delete()
    session.commit()


def get_all_notes(chat_id) -> list:  # получение текста всех заметок пользователя
    session = create_session()
    all_notes = session.query(Notes).filter(Notes.chat_id == chat_id)
    all_note_texts = [(note.note_text, note.reminder_time) for note in all_notes]
    return all_note_texts


def get_all_chat_ids() -> list:
    session = create_session()
    all_users = session.query(Users)
    all_chat_ids = [user.chat_id for user in all_users]
    return all_chat_ids


def is_already_existing_note(chat_id, note_text) -> bool:  # проверка существует ли такая заметка
    session = create_session()
    if len(session.query(Notes).filter(Notes.chat_id == chat_id).filter(Notes.note_text == note_text).all()) != 0:
        return True
    return False


def is_already_existing_user(chat_id) -> bool:  # проверка существует ли такой пользователь
    session = create_session()
    if len(session.query(Users).filter(Users.chat_id == chat_id).all()) != 0:
        return True
    return False


def add_user(chat_id, send_weather=False, weather_time='07:00') -> None:  # добавление пользователя
    session = create_session()
    user = Users(
        chat_id=chat_id,
        send_weather=send_weather,
        weather_time=weather_time
    )
    session.add(user)
    session.commit()


def remind(chat_id, note_text):  # напоминание о заметке
    bot.send_message(chat_id, f'Напоминание: {note_text}')
    delete_note(chat_id, note_text)
    return schedule.CancelJob


def pending() -> None:
    while True:
        schedule.run_pending()
        time.sleep(1)


def check_reminders():
    session = create_session()
    get_all_chat_ids()
    for chat_id in get_all_chat_ids():
        for user in session.query(Users).filter(Users.chat_id == chat_id).all():
            if user.send_weather:
                schedule.every().day.at(user.weather_time).do(send_weather, chat_id=chat_id)
        for note_text in get_all_notes(chat_id):
            schedule.every().day.at(note_text[1]).do(remind, chat_id=chat_id, note_text=note_text[0])


check_reminders()
th = Thread(target=pending)
th.start()

bot.polling(none_stop=True, interval=0)
