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
    keyboard.button(text="📢 Рассылка", callback_data="admin_broadcast")
    keyboard.button(text="👥 Пользователи", callback_data="admin_users")
    keyboard.button(text="🎁 Запросы подарков", callback_data="admin_requests")
    keyboard.adjust(2)
    return keyboard.as_markup()

# ============= ОСНОВНЫЕ КОМАНДЫ =============

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name
    
    # Сохраняем пользователя
    conn = sqlite3.connect('gift_bot.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, full_name, joined_date, last_active) 
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, full_name, datetime.now(), datetime.now()))
    c.execute('''UPDATE users SET last_active = ? WHERE user_id = ?''',
              (datetime.now(), user_id))
    conn.commit()
    conn.close()
    
    # Проверяем подписку
    is_subscribed = await check_subscription(user_id)
    
    if is_subscribed:
        await message.answer(
            "<b>🎅 Добро пожаловать в Волшебную Мастерскую Деда Мороза!</b>\n\n"
            "✨ Я - <b>Дед Мороз</b>, и я дарю новогодние подарки в Telegram!\n\n"
            "🎄 Выберите подарок стоимостью <b>до 150 звёзд</b> и выполните простое задание!\n\n"
            "👇 Нажмите кнопку ниже, чтобы загадать желание:",
            reply_markup=get_main_keyboard()
        )
    else:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="✅ ПОДПИСАТЬСЯ НА ВОЛШЕБСТВО", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
        keyboard.button(text="✅ Я ПОДПИСАЛСЯ НА ЧУДЕСА", callback_data="check_subscription")
        
        await message.answer(
            "<b>🎄 Для входа в Волшебную Мастерскую нужно подписаться на канал чудес!</b>\n\n"
            f"📢 Канал волшебства: {CHANNEL_USERNAME}\n\n"
            "После подписки нажмите кнопку ниже:",
            reply_markup=keyboard.as_markup()
        )

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)
    
    if is_subscribed:
        conn = sqlite3.connect('gift_bot.db')
        c = conn.cursor()
        c.execute('''UPDATE users SET is_subscribed = 1 WHERE user_id = ?''', (user_id,))
        conn.commit()
        conn.close()
        
        await callback.message.edit_text(
            "<b>✅ Превосходно! Вы в мастерской чудес!</b>\n\n"
            "🎅 Теперь Дед Мороз готов услышать ваше желание:\n\n"
            "👇 Нажмите кнопку ниже:",
            reply_markup=get_main_keyboard()
        )
    else:
        await callback.answer("❌ Вы ещё не подписались на канал чудес!", show_alert=True)

@dp.callback_query(F.data == "get_gift")
async def get_gift_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # Проверяем подписку
    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        await callback.answer("❌ Сначала подпишитесь на канал чудес!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "<b>🎄 ВОЛШЕБНЫЙ МОМЕНТ!</b>\n\n"
        "✨ <b>Дед Мороз слушает ваше желание...</b>\n\n"
        "🎁 Выберите новогодний подарок стоимостью <b>ДО 150 ЗВЁЗД</b> и напишите его сюда:\n\n"
        "Примеры подарков:\n"
        "• Новогодний стикерпак (50 звёзд)\n"
        "• Зимняя анимация (75 звёзд)\n"
        "• Праздничный премиум (100 звёзд)\n"
        "• Волшебный бот (120 звёзд)\n"
        "• Новогодние смайлики (150 звёзд)\n\n"
        "⭐ <i>Укажите стоимость в звёздах после названия подарка</i>"
    )
    
    # Устанавливаем состояние ожидания подарка
    user_states[user_id] = {"awaiting_gift": True}

