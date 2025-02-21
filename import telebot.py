import telebot
import requests
from telebot import types
import aiosqlite
import asyncio
import logging
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO)

load_dotenv()
bot = telebot.TeleBot(os.getenv('TOKEN'))

user_history = {}
cities = ["Токио", "Ухань", "Тяньцзинь", "Москва", "Мумбаи", "Лахор",
    "Сан-Паулу", "Джакарта", "Дунгуань", "Дакка", "Хайдарабад",
    "Ханчжоу", "Ченнаи", "Лима", "ОКРУГ КОЛУМБИЯ"]

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "Доступные команды:\n"
        "/start — запуск программы и выбор города\n"
        "/history — вывод истории поиска\n"
        "/help — вывод этой справки\n\n"
        "Вы можете ввести название города, чтобы получить текущую погоду."
    )
    bot.send_message(message.from_user.id, help_text)


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add(types.KeyboardButton('/start'))
    markup.add(types.KeyboardButton('/help'))
    markup.add(types.KeyboardButton('/history'))
    markup.add(types.KeyboardButton('15 крупнейших городов мира'))
    # markup.add(types.KeyboardButton('/forecast'))

    bot.send_message(message.from_user.id,
                     f'Здравствуйте, {message.from_user.full_name}! Это бот прогноза погоды.'
                     f'\nНапишите боту название города или выберите из списка 15-ти крупнейших городов мира, '
                     f'и он скажет, какая там температура и как она ощущается!',
                     reply_markup=markup)

@bot.message_handler(commands=['history'])
def history(message):
    user_id = message.from_user.id
    history_records = asyncio.run(get_history(user_id))
    if history_records:
        history_text = '\n'.join([f"{record[0]} - {record[1][:10]}" for record in history_records])
        bot.send_message(user_id, f'Ваша история запросов:\n{history_text}')
    else:
        bot.send_message(user_id, 'История запросов пуста.')

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == '15 крупнейших городов мира':
        cities_list = '\n'.join(cities)
        bot.send_message(message.from_user.id, f'Список 15 крупнейших городов мира:\n{cities_list}')
    else:
        weather(message)

def weather(message):
    city = message.text.strip().upper()
    user_id = message.from_user.id
    asyncio.run(add_to_history(user_id, city))
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append(city)

    url = (f'https://api.openweathermap.org/data/2.5/weather?q={city}'
         f'&units=metric&lang=ru&appid=79d1ca96933b0328e1c7e3e7a26cb347')
    response = requests.get(url)
    data = response.json()

    if response.status_code == 200:
        temperature = round(data['main']['temp'])
        temperature_feels = round(data['main']['feels_like'])
        w_now = f'Сейчас в городе {city} ' + str(temperature) + ' °C'
        w_feels = 'Ощущается как ' + str(temperature_feels) + ' °C'
        bot.send_message(message.from_user.id, w_now)
        lat = data['coord']['lat']
        lon = data['coord']['lon']
        forecast_url = (f'https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}'
                        f'&exclude=current,minutely,hourly,alerts&units=metric&lang=ru&appid=79d1ca96933b0328e1c7e3e7a26cb347')
        forecast_response = requests.get(forecast_url)
        forecast_data = forecast_response.json()

        if temperature < 5:
          bot.send_message(message.from_user.id, 'Холодно 🥶')
        elif temperature < 10:
          bot.send_message(message.from_user.id, 'Нормально 🙂')
        elif temperature < 20:
          bot.send_message(message.from_user.id, 'Тепло ☺️')
        elif temperature < 60:
          bot.send_message(message.from_user.id, 'Жарко 🥵')
        bot.send_message(message.from_user.id, w_feels)
        wind_speed = round(data['wind']['speed'])

        if wind_speed < 5:
          bot.send_message(message.from_user.id, '✅ Погода хорошая, ветра почти нет.')
        elif wind_speed < 10:
          bot.send_message(message.from_user.id, '🌬️ На улице ветрено.')
        elif wind_speed < 20:
          bot.send_message(message.from_user.id, '🌀 Ветер очень сильный, будьте осторожны, выходя из дома!')
        else:
          bot.send_message(message.from_user.id, '🌪️ На улице шторм, на улицу лучше не выходить!')
    else:
        bot.send_message(message.from_user.id, 'Город введен не верно!')

    if forecast_response.status_code == 200:
        forecast_text = "Прогноз на 7 дней:\n"
        for day in forecast_data['daily'][:7]:
            day_temp = round(day['temp']['day'])
            day_feels_like = round(day['feels_like']['day'])
            weather_description = day['weather'][0]['description']
            forecast_text += (f"Температура: {day_temp} °C, "
                              f"Ощущается как: {day_feels_like} °C, "
                              f"Погода: {weather_description}\n")
        bot.send_message(message.from_user.id, forecast_text)
    else:
        bot.send_message(message.from_user.id, 'Не удалось получить прогноз погоды на 7 дней.')


DATABASE = 'weather_bot.db'

async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS history (
                  user_id INTEGER, city TEXT, date TEXT)''')
        await db.commit()

async def add_to_history(user_id, city):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('INSERT INTO history (user_id, city, date) '
                         'VALUES (?, ?, datetime("now"))', (user_id, city))
        await db.commit()

async def get_history(user_id, date=None):
    async with aiosqlite.connect(DATABASE) as db:
        if date:
            cursor = await db.execute('SELECT city, date FROM history WHERE user_id = ? AND date(date) = ?',
                                      (user_id, date))
        else:
            cursor = await db.execute('SELECT city, date FROM history WHERE user_id = ?', (user_id,))
        rows = await cursor.fetchall()
        return rows

if __name__ == '__main__':
    asyncio.run(init_db())
    while True:
        try:
            bot.polling(none_stop=True, interval=0)
        except Exception as exc:
            logging.error(f'Exception occurred: {exc}')


# @bot.message_handler(commands=['forecast'])
# def handle_forecast(message):
#     city = message.text.strip().upper()
#     user_id = message.from_user.id
#     asyncio.run(add_to_history(user_id, city))
#     if user_id not in user_history:
#         user_history[user_id] = []
#     user_history[user_id].append(city)

#     url = (f'https://api.openweathermap.org/data/2.5/weather?q={city}'
#            f'&units=metric&lang=ru&appid=79d1ca96933b0328e1c7e3e7a26cb347')
#     response = requests.get(url)
#     data = response.json()

#     if response.status_code == 200:
#         lat = data['coord']['lat']
#         lon = data['coord']['lon']
#         forecast_url = (f'https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}'
#                         f'&exclude=current,minutely,hourly,alerts&units=metric&lang=ru&appid=79d1ca96933b0328e1c7e3e7a26cb347')
#         forecast_response = requests.get(forecast_url)
#         forecast_data = forecast_response.json()

#         if forecast_response.status_code == 200:
#             forecast_text = "Прогноз на 7 дней:\n"
#             for day in forecast_data['daily'][:7]:
#                 day_temp = round(day['temp']['day'])
#                 day_feels_like = round(day['feels_like']['day'])
#                 weather_description = day['weather'][0]['description']
#                 forecast_text += (f"Температура: {day_temp} °C, "
#                                   f"Ощущается как: {day_feels_like} °C, "
#                                   f"Погода: {weather_description}\n")
#             bot.send_message(message.from_user.id, forecast_text)
#         else:
#             bot.send_message(message.from_user.id, 'Не удалось получить прогноз погоды на 7 дней.')
#     else:
#         bot.send_message(message.from_user.id, 'Город введен не верно!')