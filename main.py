import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Хранилище: user_id -> {step, data}
user_state = {}

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_state[message.from_user.id] = {"step": "fio", "data": {}}
    await message.answer("👋 Здравствуйте! Я принимаю заявки. Напишите ваше ФИО:")

@dp.message_handler(lambda msg: user_state.get(msg.from_user.id, {}).get("step") == "fio")
async def process_fio(message: types.Message):
    data = user_state[message.from_user.id]["data"]
    data["fio"] = message.text
    user_state[message.from_user.id]["step"] = "org"
    await message.answer("Название организации (или напишите «физлицо»):")

@dp.message_handler(lambda msg: user_state.get(msg.from_user.id, {}).get("step") == "org")
async def process_org(message: types.Message):
    data = user_state[message.from_user.id]["data"]
    data["org"] = message.text
    user_state[message.from_user.id]["step"] = "phone"
    await message.answer("Ваш номер телефона (желательно +7…):")

@dp.message_handler(lambda msg: user_state.get(msg.from_user.id, {}).get("step") == "phone")
async def process_phone(message: types.Message):
    data = user_state[message.from_user.id]["data"]
    data["phone"] = message.text
    user_state[message.from_user.id]["step"] = "problem"
    await message.answer("Коротко опишите проблему:")

@dp.message_handler(lambda msg: user_state.get(msg.from_user.id, {}).get("step") == "problem")
async def process_problem(message: types.Message):
    data = user_state[message.from_user.id]["data"]
    data["problem"] = message.text

    # Формируем заявку
    report = (
        f"📩 НОВАЯ ЗАЯВКА\n"
        f"ФИО: {data['fio']}\n"
        f"Организация: {data['org']}\n"
        f"Телефон: {data['phone']}\n"
        f"Проблема: {data['problem']}"
    )

    try:
        await bot.send_message(chat_id=CHAT_ID, text=report)
        await message.answer("✅ Спасибо! Заявка отправлена. Мы свяжемся с вами.")
    except Exception as e:
        await message.answer("Произошла ошибка при отправке заявки. Позвоните нам напрямую.")
        print(e)

    # Очищаем состояние
    if message.from_user.id in user_state:
        del user_state[message.from_user.id]

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