@dp.message(F.text)
async def process_gift_request(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем, ждем ли мы подарок от этого пользователя
    if user_id not in user_states or not user_states[user_id].get("awaiting_gift"):
        return
    
    gift_name = message.text.strip()
    
    # Сохраняем запрос
    conn = sqlite3.connect('gift_bot.db')
    c = conn.cursor()
    c.execute('''INSERT INTO gift_requests (user_id, gift_name, request_time) 
                 VALUES (?, ?, ?)''',
              (user_id, gift_name, datetime.now()))
    c.execute('''UPDATE users SET gifts_requested = gifts_requested + 1 
                 WHERE user_id = ?''', (user_id,))
    conn.commit()
    conn.close()
    
    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except:
        pass
    
    # Удаляем состояние
    user_states.pop(user_id, None)
    
    # Первое сообщение
    msg1 = await message.answer("<b>✅ Ваше желание доставлено Деду Морозу!</b>")
    await asyncio.sleep(2)
    
    # Второе сообщение
    await msg1.delete()
    msg2 = await message.answer("<b>🎅 Хо Хо Хо!</b>")
    await asyncio.sleep(2)
    
    # Третье сообщение
    await msg2.delete()
    msg3 = await message.answer("<b>✨ Дед Мороз спешит выполнять ваше желание...</b>")
    await asyncio.sleep(2)
    
    # Четвертое сообщение
    await msg3.delete()
    
    # Финальное сообщение с инструкцией в новогоднем стиле
    instructions = (
        "<b>🎄 ВОЛШЕБНОЕ ЗАДАНИЕ ОТ ДЕДА МОРОЗА!</b>\n\n"
        "🎁 Чтобы получить <b>НОВОГОДНИЙ ПОДАРОК</b>, выполните волшебное задание:\n\n"
        "1️⃣ 🎅 <b>Зайдите в TikTok</b>\n"
        "2️⃣ 🔍 <b>Напишите в поиск</b>: <code>подарки тг</code> или <code>дарит подарки</code>\n"
        "3️⃣ 💬 <b>Под 20 ВОЛШЕБНЫМИ ВИДЕО</b> напишите по <b>2 КОММЕНТАРИЯ</b>:\n"
        "   • <code>@WakeGiftRoBot дарит новогодние 🎁</code>\n"
        "   • <code>Как хорошо что @wakeGiftRoBot дарит подарки на Новый Год</code>\n"
        "   • <code>Дарит только Дед Мороз - @WakeGiftRoBot</code>\n\n"
        "4️⃣ ❤️ <b>Если видите комментарии с юзернеймом нашего бота - ЛАЙКАЙТЕ и ОТВЕЧАЙТЕ</b> на него:\n"
        "   • <code>Дед Мороз реально дарит!</code>\n\n"
        "🎯 <b>За такое я буду выдавать ВОЛШЕБНЫЙ БОНУС!</b>\n\n"
        "📸 <b>СКРИНШОТЫ выполнения отправляйте в Волшебный Почтовый Ящик:</b>\n"
        "👉 @ScreenWakeBot\n\n"
        "⏳ <b>После этого ждите своего подарка под ёлкой!</b>\n\n"
        "🎄 <b>С НОВЫМ ГОДОМ И ВОЛШЕБСТВА ВАШЕМУ ДОМУ!</b>\n\n"
        f"📢 <b>Обязательная подписка на чудеса:</b> {CHANNEL_USERNAME}"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Я ВЫПОЛНИЛ ВОЛШЕБНОЕ ЗАДАНИЕ", url="https://tiktok.com")
    keyboard.button(text="🎬 TikTok", url="https://tiktok.com")
    keyboard.button(text="🔄 Загадать другое желание", callback_data="get_gift")
    keyboard.adjust(1)
    
    await message.answer(instructions, reply_markup=keyboard.as_markup())
    
    # Уведомляем админа
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🎁 Новое желание для Деда Мороза!\n\n"
            f"👤 Ребенок: @{message.from_user.username or 'нет username'}\n"
            f"🆔 ID: {user_id}\n"
            f"🎁 Желание: {gift_name}\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n"
            f"🎄 Статус: Ожидает исполнения"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")

# ============= АДМИН ПАНЕЛЬ =============

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} пытается войти в админку")
    
    if user_id == ADMIN_ID:
        logger.info(f"Доступ разрешен для {user_id}")
        await message.answer(
            "<b>🎅 МАСТЕРСКАЯ ДЕДА МОРОЗА (АДМИН ПАНЕЛЬ)</b>\n\n"
            "Выберите действие:",
            reply_markup=get_admin_keyboard()
        )
    else:
        logger.warning(f"Доступ запрещен для {user_id}")
        await message.answer("🎄 Эта мастерская только для Деда Мороза!")

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🎄 Только Дед Мороз может смотреть статистику!", show_alert=True)
        return
    
    conn = sqlite3.connect('gift_bot.db')
    c = conn.cursor()
    
    # Общая статистика
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_subscribed = 1")
    subscribed_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM gift_requests")
    total_requests = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM gift_requests WHERE status = 'pending'")
    pending_requests = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM gift_requests WHERE status = 'completed'")
    completed_requests = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM gift_requests")
    users_with_requests = c.fetchone()[0]
    
    # Активность за последние 24 часа
    yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    c.execute("SELECT COUNT(*) FROM users WHERE joined_date > ?", (yesterday,))
    new_today = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM gift_requests WHERE request_time > ?", (yesterday,))
    requests_today = c.fetchone()[0]
    
    # Топ пользователей
    c.execute('''SELECT user_id, username, gifts_requested, tasks_completed 
                 FROM users ORDER BY gifts_requested DESC LIMIT 5''')
    top_users = c.fetchall()
    
    conn.close()
    
    stats_text = (
        "<b>📊 ВОЛШЕБНАЯ СТАТИСТИКА МАСТЕРСКОЙ</b>\n\n"
        f"👥 Всего детей в списках: <b>{total_users}</b>\n"
        f"✅ Верят в чудеса (подписаны): <b>{subscribed_users}</b>\n"
        f"🎁 Всего загаданных желаний: <b>{total_requests}</b>\n"
        f"⏳ Желаний в работе: <b>{pending_requests}</b>\n"
        f"✅ Исполнено желаний: <b>{completed_requests}</b>\n"
        f"👤 Детей с желаниями: <b>{users_with_requests}</b>\n\n"
        f"📈 <b>СЕГОДНЯ ({datetime.now().strftime('%d.%m')}):</b>\n"
        f"   • Новых детей: <b>{new_today}</b>\n"
        f"   • Новых желаний: <b>{requests_today}</b>\n\n"
        "<b>🏆 ТОП-5 САМЫХ ВЕРЯЩИХ В ЧУДЕСА:</b>\n"
    )
    
    for i, (uid, username, gifts, tasks) in enumerate(top_users, 1):
        username = username or "Анонимный ребёнок"
        star = "⭐" * min(gifts, 5)
        stats_text += f"{i}. @{username} | 🎁: {gifts} | ✅: {tasks} {star}\n"
    
    stats_text += f"\n⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔄 Обновить", callback_data="admin_stats")
    keyboard.button(text="🎅 В мастерскую", callback_data="admin_menu")
    keyboard.adjust(2)
    
    await callback.message.edit_text(stats_text, reply_markup=keyboard.as_markup())

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🎄 Только Дед Мороз может делать рассылку!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "<b>📢 РАССЫЛКА ВОЛШЕБНЫХ ПОСЛАНИЙ</b>\n\n"
        "🎅 Отправьте сообщение для рассылки всем детям.\n"
        "✨ Можно использовать HTML разметку.\n\n"
        "⚠️ <i>Сообщение будет отправлено ВСЕМ детям в списках</i>\n\n"
        "<i>Пример новогоднего сообщения:</i>\n"
        "<code>🎄 С Новым Годом, дорогие дети! ✨\n"
        "Дед Мороз готовит для вас подарки! 🎁</code>",
        reply_markup=InlineKeyboardBuilder()
            .button(text="❌ Отмена", callback_data="admin_menu")
            .as_markup()
    )
    
    admin_states[ADMIN_ID] = {"awaiting_broadcast": True}

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🎄 Только Дед Мороз может смотреть список детей!", show_alert=True)
        return
    
    conn = sqlite3.connect('gift_bot.db')
    c = conn.cursor()
    c.execute('''SELECT user_id, username, gifts_requested, joined_date 
                 FROM users ORDER BY joined_date DESC LIMIT 50''')
    users = c.fetchall()
    conn.close()
    
    if not users:
        await callback.message.edit_text("🎄 В списках ещё нет детей!")
        return
    
    users_text = "<b>👥 ПОСЛЕДНИЕ 50 ДЕТЕЙ В МАСТЕРСКОЙ</b>\n\n"
    
    for i, (uid, username, gifts, joined) in enumerate(users, 1):
        username = username or "Анонимный ребёнок"
        if isinstance(joined, str):
            date_str = datetime.strptime(joined, "%Y-%m-%d %H:%M:%S.%f").strftime("%d.%m %H:%M")
        else:
            date_str = joined.strftime("%d.%m %H:%M") if hasattr(joined, 'strftime') else str(joined)
        star = "⭐" if gifts > 0 else ""
        users_text += f"{i}. ID: <code>{uid}</code> | @{username} | 🎁: {gifts} {star} | 📅: {date_str}\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🎅 В мастерскую", callback_data="admin_menu")
    
    await callback.message.edit_text(users_text, reply_markup=keyboard.as_markup())

