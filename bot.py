from aiogram import Bot, Dispatcher, executor, types
import os

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Токен бота из BotFather

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer("Привет! Вот кнопки с городами.", reply_markup=types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Открыть Web App", web_app=types.WebAppInfo(url="https://твой-сервер.railway.app/"))]
        ],
        resize_keyboard=True
    ))

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
