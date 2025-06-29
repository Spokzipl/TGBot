import os
import asyncio
import psycopg2
from contextlib import closing
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

# === Config ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Список ID админов из переменной окружения
ADMINS_TG = os.getenv("ADMINS_TG", "")
ALLOWED_ADMINS = set(int(uid) for uid in ADMINS_TG.split(",") if uid.strip().isdigit())

# Разрешить всем или только админам
ALLOW_ALL_USERS_BOT = os.getenv("ALLOW_ALL_USERS_BOT", "false").lower() == "true"

def is_user_allowed(user_id: int) -> bool:
    return ALLOW_ALL_USERS_BOT or user_id in ALLOWED_ADMINS

def init_db():
    if not DATABASE_URL:
        print("[init_db] DATABASE_URL не задана в переменных окружения!")
        return

    cities = [
        ('Vienna', 0, 0, '', '$0.00'),
        ('Paris', 0, 0, '', '$0.00'),
        ('Barcelona', 0, 0, '', '$0.00'),
        ('Prague', 0, 0, '', '$0.00')
    ]

    try:
        with closing(psycopg2.connect(DATABASE_URL)) as conn:
            conn.set_client_encoding('UTF8')
            with conn.cursor() as c:
                # УДАЛЕНИЕ таблицы citys (чтобы "снести" базу). Потом можно закомментировать эту строку
                c.execute('DROP TABLE IF EXISTS citys')

                # Таблица для логов бота
                c.execute('''
                    CREATE TABLE IF NOT EXISTS bot_logs (
                        id SERIAL PRIMARY KEY,
                        tg_id BIGINT NOT NULL,
                        username TEXT,
                        full_name TEXT,
                        text TEXT,
                        has_access BOOLEAN,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                print("[init_db] Таблица bot_logs проверена/создана.")

                # Таблица citys с городами и данными + поле created_at
                c.execute('''
                    CREATE TABLE IF NOT EXISTS citys (
                        id SERIAL PRIMARY KEY,
                        city TEXT NOT NULL UNIQUE,
                        subs INT NOT NULL DEFAULT 0,
                        posts INT NOT NULL DEFAULT 0,
                        tg_link TEXT NOT NULL DEFAULT '',
                        income TEXT NOT NULL DEFAULT '$0.00',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Для каждого города проверяем наличие и вставляем, если его нет
                for city, subs, posts, tg_link, income in cities:
                    c.execute('SELECT 1 FROM citys WHERE city = %s', (city,))
                    if not c.fetchone():
                        c.execute(
                            '''INSERT INTO citys (city, subs, posts, tg_link, income, created_at)
                               VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)''',
                            (city, subs, posts, tg_link, income)
                        )
                        print(f"[init_db] Добавлен город: {city}")
                    else:
                        print(f"[init_db] Город {city} уже есть в таблице.")

                conn.commit()
    except Exception as e:
        print(f"[init_db] Ошибка при работе с БД: {e}")

def log_message_to_db(message: types.Message, has_access: bool):
    if not DATABASE_URL:
        return
    try:
        with closing(psycopg2.connect(DATABASE_URL)) as conn:
            conn.set_client_encoding('UTF8')
            with conn.cursor() as c:
                c.execute(
                    "INSERT INTO bot_logs (tg_id, username, full_name, text, has_access) VALUES (%s, %s, %s, %s, %s)",
                    (
                        message.from_user.id,
                        message.from_user.username if message.from_user.username else None,
                        f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(),
                        message.text,
                        has_access,
                    )
                )
                conn.commit()
    except Exception as e:
        print(f"[log_message_to_db] Ошибка записи лога: {e}")

# === Telegram Bot Setup ===
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    allowed = is_user_allowed(message.from_user.id)
    log_message_to_db(message, allowed)
    if not allowed:
        await message.answer("⛔️ У вас нет доступа к этому боту.")
        return

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Открыть Web App", web_app=WebAppInfo(url="https://tgbot-production-1c7c.up.railway.app"))]
        ],
        resize_keyboard=True
    )
    await message.answer("Привет! Вот кнопка для запуска WebApp.", reply_markup=kb)

# Логируем все сообщения (не только /start)
@router.message()
async def log_all_messages(message: types.Message):
    allowed = is_user_allowed(message.from_user.id)
    log_message_to_db(message, allowed)

async def start_bot():
    await dp.start_polling(bot)

# === FastAPI Setup ===
app = FastAPI()

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
async def main():
    init_db()  # Проверяем и создаём таблицы и начальные данные при старте
    await asyncio.gather(
        start_bot(),
        start_web()
    )

if __name__ == "__main__":
    asyncio.run(main())