@dp.callback_query(F.data == "admin_requests")
async def admin_requests(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🎄 Только Дед Мороз может смотреть желания!", show_alert=True)
        return
    
    conn = sqlite3.connect('gift_bot.db')
    c = conn.cursor()
    c.execute('''SELECT gr.id, gr.user_id, u.username, gr.gift_name, gr.request_time, gr.status
                 FROM gift_requests gr
                 LEFT JOIN users u ON gr.user_id = u.user_id
                 ORDER BY gr.request_time DESC LIMIT 20''')
    requests = c.fetchall()
    conn.close()
    
    if not requests:
        await callback.message.edit_text("🎄 Ещё нет загаданных желаний!")
        return
    
    requests_text = "<b>🎁 ПОСЛЕДНИЕ 20 ЖЕЛАНИЙ ДЕТЕЙ</b>\n\n"
    
    for req_id, user_id, username, gift, req_time, status in requests:
        username = username or "Анонимный ребёнок"
        if isinstance(req_time, str):
            time_str = datetime.strptime(req_time, "%Y-%m-%d %H:%M:%S.%f").strftime("%d.%m %H:%M")
        else:
            time_str = req_time.strftime("%d.%m %H:%M") if hasattr(req_time, 'strftime') else str(req_time)
        status_icon = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
        requests_text += f"{status_icon} #{req_id} | @{username}\n🎁 {gift[:30]}... | 🕒 {time_str}\n\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🎅 В мастерскую", callback_data="admin_menu")
    
    await callback.message.edit_text(requests_text, reply_markup=keyboard.as_markup())

