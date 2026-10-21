import os
import csv
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = os.getenv("BOT_TOKEN")

# Путь к файлу заявок
REQUESTS_FILE = "requests.csv"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Создаём CSV, если его нет
def init_csv():
    if not os.path.exists(REQUESTS_FILE):
        with open(REQUESTS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "phone", "description", "status", "timestamp"])

init_csv()

# Функция сохранения заявки
def save_request(name, phone, description, status="new"):
    # Генерируем ID (можно использовать timestamp + случайное число)
    req_id = int(time.time())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(REQUESTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([req_id, name, phone, description, status, timestamp])
    return req_id

# Функция обновления статуса
def mark_as_done(req_id):
    rows = []
    found = False
    with open(REQUESTS_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["id"]) == req_id:
                row["status"] = "done"
                found = True
            rows.append(row)

    if found:
        with open(REQUESTS_FILE, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["id", "name", "phone", "description", "status", "timestamp"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return True
    return False

# Клавиатура с кнопкой «Оставить заявку»
start_kb = ReplyKeyboardMarkup(resize_keyboard=True)
start_kb.add("📝 Оставить заявку")

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот техподдержки. Нажмите «Оставить заявку», чтобы описать проблему.",
        reply_markup=start_kb
    )

# Состояние: шаг сбора заявки
user_states = {}  # user_id -> {"step": ..., "data": {...}}

@dp.message_handler(lambda m: m.text == "📝 Оставить заявку")
async def start_request(message: types.Message):
    user_states[message.from_user.id] = {"step": "name", "data": {}}
    await message.answer("Напишите ваше имя или название организации:")

@dp.message_handler(lambda m: m.from_user.id in user_states)
async def collect_request(message: types.Message):
    state = user_states[message.from_user.id]
    data = state["data"]

    if state["step"] == "name":
        data["name"] = message.text
        state["step"] = "phone"
        await message.answer("Укажите номер телефона для связи:")

    elif state["step"] == "phone":
        data["phone"] = message.text
        state["step"] = "desc"
        await message.answer("Опишите проблему или задачу (коротко):")

    elif state["step"] == "desc":
        data["description"] = message.text

        # Сохраняем заявку
        req_id = save_request(data["name"], data["phone"], data["description"])

        # Кнопка «✅ Сделано»
        inline_kb = InlineKeyboardMarkup()
        inline_kb.add(InlineKeyboardButton("✅ Сделано", callback_data=f"done_{req_id}"))

        # Отправляем заявку тебе (укажи свой chat_id или используй пересылку)
        admin_text = (
            f"🆕 Новая заявка #{req_id}\n"
            f"Имя: {data['name']}\n"
            f"Телефон: {data['phone']}\n"
            f"Описание: {data['description']}"
        )
        # Замени на свой chat_id (можно узнать через @userinfobot)
        ADMIN_CHAT_ID = 6642850412

        sent = await bot.send_message(ADMIN_CHAT_ID, admin_text, reply_markup=inline_kb)

        await message.answer("✅ Заявка отправлена! Мы свяжемся с вами в ближайшее время.")
        del user_states[message.from_user.id]

@dp.callback_query_handler(lambda c: c.data.startswith("done_"))
async def process_done(callback_query: types.CallbackQuery):
    _, req_id_str = callback_query.data.split("_", 1)
    req_id = int(req_id_str)

    if mark_as_done(req_id):
        await callback_query.message.edit_text(
            f"{callback_query.message.text}\n\n✅ Заявка #{req_id} помечена как выполненная."
        )
        await callback_query.answer()
    else:
        await callback_query.answer("Не удалось найти заявку.", show_alert=True)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
