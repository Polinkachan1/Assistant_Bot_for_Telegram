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
        add_button = types.KeyboardButton('➕️  Добавить заметку')
        markup.add(delete_button, add_button)
        bot.send_message(message.chat.id, f'Что именно вы хотите сделать?', reply_markup=markup)

    elif message.text == '⚙️ Настройки':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        weather_button = types.KeyboardButton('🌩️ Ежедневный прогноз погоды')
        markup.add(weather_button)
        bot.send_message(message.chat.id, 'Что вы хотите настроить?', reply_markup=markup)

    elif message.text == '➖  Удалить заметку':
        send_all_notes(message)

    elif message.text == '➕️  Добавить заметку':
        bot.send_message(message.chat.id, 'Напишите текст заметки')
        bot.register_next_step_handler(message, handle_note_text_message)

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
        city = message.text[6:].strip()
        set_city(message.chat.id, city)
        bot.send_message(message.chat.id, 'Город изменён')

    elif message.text[:8].lower().startswith('добавить'):  # добавление заметки
        parts_of_message = message.text[9:].strip().split()
        try:
            note_text = parts_of_message[0]
            time = parts_of_message[1]
            if len(parts_of_message) == 3:
                reminder_date = parts_of_message[2]
            else:
                reminder_date = str(date.today())
            if len(reminder_date) == 5:
                reminder_date = f'{str(date.today().year)}-{reminder_date}'
            elif len(reminder_date) == 2:
                month = str(date.today().month)
                if len(month) == 1:
                    month = f'0{month}'
                reminder_date = f'{str(date.today().year)}-{month}-{reminder_date}'

            if not is_already_existing_note(message.chat.id, note_text):
                add_reminder(time, delete_note, message.chat.id, note_text, reminder_date)
                add_note(message.chat.id, note_text, time, reminder_date)
                bot.send_message(message.chat.id, 'Заметка успешно добавлена')
            else:
                bot.send_message(message.chat.id, 'Ошибка: такая заметка уже существует')
        except:
            bot.send_message(message.chat.id, 'Ошибка: неверный формат ввода')

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
        user.should_send_weather = True

    elif callback == 'No':
        bot.answer_callback_query(call.id, 'Больше вы не будете получать прогноз погоды')
        user = session.query(Users).filter(Users.chat_id == chat_id).first()
        user.should_send_weather = False

    elif callback.startswith('delete'):
        note = callback[7:].split(';')[0]
        delete_note(chat_id, note)
        bot.delete_message(chat_id, int(callback[7:].split(';')[1]) + 1)
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
    city = get_city(chat_id)
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


def delete_note(chat_id, note_text, reminder_date=str(date.today())) -> None:  # удаление заметки
    if reminder_date == str(date.today()):
        session = create_session()
        session.query(Notes).filter(Notes.chat_id == chat_id, Notes.note_text == note_text).delete()
        session.commit()


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
        bot.send_message(chat_id, f'Напоминание: {note_text}', chat_id)
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


def set_city(chat_id, city):
    session = create_session()
    user = session.query(Users).filter(Users.chat_id == chat_id).first()
    user.city = city
    session.commit()


def get_city(chat_id):
    session = create_session()
    user = session.query(Users).filter(Users.chat_id == chat_id).first()
    return user.city


def handle_note_time_message(message, note_text):
    parts_of_message = message.text.strip().split()
    try:
        if len(parts_of_message) == 1:
            time = message.text.strip()
            reminder_date = str(date.today())
        elif len(parts_of_message) == 2:
            time = parts_of_message[0]
            reminder_date = parts_of_message[1]
            if len(reminder_date) == 5:
                reminder_date = f'{str(date.today().year)}-{reminder_date}'
            elif len(reminder_date) == 2:
                month = str(date.today().month)
                if len(month) == 1:
                    month = f'0{month}'
                reminder_date = f'{str(date.today().year)}-{month}-{reminder_date}'
        else:
            bot.send_message(message.chat.id, 'Ошибка: неверный формат ввода')
            return

        if not is_already_existing_note(message.chat.id, note_text):
            add_reminder(time, delete_note, message.chat.id, note_text, reminder_date)
            add_note(message.chat.id, note_text, time, reminder_date)
            bot.send_message(message.chat.id, 'Заметка успешно добавлена')
        else:
            bot.send_message(message.chat.id, 'Ошибка: такая заметка уже существует')
    except:
        bot.send_message(message.chat.id, 'Ошибка: неверный формат ввода')


def handle_note_text_message(message):
    note_text = message.text
    bot.send_message(message.chat.id, 'Когда напомнить о заметке?')
    bot.register_next_step_handler(message, handle_note_time_message, note_text)


main()
