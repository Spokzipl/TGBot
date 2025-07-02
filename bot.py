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

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import multiprocessing
from datetime import datetime

# === Config ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMINS_TG = os.getenv("ADMINS_TG", "")
ALLOWED_ADMINS = set(int(uid) for uid in ADMINS_TG.split(",") if uid.strip().isdigit())

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

                # Таблица bot_logs
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

                # Таблица citys
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

                # Таблица settings
                c.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        id SERIAL PRIMARY KEY,
                        city VARCHAR NOT NULL,
                        name VARCHAR NOT NULL,
                        enabled BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                print("[init_db] Таблица settings проверена/создана.")

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

# Новый маршрут API для получения данных о городе
@app.get("/api/city/{city_name}")
async def get_city(city_name: str):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        with closing(psycopg2.connect(DATABASE_URL)) as conn:
            with conn.cursor() as c:
                c.execute("SELECT subs, posts, income, tg_link FROM citys WHERE city = %s", (city_name,))
                row = c.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="City not found")
                subs, posts, income, tg_link = row
                return {
                    "city": city_name,
                    "subs": subs,
                    "posts": posts,
                    "income": income,
                    "tg_link": tg_link
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Новый маршрут API для получения настроек по городу
@app.get("/api/settings/{city}")
async def get_settings(city: str):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        with closing(psycopg2.connect(DATABASE_URL)) as conn:
            with conn.cursor() as c:
                c.execute("""
                    SELECT id, name, enabled, created_at, updated_at
                    FROM settings
                    WHERE city = %s
                    ORDER BY id
                """, (city,))
                rows = c.fetchall()
                if not rows:
                    return []
                result = []
                for r in rows:
                    id_, name, enabled, created_at, updated_at = r
                    result.append({
                        "id": id_,
                        "name": name,
                        "enabled": enabled,
                        "created_at": created_at.isoformat() if created_at else None,
                        "updated_at": updated_at.isoformat() if updated_at else None,
                    })
                return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API для обновления конкретного параметра настроек по ID
from pydantic import BaseModel

class SettingUpdate(BaseModel):
    name: str
    enabled: bool

@app.put("/api/settings/{id}")
async def update_setting(id: int, data: SettingUpdate):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        with closing(psycopg2.connect(DATABASE_URL)) as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE settings
                    SET name = %s, enabled = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, city, name, enabled, created_at, updated_at
                """, (data.name, data.enabled, id))
                row = c.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Setting not found")

                id_, city, name, enabled, created_at, updated_at = row
                return {
                    "id": id_,
                    "city": city,
                    "name": name,
                    "enabled": enabled,
                    "created_at": created_at.isoformat() if created_at else None,
                    "updated_at": updated_at.isoformat() if updated_at else None,
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_web():
    uvicorn.run(app, host="0.0.0.0", port=8000)

def run_bot():
    asyncio.run(start_bot())

if __name__ == "__main__":
    init_db()

    p_web = multiprocessing.Process(target=run_web)
    p_bot = multiprocessing.Process(target=run_bot)

    p_web.start()
    p_bot.start()

    p_web.join()
    p_bot.join()