@dp.callback_query(F.data == "admin_menu")
async def admin_menu(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    await callback.message.edit_text(
        "<b>🎅 МАСТЕРСКАЯ ДЕДА МОРОЗА (АДМИН ПАНЕЛЬ)</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard()
    )

# ============= РАССЫЛКА =============

@dp.message(F.content_type.in_({'text', 'photo'}))
async def process_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if ADMIN_ID not in admin_states or not admin_states[ADMIN_ID].get("awaiting_broadcast"):
        return
    
    admin_states.pop(ADMIN_ID, None)
    
    # Получаем всех пользователей
    conn = sqlite3.connect('gift_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    
    total_users = len(users)
    successful = 0
    failed = 0
    
    # Отправка прогресса
    progress_msg = await message.answer(
        f"📤 <b>Дед Мороз начинает рассылку...</b>\n"
        f"🎄 Отправлено: 0/{total_users}"
    )
    
    # Рассылка
    for i, user_id in enumerate(users, 1):
        try:
            if message.photo:
                await bot.send_photo(
                    user_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or "",
                    parse_mode=ParseMode.HTML
                )
            else:
                # Добавляем новогодний стиль к текстовым сообщениям
                broadcast_text = message.text
                if not broadcast_text.startswith("🎄") and not broadcast_text.startswith("🎅"):
                    broadcast_text = f"🎅 {broadcast_text}\n\n✨ С любовью, Дед Мороз"
                
                await bot.send_message(
                    user_id,
                    broadcast_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            successful += 1
        except Exception as e:
            failed += 1
        
        # Обновление прогресса каждые 10 сообщений
        if i % 10 == 0 or i == total_users:
            await progress_msg.edit_text(
                f"📤 <b>Дед Мороз в пути...</b>\n"
                f"✅ Отправлено: {i}/{total_users}\n"
                f"✨ Успешно доставлено: {successful}\n"
                f"❌ Пропущено: {failed}"
            )
        await asyncio.sleep(0.1)
    
    await message.answer(
        f"<b>✅ Волшебная рассылка завершена!</b>\n\n"
        f"👥 Всего детей в списках: {total_users}\n"
        f"✅ Успешно доставлено: {successful}\n"
        f"❌ Не доставлено: {failed}\n"
        f"📊 Волшебство доставлено: {(successful/total_users*100) if total_users > 0 else 0:.1f}%",
        reply_markup=get_admin_keyboard()
    )
    
    await progress_msg.delete()

# ============= ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ =============

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "<b>🎄 ПОМОЩЬ ВОЛШЕБНОЙ МАСТЕРСКОЙ ДЕДА МОРОЗА</b>\n\n"
        "🎅 <b>Я - Дед Мороз</b>, и я дарю новогодние подарки в Telegram!\n\n"
        "✨ <b>Как получить волшебный подарок:</b>\n"
        "1. Нажмите кнопку '🎁 ЗАГАДАТЬ ЖЕЛАНИЕ ДЕДУ МОРОЗУ'\n"
        "2. Напишите, какой подарок хотите (стоимостью до 150 звёзд)\n"
        "3. Выполните волшебное задание в TikTok\n"
        "4. Отправьте скриншоты @ScreenWakeBot\n"
        "5. Получите подарок под ёлкой!\n\n"
        "🎁 <b>Примеры подарков (до 150 звёзд):</b>\n"
        "• Новогодний стикерпак (50 звёзд)\n"
        "• Зимняя анимация (75 звёзд)\n"
        "• Праздничный премиум (100 звёзд)\n"
        "• Волшебный бот (120 звёзд)\n"
        "• Новогодние смайлики (150 звёзд)\n\n"
        "📢 <b>Обязательно:</b> Подпишитесь на наш канал чудес!\n"
        f"👉 {CHANNEL_USERNAME}\n\n"
        "🎄 <b>С НОВЫМ ГОДОМ И ВОЛШЕБНЫХ ЧУДЕС!</b>\n\n"
        "📞 <b>Волшебная поддержка:</b> @wakeguarantee"
    )
    await message.answer(help_text)

@dp.message(Command("wishlist"))
async def cmd_wishlist(message: types.Message):
    wishlist_text = (
        "<b>🎁 КАТАЛОГ НОВОГОДНИХ ПОДАРКОВ ДЕДА МОРОЗА</b>\n\n"
        "✨ <b>Все подарки до 150 звёзд:</b>\n\n"
        "⭐ <b>50 ЗВЁЗД:</b>\n"
        "• Новогодний стикерпак (20 стикеров)\n"
        "• Зимняя тема оформления\n"
        "• Новогодний никнейм\n\n"
        "⭐⭐ <b>75 ЗВЁЗД:</b>\n"
        "• Анимированные стикеры\n"
        "• Эксклюзивные гифки\n"
        "• Новогодние обои\n\n"
        "⭐⭐⭐ <b>100 ЗВЁЗД:</b>\n"
        "• Премиум доступ на 1 месяц\n"
        "• Новогодний бот-помощник\n"
        "• Набор праздничных смайлов\n\n"
        "⭐⭐⭐⭐ <b>120 ЗВЁЗД:</b>\n"
        "• Персональный Telegram-бот\n"
        "• Кастомные команды\n"
        "• Автоматизация чата\n\n"
        "⭐⭐⭐⭐⭐ <b>150 ЗВЁЗД:</b>\n"
        "• Полный набор новогодних смайликов\n"
        "• Премиум на 3 месяца\n"
        "• Эксклюзивный стикерпак от Деда Мороза\n\n"
        "🎅 <i>Укажите стоимость в звёздах при загадывании желания!</i>"
    )
    await message.answer(wishlist_text)

# ============= ЗАПУСК БОТА =============

async def main():
    print("🎅 Дед Мороз запускает свою мастерскую...")
    print(f"✨ Админ (Дед Мороз): {ADMIN_ID}")
    print(f"📢 Канал чудес: {CHANNEL_USERNAME}")
    print("✅ Бот переодет в Деда Мороза")
    print("✅ Новогодняя тематика активирована")
    print("✅ Подарки ограничены 150 звёздами")
    print("✅ Добавлена волшебная рассылка")
    print("✅ Обновлена статистика")
    print("✅ Исправлена строка про TikTok")
    
    # Удаляем вебхук и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
