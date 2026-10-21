import os
import csv
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# --- ПЕРЕМЕННЫЕ ---
API_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_RAW = os.getenv("CHAT_ID")

if not CHAT_ID_RAW:
    raise RuntimeError("Переменная окружения CHAT_ID не задана! Зайди в Render → Environment и добавь её.")

ADMIN_CHAT_ID = int(CHAT_ID_RAW)
REQUESTS_FILE = "requests.csv"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# --- РАБОТА С CSV ---
def init_csv():
    if not os.path.exists(REQUESTS_FILE):
        with open(REQUESTS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Добавили user_id, чтобы потом написать клиенту
            writer.writerow(["id", "user_id", "name", "phone", "description", "status", "timestamp"])

init_csv()

def save_request(user_id, name, phone, description, status="new"):
    req_id = int(time.time())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(REQUESTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([req_id, user_id, name, phone, description, status, timestamp])
    return req_id

def mark_as_done(req_id):
    rows = []
    found = False
    target_user_id = None
    with open(REQUESTS_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["id"]) == req_id:
                row["status"] = "done"
                found = True
                target_user_id = row["user_id"]  # Запоминаем user_id клиента
            rows.append(row)

    if found:
        with open(REQUESTS_FILE, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["id", "user_id", "name", "phone", "description", "status", "timestamp"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return True, target_user_id
    return False, None

# --- КЛАВИАТУРЫ ---
menu_kb = ReplyKeyboardMarkup(resize_keyboard=True)
menu_kb.add("🆕 Создать обращение")
menu_kb.add("❓ Помощь / О нас")

user_states = {}

# --- ХЕНДЛЕРЫ ---
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот техподдержки для малого бизнеса.\n"
        "Нажмите кнопку ниже, чтобы создать обращение.",
        reply_markup=menu_kb
    )

@dp.message_handler(lambda m: m.text == "🆕 Создать обращение")
async def start_request(message: types.Message):
    # Сохраняем user_id сразу при старте диалога
    user_states[message.from_user.id] = {"step": "name", "data": {"user_id": message.from_user.id}}
    await message.answer("Напишите ваше имя или название организации:")

@dp.message_handler(lambda m: m.from_user.id in user_states)
async def collect_request(message: types.Message):
    print(f"DEBUG: Sending to ADMIN_CHAT_ID={ADMIN_CHAT_ID}")

    state = user_states.get(message.from_user.id)
    if not state:
        return
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

        # Передаём user_id в save_request
        req_id = save_request(data["user_id"], data["name"], data["phone"], data["description"])

        inline_kb = InlineKeyboardMarkup()
        inline_kb.add(InlineKeyboardButton("✅ Сделано", callback_data=f"done_{req_id}"))

        admin_text = (
            f"🆕 Новая заявка #{req_id}\n"
            f"Имя: {data['name']}\n"
            f"Телефон: {data['phone']}\n"
            f"Описание: {data['description']}"
        )

        await bot.send_message(ADMIN_CHAT_ID, admin_text, reply_markup=inline_kb)
        await message.answer("✅ Заявка отправлена! Мы свяжемся с вами в ближайшее время.", reply_markup=menu_kb)
        del user_states[message.from_user.id]

@dp.message_handler(lambda m: m.text == "❓ Помощь / О нас")
async def help_info(message: types.Message):
    await message.answer(
        "🛠 Техподдержка для малого бизнеса\n"
        "Мы помогаем с настройкой ПК, ПО и оргтехники.\n"
        "Чтобы оставить заявку — нажмите «Создать обращение».",
        reply_markup=menu_kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("done_"))
async def process_done(callback_query: types.CallbackQuery):
    _, req_id_str = callback_query.data.split("_", 1)
    req_id = int(req_id_str)

    success, target_user_id = mark_as_done(req_id)

    if success and target_user_id:
        # Уведомляем клиента
        try:
            await bot.send_message(
                int(target_user_id),
                f"✅ Ваша заявка #{req_id} выполнена! Спасибо за обращение."
            )
        except Exception as e:
            # Если клиент заблокировал бота — просто логируем и продолжаем
            print(f"DEBUG: Не удалось отправить уведомление клиенту (возможно, бот заблокирован): {e}")

        await callback_query.message.edit_text(
            f"{callback_query.message.text}\n\n✅ Заявка #{req_id} помечена как выполненная."
        )
        await callback_query.answer()
    else:
        await callback_query.answer("Не удалось найти заявку.", show_alert=True)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
