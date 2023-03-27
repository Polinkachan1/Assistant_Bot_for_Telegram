import telebot
from telebot import types
import json
from geopy import geocoders
import requests

token = '5845372418:AAHcJJDSzuUd74O2vgGBXkhUY929jFxFuPY'
api_key = 'e056937d-4d55-412f-ae71-ec9be10f67af'
bot = telebot.TeleBot(token)
city = 'Волгодонск'


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    edit_button = types.KeyboardButton('✏️ Редактировать список дел')
    settings_button = types.KeyboardButton('⚙️ Настройки')
    markup.add(edit_button, settings_button)
    bot.send_message(message.chat.id, 'Привет ✌', reply_markup=markup)


@bot.message_handler(commands=['return_to_menu'])
def return_to_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    edit_button = types.KeyboardButton('✏️ Редактировать список дел')
    settings_button = types.KeyboardButton('⚙️ Настройки')
    markup.add(edit_button, settings_button)
    bot.send_message(message.chat.id, text='Выберите любой пункт меню', reply_markup=markup)


@bot.message_handler(content_types=['text'])
def handle_replies(message):
    if message.text == '✏️ Редактировать список дел':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        delete_button = types.KeyboardButton('➖  Удалить дело')
        add_button = types.KeyboardButton('➕️  Добавить дело')
        markup.add(delete_button, add_button)
        bot.send_message(message.chat.id, text='Что именно вы хотите сделать?', reply_markup=markup)

    elif message.text == '⚙️ Настройки':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        weather_button = types.KeyboardButton('🌩️ Ежедневный прогноз погоды')
        notification_time_button = types.KeyboardButton('🔔 Выбрать время напоминаний')
        markup.add(weather_button, notification_time_button)
        bot.send_message(message.chat.id, text='Что вы хотите настроить?', reply_markup=markup)

    elif message.text == '➖  Удалить дело':
        ...  # должно выводить список дел и спрашивать, какое из них удалить

    elif message.text == '➕️  Добавить дело':
        ...  # должно спрашивать название дела и время, когда о нем напомнить

    elif message.text == '🌩️ Ежедневный прогноз погоды':
        markup = types.InlineKeyboardMarkup()
        weather_inline_yes = types.InlineKeyboardButton('✅ Да', callback_data='Yes')
        weather_inline_no = types.InlineKeyboardButton('❌ Нет', callback_data='No')
        markup.add(weather_inline_yes, weather_inline_no)
        bot.send_message(message.chat.id, text='Вы хотите ежедневно получать прогноз погоды?'.format(message.from_user),
                         reply_markup=markup)
        bot.send_message(message.chat.id, 'Чтобы изменить город напишите: "город  *название города* "')

    elif message.text == '🔔 Выбрать время напоминаний':
        ...  # должно принимать сообщение от пользователем с информацией о времени,
        # когда ему ежедневно напоминать о его списке дел

    elif message.text[:5].lower().startswith('город'):  # изменение города пользователя
        global city
        city = message.text[6:].strip()


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    request = call.data.split('_')

    if request[0] == 'Yes':
        bot.answer_callback_query(call.id, text='Теперь вы будете получать прогноз погоды')
    elif request[0] == 'No':
        bot.answer_callback_query(call.id, text='Больше вы не будете получать прогноз погоды')


def get_weather() -> str:  # получение информации о погоде
    geolocator = geocoders.Nominatim(user_agent="telebot")
    latitude = str(geolocator.geocode(city).latitude)
    longitude = str(geolocator.geocode(city).longitude)
    response = requests.get(f'https://api.weather.yandex.ru/v2/forecast/?lat={latitude}&lon={longitude}&lang=ru_RU',
                            headers={"X-Yandex-API-Key": 'e056937d-4d55-412f-ae71-ec9be10f67af'})
    data = response.json()
    day_forecast = data['forecasts'][0]['parts']['day_short']
    return f'''Погода на сегодня: температура {day_forecast["temp"]} °C, 
скорость ветра {day_forecast["wind_speed"]} м/с, вероятность осадков {day_forecast["prec_prob"]}%'''


bot.polling(none_stop=True, interval=0)
