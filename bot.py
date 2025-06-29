import os
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.enums import ParseMode
from aiogram.types import WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# === Telegram Bot Setup ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Открыть Web App", web_app=WebAppInfo(url="https://tgbot-production-1c7c.up.railway.app"))]
        ],
        resize_keyboard=True
    )
    await message.answer("Привет! Вот кнопка для запуска WebApp.", reply_markup=kb)

async def start_bot():
    await dp.start_polling(bot)

# === FastAPI Setup ===
app = FastAPI()

# Статические файлы и главная страница (если есть)
app.mount("/Static", StaticFiles(directory="Static"), name="Static")

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

async def start_web():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

# === Main Run ===
if __name__ == "__main__":
    asyncio.run(asyncio.gather(
        start_bot(),
        start_web()
    ))
