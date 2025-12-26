import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
import sqlite3
import os
from typing import Dict, List
import json

# Настройки
BOT_TOKEN = "8521703995:AAFVnALMcFsUxK2JHHSq-P0qkCbmIb5KSa8"
ADMIN_ID = 5522585352  # ID @wakeguarantee
CHANNEL_USERNAME = "@WakeDeff"  # Обязательный канал

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Хранилище состояний
user_states = {}
admin_states = {}

# База данных
def init_db():
    try:
        conn = sqlite3.connect('gift_bot.db')
        c = conn.cursor()
        
        # Пользователи
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      full_name TEXT,
                      gifts_requested INTEGER DEFAULT 0,
                      tasks_completed INTEGER DEFAULT 0,
                      is_subscribed BOOLEAN DEFAULT 0,
                      joined_date TIMESTAMP,
                      last_active TIMESTAMP)''')
        
        # Запросы подарков
        c.execute('''CREATE TABLE IF NOT EXISTS gift_requests
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      gift_name TEXT,
                      request_time TIMESTAMP,
                      status TEXT DEFAULT 'pending',
                      stars INTEGER DEFAULT 0)''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")

init_db()

# Проверка подписки
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

# Новогодняя клавиатура с одной кнопкой
def get_main_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🎁 ЗАГАДАТЬ ЖЕЛАНИЕ ДЕДУ МОРОЗУ", callback_data="get_gift")
    return keyboard.as_markup()

# Админ клавиатура
def get_admin_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📊 Статистика", callback_data="admin_stats")
    keyboard.button