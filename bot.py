import inspect
import traceback
import asyncio
import sys
import os
import time
import signal
from datetime import datetime, timedelta
import logging
from functools import wraps
import json
import warnings
import re
import html
import sqlite3
import random
import string
from typing import Tuple, List, Dict, Optional, Any, Union
from contextlib import contextmanager
import threading
from pathlib import Path
import shutil

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ===== ШАГ 2: КОНФИГУРАЦИЯ ХРАНЕНИЯ ДАННЫХ =====
# Базовая директория для данных (можно переопределить через переменную окружения)
DEFAULT_DATA_DIR = '/app/data'
DATA_DIR = os.getenv('DATA_DIR', DEFAULT_DATA_DIR)

# Создаем директорию, если её нет
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"📁 Директория данных: {DATA_DIR}")
    print(f"📁 Права доступа: {oct(os.stat(DATA_DIR).st_mode)[-3:]}")
except Exception as e:
    print(f"⚠️ Не удалось создать {DATA_DIR}, используем текущую директорию: {e}")
    DATA_DIR = '.'

# Имена файлов баз данных
MAIN_DB_FILENAME = 'micasabot_main.db'
PERSISTENT_DB_FILENAME = 'micasabot_persistent.db'

# Полные пути к базам данных
MAIN_DB_PATH = os.path.join(DATA_DIR, MAIN_DB_FILENAME)
PERSISTENT_DB_PATH = os.path.join(DATA_DIR, PERSISTENT_DB_FILENAME)

print(f"📊 Основная БД будет: {MAIN_DB_PATH}")
print(f"📊 Persistent БД будет: {PERSISTENT_DB_PATH}")
print("=" * 60)
# ===== КОНЕЦ ШАГА 2 =====

# ===== НОВЫЙ ДЕКОРАТОР ДЛЯ ПОВТОРНЫХ ПОПЫТОК ПРИ БЛОКИРОВКЕ БД =====
import time
from functools import wraps

# ===== КОНСТАНТЫ ДЛЯ ФИНАНСОВОГО МЕНЮ =====
CALLBACK_REVENUE = "revenue"
CALLBACK_PERIOD_TODAY = f"{CALLBACK_REVENUE}_today"
CALLBACK_PERIOD_YESTERDAY = f"{CALLBACK_REVENUE}_yesterday"
CALLBACK_PERIOD_WEEK = f"{CALLBACK_REVENUE}_week"
CALLBACK_PERIOD_LAST_WEEK = f"{CALLBACK_REVENUE}_last_week"
CALLBACK_PERIOD_MONTH = f"{CALLBACK_REVENUE}_month"
CALLBACK_PERIOD_LAST_MONTH = f"{CALLBACK_REVENUE}_last_month"
CALLBACK_PERIOD_ALL = f"{CALLBACK_REVENUE}_all"
CALLBACK_PERIOD_CUSTOM = f"{CALLBACK_REVENUE}_custom"
CALLBACK_BACK_TO_PERIODS = f"{CALLBACK_REVENUE}_back_to_periods"

# ===== ФУНКЦИЯ ДЛЯ КОНВЕРТАЦИИ В МОСКОВСКОЕ ВРЕМЯ =====
def to_moscow_time(dt=None):
    """Конвертирует время в московское (UTC+3) для отображения"""
    if dt is None:
        dt = datetime.now()
    
    # Если время уже с часовым поясом, конвертируем
    if dt.tzinfo is not None:
        moscow_tz = pytz.timezone('Europe/Moscow')
        return dt.astimezone(moscow_tz).replace(tzinfo=None)
    
    # Если время без пояса, считаем что это UTC и добавляем 3 часа
    return dt + timedelta(hours=3)
# ===== КОНЕЦ ФУНКЦИИ =====

# ===== ФУНКЦИЯ ДЛЯ ОЧИСТКИ УСЛУГИ ОТ СМАЙЛИКОВ =====
def clean_service_text(service: str) -> str:
    """Удаляет смайлики из названия услуги"""
    if not service:
        return service
    # Список эмодзи для удаления
    emojis_to_remove = ['🎸', '🎤', '⏰', '🎚️', '🎵', '🎹', '📝', '👑', '🎛️', '☀️', '🌙', '💿', '💰', '🎯', '⏱️']
    cleaned = service
    for emoji in emojis_to_remove:
        cleaned = cleaned.replace(emoji, '').strip()
    return cleaned

def clean_date_text(date_str: str) -> str:
    """Удаляет цветные эмодзи из даты"""
    if not date_str:
        return date_str
    cleaned = date_str
    for emoji in ['🟢', '🟡', '🟠', '🔴', '⚪️']:
        cleaned = cleaned.replace(emoji, '').strip()
    if '(' in cleaned:
        cleaned = cleaned.split('(')[0].strip()
    return cleaned

# ===== ФУНКЦИИ ДЛЯ ПРАВИЛЬНОГО СКЛОНЕНИЯ =====
def get_hours_word(hours):
    """Возвращает правильное склонение слова 'час'"""
    hours = int(hours)
    if hours % 10 == 1 and hours % 100 != 11:
        return "час"
    elif 2 <= hours % 10 <= 4 and (hours % 100 < 10 or hours % 100 >= 20):
        return "часа"
    else:
        return "часов"

def get_minutes_word(minutes):
    """Возвращает правильное склонение слова 'минута'"""
    minutes = int(minutes)
    if minutes % 10 == 1 and minutes % 100 != 11:
        return "минута"
    elif 2 <= minutes % 10 <= 4 and (minutes % 100 < 10 or minutes % 100 >= 20):
        return "минуты"
    else:
        return "минут"

def get_days_word(days):
    """Возвращает правильное склонение слова 'день'"""
    days = int(days)
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
        return "дня"
    else:
        return "дней"

def get_months_word(months):
    """Возвращает правильное склонение слова 'месяц'"""
    months = int(months)
    if months % 10 == 1 and months % 100 != 11:
        return "месяц"
    elif 2 <= months % 10 <= 4 and (months % 100 < 10 or months % 100 >= 20):
        return "месяца"
    else:
        return "месяцев"

def format_duration(days=0, hours=0, minutes=0):
    """Форматирует длительность с правильными склонениями"""
    parts = []
    
    if days > 0:
        parts.append(f"{days} {get_days_word(days)}")
    if hours > 0:
        parts.append(f"{hours} {get_hours_word(hours)}")
    if minutes > 0:
        parts.append(f"{minutes} {get_minutes_word(minutes)}")
    
    if not parts:
        return "0 минут"
    
    return " ".join(parts)
# ===== КОНЕЦ ФУНКЦИЙ СКЛОНЕНИЯ =====

async def check_expired_blocks(context):
    """Проверяет истекшие блокировки и отправляет уведомления о разблокировке"""
    try:
        logger.info("🔍 Проверка истекших блокировок...")
        
        now_moscow = to_moscow_time()
        now_str = now_moscow.strftime('%Y-%m-%d %H:%M:%S')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT telegram_id, username, first_name, unique_id, blocked_until 
                FROM users 
                WHERE is_blocked = 1 
                AND blocked_until IS NOT NULL 
                AND blocked_until <= ?
            ''', (now_str,))
            
            expired_users = cursor.fetchall()
            
            if not expired_users:
                logger.info("✅ Нет пользователей с истекшей блокировкой")
                return
            
            logger.info(f"🔍 Найдено пользователей с истекшей блокировкой: {len(expired_users)}")
            
            for user in expired_users:
                telegram_id, username, first_name, unique_id, blocked_until = user
                
                try:
                    cursor.execute('''
                        UPDATE users 
                        SET is_blocked = 0, blocked_until = NULL 
                        WHERE telegram_id = ?
                    ''', (telegram_id,))
                    
                    logger.info(f"✅ Пользователь {telegram_id} автоматически разблокирован")
                    
                    display_name = first_name or username or "Пользователь"
                    
                    try:
                        await context.bot.send_message(
                            chat_id=int(telegram_id),
                            text=(
                                f"*🔓 Вы были автоматически разблокированы*\n\n"
                                f"*🎤 Теперь вы снова можете пользоваться ботом.*\n\n"
                            ),
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Уведомление о разблокировке отправлено пользователю {telegram_id}")
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить уведомление пользователю {telegram_id}: {e}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка при разблокировке пользователя {telegram_id}: {e}")
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"❌ Ошибка в check_expired_blocks: {e}")
        import traceback
        traceback.print_exc()

def retry_on_lock(max_retries=15, delay=0.5, backoff=1.5):
    """
    Декоратор для повторных попыток при блокировке базы данных.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    if "locked" in error_msg or "busy" in error_msg:
                        last_error = e
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"⚠️ БД заблокирована, попытка {attempt + 1}/{max_retries}, ждем {wait_time:.1f}с...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise
                except Exception as e:
                    error_msg = str(e).lower()
                    if "locked" in error_msg or "busy" in error_msg:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"⚠️ БД заблокирована, попытка {attempt + 1}/{max_retries}, ждем {wait_time:.1f}с...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise
            
            logger.error(f"❌ Не удалось выполнить {func.__name__} после {max_retries} попыток: {last_error}")
            return None
        return wrapper
    return decorator

class PersistentDatabase:       
    def __init__(self):
        self.db_path = self._find_working_path()
        print(f"🎯 БАЗА ДАННЫХ БУДЕТ СОХРАНЕНА В: {self.db_path}")
        self._init_tables()
    
    def _find_working_path(self):
        possible_paths = [
            '/app/data/micasabot.db',
            '/data/micasabot.db',
            'micasa_persistent.db',
            'micasabot_persistent.db',
            ':memory:'
        ]
        
        for path in possible_paths:
            if path == ':memory:':
                continue
            
            try:
                folder = os.path.dirname(path)
                if folder and folder != '.':
                    os.makedirs(folder, exist_ok=True)
                    print(f"📁 Создана папка: {folder}")
                
                test_file = path + '.test_write'
                with open(test_file, 'w') as f:
                    f.write(f'test_{datetime.now().isoformat()}')
                
                with open(test_file, 'r') as f:
                    content = f.read()
                
                os.remove(test_file)
                
                test_conn = sqlite3.connect(path)
                test_conn.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER)')
                test_conn.execute('INSERT INTO test VALUES (1)')
                test_conn.commit()
                test_conn.close()
                
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    print(f"✅ Рабочий путь найден: {path} (размер: {size} байт)")
                    return path
                    
            except Exception as e:
                print(f"❌ Путь {path} не работает: {e}")
                continue
        
        print("⚠️ Все пути не работают, используем базу в памяти")
        return ':memory:'
    
    def _init_tables(self):
        if self.db_path == ':memory:':
            print("🚨 ВНИМАНИЕ: БАЗА В ПАМЯТИ! Данные удалятся при перезапуске!")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS persistent_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                telegram_id TEXT NOT NULL,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                service TEXT NOT NULL,
                date_str TEXT,
                time_slot TEXT,
                price TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_persistent_telegram ON persistent_bookings (telegram_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_persistent_status ON persistent_bookings (status)')
        
        conn.commit()
        conn.close()
        print(f"✅ Таблицы созданы в {self.db_path}")
    
    def save_booking(self, booking_data):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO persistent_bookings 
                (timestamp, telegram_id, name, contact, service, date_str, time_slot, price, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                str(booking_data.get('telegram_id', '')),
                str(booking_data.get('name', '')),
                str(booking_data.get('contact', '')),
                str(booking_data.get('service', '')),
                str(booking_data.get('date_str', '')),
                str(booking_data.get('time_slot', '')),
                str(booking_data.get('price', '0')),
                str(booking_data.get('status', 'pending'))
            ))
            
            booking_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            print(f"✅ Запись #{booking_id} сохранена в СОХРАНЯЕМУЮ базу: {self.db_path}")
            return booking_id
        except Exception as e:
            print(f"❌ Ошибка сохранения в persistent базу: {e}")
            return None
    
    def enable_wal_mode(self):
        """Включает WAL режим для персистентной базы данных"""
        if self.db_path == ':memory:':
            return
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-20000')
            result = conn.execute('PRAGMA journal_mode').fetchone()
            conn.close()
            logger.info(f"✅ WAL режим для persistent БД включен: {result[0]}")
        except Exception as e:
            logger.error(f"❌ Ошибка включения WAL режима для persistent БД: {e}")

    def get_user_bookings(self, user_id):
        if self.db_path == ':memory:':
            return []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, timestamp, name, contact, service, date_str, time_slot, price, status
                FROM persistent_bookings 
                WHERE telegram_id = ? 
                AND status != 'cancelled'
                ORDER BY timestamp DESC
                LIMIT 50
            ''', (str(user_id),))
            
            rows = cursor.fetchall()
            conn.close()
            
            result = []
            for row in rows:
                result.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'name': row[2],
                    'contact': row[3],
                    'service': row[4],
                    'date_str': row[5],
                    'time_slot': row[6],
                    'price': row[7],
                    'status': row[8]
                })
            
            return result
        except Exception as e:
            print(f"❌ Ошибка чтения из persistent базы: {e}")
            return []
    
    def get_database_info(self):
        info = {
            'path': self.db_path,
            'in_memory': self.db_path == ':memory:',
            'exists': os.path.exists(self.db_path) if self.db_path != ':memory:' else False,
            'size': 0
        }
        
        if info['exists']:
            info['size'] = os.path.getsize(self.db_path)
            
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM persistent_bookings')
                info['total_records'] = cursor.fetchone()[0]
                conn.close()
            except:
                info['total_records'] = 0
        
        return info

# СОЗДАНИЕ ЭКЗЕМПЛЯРОВ БАЗ ДАННЫХ (ОБНОВЛЕНО)
persistent_db = PersistentDatabase()

# ===== КОНСТАНТЫ СОСТОЯНИЙ ДЛЯ CONVERSATION HANDLER =====
(
    NAME, CONTACT, CONTACT_INPUT, SERVICE, ENGINEER_OPTION,
    TWELVE_HOURS_OPTION, MIXING_TYPE, TRACK_CREATION_TYPE, 
    DATE, TIME, CONFIRM, SHOW_SLOTS, ADMIN_USER_ID,
    ADMIN_RECORD_TYPE, ADMIN_PRICE, ADMIN_CONFIRM,
    ADMIN_CANCEL_USER_ID, ADMIN_CANCEL_SHOW_BOOKINGS,
    ADMIN_BLOCK_USER_ID, ADMIN_BLOCK_TYPE, ADMIN_BLOCK_DURATION, ADMIN_BLOCK_CONFIRM,
    ADMIN_ACHIEVEMENT_USER_ID, ADMIN_ACHIEVEMENT_NAME, ADMIN_ACHIEVEMENT_CONFIRM,
    ADMIN_REMOVE_ACHIEVEMENT_USER_ID, ADMIN_REMOVE_ACHIEVEMENT_SHOW,
    PROMO_ENTER, STUDENT_VERIFY, REFERRAL_SHOW,
    ADMIN_VINYL_USER_ID, ADMIN_VINYL_ACTION, ADMIN_VINYL_AMOUNT, ADMIN_VINYL_CONFIRM,
    ADMIN_PROFILE_USER_ID,
    FINANCE_PERIOD_START, FINANCE_PERIOD_END,
    ADMIN_PROMO_START,
    ADMIN_PROMO_TYPE,
    ADMIN_PROMO_SERVICE,
    ADMIN_PROMO_VALUE,
    ADMIN_PROMO_DURATION,
    ADMIN_PROMO_DURATION_INPUT,
    ADMIN_PROMO_USER_ID,
    ADMIN_PROMO_CONFIRM,
    ADMIN_PROMO_DELETE_START,      # ← ДОЛЖНО БЫТЬ
    ADMIN_PROMO_DELETE_TYPE,       # ← ДОЛЖНО БЫТЬ
    ADMIN_PROMO_DELETE_USER_ID,    # ← ДОЛЖНО БЫТЬ
    ADMIN_PROMO_DELETE_CONFIRM
) = range(49)  

BOOKING_STATUS = {
    'PENDING': 'pending',
    'CONFIRMED': 'confirmed',
    'REJECTED': 'rejected',
    'CANCELLED_BY_USER': 'cancelled_by_user',
    'CANCELLED': 'cancelled',
    'COMPLETED': 'completed'
}

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler(
    os.path.join(log_dir, 'bot.log'),
    encoding='utf-8',
    mode='a'
)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.WARNING)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

logger.info("=" * 60)
logger.info("🚀 Mi Casa Records Bot STARTING... (SQLite Version)")
logger.info("=" * 60)

db_info = persistent_db.get_database_info()
logger.info(f"📊 Persistent Database: {db_info['path']}")
if db_info['in_memory']:
    logger.warning("⚠️ БАЗА В ПАМЯТИ - данные не сохранятся!")
elif db_info['exists']:
    logger.info(f"📁 Размер базы: {db_info['size']} байт, записей: {db_info.get('total_records', 0)}")

from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ Токен бота не найден в .env файле!")

ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

try:
    from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ConversationHandler,
        ContextTypes,
        CallbackQueryHandler,
        filters,
        JobQueue
    )
    from telegram.constants import ParseMode
    from telegram.helpers import escape_markdown
    import telegram
except ImportError as e:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot==20.7"])
    
    from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ConversationHandler,
        ContextTypes,
        CallbackQueryHandler,
        filters,
        JobQueue
    )
    from telegram.constants import ParseMode
    from telegram.helpers import escape_markdown
    import telegram
    logger.info("✅ Библиотека python-telegram-bot установлена")

import pytz

def format_number(num: int) -> str:
    if num == 0:
        return "0"
    return f"{num:,}".replace(',', ' ')

class AchievementSystem:
    ACHIEVEMENTS = {
        # ===== ЗАПИСИ В СТУДИИ =====
        'first_booking': {'name': '🥉 Добро пожаловать', 'desc': 'Отправил первую заявку на запись', 'vinyls': 10, 'hidden': False, 'category': 'bookings', 'emoji': '🥉'},
        'novice': {'name': '🥈 Новичок', 'desc': '3 завершенные записи', 'vinyls': 20, 'hidden': False, 'category': 'bookings', 'emoji': '🥈'},
        'amateur': {'name': '🥇 Любитель', 'desc': '10 завершенных записей', 'vinyls': 30, 'hidden': False, 'category': 'bookings', 'emoji': '🥇'},
        'pro': {'name': '🏅 Профи', 'desc': '25 завершенных записей', 'vinyls': 40, 'hidden': False, 'category': 'bookings', 'emoji': '🏅'},
        'veteran': {'name': '🎖 Ветеран', 'desc': '50 завершенных записей', 'vinyls': 50, 'hidden': False, 'category': 'bookings', 'emoji': '🎖'},
        'studio_legend': {'name': '👑 Легенда студии', 'desc': '100 завершенных записей', 'vinyls': 60, 'hidden': False, 'category': 'bookings', 'emoji': '👑'},
        
        # ===== РЕФЕРАЛЫ =====
        'friend_inviter': {'name': '🤝 Позвал друга', 'desc': '1 друг сделал запись', 'vinyls': 30, 'hidden': False, 'category': 'referrals', 'emoji': '🤝'},
        'social': {'name': '🗣 Социальный', 'desc': '3 друга сделали запись', 'vinyls': 50, 'hidden': False, 'category': 'referrals', 'emoji': '🗣'},
        'star': {'name': '⭐️ Звезда', 'desc': '5 друзей сделали запись', 'vinyls': 70, 'hidden': False, 'category': 'referrals', 'emoji': '⭐️'},
        'magnate': {'name': '💰 Магнат', 'desc': '10 друзей сделали запись', 'vinyls': 100, 'hidden': False, 'category': 'referrals', 'emoji': '💰'},
        'network_giant': {'name': '🌐 Сетевой гигант', 'desc': '20 друзей сделали запись', 'vinyls': 150, 'hidden': False, 'category': 'referrals', 'emoji': '🌐'},
        
        # ===== ОСОБЫЕ НАГРАДЫ (ТОЛЬКО АДМИН) =====
        'name_on_wall': {'name': '📜 Имя на стене', 'desc': 'Самый преданный клиент года', 'vinyls': 100, 'hidden': False, 'category': 'special', 'emoji': '📜'},
        'godspeed_legend': {'name': '🎖 Godspeed Legend', 'desc': 'За вклад в развитие студии', 'vinyls': 200, 'hidden': False, 'category': 'special', 'emoji': '🎖'},
        'golden_mic': {'name': '🎤 Золотой микрофон', 'desc': 'Популярный артист', 'vinyls': 150, 'hidden': False, 'category': 'special', 'emoji': '🎤'},
    }
    
    LEVELS = [
        {'level': 1, 'name': 'Любитель', 'vinyls_needed': 0, 'discount': 50, 'discount_type': 'once', 'uses': 1},
        {'level': 2, 'name': 'Мастер', 'vinyls_needed': 450, 'discount': 5, 'discount_type': 'permanent', 'uses': None},
        {'level': 3, 'name': 'Легенда', 'vinyls_needed': 1000, 'discount': 10, 'discount_type': 'permanent', 'uses': None},
        {'level': 4, 'name': 'Бог музыки', 'vinyls_needed': 2000, 'discount': 20, 'discount_type': 'permanent', 'uses': None},
    ]
    
    CATEGORIES = {
        'bookings': {'emoji': '🎤', 'name': 'Записи в студии'},
        'referrals': {'emoji': '👥', 'name': 'Рефералы'},
        'special': {'emoji': '🏆', 'name': 'Особые награды'}
    }
    
    @staticmethod
    def get_user_coupons_summary(user_id: str) -> dict:
        """Возвращает сводку купонов пользователя"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Получаем текущий уровень пользователя
                cursor.execute('SELECT level FROM users WHERE telegram_id = ?', (user_id,))
                result = cursor.fetchone()
                current_level = result[0] if result else 1
                
                if current_level is None or current_level == 0:
                    current_level = 1
                    cursor.execute('UPDATE users SET level = 1 WHERE telegram_id = ?', (user_id,))
                    conn.commit()
                
                # Получаем купоны пользователя
                cursor.execute('''
                    SELECT level, discount_percent, remaining_uses, is_permanent
                    FROM user_coupons 
                    WHERE user_id = ?
                    AND level <= ?
                    AND (remaining_uses > 0 OR is_permanent = 1)
                    ORDER BY level ASC, discount_percent DESC
                ''', (user_id, current_level))
                
                rows = cursor.fetchall()
                
                coupons_by_level = {}
                total_discount = 0
                permanent_discount = 0
                
                for row in rows:
                    level, discount, remaining, is_permanent = row
                    
                    if level not in coupons_by_level:
                        coupons_by_level[level] = []
                    
                    is_perm = is_permanent == 1
                    
                    if is_perm:
                        permanent_discount += discount
                        total_discount += discount
                        coupons_by_level[level].append({
                            'discount': discount,
                            'remaining': None,
                            'is_permanent': True,
                            'total_value': discount
                        })
                    else:
                        value = discount * remaining
                        total_discount += value
                        coupons_by_level[level].append({
                            'discount': discount,
                            'remaining': remaining,
                            'is_permanent': False,
                            'total_value': value
                        })
                
                level_names = {}
                for lvl in AchievementSystem.LEVELS:
                    level_names[lvl['level']] = lvl['name']
                
                return {
                    'coupons_by_level': coupons_by_level,
                    'total_discount': min(total_discount, 100),
                    'raw_total': total_discount,
                    'permanent_discount': permanent_discount,
                    'level_names': level_names
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения сводки купонов: {e}")
            return {
                'coupons_by_level': {},
                'total_discount': 0,
                'raw_total': 0,
                'permanent_discount': 0,
                'level_names': {}
            }


    @staticmethod
    async def check_and_award_achievements(user_id: str, context=None, update=None):
        """Проверяет и выдает достижения"""
        try:
            logger.info(f"🏆 Проверка достижений для {user_id}")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Получаем текущие достижения пользователя
                cursor.execute('SELECT achievement_id FROM user_achievements WHERE user_id = ?', (user_id,))
                user_achievements = {row[0] for row in cursor.fetchall()}
                
                # ===== 1. ВСЕ ЗАПИСИ (для first_booking) =====
                cursor.execute('''
                    SELECT COUNT(*) FROM bookings 
                    WHERE telegram_id = ?
                ''', (user_id,))
                total_row = cursor.fetchone()
                total_bookings = total_row[0] if total_row and total_row[0] else 0
                logger.info(f"📊 Всего записей (включая pending): {total_bookings}")
                
                # ===== 2. ЗАВЕРШЁННЫЕ ЗАПИСИ =====
                cursor.execute('''
                    SELECT COUNT(*) FROM bookings 
                    WHERE telegram_id = ? 
                    AND (
                        (status = 'completed' AND is_admin_booking = 0 AND is_contractual = 0)
                        OR
                        (is_admin_booking = 1 AND status IN ('confirmed', 'подтвержден'))
                        OR
                        (is_contractual = 1 AND status IN ('confirmed', 'подтвержден'))
                        OR
                        (is_mixing = 1 AND status IN ('confirmed', 'подтвержден'))
                        OR
                        (is_track_creation = 1 AND track_type = 'Альбом' AND status IN ('confirmed', 'подтвержден'))
                    )
                ''', (user_id,))
                completed_row = cursor.fetchone()
                completed_bookings = completed_row[0] if completed_row and completed_row[0] else 0
                logger.info(f"📊 Завершённых записей: {completed_bookings}")
                
                awarded = []
                total_vinyls = 0
                
                # ===== ДОСТИЖЕНИЯ ЗА ЗАПИСИ =====
                achievements_list = [
                    ('first_booking', 1, 10, '🥉 Добро пожаловать'),
                    ('novice', 3, 20, '🥈 Новичок'),
                    ('amateur', 10, 30, '🥇 Любитель'),
                    ('pro', 25, 40, '🏅 Профи'),
                    ('veteran', 50, 50, '🎖 Ветеран'),
                    ('studio_legend', 100, 60, '👑 Легенда студии'),
                ]
                
                for ach_id, need, vinyls, name in achievements_list:
                    if ach_id not in user_achievements:
                        if ach_id == 'first_booking':
                            # ===== ВАЖНО: first_booking от ВСЕХ записей =====
                            if total_bookings >= need:
                                logger.info(f"🎯 Выдаём {ach_id} (всего записей: {total_bookings})")
                                cursor.execute('''
                                    INSERT INTO user_achievements 
                                    (user_id, achievement_id, achievement_name, achievement_type) 
                                    VALUES (?, ?, ?, 'auto')
                                ''', (user_id, ach_id, name))
                                cursor.execute('UPDATE users SET vinyls = vinyls + ? WHERE telegram_id = ?', (vinyls, user_id))
                                awarded.append(ach_id)
                                total_vinyls += vinyls
                        else:
                            # ===== Остальные достижения от ЗАВЕРШЁННЫХ записей =====
                            if completed_bookings >= need:
                                logger.info(f"🎯 Выдаём {ach_id} (завершённых: {completed_bookings})")
                                cursor.execute('''
                                    INSERT INTO user_achievements 
                                    (user_id, achievement_id, achievement_name, achievement_type) 
                                    VALUES (?, ?, ?, 'auto')
                                ''', (user_id, ach_id, name))
                                cursor.execute('UPDATE users SET vinyls = vinyls + ? WHERE telegram_id = ?', (vinyls, user_id))
                                awarded.append(ach_id)
                                total_vinyls += vinyls
                
                # ===== РЕФЕРАЛЬНЫЕ ДОСТИЖЕНИЯ =====
                cursor.execute('SELECT referral_code FROM users WHERE telegram_id = ?', (user_id,))
                user_data = cursor.fetchone()
                
                if user_data and user_data[0]:
                    referral_code = user_data[0]
                    
                    cursor.execute('''
                        SELECT COUNT(DISTINCT u.telegram_id)
                        FROM users u
                        JOIN bookings b ON u.telegram_id = b.telegram_id
                        WHERE u.referred_by = ? 
                        AND (
                            b.service LIKE '%Админ%' OR b.service LIKE '%админ%' OR
                            (b.is_contractual = 1 AND b.status IN ('confirmed', 'подтвержден')) OR
                            (b.date_str NOT LIKE '%Не указана%' AND 
                            b.date_str NOT LIKE '%договорная%' AND 
                            b.status = 'completed')
                        )
                    ''', (referral_code,))
                    
                    active_referrals = cursor.fetchone()[0] or 0
                    logger.info(f"👥 Активных рефералов у {user_id}: {active_referrals}")
                    
                    referral_achievements_list = [
                        ('friend_inviter', '🤝 Позвал друга', 1, 30),
                        ('social', '🗣 Социальный', 3, 50),
                        ('star', '⭐️ Звезда', 5, 70),
                        ('magnate', '💰 Магнат', 10, 100),
                        ('network_giant', '🌐 Сетевой гигант', 20, 150),
                    ]
                    
                    for ach_id, name, need, vinyls in referral_achievements_list:
                        if active_referrals >= need and ach_id not in user_achievements:
                            logger.info(f"🎯 Выдаём реферальное достижение {ach_id} (нужно {need}, есть {active_referrals})")
                            cursor.execute('''
                                INSERT INTO user_achievements 
                                (user_id, achievement_id, achievement_name, achievement_type) 
                                VALUES (?, ?, ?, 'auto')
                            ''', (user_id, ach_id, name))
                            cursor.execute('UPDATE users SET vinyls = vinyls + ? WHERE telegram_id = ?', (vinyls, user_id))
                            awarded.append(ach_id)
                            total_vinyls += vinyls
                
                vinyl_row = cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (user_id,)).fetchone()
                new_vinyls = vinyl_row[0] if vinyl_row and vinyl_row[0] else 0
                
                conn.commit()
                
                # ===== ОТПРАВЛЯЕМ УВЕДОМЛЕНИЯ =====
                if awarded and context:
                    # Уведомления для достижений из achievements_list
                    for ach_id in awarded:
                        for ach_id2, need, vinyls, name in achievements_list:
                            if ach_id2 == ach_id:
                                try:
                                    message = (
                                        f"*🎉 Добавлено {vinyls} пластинок за достижение «{name}»!*\n\n"
                                        f"*✨ Гордимся, что Вы с нами!*\n\n"
                                        f"*💰 Пластинок после достижения: {new_vinyls} 💿*"
                                    )
                                    
                                    await context.bot.send_message(
                                        chat_id=int(user_id),
                                        text=message,
                                        parse_mode="Markdown"
                                    )
                                    logger.info(f"✅ Уведомление о достижении отправлено пользователю {user_id}")
                                except Exception as e:
                                    logger.error(f"❌ Ошибка отправки уведомления: {e}")
                                break
                        
                        # Уведомления для реферальных достижений
                        for ach_id2, name, need, vinyls in referral_achievements_list:
                            if ach_id2 == ach_id:
                                try:
                                    message = (
                                        f"*🎉 Добавлено {vinyls} пластинок за достижение «{name}»!*\n\n"
                                        f"*✨ Гордимся, что Вы с нами!*\n\n"
                                        f"*💰 Пластинок после достижения: {new_vinyls} 💿*"
                                    )
                                    
                                    await context.bot.send_message(
                                        chat_id=int(user_id),
                                        text=message,
                                        parse_mode="Markdown"
                                    )
                                    logger.info(f"✅ Уведомление о реферальном достижении отправлено пользователю {user_id}")
                                except Exception as e:
                                    logger.error(f"❌ Ошибка отправки уведомления: {e}")
                                break
                
                return awarded, total_vinyls
                
        except Exception as e:
            logger.error(f"❌ Ошибка в check_and_award_achievements: {e}")
            import traceback
            traceback.print_exc()
            return [], 0
    
    @staticmethod
    async def award_manual_achievement(user_id: str, achievement_id: str, admin_id: str, context=None):
        """Выдаёт достижение вручную с уведомлением о повышении уровня"""
        try:
            if achievement_id not in AchievementSystem.ACHIEVEMENTS:
                return False, "❌ Достижение не найдено"
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id FROM user_achievements 
                    WHERE user_id = ? AND achievement_id = ?
                ''', (user_id, achievement_id))
                
                if cursor.fetchone():
                    return False, "❌ Достижение уже есть у пользователя"
                
                ach = AchievementSystem.ACHIEVEMENTS[achievement_id]
                
                cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (user_id,))
                result = cursor.fetchone()
                old_vinyls = result[0] if result else 0
                
                cursor.execute('''
                    INSERT INTO user_achievements 
                    (user_id, achievement_id, achievement_name, achievement_type, awarded_by)
                    VALUES (?, ?, ?, 'manual', ?)
                ''', (user_id, achievement_id, ach['name'], admin_id))
                
                cursor.execute('''
                    UPDATE users SET vinyls = vinyls + ? WHERE telegram_id = ?
                ''', (ach['vinyls'], user_id))
                
                conn.commit()
                
                cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (user_id,))
                result = cursor.fetchone()
                new_vinyls = result[0] if result else 0
                
                old_level_info = AchievementSystem.get_level_info(old_vinyls)
                new_level_info = AchievementSystem.get_level_info(new_vinyls)
                
                await AchievementSystem.update_user_level(user_id, None, send_notification=False)
                
                if context and new_level_info['current_level'] > old_level_info['current_level']:
                    try:
                        message = (
                            f"*🎉 Повышение уровня!*\n\n"
                            f"*📈 Был уровень: {old_level_info['current_level_name']}*\n"
                            f"*📈 Стал уровень: {new_level_info['current_level_name']}*\n\n"
                            f"*🎁 Вы получили новые купоны на скидку!*\n"
                            f"*💰 Проверьте раздел «Мой уровень»*\n\n"
                            f"*💪 Продолжайте в том же духе! 🔥*"
                        )
                        
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=message,
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Уведомление о повышении уровня отправлено пользователю {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить уведомление о повышении уровня: {e}")
                
                if context:
                    try:
                        message = (
                            f"*🎉 Добавлено {ach['vinyls']} пластинок за достижение «{ach['name']}»!*\n\n"
                            f"*✨ Гордимся, что Вы с нами!*\n\n"
                            f"*💰 Пластинок после достижения: {new_vinyls} 💿*"
                        )
                        
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=message,
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Уведомление о выдаче достижения отправлено пользователю {user_id}")
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление пользователю: {e}")
                
                return True, f"✅ Достижение «{ach['name']}» выдано"
                
        except Exception as e:
            logger.error(f"Ошибка ручной выдачи достижения: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    @staticmethod
    async def remove_achievement(user_id: str, achievement_id: str, admin_id: str, context=None):
        """Удаляет достижение (БЕЗ отправки уведомлений о понижении уровня)"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT achievement_name, achievement_type FROM user_achievements 
                    WHERE user_id = ? AND achievement_id = ?
                ''', (user_id, achievement_id))
                
                result = cursor.fetchone()
                if not result:
                    return False, "❌ Достижение не найдено у пользователя"
                
                achievement_name, achievement_type = result
                
                ach = AchievementSystem.ACHIEVEMENTS.get(achievement_id, {})
                vinyls_to_remove = ach.get('vinyls', 0)
                
                cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (user_id,))
                user_result = cursor.fetchone()
                old_vinyls = user_result[0] if user_result else 0
                
                cursor.execute('''
                    DELETE FROM user_achievements 
                    WHERE user_id = ? AND achievement_id = ?
                ''', (user_id, achievement_id))
                
                new_vinyls = max(0, old_vinyls - vinyls_to_remove)
                cursor.execute('''
                    UPDATE users SET vinyls = ? WHERE telegram_id = ?
                ''', (new_vinyls, user_id))
                
                conn.commit()
                
                await AchievementSystem.update_user_level(user_id, None, send_notification=False)
                
                if context:
                    try:
                        emoji = ach.get('emoji', '🏆')
                        
                        message = (
                            f"*❌ Удалено {vinyls_to_remove} пластинок за достижение «{emoji} {achievement_name}»*\n\n"
                            f"*📉 Достижение отозвано администратором*\n"
                            f"*💰 Текущее количество пластинок: {new_vinyls} 💿*\n\n"
                            f"*📞 Свяжитесь с администратором @mothman32 для уточнения*"
                        )
                        
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=message,
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Уведомление об удалении достижения отправлено пользователю {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить уведомление об удалении: {e}")
                
                return True, f"❌ Достижение «{achievement_name}» удалено"
                
        except Exception as e:
            logger.error(f"Ошибка удаления достижения: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    @staticmethod
    def get_user_achievements(user_id: str) -> dict:
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT achievement_id FROM user_achievements WHERE user_id = ?
                ''', (user_id,))
                
                return {row[0]: True for row in cursor.fetchall()}
                
        except Exception as e:
            logger.error(f"Ошибка получения достижений пользователя: {e}")
            return {}
    
    @staticmethod
    def get_achievements_stats(user_id: str) -> dict:
        try:
            user_achievements = AchievementSystem.get_user_achievements(user_id)
            
            total_possible = len(AchievementSystem.ACHIEVEMENTS)
            total_earned = len(user_achievements)
            
            vinyls_from_achievements = 0
            
            for ach_id in user_achievements:
                if ach_id in AchievementSystem.ACHIEVEMENTS:
                    vinyls = AchievementSystem.ACHIEVEMENTS[ach_id]['vinyls']
                    vinyls_from_achievements += vinyls
            
            return {
                'total_possible': total_possible,
                'total_earned': total_earned,
                'vinyls_from_achievements': vinyls_from_achievements
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики достижений: {e}")
            return {'total_possible': 0, 'total_earned': 0, 'vinyls_from_achievements': 0}
    
    @staticmethod
    def format_achievements_list(user_id: str) -> str:
        """Форматирует список достижений пользователя"""
        try:
            user_achievements = AchievementSystem.get_user_achievements(user_id)
            stats = AchievementSystem.get_achievements_stats(user_id)
            
            text = "*🏆 Достижения*\n\n"
            
            # ===== ЗАПИСИ В СТУДИИ =====
            text += "*Записи в студии:*\n"
            booking_achievements = [
                ('first_booking', '🥉 Добро пожаловать', 'Отправили первую заявку'),
                ('novice', '🥈 Новичок', '3 завершенные записи'),
                ('amateur', '🥇 Любитель', '10 завершенных записей'),
                ('pro', '🏅 Профи', '25 завершенных записей'),
                ('veteran', '🎖 Ветеран', '50 завершенных записей'),
                ('studio_legend', '👑 Легенда студии', '100 завершенных записей')
            ]
            for ach_id, name_with_emoji, desc in booking_achievements:
                if ach_id in user_achievements:
                    text += f"✅ {name_with_emoji} — {desc}\n"
                else:
                    text += f"{name_with_emoji} — {desc}\n"
            text += "\n"
            
            # ===== РЕФЕРАЛЫ =====
            text += "*Рефералы:*\n"
            referrals_achievements = [
                ('friend_inviter', '🤝 Позвал друга', '1 друг приглашён'),
                ('social', '🗣 Социальный', '3 друга приглашены'),
                ('star', '⭐️ Звезда', '5 друзей приглашены'),
                ('magnate', '💰 Магнат', '10 друзей приглашены'),
                ('network_giant', '🌐 Сетевой гигант', '20 друзей приглашены')
            ]
            for ach_id, name_with_emoji, desc in referrals_achievements:
                if ach_id in user_achievements:
                    text += f"✅ {name_with_emoji} — {desc}\n"
                else:
                    text += f"{name_with_emoji} — {desc}\n"
            text += "\n"
            
            # ===== ОСОБЫЕ НАГРАДЫ =====
            text += "*Особые награды:*\n"
            special_achievements = [
                ('name_on_wall', '📜 Имя на стене', 'Самому преданному клиенту года'),
                ('godspeed_legend', '🎖 Godspeed Legend', 'За вклад в развитие студии'),
                ('golden_mic', '🎤 Золотой микрофон', 'Популярному артисту')
            ]
            for ach_id, name_with_emoji, desc in special_achievements:
                if ach_id in user_achievements:
                    text += f"✅ {name_with_emoji} — {desc}\n"
                else:
                    text += f"{name_with_emoji} — {desc}\n"
            text += "\n"
            
            # ===== СТАТИСТИКА =====
            text += "*Статистика:*\n"
            text += f"• Выполнено достижений: {stats['total_earned']}/{stats['total_possible']}\n"
            text += f"• Заработано пластинок: {stats['vinyls_from_achievements']} 💿"
            
            return text
            
        except Exception as e:
            logger.error(f"Ошибка форматирования списка достижений: {e}")
            return "❌ Ошибка загрузки достижений"
    
    @staticmethod
    def generate_referral_code(telegram_id: str) -> str:
        import random
        import string
        
        id_part = telegram_id[-4:] if len(telegram_id) >= 4 else telegram_id.zfill(4)
        letters = ''.join(random.choices(string.ascii_uppercase, k=4))
        return f"{letters}{id_part}"
    
    @staticmethod
    async def add_vinyls_for_booking(user_id: str, context=None, booking_data: dict = None):
        """Начисляет пластинки за запись с защитой от дублей"""
        try:
            logger.info(f"💰 НАЧАЛО начисления пластинок для пользователя {user_id}")
            
            if not booking_data:
                logger.error("❌ booking_data is None or empty!")
                return False, 0
            
            booking_id = booking_data.get('id')
            if not booking_id:
                logger.error("❌ Нет ID записи в booking_data!")
                return False, 0
            
            if not user_id:
                logger.error("❌ Нет user_id!")
                return False, 0

            with db.get_connection(timeout=60.0) as conn:
                cursor = conn.cursor()
                
                # Проверяем существование колонки
                cursor.execute("PRAGMA table_info(bookings)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'vinyls_awarded' not in columns:
                    try:
                        cursor.execute('ALTER TABLE bookings ADD COLUMN vinyls_awarded INTEGER DEFAULT 0')
                        conn.commit()
                        logger.info("✅ Добавлена колонка vinyls_awarded")
                    except Exception as e:
                        logger.error(f"❌ Ошибка добавления колонки: {e}")
                
                # ===== ПРОВЕРКА НА ДУБЛЬ =====
                cursor.execute('SELECT vinyls_awarded FROM bookings WHERE id = ?', (booking_id,))
                result = cursor.fetchone()
                if result and result[0] == 1:
                    logger.info(f"⚠️ Пластинки уже начислены за запись #{booking_id}")
                    return False, 0
                
                # ===== ПОЛУЧАЕМ ДАННЫЕ ИЗ БД =====
                cursor.execute('''
                    SELECT status, is_admin_booking, is_contractual, service, date_str, time_slot
                    FROM bookings WHERE id = ?
                ''', (booking_id,))
                db_row = cursor.fetchone()
                
                if not db_row:
                    logger.error(f"❌ Запись #{booking_id} не найдена в БД!")
                    return False, 0
                
                db_status, db_is_admin, db_is_contractual, db_service, db_date_str, db_time_slot = db_row
                
                status = booking_data.get('status', db_status)
                is_admin_booking = booking_data.get('is_admin_booking', db_is_admin)
                is_contractual = booking_data.get('is_contractual', db_is_contractual)
                service = booking_data.get('service', db_service)
                date_str = booking_data.get('date_str', db_date_str)
                time_slot = booking_data.get('time_slot', db_time_slot)
                
                logger.info(f"📋 Данные записи #{booking_id}: status={status}, is_admin={is_admin_booking}, is_contractual={is_contractual}")
                
                # ===== ПРОВЕРКА НА ОТМЕНЕННЫЕ =====
                if status in ['cancelled_by_user', 'cancelled', 'rejected', 'отклонен', 'отменен']:
                    logger.info(f"❌ Запись отменена/отклонена, пластинки не начисляются")
                    return False, 0
                
                # ===== УСЛОВИЯ ДЛЯ НАЧИСЛЕНИЯ =====
                should_award = False
                award_reason = ""
                
                if is_admin_booking:
                    should_award = True
                    award_reason = "админская запись"
                    logger.info(f"✅ Условие: админская запись")
                elif is_contractual and status in ['confirmed', 'подтвержден']:
                    should_award = True
                    award_reason = "подтвержденная договорная запись"
                    logger.info(f"✅ Условие: договорная подтвержденная запись")
                elif status == 'completed' and date_str and 'Не указана' not in date_str:
                    should_award = True
                    award_reason = "завершенная запись"
                    logger.info(f"✅ Условие: завершенная запись")
                
                if not should_award:
                    logger.info(f"❌ Запись не подходит для начисления пластинок. status={status}")
                    return False, 0
                
                # ===== НАЧИСЛЯЕМ ПЛАСТИНКИ =====
                cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (user_id,))
                result = cursor.fetchone()
                
                if not result:
                    cursor.execute('''
                        INSERT INTO users (telegram_id, vinyls) VALUES (?, ?)
                    ''', (user_id, 25))
                    new_vinyls = 25
                    logger.info(f"✅ Создан новый пользователь с 25 пластинками")
                else:
                    old_vinyls = result[0] or 0
                    new_vinyls = old_vinyls + 25
                    cursor.execute('UPDATE users SET vinyls = ? WHERE telegram_id = ?', (new_vinyls, user_id))
                    logger.info(f"✅ Пользователю начислено +25 пластинок (было {old_vinyls}, стало {new_vinyls})")
                
                cursor.execute('UPDATE bookings SET vinyls_awarded = 1 WHERE id = ?', (booking_id,))
                conn.commit()
                
                await AchievementSystem.check_and_award_achievements(user_id, context, None)
                await AchievementSystem.update_user_level(user_id, context)
                
                if context:
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=(
                                f"*🎉 Добавлено 25 пластинок за запись!*\n\n"
                                f"*✨ Продолжайте записываться!*\n\n"
                                f"*💰 Пластинок после записи: {new_vinyls} 💿*"
                            ),
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Уведомление о +25 пластинках отправлено пользователю {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки уведомления: {e}")
                
                logger.info(f"✅ УСПЕШНО начислено +25 пластинок для записи #{booking_id}")
                return True, new_vinyls
            
        except Exception as e:
            logger.error(f"❌ Ошибка начисления пластинок: {e}")
            import traceback
            traceback.print_exc()
            return False, 0
    
    @staticmethod
    async def update_user_level(user_id: str, context=None, send_notification: bool = True):
        """Обновляет уровень пользователя (БЕЗ отправки уведомлений)"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT vinyls, level FROM users WHERE telegram_id = ?', (user_id,))
                result = cursor.fetchone()
                
                if not result:
                    return
                
                vinyls, current_level = result[0] or 0, result[1] or 1
                
                new_level = 1
                for level_info in AchievementSystem.LEVELS:
                    if vinyls >= level_info['vinyls_needed']:
                        new_level = level_info['level']
                    else:
                        break
                
                level_order = [1, 2, 3, 4]
                
                if new_level > current_level:
                    cursor.execute('UPDATE users SET level = ? WHERE telegram_id = ?', (new_level, user_id))
                    
                    for level in level_order:
                        if current_level < level <= new_level:
                            CouponManager.add_level_coupons(user_id, level, conn)
                            logger.info(f"✅ Добавлены купоны за уровень {level} пользователю {user_id}")
                    
                    conn.commit()
                    logger.info(f"✅ Пользователь {user_id} повысил уровень с {current_level} до {new_level}")
                
                elif new_level < current_level:
                    cursor.execute('UPDATE users SET level = ? WHERE telegram_id = ?', (new_level, user_id))
                    
                    for level in level_order:
                        if level > new_level:
                            cursor.execute('''
                                DELETE FROM user_coupons 
                                WHERE user_id = ? AND level = ?
                            ''', (user_id, level))
                            logger.info(f"🗑️ Удалены купоны уровня {level} для пользователя {user_id}")
                    
                    conn.commit()
                    logger.info(f"📉 Пользователь {user_id} понизил уровень с {current_level} до {new_level}")
                            
        except Exception as e:
            logger.error(f"Ошибка обновления уровня: {e}")
    
    @staticmethod
    def get_level_info(vinyls: int) -> dict:
        current_level = 1
        next_level_info = None
        
        for i, level_info in enumerate(AchievementSystem.LEVELS):
            if vinyls >= level_info['vinyls_needed']:
                current_level = level_info['level']
            else:
                next_level_info = level_info
                break
        
        current_level_info = AchievementSystem.LEVELS[current_level-1]
        
        vinyls_needed_next = next_level_info['vinyls_needed'] if next_level_info else current_level_info['vinyls_needed']
        vinyls_progress = vinyls - current_level_info['vinyls_needed']
        vinyls_total_needed = vinyls_needed_next - current_level_info['vinyls_needed']
        progress_percent = int((vinyls_progress / vinyls_total_needed) * 100) if vinyls_total_needed > 0 else 100
        
        return {
            'current_level': current_level,
            'current_level_name': current_level_info['name'],
            'current_discount': current_level_info['discount'],
            'discount_type': current_level_info['discount_type'],
            'vinyls': vinyls,
            'vinyls_needed_next': vinyls_needed_next,
            'progress_percent': progress_percent,
            'next_level_name': next_level_info['name'] if next_level_info else None
        }

    @staticmethod
    async def notify_level_change(user_id: str, old_vinyls: int, new_vinyls: int, context=None):
        """Отправляет отдельное уведомление об изменении уровня"""
        try:
            old_level_info = AchievementSystem.get_level_info(old_vinyls)
            new_level_info = AchievementSystem.get_level_info(new_vinyls)
            
            if new_level_info['current_level'] == old_level_info['current_level']:
                logger.info(f"ℹ️ Уровень пользователя {user_id} не изменился")
                return False
            
            if not context:
                logger.warning(f"⚠️ context отсутствует, уведомление об изменении уровня не отправлено")
                return False
            
            if new_level_info['current_level'] > old_level_info['current_level']:
                message = (
                    f"*🎉 Повышение уровня!*\n\n"
                    f"*📈 Был уровень: {old_level_info['current_level_name']}*\n"
                    f"*📈 Стал уровень: {new_level_info['current_level_name']}*\n\n"
                    f"*🎁 Вы получили новые купоны на скидку!*\n"
                    f"*💰 Проверьте раздел «Мой уровень»*\n\n"
                    f"*💪 Продолжайте в том же духе! 🔥*"
                )
            else:
                message = (
                    f"*📉 Понижение уровня!*\n\n"
                    f"*📉 Был уровень: {old_level_info['current_level_name']}*\n"
                    f"*📉 Стал уровень: {new_level_info['current_level_name']}*\n\n"
                    f"*💪 Не расстраивайтесь! Запишитесь снова и верните уровень! 🔥*"
                )
            
            message += f"\n\n*📊 Пластинки: {old_vinyls} 💿 → {new_vinyls} 💿*"
            
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Уведомление об изменении уровня отправлено пользователю {user_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Не удалось отправить уведомление об изменении уровня: {e}")
                return False
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в notify_level_change: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    async def check_and_revoke_achievements_on_cancellation(user_id: str, cancelled_booking: dict, context=None):
        """Проверяет, нужно ли отозвать достижения после отмены записи админом"""
        try:
            logger.info(f"🔍 Проверка достижений после отмены записи для пользователя {user_id}")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (user_id,))
                result = cursor.fetchone()
                current_vinyls_before = result[0] if result else 0
                
                cursor.execute('''
                    SELECT achievement_id FROM user_achievements WHERE user_id = ?
                ''', (user_id,))
                
                user_achievements = [row[0] for row in cursor.fetchall()]
                
                if not user_achievements:
                    logger.info(f"ℹ️ У пользователя {user_id} нет достижений для проверки")
                    return []
                
                revoked_achievements = []
                total_vinyls_revoked = 0
                
                for achievement_id in user_achievements:
                    should_revoke = False
                    
                    # first_booking защищён
                    if achievement_id == 'first_booking':
                        logger.info(f"✅ Достижение 'Добро пожаловать' защищено от отзыва")
                        continue
                    
                    # Реферальные достижения защищены
                    if achievement_id in ['friend_inviter', 'social', 'star', 'magnate', 'network_giant']:
                        logger.info(f"✅ Реферальное достижение {achievement_id} защищено от отзыва")
                        continue
                    
                    ach_info = AchievementSystem.ACHIEVEMENTS.get(achievement_id, {})
                    
                    # Достижения за записи
                    if achievement_id in ['novice', 'amateur', 'pro', 'veteran', 'studio_legend']:
                        needed = {
                            'novice': 3,
                            'amateur': 10,
                            'pro': 25,
                            'veteran': 50,
                            'studio_legend': 100
                        }.get(achievement_id, 0)
                        
                        cursor.execute('''
                            SELECT COUNT(*) FROM bookings 
                            WHERE telegram_id = ? 
                            AND id != ?
                            AND (
                                (status = 'completed' AND is_admin_booking = 0 AND is_contractual = 0)
                                OR
                                (is_admin_booking = 1 AND status IN ('confirmed', 'подтвержден'))
                                OR
                                (is_contractual = 1 AND status IN ('confirmed', 'подтвержден'))
                                OR
                                (is_mixing = 1 AND status IN ('confirmed', 'подтвержден'))
                                OR
                                (is_track_creation = 1 AND track_type = 'Альбом' AND status IN ('confirmed', 'подтвержден'))
                            )
                        ''', (user_id, cancelled_booking.get('id', 0)))
                        
                        actual_count = cursor.fetchone()[0] or 0
                        
                        if actual_count < needed:
                            should_revoke = True
                            logger.info(f"❌ Достижение {achievement_id} нужно отозвать: нужно {needed}, осталось {actual_count}")
                    
                    if should_revoke:
                        cursor.execute('''
                            DELETE FROM user_achievements 
                            WHERE user_id = ? AND achievement_id = ?
                        ''', (user_id, achievement_id))
                        
                        vinyls_to_remove = ach_info.get('vinyls', 0)
                        total_vinyls_revoked += vinyls_to_remove
                        
                        cursor.execute('''
                            UPDATE users SET vinyls = vinyls - ? WHERE telegram_id = ?
                        ''', (vinyls_to_remove, user_id))
                        
                        revoked_achievements.append({
                            'id': achievement_id,
                            'name': ach_info.get('name', achievement_id),
                            'vinyls': vinyls_to_remove
                        })
                        
                        logger.info(f"✅ Отозвано достижение {achievement_id}, -{vinyls_to_remove} пластинок")
                
                cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (user_id,))
                new_vinyls = cursor.fetchone()[0] or 0
                
                if revoked_achievements:
                    await AchievementSystem.update_user_level(user_id, context)
                
                conn.commit()
                
                if revoked_achievements and context:
                    await AchievementSystem.notify_level_change(user_id, current_vinyls_before, new_vinyls, context)
                
                if revoked_achievements and context:
                    try:
                        message = "*❌ Достижение отозвано*\n\n"
                        message += "*После отмены записи вы больше не соответствуете условиям для следующих достижений:*\n\n"
                        
                        for ach in revoked_achievements:
                            message += f"*• {ach['name']} (-{ach['vinyls']}💿)*\n"
                        
                        message += f"*\n📉 Всего отозвано: {total_vinyls_revoked} пластинок*\n\n"
                        message += f"*💰 Текущее количество пластинок: {new_vinyls} 💿*\n\n"
                        message += "*💪 Не расстраивайтесь! Запишитесь снова и верните достижения!*"
                        
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=message,
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Уведомление об отзыве достижений отправлено пользователю {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить уведомление об отзыве: {e}")
                
                return revoked_achievements
                
        except Exception as e:
            logger.error(f"❌ Ошибка при отзыве достижений: {e}")
            import traceback
            traceback.print_exc()
            return []

class PromoCodeManager:
    """Менеджер для работы с промокодами"""
    
    # Типы промокодов
    TYPE_PERCENT_ALL = "percent_all"
    TYPE_PERCENT_SERVICE = "percent_service"
    TYPE_FREE_HOURS = "free_hours"
    TYPE_FREE_SERVICE = "free_service"
    
    # Доступные услуги для промокодов
    SERVICES = {
        "вокал": "🎤 Запись вокала",
        "инструмент": "🎸 Запись инструментов", 
        "аренда": "⏰ 12-часовая аренда",
        "сведение": "🎚️ Сведение/мастеринг",
        "трек": "🎵 Создание трека"
    }
    
    @staticmethod
    def generate_code() -> str:
        """Генерирует случайный промокод"""
        import random
        import string
        letters = ''.join(random.choices(string.ascii_uppercase, k=2))
        numbers = ''.join(random.choices(string.digits, k=4))
        letters2 = ''.join(random.choices(string.ascii_uppercase, k=2))
        return f"{letters}{numbers}{letters2}"
    
    @staticmethod
    async def create_promo_code(admin_id: str, data: dict) -> Tuple[bool, str, dict]:
        """Создаёт новый промокод"""
        try:
            code = data.get('code')
            target_user_id = data.get('target_user_id')
            discount_type = data.get('discount_type')
            discount_value = data.get('discount_value')
            target_service = data.get('target_service')
            expiry_date = data.get('expiry_date')
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM promo_codes WHERE code = ?', (code,))
                if cursor.fetchone():
                    return False, "❌ Промокод с таким кодом уже существует!", {}
                
                cursor.execute('''
                    INSERT INTO promo_codes 
                    (code, target_user_id, discount_type, discount_value, target_service, expiry_date, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (code, target_user_id, discount_type, discount_value, target_service, expiry_date, admin_id))
                
                promo_id = cursor.lastrowid
                conn.commit()
                logger.info(f"✅ Создан промокод {code} (ID: {promo_id}) админом {admin_id}")
                return True, f"✅ Промокод {code} успешно создан!", {'id': promo_id, 'code': code}
        except Exception as e:
            logger.error(f"❌ Ошибка создания промокода: {e}")
            return False, f"❌ Ошибка: {str(e)}", {}
    
    @staticmethod
    async def activate_promo_code(user_id: str, code: str, context=None) -> Tuple[bool, str, dict]:
        """Активирует промокод для пользователя (только один раз)"""
        try:
            code = code.upper().strip()
            if code.startswith('PROMO '):
                code = code[6:].strip()
            
            logger.info(f"🔍 Активация промокода '{code}' для пользователя {user_id}")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверка: использовал ли пользователь ЭТОТ промокод ранее
                cursor.execute('''
                    SELECT id, status FROM user_promo_usage 
                    WHERE user_id = ? AND promo_code = ? AND status IN ('used', 'pending')
                ''', (str(user_id), code))
                used_before = cursor.fetchone()
                
                if used_before:
                    logger.info(f"❌ Пользователь {user_id} уже использовал промокод {code} ранее")
                    return False, "ALREADY_USED_BEFORE", {}
                
                # Проверка: есть ли активный промокод
                cursor.execute('''
                    SELECT id, promo_code FROM user_promo_usage 
                    WHERE user_id = ? AND status = 'active'
                ''', (str(user_id),))
                existing_active = cursor.fetchone()
                
                if existing_active:
                    logger.info(f"❌ Пользователь {user_id} уже имеет активный промокод {existing_active[1]}")
                    return False, "ALREADY_USED", {'active_promo': existing_active[1]}
                
                # Проверка: существует ли промокод
                cursor.execute('''
                    SELECT code, target_user_id, discount_type, discount_value, 
                        target_service, expiry_date, is_active
                    FROM promo_codes 
                    WHERE code = ? AND is_active = 1
                ''', (code,))
                promo = cursor.fetchone()
                
                if not promo:
                    return False, "NOT_FOUND", {}
                
                (db_code, target_user_id, discount_type, discount_value, 
                 target_service, expiry_date, is_active) = promo
                
                # Проверка срока действия
                if expiry_date:
                    try:
                        expiry = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
                        now = DateTimeUtils.now().replace(tzinfo=None)
                        if now > expiry:
                            return False, "EXPIRED", {'expiry': expiry_date}
                    except Exception as e:
                        logger.error(f"Ошибка парсинга expiry_date: {e}")
                
                # Проверка, для кого промокод
                if target_user_id and str(target_user_id) != str(user_id):
                    return False, "NOT_YOURS", {'target': target_user_id}
                
                # Активируем промокод
                cursor.execute('''
                    INSERT INTO user_promo_usage (user_id, promo_code, status)
                    VALUES (?, ?, 'active')
                ''', (str(user_id), code))
                conn.commit()
                
                promo_info = {
                    'code': code,
                    'discount_type': discount_type,
                    'discount_value': discount_value,
                    'target_service': target_service
                }
                return True, "SUCCESS", promo_info
                
        except Exception as e:
            logger.error(f"❌ Ошибка активации промокода: {e}")
            return False, "ERROR", {'error': str(e)}
    
    @staticmethod
    def get_user_active_promo(user_id: str) -> Optional[dict]:
        """Возвращает активный промокод пользователя, если есть"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                now = DateTimeUtils.now().replace(tzinfo=None)
                now_str = now.strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                    SELECT u.promo_code, p.discount_type, p.discount_value, p.target_service,
                        p.expiry_date
                    FROM user_promo_usage u
                    JOIN promo_codes p ON u.promo_code = p.code
                    WHERE u.user_id = ? 
                    AND u.status = 'active'
                    AND p.is_active = 1
                    AND (p.expiry_date IS NULL OR datetime(p.expiry_date) > datetime(?))
                ''', (str(user_id), now_str))
                
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                promo_code, discount_type, discount_value, target_service, expiry_date = row
                
                return {
                    'code': promo_code,
                    'discount_type': discount_type,
                    'discount_value': discount_value,
                    'target_service': target_service,
                    'expiry_date': expiry_date
                }
        except Exception as e:
            logger.error(f"Ошибка получения активного промокода: {e}")
            return None
    
    @staticmethod
    def get_user_promo_history(user_id: str) -> List[dict]:
        """Возвращает историю промокодов пользователя"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT u.promo_code, u.activated_at, u.booking_id, u.applied_discount, u.status,
                        p.discount_type, p.discount_value, p.target_service, p.expiry_date,
                        p.is_active
                    FROM user_promo_usage u
                    JOIN promo_codes p ON u.promo_code = p.code
                    WHERE u.user_id = ?
                    ORDER BY u.activated_at DESC
                ''', (str(user_id),))
                rows = cursor.fetchall()
                
                result = []
                for row in rows:
                    result.append({
                        'code': row[0],
                        'activated_at': row[1],
                        'booking_id': row[2],
                        'applied_discount': row[3],
                        'status': row[4],
                        'discount_type': row[5],
                        'discount_value': row[6],
                        'target_service': row[7],
                        'expiry_date': row[8],
                        'is_active': row[9]
                    })
                return result
        except Exception as e:
            logger.error(f"Ошибка получения истории промокодов: {e}")
            return []
    
    @staticmethod
    def get_all_active_promos(user_id: str = None) -> List[dict]:
        """Возвращает все активные промокоды, которые пользователь ещё не использовал"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                now = DateTimeUtils.now().replace(tzinfo=None)
                now_str = now.strftime('%Y-%m-%d %H:%M:%S')
                
                if user_id:
                    cursor.execute('''
                        SELECT p.code, p.target_user_id, p.discount_type, p.discount_value, 
                               p.target_service, p.expiry_date, p.created_at
                        FROM promo_codes p
                        WHERE p.is_active = 1
                        AND (p.expiry_date IS NULL OR datetime(p.expiry_date) > datetime(?))
                        AND (
                            p.target_user_id IS NULL 
                            OR p.target_user_id = ?
                        )
                        AND NOT EXISTS (
                            SELECT 1 FROM user_promo_usage u
                            WHERE u.promo_code = p.code 
                            AND u.user_id = ? 
                            AND u.status IN ('used', 'pending')
                        )
                        ORDER BY p.created_at DESC
                    ''', (now_str, str(user_id), str(user_id)))
                else:
                    cursor.execute('''
                        SELECT p.code, p.target_user_id, p.discount_type, p.discount_value, 
                               p.target_service, p.expiry_date, p.created_at
                        FROM promo_codes p
                        WHERE p.is_active = 1
                        AND (p.expiry_date IS NULL OR datetime(p.expiry_date) > datetime(?))
                        ORDER BY p.created_at DESC
                    ''', (now_str,))
                
                rows = cursor.fetchall()
                
                result = []
                for row in rows:
                    result.append({
                        'code': row[0],
                        'target_user_id': row[1],
                        'discount_type': row[2],
                        'discount_value': row[3],
                        'target_service': row[4],
                        'expiry_date': row[5],
                        'created_at': row[6]
                    })
                return result
        except Exception as e:
            logger.error(f"Ошибка получения активных промокодов: {e}")
            return []
    
    @staticmethod
    def get_all_promos(include_inactive: bool = False) -> List[dict]:
        """Возвращает ВСЕ промокоды (активные и неактивные)"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                if include_inactive:
                    cursor.execute('''
                        SELECT code, target_user_id, discount_type, discount_value, 
                               target_service, expiry_date, is_active, created_at, created_by
                        FROM promo_codes 
                        ORDER BY created_at DESC
                    ''')
                else:
                    cursor.execute('''
                        SELECT code, target_user_id, discount_type, discount_value, 
                               target_service, expiry_date, is_active, created_at, created_by
                        FROM promo_codes 
                        WHERE is_active = 1
                        AND (expiry_date IS NULL OR datetime(expiry_date) > datetime('now'))
                        ORDER BY created_at DESC
                    ''')
                
                rows = cursor.fetchall()
                
                result = []
                for row in rows:
                    result.append({
                        'code': row[0],
                        'target_user_id': row[1],
                        'discount_type': row[2],
                        'discount_value': row[3],
                        'target_service': row[4],
                        'expiry_date': row[5],
                        'is_active': row[6],
                        'created_at': row[7],
                        'created_by': row[8]
                    })
                
                return result
        except Exception as e:
            logger.error(f"Ошибка получения всех промокодов: {e}")
            return []
    
    @staticmethod
    def delete_expired_promocodes() -> int:
        """Полностью удаляет истекшие промокоды из базы данных"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                now = DateTimeUtils.now().replace(tzinfo=None)
                now_str = now.strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                    DELETE FROM user_promo_usage 
                    WHERE promo_code IN (
                        SELECT code FROM promo_codes 
                        WHERE expiry_date IS NOT NULL AND expiry_date <= ?
                    )
                ''', (now_str,))
                
                cursor.execute('''
                    DELETE FROM promo_codes 
                    WHERE expiry_date IS NOT NULL AND expiry_date <= ?
                ''', (now_str,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"✅ Удалено {deleted_count} истекших промокодов")
                return deleted_count
        except Exception as e:
            logger.error(f"❌ Ошибка удаления истекших промокодов: {e}")
            return 0
    
    

    @staticmethod
    def deactivate_promo_code(promo_code: str, admin_id: str = None) -> Tuple[bool, str]:
        """Деактивирует промокод"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT id, code, is_active FROM promo_codes WHERE code = ?', (promo_code,))
                promo = cursor.fetchone()
                
                if not promo:
                    return False, f"❌ Промокод {promo_code} не найден!"
                
                promo_id, code, is_active = promo
                
                if is_active == 0:
                    return False, f"❌ Промокод {promo_code} уже деактивирован!"
                
                cursor.execute('UPDATE promo_codes SET is_active = 0 WHERE code = ?', (promo_code,))
                conn.commit()
                
                logger.info(f"✅ Промокод {promo_code} (ID: {promo_id}) деактивирован админом {admin_id}")
                return True, f"✅ Промокод {promo_code} успешно деактивирован!"
        except Exception as e:
            logger.error(f"❌ Ошибка деактивации промокода: {e}")
            return False, f"❌ Ошибка: {str(e)}"
    
    @staticmethod
    def format_promo_info(promo: dict) -> str:
        """Форматирует информацию о промокоде для отображения"""
        discount_type = promo.get('discount_type')
        discount_value = promo.get('discount_value')
        target_service = promo.get('target_service')
        
        if discount_type == PromoCodeManager.TYPE_PERCENT_ALL:
            return f"{discount_value}% на все услуги"
        elif discount_type == PromoCodeManager.TYPE_PERCENT_SERVICE:
            service_name = PromoCodeManager.SERVICES.get(target_service, target_service)
            return f"{discount_value}% на {service_name}"
        elif discount_type == PromoCodeManager.TYPE_FREE_HOURS:
            if discount_value == 1:
                hours_word = "час"
            elif 2 <= discount_value <= 4:
                hours_word = "часа"
            else:
                hours_word = "часов"
            return f"{discount_value} бесплатных {hours_word} (вокал/инструмент)"
        elif discount_type == PromoCodeManager.TYPE_FREE_SERVICE:
            service_name = PromoCodeManager.SERVICES.get(target_service, target_service)
            return f"Бесплатно: {service_name}"
        else:
            return f"Скидка: {discount_value}"

    @staticmethod
    def format_expiry_date(expiry_date_str: Optional[str]) -> str:
        """Форматирует дату окончания промокода для отображения"""
        if not expiry_date_str:
            return ""
        
        try:
            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d %H:%M:%S')
            now = DateTimeUtils.now().replace(tzinfo=None)
            
            if expiry_date < now:
                return " (истёк)"
            
            return f" (до {expiry_date.strftime('%d.%m.%Y')})"
        except:
            return ""

async def cleanup_expired_promocodes(context: ContextTypes.DEFAULT_TYPE):
    """Фоновая задача для удаления истекших промокодов"""
    try:
        logger.info("🔍 Запуск очистки истекших промокодов...")
        deleted_count = PromoCodeManager.delete_expired_promocodes()
        if deleted_count > 0:
            logger.info(f"🗑️ Удалено {deleted_count} истекших промокодов")
        else:
            logger.info("ℹ️ Истекших промокодов не найдено")
    except Exception as e:
        logger.error(f"❌ Ошибка в cleanup_expired_promocodes: {e}")

class Database:
    def __init__(self):
        if persistent_db.db_path != ':memory:' and os.path.exists(persistent_db.db_path):
            folder = os.path.dirname(persistent_db.db_path)
            if folder:
                self.db_path = os.path.join(folder, 'micasabot_main.db')
            else:
                self.db_path = 'micasabot_main.db'
        else:
            self.db_path = 'micasabot_main.db'
        
        logger.info(f"📊 Основная база данных: {self.db_path}")
        self._init_database()
        self._ensure_tables_exist()
        self._enable_wal_mode()
    
    def _enable_wal_mode(self):
        """Принудительное включение WAL режима"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA busy_timeout=60000')
            conn.execute('PRAGMA cache_size=-20000')
            result = conn.execute('PRAGMA journal_mode').fetchone()
            conn.close()
            logger.info(f"✅ WAL режим включен для {self.db_path}: {result[0]}")
        except Exception as e:
            logger.error(f"❌ Ошибка включения WAL для {self.db_path}: {e}")
    
    def _ensure_tables_exist(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ===== ТАБЛИЦА BOOKINGS =====
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        name TEXT NOT NULL,
                        contact TEXT NOT NULL,
                        telegram_id TEXT NOT NULL,
                        service TEXT NOT NULL,
                        time_slot TEXT NOT NULL,
                        date_str TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        price TEXT DEFAULT '0',
                        is_12_hours BOOLEAN DEFAULT 0,
                        is_mixing BOOLEAN DEFAULT 0,
                        is_track_creation BOOLEAN DEFAULT 0,
                        with_engineer BOOLEAN DEFAULT 0,
                        mixing_type TEXT,
                        track_type TEXT,
                        twelve_hours_type TEXT,
                        duration INTEGER DEFAULT 0,
                        start_hour INTEGER,
                        end_hour INTEGER,
                        is_contractual BOOLEAN DEFAULT 0,
                        base_price INTEGER DEFAULT 0,
                        level_discount_percent INTEGER DEFAULT 0,
                        level_coupon_id INTEGER,
                        promo_discount_percent INTEGER DEFAULT 0,
                        promo_code_used TEXT
                    )
                ''')
                
                # ===== ТАБЛИЦА USERS =====
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        telegram_id TEXT PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        unique_id TEXT UNIQUE,
                        registration_date TEXT,
                        total_spent INTEGER DEFAULT 0,
                        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_blocked BOOLEAN DEFAULT 0,
                        blocked_until DATETIME,
                        vinyls INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        permanent_discount INTEGER DEFAULT 0,
                        temporary_discount INTEGER DEFAULT 0,
                        discount_expiry DATETIME,
                        referral_code TEXT UNIQUE,
                        referred_by TEXT,
                        used_promos TEXT DEFAULT '',
                        morning_sessions INTEGER DEFAULT 0,
                        night_sessions INTEGER DEFAULT 0,
                        vocal_sessions INTEGER DEFAULT 0,
                        instrument_sessions INTEGER DEFAULT 0,
                        mixing_sessions INTEGER DEFAULT 0,
                        track_creation_sessions INTEGER DEFAULT 0,
                        rental_sessions INTEGER DEFAULT 0,
                        with_engineer_sessions INTEGER DEFAULT 0,
                        without_engineer_sessions INTEGER DEFAULT 0
                    )
                ''')
                
                # ===== ТАБЛИЦА USER_ACHIEVEMENTS =====
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_achievements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        achievement_id TEXT NOT NULL,
                        achievement_name TEXT NOT NULL,
                        achievement_type TEXT NOT NULL,
                        awarded_by TEXT,
                        awarded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, achievement_id)
                    )
                ''')
                
                # ===== ТАБЛИЦА USER_COUPONS =====
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_coupons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        level INTEGER NOT NULL,
                        discount_percent INTEGER NOT NULL,
                        remaining_uses INTEGER,
                        is_permanent BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                    )
                ''')
                
                # ===== ТАБЛИЦА PROMO_CODES =====
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS promo_codes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT UNIQUE NOT NULL,
                        target_user_id TEXT,
                        discount_type TEXT NOT NULL,
                        discount_value INTEGER NOT NULL,
                        target_service TEXT,
                        expiry_date DATETIME,
                        is_active BOOLEAN DEFAULT 1,
                        created_by TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (target_user_id) REFERENCES users (telegram_id)
                    )
                ''')
                
                # ===== ТАБЛИЦА USER_PROMO_USAGE =====
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_promo_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        promo_code TEXT NOT NULL,
                        activated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        booking_id INTEGER,
                        applied_discount INTEGER,
                        status TEXT DEFAULT 'active',
                        UNIQUE(user_id, promo_code),
                        FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                        FOREIGN KEY (promo_code) REFERENCES promo_codes (code),
                        FOREIGN KEY (booking_id) REFERENCES bookings (id)
                    )
                ''')
                
                # ===== ТАБЛИЦА NOTIFICATIONS =====
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        booking_id INTEGER NOT NULL,
                        user_id TEXT NOT NULL,
                        service_type TEXT NOT NULL,
                        notification_type TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        planned_send_time DATETIME NOT NULL,
                        actual_send_time DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (booking_id) REFERENCES bookings (id)
                    )
                ''')
                
                # ===== ТАБЛИЦА CACHE_SLOTS =====
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cache_slots (
                        date_str TEXT NOT NULL,
                        time_slot TEXT NOT NULL,
                        service_type TEXT NOT NULL,
                        booking_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (date_str, time_slot, service_type)
                    )
                ''')
                
                # ===== ИНДЕКСЫ =====
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookings_telegram ON bookings (telegram_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings (status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_coupons_user ON user_coupons(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_promo_codes_code ON promo_codes (code)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_promo_usage_user ON user_promo_usage(user_id)')
                
                conn.commit()
                logger.info("✅ Все таблицы созданы")
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания таблиц: {e}")
            import traceback
            traceback.print_exc()
    
    def _init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            pass
    
    @contextmanager
    def get_connection(self, timeout=60.0):
        """Получение соединения с БД с таймаутом"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=timeout
            )
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA busy_timeout=60000')
            conn.execute('PRAGMA cache_size=-20000')
            
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Ошибка БД: {e}")
            raise e
        finally:
            if conn:
                conn.close()

db = Database()

def handle_promo_code_on_cancellation(booking_id: int, telegram_id: str, hours_until: float, context=None):
    """Обрабатывает промокод при отмене записи"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем информацию о промокоде и типе услуги
            cursor.execute('''
                SELECT b.promo_code_used, b.is_mixing
                FROM bookings b
                WHERE b.id = ?
            ''', (booking_id,))
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return
            
            promo_code_used = result[0]
            is_mixing = result[1] == 1 if len(result) > 1 else False
            
            # Проверяем текущий статус промокода
            cursor.execute('''
                SELECT id, status FROM user_promo_usage 
                WHERE booking_id = ? AND promo_code = ?
            ''', (booking_id, promo_code_used))
            usage = cursor.fetchone()
            
            if not usage:
                return
            
            usage_id, current_status = usage
            
            # Если промокод уже использован - ничего не делаем
            if current_status == 'used':
                logger.info(f"ℹ️ Промокод {promo_code_used} уже использован, пропускаем")
                return
            
            # ===== ДЛЯ СВЕДЕНИЯ/МАСТЕРИНГА =====
            if is_mixing:
                # При отмене/отклонении - возвращаем промокод (статус active)
                cursor.execute('''
                    UPDATE user_promo_usage 
                    SET status = 'active', booking_id = NULL 
                    WHERE id = ?
                ''', (usage_id,))
                conn.commit()
                logger.info(f"🔄 Промокод {promo_code_used} для сведения/мастеринга ВОЗВРАЩЁН при отмене")
                return
            
            # ===== ДЛЯ ОСТАЛЬНЫХ УСЛУГ =====
            # Определяем, нужно ли вернуть или списать промокод
            if hours_until >= 12 or hours_until == -1:
                # Возвращаем промокод (статус active)
                cursor.execute('''
                    UPDATE user_promo_usage 
                    SET status = 'active', booking_id = NULL 
                    WHERE id = ?
                ''', (usage_id,))
                conn.commit()
                logger.info(f"🔄 Промокод {promo_code_used} ВОЗВРАЩЁН (до начала {hours_until:.1f} часов)")
            else:
                # Промокод сгорает (статус used)
                cursor.execute('''
                    UPDATE user_promo_usage 
                    SET status = 'used' 
                    WHERE id = ?
                ''', (usage_id,))
                conn.commit()
                logger.info(f"💀 Промокод {promo_code_used} СГОРЕЛ при отмене (до начала {hours_until:.1f} часов)")
            
    except Exception as e:
        logger.error(f"❌ Ошибка в handle_promo_code_on_cancellation: {e}")

# ===== ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ДИРЕКТОРИИ ДАННЫХ =====
def verify_data_directory():
    """Проверяет доступность директории данных при запуске"""
    global DATA_DIR
    
    print("=" * 60)
    print("🔍 ПРОВЕРКА ДИРЕКТОРИИ ДАННЫХ")
    print(f"📁 DATA_DIR = {DATA_DIR}")
    
    try:
        # Проверяем существование
        if not os.path.exists(DATA_DIR):
            print(f"📁 Директория {DATA_DIR} не существует, создаем...")
            os.makedirs(DATA_DIR, exist_ok=True)
            print(f"✅ Директория создана")
        
        # Проверяем права на запись
        test_file = os.path.join(DATA_DIR, '.startup_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"✅ Директория доступна для записи")
        
        # Показываем содержимое
        files = os.listdir(DATA_DIR)
        db_files = [f for f in files if f.endswith('.db')]
        if db_files:
            print(f"📊 Найдены файлы БД: {', '.join(db_files)}")
        else:
            print("📊 Файлы БД не найдены (будут созданы при первом запуске)")
        
        print("✅ Проверка директории данных завершена успешно")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА: Не удается получить доступ к {DATA_DIR}")
        print(f"❌ Причина: {e}")
        print("⚠️ Бот будет использовать текущую директорию для хранения данных")
        print("=" * 60)
        return False

def migrate_database():
    try:
        logger.info("🔧 Запуск миграции базы данных...")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # ===== ПРОВЕРКА И ДОБАВЛЕНИЕ ПОЛЕЙ В ТАБЛИЦУ bookings =====
            cursor.execute("PRAGMA table_info(bookings)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Существующие поля
            if 'is_contractual' not in columns:
                logger.info("📋 Добавляем столбец is_contractual в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN is_contractual BOOLEAN DEFAULT 0")
                logger.info("✅ Столбец is_contractual успешно добавлен")
            
            if 'start_hour' not in columns:
                logger.info("📋 Добавляем столбец start_hour в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN start_hour INTEGER")
                logger.info("✅ Столбец start_hour успешно добавлен")
            
            if 'end_hour' not in columns:
                logger.info("📋 Добавляем столбец end_hour в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN end_hour INTEGER")
                logger.info("✅ Столбец end_hour успешно добавлен")
            
            if 'timestamp' not in columns:
                logger.info("📋 Добавляем столбец timestamp в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP")
                logger.info("✅ Столбец timestamp успешно добавлен")
            
            # Поля для хранения информации о скидках
            if 'base_price' not in columns:
                logger.info("📋 Добавляем столбец base_price в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN base_price INTEGER DEFAULT 0")
                logger.info("✅ Столбец base_price успешно добавлен")

            if 'level_discount_percent' not in columns:
                logger.info("📋 Добавляем столбец level_discount_percent в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN level_discount_percent INTEGER DEFAULT 0")
                logger.info("✅ Столбец level_discount_percent успешно добавлен")

            if 'level_coupon_id' not in columns:
                logger.info("📋 Добавляем столбец level_coupon_id в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN level_coupon_id INTEGER")
                logger.info("✅ Столбец level_coupon_id успешно добавлен")

            if 'promo_discount_percent' not in columns:
                logger.info("📋 Добавляем столбец promo_discount_percent в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN promo_discount_percent INTEGER DEFAULT 0")
                logger.info("✅ Столбец promo_discount_percent успешно добавлен")

            if 'promo_code_used' not in columns:
                logger.info("📋 Добавляем столбец promo_code_used в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN promo_code_used TEXT")
                logger.info("✅ Столбец promo_code_used успешно добавлен")
            
            # Новые колонки
            if 'is_admin_booking' not in columns:
                logger.info("📋 Добавляем столбец is_admin_booking в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN is_admin_booking INTEGER DEFAULT 0")
                logger.info("✅ Столбец is_admin_booking успешно добавлен")
            
            if 'vinyls_awarded' not in columns:
                logger.info("📋 Добавляем столбец vinyls_awarded в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN vinyls_awarded INTEGER DEFAULT 0")
                logger.info("✅ Столбец vinyls_awarded успешно добавлен")
            
            # ===== ДОБАВЛЯЕМ ПОЛЕ free_service_applied =====
            if 'free_service_applied' not in columns:
                logger.info("📋 Добавляем столбец free_service_applied в bookings...")
                cursor.execute("ALTER TABLE bookings ADD COLUMN free_service_applied INTEGER DEFAULT 0")
                logger.info("✅ Столбец free_service_applied успешно добавлен")
            
            # ===== ПРОВЕРКА И ДОБАВЛЕНИЕ ПОЛЕЙ В ТАБЛИЦУ users =====
            cursor.execute("PRAGMA table_info(users)")
            user_columns = [column[1] for column in cursor.fetchall()]
            
            if 'is_blocked' not in user_columns:
                logger.info("📋 Добавляем столбец is_blocked в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0")
                logger.info("✅ Столбец is_blocked успешно добавлен")
            
            if 'blocked_until' not in user_columns:
                logger.info("📋 Добавляем столбец blocked_until в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN blocked_until DATETIME")
                logger.info("✅ Столбец blocked_until успешно добавлен")
            
            if 'vinyls' not in user_columns:
                logger.info("📋 Добавляем столбец vinyls в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN vinyls INTEGER DEFAULT 0")
                logger.info("✅ Столбец vinyls успешно добавлен")
            
            if 'level' not in user_columns:
                logger.info("📋 Добавляем столбец level в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
                logger.info("✅ Столбец level успешно добавлен")
            
            if 'permanent_discount' not in user_columns:
                logger.info("📋 Добавляем столбец permanent_discount в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN permanent_discount INTEGER DEFAULT 0")
                logger.info("✅ Столбец permanent_discount успешно добавлен")
            
            if 'temporary_discount' not in user_columns:
                logger.info("📋 Добавляем столбец temporary_discount в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN temporary_discount INTEGER DEFAULT 0")
                logger.info("✅ Столбец temporary_discount успешно добавлен")
            
            if 'discount_expiry' not in user_columns:
                logger.info("📋 Добавляем столбец discount_expiry в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN discount_expiry DATETIME")
                logger.info("✅ Столбец discount_expiry успешно добавлен")
            
            if 'referral_code' not in user_columns:
                logger.info("📋 Добавляем столбец referral_code в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
                logger.info("✅ Столбец referral_code успешно добавлен")
            
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users (referral_code) WHERE referral_code IS NOT NULL")
                logger.info("✅ Уникальный индекс для referral_code создан")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось создать уникальный индекс: {e}")
            
            if 'referred_by' not in user_columns:
                logger.info("📋 Добавляем столбец referred_by в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN referred_by TEXT")
                logger.info("✅ Столбец referred_by успешно добавлен")
            
            if 'used_promos' not in user_columns:
                logger.info("📋 Добавляем столбец used_promos в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN used_promos TEXT DEFAULT ''")
                logger.info("✅ Столбец used_promos успешно добавлен")
            
            if 'morning_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец morning_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN morning_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец morning_sessions успешно добавлен")
            
            if 'night_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец night_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN night_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец night_sessions успешно добавлен")
            
            if 'vocal_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец vocal_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN vocal_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец vocal_sessions успешно добавлен")
            
            if 'instrument_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец instrument_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN instrument_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец instrument_sessions успешно добавлен")
            
            if 'mixing_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец mixing_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN mixing_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец mixing_sessions успешно добавлен")
            
            if 'track_creation_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец track_creation_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN track_creation_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец track_creation_sessions успешно добавлен")
            
            if 'rental_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец rental_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN rental_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец rental_sessions успешно добавлен")
            
            if 'with_engineer_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец with_engineer_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN with_engineer_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец with_engineer_sessions успешно добавлен")
            
            if 'without_engineer_sessions' not in user_columns:
                logger.info("📋 Добавляем столбец without_engineer_sessions в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN without_engineer_sessions INTEGER DEFAULT 0")
                logger.info("✅ Столбец without_engineer_sessions успешно добавлен")
            
            if 'achievements' not in user_columns:
                logger.info("📋 Добавляем столбец achievements в users...")
                cursor.execute("ALTER TABLE users ADD COLUMN achievements TEXT DEFAULT '{}'")
                logger.info("✅ Столбец achievements успешно добавлен")
            
            # ===== ТАБЛИЦА user_coupons =====
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_coupons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    discount_percent INTEGER NOT NULL,
                    remaining_uses INTEGER,
                    is_permanent BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_coupons_user ON user_coupons(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_coupons_level ON user_coupons(level)')
            logger.info("✅ Таблица user_coupons создана")
            
            # ===== ТАБЛИЦА user_promo_usage =====
            cursor.execute("PRAGMA table_info(user_promo_usage)")
            promo_columns = [column[1] for column in cursor.fetchall()]
            
            if 'status' not in promo_columns:
                logger.info("📋 Добавляем столбец status в user_promo_usage...")
                cursor.execute("ALTER TABLE user_promo_usage ADD COLUMN status TEXT DEFAULT 'active'")
                logger.info("✅ Столбец status успешно добавлен в user_promo_usage")
            else:
                logger.info("ℹ️ Столбец status уже существует в user_promo_usage")
            
            # Обновляем существующие записи
            cursor.execute('''
                UPDATE user_promo_usage 
                SET status = 'active' 
                WHERE status IS NULL
            ''')
            if cursor.rowcount > 0:
                logger.info(f"✅ Обновлено {cursor.rowcount} записей в user_promo_usage (status -> 'active')")
            
            # Добавляем индексы для user_promo_usage
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_promo_status ON user_promo_usage (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_promo_booking ON user_promo_usage (booking_id)')
            logger.info("✅ Индексы для user_promo_usage созданы")
            
            # ===== ТАБЛИЦА booking_referral_bonuses =====
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS booking_referral_bonuses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    referrer_id TEXT NOT NULL,
                    bonus_type TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("✅ Таблица booking_referral_bonuses создана")
            
            # ===== ТАБЛИЦА cache_slots =====
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_slots (
                    date_str TEXT NOT NULL,
                    time_slot TEXT NOT NULL,
                    service_type TEXT NOT NULL,
                    booking_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date_str, time_slot, service_type)
                )
            ''')
            logger.info("✅ Таблица cache_slots создана")
            
            # ===== ТАБЛИЦА monitoring =====
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS monitoring (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_type TEXT NOT NULL,
                    check_value REAL NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("✅ Таблица monitoring создана")
            
            # ===== ОБНОВЛЕНИЕ ДОГОВОРНЫХ ЗАПИСЕЙ =====
            cursor.execute('''
                UPDATE bookings 
                SET is_contractual = 1 
                WHERE (date_str LIKE '%Не указана%' 
                   OR date_str LIKE '%договорная%'
                   OR time_slot IN ('Не указано', 'Не указано (договорная)')
                   OR service LIKE '%Договорная%'
                   OR service LIKE '%договорная%')
                   AND (is_contractual IS NULL OR is_contractual = 0)
            ''')
            updated_count = cursor.rowcount
            if updated_count > 0:
                logger.info(f"✅ Обновлено {updated_count} записей как договорные")
            
            # ===== ГЕНЕРАЦИЯ РЕФЕРАЛЬНЫХ КОДОВ (только для пользователей без кода) =====
            cursor.execute('''
                SELECT telegram_id FROM users WHERE referral_code IS NULL
            ''')
            users_without_code = cursor.fetchall()
            
            for user in users_without_code:
                telegram_id = user[0]
                code = AchievementSystem.generate_referral_code(telegram_id)
                cursor.execute('''
                    UPDATE users SET referral_code = ? WHERE telegram_id = ?
                ''', (code, telegram_id))
            
            if users_without_code:
                logger.info(f"✅ Сгенерировано реферальных кодов для {len(users_without_code)} пользователей")
            
            # ===== ОБНОВЛЕНИЕ СТАТУСА ДЛЯ ЗАПИСЕЙ С "ожидает" =====
            cursor.execute('''
                UPDATE bookings 
                SET status = 'pending' 
                WHERE status = 'ожидает'
            ''')
            if cursor.rowcount > 0:
                logger.info(f"✅ Исправлено записей с 'ожидает' на 'pending': {cursor.rowcount}")
            
            # ===== НИКОГДА НЕ ВЫДАЁМ КУПОНЫ ПРИ МИГРАЦИИ! =====
            # Купоны выдаются ТОЛЬКО при регистрации нового пользователя в функции start()
            
            conn.commit()
            
        logger.info("🎉 Миграция базы данных завершена успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка миграции базы данных: {e}")
        import traceback
        traceback.print_exc()
        return False

class CouponManager:
    """Менеджер для управления купонами уровней"""
    
    @staticmethod
    def add_level_coupons(user_id: str, level: int, db_conn=None):
        """Добавляет купоны за достижение уровня (только если нет такого же)"""
        try:
            level_info = None
            for lvl in AchievementSystem.LEVELS:
                if lvl['level'] == level:
                    level_info = lvl
                    break
            
            if not level_info:
                logger.error(f"❌ Информация об уровне {level} не найдена")
                return False
            
            discount = level_info['discount']
            uses = level_info.get('uses')
            is_permanent = level_info.get('discount_type') == 'permanent'
            
            if db_conn:
                conn = db_conn
                cursor = conn.cursor()
                should_close = False
            else:
                conn = sqlite3.connect(db.db_path, timeout=30.0)
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                cursor = conn.cursor()
                should_close = True
            
            # ===== ПРОВЕРЯЕМ, ЕСТЬ ЛИ УЖЕ ТАКОЙ КУПОН =====
            cursor.execute('''
                SELECT id FROM user_coupons 
                WHERE user_id = ? AND level = ? AND discount_percent = ?
            ''', (user_id, level, discount))
            
            existing = cursor.fetchone()
            
            if existing:
                logger.info(f"ℹ️ Купон уровня {level} уже есть у пользователя {user_id}, пропускаем")
                if should_close:
                    conn.close()
                return False
            
            # Добавляем купон
            cursor.execute('''
                INSERT INTO user_coupons 
                (user_id, level, discount_percent, remaining_uses, is_permanent)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, level, discount, uses, 1 if is_permanent else 0))
            
            logger.info(f"✅ Добавлены купоны уровня {level} ({discount}%, {uses if uses else 'бессрочно'}) для {user_id}")
            
            if should_close:
                conn.commit()
                conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления купонов уровня {level}: {e}")
            if 'should_close' in locals() and should_close and 'conn' in locals():
                try:
                    conn.close()
                except:
                    pass
            return False
    
    @staticmethod
    def get_user_coupons(user_id: str):
        """Возвращает все активные купоны пользователя (с учётом текущего уровня)"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Получаем текущий уровень пользователя
                cursor.execute('SELECT level FROM users WHERE telegram_id = ?', (user_id,))
                result = cursor.fetchone()
                current_level = result[0] if result else 1
                
                # ===== ВАЖНО! ЕСЛИ LEVEL = 0 ИЛИ NULL, УСТАНАВЛИВАЕМ 1 =====
                if current_level is None or current_level == 0:
                    current_level = 1
                    # Обновляем в базе
                    cursor.execute('UPDATE users SET level = 1 WHERE telegram_id = ?', (user_id,))
                    conn.commit()
                    logger.info(f"🔧 Установлен level = 1 для пользователя {user_id}")
                
                # Получаем купоны
                cursor.execute('''
                    SELECT id, level, discount_percent, remaining_uses, is_permanent
                    FROM user_coupons 
                    WHERE user_id = ?
                    AND level <= ?
                    AND (remaining_uses > 0 OR is_permanent = 1)
                    ORDER BY discount_percent DESC
                ''', (user_id, current_level))
                
                rows = cursor.fetchall()
                coupons = []
                for row in rows:
                    coupons.append({
                        'id': row[0],
                        'level': row[1],
                        'discount': row[2],
                        'remaining': row[3],
                        'is_permanent': row[4] == 1
                    })
                return coupons
        except Exception as e:
            logger.error(f"❌ Ошибка получения купонов: {e}")
            return []
    
    @staticmethod
    def get_total_discount(user_id: str):
        """Возвращает общую доступную скидку и список купонов"""
        coupons = CouponManager.get_user_coupons(user_id)
        
        total = 0
        coupon_list = []
        
        for coupon in coupons:
            if coupon['is_permanent']:
                total += coupon['discount']
                coupon_list.append({
                    'level': coupon['level'],
                    'discount': coupon['discount'],
                    'remaining': '∞',
                    'is_permanent': True,
                    'total_value': coupon['discount']
                })
            else:
                uses_value = coupon['discount'] * coupon['remaining']
                total += uses_value
                coupon_list.append({
                    'level': coupon['level'],
                    'discount': coupon['discount'],
                    'remaining': coupon['remaining'],
                    'total_value': uses_value,
                    'is_permanent': False
                })
        
        effective_total = min(total, 100)
        return effective_total, coupon_list, total
    
    @staticmethod
    def use_coupon(user_id: str, coupon_id: int, db_conn=None):
        """Использует 1 использование купона"""
        try:
            if db_conn:
                conn = db_conn
                cursor = conn.cursor()
                should_close = False
            else:
                conn = sqlite3.connect(db.db_path, timeout=30.0)
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                cursor = conn.cursor()
                should_close = True
            
            cursor.execute('''
                SELECT id, level, discount_percent, remaining_uses, is_permanent
                FROM user_coupons 
                WHERE id = ? AND user_id = ?
            ''', (coupon_id, user_id))
            
            coupon = cursor.fetchone()
            
            if not coupon:
                if should_close:
                    conn.close()
                return False, "Купон не найден", 0
            
            coupon_id_db, level, discount, remaining, is_permanent = coupon
            
            if is_permanent:
                if should_close:
                    conn.close()
                return True, f"Применена вечная скидка {discount}%", discount
            
            if remaining <= 0:
                if should_close:
                    conn.close()
                return False, "Купон уже использован", 0
            
            new_remaining = remaining - 1
            
            if new_remaining == 0:
                cursor.execute('DELETE FROM user_coupons WHERE id = ?', (coupon_id_db,))
                logger.info(f"✅ Купон уровня {level} ({discount}%) полностью использован пользователем {user_id}")
            else:
                cursor.execute('''
                    UPDATE user_coupons 
                    SET remaining_uses = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_remaining, coupon_id_db))
                logger.info(f"✅ Использован 1 купон уровня {level} ({discount}%), осталось {new_remaining} у {user_id}")
            
            if should_close:
                conn.commit()
                conn.close()
            
            return True, f"Применена скидка {discount}%", discount
            
        except Exception as e:
            logger.error(f"❌ Ошибка использования купона: {e}")
            if should_close and 'conn' in locals():
                conn.close()
            return False, str(e), 0
    
    @staticmethod
    def get_best_coupon(user_id: str):
        """Возвращает самый выгодный купон (с наибольшим процентом) с учётом текущего уровня"""
        
        # Получаем текущий уровень пользователя
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT level FROM users WHERE telegram_id = ?', (user_id,))
            result = cursor.fetchone()
            current_level = result[0] if result else 1
            
            # ===== ВАЖНО! ЕСЛИ LEVEL = 0 ИЛИ NULL, УСТАНАВЛИВАЕМ 1 =====
            if current_level is None or current_level == 0:
                current_level = 1
                cursor.execute('UPDATE users SET level = 1 WHERE telegram_id = ?', (user_id,))
                conn.commit()
                logger.info(f"🔧 Установлен level = 1 для пользователя {user_id} (в get_best_coupon)")
        
        # Получаем все купоны пользователя
        coupons = CouponManager.get_user_coupons(user_id)
        
        if not coupons:
            return None
        
        # Фильтруем купоны - оставляем только купоны уровней НЕ ВЫШЕ текущего
        available_coupons = []
        for coupon in coupons:
            if coupon['level'] <= current_level:
                available_coupons.append(coupon)
        
        if not available_coupons:
            return None
        
        # Сортируем по проценту скидки (от большего к меньшему)
        available_coupons.sort(key=lambda x: x['discount'], reverse=True)
        
        # Возвращаем первый доступный купон
        for coupon in available_coupons:
            if coupon['is_permanent'] or coupon['remaining'] > 0:
                return coupon
        
        return None

    @staticmethod
    def format_coupons_for_display(user_id: str) -> str:
        """Форматирует список купонов для отображения в 'Мой уровень' (только активные по уровню)"""
        
        # Получаем текущий уровень пользователя
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT level FROM users WHERE telegram_id = ?', (user_id,))
            result = cursor.fetchone()
            current_level = result[0] if result else 1
        
        # Получаем купоны с учётом текущего уровня
        coupons = CouponManager.get_user_coupons(user_id)
        
        if not coupons:
            return "🎟️ Активных купонов нет\n"
        
        total = 0
        coupon_list = []
        
        for coupon in coupons:
            if coupon['is_permanent']:
                total += coupon['discount']
                coupon_list.append({
                    'level': coupon['level'],
                    'discount': coupon['discount'],
                    'remaining': '∞',
                    'is_permanent': True,
                    'total_value': coupon['discount']
                })
            else:
                uses_value = coupon['discount'] * coupon['remaining']
                total += uses_value
                coupon_list.append({
                    'level': coupon['level'],
                    'discount': coupon['discount'],
                    'remaining': coupon['remaining'],
                    'total_value': uses_value,
                    'is_permanent': False
                })
        
        if not coupon_list:
            return "🎟️ Активных купонов нет\n"
        
        text = "🎟️ **Доступные купоны уровней:**\n\n"
        
        levels_dict = {}
        for coupon in coupon_list:
            level = coupon['level']
            if level not in levels_dict:
                levels_dict[level] = []
            levels_dict[level].append(coupon)
        
        level_names = {}
        for lvl in AchievementSystem.LEVELS:
            level_names[lvl['level']] = lvl['name']
        
        for level in sorted(levels_dict.keys()):
            # Показываем только уровни не выше текущего
            if level > current_level:
                continue
            
            level_coupons = levels_dict[level]
            level_name = level_names.get(level, f"Уровень {level}")
            
            for coupon in level_coupons:
                if coupon['is_permanent']:
                    text += f"  👑 {level_name}: {coupon['discount']}% (вечная скидка, безлимит)\n"
                else:
                    text += f"  🎫 {level_name}: {coupon['discount']}% × {coupon['remaining']} = {coupon['total_value']}%\n"
        
        effective_total = min(total, 100)
        
        text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💰 **Доступная скидка:** {effective_total}%"
        
        if total > 100:
            text += f" (максимум 100%)"
        
        return text

class UserLimits:
    @staticmethod
    def check_user_limits(user_id: str, is_date_required: bool) -> Tuple[bool, str, int]:
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                if int(user_id) in ADMIN_IDS:
                    return True, "✅ Администратор", 0
                
                cursor.execute('SELECT is_blocked, blocked_until FROM users WHERE telegram_id = ?', (user_id,))
                block_data = cursor.fetchone()
                if block_data:
                    is_blocked, blocked_until = block_data
                    if is_blocked == 1:
                        if blocked_until:
                            try:
                                blocked_time = datetime.strptime(blocked_until, '%Y-%m-%d %H:%M:%S')
                                if blocked_time > datetime.now():
                                    return False, "🔒 Вы заблокированы! Обратитесь к администратору.", 0
                            except:
                                return False, "🔒 Вы заблокированы! Обратитесь к администратору.", 0
                        else:
                            return False, "🔒 Вы заблокированы! Обратитесь к администратору.", 0
                
                admin_exclude = """
                    AND service NOT LIKE '%Админская%' 
                    AND service NOT LIKE '%админская%'
                    AND service NOT LIKE '%(Админ)%'
                    AND service NOT LIKE '%(админ)%'
                    AND date_str NOT LIKE '%админская запись%'
                """
                
                if is_date_required:
                    cursor.execute(f'''
                        SELECT COUNT(*) FROM bookings 
                        WHERE telegram_id = ? 
                        AND status IN ('pending', 'confirmed', 'подтвержден')
                        AND date_str NOT LIKE '%Не указана%'
                        AND date_str NOT LIKE '%договорная%'
                        AND date_str NOT LIKE '%админская запись%'
                        AND is_contractual = 0
                        {admin_exclude}
                    ''', (user_id,))
                    limit = 2
                else:
                    cursor.execute(f'''
                        SELECT COUNT(*) FROM bookings 
                        WHERE telegram_id = ? 
                        AND status IN ('pending', 'confirmed', 'подтвержден')
                        AND (
                            date_str LIKE '%Не указана%' 
                            OR date_str LIKE '%договорная%'
                            OR date_str LIKE '%админская запись%'
                            OR is_contractual = 1
                        )
                        AND (
                            status NOT IN ('confirmed', 'подтвержден')
                            OR (
                                status IN ('confirmed', 'подтвержден')
                                AND NOT (
                                    date_str LIKE '%Не указана%'
                                    OR date_str LIKE '%договорная%'
                                    OR is_contractual = 1
                                )
                            )
                        )
                        {admin_exclude}
                    ''', (user_id,))
                    limit = 3
                
                current_count = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT COUNT(*) FROM bookings 
                    WHERE telegram_id = ? 
                    AND status IN ('pending', 'confirmed', 'подтвержден')
                    AND (
                        service LIKE '%Админская%' 
                        OR service LIKE '%админская%'
                        OR service LIKE '%(Админ)%'
                        OR service LIKE '%(админ)%'
                        OR date_str LIKE '%админская запись%'
                    )
                ''', (user_id,))
                
                admin_count = cursor.fetchone()[0]
                logger.info(f"🔍 Проверка лимитов для {user_id}: обычных={current_count}, админских={admin_count}")
                
                if current_count >= limit:
                    if is_date_required:
                        # ===== ЖИРНЫЙ ТОЛЬКО ЗАГОЛОВОК, СТАТИСТИКА И "ЧТО МОЖНО СДЕЛАТЬ" =====
                        message = (
                            f"*❌ Превышен лимит записей в студию!*\n\n"
                            f"*📊 У вас уже есть {current_count} записи в студию*\n"
                            f"*🎯 Максимально можно: {limit} записи в студию*\n\n"
                            f"*💡 Что можно сделать:*\n"
                            f"• Дождитесь обработки текущих заявок\n"
                            f"• Или обратитесь к администратору @mothman32"
                        )
                    else:
                        # ===== ЖИРНЫЙ ТОЛЬКО ЗАГОЛОВОК, СТАТИСТИКА И "ЧТО МОЖНО СДЕЛАТЬ" =====
                        message = (
                            f"*❌ Превышен лимит договорных записей!*\n\n"
                            f"*📊 У вас уже есть {current_count} договорных записи*\n"
                            f"*🎯 Максимально можно: {limit} договорные записи*\n\n"
                            f"*💡 Что можно сделать:*\n"
                            f"• Дождитесь обработки текущих заявок\n"
                            f"• Или обратитесь к администратору @mothman32"
                        )
                    return False, message, current_count
                
                return True, f"✅ Можно создать запись (у вас {current_count} из {limit})", current_count
                
        except Exception as e:
            logger.error(f"Ошибка проверки лимитов пользователя: {e}")
            return True, "⚠️ Ошибка проверки лимитов", 0

class MemoryCache:
    date_slots_cache = {}
    cache_timestamps = {}
    future_dates_cache = None
    future_dates_time = 0
    date_load_cache = {}
    date_load_time = 0
    date_colors_cache = {}
    date_colors_time = 0
    lock = threading.RLock()
    
    @staticmethod
    def get_date_slots(date_str, ttl=60):
        with MemoryCache.lock:
            if date_str in MemoryCache.date_slots_cache:
                if time.time() - MemoryCache.cache_timestamps.get(date_str, 0) < ttl:
                    return MemoryCache.date_slots_cache[date_str]
            return None
    
    @staticmethod
    def set_date_slots(date_str, slots):
        with MemoryCache.lock:
            MemoryCache.date_slots_cache[date_str] = slots
            MemoryCache.cache_timestamps[date_str] = time.time()
    
    @staticmethod
    def invalidate_date(date_str):
        with MemoryCache.lock:
            logger.info(f"🗑️ Очистка кэша для даты: '{date_str}'")
            
            # Очищаем слоты
            MemoryCache.date_slots_cache.pop(date_str, None)
            MemoryCache.cache_timestamps.pop(date_str, None)
            MemoryCache.date_load_cache.pop(date_str, None)
            
            # Очищаем цвета
            keys_to_remove = []
            for key in MemoryCache.date_colors_cache.keys():
                if date_str in key:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                MemoryCache.date_colors_cache.pop(key, None)
                logger.info(f"🗑️ Удалён цвет для ключа: '{key}'")
            
            # Очищаем future_dates
            MemoryCache.future_dates_cache = None
            MemoryCache.future_dates_time = 0
            
            logger.info(f"🗑️ Кэш полностью очищен для даты: '{date_str}'")
    
    @staticmethod
    def get_future_dates(ttl=300):
        with MemoryCache.lock:
            if MemoryCache.future_dates_cache and time.time() - MemoryCache.future_dates_time < ttl:
                return MemoryCache.future_dates_cache
            return None
    
    @staticmethod
    def set_future_dates(dates):
        with MemoryCache.lock:
            MemoryCache.future_dates_cache = dates
            MemoryCache.future_dates_time = time.time()
    
    @staticmethod
    def get_date_load(date_str, ttl=300):
        with MemoryCache.lock:
            if date_str in MemoryCache.date_load_cache:
                cached_time, load = MemoryCache.date_load_cache[date_str]
                if time.time() - cached_time < ttl:
                    return load
            return None
    
    @staticmethod
    def set_date_load(date_str, load):
        with MemoryCache.lock:
            MemoryCache.date_load_cache[date_str] = (time.time(), load)
    
    @staticmethod
    def get_date_color(date_key, ttl=300):
        with MemoryCache.lock:
            if date_key in MemoryCache.date_colors_cache:
                cached_time, color = MemoryCache.date_colors_cache[date_key]
                if time.time() - cached_time < ttl:
                    return color
            return None
    
    @staticmethod
    def set_date_color(date_key, color):
        with MemoryCache.lock:
            MemoryCache.date_colors_cache[date_key] = (time.time(), color)

class RateLimiter:
    @staticmethod
    def check_rate_limit(user_id: str, limit: int = 60, period: int = 60) -> Tuple[bool, str, Optional[float]]:
        try:
            now = time.time()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    'SELECT request_count, first_request_time, is_blocked, blocked_until FROM rate_limits WHERE user_id = ?',
                    (str(user_id),)
                )
                result = cursor.fetchone()
                
                if not result:
                    cursor.execute('''
                        INSERT INTO rate_limits (user_id, request_count, first_request_time, last_request_time)
                        VALUES (?, 1, datetime(?, 'unixepoch'), datetime(?, 'unixepoch'))
                    ''', (str(user_id), now, now))
                    return True, "", None
                
                request_count, first_request_time_str, is_blocked, blocked_until_str = result
                
                if is_blocked and blocked_until_str:
                    blocked_until = datetime.strptime(blocked_until_str, '%Y-%m-%d %H:%M:%S').timestamp()
                    if now < blocked_until:
                        seconds_to_wait = blocked_until - now
                        return False, f"Вы временно заблокированы за слишком частые запросы. Подождите {int(seconds_to_wait)} секунд.", seconds_to_wait
                    else:
                        cursor.execute('''
                            UPDATE rate_limits 
                            SET is_blocked = 0, blocked_until = NULL, request_count = 0,
                                first_request_time = datetime(?, 'unixepoch')
                            WHERE user_id = ?
                        ''', (now, str(user_id)))
                
                if first_request_time_str:
                    first_request_time = datetime.strptime(first_request_time_str, '%Y-%m-%d %H:%M:%S').timestamp()
                else:
                    first_request_time = now
                
                if now - first_request_time > period:
                    cursor.execute('''
                        UPDATE rate_limits 
                        SET request_count = 1, first_request_time = datetime(?, 'unixepoch'),
                            last_request_time = datetime(?, 'unixepoch')
                        WHERE user_id = ?
                    ''', (now, now, str(user_id)))
                    return True, "", None
                
                if request_count >= limit:
                    blocked_until = now + 300
                    blocked_until_str = datetime.fromtimestamp(blocked_until).strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute('''
                        UPDATE rate_limits 
                        SET is_blocked = 1, blocked_until = ?, request_count = 0
                        WHERE user_id = ?
                    ''', (blocked_until_str, str(user_id)))
                    
                    return False, "Слишком много запросов! Вы заблокированы на 5 минут.", 300.0
                
                cursor.execute('''
                    UPDATE rate_limits 
                    SET request_count = request_count + 1, last_request_time = datetime(?, 'unixepoch')
                    WHERE user_id = ?
                ''', (now, str(user_id)))
                
                return True, "", None
                
        except Exception as e:
            logger.error(f"Ошибка rate limiting: {e}")
            return True, "", None

class Monitor:
    @staticmethod
    def check_database_size():
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monitoring'")
                if not cursor.fetchone():
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS monitoring (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            check_type TEXT NOT NULL,
                            check_value REAL NOT NULL,
                            status TEXT NOT NULL,
                            message TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    conn.commit()
            
            db_size = os.path.getsize(db.db_path) if os.path.exists(db.db_path) else 0
            mb_size = db_size / (1024 * 1024)
            
            status = "OK"
            message = f"Размер БД: {mb_size:.2f} MB"
            
            if mb_size > 100:
                status = "WARNING"
                message = f"Размер БД превышает 100 MB: {mb_size:.2f} MB"
            elif mb_size > 500:
                status = "CRITICAL"
                message = f"Размер БД критически большой: {mb_size:.2f} MB"
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO monitoring (check_type, check_value, status, message)
                    VALUES (?, ?, ?, ?)
                ''', ('db_size', mb_size, status, message))
            
            return status, message
            
        except Exception as e:
            return "ERROR", f"Ошибка проверки размера БД: {str(e)}"
    
    @staticmethod
    def check_bookings_count():
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bookings'")
                if not cursor.fetchone():
                    return "ERROR", "Таблица bookings не существует"
                
                cursor.execute('SELECT COUNT(*) FROM bookings')
                count = cursor.fetchone()[0]
            
            status = "OK"
            message = f"Записей в БД: {count}"
            
            if count > 10000:
                status = "WARNING"
                message = f"Большое количество записей: {count}"
            elif count > 50000:
                status = "CRITICAL"
                message = f"Критическое количество записей: {count}"
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO monitoring (check_type, check_value, status, message)
                    VALUES (?, ?, ?, ?)
                ''', ('bookings_count', count, status, message))
            
            return status, message
            
        except Exception as e:
            return "ERROR", f"Ошибка проверки количества записей: {str(e)}"
    
    @staticmethod
    def check_notifications():
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
                if not cursor.fetchone():
                    return "ERROR", "Таблица notifications не существует"
                
                cursor.execute('SELECT COUNT(*) FROM notifications WHERE status = "pending"')
                pending = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM notifications WHERE status = "error"')
                errors = cursor.fetchone()[0]
            
            status = "OK"
            message = f"Уведомлений: {pending} ожидают, {errors} с ошибками"
            
            if errors > 10:
                status = "WARNING"
                message = f"Много уведомлений с ошибками: {errors}"
            elif errors > 50:
                status = "CRITICAL"
                message = f"Критическое количество ошибок уведомлений: {errors}"
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO monitoring (check_type, check_value, status, message)
                    VALUES (?, ?, ?, ?)
                ''', ('notifications', pending, status, message))
            
            return status, message
            
        except Exception as e:
            return "ERROR", f"Ошибка проверки уведомлений: {str(e)}"
    
    @staticmethod
    def run_all_checks():
        logger.info("🔍 Запуск проверок мониторинга...")
        
        results = []
        results.append(Monitor.check_database_size())
        results.append(Monitor.check_bookings_count())
        results.append(Monitor.check_notifications())
        
        for check_type, (status, message) in zip(['db_size', 'bookings', 'notifications'], results):
            if status in ["WARNING", "CRITICAL", "ERROR"]:
                logger.warning(f"⚠️ Мониторинг {check_type}: {message}")
        
        return results

async def update_completed_bookings(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет прошедшие записи и начисляет пластинки за завершённые подтверждённые записи"""
    try:
        logger.info("🔄 Запуск проверки прошедших записей...")
        
        now = DateTimeUtils.now()
        awarded_count = 0
        rejected_count = 0
        
        with db.get_connection(timeout=60.0) as conn:
            cursor = conn.cursor()
            
            # ===== ПРОВЕРЯЕМ СУЩЕСТВОВАНИЕ КОЛОНКИ (ТОЛЬКО ОДИН РАЗ) =====
            cursor.execute("PRAGMA table_info(bookings)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'vinyls_awarded' not in columns:
                try:
                    cursor.execute('ALTER TABLE bookings ADD COLUMN vinyls_awarded INTEGER DEFAULT 0')
                    conn.commit()
                    logger.info("✅ Добавлена колонка vinyls_awarded")
                except Exception as e:
                    logger.error(f"❌ Ошибка добавления колонки: {e}")
            
            # ============================================================
            # ЧАСТЬ 1: НАЧИСЛЕНИЕ ПЛАСТИНОК
            # ============================================================
            cursor.execute('''
                SELECT id, date_str, time_slot, telegram_id, service, name, contact, price,
                       duration, status, is_12_hours, twelve_hours_type, is_mixing, 
                       is_track_creation, track_type, with_engineer, is_contractual,
                       is_admin_booking, start_hour, end_hour
                FROM bookings 
                WHERE status IN ('confirmed', 'подтвержден')
                AND vinyls_awarded = 0
                ORDER BY id ASC
            ''')
            
            bookings = cursor.fetchall()
            logger.info(f"🔍 Найдено подтвержденных записей для проверки: {len(bookings)}")
            
            for booking in bookings:
                (booking_id, date_str, time_slot, telegram_id, service, name, contact, price,
                 duration, status, is_12_hours, twelve_hours_type, is_mixing, 
                 is_track_creation, track_type, with_engineer, is_contractual,
                 is_admin_booking, start_hour, end_hour) = booking
                
                should_complete = False
                
                # 1. Сведение/мастеринг
                if is_mixing == 1:
                    should_complete = True
                    logger.info(f"✅ Запись #{booking_id} - сведение/мастеринг")
                
                # 2. Админская/договорная
                elif is_admin_booking == 1 or is_contractual == 1:
                    should_complete = True
                    logger.info(f"✅ Запись #{booking_id} - админская/договорная")
                
                # 3. Создание альбома
                elif is_track_creation == 1 and track_type and 'Альбом' in track_type:
                    should_complete = True
                    logger.info(f"✅ Запись #{booking_id} - создание альбома")
                
                # 4. Проверка по дате и времени
                elif date_str and 'Не указана' not in date_str and 'договорная' not in date_str.lower():
                    try:
                        clean_date = date_str
                        if '(' in clean_date:
                            clean_date = clean_date.split('(')[0].strip()
                        if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                            clean_date = clean_date[2:].strip()
                        
                        day, month, year = map(int, clean_date.split('.'))
                        
                        if time_slot and '-' in time_slot:
                            norm_time = DateTimeUtils.normalize_time_input(time_slot)
                            start_str, end_str = norm_time.split('-')
                            start_hour_calc = int(start_str)
                            end_hour_calc = int(end_str)
                            
                            # ===== ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ =====
                            logger.info(f"🔍 ОТЛАДКА: booking_id={booking_id}")
                            logger.info(f"🔍 ОТЛАДКА: start_hour_calc={start_hour_calc}, end_hour_calc={end_hour_calc}")
                            logger.info(f"🔍 ОТЛАДКА: year={year}, month={month}, day={day}")
                            
                            # ===== НОРМАЛИЗУЕМ ЧАСЫ =====
                            start_hour_calc = start_hour_calc if start_hour_calc != 24 else 0
                            end_hour_calc = end_hour_calc if end_hour_calc != 24 else 0
                            
                            logger.info(f"🔍 ОТЛАДКА: ПОСЛЕ НОРМАЛИЗАЦИИ: start={start_hour_calc}, end={end_hour_calc}")
                            
                            # ===== ОПРЕДЕЛЯЕМ, ПЕРЕСЕКАЕТ ЛИ СЛОТ ПОЛНОЧЬ =====
                            is_crossing = end_hour_calc <= start_hour_calc
                            
                            logger.info(f"🔍 Слот {start_hour_calc}-{end_hour_calc}, пересекает полночь: {is_crossing}")
                        else:
                            continue
                        
                        # ===== РАСЧЕТ ВРЕМЕНИ ОКОНЧАНИЯ =====
                        if is_12_hours == 1:
                            if twelve_hours_type and ('Ночь' in twelve_hours_type or 'ночь' in twelve_hours_type.lower()):
                                end_datetime = datetime(year, month, day, 9, 0, 0)
                                end_datetime = Config.TIMEZONE.localize(end_datetime)
                                end_datetime = end_datetime + timedelta(days=1)
                            else:
                                end_datetime = datetime(year, month, day, 21, 0, 0)
                                end_datetime = Config.TIMEZONE.localize(end_datetime)
                        else:
                            if is_crossing:
                                # Слот пересекает полночь - окончание на следующий день
                                logger.info(f"🔍 ОТЛАДКА: создаём end_datetime с hour={end_hour_calc}, day={day}+1")
                                end_datetime = datetime(year, month, day, end_hour_calc, 0, 0)
                                end_datetime = Config.TIMEZONE.localize(end_datetime)
                                end_datetime = end_datetime + timedelta(days=1)
                                logger.info(f"🔍 Кросс-ночной слот: окончание {end_datetime}")
                            else:
                                # Обычный дневной слот
                                if end_hour_calc == 24 or end_hour_calc == 0:
                                    end_datetime = datetime(year, month, day, 23, 59, 59)
                                    end_datetime = Config.TIMEZONE.localize(end_datetime)
                                    end_datetime = end_datetime + timedelta(seconds=1)
                                else:
                                    logger.info(f"🔍 ОТЛАДКА: создаём end_datetime с hour={end_hour_calc}")
                                    end_datetime = datetime(year, month, day, end_hour_calc, 0, 0)
                                    end_datetime = Config.TIMEZONE.localize(end_datetime)
                                logger.info(f"🔍 Обычный слот: окончание {end_datetime}")
                        
                        now_utc = now.astimezone(pytz.UTC)
                        end_utc = end_datetime.astimezone(pytz.UTC)
                        
                        if now_utc >= end_utc - timedelta(minutes=1):
                            should_complete = True
                            logger.info(f"✅ Запись #{booking_id} завершилась в {end_datetime}")
                            
                    except Exception as e:
                        logger.error(f"Ошибка парсинга даты для записи #{booking_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                if should_complete:
                    try:
                        cursor.execute('SELECT vinyls_awarded FROM bookings WHERE id = ?', (booking_id,))
                        result = cursor.fetchone()
                        already_awarded = result[0] == 1 if result else False
                        
                        if already_awarded:
                            logger.info(f"ℹ️ Пластинки уже начислены для записи #{booking_id}")
                            continue
                        
                        booking_data = {
                            'id': booking_id,
                            'telegram_id': telegram_id,
                            'status': 'confirmed',
                            'service': service,
                            'date_str': date_str,
                            'time_slot': time_slot,
                            'name': name,
                            'contact': contact,
                            'price': price,
                            'duration': duration,
                            'is_mixing': is_mixing,
                            'is_admin_booking': is_admin_booking,
                            'is_contractual': is_contractual,
                            'is_12_hours': is_12_hours,
                            'is_track_creation': is_track_creation,
                            'twelve_hours_type': twelve_hours_type
                        }
                        
                        vinyls_added, new_vinyls = await AchievementSystem.add_vinyls_for_booking(
                            str(telegram_id), context, booking_data
                        )
                        
                        if vinyls_added:
                            logger.info(f"✅ Пользователю {telegram_id} начислено +25 пластинок за запись #{booking_id}")
                            awarded_count += 1
                            
                            cursor.execute('UPDATE bookings SET status = "completed" WHERE id = ?', (booking_id,))
                            cursor.execute('DELETE FROM notifications WHERE booking_id = ?', (booking_id,))
                            
                            if date_str:
                                clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
                                if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                                    clean_date = clean_date[2:].strip()
                                MemoryCache.invalidate_date(clean_date)
                            
                            logger.info(f"✅ Запись #{booking_id} завершена")
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки записи #{booking_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
            
            # ============================================================
            # ЧАСТЬ 2: ОТКЛОНЕНИЕ ПРОСРОЧЕННЫХ PENDING
            # ============================================================
            cursor.execute('''
                SELECT id, date_str, time_slot, telegram_id, service, name, contact, price, 
                       duration, with_engineer, is_12_hours, is_mixing, is_track_creation,
                       is_contractual, is_admin_booking, start_hour, end_hour,
                       twelve_hours_type
                FROM bookings 
                WHERE status = 'pending'
                AND is_admin_booking = 0
                AND is_contractual = 0
                AND service NOT LIKE '%Админ%'
                AND service NOT LIKE '%админ%'
                ORDER BY id ASC
            ''')
            
            expired_pending = cursor.fetchall()
            logger.info(f"🔍 Найдено pending записей для проверки: {len(expired_pending)}")
            
            for booking in expired_pending:
                (booking_id, date_str, time_slot, telegram_id, service, name, contact, price, 
                 duration, with_engineer, is_12_hours, is_mixing, is_track_creation,
                 is_contractual, is_admin_booking, start_hour, end_hour,
                 twelve_hours_type) = booking
                
                is_expired = False
                
                if date_str and 'Не указана' not in date_str and 'договорная' not in date_str.lower():
                    try:
                        clean_date = date_str
                        if '(' in clean_date:
                            clean_date = clean_date.split('(')[0].strip()
                        if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                            clean_date = clean_date[2:].strip()
                        
                        day, month, year = map(int, clean_date.split('.'))
                        
                        if time_slot and '-' in time_slot:
                            norm_time = DateTimeUtils.normalize_time_input(time_slot)
                            start_str = norm_time.split('-')[0].strip()
                            start_hour_calc = int(start_str)
                            # Нормализуем для datetime
                            if start_hour_calc == 24:
                                start_hour_calc = 0
                        else:
                            start_hour_calc = 0
                        
                        # ===== ИСПРАВЛЕНО: ПРАВИЛЬНЫЙ РАСЧЕТ ДЛЯ НОЧНЫХ СЛОТОВ =====
                        booking_start_datetime = datetime(year, month, day, start_hour_calc, 0, 0)
                        booking_start_datetime = Config.TIMEZONE.localize(booking_start_datetime)
                        
                        # Если время начала после 20:00 и end_hour < start_hour - это ночной слот
                        # Например: 22-2, 21-9, 23-0
                        if end_hour and end_hour < start_hour_calc:
                            booking_start_datetime = booking_start_datetime + timedelta(days=1)
                            logger.info(f"🔍 Ночной слот для pending: начало {booking_start_datetime}")
                        
                        now_utc = now.astimezone(pytz.UTC)
                        start_utc = booking_start_datetime.astimezone(pytz.UTC)
                        
                        if now_utc > start_utc:
                            is_expired = True
                            logger.info(f"⏰ Запись #{booking_id} просрочена")
                            
                    except Exception as e:
                        logger.error(f"Ошибка проверки pending записи #{booking_id}: {e}")
                        continue
                
                if is_expired:
                    try:
                        cursor.execute('SELECT status FROM bookings WHERE id = ?', (booking_id,))
                        check = cursor.fetchone()
                        if not check or check[0] != 'pending':
                            continue
                        
                        cursor.execute('UPDATE bookings SET status = "rejected" WHERE id = ?', (booking_id,))
                        cursor.execute('DELETE FROM notifications WHERE booking_id = ?', (booking_id,))
                        
                        if date_str:
                            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
                            if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                                clean_date = clean_date[2:].strip()
                            MemoryCache.invalidate_date(clean_date)
                        
                        rejected_count += 1
                        logger.info(f"✅ Запись #{booking_id} автоматически отклонена")
                        
                        try:
                            display_time = time_slot
                            if time_slot and '-' in time_slot:
                                display_time = DateTimeUtils.format_time_for_display(time_slot)
                            
                            message_text = (
                                f"*❌ Ваша заявка автоматически отклонена*\n\n"
                                f"*⏰ Запись не была подтверждена до начала*\n\n"
                                f"👤 Имя: {name}\n"
                                f"📱 Контакт: {contact}\n"
                                f"🎧 Услуга: {service}\n"
                                f"📅 Дата: {clean_date}\n"
                                f"⏰ Время: {display_time}\n\n"
                                f"*📞 Свяжитесь с администратором @mothman32*"
                            )
                            
                            await context.bot.send_message(
                                chat_id=int(telegram_id),
                                text=message_text,
                                parse_mode="Markdown"
                            )
                            logger.info(f"✅ Уведомление об отклонении отправлено {telegram_id}")
                        except Exception as e:
                            logger.error(f"❌ Не удалось отправить уведомление: {e}")
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка отклонения записи #{booking_id}: {e}")
                        continue
            
            conn.commit()
            
        logger.info(f"✅ Проверка завершена! Начислено: {awarded_count}, отклонено: {rejected_count}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в update_completed_bookings: {e}")
        import traceback
        traceback.print_exc()

async def cleanup_old_bookings(context: ContextTypes.DEFAULT_TYPE):
    """Очистка старых записей - НЕ УДАЛЯЕМ completed"""
    try:
        logger.info("🧹 Запуск очистки старых записей...")
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM bookings 
                WHERE status IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
                AND datetime(timestamp) < datetime('now', '-90 days')
            ''')
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"✅ Удалено {deleted} старых записей")
    except Exception as e:
        logger.error(f"❌ Ошибка очистки старых записей: {e}")

class Config:
    TOKEN = BOT_TOKEN
    ADMIN_IDS = ADMIN_IDS
    TIMEZONE = pytz.timezone('Europe/Moscow')
    MAX_BOOKING_DAYS = 27
    MAX_BOOKING_HOURS = 6
    NIGHT_HOURS = (0, 6)
    NIGHT_SURCHARGE_AMOUNT = 200
    USER_LIMITS = {
        'with_date': 2,
        'without_date': 3
    }
    TIME_PERIODS = [
        {"name": "Ночь", "start": 0, "end": 6, "rules": "night", "surcharge": True},
        {"name": "Утро", "start": 6, "end": 12, "rules": "day", "surcharge": False},
        {"name": "День", "start": 12, "end": 18, "rules": "day", "surcharge": False},
        {"name": "Вевер", "start": 18, "end": 24, "rules": "day", "surcharge": False}
    ]
    MIN_BOOKING_ADVANCE = {
        'rental': 72,
        'track_creation': 72,
        'with_engineer': 48,
        'without_engineer': 24,  # ← БЫЛО 24
        'default': 24
    }


    DAY_START = 9
    DAY_END = 21
    PRICES = {
        'vocal_engineer_under3': 1500,
        'vocal_engineer_over3': 1300,
        'vocal_engineer_over6': 1100,
        'vocal_engineer_night_under3': 1700,
        'vocal_engineer_night_over3': 1500,
        'vocal_engineer_night_over6': 1400,
        'vocal_no_engineer_under3': 1400,
        'vocal_no_engineer_over3': 1200,
        'vocal_no_engineer_over6': 1000,
        'mixing_track': 2500,
        '12_hours_rent_day': 7000,
        '12_hours_rent_night': 6500,
        'default': 1500,
        'track_creation_single': 9000
    }
    
    # В классе Config добавь или обнови:
    NOTIFICATION_INTERVALS = {
        'vocal_with_engineer': [48, 24, 12, 6],  # 48ч, 24ч, 12ч, 6ч
        'vocal_without_engineer': [24, 12, 6, 3],  # 24ч, 12ч, 6ч, 3ч
        'instruments_with_engineer': [48, 24, 12, 6],
        'instruments_without_engineer': [24, 12, 6, 3],
        'rental': [48, 24, 12],  # для аренды
        'track_creation': [48, 24, 12],  # для создания трека
        'mixing': [],  # для сведения - нет уведомлений
        'default': [24, 12, 3]
    }
    
    TRACK_CREATION = {
        'min_advance_hours': 72,
        'min_duration': 4,
        'max_duration': 4,
    }
    MAX_NAME_LENGTH = 50
    MAX_CONTACT_LENGTH = 50
    MAX_TIME_STR_LENGTH = 20
    RATE_LIMIT = 60
    RATE_BLOCK_TIME = 300
    
    # ===== ФИНАНСОВЫЕ КОНСТАНТЫ =====
    RENT_COST = 45000  # Аренда в месяц
    ENGINEER_BASE_RATE = 500  # Базовая ставка звукорежиссера в час
    ENGINEER_NIGHT_SURCHARGE = 200  # Ночная надбавка звукорежиссеру в час
    
    @staticmethod
    def get_period_by_hour(hour: int):
        for period in Config.TIME_PERIODS:
            if period["start"] <= hour < period["end"]:
                return period
        return Config.TIME_PERIODS[-1]
    
    @staticmethod
    def validate_string_length(text: str, max_length: int, field_name: str = "поле"):
        if not text or len(text.strip()) == 0:
            return False, f"*❌ {field_name} не может быть пустым!*"
        
        if len(text) > max_length:
            # Определяем правильное окончание для поля
            if field_name == "имя":
                return False, f"*❌ Максимально 50 символов, слишком длинное имя! Введите имя длиной от 2 до 50 символов!*"
            elif field_name == "контакт":
                return False, f"*❌ Максимально 50 символов, слишком длинный контакт! Введите контакт длиной от 2 до 50 символов!*"
            else:
                return False, f"*❌ Максимально {max_length} символов, слишком длинное {field_name}!*"
        
        if len(text.strip()) < 2 and field_name == "имя":
            return False, "*❌ Минимально 2 символа, слишком короткое имя! Введите имя длиной от 2 до 50 символов!*"
        
        if len(text.strip()) < 2 and field_name == "контакт":
            return False, f"*❌ Минимально 2 символа, слишком короткий контакт! Введите контакт длиной от 2 до {Config.MAX_CONTACT_LENGTH} символов!*"
        
        return True, ""

class SecurityUtils:
    @staticmethod
    def safe_markdown_text(text: str) -> str:
        if not text:
            return ""
        
        text = str(text)
        
        text = text.replace('\\', '\\\\')
        
        critical_chars = ['_', '*', '[', ']', '`']
        
        for char in critical_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    @staticmethod
    def validate_time_format(time_str, is_track_creation=False) -> Tuple[bool, str]:
        try:
            if len(time_str) > Config.MAX_TIME_STR_LENGTH:
                return False, f"❌ *Слишком длинный формат времени! Максимально {Config.MAX_TIME_STR_LENGTH} символов.*"
            
            if '-' not in time_str:
                return False, "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*"
            
            parts = time_str.split('-')
            if len(parts) != 2:
                return False, "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*"
            
            start_str, end_str = parts[0].strip(), parts[1].strip()
            
            if not start_str or not end_str:
                return False, "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*"
            
            try:
                start_hour = int(start_str)
                end_hour = int(end_str)
            except ValueError:
                return False, "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*"
            
            if start_hour == 24:
                start_hour = 0
            if end_hour == 24:
                end_hour = 0
            
            if not (0 <= start_hour <= 23):
                return False, "❌ *Начальный час должен быть от 0 до 23 (или 24 для полночи)*"
            
            if not (0 <= end_hour <= 23):
                return False, "❌ *Конечный час должен быть от 0 до 23 (или 24 для полночи)*"
            
            if start_hour == 0 and end_hour == 0 and not is_track_creation:
                return True, ""
            
            if start_hour == end_hour and not is_track_creation:
                return False, "❌ *Время должно быть минимально 1 час! У вас: 0 часов*"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Ошибка валидации времени: {e}")
            return False, "❌ *Произошла ошибка при обработке времени*"

def get_user_display_name(user_data):
    """
    Возвращает имя пользователя для отображения в приоритете:
    1. username (если есть)
    2. unique_id (если нет username)
    3. telegram_id (последние 4 цифры, если ничего нет)
    """
    username = user_data.get('username')
    unique_id = user_data.get('unique_id')
    telegram_id = user_data.get('telegram_id')
    
    if username and username.strip():
        return f"@{username}"
    elif unique_id and unique_id.strip():
        return unique_id
    elif telegram_id:
        return f"ID: ...{str(telegram_id)[-4:]}"
    else:
        return "Пользователь"

class DateTimeUtils:
    @staticmethod
    def now():
        return datetime.now(Config.TIMEZONE)
    
    @staticmethod
    def normalize_time_input(time_str):
        if not time_str or time_str == 'Не указано' or '-' not in time_str:
            return time_str
        
        logger.info(f"Нормализация времени: Входная строка: '{time_str}'")
        
        time_str = time_str.replace(' ', '')
        
        parts = time_str.split('-')
        if len(parts) != 2:
            return time_str
        
        start_str, end_str = parts[0].strip(), parts[1].strip()
        
        try:
            start_hour = int(start_str)
            end_hour = int(end_str)
            
            # ===== НОРМАЛИЗУЕМ 24 -> 0 ДЛЯ ОБОИХ ЧАСОВ =====
            if start_hour == 24:
                start_hour = 0
            if end_hour == 24:
                end_hour = 0
            
            result = f"{start_hour}-{end_hour}"
            logger.info(f"Нормализация времени: Результат: '{result}'")
            return result
            
        except ValueError:
            logger.error(f"Ошибка преобразования времени: {time_str}")
            return time_str

    @staticmethod
    def format_time_for_display(time_str):
        if not time_str or '-' not in time_str:
            return time_str
        
        parts = time_str.split('-')
        if len(parts) != 2:
            return time_str
        
        start_str, end_str = parts[0].strip(), parts[1].strip()
        
        try:
            start_hour = int(start_str)
            end_hour = int(end_str)
            
            # 24 → 00
            if start_hour == 24:
                start_hour = 0
            if end_hour == 24:
                end_hour = 0
            
            # Форматируем с ведущим нулём (01, 02, 03...)
            display_start = f"{start_hour:02d}"
            display_end = f"{end_hour:02d}"
            
            return f"{display_start}-{display_end}"
            
        except ValueError:
            return time_str
    
    @staticmethod
    def get_future_dates(count=27):
        try:
            cached = MemoryCache.get_future_dates(ttl=300)
            if cached:
                return cached
            
            today = DateTimeUtils.now()
            dates = []
            
            for i in range(count + 1):
                day_date = today + timedelta(days=i)
                date_str = day_date.strftime("%d.%m.%Y")
                day_name = WEEKDAYS_RU[day_date.weekday()]
                dates.append(f"{date_str} ({day_name})")
            
            MemoryCache.set_future_dates(dates)
            return dates
            
        except Exception as e:
            today = datetime.now(Config.TIMEZONE).date()
            return [f"{(today + timedelta(days=i)).strftime('%d.%m.%Y')}" for i in range(count + 1)]

    @staticmethod
    def parse_date_input(user_input):
        try:
            if len(user_input) > 50:
                return None, "❌ Слишком длинная дата!"
            
            text = user_input.strip()
            
            if '(' in text:
                date_part = text.split('(')[0].strip()
            else:
                date_part = text.strip()
            
            if '.' not in date_part:
                return None, "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*"
            
            parts = date_part.split('.')
            if len(parts) != 3:
                return None, "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*"
            
            try:
                day, month, year = map(int, parts)
            except ValueError:
                return None, "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*"
            
            if not (1 <= day <= 31):
                return None, "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*"
            if not (1 <= month <= 12):
                return None, "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*"
            if not (2024 <= year <= 2030):
                return None, "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*"
            
            naive_datetime = datetime(year, month, day)
            user_datetime = Config.TIMEZONE.localize(naive_datetime)
            
            return user_datetime, ""
            
        except Exception as e:
            logger.error(f"Ошибка парсинга даты: {e}")
            return None, "❌ Ошибка обработки даты"

    @staticmethod
    def get_booking_datetime(date_str, time_str):
        try:
            normalized_time = DateTimeUtils.normalize_time_input(time_str)
            
            date_part = date_str.split('(')[0].strip() if '(' in date_str else date_str
            
            is_valid, error_msg = SecurityUtils.validate_time_format(normalized_time, False)
            if not is_valid:
                return None
            
            start_hour_str = normalized_time.split('-')[0].strip()
            start_hour = int(start_hour_str)
            
            day, month, year = map(int, date_part.split('.'))
            
            naive_datetime = datetime(year, month, day, start_hour, 0, 0, 0)
            user_datetime = Config.TIMEZONE.localize(naive_datetime)
            
            return user_datetime
        except:
            return None

    @staticmethod
    def calculate_duration(start_hour, end_hour):
        try:
            start_hour = int(start_hour)
            end_hour = int(end_hour)
            
            logger.info(f"🔍 calculate_duration: start={start_hour}, end={end_hour}")
            
            if end_hour == 0 or end_hour == 24:
                if start_hour == 0 or start_hour == 24:
                    return 0
                
                duration = 24 - start_hour
                logger.info(f"🔍 Продолжительность (ночная): {duration} часов")
                return duration
            
            if end_hour > start_hour:
                duration = end_hour - start_hour
            else:
                duration = (24 - start_hour) + end_hour
            
            logger.info(f"🔍 Продолжительность: {duration} часов")
            return duration
        except Exception as e:
            logger.error(f"Ошибка расчета длительности: {e}")
            return 0

    @staticmethod
    def is_day_time(start_hour):
        period = Config.get_period_by_hour(int(start_hour))
        return period["rules"] == "day"

    @staticmethod
    def can_book_in_advance(start_datetime, start_hour, with_engineer, is_12_hours=False, is_track_creation=False, booking_start_time=None):
        reference_time = DateTimeUtils.now()
        
        if not start_datetime:
            return False, -1
        
        if start_datetime <= reference_time:
            return False, -1
        
        time_until_booking = start_datetime - reference_time
        hours_until_booking = time_until_booking.total_seconds() / 3600
        
        if is_12_hours:
            min_hours = Config.MIN_BOOKING_ADVANCE['rental']
        elif is_track_creation:
            min_hours = Config.MIN_BOOKING_ADVANCE['track_creation']
        elif with_engineer:
            min_hours = Config.MIN_BOOKING_ADVANCE['with_engineer']  # 48
        else:
            min_hours = Config.MIN_BOOKING_ADVANCE['without_engineer']  # 24
        
        logger.info(f"🔍 can_book_in_advance:")
        logger.info(f"   До начала: {hours_until_booking:.1f} часов")
        logger.info(f"   Требуется мин.: {min_hours} часов")
        
        if hours_until_booking >= min_hours:
            return True, min_hours
        else:
            return False, min_hours

    @staticmethod
    def format_time_until(delta_timedelta):
        total_seconds = delta_timedelta.total_seconds()
        
        if total_seconds <= 0:
            return "время уже прошло"
        
        days = int(total_seconds // 86400)
        hours = int((total_seconds % 86400) // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        
        parts = []
        
        if days > 0:
            if days == 1:
                parts.append(f"{days} день")
            elif 2 <= days <= 4:
                parts.append(f"{days} дня")
            else:
                parts.append(f"{days} дней")
        
        if hours > 0:
            if hours == 1:
                parts.append(f"{hours} час")
            elif 2 <= hours <= 4:
                parts.append(f"{hours} часа")
            else:
                parts.append(f"{hours} часов")
        
        if minutes > 0:
            if minutes == 1:
                parts.append(f"{minutes} минута")
            elif 2 <= minutes <= 4:
                parts.append(f"{minutes} минуты")
            else:
                parts.append(f"{minutes} минут")
        
        if not parts and seconds > 0:
            if seconds == 1:
                return f"{seconds} секунда"
            elif 2 <= seconds <= 4:
                return f"{seconds} секунды"
            else:
                return f"{seconds} секунд"
        
        if not parts:
            return "меньше минуты"
        
        return " ".join(parts)

    @staticmethod
    def is_valid_booking_time(time_str, with_engineer, is_12_hours=False, is_track_creation=False):
        try:
            if time_str.endswith('-24'):
                time_str = time_str.replace('-24', '-0')
            
            is_valid, error_msg = SecurityUtils.validate_time_format(time_str, is_track_creation)
            if not is_valid:
                return False, error_msg
            
            if "-" not in time_str:
                return False, "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*"
            
            start_hour_str, end_hour_str = time_str.split("-")
            
            if start_hour_str == '24':
                start_hour_str = '0'
            if end_hour_str == '24':
                end_hour_str = '0'
            
            start_hour = int(start_hour_str.strip())
            end_hour = int(end_hour_str.strip())
            
            if end_hour > start_hour:
                duration = end_hour - start_hour
            elif end_hour < start_hour:
                duration = (24 - start_hour) + end_hour
            else:
                duration = 0
            
            if is_track_creation:
                if duration == 0:
                    return False, f"*❌ Для создания трека требуется ровно 4 часа! Выберите длительность 4 часа!*"
                if duration != 4:
                    return False, f"*❌ Для создания трека требуется ровно 4 часа! Выберите длительность 4 часа!*"
            else:
                if duration == 0:
                    return False, "*❌ Минимальное время записи — 1 час! Выберите длительность от 1 до 6 часов!*"
                if duration > 6:
                    return False, f"*❌ Максимальное время записи — 6 часов! Выберите длительность от 1 до 6 часов!*"
                if duration < 1:
                    return False, f"❌ *Минимально 1 час! У вас: {duration} часов*"
            
            if is_12_hours:
                if duration != 12:
                    return False, "❌ *12-часовая аренда должна быть ровно 12 часов*"
                
                if (start_hour == 9 and (end_hour == 21 or end_hour == 0)):
                    return True, 12
                elif (start_hour == 21 and (end_hour == 9 or end_hour == 0)):
                    return True, 12
                else:
                    return False, "❌ *Для 12-часовой аренды используйте: 9-21 (день) или 21-9 (ночь)*"
            else:
                return True, duration
                    
        except ValueError:
            return False, "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*"
        except Exception as e:
            logger.error(f"Ошибка валидации времени бронирования: {e}")
            return False, "❌ *Произошла ошибка обработки времени*"

    @staticmethod
    def get_booking_period_info(start_hour):
        period = Config.get_period_by_hour(int(start_hour))
        return {
            "name": period["name"],
            "range": f"{period['start']:02d}:00-{period['end']:02d}:00",
            "rules_type": period["rules"],
            "surcharge": period["surcharge"],
            "rules_text": "правилам для дня" if period["rules"] == "day" else "правилам для ночи"
        }

    @staticmethod
    def is_cross_day_booking(time_str):
        try:
            if not time_str or '-' not in time_str:
                return False
            
            start_str, end_str = time_str.split('-')
            start_hour = int(start_str.strip())
            end_hour = int(end_str.strip())
            
            return end_hour <= start_hour
        except:
            return False

    @staticmethod
    def get_affected_dates(date_str, time_str):
        try:
            if not DateTimeUtils.is_cross_day_booking(time_str):
                return [date_str]
            
            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
            day, month, year = map(int, clean_date.split('.'))
            
            next_day = datetime(year, month, day) + timedelta(days=1)
            next_day_str = next_day.strftime("%d.%m.%Y")
            
            return [date_str, next_day_str]
        except:
            return [date_str]
   
    @staticmethod
    def get_hours_until_booking(date_str: str, time_slot: str) -> float:
        """Возвращает количество часов до начала записи, или -1 если ошибка"""
        try:
            if not date_str or not time_slot:
                return -1
            
            # Очищаем дату
            clean_date = date_str
            if '(' in clean_date:
                clean_date = clean_date.split('(')[0].strip()
            if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                clean_date = clean_date[2:].strip()
            
            if 'Не указана' in clean_date or 'договорная' in clean_date.lower():
                return -1
            
            # Очищаем время
            clean_time = time_slot
            if clean_time == 'Не указано' or clean_time == 'Не указано (договорная)':
                return -1
            
            # Нормализуем время
            if '-' in clean_time:
                clean_time = DateTimeUtils.normalize_time_input(clean_time)
                start_hour_str = clean_time.split('-')[0].strip()
                start_hour = int(start_hour_str)
            else:
                return -1
            
            # Парсим дату
            day, month, year = map(int, clean_date.split('.'))
            
            # Создаем datetime начала записи
            start_datetime = datetime(year, month, day, start_hour, 0, 0)
            start_datetime = Config.TIMEZONE.localize(start_datetime)
            
            now = DateTimeUtils.now()
            
            if start_datetime <= now:
                return 0
            
            time_until = start_datetime - now
            hours_until = time_until.total_seconds() / 3600
            
            return hours_until
            
        except Exception as e:
            logger.error(f"Ошибка в get_hours_until_booking: {e}")
            return -1


    @staticmethod
    def get_min_advance_hours_for_service(with_engineer=False, is_12_hours=False, is_track_creation=False):
        if is_12_hours:
            return Config.MIN_BOOKING_ADVANCE['rental']
        elif is_track_creation:
            return Config.MIN_BOOKING_ADVANCE['track_creation']
        elif with_engineer:
            return Config.MIN_BOOKING_ADVANCE['with_engineer']
        else:
            return Config.MIN_BOOKING_ADVANCE['without_engineer']
    
    @staticmethod
    def check_date_availability(date_str, start_hour, with_engineer=False, 
                                is_12_hours=False, is_track_creation=False, booking_start_time=None):
        try:
            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
            
            day, month, year = map(int, clean_date.split('.'))
            
            if is_12_hours:
                if "Ночь" in str(booking_start_time) or "night" in str(booking_start_time).lower():
                    start_hour = 21
                else:
                    start_hour = 9
            
            naive_datetime = datetime(year, month, day, start_hour, 0, 0, 0)
            booking_datetime = Config.TIMEZONE.localize(naive_datetime)
            
            now = DateTimeUtils.now()
            
            if booking_datetime <= now:
                return False, 0, 0, 0
            
            time_until_booking = booking_datetime - now
            
            min_hours = DateTimeUtils.get_min_advance_hours_for_service(
                with_engineer, is_12_hours, is_track_creation
            )
            
            total_seconds = time_until_booking.total_seconds()
            hours_until = total_seconds / 3600
            
            hours_until_int = int(total_seconds // 3600)
            minutes_until_int = int((total_seconds % 3600) // 60)
            
            logger.info(f"🔍 Проверка доступности даты:")
            logger.info(f"   Дата: {clean_date}, час: {start_hour}")
            logger.info(f"   Время бронирования: {booking_datetime}")
            logger.info(f"   Сейчас: {now}")
            logger.info(f"   До начала: {hours_until:.1f} часов ({hours_until_int}ч {minutes_until_int}мин)")
            logger.info(f"   Требуется мин.: {min_hours} часов")
            logger.info(f"   is_12_hours: {is_12_hours}, booking_start_time: {booking_start_time}")
            
            if hours_until < min_hours:
                return False, min_hours, hours_until_int, minutes_until_int
            
            return True, min_hours, 0, 0
            
        except Exception as e:
            logger.error(f"Ошибка проверки доступности даты: {e}")
            import traceback
            traceback.print_exc()
            return True, 0, 0, 0
        
    @staticmethod
    def can_book_12_hours_rental(start_datetime, start_hour):
        if not start_datetime:
            return False, 0
        
        reference_time = DateTimeUtils.now()
        
        if start_datetime <= reference_time:
            return False, -1
        
        time_until_booking = start_datetime - reference_time
        hours_until_booking = time_until_booking.total_seconds() / 3600
        
        min_hours = 72
        
        logger.info(f"🔍 can_book_12_hours_rental:")
        logger.info(f"   Время бронирования: {start_datetime}")
        logger.info(f"   Сейчас: {reference_time}")
        logger.info(f"   До начала: {hours_until_booking:.1f} часов")
        logger.info(f"   Требуется мин.: {min_hours} часов")
        
        return hours_until_booking >= min_hours, hours_until_booking
    
    @staticmethod
    def format_time_left(hours, minutes):
        if hours > 0 and minutes > 0:
            return f"{hours} часов {minutes} минут"
        elif hours > 0:
            return f"{hours} часов"
        elif minutes > 0:
            return f"{minutes} минут"
        else:
            return "менее минуты"

def get_notification_service_type(service: str, with_engineer: bool = False, 
                                 is_12_hours: bool = False, 
                                 is_track_creation: bool = False,
                                 is_mixing: bool = False) -> str:
    
    if is_mixing:
        return 'mixing'
    
    if is_12_hours:
        return 'rental'
    
    if is_track_creation:
        service_lower = service.lower() if service else ""
        if 'альбом' in service_lower or 'договорн' in service_lower:
            return 'mixing'
        return 'track_creation'
    
    service_lower = service.lower() if service else ""
    
    if 'вокал' in service_lower:
        if with_engineer:
            return 'vocal_with_engineer'
        else:
            return 'vocal_without_engineer'
    
    elif 'инструмент' in service_lower:
        if with_engineer:
            return 'instruments_with_engineer'
        else:
            return 'instruments_without_engineer'
    
    return 'default'

class PriceCalculator:
    @staticmethod
    def get_night_hours_count(start_hour, end_hour, duration):
        """Подсчитывает количество ночных часов (00:00-06:00)"""
        if start_hour is None or end_hour is None:
            return 0
            
        night_hours = 0
        
        # Нормализуем часы
        start = start_hour % 24
        end = end_hour % 24 if end_hour != 24 else 0
        
        if end <= start:
            # Ночной слот, пересекающий полночь
            for hour in range(start, 24):
                if 0 <= hour < 6:
                    night_hours += 1
            for hour in range(0, end):
                if 0 <= hour < 6:
                    night_hours += 1
        else:
            # Дневной слот
            for hour in range(start, end):
                if 0 <= hour < 6:
                    night_hours += 1
        
        return night_hours

    @staticmethod
    def calculate_base_price(duration, with_engineer):
        """Рассчитывает базовую цену без ночных надбавок"""
        if with_engineer:
            if duration >= 6:
                return duration * Config.PRICES['vocal_engineer_over6']
            elif duration >= 3:
                return duration * Config.PRICES['vocal_engineer_over3']
            else:
                return duration * Config.PRICES['vocal_engineer_under3']
        else:
            if duration >= 6:
                return duration * Config.PRICES['vocal_no_engineer_over6']
            elif duration >= 3:
                return duration * Config.PRICES['vocal_no_engineer_over3']
            else:
                return duration * Config.PRICES['vocal_no_engineer_under3']

    @staticmethod
    def get_price_per_hour(with_engineer: bool, duration: int = None) -> int:
        """Возвращает ставку за час в зависимости от длительности"""
        if with_engineer:
            if duration is not None and duration >= 6:
                return Config.PRICES['vocal_engineer_over6']
            elif duration is not None and duration >= 3:
                return Config.PRICES['vocal_engineer_over3']
            else:
                return Config.PRICES['vocal_engineer_under3']
        else:
            if duration is not None and duration >= 6:
                return Config.PRICES['vocal_no_engineer_over6']
            elif duration is not None and duration >= 3:
                return Config.PRICES['vocal_no_engineer_over3']
            else:
                return Config.PRICES['vocal_no_engineer_under3']

    @staticmethod
    def calculate(service, duration, is_mixing=False, mixing_type=None, 
                is_12_hours=False, is_track_creation=False, track_type=None,
                twelve_hours_type=None, start_hour=None, end_hour=None, 
                with_engineer=False, user_id=None, consume_coupon=False):
        """
        Рассчитывает цену в ПРАВИЛЬНОМ порядке:
        1. Базовая цена (часы × ставка)
        2. Ночная надбавка (для работы с инженером ИЛИ для создания трека!)
        3. Бесплатные часы/услуга (вычитаются из ОБЩЕЙ суммы)
        4. Процентная скидка по уровню
        5. Процентная скидка по промокоду
        """
        
        logger.info(f"💰 РАСЧЕТ ЦЕНЫ: service={service}, duration={duration}, with_engineer={with_engineer}, user_id={user_id}, is_track_creation={is_track_creation}, start_hour={start_hour}, end_hour={end_hour}")
        
        # ===== 1. БАЗОВАЯ ЦЕНА =====
        if duration == 0 and not is_mixing and not is_track_creation:
            base_price = 0
            
        elif is_12_hours:
            if twelve_hours_type and ('Ночь' in twelve_hours_type or 'ночь' in twelve_hours_type.lower()):
                base_price = Config.PRICES['12_hours_rent_night']
            else:
                base_price = Config.PRICES['12_hours_rent_day']
            logger.info(f"💰 АРЕНДА: base_price={base_price}")
            
            level_discount_percent = 0
            level_coupon_id = None
            promo_discount_percent = 0
            promo_code_used = None
            free_service_applied = False
            
            if user_id:
                # 1. ПРОВЕРЯЕМ КУПОН УРОВНЯ
                try:
                    best_coupon = CouponManager.get_best_coupon(str(user_id))
                    if best_coupon:
                        level_discount_percent = best_coupon['discount']
                        level_coupon_id = best_coupon['id']
                        logger.info(f"💰 Найден купон для аренды: скидка {level_discount_percent}%")
                        
                        if consume_coupon and not best_coupon.get('is_permanent', False):
                            success, msg, discount_used = CouponManager.use_coupon(str(user_id), level_coupon_id)
                            if success:
                                logger.info(f"✅ Купон использован для аренды")
                            else:
                                logger.warning(f"⚠️ Не удалось использовать купон для аренды: {msg}")
                                level_discount_percent = 0
                                level_coupon_id = None
                except Exception as e:
                    logger.error(f"Ошибка при работе с купоном для аренды: {e}")
                
                # 2. ПРОВЕРЯЕМ ПРОМОКОД
                try:
                    promo = PromoCodeManager.get_user_active_promo(str(user_id))
                    if promo:
                        service_lower = service.lower() if service else ""
                        target_service = promo.get('target_service')
                        
                        promo_applies = False
                        
                        if promo['discount_type'] == PromoCodeManager.TYPE_PERCENT_ALL:
                            promo_applies = True
                        elif promo['discount_type'] == PromoCodeManager.TYPE_PERCENT_SERVICE:
                            if target_service == "аренда" and ("аренд" in service_lower or "12-час" in service_lower):
                                promo_applies = True
                        elif promo['discount_type'] == PromoCodeManager.TYPE_FREE_SERVICE:
                            if target_service == "аренда" and ("аренд" in service_lower or "12-час" in service_lower):
                                promo_applies = True
                                free_service_applied = True
                                promo_code_used = promo['code']
                                logger.info(f"💰 Бесплатная аренда, цена = 0")
                        
                        if promo_applies:
                            if promo['discount_type'] == PromoCodeManager.TYPE_FREE_SERVICE:
                                current_price = 0
                                free_service_applied = True
                                promo_code_used = promo['code']
                                logger.info(f"💰 Бесплатная аренда, цена = 0")
                            elif promo['discount_type'] in [PromoCodeManager.TYPE_PERCENT_ALL, PromoCodeManager.TYPE_PERCENT_SERVICE]:
                                promo_discount_percent = promo['discount_value']
                                promo_code_used = promo['code']
                                logger.info(f"💰 Промокод для аренды: +{promo_discount_percent}%")
                except Exception as e:
                    logger.error(f"Ошибка при работе с промокодом для аренды: {e}")
            
            # 3. ПРИМЕНЯЕМ СКИДКИ
            if free_service_applied:
                current_price = 0
                final_price = 0
            else:
                current_price = base_price
                total_percent_discount = level_discount_percent + promo_discount_percent
                
                if total_percent_discount > 0:
                    current_price = current_price * (100 - min(total_percent_discount, 100)) / 100
                    logger.info(f"💰 Аренда со скидкой: {current_price} (скидка {total_percent_discount}%)")
                
                final_price = int(current_price) if current_price > 0 else 0
            
            return {
                'base_price': base_price,
                'final_price': final_price,
                'level_discount_percent': level_discount_percent,
                'level_coupon_id': level_coupon_id,
                'promo_discount_percent': promo_discount_percent,
                'promo_code_used': promo_code_used,
                'is_contractual': False,
                'free_hours_applied': 0,
                'night_surcharge': 0,
                'free_service_applied': free_service_applied
            }

        elif is_mixing:
            if mixing_type and "Альбом" in mixing_type:
                return {
                    'base_price': 0,
                    'final_price': "Договорная",
                    'level_discount_percent': 0,
                    'level_coupon_id': None,
                    'promo_discount_percent': 0,
                    'promo_code_used': None,
                    'is_contractual': True,
                    'free_hours_applied': 0,
                    'free_service_applied': False
                }
            base_price = Config.PRICES['mixing_track']
            if duration == 0:
                duration = 1
            logger.info(f"💰 СВЕДЕНИЕ: base_price={base_price}")

        elif is_track_creation:
            if track_type and "Альбом" in track_type:
                return {
                    'base_price': 0,
                    'final_price': "Договорная",
                    'level_discount_percent': 0,
                    'level_coupon_id': None,
                    'promo_discount_percent': 0,
                    'promo_code_used': None,
                    'is_contractual': True,
                    'free_hours_applied': 0,
                    'free_service_applied': False
                }
            base_price = Config.PRICES['track_creation_single']
            logger.info(f"💰 СОЗДАНИЕ ТРЕКА: base_price={base_price}")

        elif with_engineer:
            base_price = PriceCalculator.calculate_base_price(duration, with_engineer)
            logger.info(f"💰 Базовая цена (с инженером): {base_price}₽")
        else:
            base_price = PriceCalculator.calculate_base_price(duration, with_engineer)
            logger.info(f"💰 Базовая цена (без инженера): {base_price}₽")
        
        # Если договорная цена
        if isinstance(base_price, str) and base_price == "Договорная":
            return {
                'base_price': 0,
                'final_price': "Договорная",
                'level_discount_percent': 0,
                'level_coupon_id': None,
                'promo_discount_percent': 0,
                'promo_code_used': None,
                'is_contractual': True,
                'free_hours_applied': 0,
                'free_service_applied': False
            }
        
        # ===== 2. НОЧНАЯ НАДБАВКА =====
        night_surcharge = 0
        
        # Для создания трека - применяем ночную надбавку!
        if is_track_creation and start_hour is not None and end_hour is not None:
            night_hours = PriceCalculator.get_night_hours_count(start_hour, end_hour, duration)
            night_surcharge = night_hours * Config.NIGHT_SURCHARGE_AMOUNT
            logger.info(f"💰 СОЗДАНИЕ ТРЕКА: ночных часов: {night_hours}, надбавка: +{night_surcharge}₽")
        
        # Для обычной записи с инженером
        elif start_hour is not None and end_hour is not None and not is_12_hours and not is_mixing and not is_track_creation:
            if with_engineer:
                night_hours = PriceCalculator.get_night_hours_count(start_hour, end_hour, duration)
                night_surcharge = night_hours * Config.NIGHT_SURCHARGE_AMOUNT
                logger.info(f"💰 ОБЫЧНАЯ ЗАПИСЬ: ночных часов: {night_hours}, надбавка (с инженером): +{night_surcharge}₽")
            else:
                logger.info(f"💰 Ночная надбавка не применяется (работа без инженера)")
        
        total_before_discounts = base_price + night_surcharge
        logger.info(f"💰 Сумма до скидок: {total_before_discounts}₽")
        
        # Начальные значения
        current_price = total_before_discounts
        remaining_duration = duration
        level_discount_percent = 0
        level_coupon_id = None
        promo_discount_percent = 0
        promo_code_used = None
        free_hours_applied = 0
        free_service_applied = False
        
        # ===== 3. БЕСПЛАТНЫЕ ЧАСЫ/УСЛУГА (из промокода) =====
        if user_id:
            try:
                promo = PromoCodeManager.get_user_active_promo(str(user_id))
            except:
                promo = None
            
            if promo:
                service_lower = service.lower() if service else ""
                target_service = promo.get('target_service')
                
                promo_applies = False
                
                if promo['discount_type'] == PromoCodeManager.TYPE_PERCENT_ALL:
                    promo_applies = True
                    logger.info(f"💰 ПРОМОКОД % НА ВСЕ ПРИМЕНЯЕТСЯ")
                    
                elif promo['discount_type'] == PromoCodeManager.TYPE_PERCENT_SERVICE:
                    if target_service == "вокал" and "вокал" in service_lower:
                        promo_applies = True
                    elif target_service == "инструмент" and "инструмент" in service_lower:
                        promo_applies = True
                    elif target_service == "аренда" and ("аренд" in service_lower or "12-час" in service_lower):
                        promo_applies = True
                    elif target_service == "сведение" and ("сведен" in service_lower or "мастеринг" in service_lower):
                        promo_applies = True
                    elif target_service == "трек" and "создание трека" in service_lower:
                        promo_applies = True
                    logger.info(f"💰 ПРОМОКОД % НА УСЛУГУ ПРИМЕНЯЕТСЯ")
                        
                elif promo['discount_type'] == PromoCodeManager.TYPE_FREE_HOURS:
                    if "вокал" in service_lower or "инструмент" in service_lower or "создание трека" in service_lower:
                        promo_applies = True
                        logger.info(f"💰 ПРОМОКОД БЕСПЛАТНЫЕ ЧАСЫ ПРИМЕНЯЕТСЯ")
                        
                elif promo['discount_type'] == PromoCodeManager.TYPE_FREE_SERVICE:
                    if target_service == "вокал" and "вокал" in service_lower:
                        promo_applies = True
                    elif target_service == "инструмент" and "инструмент" in service_lower:
                        promo_applies = True
                    elif target_service == "аренда" and ("аренд" in service_lower or "12-час" in service_lower):
                        promo_applies = True
                    elif target_service == "сведение" and ("сведен" in service_lower or "мастеринг" in service_lower):
                        promo_applies = True
                    elif target_service == "трек" and "создание трека" in service_lower:
                        promo_applies = True
                    logger.info(f"💰 ПРОМОКОД БЕСПЛАТНАЯ УСЛУГА ПРИМЕНЯЕТСЯ")
                
                if promo_applies:
                    if promo['discount_type'] == PromoCodeManager.TYPE_FREE_HOURS:
                        free_hours = promo['discount_value']
                        free_hours_applied = free_hours
                        
                        if is_12_hours or is_mixing:
                            logger.info(f"💰 Бесплатные часы не применяются для этого типа услуги")
                        else:
                            price_per_hour = PriceCalculator.get_price_per_hour(with_engineer, duration)
                            free_hours_cost = free_hours * price_per_hour
                            current_price = total_before_discounts - free_hours_cost
                            promo_code_used = promo['code']
                            logger.info(f"💰 Бесплатных часов: {free_hours}, стоимость: -{free_hours_cost}₽, осталось: {current_price}₽")
                        
                    elif promo['discount_type'] == PromoCodeManager.TYPE_FREE_SERVICE:
                        current_price = 0
                        free_service_applied = True
                        promo_code_used = promo['code']
                        logger.info(f"💰 Бесплатная услуга, цена = 0, промокод: {promo_code_used}")
        
        # ===== 4. ЕСЛИ ЦЕНА УЖЕ 0 - ВОЗВРАЩАЕМ =====
        if current_price == 0 or free_service_applied:
            return {
                'base_price': int(base_price),
                'final_price': 0,
                'level_discount_percent': 0,
                'level_coupon_id': None,
                'promo_discount_percent': 0,
                'promo_code_used': promo_code_used,
                'is_contractual': False,
                'free_hours_applied': free_hours_applied,
                'free_service_applied': free_service_applied,
                'night_surcharge': night_surcharge
            }
        
        # ===== 5. ПРИМЕНЯЕМ ПРОЦЕНТНУЮ СКИДКУ ПО УРОВНЮ (КУПОН) =====
        # ===== НЕ ПРИМЕНЯЕМ ДЛЯ АЛЬБОМОВ =====
        is_album = False
        if is_mixing and mixing_type and "Альбом" in mixing_type:
            is_album = True
        elif is_track_creation and track_type and "Альбом" in track_type:
            is_album = True
        elif is_12_hours and "договорная" in str(service).lower():
            is_album = True
        
        if user_id and not is_album:
            try:
                best_coupon = CouponManager.get_best_coupon(str(user_id))
                
                if best_coupon:
                    level_discount_percent = best_coupon['discount']
                    level_coupon_id = best_coupon['id']
                    logger.info(f"💰 Найден купон: скидка {level_discount_percent}%")
                    
                    if consume_coupon and not best_coupon.get('is_permanent', False):
                        success, msg, discount_used = CouponManager.use_coupon(str(user_id), level_coupon_id)
                        if success:
                            logger.info(f"✅ Купон использован")
                        else:
                            logger.warning(f"⚠️ Не удалось использовать купон: {msg}")
                            level_discount_percent = 0
                            level_coupon_id = None
            except Exception as e:
                logger.error(f"Ошибка при работе с купоном: {e}")
        
        # ===== 6. ПРИМЕНЯЕМ ПРОЦЕНТНУЮ СКИДКУ ПО ПРОМОКОДУ =====
        if user_id and not promo_code_used:
            try:
                promo = PromoCodeManager.get_user_active_promo(str(user_id))
                
                if promo and promo['discount_type'] in [PromoCodeManager.TYPE_PERCENT_ALL, PromoCodeManager.TYPE_PERCENT_SERVICE]:
                    service_lower = service.lower() if service else ""
                    target_service = promo.get('target_service')
                    
                    promo_applies = False
                    
                    if promo['discount_type'] == PromoCodeManager.TYPE_PERCENT_ALL:
                        promo_applies = True
                    elif promo['discount_type'] == PromoCodeManager.TYPE_PERCENT_SERVICE:
                        if target_service == "вокал" and "вокал" in service_lower:
                            promo_applies = True
                        elif target_service == "инструмент" and "инструмент" in service_lower:
                            promo_applies = True
                        elif target_service == "аренда" and ("аренд" in service_lower or "12-час" in service_lower):
                            promo_applies = True
                        elif target_service == "сведение" and ("сведен" in service_lower or "мастеринг" in service_lower):
                            promo_applies = True
                        elif target_service == "трек" and "создание трека" in service_lower:
                            promo_applies = True
                    
                    if promo_applies:
                        promo_discount_percent = promo['discount_value']
                        promo_code_used = promo['code']
                        logger.info(f"💰 Промокод на %: +{promo_discount_percent}%")
            except Exception as e:
                logger.error(f"Ошибка при работе с промокодом: {e}")
        
        # ===== 7. ПРИМЕНЯЕМ СУММАРНУЮ ПРОЦЕНТНУЮ СКИДКУ =====
        total_percent_discount = level_discount_percent + promo_discount_percent
        old_price = current_price
        
        if total_percent_discount > 0:
            current_price = current_price * (100 - min(total_percent_discount, 100)) / 100
            logger.info(f"💰 Суммарная скидка: {total_percent_discount}%, было {old_price:.0f}₽, стало {current_price:.0f}₽")
        
        final_price = int(current_price) if current_price > 0 else 0
        
        logger.info(f"💰 ИТОГ: {final_price}₽ (база={base_price}, ночь=+{night_surcharge}, скидка={total_percent_discount}%)")
        
        return {
            'base_price': int(base_price),
            'final_price': final_price,
            'level_discount_percent': level_discount_percent,
            'level_coupon_id': level_coupon_id,
            'promo_discount_percent': promo_discount_percent,
            'promo_code_used': promo_code_used,
            'is_contractual': False,
            'free_hours_applied': free_hours_applied,
            'night_surcharge': night_surcharge,
            'free_service_applied': free_service_applied
        }

    @staticmethod
    def format_price_breakdown(service, duration, start_hour, end_hour, with_engineer):
        """Форматирует breakdown цены для отображения"""
        if 'трек' in str(service).lower() and 'создание' in str(service).lower():
            base_price = Config.PRICES['track_creation_single']
            if with_engineer and start_hour is not None and end_hour is not None:
                night_hours = PriceCalculator.get_night_hours_count(start_hour, end_hour, duration)
                night_surcharge = night_hours * Config.NIGHT_SURCHARGE_AMOUNT
                total_price = base_price + night_surcharge
                if night_hours > 0:
                    return f"{total_price}₽ (база: {base_price}₽ + ночь: {night_surcharge}₽)"
            return f"{base_price}₽"
        
        if not with_engineer or start_hour is None or end_hour is None:
            price = PriceCalculator.calculate_base_price(duration, with_engineer)
            return f"{price}₽"
        
        base_price = PriceCalculator.calculate_base_price(duration, with_engineer)
        night_hours = PriceCalculator.get_night_hours_count(start_hour, end_hour, duration)
        night_surcharge = night_hours * Config.NIGHT_SURCHARGE_AMOUNT
        total_price = base_price + night_surcharge
        
        if night_hours > 0:
            return f"{total_price}₽ (база: {base_price}₽ + ночь: {night_surcharge}₽)"
        else:
            return f"{total_price}₽"

    @staticmethod
    def format_hours_ru(hours):
        """Форматирует часы с правильным склонением"""
        try:
            hours_int = int(hours)
            if hours_int == 1:
                return "1 час"
            elif 2 <= hours_int <= 4:
                return f"{hours_int} часа"
            else:
                return f"{hours_int} часов"
        except:
            return f"{hours} часов"

class DateColorAnalyzer:
    @staticmethod
    def get_color_for_date(date_str: str, service_type: str, with_engineer: bool = False) -> str:
        try:
            logger.info(f"🔍 DateColorAnalyzer.get_color_for_date: {date_str}, тип: {service_type}, инженер: {with_engineer}")
            
            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
            
            cache_key = f"{clean_date}_{service_type}_{with_engineer}"
            cached_color = MemoryCache.get_date_color(cache_key, ttl=300)
            if cached_color:
                logger.info(f"🔍 Из кэша: {cached_color} для ключа: {cache_key}")
                return cached_color
            
            logger.info(f"🔍 Кэш не найден для {cache_key}, пересчитываем...")
            
            parsed_date, _ = DateTimeUtils.parse_date_input(clean_date)
            if parsed_date and parsed_date.date() < DateTimeUtils.now().date():
                MemoryCache.set_date_color(cache_key, "🔴")
                return "🔴"
            
            if service_type in ["12_hours_day", "12_hours_night"]:
                color = DateColorAnalyzer._get_color_for_rental(clean_date, service_type)
                MemoryCache.set_date_color(cache_key, color)
                return color
            
            is_track_creation = (service_type == "track_creation")
            free_intervals = FreeIntervalCalculator.get_all_free_intervals(
                clean_date, is_track_creation, with_engineer
            )
            
            if not free_intervals:
                MemoryCache.set_date_color(cache_key, "🔴")
                return "🔴"
            
            if is_track_creation:
                color = DateColorAnalyzer._get_color_for_track_creation(free_intervals)
            else:
                color = DateColorAnalyzer._get_color_for_vocal(free_intervals)
            
            MemoryCache.set_date_color(cache_key, color)
            return color
                
        except Exception as e:
            logger.error(f"Ошибка анализа цвета даты: {e}")
            return "⚪️"
    
    @staticmethod
    def _get_color_for_rental(date_str: str, service_type: str) -> str:
        try:
            if "day" in service_type:
                time_slot = "9-21"
                start_hour = 9
            else:
                time_slot = "21-9"
                start_hour = 21
            
            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
            
            logger.info(f"🔍 Проверка аренды: {clean_date}, тип: {service_type}, время: {time_slot}")
            
            # 1. Проверяем доступность слота (занят/свободен)
            is_available = BookingManager.check_12_hours_slot_available(clean_date, service_type)
            
            if not is_available:
                logger.info(f"🔍 🔴 Слот занят")
                return "🔴"
            
            # ===== НОВАЯ ПРОВЕРКА ДЛЯ НОЧНОЙ АРЕНДЫ =====
            # Проверяем, что на следующий день нет броней с 0:00 до 9:00
            if "night" in service_type:
                try:
                    day, month, year = map(int, clean_date.split('.'))
                    current_date = datetime(year, month, day)
                    next_date = current_date + timedelta(days=1)
                    next_date_str = next_date.strftime("%d.%m.%Y")
                    
                    logger.info(f"🔍 Проверяем следующий день для ночной аренды: {next_date_str}")
                    
                    # Получаем все занятые слоты на следующий день
                    booked_slots_next = BookingManager.get_all_time_slots_for_date(next_date_str)
                    
                    # Проверяем часы 0-9 на следующий день
                    for hour in range(0, 9):
                        hour_slot = f"{hour}-{hour+1}"
                        if hour_slot in booked_slots_next:
                            logger.info(f"🔍 🔴 Ночная аренда на {clean_date} занята: следующий день {next_date_str}, час {hour_slot} занят")
                            return "🔴"
                            
                except Exception as e:
                    logger.error(f"Ошибка проверки следующего дня для ночной аренды: {e}")
                    return "🔴"
            
            # 2. Проверяем правило 72 часов
            booking_datetime = DateTimeUtils.get_booking_datetime(clean_date, time_slot)
            if not booking_datetime:
                logger.info(f"🔍 ⚪️ Не удалось создать datetime")
                return "⚪️"
            
            now = DateTimeUtils.now()
            time_until_booking = booking_datetime - now
            hours_until_booking = time_until_booking.total_seconds() / 3600
            
            logger.info(f"🔍 До начала аренды: {hours_until_booking:.1f} часов")
            
            if hours_until_booking < 72:
                logger.info(f"🔍 🔴 Нельзя забронировать: требуется 72 часа, осталось {hours_until_booking:.1f} часов")
                return "🔴"
            
            logger.info(f"🔍 🟢 Слот доступен для бронирования")
            return "🟢"
                
        except Exception as e:
            logger.error(f"Ошибка проверки аренды: {e}")
            import traceback
            traceback.print_exc()
            return "⚪️"
        
    @staticmethod
    def _get_color_for_track_creation(free_intervals: List[Dict]) -> str:
        try:
            has_4h_normal_slot = False
            has_4h_cross_night_slot = False
            
            for interval in free_intervals:
                if interval['duration'] >= 4:
                    has_4h_normal_slot = True
                    logger.info(f"   ✅ Нормальный 4-часовой слот: {interval['start']}-{interval['end']}")
                
                elif interval['end'] == 24 and interval['start'] >= 20:
                    hours_before_midnight = interval['duration']
                    hours_needed_after_midnight = 4 - hours_before_midnight
                    
                    logger.info(f"   🔍 Интервал {interval['start']}-24 ({hours_before_midnight}ч)")
                    logger.info(f"   Может быть частью кроссночного бронирования (+{hours_needed_after_midnight}ч после полуночи)")
                    
                    if hours_needed_after_midnight <= 6:
                        has_4h_cross_night_slot = True
            
            logger.info(f"🔍 Итоги проверки: normal_slot={has_4h_normal_slot}, cross_slot={has_4h_cross_night_slot}")
            
            if has_4h_normal_slot:
                return "🟢"
            elif has_4h_cross_night_slot:
                return "🟠"
            else:
                return "🔴"
                    
        except Exception as e:
            logger.error(f"Ошибка анализа для трека: {e}")
            return "🔴"
    
    @staticmethod
    def _get_color_for_vocal(free_intervals: List[Dict]) -> str:
        try:
            total_free_hours = sum(interval['duration'] for interval in free_intervals)
            free_percentage = (total_free_hours / 24) * 100
            
            # ===== ИСПРАВЛЕНО: >= 75 ДЛЯ 🟢 =====
            if free_percentage >= 75:
                return "🟢"
            elif free_percentage >= 50:
                return "🟡"
            elif free_percentage >= 25:
                return "🟠"
            else:
                return "🔴"
                
        except Exception as e:
            logger.error(f"Ошибка анализа для вокала: {e}")
            return "🔴"
    
    @staticmethod
    def get_color_legend(service_type: str, with_engineer: bool = False) -> str:
        if service_type in ["12_hours_day", "12_hours_night"]:
            legend = (
                "🟢 — Слот доступен для бронирования\n"
                "🔴 — Слот занят или нельзя забронировать\n"
                "⚪️ — Неизвестно (техническая проверка)"
            )
        elif service_type == "track_creation":
            legend = (
                "🟢 — Есть 4-часовой слот (можно забронировать ДО полуночи)\n"
                "🟠 — Есть 4-часовой слот только через полночь\n"
                "🔴 — Нет 4-часового слота\n"
                "⚪️ — Неизвестно (техническая проверка)"
            )
        else:
            legend = (
                "🟢 — Свободно >75% времени (более 18 часов)\n"
                "🟡 — Свободно 50-75% времени (12-18 часов)\n"
                "🟠 — Свободно 25-50% времени (6-12 часов)\n"
                "🔴 — Свободно <25% времени (менее 6 часов)\n"
                "⚪️ — Неизвестно (техническая проверка)"
            )
        
        return legend

class BookingManager:
    _slots_cache = {}
    _cache_timeout = 60
    _date_load_cache = {}
    _date_load_timeout = 60

    @staticmethod
    def check_12_hours_slot_available(date_str: str, service_type: str) -> bool:
        try:
            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
            
            logger.info(f"🔍 === ПРОВЕРКА 12-ЧАСОВОЙ АРЕНДЫ НА {clean_date} ===")
            logger.info(f"🔍 Тип аренды: {service_type}")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                if "day" in service_type:
                    target_type = "День"
                    logger.info(f"🔍 Ищем ДНЕВНУЮ аренду (9-21)")
                    
                    # Проверяем, есть ли уже дневная аренда на эту дату
                    cursor.execute('''
                        SELECT id FROM bookings 
                        WHERE date_str LIKE ? || '%' 
                        AND is_12_hours = 1
                        AND twelve_hours_type LIKE ?
                        AND status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
                    ''', (clean_date, f'%{target_type}%'))
                    
                    if cursor.fetchone():
                        logger.info(f"🔍 ❌ Дневная аренда на {clean_date} уже существует")
                        return False
                    
                    # ===== ИСПРАВЛЕНО: используем get_all_time_slots_for_date =====
                    booked_slots = BookingManager.get_all_time_slots_for_date(clean_date)
                    logger.info(f"🔍 Занятые слоты на {clean_date}: {booked_slots}")
                    
                    # Проверяем часы 9-21
                    for hour in range(9, 21):
                        hour_slot = f"{hour}-{hour+1}"
                        if hour_slot in booked_slots:
                            logger.info(f"🔍 ❌ Час {hour_slot} на {clean_date} занят")
                            return False
                    
                    logger.info(f"🔍 ✅ Дневная аренда на {clean_date} доступна")
                    return True
                    
                else:  # night
                    target_type = "Ночь"
                    logger.info(f"🔍 Ищем НОЧНУЮ аренду (21-9)")
                    
                    # Проверяем, есть ли уже ночная аренда на эту дату
                    cursor.execute('''
                        SELECT id FROM bookings 
                        WHERE date_str LIKE ? || '%' 
                        AND is_12_hours = 1
                        AND twelve_hours_type LIKE ?
                        AND status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
                    ''', (clean_date, f'%{target_type}%'))
                    
                    if cursor.fetchone():
                        logger.info(f"🔍 ❌ Ночная аренда на {clean_date} уже существует")
                        return False
                    
                    # ===== ИСПРАВЛЕНО: проверяем ТЕКУЩИЙ день через get_all_time_slots_for_date =====
                    booked_slots = BookingManager.get_all_time_slots_for_date(clean_date)
                    logger.info(f"🔍 Занятые слоты на {clean_date} (текущий день): {booked_slots}")
                    
                    # Проверяем часы 21-24 на текущую дату
                    for hour in range(21, 24):
                        hour_slot = f"{hour}-{hour+1}"
                        if hour_slot in booked_slots:
                            logger.info(f"🔍 ❌ Час {hour_slot} на {clean_date} занят")
                            return False
                    
                    # ===== ИСПРАВЛЕНО: проверяем СЛЕДУЮЩИЙ день через get_all_time_slots_for_date =====
                    try:
                        day, month, year = map(int, clean_date.split('.'))
                        current_date = datetime(year, month, day)
                        next_date = current_date + timedelta(days=1)
                        next_date_str = next_date.strftime("%d.%m.%Y")
                        
                        logger.info(f"🔍 Проверяем следующий день: {next_date_str}")
                        
                        booked_slots_next = BookingManager.get_all_time_slots_for_date(next_date_str)
                        logger.info(f"🔍 Занятые слоты на {next_date_str} (следующий день): {booked_slots_next}")
                        
                        for hour in range(0, 9):
                            hour_slot = f"{hour}-{hour+1}"
                            if hour_slot in booked_slots_next:
                                logger.info(f"🔍 ❌ Час {hour_slot} на {next_date_str} занят")
                                return False
                                
                    except Exception as e:
                        logger.error(f"Ошибка проверки следующего дня: {e}")
                        return False
                    
                    logger.info(f"🔍 ✅ Ночная аренда на {clean_date} доступна")
                    return True
                        
        except Exception as e:
            logger.error(f"Ошибка проверки 12-часового слота: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def debug_12_hour_booking(date_str):
        logger.info("=" * 60)
        logger.info(f"🔍 ДЕБАГ 12-ЧАСОВЫХ АРЕНД НА ДАТУ: {date_str}")
        logger.info("=" * 60)
        
        clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
        
        MemoryCache.invalidate_date(clean_date)
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, time_slot, twelve_hours_type, date_str 
                FROM bookings 
                WHERE date_str LIKE ? || '%' 
                AND is_12_hours = 1
                AND status NOT IN ('rejected', 'отклонен', 'cancelled', 'отменен')
            ''', (clean_date,))
            
            bookings = cursor.fetchall()
            logger.info(f"🔍 Найдено 12-часовых аренд на {clean_date}: {len(bookings)}")
            
            for booking in bookings:
                booking_id, time_slot, twelve_hours_type, booking_date = booking
                logger.info(f"  • Запись #{booking_id}: {time_slot} ({twelve_hours_type}) на {booking_date}")
            
            try:
                day, month, year = map(int, clean_date.split('.'))
                current_date = datetime(year, month, day)
                prev_date = current_date - timedelta(days=1)
                prev_date_str = prev_date.strftime("%d.%m.%Y")
                
                cursor.execute('''
                    SELECT id, time_slot, twelve_hours_type, date_str 
                    FROM bookings 
                    WHERE date_str LIKE ? || '%' 
                    AND is_12_hours = 1
                    AND status NOT IN ('rejected', 'отклонен', 'cancelled', 'отменен')
                ''', (prev_date_str,))
                
                prev_bookings = cursor.fetchall()
                logger.info(f"🔍 Найдено 12-часовых аренд с предыдущего дня {prev_date_str}: {len(prev_bookings)}")
                
                for booking in prev_bookings:
                    booking_id, time_slot, twelve_hours_type, booking_date = booking
                    logger.info(f"  • Запись #{booking_id}: {time_slot} ({twelve_hours_type}) на {booking_date}")
                    
            except Exception as e:
                logger.error(f"Ошибка проверки предыдущего дня: {e}")
        
        slots = BookingManager.get_all_time_slots_for_date(date_str)
        logger.info(f"🔍 Итоговые заблокированные слоты на {clean_date}:")
        for slot in sorted(slots, key=lambda x: int(x.split('-')[0])):
            logger.info(f"  • {slot}")
        
        logger.info("=" * 60)
        
        return slots

    @staticmethod
    def get_all_time_slots_for_date(date_str):
        try:
            if not date_str or len(date_str) > 50:
                return []
            
            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
            
            cached_slots = MemoryCache.get_date_slots(clean_date, ttl=5)
            if cached_slots is not None:
                return cached_slots
            
            logger.info(f"🔍 get_all_time_slots_for_date: {clean_date}")
            
            booked_slots = []
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Записи на эту дату (ВКЛЮЧАЯ pending!)
                cursor.execute('''
                    SELECT time_slot, is_12_hours, twelve_hours_type FROM bookings 
                    WHERE date_str LIKE ? || '%' 
                    AND status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
                ''', (clean_date,))
                
                rows = cursor.fetchall()
                logger.info(f"🔍 Найдено записей на {clean_date}: {len(rows)}")
                
                for row in rows:
                    time_slot, is_12_hours, twelve_hours_type = row
                    
                    if not time_slot or time_slot == 'Не указано' or '-' not in time_slot:
                        continue
                        
                    normalized_slot = DateTimeUtils.normalize_time_input(time_slot)
                    
                    try:
                        start_str, end_str = normalized_slot.split('-')
                        start_hour = int(start_str)
                        end_hour = int(end_str)
                        
                        logger.info(f"🔍 Бронь на {clean_date}: {normalized_slot} (12ч: {is_12_hours}, тип: {twelve_hours_type})")
                        
                        if is_12_hours and twelve_hours_type:
                            if 'Ночь' in twelve_hours_type or 'ночь' in twelve_hours_type.lower():
                                logger.info(f"   → 12-часовая НОЧНАЯ аренда: блокирует 21-24 (этот день)")
                                for hour in range(21, 24):
                                    booked_slots.append(f"{hour}-{hour+1}")
                                
                            elif 'День' in twelve_hours_type or 'день' in twelve_hours_type.lower():
                                logger.info(f"   → 12-часовая ДНЕВНАЯ аренда: блокирует 9-21")
                                for hour in range(9, 21):
                                    booked_slots.append(f"{hour}-{hour+1}")
                        
                        else:
                            # ===== ПРОСТАЯ ЛОГИКА =====
                            # Ночной слот — только когда end_hour <= start_hour (пересекает полночь)
                            if end_hour <= start_hour:
                                logger.info(f"   → НОЧНОЙ слот: блокирует {start_hour}-24 (этот день)")
                                for hour in range(start_hour, 24):
                                    booked_slots.append(f"{hour}-{hour+1}")
                            else:
                                logger.info(f"   → ОБЫЧНЫЙ дневной слот: блокирует {start_hour}-{end_hour}")
                                for hour in range(start_hour, end_hour):
                                    booked_slots.append(f"{hour}-{hour+1}")
                                
                    except Exception as e:
                        logger.error(f"Ошибка обработки слота {normalized_slot}: {e}")
                        continue
                
                # 2. КРИТИЧЕСКИ ВАЖНО: Проверяем ночные записи с ПРЕДЫДУЩЕГО ДНЯ
                try:
                    day, month, year = map(int, clean_date.split('.'))
                    current_date = datetime(year, month, day)
                    prev_date = current_date - timedelta(days=1)
                    prev_date_str = prev_date.strftime("%d.%m.%Y")
                    
                    logger.info(f"🔍 Проверяем ночные записи с предыдущего дня: {prev_date_str}")
                    
                    cursor.execute('''
                        SELECT time_slot, is_12_hours, twelve_hours_type FROM bookings 
                        WHERE date_str LIKE ? || '%' 
                        AND status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
                    ''', (prev_date_str,))
                    
                    prev_rows = cursor.fetchall()
                    logger.info(f"🔍 Найдено записей на {prev_date_str}: {len(prev_rows)}")
                    
                    for row in prev_rows:
                        time_slot, is_12_hours, twelve_hours_type = row
                        
                        if not time_slot or time_slot == 'Не указано' or '-' not in time_slot:
                            continue
                        
                        normalized_slot = DateTimeUtils.normalize_time_input(time_slot)
                        
                        try:
                            start_str, end_str = normalized_slot.split('-')
                            start_hour = int(start_str)
                            end_hour = int(end_str)
                            
                            # Проверяем 12-часовую ночную аренду с предыдущего дня
                            if is_12_hours and twelve_hours_type and ('Ночь' in twelve_hours_type or 'ночь' in twelve_hours_type.lower()):
                                logger.info(f"🔍 Ночная 12-часовая аренда с {prev_date_str} блокирует 0-9 на {clean_date}")
                                for hour in range(0, 9):
                                    booked_slots.append(f"{hour}-{hour+1}")
                            
                            # Если это обычный ночной слот (пересекает полночь)
                            elif end_hour <= start_hour:
                                logger.info(f"🔍 Ночная запись с {prev_date_str} {normalized_slot} блокирует 00-{end_hour} на {clean_date}")
                                for hour in range(0, end_hour):
                                    booked_slots.append(f"{hour}-{hour+1}")
                                        
                        except Exception as e:
                            logger.error(f"Ошибка обработки слота с предыдущего дня: {e}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Ошибка проверки предыдущего дня: {e}")
            
            booked_slots = list(set(booked_slots))
            booked_slots.sort(key=lambda x: int(x.split('-')[0]))
            
            logger.info(f"🔍 Итоговые занятые слоты на {clean_date}: {booked_slots}")
            
            MemoryCache.set_date_slots(clean_date, booked_slots)
            return booked_slots
            
        except Exception as e:
            logger.error(f"Ошибка получения слотов для даты: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def is_time_slot_conflict(new_time_slot, booked_slots, date_str=None):
        try:
            if not new_time_slot or '-' not in new_time_slot:
                return False
            
            logger.info(f"🔍 === ПРОВЕРКА КОНФЛИКТА ДЛЯ: {new_time_slot} ===")
            logger.info(f"🔍 Занятые слоты: {booked_slots}")
            
            new_start_str, new_end_str = new_time_slot.split('-')
            new_start = int(new_start_str.strip())
            new_end = int(new_end_str.strip())
            
            # Нормализуем конечный час (24 -> 0 для расчета)
            if new_end == 0 or new_end == 24:
                new_end_norm = 24
            else:
                new_end_norm = new_end
            
            logger.info(f"🔍 Новый слот: {new_start}-{new_end} (нормализовано: {new_start}-{new_end_norm})")
            
            new_hours = set()
            
            if new_end_norm > new_start:
                for hour in range(new_start, new_end_norm):
                    new_hours.add(hour % 24)
            else:
                for hour in range(new_start, 24):
                    new_hours.add(hour)
                for hour in range(0, new_end_norm):
                    new_hours.add(hour)
            
            logger.info(f"🔍 Часы нового слота: {sorted(new_hours)}")
            
            for booked_slot in booked_slots:
                if not booked_slot or '-' not in booked_slot:
                    continue
                
                booked_start_str, booked_end_str = booked_slot.split('-')
                booked_start = int(booked_start_str.strip())
                booked_end = int(booked_end_str.strip())
                
                if booked_end == 0 or booked_end == 24:
                    booked_end_norm = 24
                else:
                    booked_end_norm = booked_end
                
                logger.info(f"🔍 Проверяем с забронированным: {booked_start}-{booked_end} (норм: {booked_start}-{booked_end_norm})")
                
                booked_hours = set()
                
                if booked_end_norm > booked_start:
                    for hour in range(booked_start, booked_end_norm):
                        booked_hours.add(hour % 24)
                else:
                    for hour in range(booked_start, 24):
                        booked_hours.add(hour)
                    for hour in range(0, booked_end_norm):
                        booked_hours.add(hour)
                
                logger.info(f"🔍 Часы забронированного слота: {sorted(booked_hours)}")
                
                intersection = new_hours.intersection(booked_hours)
                if intersection:
                    logger.info(f"🔍 КОНФЛИКТ! Пересекающиеся часы: {sorted(intersection)}")
                    return True
                else:
                    logger.info(f"🔍 Нет конфликта с {booked_slot}")
            
            logger.info(f"🔍 ✅ Все проверки пройдены, конфликтов нет")
            return False
                        
        except Exception as e:
            logger.error(f"Ошибка проверки конфликта слота: {e}")
            import traceback
            traceback.print_exc()
            return True

    @staticmethod
    def check_time_slot_available(date_str, time_slot, service_type="vocal"):
        try:
            if not date_str or not time_slot or '-' not in time_slot:
                return False
            
            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
            
            logger.info("=" * 60)
            logger.info(f"🔍 check_time_slot_available (FINAL):")
            logger.info(f"   Дата: {clean_date}")
            logger.info(f"   Время: {time_slot}")
            
            normalized_time = DateTimeUtils.normalize_time_input(time_slot)
            
            if '-' not in normalized_time:
                logger.error(f"Неверный формат времени: {normalized_time}")
                return False
            
            start_str, end_str = normalized_time.split('-')
            try:
                start_hour = int(start_str.strip())
                end_hour = int(end_str.strip())
            except ValueError:
                logger.error(f"Неверный формат часов: {start_str}-{end_str}")
                return False
            
            logger.info(f"🔍 Время для проверки: {start_hour}-{end_hour}")
            
            # Получаем все занятые слоты (включая pending!)
            booked_slots = BookingManager.get_all_time_slots_for_date(clean_date)
            logger.info(f"🔍 Занятые слоты на {clean_date}: {booked_slots}")
            
            if end_hour > start_hour:
                # Обычный дневной слот
                for hour in range(start_hour, end_hour):
                    hour_slot = f"{hour}-{hour+1}"
                    if hour_slot in booked_slots:
                        logger.info(f"🔍 КОНФЛИКТ: слот {hour_slot} занят!")
                        return False
            
            else:
                # Ночной слот, пересекающий полночь
                for hour in range(start_hour, 24):
                    hour_slot = f"{hour}-{hour+1}"
                    if hour_slot in booked_slots:
                        logger.info(f"🔍 КОНФЛИКТ (этот день): слот {hour_slot} занят!")
                        return False
                
                try:
                    day, month, year = map(int, clean_date.split('.'))
                    current_date = datetime(year, month, day)
                    next_date = current_date + timedelta(days=1)
                    next_date_str = next_date.strftime("%d.%m.%Y")
                    
                    booked_slots_day2 = BookingManager.get_all_time_slots_for_date(next_date_str)
                    logger.info(f"🔍 Занятые слоты на {next_date_str}: {booked_slots_day2}")
                    
                    for hour in range(0, end_hour):
                        hour_slot = f"{hour}-{hour+1}"
                        if hour_slot in booked_slots_day2:
                            logger.info(f"🔍 КОНФЛИКТ (след. день): слот {hour_slot} занят на {next_date_str}!")
                            return False
                            
                except Exception as e:
                    logger.error(f"Ошибка проверки следующего дня: {e}")
                    return False
            
            logger.info(f"🔍 ✅ Слот {time_slot} на {clean_date} ДОСТУПЕН")
            logger.info("=" * 60)
            return True
                    
        except Exception as e:
            logger.error(f"Ошибка в check_time_slot_available: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def save_to_sheets(user_data, user_id=None, return_row_index=False):
        try:
            logger.info("=" * 80)
            logger.info("🚀 СОХРАНЕНИЕ БРОНИРОВАНИЯ - СТАРТ")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM bookings')
                count_before = cursor.fetchone()[0]
                is_first_booking = (count_before == 0)
            
            logger.info(f"🔍 Записей в базе ДО сохранения: {count_before}")
            logger.info(f"🔍 Это первая запись в базе? {is_first_booking}")
            
            timestamp = DateTimeUtils.now().strftime('%Y-%m-%d %H:%M:%S')
            
            is_admin_booking = user_data.get('is_admin_booking', False)
            
            if is_admin_booking and 'target_telegram_id' in user_data:
                telegram_id = str(user_data.get('target_telegram_id'))
                logger.info(f"🔍 Админская запись для пользователя: {telegram_id}")
                
                name = f"Админская запись (администратор)"
                contact = f"ID: {user_data.get('target_unique_id', 'Не указан')}"
                
                record_type = user_data.get('admin_record_type', '')
                if record_type == "📝 Договорная запись":
                    service = f"📝 Договорная запись (Админ)"
                    date_str_for_db = "Не указана (договорная)"
                    time_slot_for_db = "Не указано (договорная)"
                else:
                    service = f"🎤 Запись в студии (Админ)"
                    date_str_for_db = "Запись в студии"
                    time_slot_for_db = "Запись в студии"
                    
            else:
                telegram_id = str(user_id) if user_id else "000"
                logger.info(f"🔍 Обычная запись для пользователя: {telegram_id}")
                
                name = user_data.get('name', 'Не указано')
                contact = user_data.get('contact', 'Не указано')
                service = user_data.get('service', 'Не указана')
                date_str_for_db = user_data.get('date', 'Не указана')
                time_slot_for_db = user_data.get('time', 'Не указано')
            
            logger.info(f"🔍 Пользователь: {telegram_id}, Услуга: {service}")
            
            time_slot = time_slot_for_db
            original_time = time_slot
            
            if time_slot != 'Не указано' and time_slot != 'Не указано (договорная)' and time_slot != 'Запись в студии':
                time_slot = DateTimeUtils.normalize_time_input(time_slot)
                time_slot = BookingManager.force_normalize_time(time_slot)
                
                if '-' in time_slot:
                    parts = time_slot.split('-')
                    if len(parts) == 2:
                        try:
                            start_hour = int(parts[0].strip())
                            end_hour = int(parts[1].strip())
                            time_slot = f"{start_hour}-{end_hour}"
                        except ValueError as e:
                            logger.error(f"Ошибка парсинга времени {time_slot}: {e}")
                            time_slot = 'Не указано'
            
            date_str = date_str_for_db
            
            clean_date = date_str
            if '(' in date_str:
                clean_date = date_str.split('(')[0].strip()
            
            is_12_hours = user_data.get('is_12_hours', False)
            is_mixing = user_data.get('is_mixing', False)
            is_track_creation = user_data.get('is_track_creation', False)
            with_engineer = user_data.get('with_engineer', False)
            mixing_type = user_data.get('mixing_type', None)
            track_type = user_data.get('track_type', None)
            twelve_hours_type = user_data.get('12_hours_type', None)
            duration = user_data.get('duration', 0)
            start_hour = user_data.get('start_hour', None)
            end_hour = user_data.get('end_hour', None)

            # ===== ЦЕНА БЕРЁТСЯ ИЗ user_data (УЖЕ РАССЧИТАНА В PriceCalculator) =====
            price = str(user_data.get('price', '0'))
            
            # ===== ПРОВЕРЯЕМ, БЫЛ ЛИ ПРИМЕНЁН ПРОМОКОД НА БЕСПЛАТНУЮ УСЛУГУ =====
            free_service_applied = user_data.get('free_service_applied', False)
            if free_service_applied:
                price = '0'
                logger.info(f"💰 Бесплатная услуга, цена = 0")
            
            # ===== ПОЛУЧАЕМ level_coupon_id ИЗ user_data (НЕ ИЗ price_result!) =====
            level_coupon_id = user_data.get('level_coupon_id')
            level_discount_percent = user_data.get('level_discount_percent', 0)
            promo_code_used = user_data.get('promo_code_used')
            promo_discount_percent = user_data.get('promo_discount_percent', 0)

            logger.info(f"🔍 Цена из user_data: {price}")
            logger.info(f"🔍 free_service_applied: {free_service_applied}")
            logger.info(f"🔍 level_coupon_id из user_data: {level_coupon_id}")
            logger.info(f"🔍 level_discount_percent из user_data: {level_discount_percent}")
            logger.info(f"🔍 promo_code_used из user_data: {promo_code_used}")
            logger.info(f"🔍 promo_discount_percent из user_data: {promo_discount_percent}")

            status = 'confirmed' if is_admin_booking else 'pending'
            logger.info(f"🔍 Статус записи: {status} (админская: {is_admin_booking})")
            
            affected_dates = [clean_date]

            # ================================================================
            # ===== ИСПРАВЛЕННАЯ ОЧИСТКА КЭША =====
            # ================================================================
            if clean_date and 'Не указана' not in clean_date and clean_date != 'Запись в студии':
                # Очищаем текущую дату
                MemoryCache.invalidate_date(clean_date)
                
                # ===== НОВОЕ: ВСЕГДА ОЧИЩАЕМ ПРЕДЫДУЩИЙ И СЛЕДУЮЩИЙ ДЕНЬ =====
                try:
                    day, month, year = map(int, clean_date.split('.'))
                    current_date = datetime(year, month, day)
                    
                    # Предыдущий день
                    prev_date = current_date - timedelta(days=1)
                    MemoryCache.invalidate_date(prev_date.strftime("%d.%m.%Y"))
                    affected_dates.append(prev_date.strftime("%d.%m.%Y"))
                    logger.info(f"🗑️ Очищен кэш для предыдущего дня: {prev_date.strftime('%d.%m.%Y')}")
                    
                    # Следующий день
                    next_date = current_date + timedelta(days=1)
                    MemoryCache.invalidate_date(next_date.strftime("%d.%m.%Y"))
                    affected_dates.append(next_date.strftime("%d.%m.%Y"))
                    logger.info(f"🗑️ Очищен кэш для следующего дня: {next_date.strftime('%d.%m.%Y')}")
                    
                except Exception as e:
                    logger.error(f"Ошибка очистки кэша для соседних дат: {e}")
                
                # Старая логика для дополнительных дат (если слот пересекает полночь)
                if time_slot and '-' in time_slot and time_slot != 'Не указано':
                    start_str, end_str = time_slot.split('-')
                    try:
                        start_hour_check = int(start_str.strip())
                        end_hour_check = int(end_str.strip())
                        
                        # ===== ЕСЛИ СЛОТ ПЕРЕСЕКАЕТ ПОЛНОЧЬ =====
                        if end_hour_check <= start_hour_check or time_slot == '21-9':
                            day, month, year = map(int, clean_date.split('.'))
                            current_date = datetime(year, month, day)
                            
                            # Очищаем кэш для следующего дня
                            next_date = current_date + timedelta(days=1)
                            next_date_str = next_date.strftime("%d.%m.%Y")
                            MemoryCache.invalidate_date(next_date_str)
                            affected_dates.append(next_date_str)
                            
                            # Очищаем кэш для предыдущего дня
                            prev_date = current_date - timedelta(days=1)
                            prev_date_str = prev_date.strftime("%d.%m.%Y")
                            MemoryCache.invalidate_date(prev_date_str)
                            affected_dates.append(prev_date_str)
                            
                    except ValueError as e:
                        logger.error(f"Ошибка парсинга времени для сброса кэша: {e}")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT seq FROM sqlite_sequence WHERE name='bookings'")
                seq_result = cursor.fetchone()
                seq_before = seq_result[0] if seq_result else 0
                logger.info(f"🔍 Аутоинкремент ДО сохранения: {seq_before}")
                
                record_type = user_data.get('admin_record_type', '')
                
                if is_admin_booking:
                    if record_type == "📝 Договорная запись":
                        is_contractual = True
                        logger.info(f"🔍 Админская договорная запись")
                    else:
                        is_contractual = False
                        logger.info(f"🔍 Админская запись в студии (не договорная)")
                else:
                    is_contractual = (
                        'Не указана' in clean_date or 
                        'договорная' in str(clean_date).lower() or
                        time_slot in ['Не указано', 'Не указано (договорная)'] or
                        'договорная' in str(price).lower() or
                        (is_mixing and mixing_type and 'Альбом' in mixing_type) or
                        (is_track_creation and track_type and 'Альбом' in track_type)
                    )
                
                logger.info(f"🔍 is_contractual = {is_contractual} для записи: {service}")
                
                # ===== INSERT =====
                cursor.execute('''
                    INSERT INTO bookings (
                        timestamp, name, contact, telegram_id, service,
                        time_slot, date_str, status, price,
                        is_12_hours, is_mixing, is_track_creation, with_engineer,
                        mixing_type, track_type, twelve_hours_type, duration,
                        start_hour, end_hour, is_contractual, is_admin_booking,
                        free_service_applied
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp, name, contact, telegram_id, service,
                    time_slot, clean_date, status, price,
                    1 if is_12_hours else 0,
                    1 if is_mixing else 0,
                    1 if is_track_creation else 0,
                    1 if with_engineer else 0,
                    mixing_type, track_type, twelve_hours_type, duration,
                    start_hour, end_hour,
                    1 if is_contractual else 0,
                    1 if is_admin_booking else 0,
                    1 if free_service_applied else 0
                ))
                
                booking_id = cursor.lastrowid
                
                logger.info(f"✅ Запись сохранена с ID: {booking_id}")
                
                # ===== ПОСЛЕ INSERT ОБНОВЛЯЕМ level_coupon_id =====
                if level_coupon_id:
                    cursor.execute('UPDATE bookings SET level_coupon_id = ? WHERE id = ?', (level_coupon_id, booking_id))
                    logger.info(f"💰 level_coupon_id {level_coupon_id} сохранён для записи #{booking_id}")
                
                if level_discount_percent:
                    cursor.execute('UPDATE bookings SET level_discount_percent = ? WHERE id = ?', (level_discount_percent, booking_id))
                    logger.info(f"💰 level_discount_percent {level_discount_percent} сохранён для записи #{booking_id}")
                
                if promo_code_used:
                    cursor.execute('UPDATE bookings SET promo_code_used = ? WHERE id = ?', (promo_code_used, booking_id))
                    logger.info(f"💰 promo_code_used {promo_code_used} сохранён для записи #{booking_id}")
                
                if promo_discount_percent:
                    cursor.execute('UPDATE bookings SET promo_discount_percent = ? WHERE id = ?', (promo_discount_percent, booking_id))
                    logger.info(f"💰 promo_discount_percent {promo_discount_percent} сохранён для записи #{booking_id}")
                
                # ===== СОХРАНЯЕМ free_service_applied В БД =====
                if free_service_applied:
                    cursor.execute('UPDATE bookings SET free_service_applied = 1 WHERE id = ?', (booking_id,))
                    logger.info(f"💰 free_service_applied 1 сохранён для записи #{booking_id}")
                
                if price and price != '0' and 'договорная' not in str(price).lower():
                    try:
                        price_value = 0
                        if isinstance(price, (int, float)):
                            price_value = int(price)
                        elif isinstance(price, str):
                            cleaned_price = ''.join(filter(str.isdigit, price))
                            if cleaned_price:
                                price_value = int(cleaned_price)
                        
                        if price_value > 0:
                            logger.info(f"💰 Обновляем total_spent для пользователя {telegram_id}: +{price_value}₽")
                            
                            cursor.execute('SELECT total_spent FROM users WHERE telegram_id = ?', (telegram_id,))
                            user_data_db = cursor.fetchone()
                            
                            if user_data_db:
                                current_total = user_data_db[0] or 0
                                new_total = current_total + price_value
                                cursor.execute('UPDATE users SET total_spent = ? WHERE telegram_id = ?', 
                                            (new_total, telegram_id))
                                logger.info(f"💰 Обновлен total_spent: {current_total} -> {new_total}₽")
                            else:
                                unique_id = f"MC{int(time.time())}{telegram_id[-6:]}"
                                registration_date = DateTimeUtils.now().strftime('%d.%m.%Y')
                                
                                cursor.execute('''
                                    INSERT INTO users 
                                    (telegram_id, username, unique_id, registration_date, total_spent)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (telegram_id, telegram_id, unique_id, registration_date, price_value))
                                logger.info(f"💰 Создан новый пользователь с total_spent: {price_value}₽")
                    except Exception as e:
                        logger.error(f"❌ Ошибка обновления total_spent в save_to_sheets: {e}")
                
                cursor.execute("SELECT seq FROM sqlite_sequence WHERE name='bookings'")
                seq_result = cursor.fetchone()
                seq_after = seq_result[0] if seq_result else 0
                logger.info(f"🔍 Аутоинкремент ПОСЛЕ сохранения: {seq_after}")
                
                if clean_date and 'Не указана' not in clean_date and is_12_hours:
                    if twelve_hours_type and ('День' in twelve_hours_type or 'день' in twelve_hours_type.lower()):
                        cache_service_type = '12_hours_day'
                    else:
                        cache_service_type = '12_hours_night'
                    
                    cursor.execute('''
                        DELETE FROM cache_slots 
                        WHERE date_str = ? AND time_slot = ? AND service_type = ?
                    ''', (clean_date, time_slot, cache_service_type))
                    
                    cursor.execute('''
                        INSERT INTO cache_slots (date_str, time_slot, service_type, booking_id)
                        VALUES (?, ?, ?, ?)
                    ''', (clean_date, time_slot, cache_service_type, booking_id))
                    
                    logger.info(f"📦 Обновлен кэш для 12-часовой аренды: {clean_date} {time_slot}")
                
                cursor.execute('SELECT COUNT(*) FROM bookings')
                count_after = cursor.fetchone()[0]
                logger.info(f"🔍 Записей в базе ПОСЛЕ сохранения: {count_after}")
                
                conn.commit()
                
                logger.info(f"✅ Сохранение завершено. Booking ID: {booking_id}")
                logger.info(f"✅ УСПЕХ! Запись #{booking_id} создана.")
                logger.info(f"🔍 Статус записи: {status}")
                logger.info("=" * 80)
                
                if not is_admin_booking:
                    try:
                        booking_data_persistent = {
                            'telegram_id': str(telegram_id),
                            'name': name,
                            'contact': contact,
                            'service': service,
                            'date_str': clean_date,
                            'time_slot': time_slot,
                            'price': str(price),
                            'status': status
                        }
                        
                        persistent_booking_id = persistent_db.save_booking(booking_data_persistent)
                        if persistent_booking_id:
                            logger.info(f"📦 Запись #{persistent_booking_id} сохранена в ПЕРСИСТЕНТНУЮ базу")
                        else:
                            logger.warning("⚠️ Не удалось сохранить в персистентную базу")
                                
                    except Exception as e:
                        logger.error(f"❌ Ошибка сохранения в персистентную базу: {e}")
                
                if return_row_index:
                    return True, booking_id
                return True
                        
        except sqlite3.IntegrityError as e:
            logger.error(f"❌ ОШИБКА UNIQUE INDEX: Не удалось сохранить бронирование: {e}")
            if return_row_index:
                return False, None
            return False
        except Exception as e:
            logger.error(f"Ошибка сохранения бронирования: {e}")
            import traceback
            traceback.print_exc()
            if return_row_index:
                return False, None
            return False

    @staticmethod
    def force_normalize_time(time_str):
        if not time_str or time_str == 'Не указано':
            return time_str
        
        time_str = time_str.replace(' ', '')
        
        if '-' not in time_str:
            return time_str
        
        try:
            start_str, end_str = time_str.split('-')
            
            start_hour = int(start_str)
            end_hour = int(end_str)
            
            if end_hour == 24:
                end_hour = 0
            
            return f"{start_hour}-{end_hour}"
            
        except ValueError:
            return time_str

class FreeIntervalCalculator:
    @staticmethod
    def format_interval_for_display(interval):
        duration = interval['duration']
        formatted_duration = PriceCalculator.format_hours_ru(duration)
        
        if interval['start'] == 0 and interval['end'] == 24:
            return "00:00 — 00:00 (24 часа доступно)"
        
        if interval['start'] == 23 and interval['end'] == 24:
            return "23:00 — 00:00 (1 час доступен, можно бронировать через полночь)"
        
        if interval['start'] == 22 and interval['end'] == 24:
            formatted_duration = PriceCalculator.format_hours_ru(interval['duration'])
            return f"22:00 — 00:00 ({formatted_duration} доступно, можно бронировать через полночь)"
        
        if interval['start'] == 21 and interval['end'] == 24:
            formatted_duration = PriceCalculator.format_hours_ru(interval['duration'])
            return f"21:00 — 00:00 ({formatted_duration} доступно, можно бронировать через полночь)"
        
        if interval['start'] == 20 and interval['end'] == 24:
            formatted_duration = PriceCalculator.format_hours_ru(interval['duration'])
            return f"20:00 — 00:00 ({formatted_duration} доступно, можно бронировать через полночь)"
        
        if interval['end'] == 24:
            start_display = f"{interval['start']:02d}"
            
            if duration >= 4:
                return f"{start_display}:00 — 00:00 ({formatted_duration} доступно)"
            else:
                return f"{start_display}:00 — 00:00 ({formatted_duration} доступно, можно бронировать через полночь)"
        
        start_display = "00" if interval['start'] == 0 else f"{interval['start']:02d}"
        end_display = "00" if interval['end'] == 0 else f"{interval['end']:02d}"
        
        return f"{start_display}:00 — {end_display}:00 ({formatted_duration} доступно)"
    
    @staticmethod
    def get_all_free_intervals(date_str: str, is_track_creation: bool, with_engineer: bool):
        """Возвращает все свободные интервалы на дату с учетом ограничений"""
        try:
            clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
            
            logger.info(f"🔍 === get_all_free_intervals для {clean_date} ===")
            logger.info(f"   is_track_creation: {is_track_creation}")
            logger.info(f"   with_engineer: {with_engineer}")
            
            # ПОЛУЧАЕМ ЗАНЯТЫЕ СЛОТЫ
            booked_slots = BookingManager.get_all_time_slots_for_date(clean_date)
            logger.info(f"🔍 Занятые слоты на {clean_date}: {booked_slots}")
            
            now = DateTimeUtils.now()
            day, month, year = map(int, clean_date.split('.'))
            target_date = Config.TIMEZONE.localize(datetime(year, month, day, 0, 0, 0))
            
            occupied_hours = set()
            
            # Преобразуем занятые слоты в занятые часы
            for slot in booked_slots:
                if not slot or '-' not in slot:
                    continue
                    
                try:
                    start_str, end_str = slot.split('-')
                    start_hour = int(start_str.strip())
                    end_hour = int(end_str.strip())
                    
                    if end_hour > start_hour:
                        for hour in range(start_hour, end_hour):
                            occupied_hours.add(hour)
                    else:
                        for hour in range(start_hour, 24):
                            occupied_hours.add(hour)
                            
                except Exception as e:
                    logger.error(f"Ошибка обработки слота {slot}: {e}")
                    continue
            
            # ============================================================
            # БЛОКИРОВКА ПО ВРЕМЕНИ (ПРАВИЛА БРОНИРОВАНИЯ)
            # ============================================================
            blocked_hours = set()
            
            for hour in range(24):
                hour_datetime = target_date + timedelta(hours=hour)
                
                if is_track_creation:
                    min_hours = Config.MIN_BOOKING_ADVANCE['track_creation']  # 72 часа
                elif with_engineer:
                    min_hours = Config.MIN_BOOKING_ADVANCE['with_engineer']  # 48 часов
                else:
                    min_hours = Config.MIN_BOOKING_ADVANCE['without_engineer']  # 24 часа
                
                can_book, _ = DateTimeUtils.can_book_in_advance(
                    hour_datetime, hour, with_engineer, 
                    is_12_hours=False, is_track_creation=is_track_creation
                )
                
                if not can_book:
                    blocked_hours.add(hour)
                    logger.info(f"🔍 Час {hour:02d} заблокирован правилами (требуется {min_hours} часов)")
            
            logger.info(f"🔍 Занятые часы (брони): {sorted(occupied_hours)}")
            logger.info(f"🔍 Заблокированные часы (правила): {sorted(blocked_hours)}")
            
            # Объединяем все недоступные часы
            unavailable_hours = occupied_hours.union(blocked_hours)
            free_hours = sorted(set(range(24)) - unavailable_hours)
            
            logger.info(f"🔍 Свободные часы: {free_hours}")
            
            if not free_hours:
                logger.info(f"🔍 Нет свободных часов на {clean_date}")
                return []
            
            # Формируем интервалы
            intervals = []
            free_hours.sort()
            
            current_start = free_hours[0]
            current_end = free_hours[0]
            
            for i in range(1, len(free_hours)):
                if free_hours[i] == free_hours[i-1] + 1:
                    current_end = free_hours[i]
                else:
                    if current_end >= current_start:
                        end_hour_display = current_end + 1
                        if end_hour_display == 24:
                            end_hour_display = 24
                        
                        duration = end_hour_display - current_start
                        
                        intervals.append({
                            'start': current_start,
                            'end': end_hour_display,
                            'duration': duration
                        })
                        
                        logger.info(f"🔍 Добавлен интервал: {current_start:02d}:00-{end_hour_display:02d}:00 ({duration} часов)")
                    
                    current_start = free_hours[i]
                    current_end = free_hours[i]
            
            if current_end >= current_start:
                end_hour_display = current_end + 1
                if end_hour_display == 24:
                    end_hour_display = 24
                
                duration = end_hour_display - current_start
                
                intervals.append({
                    'start': current_start,
                    'end': end_hour_display,
                    'duration': duration
                })
                
                logger.info(f"🔍 Добавлен последний интервал: {current_start:02d}:00-{end_hour_display:02d}:00 ({duration} часов)")
            
            logger.info(f"🔍 Итоговые интервалы: {[(i['start'], i['end'], i['duration']) for i in intervals]}")
            
            return intervals
                    
        except Exception as e:
            logger.error(f"Ошибка расчета всех свободных интервалов: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def debug_free_intervals(date_str: str, is_track_creation: bool, with_engineer: bool):
        logger.info("=" * 60)
        logger.info(f"🔍 ДЕБАГ СВОБОДНЫХ ИНТЕРВАЛОВ НА ДАТУ: {date_str}")
        logger.info(f"🔍 Параметры: is_track_creation={is_track_creation}, with_engineer={with_engineer}")
        logger.info("=" * 60)
        
        result = FreeIntervalCalculator.get_max_free_interval(date_str, is_track_creation, with_engineer)
        
        logger.info(f"🔍 Результат: {result}")
        logger.info("=" * 60)
        
        return result

    @staticmethod
    def get_max_free_interval(date_str: str, is_track_creation: bool, with_engineer: bool):
        try:
            intervals = FreeIntervalCalculator.get_all_free_intervals(date_str, is_track_creation, with_engineer)
            
            if not intervals:
                return "NO_SLOTS"
            
            if is_track_creation:
                suitable_intervals = []
                
                for interval in intervals:
                    if interval['duration'] >= 4:
                        suitable_intervals.append(interval)
                    
                    elif interval['end'] == 24 and interval['start'] >= 20:
                        suitable_intervals.append(interval)
                
                if not suitable_intervals:
                    return "NO_4H_SLOT"
                
                max_interval = max(suitable_intervals, key=lambda x: x['duration'])
                return max_interval
            
            max_interval = max(intervals, key=lambda x: x['duration'])
            return max_interval
            
        except Exception as e:
            logger.error(f"Ошибка расчета свободных интервалов: {e}")
            import traceback
            traceback.print_exc()
            return "NO_SLOTS"
    
 
    @staticmethod
    def is_time_in_interval(time_str: str, interval: dict, is_track_creation: bool = False):
        try:
            if not time_str or '-' not in time_str:
                return False, "Неверный формат времени"
            
            time_str = time_str.replace(' ', '')
            
            parts = time_str.split('-')
            if len(parts) != 2:
                return False, "Неверный формат времени. Используйте час-час"
            
            start_str, end_str = parts[0].strip(), parts[1].strip()
            
            try:
                start_hour = int(start_str)
                end_hour = int(end_str)
            except ValueError:
                return False, "Часы должны быть числами"
            
            if end_hour > start_hour:
                duration = end_hour - start_hour
            elif end_hour < start_hour:
                duration = (24 - start_hour) + end_hour
            else:
                duration = 0
            
            if is_track_creation:
                if duration == 0:
                    return False, f"*❌ Для создания трека требуется ровно 4 часа! Выберите длительность 4 часа!*"
                if duration != 4:
                    return False, f"*❌ Для создания трека требуется ровно 4 часа! Выберите длительность 4 часа!*"
            else:
                if duration == 0:
                    return False, "*❌ Минимальное время записи — 1 час! Выберите длительность от 1 до 6 часов!*"
                if duration > 6:
                    return False, f"*❌ Максимальное время записи — 6 часов! Выберите длительность от 1 до 6 часов!*"
                if duration < 1:
                    return False, f"❌ Минимально 1 час! У вас: {duration} часов"
            
            interval_start = interval['start']
            interval_end = interval['end']
            
            logger.info(f"🔍 Проверка времени: {time_str} в интервале {interval_start}-{interval_end}")
            logger.info(f"   calc: {start_hour}-{end_hour}, duration: {duration}")
            logger.info(f"   interval: {interval}")
            
            if is_track_creation and end_hour <= start_hour:
                logger.info(f"🔍 Кроссночное бронирование трека: {start_hour}-{end_hour}")
                
                if interval_end == 24 and interval_start <= start_hour:
                    hours_before_midnight = 24 - start_hour
                    hours_after_midnight = end_hour
                    total_hours = hours_before_midnight + hours_after_midnight
                    
                    logger.info(f"🔍 Кроссночное: до полуночи={hours_before_midnight}ч, после={hours_after_midnight}ч, всего={total_hours}ч")
                    
                    if total_hours == 4:
                        if start_hour >= interval_start:
                            return True, ""
                        else:
                            return False, f"❌ Время должно начинаться с {interval_start:02d}:00 или позже"
                    else:
                        return False, f"*❌ Для создания трека требуется ровно 4 часа! Выберите длительность 4 часа!*"
                else:
                    return False, f"❌ Для кроссночного бронирования трека выберите время, начинающееся с {interval_start:02d}:00 или позже"
            
            if interval_end == 24:
                logger.info(f"🔍 Обработка интервала {interval_start}-24 (до полночи)")
                
                if interval_start <= start_hour < 24:
                    if end_hour <= start_hour:
                        if is_track_creation:
                            if duration == 4:
                                return True, ""
                            else:
                                return False, f"*❌ Для создания трека требуется ровно 4 часа! Выберите длительность 4 часа!*"
                        else:
                            if 1 <= duration <= 6:
                                return True, ""
                            else:
                                return False, f"❌ Длительность должна быть 1-6 часов! У вас: {duration} часов"
                    else:
                        if end_hour <= 24:
                            return True, ""
                        else:
                            return False, f"❌ Время должно быть до 24:00! Вы ввели: {end_hour}"
                else:
                    return False, f"❌ Время должно начинаться с {interval_start:02d}:00 или позже! Вы ввели: {start_hour}"
            
            else:
                logger.info(f"🔍 Обработка обычного интервала {interval_start}-{interval_end}")
                
                if end_hour <= start_hour:
                    return False, "❌ Время пересекает полночь, но интервал не позволяет этого"
                
                if interval_start <= start_hour and end_hour <= interval_end:
                    return True, ""
                else:
                    return False, f"❌ Время должно быть внутри {interval_start:02d}:00-{interval_end:02d}:00"
                            
        except Exception as e:
            logger.error(f"Ошибка проверки времени в интервале: {e}")
            import traceback
            traceback.print_exc()
            return False, "❌ Ошибка проверки времени"

class NotificationManager:
    @staticmethod
    def create_notification(booking_id: int, user_id: str, service_type: str, 
                        booking_datetime: datetime, notification_type: str, 
                        hours_before: int):
        try:
            logger.info(f"Создание уведомления: booking_id={booking_id}, тип={notification_type}")
            
            send_time = booking_datetime - timedelta(hours=hours_before)
            send_time_str = send_time.strftime('%Y-%m-%d %H:%M:%S')
            created_time = DateTimeUtils.now().strftime('%Y-%m-%d %H:%M:%S')
            
            logger.info(f"Время отправки: {send_time_str}")
            logger.info(f"Время создания: {created_time}")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id FROM notifications 
                    WHERE booking_id = ? AND notification_type = ? AND status = 'pending'
                ''', (booking_id, notification_type))
                
                existing = cursor.fetchone()
                if existing:
                    logger.info(f"Уведомление {notification_type} для записи #{booking_id} уже существует (ID: {existing[0]})")
                    return False
                
                cursor.execute('''
                    INSERT INTO notifications (
                        booking_id, user_id, service_type, notification_type,
                        status, planned_send_time, actual_send_time, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    booking_id, user_id, service_type, notification_type,
                    'pending', send_time_str, '', created_time
                ))
                
                notification_id = cursor.lastrowid
                logger.info(f"Уведомление успешно добавлено в базу (ID: {notification_id})")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка создания уведомления: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def get_pending_notifications():
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
                if not cursor.fetchone():
                    logger.warning("⚠️ Таблица notifications не существует, создаем...")
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS notifications (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            booking_id INTEGER NOT NULL,
                            user_id TEXT NOT NULL,
                            service_type TEXT NOT NULL,
                            notification_type TEXT NOT NULL,
                            status TEXT DEFAULT 'pending',
                            planned_send_time DATETIME NOT NULL,
                            actual_send_time DATETIME,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (booking_id) REFERENCES bookings (id)
                        )
                    ''')
                    conn.commit()
                    return []
                
                now = DateTimeUtils.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                    SELECT n.id, n.booking_id, n.user_id, n.service_type, 
                        n.notification_type, n.status, n.planned_send_time,
                        b.service, b.date_str, b.time_slot
                    FROM notifications n
                    LEFT JOIN bookings b ON n.booking_id = b.id
                    WHERE n.status = 'pending' 
                    AND datetime(n.planned_send_time) <= datetime(?)
                    AND b.status IN ('confirmed', 'подтвержден')
                    AND b.service NOT LIKE '%Админская%'
                    AND b.service NOT LIKE '%админская%'
                    ORDER BY n.planned_send_time ASC
                ''', (now,))
                
                pending = []
                for row in cursor.fetchall():
                    notification_data = {
                        'notification_id': row[0],
                        'booking_id': row[1],
                        'user_id': row[2],
                        'service_type': row[3],
                        'notification_type': row[4],
                        'status': row[5],
                        'planned_send_time': row[6],
                        'service': row[7] if len(row) > 7 else '',
                        'date_str': row[8] if len(row) > 8 else '',
                        'time_slot': row[9] if len(row) > 9 else ''
                    }
                    pending.append(notification_data)
                
                return pending
            
        except Exception as e:
            logger.error(f"Ошибка получения ожидающих уведомлений: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def update_notification_status(booking_id: int, notification_type: str, status: str):
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                if status == 'sent':
                    cursor.execute('''
                        DELETE FROM notifications 
                        WHERE booking_id = ? AND notification_type = ?
                    ''', (booking_id, notification_type))
                    logger.info(f"Уведомление удалено после отправки")
                else:
                    cursor.execute('''
                        DELETE FROM notifications 
                        WHERE booking_id = ? AND notification_type = ?
                    ''', (booking_id, notification_type))
                    logger.info(f"Уведомление удалено (статус: {status})")
                
                return cursor.rowcount > 0
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса уведомления: {e}")
            return False

    @staticmethod
    def cancel_notifications_for_booking(booking_id: int):
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM notifications 
                    WHERE booking_id = ?
                ''', (booking_id,))
                
                deleted = cursor.rowcount
                logger.info(f"Удалено уведомлений для записи #{booking_id}: {deleted}")
                return deleted > 0
                
        except Exception as e:
            logger.error(f"Ошибка удаления уведомлений: {e}")
            return False

class KeyboardManager:
    """Менеджер клавиатур для бота"""
    
    @staticmethod
    def get_main_menu_and_back_keyboard():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True)
    
    @staticmethod
    def get_main_menu_only_keyboard():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True)
    
    @staticmethod
    def get_main_keyboard(user=None):
        user_id = user.id if user else None
        
        keyboard = [
            ["🎤 Записаться в студию", "📅 Мои записи"],
            ["👤 Мой профиль", "🔔 Напоминания"],
            ["🏆 Достижения", "🎁 Промокоды"],
            ["👥 Рефералы", "📈 Мой уровень"],
            ["❓ Помощь", "❗️ Полезная информация"],
            ["🏆 Топ пользователей"],
        ]
        
        if user_id and user_id in Config.ADMIN_IDS:
            keyboard.append(["👑 Создать запись", "👑 Отменить запись"])
            keyboard.append(["👑 Заблокировать", "👑 Выдать достижение"])
            keyboard.append(["👑 Удалить достижение", "👑 Пластинки"])
            keyboard.append(["👑 Профиль", "👑 Выручка"])
            keyboard.append(["👑 Создать промокод", "👑 Удалить промокод"])
        
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def get_services():
        return ReplyKeyboardMarkup([
            ["🎤 Запись вокала", "🎸 Запись инструментов"],
            ["⏰ 12-часовая аренда", "🎚️ Сведение/мастеринг"],
            ["🎵 Создание трека", "🎹 Аранжировка/Биты"],
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True)
    
    @staticmethod
    def get_engineer_options():
        return ReplyKeyboardMarkup([
            ["👨‍🔧 С инженером", "💪 Без инженера"],
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True)
    
    @staticmethod
    def get_contact_request():
        """Клавиатура с кнопками слева и справа для ввода контакта"""
        contact_button = KeyboardButton("📲 Отправить контакт", request_contact=True)
        return ReplyKeyboardMarkup([
            [contact_button, "✏️ Ввести вручную"],  # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_text_contact_input():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_mixing():
        return ReplyKeyboardMarkup([
            ["🎵 Трек", "💿 Альбом"],                # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_track_creation_options():
        return ReplyKeyboardMarkup([
            ["🎵 Трек", "💿 Альбом"],                # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_12_hours_options():
        return ReplyKeyboardMarkup([
            ["☀️ День (9-21)", "🌙 Ночь (21-9)"],   # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_dates(service_type="vocal", with_engineer=False):
        dates = DateTimeUtils.get_future_dates(Config.MAX_BOOKING_DAYS)
        
        colored_dates = []
        for date_str in dates:
            color = DateColorAnalyzer.get_color_for_date(date_str, service_type, with_engineer)
            colored_date = f"{color} {date_str}"
            colored_dates.append(colored_date)
        
        keyboard = []
        for i in range(0, len(colored_dates), 2):
            row = colored_dates[i:i+2]
            keyboard.append(row)
        
        keyboard.append(["↩️ Главное меню", "↩️ Назад"])  # ← КНОПКИ СЛЕВА И СПРАВА
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def get_confirmation():
        return ReplyKeyboardMarkup([
            ["✅ Всё верно, отправить", "✏️ Исправить данные"],  # ← КНОПКИ СЛЕВА И СПРАВА
            ["❌ Отменить"]                                       # ← ЦЕНТР
        ], resize_keyboard=True)
    
    @staticmethod
    def get_back_only():
        return ReplyKeyboardMarkup([["↩️ Назад"]], resize_keyboard=True)
    
    @staticmethod
    def get_time_input():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_user_id_input():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_record_type():
        return ReplyKeyboardMarkup([
            ["📝 Договорная запись", "🎤 Запись в студии"],  # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню", "↩️ Назад"]                 # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_price_input():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_confirmation():
        return ReplyKeyboardMarkup([
            ["✅ Да, создать запись", "✏️ Исправить данные"],  # ← КНОПКИ СЛЕВА И СПРАВА
            ["❌ Отменить", "↩️ Назад"]                       # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_back_only():
        return ReplyKeyboardMarkup([["↩️ Назад"]], resize_keyboard=True)
    
    @staticmethod
    def get_admin_achievement_back():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_promo_keyboard():
        return ReplyKeyboardMarkup([
            ["🎟 Ввести промокод"],
            ["↩️ Главное меню", "↩️ Назад"]         # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_referral_keyboard():
        return ReplyKeyboardMarkup([
            ["👥 Мои рефералы", "🎟 Ввести код друга"],  # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню", "↩️ Назад"]             # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    # ===== МЕТОДЫ ДЛЯ ПРОМОКОДОВ (INLINE-КЛАВИАТУРЫ) =====
    @staticmethod
    def get_promo_main_menu():
        """Главное меню промокодов (inline-клавиатура)"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🎟 Ввести промокод", callback_data="promo_enter")],
            [InlineKeyboardButton("📋 Ваш промокод", callback_data="promo_show_my")]
        ])
    
    @staticmethod
    def get_promo_back_only():
        """Кнопка возврата в меню промокодов (inline-клавиатура)"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Назад", callback_data="promo_back_to_main")]
        ])
    
    # ===== МЕТОДЫ ДЛЯ СОЗДАНИЯ ПРОМОКОДОВ (АДМИНСКИЕ) =====
    @staticmethod
    def get_admin_promo_type_keyboard():
        return ReplyKeyboardMarkup([
            ["💰 % на все", "🎯 % на услугу"],           # ← КНОПКИ СЛЕВА И СПРАВА
            ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"], # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню", "↩️ Назад"]              # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_promo_service_keyboard():
        return ReplyKeyboardMarkup([
            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
            ["🎚️ Сведение", "🎵 Создание трека"],
            ["↩️ Главное меню", "↩️ Назад"]              # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_promo_duration_keyboard():
        return ReplyKeyboardMarkup([
            ["♾️ Бессрочный", "⏱️ Временный"],          # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню", "↩️ Назад"]              # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_promo_confirm_keyboard():
        return ReplyKeyboardMarkup([
            ["✅ Да, создать промокод", "✏️ Исправить данные"],  # ← КНОПКИ СЛЕВА И СПРАВА
            ["❌ Отменить"]                                      # ← ЦЕНТР
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_promo_delete_type_keyboard():
        return ReplyKeyboardMarkup([
            ["🌍 Общий промокод", "👤 Персональный промокод"],  # ← КНОПКИ СЛЕВА И СПРАВА
            ["↩️ Главное меню"]
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_promo_delete_user_keyboard():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]              # ← КНОПКИ СЛЕВА И СПРАВА
        ], resize_keyboard=True)
    
    @staticmethod
    def get_admin_promo_delete_back_keyboard():
        return ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True)

async def get_booking_info(booking_id: int):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, service, date_str, time_slot, status, telegram_id, price
                FROM bookings 
                WHERE id = ?
            ''', (booking_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            booking_info = {
                'booking_id': booking_id,
                'db_booking_id': row[0],
                'name': row[1],
                'service': row[2],
                'date': row[3],
                'time': row[4],
                'status': row[5],
                'user_id': row[6],
                'price': row[7]
            }
            
            return booking_info
            
    except Exception as e:
        logger.error(f"Ошибка получения информации о бронировании: {e}")
        return None

async def send_notification_message(context, user_id: str, booking_info: dict, hours_before: int):
    """
    Отправляет уведомление о предстоящей записи в студию.
    booking_info должен содержать: booking_id, service, date, time, price, with_engineer
    """
    try:
        booking_id = booking_info.get('booking_id', 'N/A')
        service = booking_info.get('service', '')
        date_str = booking_info.get('date', '')
        time_str = booking_info.get('time', '')
        price = booking_info.get('price', '')
        with_engineer = booking_info.get('with_engineer', False)
        
        hours_text = PriceCalculator.format_hours_ru(hours_before)
        
        service_lower = service.lower() if service else ""
        
        # ===== ТОЛЬКО ЗАПИСИ В СТУДИЮ =====
        
        # 1. АРЕНДА
        if 'аренд' in service_lower or '12-час' in service_lower:
            message = (
                f"*🔔 Напоминание о записи*\n\n"
                f"*📋 Детали записи:*\n"
                f"• Услуга: 12-часовая аренда\n"
                f"• Дата: {date_str}\n"
                f"• Время: {time_str}\n"
                f"• До начала осталось: {hours_text}\n"
                f"• ID записи: #{int(booking_id)}\n\n"
                f"*📍 Адрес студии: Садовая ул., 91*\n"
                f"*📱 Контакты: @mothman32*\n\n"
                f"*✨ Если у вас изменились планы, пожалуйста, свяжитесь с администратором!*"
            )
        
        # 2. СОЗДАНИЕ ТРЕКА
        elif 'создание трека' in service_lower:
            message = (
                f"*🔔 Напоминание о записи*\n\n"
                f"*📋 Детали записи:*\n"
                f"• Услуга: Создание трека\n"
                f"• Дата: {date_str}\n"
                f"• Время: {time_str}\n"
                f"• До начала осталось: {hours_text}\n"
                f"• ID записи: #{int(booking_id)}\n\n"
                f"*📍 Адрес студии: Садовая ул., 91*\n"
                f"*📱 Контакты: @mothman32*\n\n"
                f"*✨ Если у вас изменились планы, пожалуйста, свяжитесь с администратором!*"
            )
        
        # 3. ЗАПИСЬ ВОКАЛА (С ИНЖЕНЕРОМ)
        elif 'вокал' in service_lower and with_engineer:
            message = (
                f"*🔔 Напоминание о записи*\n\n"
                f"*📋 Детали записи:*\n"
                f"• Услуга: Запись вокала (с инженером)\n"
                f"• Дата: {date_str}\n"
                f"• Время: {time_str}\n"
                f"• До начала осталось: {hours_text}\n"
                f"• ID записи: #{int(booking_id)}\n\n"
                f"*📍 Адрес студии: Садовая ул., 91*\n"
                f"*📱 Контакты: @mothman32*\n\n"
                f"*✨ Если у вас изменились планы, пожалуйста, свяжитесь с администратором!*"
            )
        
        # 4. ЗАПИСЬ ВОКАЛА (БЕЗ ИНЖЕНЕРА)
        elif 'вокал' in service_lower and not with_engineer:
            message = (
                f"*🔔 Напоминание о записи*\n\n"
                f"*📋 Детали записи:*\n"
                f"• Услуга: Запись вокала (без инженера)\n"
                f"• Дата: {date_str}\n"
                f"• Время: {time_str}\n"
                f"• До начала осталось: {hours_text}\n"
                f"• ID записи: #{int(booking_id)}\n\n"
                f"*📍 Адрес студии: Садовая ул., 91*\n"
                f"*📱 Контакты: @mothman32*\n\n"
                f"*✨ Если у вас изменились планы, пожалуйста, свяжитесь с администратором!*"
            )
        
        # 5. ЗАПИСЬ ИНСТРУМЕНТОВ (С ИНЖЕНЕРОМ)
        elif 'инструмент' in service_lower and with_engineer:
            message = (
                f"*🔔 Напоминание о записи*\n\n"
                f"*📋 Детали записи:*\n"
                f"• Услуга: Запись инструментов (с инженером)\n"
                f"• Дата: {date_str}\n"
                f"• Время: {time_str}\n"
                f"• До начала осталось: {hours_text}\n"
                f"• ID записи: #{int(booking_id)}\n\n"
                f"*📍 Адрес студии: Садовая ул., 91*\n"
                f"*📱 Контакты: @mothman32*\n\n"
                f"*✨ Если у вас изменились планы, пожалуйста, свяжитесь с администратором!*"
            )
        
        # 6. ЗАПИСЬ ИНСТРУМЕНТОВ (БЕЗ ИНЖЕНЕРА)
        elif 'инструмент' in service_lower and not with_engineer:
            message = (
                f"*🔔 Напоминание о записи*\n\n"
                f"*📋 Детали записи:*\n"
                f"• Услуга: Запись инструментов (без инженера)\n"
                f"• Дата: {date_str}\n"
                f"• Время: {time_str}\n"
                f"• До начала осталось: {hours_text}\n"
                f"• ID записи: #{int(booking_id)}\n\n"
                f"*📍 Адрес студии: Садовая ул., 91*\n"
                f"*📱 Контакты: @mothman32*\n\n"
                f"*✨ Если у вас изменились планы, пожалуйста, свяжитесь с администратором!*"
            )
        
        await context.bot.send_message(
            chat_id=int(user_id),
            text=message,
            parse_mode="Markdown"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")
        return False

async def process_notifications(context: ContextTypes.DEFAULT_TYPE):
    """Обработка уведомлений - отправляет только для подтвержденных записей"""
    try:
        logger.info("=" * 60)
        logger.info("ЗАПУСК ПРОВЕРКИ УВЕДОМЛЕНИЙ")
        
        pending = NotificationManager.get_pending_notifications()
        logger.info(f"Найдено уведомлений для отправки: {len(pending)}")
        
        if not pending:
            return
        
        for notification in pending:
            try:
                booking_id = notification['booking_id']
                user_id = notification['user_id']
                notification_type = notification['notification_type']
                
                booking_info = await get_booking_info(int(booking_id))
                
                if not booking_info:
                    logger.info(f"Запись #{booking_id} не найдена, удаляем уведомление")
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM notifications WHERE booking_id = ? AND notification_type = ?', 
                                     (booking_id, notification_type))
                    continue
                
                status = booking_info.get('status', '').lower()
                
                # Отправляем только для подтвержденных записей
                if 'confirmed' not in status and 'подтвержден' not in status:
                    logger.info(f"Запись #{booking_id} не подтверждена (статус: {status}), удаляем уведомление")
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM notifications WHERE booking_id = ? AND notification_type = ?', 
                                     (booking_id, notification_type))
                    continue
                
                try:
                    hours_before = int(notification_type.split('h_')[0])
                except:
                    hours_before = 0
                
                logger.info(f"Отправка уведомления за {hours_before} часов")
                
                success = await send_notification_message(context, user_id, booking_info, hours_before)
                
                if success:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM notifications WHERE booking_id = ? AND notification_type = ?', 
                                     (booking_id, notification_type))
                    logger.info(f"✅ Уведомление отправлено и удалено из базы")
                else:
                    logger.error(f"❌ Ошибка отправки уведомления, оставляем для повторной попытки")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка обработки уведомления: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Ошибка обработки уведомлений: {e}")
        import traceback
        traceback.print_exc()

def handle_errors_with_rate_limit(func):
    @wraps(func)
    async def wrapper(update: Update, context, *args, **kwargs):
        try:
            user_id = str(update.effective_user.id)
            
            if update.effective_user.id in Config.ADMIN_IDS:
                return await func(update, context, *args, **kwargs)
            
            is_allowed, message, seconds_to_wait = RateLimiter.check_rate_limit(
                user_id, 
                limit=Config.RATE_LIMIT, 
                period=60
            )
            
            if not is_allowed:
                if update.message:
                    if seconds_to_wait and seconds_to_wait > 60:
                        await update.message.reply_text(
                            f"⏰ {message}\n\n"
                            f"Пожалуйста, подождите {int(seconds_to_wait)} секунд перед следующим запросом.",
                            parse_mode="Markdown"
                        )
                return
            
            return await func(update, context, *args, **kwargs)
        except telegram.error.Forbidden:
            return ConversationHandler.END
        except telegram.error.TimedOut:
            if update and update.message:
                await update.message.reply_text(
                    "⏳ Превышено время ожидания. Попробуйте еще раз.",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                )
            return ConversationHandler.END
        except Exception as e:
            return ConversationHandler.END
    return wrapper

async def handle_main_menu_button(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    username = update.effective_user.username or "Неизвестный"
    
    logger.info(f"🔍 Пользователь {user_id} (@{username}) нажал 'Главное меню'. Очистка данных.")
    
    context.user_data.pop('visible_booking_ids', None)
    
    context.user_data.clear()
    context.user_data.pop('_conversation_state', None)
    
    menu_message = (
        '*🏠 Возвращаемся в главное меню*\n\n'
        '*👇 Выберите подходящий вариант:*'
    )
    
    await update.message.reply_text(
        menu_message,
        reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END

async def check_user_blocked(update: Update, context) -> bool:
    """Проверяет, заблокирован ли пользователь. Если да - отправляет сообщение и возвращает True"""
    user_id = update.effective_user.id
    
    if user_id in Config.ADMIN_IDS:
        return False
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_blocked, blocked_until FROM users WHERE telegram_id = ?
            ''', (str(user_id),))
            
            result = cursor.fetchone()
            if not result:
                return False
            
            is_blocked, blocked_until = result
            
            if is_blocked == 1:
                if blocked_until:
                    try:
                        blocked_time = datetime.strptime(blocked_until, '%Y-%m-%d %H:%M:%S')
                        now_moscow = to_moscow_time()
                        
                        if blocked_time > now_moscow:
                            time_left = blocked_time - now_moscow
                            days = time_left.days
                            hours = time_left.seconds // 3600
                            minutes = (time_left.seconds % 3600) // 60
                            
                            time_text = format_duration(days, hours, minutes)
                            
                            await update.message.reply_text(
                                f"*🔒 Вы заблокированы!*\n\n"
                                f"*⏳ До разблокировки осталось: {time_text}*\n\n"
                                f"*📞 По вопросам обращайтесь к администратору: @mothman32*",
                                parse_mode="Markdown"
                            )
                            return True
                        else:
                            # Автоматически разблокируем при попытке действия
                            cursor.execute('''
                                UPDATE users 
                                SET is_blocked = 0, blocked_until = NULL 
                                WHERE telegram_id = ?
                            ''', (str(user_id),))
                            conn.commit()
                            logger.info(f"✅ Пользователь {user_id} автоматически разблокирован при попытке действия")
                            return False
                    except Exception as e:
                        logger.error(f"Ошибка парсинга времени блокировки: {e}")
                        await update.message.reply_text(
                            f"*🔒 Вы заблокированы!*\n\n"
                            f"*⏳ Тип блокировки: Навсегда*\n\n"
                            f"*📞 По вопросам обращайтесь к администратору: @mothman32*",
                            parse_mode="Markdown"
                        )
                        return True
                else:
                    await update.message.reply_text(
                        f"*🔒 Вы заблокированы!*\n\n"
                        f"*⏳ Тип блокировки: Навсегда*\n\n"
                        f"*📞 По вопросам обращайтесь к администратору: @mothman32*",
                        parse_mode="Markdown"
                    )
                    return True
    except Exception as e:
        logger.error(f"Ошибка проверки блокировки: {e}")
        return False
    
    return False

@handle_errors_with_rate_limit
async def help_handler(update: Update, context):
    """Показывает информацию о помощи"""
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    message = (
        "*❓ Помощь*\n\n"
        "*Как пользоваться сервисом:*\n"
        "• Записаться в студию — создание новой записи\n"
        "• Мои записи — просмотр и отмена записей\n"
        "• Мой профиль — информация о пользователе\n"
        "• Напоминания — просмотр уведомлений\n"
        "• Достижения — список выполненных достижений\n"
        "• Промокоды — активация промокодов\n"
        "• Рефералы — реферальная программа\n"
        "• Мой уровень — прогресс и скидки\n"
        "• Топ пользователей — рейтинг по пластинкам\n\n"
        "*Сервис находится в бета-тестировании:*\n"
        "• Возможны небольшие ошибки\n"
        "• Мы постоянно улучшаем сервис\n"
        "• Ваши отзывы помогают нам стать лучше\n\n"
        "*По техническим вопросам:* @mothman32\n"
        "*Администратор:* @mothman32\n\n"
        "*Адрес студии:* Садовая ул., 91"
    )
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
    )

@handle_errors_with_rate_limit
async def useful_info_handler(update: Update, context):
    """Показывает полезную информацию с файлом"""
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    file_path = "Полезная_информация.docx"
    
    # ===== ТЕКСТОВОЕ СООБЩЕНИЕ =====
    message = (
        "*❗️ Полезная информация*\n\n"
        "*В этом документе собрана вся полезная информация о студии:*\n"
        "• Адрес и контакты\n"
        "• Режим работы\n"
        "• Оборудование студии\n"
        "• Полный прайс-лист\n"
        "• Правила бронирования\n"
        "• Условия отмены"
    )
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown"
    )
    
    # ===== ФАЙЛ =====
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, 'rb') as doc:
                await update.message.reply_document(
                    document=doc,
                    filename="Полезная_информация.docx",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)  # ← КЛАВИАТУРА ЗДЕСЬ!
                )
        else:
            await update.message.reply_text(
                "❌ Файл с информацией временно недоступен.",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
    except Exception as e:
        logger.error(f"❌ Ошибка отправки файла: {e}")
        await update.message.reply_text(
            "❌ Не удалось загрузить файл. Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

@handle_errors_with_rate_limit
async def start(update: Update, context):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or ""
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (user_id,))
        existing_user = cursor.fetchone()
        
        if not existing_user:
            unique_id = f"MC{int(time.time())}{user_id[-6:]}"
            registration_date = DateTimeUtils.now().strftime('%d.%m.%Y')
            referral_code = AchievementSystem.generate_referral_code(user_id)
            
            cursor.execute('''
                INSERT INTO users 
                (telegram_id, username, unique_id, registration_date, referral_code, vinyls, level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, unique_id, registration_date, referral_code, 0, 1))
            
            try:
                CouponManager.add_level_coupons(user_id, 1, db_conn=conn)
                logger.info(f"✅ Новый пользователь {user_id} зарегистрирован с купоном уровня 1 (50%)")
            except Exception as e:
                logger.error(f"❌ Ошибка добавления купона: {e}")
            
            conn.commit()
            logger.info(f"✅ Новый пользователь {user_id} зарегистрирован")
        else:
            logger.info(f"👤 Существующий пользователь {user_id} - пропускаем выдачу купона")
    
    # Путь к фото для приветствия
    welcome_photo_path = "photos/welcome.jpg"
    
    # Текст приветствия (ИСПРАВЛЕН)
    welcome_text = (
        "*🎙️ Добро пожаловать в студию Godspeed Records!*\n\n"
        "*✨ Профессиональная студия звукозаписи в самом сердце Санкт-Петербурга*\n\n"
        "*🎧 Чем можем вам помочь:*\n"
        "• Запись вокала и инструментов\n"
        "• Аренда студии на 12 часов\n"
        "• Сведение и мастеринг\n"
        "• Создание треков с нуля\n"
        "• Эксклюзивные биты и аранжировки\n\n"
        "*🏆 Новая система достижений!*\n"
        "• Получайте пластинки за записи\n"
        "• Открывайте уровни и скидки\n"
        "• Приводите друзей и зарабатывайте\n\n"
        "*⚠️ Сервис находится в бета-тестировании:*\n"
        "• Возможны небольшие ошибки\n"
        "• Мы постоянно улучшаем сервис\n"
        "• Ваши отзывы помогают нам стать лучше\n\n"
        "*🛠 По техническим вопросам: @mothman32*\n\n"
        "*👇 Выберите подходящий вариант:*"
    )
    
    try:
        # Отправляем фото с подписью
        with open(welcome_photo_path, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=welcome_text,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
    except FileNotFoundError:
        # Если фото не найдено, отправляем только текст
        logger.warning(f"⚠️ Приветственное фото не найдено: {welcome_photo_path}")
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
    except Exception as e:
        logger.error(f"❌ Ошибка отправки приветственного фото: {e}")
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
    
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def fix_my_coupons(update: Update, context):
    """Добавляет купоны текущему пользователю"""
    user_id = str(update.effective_user.id)
    
    try:
        # Добавляем купон уровня 1
        CouponManager.add_level_coupons(user_id, 1)
        
        # Проверяем, добавился ли купон
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM user_coupons WHERE user_id = ?', (user_id,))
            count = cursor.fetchone()[0]
        
        await update.message.reply_text(
            f"✅ Купоны уровня 1 добавлены!\n\n"
            f"📊 Теперь у вас есть {count} активных купонов.\n\n"
            f"Нажмите '📈 Мой уровень' чтобы проверить.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка добавления купонов: {e}")
        await update.message.reply_text(
            f"❌ Ошибка: {e}\n\n"
            f"Обратитесь к администратору @mothman32",
            parse_mode="Markdown"
        )

@handle_errors_with_rate_limit
async def check_coupons_table(update: Update, context):
    """Проверяет таблицу купонов (только для админа)"""
    user_id = str(update.effective_user.id)
    
    if user_id not in [str(admin_id) for admin_id in Config.ADMIN_IDS]:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    args = context.args
    target_id = args[0] if args else user_id
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_coupons'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            await update.message.reply_text("❌ Таблица user_coupons не существует! Нужно выполнить миграцию.")
            return
        
        # Получаем купоны пользователя
        cursor.execute('''
            SELECT id, level, discount_percent, remaining_uses, is_permanent, created_at
            FROM user_coupons WHERE user_id = ?
        ''', (target_id,))
        rows = cursor.fetchall()
        
        if rows:
            message = f"📊 Купоны пользователя {target_id}:\n\n"
            for row in rows:
                perm = "вечная" if row[4] else f"{row[3]} использований"
                message += f"• Уровень {row[1]}: {row[2]}% ({perm})\n"
            await update.message.reply_text(message, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ У пользователя {target_id} нет купонов!")

@handle_errors_with_rate_limit
async def achievements_handler(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    user_id = str(update.effective_user.id)
    
    achievements_text = AchievementSystem.format_achievements_list(user_id)
    
    await update.message.reply_text(
        achievements_text,
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
    )
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def level_handler(update: Update, context: CallbackContext) -> int:
    """Обработчик команды /level - отображение информации об уровне пользователя"""
    
    user_id = str(update.effective_user.id)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT vinyls, level, permanent_discount, temporary_discount, discount_expiry
            FROM users WHERE telegram_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        
        if not result:
            vinyls = 0
            level = 1
        else:
            vinyls = result[0] or 0
            level = result[1] or 1
        
        level_info = AchievementSystem.get_level_info(vinyls)
        
        # Получаем активные купоны пользователя
        active_coupons = CouponManager.get_user_coupons(user_id)
        active_levels = {coupon['level'] for coupon in active_coupons}
        
        # ===== ФОРМИРУЕМ ТЕКСТ В НУЖНОМ ПОРЯДКЕ =====
        text = f"*📈 Мой уровень*\n\n"
        
        # 1. ВСЕ УРОВНИ (сверху)
        text += f"*Все уровни:*\n"
        for lvl in AchievementSystem.LEVELS:
            emoji = "✅ " if lvl['level'] in active_levels else ""
            medal = "🥇" if lvl['level'] == 1 else "🏅" if lvl['level'] == 2 else "🎖" if lvl['level'] == 3 else "👑"
            
            text += f"{emoji}{medal} {lvl['name']} — {lvl['discount']}%"
            
            if lvl['discount_type'] == 'permanent':
                text += f" (вечная)\n"
            else:
                text += f" ({lvl['uses']} раз)\n"
        
        text += "\n"
        
        # 2. СЛЕДУЮЩИЙ УРОВЕНЬ
        text += f"*Следующий уровень:*\n"
        if level_info['next_level_name']:
            text += f"• {level_info['next_level_name']}\n"
            text += f"• Нужно пластинок: {level_info['vinyls_needed_next']}\n"
            text += f"• Прогресс: {level_info['progress_percent']}%\n\n"
        else:
            text += f"• Достигнут максимальный уровень!\n\n"
        
        # 3. СТАТИСТИКА (внизу)
        text += f"*Статистика:*\n"
        text += f"• Пластинок: {vinyls}\n"
        text += f"• Текущий уровень: {level_info['current_level_name']}\n"
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

@handle_errors_with_rate_limit
async def top_vinyls_handler(update: Update, context):
    """Показывает топ-10 пользователей по пластинкам"""
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    current_user_display = None
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT username, unique_id, telegram_id FROM users WHERE telegram_id = ?', (str(user_id),))
            current_user = cursor.fetchone()
            if current_user:
                current_user_data = {
                    'username': current_user[0],
                    'unique_id': current_user[1],
                    'telegram_id': current_user[2]
                }
                current_user_display = get_user_display_name(current_user_data)
            
            cursor.execute('''
                SELECT 
                    username,
                    unique_id,
                    telegram_id,
                    vinyls,
                    level
                FROM users 
                WHERE vinyls > 0
                ORDER BY vinyls DESC, level DESC
                LIMIT 10
            ''')
            
            top_users = cursor.fetchall()
            
            if not top_users:
                await update.message.reply_text(
                    "*📭 Пока нет пользователей с пластинками*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                )
                return
            
            message = "*🏆 Топ пользователей*\n\n"
            
            medals = ["🥇", "🥈", "🥉"]
            
            for i, user in enumerate(top_users, 1):
                (username, unique_id, telegram_id, vinyls, level) = user
                
                user_data = {
                    'username': username,
                    'unique_id': unique_id,
                    'telegram_id': telegram_id
                }
                display_name = get_user_display_name(user_data)
                safe_display_name = SecurityUtils.safe_markdown_text(display_name)
                
                if i <= 3:
                    medal = medals[i-1]
                else:
                    medal = f"{i}."
                
                is_current = " ⬅️" if display_name == current_user_display else ""
                
                message += f"{medal} *{safe_display_name}* — {vinyls} 💿{is_current}\n"
            
            message += "\n"
            
            if current_user_display:
                cursor.execute('''
                    SELECT vinyls, level,
                           (SELECT COUNT(*) + 1 FROM users WHERE vinyls > u.vinyls) as rank
                    FROM users u
                    WHERE telegram_id = ?
                ''', (str(user_id),))
                
                user_stats = cursor.fetchone()
                if user_stats:
                    user_vinyls, user_level, user_rank = user_stats
                    
                    if user_vinyls > 0:
                        message += f"*Статистика:*\n"
                        message += f"• Место: {user_rank}\n"
                        message += f"• Пластинок: {user_vinyls}\n\n"
                    else:
                        message += f"*💡 У вас пока нет пластинок*\n\n"
            
            message += "*Как получить пластинки:*\n"
            message += "• Запись в студии — +25 пластинок\n"
            message += "• Пригласить друга — +25 пластинок\n"
            message += "• Выполнить достижения — от 1000+ пластинок"
            
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            
    except Exception as e:
        logger.error(f"Ошибка в top_vinyls_handler: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "*❌ Ошибка загрузки топа пластинок*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

@handle_errors_with_rate_limit
async def promo_main_menu(update: Update, context, edit_mode: bool = False, query=None):
    """Главное меню промокодов - показывает ТОЛЬКО доступные для пользователя"""
    user_id = str(update.effective_user.id)
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data.pop('awaiting_promo_code', None)
    
    all_promos = PromoCodeManager.get_all_active_promos(user_id)
    
    if all_promos:
        permanent_promos = []
        temporary_promos = []
        
        for promo in all_promos:
            if promo.get('expiry_date'):
                temporary_promos.append(promo)
            else:
                permanent_promos.append(promo)
        
        message = "*🎁 Доступные промокоды*\n\n"
        
        if permanent_promos:
            message += "*♾️ Бессрочные:*\n"
            for promo in permanent_promos:
                promo_text = PromoCodeManager.format_promo_info(promo)
                message += f"• `{promo['code']}` — {promo_text}\n"
            message += "\n"
        
        if temporary_promos:
            message += "*⏱️ Временные:*\n"
            for promo in temporary_promos:
                promo_text = PromoCodeManager.format_promo_info(promo)
                expiry_text = PromoCodeManager.format_expiry_date(promo['expiry_date'])
                message += f"• `{promo['code']}` — {promo_text}{expiry_text}\n"
            message += "\n"
        
        message += "*👇 Чтобы активировать промокод, нажмите кнопку ниже:*"
    else:
        message = (
            f"*🎁 Доступные промокоды*\n\n"
            f"*📭 У Вас нет доступных промокодов*\n\n"
        )
    
    if edit_mode and query:
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_promo_main_menu()
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_promo_main_menu()
        )

@handle_errors_with_rate_limit
async def promo_callback_handler(update: Update, context):
    """Обработчик inline-кнопок промокодов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(update.effective_user.id)
    
    if await check_user_blocked(update, context):
        return
    
    if data == "promo_enter":
        context.user_data['awaiting_promo_code'] = True
        
        await query.edit_message_text(
            text=(
                f"*🎟 Введите промокод*\n\n"
                f"*Чтобы активировать промокод, напишите:*\n"
                f"`promo КОД`\n\n"
                f"*Пример:* `promo ABCD10`\n\n"
                f"*✏️ Просто отправьте сообщение в чат*"
            ),
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_promo_back_only()
        )
        
    elif data == "promo_show_my":
        active_promo = PromoCodeManager.get_user_active_promo(user_id)
        
        if not active_promo:
            message = (
                "*📋 Ваш активированный промокод*\n\n"
                "*📭 У Вас нет активированного промокода*"
            )
        else:
            promo_text = PromoCodeManager.format_promo_info(active_promo)
            expiry_text = PromoCodeManager.format_expiry_date(active_promo.get('expiry_date'))
            
            message = (
                f"*📋 Ваш активированный промокод*\n\n"
                f"*✅ Активный промокод:*\n"
                f"• `{active_promo['code']}` — {promo_text}{expiry_text}"
            )
        
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_promo_back_only()
        )
        
    elif data == "promo_back_to_main":
        context.user_data.pop('awaiting_promo_code', None)
        await promo_main_menu(update, context, edit_mode=True, query=query)

@handle_errors_with_rate_limit
async def process_promo_code_message(update: Update, context):
    """Обработка введённого промокода"""
    
    user_id = str(update.effective_user.id)
    
    if await check_user_blocked(update, context):
        context.user_data.pop('awaiting_promo_code', None)
        return
    
    text = update.message.text.strip()
    
    if text in ["↩️ Главное меню", "↩️ Назад"]:
        context.user_data.pop('awaiting_promo_code', None)
        await promo_main_menu(update, context)
        return
    
    if not text.lower().startswith('promo '):
        error_message = (
            f"*❌ Неверный формат!*\n\n"
            f"*Правильный формат:* `promo КОД`\n"
            f"*Пример:* `promo ABCD12`\n\n"
            f"*💡 Промокод можно ввести только через команду `promo КОД`*"
        )
        
        await update.message.reply_text(
            error_message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_promo_main_menu()
        )
        return
    
    code = text[5:].strip().upper()
    logger.info(f"🔍 Попытка активации промокода: '{code}' от пользователя {user_id}")
    
    success, result_code, promo_info = await PromoCodeManager.activate_promo_code(user_id, code, context)
    
    if success:
        context.user_data.pop('awaiting_promo_code', None)
        promo_text = PromoCodeManager.format_promo_info(promo_info)
        
        await update.message.reply_text(
            f"*✅ Промокод активирован!*\n\n"
            f"🎟 Код: `{code}`\n"
            f"🎁 Бонус: {promo_text}\n\n"
            f"*✨ Скидка будет применена автоматически при следующей записи!*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        
        logger.info(f"✅ Пользователь {user_id} активировал промокод {code}")
        
    else:
        if result_code == "NOT_FOUND":
            error_message = (
                f"*❌ Промокод не найден!*"
            )
            
        elif result_code == "EXPIRED":
            expiry = promo_info.get('expiry', 'неизвестно')
            error_message = (
                f"*❌ Промокод истёк!*"
            )
            
        elif result_code == "NOT_YOURS":
            error_message = (
                f"*❌ Промокод не принадлежит вам!*"
            )
            
        elif result_code == "ALREADY_USED":
            active_promo = promo_info.get('active_promo', 'неизвестно')
            error_message = (
                f"*❌ Нельзя активировать больше 1 промокода!*"
            )
            
        elif result_code == "ALREADY_USED_BEFORE":
            error_message = (
                f"*❌ Вы уже использовали этот промокод ранее!*"
            )
            
        else:
            error_message = (
                f"*❌ Ошибка активации!*"
            )
        
        await update.message.reply_text(
            error_message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_promo_main_menu()
        )
    
    context.user_data.pop('awaiting_promo_code', None)

def format_currency(amount):
    """Форматирует число в валюту"""
    return f"{amount:,}₽".replace(',', ' ')

async def calculate_and_show_revenue(update: Update, context, start_date, end_date, period_name):
    """Рассчитывает выручку за период"""
    
    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            user_id = query.from_user.id
            message = query.message
            is_callback = True
        else:
            user_id = update.effective_user.id
            message = update.message
            is_callback = False
        
        if user_id not in Config.ADMIN_IDS:
            error_text = "❌ У вас нет прав для просмотра выручки!"
            if is_callback:
                await query.edit_message_text(text=error_text, parse_mode="Markdown")
            else:
                await update.message.reply_text(error_text, parse_mode="Markdown")
            return
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            if start_date:
                start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
                end_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                    SELECT id, timestamp, name, service, price, date_str, time_slot,
                           is_12_hours, twelve_hours_type, is_mixing, is_track_creation,
                           with_engineer, duration, start_hour, end_hour, status,
                           is_contractual, is_admin_booking
                    FROM bookings 
                    WHERE datetime(timestamp) >= datetime(?)
                    AND datetime(timestamp) <= datetime(?)
                    ORDER BY timestamp DESC
                ''', (start_str, end_str))
            else:
                cursor.execute('''
                    SELECT id, timestamp, name, service, price, date_str, time_slot,
                           is_12_hours, twelve_hours_type, is_mixing, is_track_creation,
                           with_engineer, duration, start_hour, end_hour, status,
                           is_contractual, is_admin_booking
                    FROM bookings 
                    ORDER BY timestamp DESC
                ''')
            
            bookings = cursor.fetchall()
            
            total_revenue = 0
            counted_bookings = []
            skipped_bookings = []
            
            for booking in bookings:
                (booking_id, timestamp, name, service, price, date_str, time_slot,
                 is_12_hours, twelve_hours_type, is_mixing, is_track_creation,
                 with_engineer, duration, start_hour, end_hour, status,
                 is_contractual, is_admin_booking) = booking
                
                booking_price = 0
                
                # Получаем цену
                if price and price != '0' and price != 'Договорная' and 'договорная' not in str(price).lower():
                    try:
                        booking_price = int(''.join(filter(str.isdigit, str(price))))
                    except:
                        booking_price = 0
                elif is_12_hours == 1:
                    booking_price = 7000 if twelve_hours_type and 'День' in twelve_hours_type else 6500
                elif is_mixing == 1:
                    booking_price = 2500
                elif is_track_creation == 1:
                    booking_price = 9000
                
                # ===== ПРАВИЛЬНАЯ ЛОГИКА УЧЁТА =====
                should_count = False
                reason = ""
                
                # 1. Админская запись - всегда
                if is_admin_booking == 1:
                    should_count = True
                    reason = "админская запись"
                
                # 2. Договорная запись - только после подтверждения
                elif is_contractual == 1 and status in ['confirmed', 'подтвержден']:
                    should_count = True
                    reason = "договорная подтверждённая"
                
                # 3. Сведение/мастеринг - только после подтверждения
                elif is_mixing == 1 and status in ['confirmed', 'подтвержден']:
                    should_count = True
                    reason = "сведение/мастеринг"
                
                # 4. Создание трека (альбом - договорная) - после подтверждения
                elif is_track_creation == 1 and status in ['confirmed', 'подтвержден']:
                    should_count = True
                    reason = "создание трека"
                
                # 5. Обычные записи (вокал, инструмент, аренда) - только после физического завершения
                elif status == 'completed':
                    should_count = True
                    reason = "завершённая запись"
                
                else:
                    # Формируем причину пропуска
                    if status == 'pending':
                        status_display = "ожидающая подтверждения"
                    elif status in ['rejected', 'отклонен']:
                        status_display = "отклонённая"
                    elif status in ['cancelled', 'cancelled_by_user', 'отменен']:
                        status_display = "отменённая"
                    else:
                        status_display = status
                    
                    skip_reason = status_display
                    if date_str and 'Не указана' not in date_str:
                        clean_date = date_str.split('(')[0].strip() if '(' in date_str else date_str
                        if clean_date.startswith(('🟢', '🟡', '🟠', '🔴', '⚪️')):
                            clean_date = clean_date[2:].strip()
                        skip_reason += f" ({clean_date})"
                    
                    skipped_bookings.append({
                        'id': booking_id,
                        'price': booking_price,
                        'reason': skip_reason
                    })
                    continue
                
                if should_count and booking_price > 0:
                    total_revenue += booking_price
                    counted_bookings.append({
                        'id': booking_id,
                        'price': booking_price,
                        'reason': reason
                    })
                elif should_count and booking_price == 0:
                    skipped_bookings.append({
                        'id': booking_id,
                        'price': 0,
                        'reason': "договорная цена (0₽)"
                    })
            
            counted_bookings.sort(key=lambda x: x['id'], reverse=True)
            skipped_bookings.sort(key=lambda x: x['id'], reverse=True)
            
            formatted_revenue = f"{total_revenue:,}₽".replace(',', ' ')
            
            message_text = f"*💰 Выручка {period_name}:*\n\n"
            message_text += f"*📊 Статистика:*\n"
            message_text += f"• Всего записей в периоде: {len(bookings)}\n"
            message_text += f"• Учтено в выручке: {len(counted_bookings)}\n"
            message_text += f"• Пропущено: {len(skipped_bookings)}\n"
            message_text += f"• Общая выручка: {formatted_revenue}\n\n"
            
            if counted_bookings:
                message_text += "*📋 Последние учтенные записи:*\n"
                for booking in counted_bookings[:10]:
                    formatted_price = f"{booking['price']:,}₽".replace(',', ' ')
                    message_text += f"• #{booking['id']} - {formatted_price} - {booking['reason']}\n"
                message_text += "\n"
            
            if skipped_bookings:
                message_text += "📋 Последние неучтенные записи:\n"
                for booking in skipped_bookings[:10]:
                    if booking['price'] > 0:
                        formatted_price = f"{booking['price']:,}₽".replace(',', ' ')
                        message_text += f"• #{booking['id']} - {formatted_price} - {booking['reason']}\n"
                    else:
                        message_text += f"• #{booking['id']} - {booking['reason']}\n"
            
            keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="revenue_back_to_periods")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if is_callback:
                await query.edit_message_text(
                    text=message_text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    text=message_text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            
    except Exception as e:
        logger.error(f"Ошибка расчета выручки: {e}")
        import traceback
        traceback.print_exc()
        
        error_message = "❌ Ошибка при расчете выручки!"
        
        if 'is_callback' in locals() and is_callback:
            try:
                await query.edit_message_text(text=error_message, parse_mode="Markdown")
            except:
                pass
        else:
            try:
                await update.message.reply_text(error_message, parse_mode="Markdown")
            except:
                pass

@handle_errors_with_rate_limit
async def handle_revenue_menu(update: Update, context):
    """Показывает меню выбора периода для выручки с inline-кнопками"""
    user_id = update.effective_user.id
    
    logger.info(f"🔍 handle_revenue_menu вызвана пользователем {user_id}")
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # Используем ТОЧНЫЕ строки для callback_data
    keyboard = [
        [
            InlineKeyboardButton("📅 Сегодня", callback_data="revenue_today"),
            InlineKeyboardButton("📅 Вчера", callback_data="revenue_yesterday")
        ],
        [
            InlineKeyboardButton("📅 Эта неделя", callback_data="revenue_week"),
            InlineKeyboardButton("📅 Прошлая неделя", callback_data="revenue_last_week")
        ],
        [
            InlineKeyboardButton("📅 Этот месяц", callback_data="revenue_month"),
            InlineKeyboardButton("📅 Прошлый месяц", callback_data="revenue_last_month")
        ],
        [
            InlineKeyboardButton("📅 За все время", callback_data="revenue_all"),
            InlineKeyboardButton("✏️ Свой период", callback_data="revenue_custom")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text="*👑 Выберите период*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_revenue_period_selection(update: Update, context):
    """Обрабатывает выбор периода из inline-меню"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    now = DateTimeUtils.now()
    
    logger.info(f"🔍 handle_revenue_period_selection: data={data}")
    
    # Используем ТОЧНЫЕ строки для сравнения
    if data == "revenue_today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
        period_name = "сегодня"
        
    elif data == "revenue_yesterday":
        yesterday = now - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        period_name = "вчера"
        
    elif data == "revenue_week":
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
        period_name = "эту неделю"
        
    elif data == "revenue_last_week":
        start_date = now - timedelta(days=now.weekday() + 7)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
        period_name = "прошлую неделю"
        
    elif data == "revenue_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
        period_name = "этот месяц"
        
    elif data == "revenue_last_month":
        if now.month == 1:
            start_date = now.replace(year=now.year-1, month=12, day=1, hour=0, minute=0, second=0)
        else:
            start_date = now.replace(month=now.month-1, day=1, hour=0, minute=0, second=0)
        
        if now.month == 1:
            end_date = now.replace(year=now.year-1, month=12, day=31, hour=23, minute=59, second=59)
        else:
            last_day = (start_date.replace(month=start_date.month+1, day=1) - timedelta(days=1)).day
            end_date = start_date.replace(day=last_day, hour=23, minute=59, second=59)
        period_name = "прошлый месяц"
        
    elif data == "revenue_all":
        start_date = None
        end_date = now
        period_name = "все время"
        
    elif data == "revenue_custom":
        context.user_data['awaiting_custom_revenue_period'] = True
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data="revenue_back_to_periods")]]
        await query.edit_message_text(
            text="*💰 Введите период*\n\n*📋 Форматы ввода:*\n\n• 01.03.2026 - 15.03.2026",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    elif data == "revenue_back_to_periods":
        context.user_data.pop('awaiting_custom_revenue_period', None)
        # Возвращаем меню выбора периода
        keyboard = [
            [
                InlineKeyboardButton("📅 Сегодня", callback_data="revenue_today"),
                InlineKeyboardButton("📅 Вчера", callback_data="revenue_yesterday")
            ],
            [
                InlineKeyboardButton("📅 Эта неделя", callback_data="revenue_week"),
                InlineKeyboardButton("📅 Прошлая неделя", callback_data="revenue_last_week")
            ],
            [
                InlineKeyboardButton("📅 Этот месяц", callback_data="revenue_month"),
                InlineKeyboardButton("📅 Прошлый месяц", callback_data="revenue_last_month")
            ],
            [
                InlineKeyboardButton("📅 За все время", callback_data="revenue_all"),
                InlineKeyboardButton("✏️ Свой период", callback_data="revenue_custom")
            ]
        ]
        await query.edit_message_text(
            text="*💰 Выберите период*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    else:
        # Неизвестный callback
        logger.warning(f"⚠️ Неизвестный callback data: {data}")
        await query.edit_message_text(
            text="❌ Неизвестная команда",
            parse_mode="Markdown"
        )
        return
    
    await calculate_and_show_revenue(update, context, start_date, end_date, period_name)

@handle_errors_with_rate_limit
async def handle_custom_revenue_period_inline(update: Update, context):
    """Обрабатывает ввод пользовательского периода для выручки (через inline)"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        return ConversationHandler.END
    
    if not context.user_data.get('awaiting_custom_revenue_period'):
        return ConversationHandler.END
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    try:
        if ' - ' not in text:
            raise ValueError("Неверный формат")
        
        start_str, end_str = text.split(' - ')
        start_date = datetime.strptime(start_str.strip(), '%d.%m.%Y')
        end_date = datetime.strptime(end_str.strip(), '%d.%m.%Y')
        
        start_date = start_date.replace(hour=0, minute=0, second=0)
        end_date = end_date.replace(hour=23, minute=59, second=59)
        
        start_date = Config.TIMEZONE.localize(start_date)
        end_date = Config.TIMEZONE.localize(end_date)
        
        period_name = f"с {start_str} по {end_str}"
        
        context.user_data.pop('awaiting_custom_revenue_period', None)
        
        # Создаем fake query для отправки результата
        class FakeQuery:
            def __init__(self, message, from_user):
                self.message = message
                self.from_user = from_user
            async def edit_message_text(self, text, parse_mode, reply_markup):
                await self.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            async def answer(self):
                pass
        
        fake_query = FakeQuery(update.message, update.effective_user)
        fake_update = Update(update.update_id, callback_query=fake_query)
        
        await calculate_and_show_revenue(fake_update, context, start_date, end_date, period_name)
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка парсинга дат: {e}")
        
        # Просто отправляем сообщение об ошибке БЕЗ КНОПКИ "Назад"
        await update.message.reply_text(
            "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*",
            parse_mode="Markdown"
        )
        return

@handle_errors_with_rate_limit
async def handle_custom_revenue_period(update: Update, context):
    """Обрабатывает ввод пользовательского периода для выручки"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        return ConversationHandler.END
    
    if not context.user_data.get('awaiting_custom_revenue_period'):
        return ConversationHandler.END
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    try:
        if ' - ' not in text:
            raise ValueError("Неверный формат")
        
        start_str, end_str = text.split(' - ')
        start_date = datetime.strptime(start_str.strip(), '%d.%m.%Y')
        end_date = datetime.strptime(end_str.strip(), '%d.%m.%Y')
        
        start_date = start_date.replace(hour=0, minute=0, second=0)
        end_date = end_date.replace(hour=23, minute=59, second=59)
        
        start_date = Config.TIMEZONE.localize(start_date)
        end_date = Config.TIMEZONE.localize(end_date)
        
        period_name = f"с {start_str} по {end_str}"
        
        context.user_data.pop('awaiting_custom_revenue_period', None)
        context.user_data.pop('in_revenue_menu', None)
        
        await calculate_revenue_for_period(update, context, start_date, end_date, period_name)
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка парсинга дат: {e}")
        
        await update.message.reply_text(
            "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return

@handle_errors_with_rate_limit
async def promo_handler(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🎁 Промокоды\n\n"
        "Доступные промокоды:\n"
        "• WELCOME50 — 50% на первую запись\n"
        "• STUDENT — 25% для студентов (требуется подтверждение)\n\n"
        "Чтобы активировать промокод, введите команду:\n"
        "/promo КОД",
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
    )
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def referral_command(update: Update, context):
    """Показывает реферальную информацию пользователя"""
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    user_id = str(update.effective_user.id)
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT referral_code, referred_by, vinyls, username, first_name
                FROM users WHERE telegram_id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            # Если пользователь новый — создаем запись
            if not user_data:
                username = update.effective_user.username or ""
                first_name = update.effective_user.first_name or ""
                unique_id = f"MC{int(time.time())}{user_id[-6:]}"
                registration_date = DateTimeUtils.now().strftime('%d.%m.%Y')
                referral_code = AchievementSystem.generate_referral_code(user_id)
                
                cursor.execute('''
                    INSERT INTO users 
                    (telegram_id, username, first_name, unique_id, registration_date, referral_code, vinyls)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, unique_id, registration_date, referral_code, 0))
                
                conn.commit()
                
                referral_code = referral_code
                referred_by = None
                vinyls = 0
            else:
                referral_code = user_data[0]
                referred_by = user_data[1]
                vinyls = user_data[2] or 0
            
            # Считаем активных рефералов (кто сделал запись)
            cursor.execute('''
                SELECT COUNT(DISTINCT u.telegram_id)
                FROM users u
                JOIN bookings b ON u.telegram_id = b.telegram_id
                WHERE u.referred_by = ? 
                AND (
                    b.service LIKE '%Админ%' OR b.service LIKE '%админ%' OR
                    (b.is_contractual = 1 AND b.status IN ('confirmed', 'подтвержден')) OR
                    (b.date_str NOT LIKE '%Не указана%' AND 
                     b.date_str NOT LIKE '%договорная%' AND 
                     b.status = 'completed')
                )
            ''', (referral_code,))
            
            active_referrals = cursor.fetchone()[0] or 0
            earned_vinyls = active_referrals * 25
            
            # Если пользователь был приглашен — +15 пластинок
            if referred_by:
                earned_vinyls += 15
            
            user_achievements = AchievementSystem.get_user_achievements(user_id)
            
            # ===== ФОРМИРУЕМ СООБЩЕНИЕ =====
            message = (
                f"*👥 Реферальная система*\n\n"
                f"*🔑 Ваш реферальный код:* `{referral_code}`\n\n"
                f"*📊 Статистика:*\n"
                f"• Приглашенных друзей: {active_referrals}\n"
                f"• Заработано пластинок: {earned_vinyls} 💿\n\n"
            )
            
            if referred_by:
                message += f"*🎉 Вы были приглашены! +15 пластинок за регистрацию*\n\n"
            
            message += (
                f"*🎁 Как это работает:*\n"
                f"• Дайте свой код друзьям\n"
                f"• Друг вводит код в разделе 'Рефералы' → 'Ввести код друга'\n"
                f"• Когда друг сделает первую запись, вы получите +25 пластинок\n"
                f"• Друг получает +15 пластинок за регистрацию\n\n"
            )
            
            message += f"*Достижения за рефералов:*\n"
            
            referral_achievements_list = [
                ('friend_inviter', '🤝 Позвал друга', '1 друг сделал запись'),
                ('social', '🗣 Социальный', '3 друга сделали запись'),
                ('star', '⭐️ Звезда', '5 друзей сделали запись'),
                ('magnate', '💰 Магнат', '10 друзей сделали запись'),
                ('network_giant', '🌐 Сетевой гигант', '20 друзей сделали запись')
            ]
            
            for ach_id, name_with_emoji, desc in referral_achievements_list:
                if ach_id in user_achievements:
                    message += f"✅ {name_with_emoji} — {desc}\n"
                else:
                    message += f"{name_with_emoji} — {desc}\n"
            
            keyboard = [
                [InlineKeyboardButton("🎟 Ввести код друга", callback_data="enter_referral_code")],
                [InlineKeyboardButton("👥 Мои рефералы", callback_data="show_my_referrals")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"Ошибка в referral_command: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "❌ Ошибка загрузки реферальной информации",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

@handle_errors_with_rate_limit
async def enter_referral_code_callback(update: Update, context):
    """Обработчик кнопки 'Ввести код друга'"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_referral_code'] = True
    
    await query.edit_message_text(
        "*🔑 Введите реферальный код друга*\n\n"
        "*📋 Код должен быть в формате:* `ABCD1234`\n\n"
        "*✏️ Просто отправьте код в чат:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("↩️ Назад", callback_data="back_to_referral")
        ]])
    )


@handle_errors_with_rate_limit
async def show_my_referrals_callback(update: Update, context):
    """Показывает список рефералов пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT referral_code FROM users WHERE telegram_id = ?', (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data:
                await query.edit_message_text(
                    "❌ Данные не найдены",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("↩️ Назад", callback_data="back_to_referral")
                    ]])
                )
                return
            
            referral_code = user_data[0]
            
            cursor.execute('''
                SELECT 
                    u.telegram_id, 
                    u.username, 
                    u.first_name, 
                    u.registration_date,
                    u.vinyls,
                    COUNT(b.id) as total_bookings,
                    SUM(CASE 
                        WHEN b.service LIKE '%Админ%' OR b.service LIKE '%админ%' THEN 1 
                        ELSE 0 
                    END) as admin_bookings,
                    SUM(CASE 
                        WHEN b.is_contractual = 1 AND b.status IN ('confirmed', 'подтвержден') THEN 1 
                        ELSE 0 
                    END) as contract_bookings,
                    SUM(CASE 
                        WHEN b.date_str NOT LIKE '%Не указана%' 
                             AND b.date_str NOT LIKE '%договорная%' 
                             AND b.status = 'completed' THEN 1 
                        ELSE 0 
                    END) as completed_bookings
                FROM users u
                LEFT JOIN bookings b ON u.telegram_id = b.telegram_id
                WHERE u.referred_by = ?
                GROUP BY u.telegram_id
                ORDER BY u.registration_date DESC
            ''', (referral_code,))
            
            referrals = cursor.fetchall()
            
            if not referrals:
                await query.edit_message_text(
                    "*👥 Мои рефералы*\n\n"
                    "*📭 У вас пока нет приглашенных друзей*\n\n"
                    "*✨ Поделитесь своим кодом и получайте бонусы!*",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("↩️ Назад", callback_data="back_to_referral")
                    ]])
                )
                return
            
            message = "*👥 Мои рефералы*\n\n"
            
            total_earned = 0
            active_count = 0
            
            for i, ref in enumerate(referrals, 1):
                (ref_id, username, first_name, reg_date, vinyls, 
                 total_bookings, admin_bookings, contract_bookings, 
                 completed_bookings) = ref
                
                name_display = first_name or username or f"Пользователь {ref_id[-4:]}"
                
                status_text = "❌ Нет записи"
                earned = 0
                
                if admin_bookings > 0:
                    status_text = "✅ Админская запись"
                    earned = 25
                    active_count += 1
                    total_earned += earned
                elif contract_bookings > 0:
                    status_text = "✅ Договорная запись"
                    earned = 25
                    active_count += 1
                    total_earned += earned
                elif completed_bookings > 0:
                    status_text = "✅ Прошедшая запись"
                    earned = 25
                    active_count += 1
                    total_earned += earned
                
                message += f"{i}. {name_display}"
                if username:
                    message += f" (@{username})"
                message += f"\n   • Статус: {status_text}"
                if earned > 0:
                    message += f" (+{earned} 💿 вам)"
                message += f"\n   • Всего записей: {total_bookings}"
                message += f"\n   • Пластинок друга: {vinyls} 💿"
                message += f"\n   • Зарегистрирован: {reg_date}\n\n"
            
            message += f"💰 Всего заработано с рефералов: {total_earned} 💿\n"
            message += f"👥 Количество активных рефералов: {active_count}"
            
            keyboard = [
                [InlineKeyboardButton("↩️ Назад", callback_data="back_to_referral")]
            ]
            
            await query.edit_message_text(
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Ошибка в show_my_referrals_callback: {e}")
        await query.answer("❌ Ошибка загрузки данных", show_alert=True)

@handle_errors_with_rate_limit
async def back_to_referral_callback(update: Update, context):
    """Возврат в главное меню рефералов"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop('awaiting_referral_code', None)
    
    user_id = str(update.effective_user.id)
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT referral_code, referred_by, vinyls 
                FROM users WHERE telegram_id = ?
            ''', (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                await query.edit_message_text(
                    "❌ Ошибка загрузки данных",
                    parse_mode="Markdown"
                )
                return
            
            referral_code = user_data[0]
            referred_by = user_data[1]
            vinyls = user_data[2] or 0
            
            # Считаем активных рефералов
            cursor.execute('''
                SELECT COUNT(DISTINCT u.telegram_id)
                FROM users u
                JOIN bookings b ON u.telegram_id = b.telegram_id
                WHERE u.referred_by = ? 
                AND (
                    b.service LIKE '%Админ%' OR b.service LIKE '%админ%' OR
                    (b.is_contractual = 1 AND b.status IN ('confirmed', 'подтвержден')) OR
                    (b.date_str NOT LIKE '%Не указана%' AND 
                     b.date_str NOT LIKE '%договорная%' AND 
                     b.status = 'completed')
                )
            ''', (referral_code,))
            
            active_referrals = cursor.fetchone()[0] or 0
            earned_vinyls = active_referrals * 25
            
            if referred_by:
                earned_vinyls += 15
            
            user_achievements = AchievementSystem.get_user_achievements(user_id)
            
            # ===== ФОРМИРУЕМ СООБЩЕНИЕ =====
            message = (
                f"*👥 Реферальная система*\n\n"
                f"*🔑 Ваш реферальный код:* `{referral_code}`\n\n"
                f"*📊 Статистика:*\n"
                f"• Приглашенных друзей: {active_referrals}\n"
                f"• Заработано пластинок: {earned_vinyls} 💿\n\n"
            )
            
            if referred_by:
                message += f"*🎉 Вы были приглашены! +15 пластинок за регистрацию*\n\n"
            
            message += (
                f"*🎁 Как это работает:*\n"
                f"• Дайте свой код друзьям\n"
                f"• Друг вводит код в разделе 'Рефералы' → 'Ввести код друга'\n"
                f"• Когда друг сделает первую запись, вы получите +25 пластинок\n"
                f"• Друг получает +15 пластинок за регистрацию\n\n"
            )
            
            message += f"*Достижения за рефералов:*\n"
            
            referral_achievements_list = [
                ('friend_inviter', '🤝 Позвал друга', '1 друг сделал запись'),
                ('social', '🗣 Социальный', '3 друга сделали запись'),
                ('star', '⭐️ Звезда', '5 друзей сделали запись'),
                ('magnate', '💰 Магнат', '10 друзей сделали запись'),
                ('network_giant', '🌐 Сетевой гигант', '20 друзей сделали запись')
            ]
            
            for ach_id, name_with_emoji, desc in referral_achievements_list:
                if ach_id in user_achievements:
                    message += f"✅ {name_with_emoji} — {desc}\n"
                else:
                    message += f"{name_with_emoji} — {desc}\n"
            
            keyboard = [
                [InlineKeyboardButton("🎟 Ввести код друга", callback_data="enter_referral_code")],
                [InlineKeyboardButton("👥 Мои рефералы", callback_data="show_my_referrals")]
            ]
            
            await query.edit_message_text(
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Ошибка в back_to_referral_callback: {e}")
        await query.edit_message_text(
            "❌ Ошибка загрузки реферальной информации",
            parse_mode="Markdown"
        )

@handle_errors_with_rate_limit
async def process_referral_code_message(update: Update, context):
    """Обработка введенного реферального кода"""
    
    if not context.user_data.get('awaiting_referral_code'):
        return await handle_main_menu(update, context)
    
    code = update.message.text.strip().upper()
    user_id = str(update.effective_user.id)
    
    logger.info(f"🔍 Попытка активации кода: '{code}' от пользователя {user_id}")
    
    if code in ["↩️ ГЛАВНОЕ МЕНЮ", "↩️ НАЗАД", "↩️ Главное меню", "↩️ Назад"]:
        context.user_data.pop('awaiting_referral_code', None)
        await update.message.reply_text(
            "🏠 Возврат в меню",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        return ConversationHandler.END
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, существует ли код
            cursor.execute('''
                SELECT telegram_id, username, first_name 
                FROM users WHERE referral_code = ?
            ''', (code,))
            
            referrer = cursor.fetchone()
            
            if not referrer:
                await update.message.reply_text(
                    "*❌ Код не найден*",
                    parse_mode="Markdown"
                )
                return
            
            referrer_id = referrer[0]
            referrer_name = referrer[1] or referrer[2] or "Пользователь"
            
            # Нельзя ввести свой код
            if referrer_id == user_id:
                await update.message.reply_text(
                    "*❌ Нельзя ввести свой собственный код*",
                    parse_mode="Markdown"
                )
                return
            
            # Проверяем, не использовал ли пользователь уже код
            cursor.execute('SELECT referred_by FROM users WHERE telegram_id = ?', (user_id,))
            user_data = cursor.fetchone()
            
            if user_data and user_data[0]:
                await update.message.reply_text(
                    "*❌ Вы уже использовали реферальный код*",
                    parse_mode="Markdown"
                )
                context.user_data.pop('awaiting_referral_code', None)
                return ConversationHandler.END
            
            # Проверяем, есть ли у пользователя записи (только для новых)
            cursor.execute('''
                SELECT 
                    COUNT(CASE 
                        WHEN b.status IN ('confirmed', 'подтвержден') 
                             AND b.date_str NOT LIKE '%Не указана%' 
                             AND b.date_str NOT LIKE '%договорная%'
                             AND b.service NOT LIKE '%Админ%'
                             AND b.service NOT LIKE '%админ%'
                        THEN 1 
                    END) as confirmed_user_bookings,
                    COUNT(CASE 
                        WHEN b.status IN ('confirmed', 'подтвержден')
                             AND (b.is_contractual = 1 
                                  OR b.date_str LIKE '%договорная%'
                                  OR b.date_str LIKE '%Не указана%')
                             AND b.service NOT LIKE '%Админ%'
                             AND b.service NOT LIKE '%админ%'
                        THEN 1 
                    END) as confirmed_contract_bookings,
                    COUNT(CASE 
                        WHEN b.service LIKE '%Админ%' 
                             OR b.service LIKE '%админ%'
                             OR b.name LIKE '%Админская запись%'
                             OR b.contact LIKE '%ID: MC%'
                        THEN 1 
                    END) as admin_bookings,
                    COUNT(CASE 
                        WHEN b.status = 'completed'
                             AND b.date_str NOT LIKE '%Не указана%' 
                             AND b.date_str NOT LIKE '%договорная%'
                             AND b.service NOT LIKE '%Админ%'
                             AND b.service NOT LIKE '%админ%'
                        THEN 1 
                    END) as completed_user_bookings
                FROM bookings b
                WHERE b.telegram_id = ?
            ''', (user_id,))
            
            result = cursor.fetchone()
            confirmed_user = result[0] or 0
            confirmed_contract = result[1] or 0
            admin_bookings = result[2] or 0
            completed_user = result[3] or 0
            
            total_existing_bookings = confirmed_user + confirmed_contract + admin_bookings + completed_user
            
            cursor.execute('''
                SELECT COUNT(*) FROM user_achievements 
                WHERE user_id = ? AND achievement_id = 'first_booking'
            ''', (user_id,))
            has_first_booking = cursor.fetchone()[0] > 0
            
            logger.info(f"🔍 Проверка реферального кода для {user_id}:")
            logger.info(f"   • Подтвержденных пользовательских: {confirmed_user}")
            logger.info(f"   • Подтвержденных договорных: {confirmed_contract}")
            logger.info(f"   • Админских: {admin_bookings}")
            logger.info(f"   • Прошедших пользовательских: {completed_user}")
            logger.info(f"   • ВСЕГО записей: {total_existing_bookings}")
            logger.info(f"   • Есть достижение 'Добро пожаловать': {has_first_booking}")
            
            # Если есть записи — нельзя активировать код
            if total_existing_bookings > 0 or has_first_booking:
                await update.message.reply_text(
                    f"*❌ Реферальный код нельзя активировать*\n\n"
                    f"*💡 Реферальные бонусы доступны только новым пользователям*",
                    parse_mode="Markdown"
                )
                context.user_data.pop('awaiting_referral_code', None)
                return ConversationHandler.END
            
            # Начисляем бонус пользователю (+15 пластинок)
            cursor.execute('SELECT telegram_id, vinyls FROM users WHERE telegram_id = ?', (user_id,))
            existing_user = cursor.fetchone()
            
            current_vinyls = 0
            
            if not existing_user:
                # Создаем нового пользователя
                username = update.effective_user.username or ""
                first_name = update.effective_user.first_name or ""
                unique_id = f"MC{int(time.time())}{user_id[-6:]}"
                registration_date = DateTimeUtils.now().strftime('%d.%m.%Y')
                user_referral_code = AchievementSystem.generate_referral_code(user_id)
                
                cursor.execute('''
                    INSERT INTO users 
                    (telegram_id, username, first_name, unique_id, registration_date, referral_code, vinyls)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, unique_id, registration_date, user_referral_code, 15))
                
                current_vinyls = 15
                logger.info(f"✅ Новый пользователь {user_id} получил +15 пластинок")
            else:
                current_vinyls = existing_user[1] or 0
                cursor.execute('''
                    UPDATE users SET vinyls = ? WHERE telegram_id = ?
                ''', (current_vinyls + 15, user_id))
                logger.info(f"✅ Пользователь {user_id} получил +15 пластинок (было {current_vinyls}, стало {current_vinyls + 15})")
                current_vinyls += 15
            
            # Сохраняем, кто пригласил
            cursor.execute('''
                UPDATE users SET referred_by = ? WHERE telegram_id = ?
            ''', (code, user_id))
            
            conn.commit()
            
            # Проверяем достижения для пригласившего
            await AchievementSystem.check_and_award_achievements(str(referrer_id), context, update)
            
            # Отправляем уведомление пригласившему
            try:
                user_display = update.effective_user.username or update.effective_user.first_name or "Новый пользователь"
                
                await context.bot.send_message(
                    chat_id=int(referrer_id),
                    text=(
                        f"*🎉 Новый реферал!*\n\n"
                        f"*👤 Пользователь {user_display} зарегистрировался по вашему реферальному коду!*\n\n"
                        f"*⚡ Когда он сделает первую запись, вы получите +25 пластинок*"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пригласившему: {e}")
            
            context.user_data.pop('awaiting_referral_code', None)
            
            await update.message.reply_text(
                f"*✅ Код активирован!*\n\n"
                f"*🎉 Вы были приглашены пользователем {referrer_name}*\n\n"
                f"*🎁 Вы получили +15 пластинок за регистрацию*\n\n"
                f"*⚡ Когда вы сделаете первую запись, {referrer_name} получит +25 пластинок*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            
    except Exception as e:
        logger.error(f"Ошибка активации реферального кода: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "*❌ Ошибка активации кода*\n\n"
            "*💡 Пожалуйста, попробуйте позже или свяжитесь с администратором.*",
            parse_mode="Markdown"
        )
        return

async def award_referral_bonus(booking_user_id: str, booking_data: dict, context):
    """
    Начисляет бонус пригласившему пользователю, когда реферал делает первую запись
    """
    try:
        logger.info(f"🎯 Начисление реферального бонуса для пользователя {booking_user_id}")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT referred_by FROM users WHERE telegram_id = ?
            ''', (booking_user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data or not user_data[0]:
                logger.info(f"Пользователь {booking_user_id} не был приглашен")
                return
            
            referrer_code = user_data[0]
            
            cursor.execute('''
                SELECT telegram_id, username, vinyls FROM users WHERE referral_code = ?
            ''', (referrer_code,))
            
            referrer = cursor.fetchone()
            
            if not referrer:
                logger.warning(f"Реферер с кодом {referrer_code} не найден")
                return
            
            referrer_id = referrer[0]
            referrer_username = referrer[1] or "Пользователь"
            referrer_vinyls = referrer[2] or 0
            
            # Проверяем, не начисляли ли уже бонус
            cursor.execute('''
                SELECT COUNT(*) FROM booking_referral_bonuses 
                WHERE user_id = ? AND referrer_id = ?
            ''', (booking_user_id, referrer_id))
            
            if cursor.fetchone()[0] > 0:
                logger.info(f"Бонус для реферера {referrer_id} уже начислен")
                return
            
            # Проверяем, подходит ли запись для начисления бонуса
            is_admin_booking = booking_data.get('is_admin_booking', False)
            is_contractual = booking_data.get('is_contractual', False)
            status = booking_data.get('status', '')
            date_str = booking_data.get('date_str', '')
            service = booking_data.get('service', '')
            
            should_award = False
            award_reason = ""
            
            if is_contractual and status in ['confirmed', 'подтвержден']:
                should_award = True
                award_reason = "подтвержденная договорная запись"
                logger.info(f"✅ Случай 1: Подтвержденная договорная запись")
            
            elif is_admin_booking:
                should_award = True
                award_reason = "админская запись"
                logger.info(f"✅ Случай 2: Админская запись")
            
            elif status == 'completed' and date_str and 'Не указана' not in date_str and 'договорная' not in date_str.lower():
                should_award = True
                award_reason = "прошедшая запись с датой"
                logger.info(f"✅ Случай 3: Прошедшая запись с датой")
            
            if not should_award:
                logger.info(f"❌ Запись не подходит для начисления бонуса: is_admin={is_admin_booking}, is_contract={is_contractual}, status={status}")
                return
            
            # Начисляем бонус
            cursor.execute('''
                SELECT username, first_name FROM users WHERE telegram_id = ?
            ''', (booking_user_id,))
            friend_data = cursor.fetchone()
            friend_name = friend_data[0] or friend_data[1] or "Пользователь"
            
            new_vinyls = referrer_vinyls + 25
            cursor.execute('''
                UPDATE users SET vinyls = ? WHERE telegram_id = ?
            ''', (new_vinyls, referrer_id))
            
            cursor.execute('''
                INSERT INTO booking_referral_bonuses (user_id, referrer_id, bonus_type)
                VALUES (?, ?, ?)
            ''', (booking_user_id, referrer_id, award_reason))
            
            conn.commit()
            
            logger.info(f"✅ Пригласившему {referrer_id} начислено +25 пластинок ({award_reason})")
            
            # Отправляем уведомление пригласившему
            try:
                vinyl_message = (
                    f"*🎉 Ваш реферал сделал первую запись!*\n\n"
                    f"*👤 Пользователь {friend_name} только что сделал свою первую запись*\n"
                    f"*📋 Тип: {award_reason}*\n\n"
                    f"*🎁 Вы получили +25 пластинок 💿*\n"
                    f"*💰 Всего пластинок: {new_vinyls}*"
                )
                
                await context.bot.send_message(
                    chat_id=int(referrer_id),
                    text=vinyl_message,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Уведомление о +25 пластинках отправлено {referrer_id}")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить уведомление о пластинках: {e}")
            
            # Проверяем достижения
            await AchievementSystem.check_and_award_achievements(str(referrer_id), context, update=None)
            await AchievementSystem.check_and_award_achievements(str(booking_user_id), context, update=None)
            
    except Exception as e:
        logger.error(f"❌ Ошибка начисления бонуса: {e}")
        import traceback
        traceback.print_exc()

@handle_errors_with_rate_limit
async def start_booking(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    user_id = str(update.effective_user.id)
    
    context.user_data.clear()
    
    logger.info(f"🔍 Начало записи для пользователя {user_id}")
    
    await update.message.reply_text(
        "*👤 Шаг 1/7: Ввод имени*\n\n"
        "*✨ Здравствуйте! Как к Вам обращаться?*\n\n"
        "*Вы можете ввести:*\n"
        "• Настоящее имя — Мирон\n"
        "• Творческий псевдоним — Ex Sinner\n"
        "• Любое удобное для Вас имя\n\n"
        "*✏️ Введите ваше имя:*",
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_main_menu_only_keyboard()
    )
    return NAME

@handle_errors_with_rate_limit
async def show_my_bookings(update: Update, context):
    """Показывает записи пользователя: все студийные + ожидающие договорные"""
    
    if not update or not update.message:
        logger.error("show_my_bookings: update или update.message равен None")
        return
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    user = update.effective_user
    if not user:
        logger.error("show_my_bookings: effective_user равен None")
        return
    
    user_id = str(user.id)
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT username, unique_id FROM users WHERE telegram_id = ?', (user_id,))
            user_info = cursor.fetchone()
            if user_info:
                current_user_display = get_user_display_name({
                    'username': user_info[0],
                    'unique_id': user_info[1],
                    'telegram_id': user_id
                })
            else:
                current_user_display = f"ID: ...{user_id[-4:]}"
            
            # ===== SQL ЗАПРОС =====
            cursor.execute('''
                SELECT b.id, b.service, b.time_slot, b.date_str, b.status, b.price,
                    b.is_mixing, b.mixing_type, b.is_track_creation, b.track_type,
                    b.is_12_hours, b.twelve_hours_type, b.with_engineer, b.name, b.contact,
                    b.duration, b.timestamp, b.is_contractual, b.is_admin_booking,
                    b.level_discount_percent, b.promo_discount_percent, b.promo_code_used,
                    b.level_coupon_id
                FROM bookings b
                WHERE b.telegram_id = ? 
                AND b.status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен', 'completed')
                AND (
                    (b.is_contractual = 0 AND b.is_admin_booking = 0 AND b.is_mixing = 0)
                    OR
                    (b.is_mixing = 1 AND b.status = 'pending')
                    OR
                    (b.is_contractual = 1 AND b.is_admin_booking = 0 AND b.status = 'pending')
                )
                ORDER BY 
                    CASE 
                        WHEN b.status = 'pending' THEN 0 
                        ELSE 1 
                    END,
                    b.id ASC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            
            if not rows:
                await update.message.reply_text(
                    text=(
                        f"*📭 У Вас нет активных записей*\n\n"
                    ),
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                )
                return
            
            dated_bookings = []
            contract_bookings = []
            
            for row in rows:
                (booking_id, service, time_slot, date_str, status, price,
                 is_mixing, mixing_type, is_track_creation, track_type,
                 is_12_hours, twelve_hours_type, with_engineer, name, contact,
                 duration, timestamp, is_contractual_db, is_admin_booking_db,
                 level_discount_percent, promo_discount_percent, promo_code_used,
                 level_coupon_id) = row
                
                is_contractual = is_contractual_db == 1
                is_admin_booking = is_admin_booking_db == 1
                
                status_lower = status.lower() if status else ""
                
                if 'pending' in status_lower or 'ожидает' in status_lower:
                    status_emoji = "⏳"
                    status_text = "Ожидает подтверждения"
                elif 'confirmed' in status_lower or 'подтвержден' in status_lower:
                    status_emoji = "✅"
                    status_text = "Подтверждена"
                else:
                    status_emoji = "⏳"
                    status_text = status
                
                safe_service = SecurityUtils.safe_markdown_text(service) if service else ""
                safe_name = SecurityUtils.safe_markdown_text(name) if name else ""
                safe_contact = SecurityUtils.safe_markdown_text(contact) if contact else ""
                
                if is_admin_booking:
                    safe_name = "Администратор"
                
                # ===== ИСПРАВЛЕННОЕ ФОРМИРОВАНИЕ ТЕКСТА КУПОНА / СКИДКИ ПО УРОВНЮ =====
                coupon_text = ""
                
                # Сначала проверяем level_discount_percent из записи
                if level_discount_percent and level_discount_percent > 0:
                    # Пытаемся найти купон в user_coupons для деталей
                    if level_coupon_id:
                        cursor.execute('''
                            SELECT level, discount_percent FROM user_coupons WHERE id = ?
                        ''', (level_coupon_id,))
                        coupon_info = cursor.fetchone()
                        if coupon_info:
                            level, discount = coupon_info
                            coupon_text = f"• Купон уровня {level}: {discount}%"
                        else:
                            # Купон удалён, но скидка была применена
                            coupon_text = f"• Скидка по уровню: {level_discount_percent}%"
                    else:
                        # Нет ID купона, но скидка была применена
                        coupon_text = f"• Скидка по уровню: {level_discount_percent}%"
                
                # ===== ФОРМИРУЕМ ТЕКСТ ПРОМОКОДА =====
                promo_text = ""
                if promo_code_used:
                    cursor.execute('''
                        SELECT discount_type, discount_value, target_service 
                        FROM promo_codes WHERE code = ?
                    ''', (promo_code_used,))
                    promo_info = cursor.fetchone()
                    
                    if promo_info:
                        discount_type, discount_value, target_service = promo_info
                        
                        if discount_type == 'percent_all':
                            promo_text = f"• Промокод: {discount_value}% на всё (код: {promo_code_used})"
                        elif discount_type == 'percent_service':
                            service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                            promo_text = f"• Промокод: {discount_value}% на {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                        elif discount_type == 'free_hours':
                            if discount_value == 1:
                                hours_text = "1 час"
                            elif discount_value in [2, 3, 4]:
                                hours_text = f"{discount_value} часа"
                            else:
                                hours_text = f"{discount_value} часов"
                            promo_text = f"• Промокод: {hours_text} бесплатно (код: {promo_code_used})"
                        elif discount_type == 'free_service':
                            service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                            promo_text = f"• Промокод: бесплатно: {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                
                booking_info = {
                    'id': booking_id,
                    'status_emoji': status_emoji,
                    'status_text': status_text,
                    'service': safe_service,
                    'is_12_hours': is_12_hours,
                    'twelve_hours_type': twelve_hours_type,
                    'is_mixing': is_mixing,
                    'mixing_type': mixing_type,
                    'is_track_creation': is_track_creation,
                    'track_type': track_type,
                    'date_str': date_str,
                    'time_slot': time_slot,
                    'price': price,
                    'duration': duration,
                    'is_contractual': is_contractual,
                    'is_admin_booking': is_admin_booking,
                    'timestamp': timestamp,
                    'name': safe_name,
                    'contact': safe_contact,
                    'coupon_text': coupon_text,
                    'promo_text': promo_text,
                    'level_discount_percent': level_discount_percent,
                    'promo_discount_percent': promo_discount_percent
                }
                
                # ===== РАЗДЕЛЯЕМ ЗАПИСИ =====
                if is_mixing == 1 or is_contractual:
                    contract_bookings.append(booking_info)
                else:
                    dated_bookings.append(booking_info)
            
            dated_bookings.sort(key=lambda x: x['id'])
            contract_bookings.sort(key=lambda x: x['id'])
            
            message_parts = []
            current_part = f"*📅 Мои записи*\n\n*👤 Профиль: {SecurityUtils.safe_markdown_text(current_user_display)}*\n\n"
            
            # ===== ОБЫЧНЫЕ ЗАПИСИ =====
            if dated_bookings:
                current_part += "*📋 Записи в студии:*\n\n"
                
                for booking in dated_bookings:
                    booking_text = f"{booking['status_emoji']} *Запись #{booking['id']}*\n"
                    booking_text += f"• Имя: {booking['name']}\n"
                    booking_text += f"• Контакт: {booking['contact']}\n"
                    booking_text += f"• Услуга: {booking['service']}\n"
                    
                    if booking['is_12_hours'] and booking['twelve_hours_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['twelve_hours_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    elif booking['is_mixing'] and booking['mixing_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['mixing_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    elif booking['is_track_creation'] and booking['track_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['track_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    
                    if booking['date_str'] and 'Не указана' not in booking['date_str'] and booking['date_str'] != 'Запись в студии':
                        clean_date = booking['date_str'].split('(')[0].strip() if '(' in booking['date_str'] else booking['date_str']
                        if '(' in booking['date_str']:
                            day_part = booking['date_str'].split('(')[1].replace(')', '').strip()
                            safe_day_part = SecurityUtils.safe_markdown_text(day_part)
                            booking_text += f"• Дата: {clean_date} ({safe_day_part})\n"
                        else:
                            booking_text += f"• Дата: {clean_date}\n"
                    
                    if (booking['time_slot'] and 
                        booking['time_slot'] not in ['Не указано', 'Не указано (договорная)', 'Запись в студии']):
                        display_time = DateTimeUtils.format_time_for_display(booking['time_slot'])
                        safe_display_time = SecurityUtils.safe_markdown_text(display_time)
                        if booking['is_12_hours']:
                            booking_text += f"• Время: {safe_display_time} (12 часов)\n"
                        elif booking['duration'] and booking['duration'] > 0:
                            formatted_duration = PriceCalculator.format_hours_ru(booking['duration'])
                            booking_text += f"• Время: {safe_display_time} ({formatted_duration})\n"
                        else:
                            booking_text += f"• Время: {safe_display_time}\n"
                    
                    if booking['is_12_hours']:
                        price_from_db = booking.get('price', 0)
                        if price_from_db and price_from_db != '0':
                            try:
                                price_int = int(float(price_from_db))
                                booking_text += f"• Стоимость аренды: {price_int}₽ + залог (по договору)\n"
                            except:
                                booking_text += f"• Стоимость: {price_from_db}₽\n"
                        else:
                            rent_price = 7000 if booking.get('twelve_hours_type', '').startswith('День') else 6500
                            booking_text += f"• Стоимость аренды: {rent_price}₽ + залог (по договору)\n"
                    elif booking['price'] and str(booking['price']) != '0':
                        if 'договорная' in str(booking['price']).lower():
                            booking_text += "• Стоимость: Договорная\n"
                        else:
                            try:
                                price_int = int(float(booking['price']))
                                formatted_price = f"{price_int}₽"
                                booking_text += f"• Стоимость: {formatted_price}\n"
                            except:
                                safe_price = SecurityUtils.safe_markdown_text(str(booking['price']))
                                booking_text += f"• Стоимость: {safe_price}\n"
                    
                    # ===== ДОБАВЛЯЕМ КУПОН / СКИДКУ ПО УРОВНЮ =====
                    if booking.get('coupon_text'):
                        booking_text += f"{booking['coupon_text']}\n"
                    
                    # ===== ДОБАВЛЯЕМ ПРОМОКОД =====
                    if booking.get('promo_text'):
                        booking_text += f"{booking['promo_text']}\n"
                    
                    booking_text += f"• Статус: {booking['status_text']}\n\n"
                    
                    if len(current_part + booking_text) > 3500:
                        message_parts.append(current_part)
                        current_part = booking_text
                    else:
                        current_part += booking_text
            
            # ===== ДОГОВОРНЫЕ ЗАПИСИ (ТОЛЬКО PENDING) =====
            if contract_bookings:
                if len(current_part + "*📝 Ожидающие договорные записи:*\n\n") > 3500:
                    message_parts.append(current_part)
                    current_part = "*📝 Ожидающие договорные записи:*\n\n"
                else:
                    current_part += "*📝 Ожидающие договорные записи:*\n\n"
                
                for booking in contract_bookings:
                    booking_text = f"{booking['status_emoji']} *Запись #{booking['id']}*\n"
                    booking_text += f"• Имя: {booking['name']}\n"
                    booking_text += f"• Контакт: {booking['contact']}\n"
                    booking_text += f"• Услуга: {booking['service']}\n"
                    
                    if booking['is_mixing'] and booking['mixing_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['mixing_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    elif booking['is_track_creation'] and booking['track_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['track_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    
                    if booking['price'] and str(booking['price']) != '0':
                        if 'договорная' in str(booking['price']).lower():
                            booking_text += "• Стоимость: Договорная\n"
                        else:
                            try:
                                price_int = int(float(booking['price']))
                                formatted_price = f"{price_int}₽"
                                booking_text += f"• Стоимость: {formatted_price}\n"
                            except:
                                safe_price = SecurityUtils.safe_markdown_text(str(booking['price']))
                                booking_text += f"• Стоимость: {safe_price}\n"
                    
                    # ===== ДОБАВЛЯЕМ КУПОН / СКИДКУ ПО УРОВНЮ =====
                    if booking.get('coupon_text'):
                        booking_text += f"{booking['coupon_text']}\n"
                    
                    # ===== ДОБАВЛЯЕМ ПРОМОКОД =====
                    if booking.get('promo_text'):
                        booking_text += f"{booking['promo_text']}\n"
                    
                    booking_text += f"• Статус: {booking['status_text']}\n\n"
                    
                    if len(current_part + booking_text) > 3500:
                        message_parts.append(current_part)
                        current_part = booking_text
                    else:
                        current_part += booking_text
            
            if current_part:
                if not message_parts:
                    current_part += "*👇 Отменить записи в студии:*"
                message_parts.append(current_part)
            
            # ===== КНОПКИ ТОЛЬКО ДЛЯ dated_bookings =====
            keyboard_buttons = []
            for booking in dated_bookings:
                button_text = f"❌ Отменить #{booking['id']}"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"cancel_{booking['id']}"
                    )
                ])
            
            if keyboard_buttons:
                keyboard_buttons.sort(key=lambda x: int(x[0].callback_data.split('_')[1]))
                reply_markup = InlineKeyboardMarkup(keyboard_buttons)
            else:
                reply_markup = KeyboardManager.get_main_keyboard(update.effective_user)
            
            for i, part in enumerate(message_parts):
                if i == len(message_parts) - 1:
                    await update.message.reply_text(
                        part,
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(
                        part,
                        parse_mode="Markdown"
                    )
        
    except Exception as e:
        logger.error(f"Ошибка показа записей пользователя: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "*📅 Мои записи*\n\n"
            "*⚠️ Не удалось загрузить информацию*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

@handle_errors_with_rate_limit
async def handle_main_menu(update: Update, context):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    # ===== ОБРАБОТКА КНОПКИ "ГЛАВНОЕ МЕНЮ" =====
    if text == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    # ===== ОБРАБОТКА КНОПКИ "НАЗАД" =====
    if text == "↩️ Назад":
        current_state = context.user_data.get('_conversation_state')
        
        if current_state == ADMIN_CANCEL_SHOW_BOOKINGS:
            return await handle_admin_cancel_back(update, context)
        elif current_state == ADMIN_REMOVE_ACHIEVEMENT_SHOW:
            return await handle_admin_remove_achievement_back(update, context)
        elif current_state in [NAME, CONTACT, CONTACT_INPUT, SERVICE, ENGINEER_OPTION, 
                               TWELVE_HOURS_OPTION, MIXING_TYPE, TRACK_CREATION_TYPE, 
                               DATE, SHOW_SLOTS, CONFIRM]:
            return await handle_back_button(update, context)
        else:
            context.user_data.clear()
            await update.message.reply_text(
                "*🏠 Возвращаемся в главное меню*\n\n"
                "*👇 Выберите подходящий вариант:*",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
                parse_mode="Markdown"
            )
            return ConversationHandler.END
    
    # ===== КОМАНДЫ =====
    if text == '/start':
        return await start(update, context)
    
    if text == '/pending' and user_id in Config.ADMIN_IDS:
        return await pending_command(update, context)
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    if context.user_data.get('in_revenue_menu'):
        return await handle_revenue_period_selection(update, context)
    
    if context.user_data.get('awaiting_custom_revenue_period'):
        return await handle_custom_revenue_period(update, context)
    
    if context.user_data.get('_conversation_state') is not None:
        return
    
    # ===== НОВЫЕ КНОПКИ =====
    if text == "❓ Помощь":
        return await help_handler(update, context)
    
    if text == "❗️ Полезная информация":
        return await useful_info_handler(update, context)
    
    # ===== ОСНОВНЫЕ КНОПКИ ПОЛЬЗОВАТЕЛЯ =====
    if text == "🎤 Записаться в студию":
        if await check_user_blocked(update, context):
            return ConversationHandler.END
        return await start_booking(update, context)
    
    if text == "📅 Мои записи":
        await show_my_bookings(update, context)
        return ConversationHandler.END
    
    if text == "🔔 Напоминания":
        await notifications_command(update, context)
        return ConversationHandler.END
    
    if text == "👤 Мой профиль":
        await profile_handler(update, context)
        return ConversationHandler.END
    
    if text == "🏆 Достижения":
        await achievements_handler(update, context)
        return ConversationHandler.END
    
    if text == "🎁 Промокоды":
        await promo_main_menu(update, context)
        return ConversationHandler.END
    
    if text == "👥 Рефералы":
        await referral_command(update, context)
        return ConversationHandler.END
    
    if text == "📈 Мой уровень":
        await level_handler(update, context)
        return ConversationHandler.END
    
    if text == "🏆 Топ пользователей":
        await top_vinyls_handler(update, context)
        return ConversationHandler.END
    
    # ===== АДМИНСКИЕ КНОПКИ =====
    if text == "👑 Создать запись":
        return await handle_admin_create_booking(update, context)
    
    if text == "👑 Отменить запись":
        return await handle_admin_cancel_start(update, context)
    
    if text == "👑 Заблокировать":
        return await handle_admin_block_start(update, context)
    
    if text == "👑 Выдать достижение":
        return await handle_admin_award_achievement_start(update, context)
    
    if text == "👑 Удалить достижение":
        return await handle_admin_remove_achievement_start(update, context)
    
    if text == "👑 Пластинки":
        return await handle_admin_vinyl_start(update, context)
    
    if text == "👑 Профиль":
        return await handle_admin_profile_start(update, context)
    
    if text == "👑 Выручка":
        return await handle_revenue_menu(update, context)
    
    if text == "👑 Создать промокод":
        return await admin_promo_start(update, context)
    
    if text == "👑 Удалить промокод":
        return await admin_promo_delete_start(update, context)
    
    # Если ничего не подошло - игнорируем
    return None

async def handle_global_buttons(update: Update, context):
    text = update.message.text.strip()
    
    logger.info(f"🔍 ГЛОБАЛЬНЫЙ ОБРАБОТЧИК КНОПОК: '{text}'")
    
    # ===== КНОПКИ, КОТОРЫЕ ДОЛЖЕН ОБРАБАТЫВАТЬ CONVERSATIONHANDLER =====
    if text in ["✅ Всё верно, отправить", "✏️ Исправить данные", "❌ Отменить", "↩️ Назад"]:
        return None
    
    # ===== ОСНОВНЫЕ КНОПКИ ПОЛЬЗОВАТЕЛЯ =====
    if text == "📅 Мои записи":
        await show_my_bookings(update, context)
        return ConversationHandler.END
    
    if text == "🔔 Напоминания":
        await notifications_command(update, context)
        return ConversationHandler.END
    
    if text == "👤 Мой профиль":
        await profile_handler(update, context)
        return ConversationHandler.END
    
    if text == "🏆 Достижения":
        await achievements_handler(update, context)
        return ConversationHandler.END
    
    if text == "🎁 Промокоды":
        await promo_main_menu(update, context)
        return ConversationHandler.END
    
    if text == "👥 Рефералы":
        await referral_command(update, context)
        return ConversationHandler.END
    
    if text == "📈 Мой уровень":
        await level_handler(update, context)
        return ConversationHandler.END
    
    if text == "🏆 Топ пользователей":
        await top_vinyls_handler(update, context)
        return ConversationHandler.END
    
    # ===== КНОПКИ ПОМОЩИ =====
    if text == "❓ Помощь":
        await help_handler(update, context)
        return ConversationHandler.END
    
    if text == "❗️ Полезная информация":
        await useful_info_handler(update, context)
        return ConversationHandler.END
    
    # ===== АДМИНСКИЕ КНОПКИ =====
    if text == "👑 Выручка":
        return await handle_revenue_menu(update, context)
    
    if text == "👑 Удалить промокод":
        return await admin_promo_delete_start(update, context)
    
    return None

@handle_errors_with_rate_limit
async def notifications_command(update: Update, context):
    """Показывает ожидающие уведомления пользователя"""
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    user = update.effective_user
    user_id = str(user.id)
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT n.id, n.booking_id, n.notification_type, n.status, 
                       n.planned_send_time, n.actual_send_time,
                       b.service, b.date_str, b.time_slot, b.with_engineer
                FROM notifications n
                LEFT JOIN bookings b ON n.booking_id = b.id
                WHERE n.user_id = ?
                AND n.status = 'pending'
                AND b.status IN ('confirmed', 'подтвержден')
                AND b.service NOT LIKE '%Админская%'
                AND b.service NOT LIKE '%админская%'
                ORDER BY n.planned_send_time ASC
                LIMIT 20
            ''', (user_id,))
            
            rows = cursor.fetchall()
            
            if not rows:
                await update.message.reply_text(
                    text=(
                        f"*📭 У Вас нет активных напоминаний*"
                    ),
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                )
                return
            
            message = "*🔔 Напоминания*\n\n"
            message += "*📋 Детали ваших заявок:*\n\n"
            
            for row in rows:
                (notif_id, booking_id, notif_type, status, 
                 planned_time, actual_time, service, date_str, time_slot, with_engineer) = row
                
                # Получаем часы из типа уведомления
                hours = 0
                if 'h_before' in notif_type:
                    try:
                        hours = int(notif_type.replace('h_before', ''))
                    except:
                        hours = 0
                
                # Форматируем время отправки
                time_text = ""
                if planned_time:
                    try:
                        planned_datetime = datetime.strptime(planned_time, '%Y-%m-%d %H:%M:%S')
                        now = DateTimeUtils.now()
                        time_until = planned_datetime - now.replace(tzinfo=None)
                        
                        if time_until.total_seconds() > 0:
                            days = time_until.days
                            hours_left = time_until.seconds // 3600
                            minutes = (time_until.seconds % 3600) // 60
                            
                            if days > 0:
                                time_text = f"{days} д. {hours_left} ч."
                            elif hours_left > 0 and minutes > 0:
                                time_text = f"{hours_left} ч. {minutes} мин."
                            elif hours_left > 0:
                                time_text = f"{hours_left} ч."
                            elif minutes > 0:
                                time_text = f"{minutes} мин."
                            else:
                                time_text = "скоро"
                        else:
                            time_text = "скоро"
                    except:
                        time_text = ""
                
                # Очищаем дату от эмодзи
                clean_date = date_str
                if clean_date and '(' in clean_date:
                    clean_date = clean_date.split('(')[0].strip()
                if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                    clean_date = clean_date[2:].strip()
                
                # Форматируем время
                display_time = time_slot
                if display_time and '-' in display_time:
                    display_time = DateTimeUtils.format_time_for_display(display_time)
                
                # Убираем смайлики из услуги
                clean_service = service
                for emoji in ['🎤', '🎸', '⏰', '🎚️', '🎵', '🎹']:
                    clean_service = clean_service.replace(emoji, '').strip()
                
                # ===== ФОРМИРУЕМ НАЗВАНИЕ УСЛУГИ ДЛЯ ОТОБРАЖЕНИЯ =====
                service_lower = clean_service.lower() if clean_service else ""
                with_engineer_bool = with_engineer == 1
                
                if 'аренд' in service_lower or '12-час' in service_lower:
                    service_display = "12-часовая аренда"
                elif 'создание трека' in service_lower or 'трек' in service_lower:
                    service_display = "Создание трека"
                elif 'вокал' in service_lower and with_engineer_bool:
                    service_display = "Запись вокала (с инженером)"
                elif 'вокал' in service_lower and not with_engineer_bool:
                    service_display = "Запись вокала (без инженера)"
                elif 'инструмент' in service_lower and with_engineer_bool:
                    service_display = "Запись инструментов (с инженером)"
                elif 'инструмент' in service_lower and not with_engineer_bool:
                    service_display = "Запись инструментов (без инженера)"
                else:
                    service_display = clean_service
                
                message += f"⏳ *Напоминание за {hours} часов*\n"
                message += f"• Услуга: {service_display}\n"
                
                if clean_date and 'Не указана' not in clean_date and clean_date != 'Запись в студии':
                    message += f"• Дата: {clean_date}\n"
                
                if display_time and display_time not in ['Не указано', 'Не указано (договорная)']:
                    message += f"• Время: {display_time}\n"
                
                # ===== ИСПРАВЛЕНО: убрано слово "через" =====
                if time_text:
                    message += f"• Отправка через: {time_text}\n"
                
                message += f"• ID записи: #{booking_id}\n\n"
            
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
        
    except Exception as e:
        logger.error(f"Ошибка показа уведомлений: {e}")
        await update.message.reply_text(
            "*🔔 Напоминания*\n\n"
            "*⚠️ Не удалось загрузить информацию*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

@handle_errors_with_rate_limit
async def get_name(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = NAME
    
    text = update.message.text.strip()
    
    logger.info(f"🔍 get_name вызван с текстом: '{text}'")
    
    if text == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "🎙️ Добро пожаловать в студию Godspeed Records!\n\n"
            "✨ Профессиональная студия звукозаписи в самом сердце Санкт-Петербурга\n\n"
            "🎧 Чем можем вам помочь\n"
            "• Запись вокала и инструментов\n"
            "• Аренда студии на 12 часов\n"
            "• Сведение и мастеринг\n"
            "• Создание треков с нуля\n"
            "• Эксклюзивные биты и аранжировки\n\n"
            "🏆 Новая система достижений!\n"
            "• Получайте пластинки за записи\n"
            "• Открывайте уровни и скидки\n"
            "• Приводите друзей и зарабатывайте\n\n"
            "👇 Выберите подходящий вариант:",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    is_valid, error_msg = Config.validate_string_length(text, Config.MAX_NAME_LENGTH, "имя")
    if not is_valid:
        await update.message.reply_text(
            error_msg,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_menu_only_keyboard()
        )
        return NAME
    
    context.user_data['name'] = text
    context.user_data['safe_name'] = SecurityUtils.safe_markdown_text(text)
    
    await update.message.reply_text(
        "*📱 Шаг 2/7: Ввод контактов*\n\n"
        "*✨ Как с Вами связаться?*\n\n"
        "*Вы можете выбрать:*\n"
        "• Нажать кнопку \"Отправить контакт\"\n"
        "• Ввести контакты вручную\n\n"
        "*Вы можете указать:*\n"
        "• Номер телефона\n"
        "• Telegram username\n"
        "• Любой другой способ связи\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_contact_request()
    )
    return CONTACT

@handle_errors_with_rate_limit
async def get_contact(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = CONTACT
    
    text = update.message.text if update.message.text else ""
    
    if update.message.text:
        text = update.message.text.strip()
        
        if text == "↩️ Главное меню":
            return await handle_main_menu_button(update, context)
        
        if text not in ["↩️ Назад", "✏️ Ввести вручную"]:
            await update.message.reply_text(
                "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_contact_request()
            )
            return CONTACT
        
        if text == "↩️ Назад":
            await update.message.reply_text(
                "*👤 Шаг 1/7: Ввод имени*\n\n"
                "*✨ Здравствуйте! Как к Вам обращаться?*\n\n"
                "*Вы можете ввести:*\n"
                "• Настоящее имя — Мирон\n"
                "• Творческий псевдоним — Ex Sinner\n"
                "• Любое удобное для Вас имя\n\n"
                "*✏️ Введите ваше имя:*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_menu_only_keyboard()
            )
            return NAME
        
        if text == "✏️ Ввести вручную":
            await update.message.reply_text(
                "*✏️ Введите ваши контакты:*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_text_contact_input()
            )
            return CONTACT_INPUT
    
    if update.message.contact:
        contact = update.message.contact
        phone_number = contact.phone_number
        username = update.effective_user.username or ""
        
        if len(phone_number) > Config.MAX_CONTACT_LENGTH:
            await update.message.reply_text(
                f"❌ Максимально {Config.MAX_CONTACT_LENGTH} символов, слишком длинный номер телефона!",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_contact_request()
            )
            return CONTACT
        
        contact_info = f"{phone_number}"
        if username:
            contact_info += f" | @{username}"
        
        context.user_data['contact'] = contact_info
        context.user_data['safe_contact'] = SecurityUtils.safe_markdown_text(contact_info)
        
        await update.message.reply_text(
            "*🎧 Шаг 3/7: Выбор услуги*\n\n"
            "*✨ Какая услуга Вас интересует?*\n\n"
            "*Вы можете выбрать:*\n"
            "• Запись вокала — профессиональная запись\n"
            "• Запись инструментов — электро-гитара, акустическая гитара\n"
            "• 12-часовая аренда — полный доступ к студии\n"
            "• Сведение/мастеринг — доведение до идеала\n"
            "• Создание трека — создание трека с нуля\n"
            "• Аранжировка/Биты — готовые решения\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_services()
        )
        return SERVICE
    
    await update.message.reply_text(
        "*📱 Шаг 2/7: Ввод контактов*\n\n"
        "*✨ Как с Вами связаться?*\n\n"
        "*Вы можете выбрать:*\n"
        "• Нажать кнопку \"Отправить контакт\"\n"
        "• Ввести контакты вручную\n\n"
        "*Вы можете указать:*\n"
        "• Номер телефона\n"
        "• Telegram username\n"
        "• Любой другой способ связи\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_contact_request()
    )
    return CONTACT

@handle_errors_with_rate_limit
async def get_contact_input(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = CONTACT_INPUT
    
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        name = context.user_data.get('name', '')
        safe_name = SecurityUtils.safe_markdown_text(name)
        
        await update.message.reply_text(
            "*📱 Шаг 2/7: Ввод контактов*\n\n"
            "*✨ Как с Вами связаться?*\n\n"
            "*Вы можете выбрать:*\n"
            "• Нажать кнопку \"Отправить контакт\"\n"
            "• Ввести контакты вручную\n\n"
            "*Вы можете указать:*\n"
            "• Номер телефона\n"
            "• Telegram username\n"
            "• Любой другой способ связи\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_contact_request()
        )
        return CONTACT
    
    is_valid, error_msg = Config.validate_string_length(text, Config.MAX_CONTACT_LENGTH, "контакт")
    if not is_valid:
        keyboard = KeyboardManager.get_text_contact_input()
        
        await update.message.reply_text(
            error_msg,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return CONTACT_INPUT
    
    context.user_data['contact'] = text
    context.user_data['safe_contact'] = SecurityUtils.safe_markdown_text(text)
    
    await update.message.reply_text(
        "*🎧 Шаг 3/7: Выбор услуги*\n\n"
        "*✨ Какая услуга Вас интересует?*\n\n"
        "*Вы можете выбрать:*\n"
        "• Запись вокала — профессиональная запись\n"
        "• Запись инструментов — электро-гитара, акустическая гитара\n"
        "• 12-часовая аренда — полный доступ к студии\n"
        "• Сведение/мастеринг — доведение до идеала\n"
        "• Создание трека — создание трека с нуля\n"
        "• Аранжировка/Биты — готовые решения\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_services()
    )
    return SERVICE

@handle_errors_with_rate_limit
async def get_service(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = SERVICE
    
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    if text == "↩️ Назад":
        logger.info(f"🔍 Пользователь нажал 'Назад' в get_service")
        context.user_data.pop('with_engineer', None)
        context.user_data.pop('service', None)
        
        name = context.user_data.get('name', '')
        safe_name = SecurityUtils.safe_markdown_text(name)
        
        await update.message.reply_text(
            "*📱 Шаг 2/7: Ввод контактов*\n\n"
            "*✨ Как с Вами связаться?*\n\n"
            "*Вы можете выбрать:*\n"
            "• Нажать кнопку \"Отправить контакт\"\n"
            "• Ввести контакты вручную\n\n"
            "*Вы можете указать:*\n"
            "• Номер телефона\n"
            "• Telegram username\n"
            "• Любой другой способ связи\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_contact_request()
        )
        return CONTACT
    
    valid_services = [
        "🎤 Запись вокала", "🎸 Запись инструментов",
        "⏰ 12-часовая аренда", "🎚️ Сведение/мастеринг",
        "🎵 Создание трека", "🎹 Аранжировка/Биты"
    ]
    
    user_id = str(update.effective_user.id)
    
    # ===== ПРОВЕРКА ЛИМИТОВ ДЛЯ ВСЕХ УСЛУГ (КРОМЕ СОЗДАНИЯ ТРЕКА) =====
    if text == "🎚️ Сведение/мастеринг":
        is_allowed, message, current_count = UserLimits.check_user_limits(user_id, False)
        if not is_allowed:
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            return ConversationHandler.END
    
    elif text == "⏰ 12-часовая аренда":
        is_allowed, message, current_count = UserLimits.check_user_limits(user_id, True)
        if not is_allowed:
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            return ConversationHandler.END
    
    elif text in ["🎤 Запись вокала", "🎸 Запись инструментов"]:
        is_allowed, message, current_count = UserLimits.check_user_limits(user_id, True)
        if not is_allowed:
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            return ConversationHandler.END
    
    # ===== СОЗДАНИЕ ТРЕКА - ПРОВЕРКУ УБРАЛИ! ОНА БУДЕТ В get_track_creation_type() =====
    elif text == "🎵 Создание трека":
        # Проверка лимитов ПЕРЕНЕСЕНА в get_track_creation_type()
        # Здесь только устанавливаем данные и переходим к выбору формата
        pass
    
    keys_to_remove = [
        'is_12_hours', '12_hours_type', 'is_mixing', 'mixing_type',
        'is_track_creation', 'track_type', 'with_engineer', 
        'service', 'service_type', 'duration', 'time', 'date',
        'price', 'display_period', 'free_intervals', 'free_interval',
        'start_hour', 'end_hour', 'date_with_color', 'display_time',
        'suitable_intervals'
    ]
    for key in keys_to_remove:
        if key in context.user_data:
            context.user_data.pop(key)
    
    if text == "🎤 Запись вокала":
        context.user_data['service_type'] = "Запись вокала"
        
        await update.message.reply_text(
            "*👨‍🔧 Шаг 4/7: Выбор формата*\n\n"
            "*✨ Вам требуется помощь звукорежиссера?*\n\n"
            "*С инженером — рекомендуем:*\n"
            "• Профессиональная настройка оборудования\n"
            "• Помощь в процессе записи\n"
            "• Консультации по исполнению\n\n"
            "*Без инженера — для опытных:*\n"
            "• Самостоятельная работа в студии\n"
            "• Экономия 200₽ в час\n"
            "• Полный творческий контроль\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_engineer_options()
        )
        return ENGINEER_OPTION
    
    elif text == "🎸 Запись инструментов":
        context.user_data['service_type'] = "Запись инструментов"
        
        await update.message.reply_text(
            "*👨‍🔧 Шаг 4/7: Выбор формата*\n\n"
            "*✨ Вам требуется помощь звукорежиссера?*\n\n"
            "*С инженером — рекомендуем:*\n"
            "• Профессиональная настройка оборудования\n"
            "• Помощь в процессе записи\n"
            "• Консультации по исполнению\n\n"
            "*Без инженера — для опытных:*\n"
            "• Самостоятельная работа в студии\n"
            "• Экономия 200₽ в час\n"
            "• Полный творческий контроль\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_engineer_options()
        )
        return ENGINEER_OPTION
    
    elif text == "⏰ 12-часовая аренда":
        context.user_data['service'] = "⏰ 12-часовая аренда"
        context.user_data['service_type'] = "12-часовая аренда"
        context.user_data['is_12_hours'] = True
        context.user_data['with_engineer'] = False
        
        await update.message.reply_text(
            "*⏰ Шаг 4/6: Выбор формата*\n\n"
            "*✨ Когда для Вас забронировать студию?*\n\n"
            "*День — 7000₽ + залог (по договору)*\n"  
            "• Работа с 9:00 до 21:00\n"
            "• Полный контроль студии\n\n"
            "*Ночь — 6500₽ + залог (по договору)*\n"
            "• Работа с 21:00 до 9:00\n"
            "• Специальная ночная цена\n\n"
            "*👇 Выберите подходящий вариант:*", 
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_12_hours_options()
        )
        return TWELVE_HOURS_OPTION
    
    elif text == "🎚️ Сведение/мастеринг":
        context.user_data['service'] = "🎛️ Сведение/мастеринг"
        context.user_data['service_type'] = "🎛️ Сведение/мастеринг"
        context.user_data['is_mixing'] = True
        
        await update.message.reply_text(
            "*🎚️ Шаг 4/5: Выбор сведения*\n\n"
            "*✨ Что Вам требуется свести?*\n\n"
            "*Трек — 2500₽*\n"
            "• Профессиональное сведение\n"
            "• Мастеринг готового микса\n\n"
            "*Альбом — договорная*\n"
            "• Обсуждение проекта\n"
            "• Индивидуальный подход\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_mixing()
        )
        return MIXING_TYPE
    
    elif text == "🎵 Создание трека":
        context.user_data['service'] = "Создание трека"
        context.user_data['service_type'] = "Создание трека"
        context.user_data['is_track_creation'] = True
        context.user_data['with_engineer'] = True
        
        # Очищаем старые данные
        keys_to_remove = [
            'is_12_hours', '12_hours_type', 'is_mixing', 'mixing_type',
            'track_type', 'date', 'date_with_color', 'time', 'display_time',
            'duration', 'price', 'start_hour', 'end_hour', 'free_intervals',
            'suitable_intervals'
        ]
        for key in keys_to_remove:
            if key in context.user_data:
                context.user_data.pop(key)
        
        logger.info(f"🔍 Переход к выбору формата трека")
        
        await update.message.reply_text(
            "*🎵 Шаг 4/7: Выбор формата*\n\n"
            "*✨ Что Вам требуется создать?*\n\n"
            "*Трек — 9000₽*\n"
            "• Работа с инженером звукозаписи\n"
            "• Создание трека с нуля\n"
            "• Профессиональный подход\n\n"
            "*Альбом — договорная*\n"
            "• Обсуждение работы\n"
            "• Индивидуальный подход\n"
            "• Специальные условия\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_track_creation_options()
        )
        return TRACK_CREATION_TYPE
    
    elif text == "🎹 Аранжировка/Биты":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Написать продюсеру", url="https://t.me/Simweyy")]
        ])

        await update.message.reply_text(
            "*🎹 Аранжировка/Биты*\n\n"
            "*✨ Предлагаем Вам выбрать готовые решения или заказать индивидуальную работу:*\n\n"
            "*Готовые биты:*\n"
            "• MP3 Leasing — 1500₽\n"
            "• WAV Leasing — 2500₽\n"
            "• WAV TRACK OUT — 5000₽\n"
            "• EXCLUSIVE RIGHTS — от 10000₽\n\n"
            "*Заказной бит:*\n"
            "• Договорная цена\n"
            "• Обсуждение с продюсером\n"
            "• Индивидуальный подход\n\n"
            "[BEATS](t.me/godspeedbeats) — готовые биты\n"
            "[LOOPS](https://t.me/simweyloops) — лупы и сэмплы\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=keyboard
        )
        return SERVICE
    
    keyboard = KeyboardManager.get_services()
    
    await update.message.reply_text(
        "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    return SERVICE

@handle_errors_with_rate_limit
async def get_engineer_option(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = ENGINEER_OPTION
    
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    if text == "↩️ Назад":
        logger.info(f"🔍 Пользователь нажал 'Назад' в get_engineer_option")
        context.user_data.pop('with_engineer', None)
        context.user_data.pop('service', None)
        
        await update.message.reply_text(
            "*🎧 Шаг 3/7: Выбор услуги*\n\n"
            "*✨ Какая услуга Вас интересует?*\n\n"
            "*Вы можете выбрать:*\n"
            "• Запись вокала — профессиональная запись\n"
            "• Запись инструментов — электро-гитара, акустическая гитара\n"
            "• 12-часовая аренда — полный доступ к студии\n"
            "• Сведение/мастеринг — доведение до идеала\n"
            "• Создание трека — создание трека с нуля\n"
            "• Аранжировка/Биты — готовые решения\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_services()
        )
        return SERVICE
    
    valid_options = ["👨‍🔧 С инженером", "💪 Без инженера"]
    
    if text not in valid_options:
        reply_markup = ReplyKeyboardMarkup([
            ["👨‍🔧 С инженером", "💪 Без инженера"],
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True, one_time_keyboard=True)
        
        try:
            await update.message.edit_reply_markup(reply_markup=reply_markup)
            
            await update.message.reply_text(
                "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            
        except Exception as edit_error:
            logger.error(f"Ошибка редактирования клавиатуры: {edit_error}")
            
            await update.message.reply_text(
                "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        
        return ENGINEER_OPTION
    
    service_type = context.user_data.get('service_type', '')
    
    if service_type == "Запись вокала":
        full_service = f"🎤 {service_type} ({'с инженером' if text == '👨‍🔧 С инженером' else 'без инженера'})"
    elif service_type == "Запись инструментов":
        full_service = f"🎸 {service_type} ({'с инженером' if text == '👨‍🔧 С инженером' else 'без инженера'})"
    else:
        full_service = f"{service_type} ({'с инженером' if text == '👨‍🔧 С инженером' else 'без инженера'})"
    
    keys_to_remove = [
        'is_12_hours', '12_hours_type', 'is_mixing', 'mixing_type',
        'is_track_creation', 'track_type', 'free_intervals', 'free_interval',
        'start_hour', 'end_hour', 'date', 'date_with_color', 'time'
    ]
    for key in keys_to_remove:
        context.user_data.pop(key, None)
    
    context.user_data['service'] = full_service
    context.user_data['with_engineer'] = (text == "👨‍🔧 С инженером")
    context.user_data['is_mixing'] = False
    context.user_data['is_12_hours'] = False
    context.user_data['is_track_creation'] = False
    
    with_engineer = (text == "👨‍🔧 С инженером")
    
    if with_engineer:
        rules_text = (
            "*Правила для работы с инженером:*\n"
            "• Запись минимально за 48 часов\n"
        )
    else:
        rules_text = (
            "*Правила для работы без инженера:*\n"
            "• Запись минимально за 24 часа\n"
        )
    
    reply_markup = KeyboardManager.get_dates("vocal", with_engineer)
    
    await update.message.reply_text(
        "*📅 Шаг 5/7: Выбор даты*\n\n"
        "*✨ Когда для Вас забронировать студию?*\n\n"
        f"{rules_text}\n"
        "*Легенда цветов:*\n"
        "🟢 — Свободно более 18 часов \n"
        "🟡 — Свободно более 12 часов\n"
        "🟠 — Свободно более 6 часов\n"
        "🔴 — Свободно менее 6 часов\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return DATE

@handle_errors_with_rate_limit
async def get_twelve_hours_option(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = TWELVE_HOURS_OPTION
    
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*🎧 Шаг 3/7: Выбор услуги*\n\n"
            "*✨ Какая услуга Вас интересует?*\n\n"
            "*Вы можете выбрать:*\n"
            "• Запись вокала — профессиональная запись\n"
            "• Запись инструментов — электро-гитара, акустическая гитара\n"
            "• 12-часовая аренда — полный доступ к студии\n"
            "• Сведение/мастеринг — доведение до идеала\n"
            "• Создание трека — создание трека с нуля\n"
            "• Аранжировка/Биты — готовые решения\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_services()
        )
        return SERVICE
    
    is_day = any(day_text in text for day_text in ["☀️ День", "День (9-21)", "День"])
    is_night = any(night_text in text for night_text in ["🌙 Ночь", "Ночь (21-9)", "Ночь"])
    
    if not is_day and not is_night:
        logger.warning(f"❌ Неизвестный выбор: '{text}'")
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_12_hours_options()
        )
        return TWELVE_HOURS_OPTION
    
    if is_day:
        logger.info("✅ Выбран день (9-21)")
        keys_to_remove = [
            'is_mixing', 'mixing_type', 'is_track_creation', 'track_type',
            'with_engineer', 'display_period', 'free_intervals', 'free_interval',
            'start_hour', 'end_hour'
        ]
        for key in keys_to_remove:
            context.user_data.pop(key, None)
        
        context.user_data['12_hours_type'] = "День"
        context.user_data['time'] = "9-21"
        context.user_data['service'] = "⏰ 12-часовая аренда"
        context.user_data['is_12_hours'] = True
        context.user_data['booking_start_time'] = "День"
        service_type = "12_hours_day"
        selected_text = "☀️ День (9-21)"
    else:
        logger.info("✅ Выбрана ночь (21-9)")
        keys_to_remove = [
            'is_mixing', 'mixing_type', 'is_track_creation', 'track_type',
            'with_engineer', 'display_period', 'free_intervals', 'free_interval',
            'start_hour', 'end_hour'
        ]
        for key in keys_to_remove:
            context.user_data.pop(key, None)
        
        context.user_data['12_hours_type'] = "Ночь"
        context.user_data['time'] = "21-9"
        context.user_data['service'] = "⏰ 12-часовая аренда"
        context.user_data['is_12_hours'] = True
        context.user_data['booking_start_time'] = "Ночь"
        service_type = "12_hours_night"
        selected_text = "🌙 Ночь (21-9)"
    
    context.user_data['duration'] = 12
    context.user_data['service_type_check'] = service_type
    
    user_id = str(update.effective_user.id)
    is_allowed, message, current_count = UserLimits.check_user_limits(user_id, True)
    
    if not is_allowed:
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "*📅 Шаг 5/6: Выбор даты*\n\n"
        "*✨ Когда для Вас забронировать студию?*\n\n"
        "*Правила для аренды студии:*\n"
        "• Аренда минимально за 72 часа\n"
        "• Ровно 12 часов работы в студии\n"
        "• Без инженера звукозаписи\n\n"
        "*Легенда цветов:*\n"
        "🟢 — Слот доступен для бронирования\n"
        "🔴 — Слот недоступен для бронирования\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_dates(service_type, False)
    )
    return DATE

@handle_errors_with_rate_limit
async def get_mixing_type(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = MIXING_TYPE
    
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*🎧 Шаг 3/7: Выбор услуги*\n\n"
            "*✨ Какая услуга Вас интересует?*\n\n"
            "*Вы можете выбрать:*\n"
            "• Запись вокала — профессиональная запись\n"
            "• Запись инструментов — электро-гитара, акустическая гитара\n"
            "• 12-часовая аренда — полный доступ к студии\n"
            "• Сведение/мастеринг — доведение до идеала\n"
            "• Создание трека — создание трека с нуля\n"
            "• Аранжировка/Биты — готовые решения\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_services()
        )
        return SERVICE
    
    if text not in ["🎵 Трек", "💿 Альбом"]:
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_mixing()
        )
        return MIXING_TYPE
    
    mixing_type = text
    user_id = str(update.effective_user.id)
    
    if "Трек" in mixing_type:
        context.user_data['mixing_type'] = "Трек"
        context.user_data['service'] = "Сведение/мастеринг"
        context.user_data['is_mixing'] = True
        
        # ===== РАСЧЕТ ЦЕНЫ =====
        price_result = PriceCalculator.calculate(
            service=context.user_data['service'],
            duration=1,
            is_mixing=True,
            mixing_type="Трек",
            user_id=user_id,
            consume_coupon=False
        )
        
        context.user_data['price_result'] = price_result
        context.user_data['price'] = price_result['final_price']
        
        # ===== ФОРМИРУЕМ ТЕКСТ О СКИДКАХ =====
        discount_text = ""
        
        if price_result.get('level_discount_percent', 0) > 0:
            discount_text += f"\n• Скидка по уровню: {price_result['level_discount_percent']}%"
        
        if price_result.get('promo_discount_percent', 0) > 0:
            discount_text += f"\n• Промокод: {price_result['promo_discount_percent']}%"
        
        if price_result.get('free_service_applied', False) and price_result.get('promo_code_used'):
            discount_text += f"\n• Промокод: Бесплатная услуга"
        
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        
        # Очищаем услугу и тип от смайликов
        clean_service = context.user_data['service'].replace('', '').strip()
        clean_type = context.user_data.get('mixing_type', 'Не указан').replace('', '').strip()
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ (БЕЗ СМАЙЛИКОВ) =====
        confirmation_lines = [
            f"*✅ Шаг 5/5: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}",
            f"• Тип: {clean_type}",
            f"• Стоимость: {price_result['final_price']}₽"
        ]
        
        if discount_text:
            confirmation_lines.append(discount_text.lstrip('\n'))
        
        confirmation_lines.append("")
        confirmation_lines.append("*👇 Выберите подходящий вариант:*")
        
        confirmation_text = "\n".join(confirmation_lines)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM
    
    else:
        context.user_data['mixing_type'] = "Альбом"
        context.user_data['service'] = "Сведение/мастеринг"
        context.user_data['price'] = "Договорная"
        context.user_data['is_mixing'] = True
        
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        
        # ===== ОЧИЩАЕМ УСЛУГУ И ТИП ОТ СМАЙЛИКОВ =====
        clean_service = context.user_data['service'].replace('', '').strip()
        clean_type = context.user_data.get('mixing_type', 'Не указан').replace('', '').strip()
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ (БЕЗ СМАЙЛИКОВ) =====
        confirmation_lines = [
            f"*✅ Шаг 5/5: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}",
            f"• Тип: {clean_type}",
            f"• Стоимость: Договорная",
            "",
            "*👇 Выберите подходящий вариант:*"
        ]
        
        confirmation_text = "\n".join(confirmation_lines)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM

@handle_errors_with_rate_limit
async def get_track_creation_type(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = TRACK_CREATION_TYPE
    
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*🎧 Шаг 3/7: Выбор услуги*\n\n"
            "*✨ Какая услуга Вас интересует?*\n\n"
            "*Вы можете выбрать:*\n"
            "• Запись вокала — профессиональная запись\n"
            "• Запись инструментов — электро-гитара, акустическая гитара\n"
            "• 12-часовая аренда — полный доступ к студии\n"
            "• Сведение/мастеринг — доведение до идеала\n"
            "• Создание трека — создание трека с нуля\n"
            "• Аранжировка/Биты — готовые решения\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_services()
        )
        return SERVICE
    
    if text == "🎵 Трек":
        user_id = str(update.effective_user.id)
        
        # ===== ПРОВЕРКА ЛИМИТА ЗАПИСЕЙ С ДАТОЙ (2) =====
        is_allowed, message, current_count = UserLimits.check_user_limits(user_id, True)
        if not is_allowed:
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            return ConversationHandler.END
        
        # Очищаем старые данные
        keys_to_remove = [
            'is_12_hours', '12_hours_type', 'is_mixing', 'mixing_type',
            'date', 'date_with_color', 'time', 'display_time',
            'duration', 'price', 'start_hour', 'end_hour', 'free_intervals',
            'suitable_intervals'
        ]
        for key in keys_to_remove:
            context.user_data.pop(key, None)
        
        context.user_data['is_track_creation'] = True
        context.user_data['track_type'] = "Трек"
        context.user_data['service'] = "Создание трека"
        context.user_data['price'] = 9000
        context.user_data['with_engineer'] = True
        
        await update.message.reply_text(
            "*📅 Шаг 5/7: Выбор даты*\n\n"
            "*✨ Когда для Вас забронировать студию?*\n\n"
            "*Правила для создания трека:*\n"
            "• Запись минимально за 72 часа\n"
            "• От 4 часов работы в студии\n"
            "• Обязательно с инженером звукозаписи\n\n"
            "*Легенда цветов:*\n"
            "🟢 — Есть 4-часовые слоты\n"
            "🟠 — Есть 4-часовые слоты только через полночь\n"
            "🔴 — Нет 4-часовых слотов\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_dates("track_creation", True)
        )
        return DATE
    
    elif text == "💿 Альбом":
        user_id = str(update.effective_user.id)
        
        # ===== ПРОВЕРКА ЛИМИТА ДОГОВОРНЫХ ЗАПИСЕЙ (3) =====
        is_allowed, message, current_count = UserLimits.check_user_limits(user_id, False)
        if not is_allowed:
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            return ConversationHandler.END
        
        # Очищаем старые данные
        keys_to_remove = [
            'is_12_hours', '12_hours_type', 'is_mixing', 'mixing_type',
            'with_engineer', 'date', 'date_with_color', 'time', 'display_time',
            'duration', 'price', 'start_hour', 'end_hour', 'free_intervals'
        ]
        for key in keys_to_remove:
            context.user_data.pop(key, None)
        
        context.user_data['is_track_creation'] = True
        context.user_data['track_type'] = "Альбом"
        context.user_data['price'] = "Договорная"
        context.user_data['date'] = "Не указана (договорная)"
        context.user_data['time'] = "Не указано (договорная)"
        
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        
        # ===== ОЧИЩАЕМ УСЛУГУ И ТИП ОТ СМАЙЛИКОВ =====
        clean_service = context.user_data['service'].replace('', '').strip()
        clean_type = context.user_data.get('track_type', 'Не указан').replace('', '').strip()
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ =====
        confirmation_lines = [
            f"*✅ Шаг 5/5: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}",
            f"• Тип: {clean_type}",
            f"• Стоимость: Договорная",
            "",
            "*👇 Выберите подходящий вариант:*"
        ]
        
        confirmation_text = "\n".join(confirmation_lines)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM
    
    else:
        reply_markup = ReplyKeyboardMarkup([
            ["🎵 Трек", "💿 Альбом"],
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return TRACK_CREATION_TYPE

async def handle_no_date_option(update: Update, context):
    """Обработка выбора 'Договорная (без даты)'"""
    logger.info("🔍 Выбрана договорная запись без даты")
    
    is_mixing = context.user_data.get('is_mixing', False)
    is_track_creation = context.user_data.get('is_track_creation', False)
    
    if is_mixing:
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        
        # Очищаем услугу от смайликов
        clean_service = context.user_data['service'].replace('', '').strip()
        clean_type = context.user_data.get('mixing_type', 'Не указан').replace('', '').strip()
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ =====
        confirmation_lines = [
            f"*✅ Шаг 5/5: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}",
            f"• Тип: {clean_type}",
            f"• Стоимость: Договорная",
            "",
            "*👇 Выберите подходящий вариант:*"
        ]
        
        confirmation_text = "\n".join(confirmation_lines)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM
    
    elif is_track_creation:
        track_type = context.user_data.get('track_type', '')
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        
        # Очищаем услугу и тип от смайликов
        clean_service = context.user_data['service'].replace('', '').strip()
        clean_type = track_type.replace('', '').strip()
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ =====
        confirmation_lines = [
            f"*✅ Шаг 5/5: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}",
            f"• Тип: {clean_type}",
            f"• Стоимость: Договорная",
            "",
            "*👇 Выберите подходящий вариант:*"
        ]
        
        confirmation_text = "\n".join(confirmation_lines)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM
    
    else:
        context.user_data['date'] = "Не указана (договорная)"
        context.user_data['time'] = "Не указано (договорная)"
        context.user_data['is_contractual'] = True
        
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        
        # Очищаем услугу от смайликов
        clean_service = context.user_data['service'].replace('', '').replace('', '').replace('', '').replace('', '').replace('', '').replace('', '').replace('', '').strip()
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ =====
        confirmation_lines = [
            f"*✅ Шаг 5/5: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}",
            f"• Стоимость: Договорная",
            "",
            "*👇 Выберите подходящий вариант:*"
        ]
        
        confirmation_text = "\n".join(confirmation_lines)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM

@handle_errors_with_rate_limit
async def pending_command(update: Update, context):
    """Команда /pending - показать все ожидающие записи (только для админов)"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этой команды!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text(
        "*🔍 Ищу ожидающие подтверждения записи...*",
        parse_mode="Markdown"
    )
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, timestamp, name, contact, service, date_str, time_slot, price,
                       is_mixing, mixing_type, is_track_creation, track_type,
                       is_12_hours, twelve_hours_type, with_engineer, duration,
                       telegram_id, level_discount_percent, promo_discount_percent, promo_code_used
                FROM bookings 
                WHERE status = 'pending'
                AND service NOT LIKE '%Админ%'
                AND service NOT LIKE '%админ%'
                ORDER BY timestamp ASC
            ''')
            
            pending_bookings = cursor.fetchall()
            
            if not pending_bookings:
                await update.message.reply_text(
                    "*✅ Нет ожидающих подтверждения заявок*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                )
                return
            
            sent_count = 0
            for booking in pending_bookings:
                (booking_id, timestamp, name, contact, service, date_str, time_slot, price,
                 is_mixing, mixing_type, is_track_creation, track_type,
                 is_12_hours, twelve_hours_type, with_engineer, duration,
                 telegram_id, level_discount_percent, promo_discount_percent, promo_code_used) = booking
                
                display_date = date_str
                if date_str and '(' in date_str:
                    display_date = date_str.split('(')[0].strip()
                
                # ===== ИСПРАВЛЕНО: format_time_for_display() нормализует 24→00 =====
                display_time = time_slot
                if time_slot and '-' in time_slot:
                    display_time = DateTimeUtils.format_time_for_display(time_slot)
                
                # ===== ФОРМИРУЕМ ТЕКСТ СО СКИДКАМИ (БЕЗ ЛИШНИХ ПРОБЕЛОВ) =====
                discount_lines = []
                if level_discount_percent and level_discount_percent > 0:
                    discount_lines.append(f"🎟 Скидка по уровню: {level_discount_percent}%")
                if promo_discount_percent and promo_discount_percent > 0:
                    discount_lines.append(f"🎟 Промокод: {promo_discount_percent}%")
                if promo_code_used:
                    discount_lines.append(f"🎟 Код промокода: {promo_code_used}")
                
                discount_text = ""
                if discount_lines:
                    discount_text = "\n" + "\n".join(discount_lines)
                
                # Формируем сообщение в зависимости от типа услуги
                if is_12_hours:
                    try:
                        price_int = int(float(price)) if price else 0
                        rent_price_display = f"{price_int}₽ + залог"
                    except:
                        rent_price_display = f"{price}₽ + залог" if price else "0₽ + залог"
                    
                    message_text = (
                        f"🚨 Новая заявка! #{booking_id}\n\n"
                        f"👤 Пользователь: {name}\n"
                        f"📱 Контакт: {contact}\n"
                        f"🎧 Услуга: {service}\n"
                        f"⏰ Тип аренды: {twelve_hours_type}\n"
                        f"📅 Дата: {display_date}\n"
                        f"🕐 Время: {display_time} (12 часов)\n"
                        f"💰 Стоимость аренды: {rent_price_display}{discount_text}\n\n"
                        f"📅 Создана: {timestamp}\n\n"
                        f"*👇 Подтвердить или отклонить?*"
                    )
                    
                elif is_mixing:
                    mix_type = mixing_type if mixing_type else "Не указан"
                    try:
                        price_int = int(float(price)) if price else 0
                        price_text = "Договорная" if price_int == 0 else f"{price_int}₽"
                    except:
                        price_text = "Договорная" if "Договорная" in str(price) else f"{price}₽"
                    
                    message_text = (
                        f"🚨 Новая заявка! #{booking_id}\n\n"
                        f"👤 Пользователь: {name}\n"
                        f"📱 Контакт: {contact}\n"
                        f"🎧 Услуга: {service}\n"
                        f"🎚️ Тип работы: {mix_type}\n"
                        f"💰 Стоимость: {price_text}{discount_text}\n\n"
                        f"📅 Создана: {timestamp}\n\n"
                        f"*👇 Подтвердить или отклонить?*"
                    )
                    
                elif is_track_creation:
                    track_type_text = track_type if track_type else "Не указан"
                    try:
                        price_int = int(float(price)) if price else 0
                        price_text = "Договорная" if price_int == 0 else f"{price_int}₽"
                    except:
                        price_text = "Договорная" if "Договорная" in str(price) else f"{price}₽"
                    
                    message_text = f"🚨 Новая заявка! #{booking_id}\n\n"
                    message_text += f"👤 Пользователь: {name}\n"
                    message_text += f"📱 Контакт: {contact}\n"
                    message_text += f"🎧 Услуга: {service}\n"
                    message_text += f"🎵 Тип: {track_type_text}\n"
                    
                    if date_str and 'Не указана' not in date_str:
                        message_text += f"📅 Дата: {display_date}\n"
                    if time_slot and time_slot not in ['Не указано', 'Не указано (договорная)']:
                        message_text += f"⏰ Время: {display_time} (4 часа)\n"
                    
                    message_text += f"💰 Стоимость: {price_text}{discount_text}\n\n"
                    message_text += f"📅 Создана: {timestamp}\n\n"
                    message_text += f"*👇 Подтвердить или отклонить?*"
                    
                else:
                    duration_text = ""
                    if duration and duration > 0:
                        duration_text = f" ({PriceCalculator.format_hours_ru(duration)})"
                    
                    try:
                        price_int = int(float(price)) if price else 0
                        price_text = f"{price_int}₽" if price_int > 0 else "0₽"
                    except:
                        price_text = f"{price}₽"
                    
                    message_text = f"🚨 Новая заявка! #{booking_id}\n\n"
                    message_text += f"👤 Пользователь: {name}\n"
                    message_text += f"📱 Контакт: {contact}\n"
                    message_text += f"🎧 Услуга: {service}\n"
                    
                    if date_str and 'Не указана' not in date_str:
                        message_text += f"📅 Дата: {display_date}\n"
                    if time_slot and time_slot not in ['Не указано', 'Не указано (договорная)']:
                        message_text += f"⏰ Время: {display_time}{duration_text}\n"
                    if price and price != '0':
                        message_text += f"💰 Стоимость: {price_text}{discount_text}\n"
                    
                    message_text += f"\n📅 Создана: {timestamp}\n\n"
                    message_text += f"*👇 Подтвердить или отклонить?*"
                
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{booking_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{booking_id}")
                    ]
                ])
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                sent_count += 1
            
            await update.message.reply_text(
                f"*✅ Найдено и отправлено {sent_count} ожидающих заявок*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка в pending_command: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            f"❌ Ошибка при получении заявок: {str(e)}",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

@handle_errors_with_rate_limit
async def get_date(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    context.user_data['_conversation_state'] = DATE
    
    text = update.message.text.strip()
    
    logger.info(f"🔍 get_date вызван: '{text}'")
    logger.info(f"🔍 Текущее время: {DateTimeUtils.now()}")
    
    if text == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    if text == "↩️ Назад":
        logger.info(f"🔍 Пользователь нажал 'Назад' на шаге DATE")
        
        is_track_creation = context.user_data.get('is_track_creation', False)
        is_12_hours = context.user_data.get('is_12_hours', False)
        is_mixing = context.user_data.get('is_mixing', False)
        with_engineer = context.user_data.get('with_engineer', False)
        
        keys_to_remove = [
            'free_intervals', 'free_interval', 'time', 'display_time',
            'duration', 'price', 'date_with_color', 'display_period',
            'start_hour', 'end_hour', 'suitable_intervals', 'date'
        ]
        for key in keys_to_remove:
            context.user_data.pop(key, None)
        
        if is_track_creation:
            await update.message.reply_text(
                "*🎵 Шаг 4/7: Выбор формата*\n\n"
                "*✨ Что Вам требуется создать?*\n\n"
                "*Трек — 9000₽*\n"
                "• Работа с инженером звукозаписи\n"
                "• Создание трека с нуля\n"
                "• Профессиональный подход\n\n"
                "*Альбом — договорная*\n"
                "• Обсуждение работы\n"
                "• Индивидуальный подход\n"
                "• Специальные условия\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_track_creation_options()
            )
            return TRACK_CREATION_TYPE
            
        elif is_12_hours:
            await update.message.reply_text(
                "*⏰ Шаг 4/6: Выбор формата*\n\n"
                "*✨ Когда для Вас забронировать студию?*\n\n"
                "*День — 7000₽ + залог (по договору)*\n"  
                "• Работа с 9:00 до 21:00\n"
                "• Полный контроль студии\n\n"
                "*Ночь — 6500₽ + залог (по договору)*\n"
                "• Работа с 21:00 до 9:00\n"
                "• Специальная ночная цена\n\n"
                "*👇 Выберите подходящий вариант:*",  
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_12_hours_options()
            )
            return TWELVE_HOURS_OPTION
            
        elif is_mixing:
            await update.message.reply_text(
                "🎚️ Шаг 4/5: Тип сведения\n\n"
                "✨ Что Вам требуется свести?\n\n"
                "Трек — 2 500₽\n"
                "• Профессиональное сведение\n"
                "• Мастеринг готового микса\n\n"
                "Альбом — договорная\n"
                "• Обсуждение проекта\n"
                "• Индивидуальный подход\n\n"
                "👇 Выберите подходящий вариант:",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_mixing()
            )
            return MIXING_TYPE
            
        else:
            service_type = context.user_data.get('service_type', '')
            
            if service_type == "Запись вокала":
                await update.message.reply_text(
                    "*👨‍🔧 Шаг 4/7: Выбор формата*\n\n"
                    "*✨ Вам требуется помощь звукорежиссера?*\n\n"
                    "*С инженером — рекомендуем:*\n"
                    "• Профессиональная настройка оборудования\n"
                    "• Помощь в процессе записи\n"
                    "• Консультации по исполнению\n\n"
                    "*Без инженера — для опытных:*\n"
                    "• Самостоятельная работа в студии\n"
                    "• Экономия 200₽ в час\n"
                    "• Полный творческий контроль\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_engineer_options()
                )
                return ENGINEER_OPTION
                
            elif service_type == "Запись инструментов":
                await update.message.reply_text(
                    "*👨‍🔧 Шаг 4/7: Выбор формата*\n\n"
                    "*✨ Вам требуется помощь звукорежиссера?*\n\n"
                    "*С инженером — рекомендуем:*\n"
                    "• Профессиональная настройка оборудования\n"
                    "• Помощь в процессе записи\n"
                    "• Консультации по исполнению\n\n"
                    "*Без инженера — для опытных:*\n"
                    "• Самостоятельная работа в студии\n"
                    "• Экономия 200₽ в час\n"
                    "• Полный творческий контроль\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_engineer_options()
                )
                return ENGINEER_OPTION
                
            else:
                await update.message.reply_text(
                    "✅ Контакт успешно получен!\n\n"
                    "*🎧 Шаг 3/7: Выбор услуги*\n\n"
                    "*✨ Какая услуга Вас интересует?*\n\n"
                    "*Вы можете выбрать:*\n"
                    "• Запись вокала — профессиональная запись\n"
                    "• Запись инструментов — электро-гитара, акустическая гитара\n"
                    "• 12-часовая аренда — полный доступ к студии\n"
                    "• Сведение/мастеринг — доведение до идеала\n"
                    "• Создание трека — создание трека с нуля\n"
                    "• Аранжировка/Биты — готовые решения\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_services()
                )
                return SERVICE
    
    if text == "Договорная (без даты)":
        return await handle_no_date_option(update, context)
    
    if '.' in text:
        return await handle_date_selection(update, context, text)
    
    if '-' in text and text.count('-') == 1:
        parts = text.split('-')
        if len(parts) == 2:
            start_part = parts[0].strip()
            end_part = parts[1].strip()
            
            start_clean = start_part.lstrip('0') if start_part != '0' else '0'
            end_clean = end_part.lstrip('0') if end_part != '0' else '0'
            
            if start_clean.isdigit() and end_clean.isdigit():
                is_track_creation = context.user_data.get('is_track_creation', False)
                is_12_hours = context.user_data.get('is_12_hours', False)
                with_engineer = context.user_data.get('with_engineer', False)
                
                if is_track_creation:
                    reply_markup = KeyboardManager.get_dates("track_creation", True)
                elif is_12_hours:
                    service_type = "12_hours_day" if context.user_data.get('12_hours_type', '').startswith('День') else "12_hours_night"
                    reply_markup = KeyboardManager.get_dates(service_type, False)
                else:
                    reply_markup = KeyboardManager.get_dates("vocal", with_engineer)
                
                await update.message.reply_text(
                    "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*",
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
                return DATE
    
    is_track_creation = context.user_data.get('is_track_creation', False)
    is_12_hours = context.user_data.get('is_12_hours', False)
    with_engineer = context.user_data.get('with_engineer', False)
    
    if is_track_creation:
        reply_markup = KeyboardManager.get_dates("track_creation", True)
    elif is_12_hours:
        service_type = "12_hours_day" if context.user_data.get('12_hours_type', '').startswith('День') else "12_hours_night"
        reply_markup = KeyboardManager.get_dates(service_type, False)
    else:
        reply_markup = KeyboardManager.get_dates("vocal", with_engineer)
    
    await update.message.reply_text(
        "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return DATE

async def handle_date_selection(update: Update, context, text: str):
    """Обработка выбора даты"""
    
    if text == "Договорная (без даты)":
        is_mixing = context.user_data.get('is_mixing', False)
        if is_mixing:
            safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
            safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
            
            confirmation_text = (
                "*✅ Шаг 5/5: Подтверждение записи на сведение*\n\n"
                "*✨ Проверьте свои данные:*\n\n"
                f"👤 Имя: {safe_name}\n"
                f"📱 Контакт: {safe_contact}\n"
                f"🎧 Услуга: {context.user_data['service']}\n"
                f"🎚️ Тип работы: {context.user_data.get('mixing_type', 'Не указан')}\n"
                f"💰 Стоимость: Договорная\n\n"
                "*📝 Администратор свяжется с вами для обсуждения деталей*\n\n"
                "*👇 Всё верно?*"
            )
            
            await update.message.reply_text(
                confirmation_text,
                reply_markup=KeyboardManager.get_confirmation(),
                parse_mode="Markdown"
            )
            return CONFIRM
    
    parsed_date, error_msg = DateTimeUtils.parse_date_input(text)
    
    original_text = text
    clean_text = text
    
    if not parsed_date:
        if text and len(text) > 2 and text[0] in "🟢🟡🟠🔴⚪️":
            clean_text = text[2:].strip()
            logger.info(f"🔍 Убрали эмодзи: '{clean_text}'")
        
        if '(' in clean_text:
            clean_text = clean_text.split('(')[0].strip()
            logger.info(f"🔍 Убрали день недели: '{clean_text}'")
        
        parsed_date, error_msg = DateTimeUtils.parse_date_input(clean_text)
        
        if parsed_date:
            logger.info(f"🔍 Успешно спарсили после очистки: '{clean_text}'")
            context.user_data['date_with_color'] = original_text
            context.user_data['date'] = clean_text
        else:
            logger.error(f"🔍 Не удалось спарсить даже после очистки: '{clean_text}'")
            context.user_data['date_with_color'] = original_text
            context.user_data['date'] = original_text
    else:
        context.user_data['date_with_color'] = text
        context.user_data['date'] = text
    
    if not parsed_date:
        logger.error(f"🔍 НЕВОЗМОЖНО спарсить дату: '{text}', ошибка: {error_msg}")
        
        is_track_creation = context.user_data.get('is_track_creation', False)
        is_12_hours = context.user_data.get('is_12_hours', False)
        is_mixing = context.user_data.get('is_mixing', False)
        with_engineer = context.user_data.get('with_engineer', False)
        
        if is_track_creation:
            await update.message.reply_text(
                "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("track_creation", True)
            )
        elif is_12_hours:
            service_type = "12_hours_day" if context.user_data.get('12_hours_type', '').startswith('День') else "12_hours_night"
            await update.message.reply_text(
                "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates(service_type, False)
            )
        else:
            await update.message.reply_text(
                "*❌ Неверный формат даты! Используйте формат ДД.ММ.ГГГГ, например: 01.10.2026 или 02.10.2026 (Пт)!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("vocal", with_engineer)
            )
        return DATE
    
    today = DateTimeUtils.now()
    
    if parsed_date.date() < today.date():
        is_track_creation = context.user_data.get('is_track_creation', False)
        is_12_hours = context.user_data.get('is_12_hours', False)
        with_engineer = context.user_data.get('with_engineer', False)
        
        if is_track_creation:
            await update.message.reply_text(
                f"*❌ Дата уже прошла! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("track_creation", True)
            )
        elif is_12_hours:
            service_type = "12_hours_day" if context.user_data.get('12_hours_type', '').startswith('День') else "12_hours_night"
            await update.message.reply_text(
                f"*❌ Дата уже прошла! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates(service_type, False)
            )
        else:
            await update.message.reply_text(
                f"*❌ Дата уже прошла! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("vocal", with_engineer)
            )
        return DATE
    
    max_date = today + timedelta(days=Config.MAX_BOOKING_DAYS)
    
    if parsed_date.date() > max_date.date():
        is_track_creation = context.user_data.get('is_track_creation', False)
        is_12_hours = context.user_data.get('is_12_hours', False)
        with_engineer = context.user_data.get('with_engineer', False)
        
        if is_track_creation:
            await update.message.reply_text(
                f"*❌ Слишком поздно! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("track_creation", True)
            )
        elif is_12_hours:
            service_type = "12_hours_day" if context.user_data.get('12_hours_type', '').startswith('День') else "12_hours_night"
            await update.message.reply_text(
                f"*❌ Слишком поздно! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates(service_type, False)
            )
        else:
            await update.message.reply_text(
                f"*❌ Слишком поздно! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("vocal", with_engineer)
            )
        return DATE
    
    is_12_hours = context.user_data.get('is_12_hours', False)
    
    if is_12_hours:
        clean_date = context.user_data['date']
        date_str = parsed_date.strftime('%d.%m.%Y')
        twelve_hours_type = context.user_data.get('12_hours_type', '')
        
        logger.info(f"🔍 Проверка 12-часовой аренды на дату: {date_str}")
        logger.info(f"🔍 Тип аренды: {twelve_hours_type}")
        
        if 'Ночь' in twelve_hours_type or "night" in twelve_hours_type.lower():
            service_type = "12_hours_night"
            target_time_slot = "21-9"
            start_hour = 21
            rent_price = 6500
        else:
            service_type = "12_hours_day"
            target_time_slot = "9-21"
            start_hour = 9
            rent_price = 7000
        
        booking_datetime = DateTimeUtils.get_booking_datetime(date_str, target_time_slot)
        if not booking_datetime:
            await update.message.reply_text(
                f"*❌ Этот слот занят на эту дату! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates(service_type, False)
            )
            return DATE
        
        now = DateTimeUtils.now()
        time_until_booking = booking_datetime - now
        hours_until_booking = time_until_booking.total_seconds() / 3600
        
        logger.info(f"🔍 До начала аренды: {hours_until_booking:.1f} часов")
        
        if hours_until_booking < 72:
            await update.message.reply_text(
                f"*❌ Этот слот занят на эту дату! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates(service_type, False)
            )
            return DATE
        
        is_available = BookingManager.check_12_hours_slot_available(date_str, service_type)
        
        logger.info(f"🔍 Результат проверки доступности: {is_available}")
        
        if not is_available:
            await update.message.reply_text(
                f"*❌ Этот слот занят на эту дату! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates(service_type, False)
            )
            return DATE
        
        # ===== СОХРАНЯЕМ ДАННЫЕ =====
        context.user_data['time'] = target_time_slot
        context.user_data['display_time'] = target_time_slot
        context.user_data['duration'] = 12
        context.user_data['rent_price'] = rent_price
        
        logger.info(f"✅ Дата {date_str} свободна для {service_type} аренды")
        
        # ===== ПЕРЕХОДИМ К SHOW_SLOTS =====
        context.user_data['_conversation_state'] = SHOW_SLOTS
        
        await show_slots(update, context)
        return SHOW_SLOTS
    
    is_mixing = context.user_data.get('is_mixing', False)
    is_track_creation = context.user_data.get('is_track_creation', False)
    with_engineer = context.user_data.get('with_engineer', False)
    
    free_intervals = FreeIntervalCalculator.get_all_free_intervals(
        clean_text, is_track_creation, with_engineer
    )
    
    logger.info(f"🔍 Свободные интервалы на {clean_text}: {len(free_intervals) if free_intervals else 0}")
    
    if not free_intervals:
        if is_track_creation:
            await update.message.reply_text(
                f"*❌ Все слоты заняты на эту дату! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("track_creation", True)
            )
        else:
            await update.message.reply_text(
                f"*❌ Все слоты заняты на эту дату! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("vocal", with_engineer)
            )
        return DATE
    
    context.user_data['free_intervals'] = free_intervals
    
    date_color = ""
    date_with_color = context.user_data.get('date_with_color', '')
    if date_with_color and len(date_with_color) > 0 and date_with_color[0] in "🟢🟡🟠🔴⚪️":
        date_color = date_with_color[0]
    else:
        if is_track_creation:
            date_color = DateColorAnalyzer.get_color_for_date(clean_text, "track_creation", True)
        elif is_12_hours:
            service_type = "12_hours_day" if context.user_data.get('12_hours_type', '').startswith('День') else "12_hours_night"
            date_color = DateColorAnalyzer.get_color_for_date(clean_text, service_type, False)
        else:
            date_color = DateColorAnalyzer.get_color_for_date(clean_text, "vocal", with_engineer)
    
    # ============================================================
    # ===== БЛОК ДЛЯ СОЗДАНИЯ ТРЕКА (ШАГ 6) =====
    # ============================================================
    if is_track_creation and "Договорная" not in str(context.user_data.get('track_type', '')):
        suitable_intervals = []
        has_direct_4h_slot = False
        has_cross_night_slot = False
        
        clean_date_for_parse = clean_text
        if '(' in clean_date_for_parse:
            clean_date_for_parse = clean_date_for_parse.split('(')[0].strip()
        
        added_intervals = set()
        
        for interval in free_intervals:
            interval_key = f"{interval['start']}-{interval['end']}"
            
            if interval['duration'] >= 4 and interval_key not in added_intervals:
                has_direct_4h_slot = True
                suitable_intervals.append(interval)
                added_intervals.add(interval_key)
                logger.info(f"🔍 Найден прямой 4-часовой слот: {interval['start']}-{interval['end']}")
            
            elif interval['end'] == 24 and interval['start'] >= 20 and interval_key not in added_intervals:
                try:
                    current_date = datetime.strptime(clean_date_for_parse, '%d.%m.%Y')
                    next_date = current_date + timedelta(days=1)
                    next_date_str = next_date.strftime('%d.%m.%Y')
                    
                    logger.info(f"🔍 Проверка следующего дня для кросс-ночного слота: {next_date_str}")
                    
                    next_day_intervals = FreeIntervalCalculator.get_all_free_intervals(
                        next_date_str, is_track_creation, with_engineer
                    )
                    
                    for next_interval in next_day_intervals:
                        if next_interval['start'] == 0:
                            total_hours = interval['duration'] + next_interval['duration']
                            if total_hours >= 4 and interval_key not in added_intervals:
                                has_cross_night_slot = True
                                suitable_intervals.append(interval)
                                added_intervals.add(interval_key)
                                logger.info(f"🔍 Найден кросс-ночной слот: {interval['start']}-{interval['end']} + следующий день ({next_interval['start']}-{next_interval['end']})")
                                break
                except Exception as e:
                    logger.error(f"Ошибка проверки следующего дня: {e}")
        
        for interval in free_intervals:
            interval_key = f"{interval['start']}-{interval['end']}"
            if interval['start'] == 0 and interval['duration'] >= 4 and interval_key not in added_intervals:
                has_direct_4h_slot = True
                suitable_intervals.append(interval)
                added_intervals.add(interval_key)
                logger.info(f"🔍 Найден прямой 4-часовой слот после полуночи: {interval['start']}-{interval['end']}")
        
        if not has_direct_4h_slot and not has_cross_night_slot:
            await update.message.reply_text(
                f"*❌ Все слоты заняты на эту дату! Выберите доступную дату!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("track_creation", True)
            )
            return DATE
        else:
            context.user_data['suitable_intervals'] = suitable_intervals
            logger.info(f"✅ Найдены подходящие интервалы для трека: {len(suitable_intervals)}")
            
            # ===== ИСПРАВЛЕННОЕ СООБЩЕНИЕ ДЛЯ ШАГА 6 ТРЕКА =====
            message = f"*🎵 Шаг 6/7: Выбор времени*\n\n"
            
            message += f"*✨ Во сколько для Вас забронировать студию?*\n\n"
            message += f"*Свободное время:*\n"
            if suitable_intervals:
                for interval in suitable_intervals:
                    if interval['end'] == 24 and interval['start'] >= 20:
                        start_display = f"{interval['start']:02d}"
                        message += f"{date_color} {start_display}:00 — 00:00 ({interval['duration']} часов)\n"
                    else:
                        start_display = f"{interval['start']:02d}"
                        end_display = "00" if interval['end'] == 24 else f"{interval['end']:02d}"
                        message += f"{date_color} {start_display}:00 — {end_display}:00 ({interval['duration']} часов доступно)\n"
            else:
                message += f"❌ Нет свободных интервалов\n"
            
            message += f"\n*Ночная надбавка при работе с инженером:*\n"
            message += f"• С 00:00 до 06:00 +200₽ в час\n\n"
            
            message += f"*✏️ Введите время в формате час-час:*"
            
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_time_input()
            )
            context.user_data['_conversation_state'] = SHOW_SLOTS
            return SHOW_SLOTS
    # ============================================================
    # ===== КОНЕЦ БЛОКА ДЛЯ ТРЕКА =====
    # ============================================================
    
    if not is_mixing and not (is_track_creation and "Договорная" in str(context.user_data.get('track_type', ''))):
        user_id = str(update.effective_user.id)
        is_allowed, message, current_count = UserLimits.check_user_limits(user_id, True)
        
        if not is_allowed:
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            return ConversationHandler.END
    
    if is_mixing:
        mixing_type = context.user_data.get('mixing_type', '')
        
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        
        if "Договорная" in str(context.user_data.get('price', '')):
            confirmation_text = (
                "*✅ Шаг 5/5: Подтверждение записи на сведение*\n\n"
                "*✨ Проверьте свои данные:*\n\n"
                f"👤 Имя: {safe_name}\n"
                f"📱 Контакт: {safe_contact}\n"
                f"🎧 Услуга: {context.user_data['service']}\n"
                f"🎚️ Тип работы: {mixing_type}\n"
                f"💰 Стоимость: Договорная\n\n"
                "*📝 Администратор свяжется с вами для обсуждения деталей*\n\n"
                "*👇 Всё верно?*"
            )
        else:
            confirmation_text = (
                "*✅ Шаг 5/5: Подтверждение записи на сведение*\n\n"
                "*✨ Проверьте свои данные:*\n\n"
                f"👤 Имя: {safe_name}\n"
                f"📱 Контакт: {safe_contact}\n"
                f"🎧 Услуга: {context.user_data['service']}\n"
                f"🎚️ Тип работы: {mixing_type}\n"
                f"💰 Стоимость: {context.user_data.get('price', 0)}₽\n\n"
                "*📝 Администратор свяжется с вами для обсуждения деталей*\n\n"
                "*👇 Всё верно?*"
            )
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM
    
    elif is_track_creation:
        track_type = context.user_data.get('track_type', '')
        if "Альбом" in track_type or "Договорная" in str(track_type):
            safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
            safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
            
            confirmation_text = (
                "*✅ Шаг 5/5: Подтверждение записи на создание трека*\n\n"
                "*✨ Проверьте свои данные:*\n\n"
                f"👤 Имя: {safe_name}\n"
                f"📱 Контакт: {safe_contact}\n"
                f"🎧 Услуга: Создание трека\n"
                f"🎵 Тип работы: {context.user_data['track_type']}\n"
                f"💰 Стоимость: Договорная\n\n"
                "*📝 Администратор свяжется с вами для обсуждения деталей*\n\n"
                "*👇 Всё верно?*"
            )
            
            await update.message.reply_text(
                confirmation_text,
                reply_markup=KeyboardManager.get_confirmation(),
                parse_mode="Markdown"
            )
            return CONFIRM
    
    else:
        service_type = context.user_data.get('service_type', '')
        
        # ===== ФОРМИРУЕМ СООБЩЕНИЕ ДЛЯ ОБЫЧНОЙ ЗАПИСИ =====
        message = ""
        
        if service_type == "Запись вокала":
            message += f"*🎤 Шаг 6/7: Выбор времени*\n\n"
        elif service_type == "Запись инструментов":
            message += f"*🎸 Шаг 6/7: Выбор времени*\n\n"
        else:
            message += f"*🎵 Шаг 6/7: Выбор времени*\n\n"
        
        message += f"*✨ Во сколько для Вас забронировать студию?*\n\n"
        message += f"*Свободное время:*\n"
        
        for interval in free_intervals:
            display_text = FreeIntervalCalculator.format_interval_for_display(interval)
            message += f"{date_color} {display_text}\n"
        
        message += f"\n*Ночная надбавка при работе с инженером:*\n"
        message += f"• С 00:00 до 06:00 +200₽ в час\n\n"
        
        message += f"*✏️ Введите время в формате час-час:*"
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_time_input()
        )
        context.user_data['_conversation_state'] = SHOW_SLOTS
        return SHOW_SLOTS

@handle_errors_with_rate_limit
async def handle_confirmation_text(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    if not update.message:
        return CONFIRM
    
    text = update.message.text.strip()
    logger.info(f"🔍 handle_confirmation_text вызван с текстом: '{text}'")
    
    valid_buttons = ["✅ Всё верно, отправить", "✏️ Исправить данные", "❌ Отменить", "↩️ Назад"]
    
    if text not in valid_buttons:
        keyboard = KeyboardManager.get_confirmation()
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return CONFIRM
    
    if text == "✏️ Исправить данные":
        return await handle_edit_data(update, context)
    
    if text == "❌ Отменить":
        return await handle_cancel_booking(update, context)
    
    if text == "↩️ Назад":
        return await handle_back_to_previous_step(update, context)
    
    if text == "✅ Всё верно, отправить":
        return await confirm_booking(update, context)

@handle_errors_with_rate_limit
async def confirm_booking(update: Update, context):
    """Подтверждение и отправка записи (списываем купон при создании)"""
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    logger.info("🔍 confirm_booking вызван")
    
    try:
        user_id = update.effective_user.id
        is_mixing = context.user_data.get('is_mixing', False)
        is_12_hours = context.user_data.get('is_12_hours', False)
        is_track_creation = context.user_data.get('is_track_creation', False)
        selected_date = context.user_data.get('date', '')
        time_slot = context.user_data.get('time', '')
        service = context.user_data.get('service', '')
        track_type = context.user_data.get('track_type', '')
        
        duration = context.user_data.get('duration', 0)
        with_engineer = context.user_data.get('with_engineer', False)
        start_hour = context.user_data.get('start_hour')
        end_hour = context.user_data.get('end_hour')
        
        # ===== 1. СНАЧАЛА ПОЛУЧАЕМ КУПОН (БЕЗ СПИСАНИЯ) =====
        price_result_preview = PriceCalculator.calculate(
            service,
            duration,
            is_mixing=is_mixing,
            mixing_type=context.user_data.get('mixing_type'),
            is_12_hours=is_12_hours,
            is_track_creation=is_track_creation,
            track_type=track_type,
            twelve_hours_type=context.user_data.get('12_hours_type'),
            start_hour=start_hour,
            end_hour=end_hour,
            with_engineer=with_engineer,
            user_id=str(user_id),
            consume_coupon=False
        )
        
        level_coupon_id = price_result_preview.get('level_coupon_id')
        level_discount_percent = price_result_preview.get('level_discount_percent')
        promo_code_used = price_result_preview.get('promo_code_used')
        promo_discount_percent = price_result_preview.get('promo_discount_percent')
        
        logger.info(f"💰 КУПОН ДО СПИСАНИЯ: level_coupon_id={level_coupon_id}, level_discount_percent={level_discount_percent}")
        logger.info(f"💰 ПРОМОКОД ДО СПИСАНИЯ: promo_code_used={promo_code_used}, promo_discount_percent={promo_discount_percent}")
        
        # ===== 2. ТЕПЕРЬ РАССЧИТЫВАЕМ ЦЕНУ СО СПИСАНИЕМ =====
        price_result = PriceCalculator.calculate(
            service,
            duration,
            is_mixing=is_mixing,
            mixing_type=context.user_data.get('mixing_type'),
            is_12_hours=is_12_hours,
            is_track_creation=is_track_creation,
            track_type=track_type,
            twelve_hours_type=context.user_data.get('12_hours_type'),
            start_hour=start_hour,
            end_hour=end_hour,
            with_engineer=with_engineer,
            user_id=str(user_id),
            consume_coupon=True
        )
        
        # ===== 3. ДОБАВЛЯЕМ В user_data =====
        context.user_data['price_result'] = price_result
        context.user_data['level_coupon_id'] = level_coupon_id
        context.user_data['level_discount_percent'] = level_discount_percent
        context.user_data['promo_code_used'] = promo_code_used
        context.user_data['promo_discount_percent'] = promo_discount_percent
        context.user_data['price'] = price_result['final_price']
        context.user_data['free_service_applied'] = price_result.get('free_service_applied', False)
        
        logger.info(f"💰 price_result['final_price']: {price_result['final_price']}")
        logger.info(f"💰 УСТАНОВЛЕНА ЦЕНА В USER_DATA: {context.user_data['price']}")
        logger.info(f"💰 free_service_applied: {context.user_data['free_service_applied']}")
        
        # Проверяем доступность слота
        if selected_date and time_slot and 'Не указана' not in selected_date and 'Не указано' not in time_slot:
            clean_date = selected_date
            if '(' in clean_date:
                clean_date = clean_date.split('(')[0].strip()
            if clean_date.startswith(('🟢', '🟡', '🟠', '🔴', '⚪️')):
                clean_date = clean_date[2:].strip()
            
            service_type = "track_creation" if is_track_creation else "vocal"
            is_available = BookingManager.check_time_slot_available(clean_date, time_slot, service_type)
            
            if not is_available:
                await update.message.reply_text(
                    f"*❌ К сожалению, это время только что заняли!*",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
                    parse_mode="Markdown"
                )
                context.user_data.clear()
                return ConversationHandler.END
        
        logger.info(f"💰 ПЕРЕД СОХРАНЕНИЕМ В BOOKING: context.user_data.get('price') = {context.user_data.get('price')}")
        logger.info(f"💰 ПЕРЕД СОХРАНЕНИЕМ free_service_applied: {context.user_data.get('free_service_applied')}")
        
        # Сохраняем запись
        success, booking_id = BookingManager.save_to_sheets(
            context.user_data,
            user_id=user_id,
            return_row_index=True
        )
        
        if not success:
            await update.message.reply_text(
                f"❌ Не удалось создать запись!\n\n"
                f"💡 Пожалуйста, попробуйте снова",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
                parse_mode="Markdown"
            )
            context.user_data.clear()
            return ConversationHandler.END

        # ============================================================
        # ===== ВАЖНО: ПРОВЕРЯЕМ ДОСТИЖЕНИЯ СРАЗУ ПОСЛЕ СОХРАНЕНИЯ =====
        # ============================================================
        logger.info(f"🔍 ПРОВЕРКА ДОСТИЖЕНИЙ ДЛЯ ПОЛЬЗОВАТЕЛЯ {user_id}")
        awarded, total_vinyls = await AchievementSystem.check_and_award_achievements(str(user_id), context, update)
        logger.info(f"✅ Выдано достижений: {awarded}, всего пластинок: {total_vinyls}")
        
        # ===== СОХРАНЯЕМ ИНФОРМАЦИЮ О КУПОНЕ И ПРОМОКОДЕ =====
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            if level_coupon_id:
                cursor.execute('UPDATE bookings SET level_coupon_id = ? WHERE id = ?', (level_coupon_id, booking_id))
                logger.info(f"💰 Купон ID {level_coupon_id} сохранён для записи #{booking_id}")
            
            if level_discount_percent:
                cursor.execute('UPDATE bookings SET level_discount_percent = ? WHERE id = ?', (level_discount_percent, booking_id))
                logger.info(f"💰 level_discount_percent {level_discount_percent} сохранён для записи #{booking_id}")
            
            if promo_code_used:
                cursor.execute('UPDATE bookings SET promo_code_used = ? WHERE id = ?', (promo_code_used, booking_id))
                logger.info(f"💰 promo_code_used {promo_code_used} сохранён для записи #{booking_id}")
            
            if promo_discount_percent:
                cursor.execute('UPDATE bookings SET promo_discount_percent = ? WHERE id = ?', (promo_discount_percent, booking_id))
                logger.info(f"💰 promo_discount_percent {promo_discount_percent} сохранён для записи #{booking_id}")
            
            # Обновляем статус промокода
            if promo_code_used:
                cursor.execute('SELECT id, status FROM user_promo_usage WHERE user_id = ? AND promo_code = ?', (str(user_id), promo_code_used))
                existing = cursor.fetchone()
                
                if existing:
                    usage_id, current_status = existing
                    if current_status == 'used':
                        logger.warning(f"⚠️ Промокод {promo_code_used} уже использован, пропускаем")
                    else:
                        cursor.execute('UPDATE user_promo_usage SET status = "pending", booking_id = ? WHERE id = ?', (booking_id, usage_id))
                        logger.info(f"💰 Промокод {promo_code_used} заморожен (pending) для записи #{booking_id}")
                else:
                    cursor.execute('INSERT INTO user_promo_usage (user_id, promo_code, booking_id, status) VALUES (?, ?, ?, "pending")', (str(user_id), promo_code_used, booking_id))
                    logger.info(f"💰 Промокод {promo_code_used} создан со статусом pending для записи #{booking_id}")
            
            conn.commit()
        
        # ===== ОБНОВЛЯЕМ СТАТИСТИКУ ПОЛЬЗОВАТЕЛЯ =====
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            if is_12_hours:
                cursor.execute('UPDATE users SET rental_sessions = rental_sessions + 1 WHERE telegram_id = ?', (str(user_id),))
            elif is_mixing:
                cursor.execute('UPDATE users SET mixing_sessions = mixing_sessions + 1 WHERE telegram_id = ?', (str(user_id),))
            elif is_track_creation:
                cursor.execute('UPDATE users SET track_creation_sessions = track_creation_sessions + 1 WHERE telegram_id = ?', (str(user_id),))
            elif "вокал" in service.lower():
                cursor.execute('UPDATE users SET vocal_sessions = vocal_sessions + 1 WHERE telegram_id = ?', (str(user_id),))
            elif "инструмент" in service.lower():
                cursor.execute('UPDATE users SET instrument_sessions = instrument_sessions + 1 WHERE telegram_id = ?', (str(user_id),))
            
            with_engineer = context.user_data.get('with_engineer', False)
            if with_engineer:
                cursor.execute('UPDATE users SET with_engineer_sessions = with_engineer_sessions + 1 WHERE telegram_id = ?', (str(user_id),))
            else:
                cursor.execute('UPDATE users SET without_engineer_sessions = without_engineer_sessions + 1 WHERE telegram_id = ?', (str(user_id),))
            
            conn.commit()
        
        # ===== ОТПРАВКА СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЮ =====
        safe_name = SecurityUtils.safe_markdown_text(context.user_data.get('name', ''))
        safe_contact = SecurityUtils.safe_markdown_text(context.user_data.get('contact', ''))
        
        # ===== ОЧИЩАЕМ УСЛУГУ ОТ СМАЙЛИКОВ =====
        clean_service = clean_service_text(service)
        
        # ===== ОЧИЩАЕМ ДАТУ ОТ СМАЙЛИКОВ =====
        clean_date_display = selected_date
        if clean_date_display:
            for emoji in ['🟢', '🟡', '🟠', '🔴', '⚪️']:
                clean_date_display = clean_date_display.replace(emoji, '').strip()
            if '(' in clean_date_display:
                clean_date_display = clean_date_display.split('(')[0].strip()
        
        # ===== ОЧИЩАЕМ ТИП ОТ СМАЙЛИКОВ =====
        clean_type = ""
        if is_track_creation and context.user_data.get('track_type'):
            track_type_raw = context.user_data.get('track_type')
            clean_type = clean_service_text(track_type_raw)
        elif is_mixing and context.user_data.get('mixing_type'):
            mixing_type_raw = context.user_data.get('mixing_type')
            clean_type = clean_service_text(mixing_type_raw)
        elif is_12_hours and context.user_data.get('12_hours_type'):
            twelve_hours_type_raw = context.user_data.get('12_hours_type')
            clean_type = clean_service_text(twelve_hours_type_raw)
        
        # ===== ФОРМИРУЕМ ТЕКСТ СКИДОК ДЛЯ ПОЛЬЗОВАТЕЛЯ =====
        discount_lines = []
        
        if level_discount_percent and level_discount_percent > 0:
            discount_lines.append(f"• Скидка по уровню: {level_discount_percent}%")
        
        if promo_discount_percent and promo_discount_percent > 0:
            discount_lines.append(f"• Промокод: {promo_discount_percent}%")
            discount_lines.append(f"• Код промокода: {promo_code_used}")
                
        if price_result.get('free_hours_applied', 0) > 0:
            free_hours = price_result['free_hours_applied']
            if free_hours == 1:
                hours_text = "бесплатный час"
            elif free_hours in [2, 3, 4]:
                hours_text = f"{free_hours} бесплатных часа"
            else:
                hours_text = f"{free_hours} бесплатных часов"
            discount_lines.append(f"• Промокод: {hours_text}")
            discount_lines.append(f"• Код промокода: {promo_code_used}")
        
        if price_result.get('free_service_applied', False) and promo_code_used:
            discount_lines.append(f"• Промокод: Бесплатная услуга")
            discount_lines.append(f"• Код промокода: {promo_code_used}")
        
        if promo_code_used and not price_result.get('free_service_applied', False) and not price_result.get('free_hours_applied', 0) > 0 and not promo_discount_percent:
            discount_lines.append(f"• Код промокода: {promo_code_used}")
        
        discount_text = ""
        if discount_lines:
            discount_text = "\n" + "\n".join(discount_lines)
        
        # Форматируем время
        display_time = time_slot
        if display_time and '-' in display_time:
            display_time = DateTimeUtils.format_time_for_display(display_time)
        
        # ===== НОВЫЙ ФОРМАТ СООБЩЕНИЯ =====
        user_msg_lines = [
            f"*✅ Заявка успешно отправлена!*",
            "",
            f"*✨ Ожидайте подтверждения от администратора!*",
            "",
            f"*📋 Детали вашей записи:*",
            f"• Номер записи: #{booking_id}",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}"
        ]
        
        # Добавляем тип услуги (без смайликов)
        if clean_type:
            user_msg_lines.append(f"• Тип: {clean_type}")
        
        if clean_date_display and 'Не указана' not in clean_date_display:
            user_msg_lines.append(f"• Дата: {clean_date_display}")
        
        if display_time and display_time not in ['Не указано', 'Не указано (договорная)']:
            if is_12_hours:
                user_msg_lines.append(f"• Время: {display_time} (12 часов)")
            elif is_track_creation:
                user_msg_lines.append(f"• Время: {display_time} (4 часа)")
            elif duration and duration > 0:
                formatted_duration = PriceCalculator.format_hours_ru(duration)
                user_msg_lines.append(f"• Время: {display_time} ({formatted_duration})")
            else:
                user_msg_lines.append(f"• Время: {display_time}")
        
        # ===== ЦЕНА (для аренды — итоговая со скидкой + залог) =====
        if is_12_hours == 1:
            rent_price = 6500 if context.user_data.get('12_hours_type') and 'Ночь' in context.user_data.get('12_hours_type') else 7000
            final_price = price_result.get('final_price', rent_price)
            user_msg_lines.append(f"• Стоимость: {final_price}₽ + залог (по договору)")
        elif price_result['final_price'] == "Договорная" or price_result.get('is_contractual'):
            user_msg_lines.append(f"• Стоимость: Договорная")
        elif price_result.get('free_service_applied', False):
            user_msg_lines.append(f"• Стоимость: 0₽ (Бесплатная услуга)")
        elif price_result['final_price'] == 0:
            user_msg_lines.append(f"• Стоимость: 0₽")
        else:
            user_msg_lines.append(f"• Стоимость: {price_result['final_price']}₽")
        
        if discount_text:
            user_msg_lines.append(discount_text.lstrip('\n'))
        
        user_msg = "\n".join(user_msg_lines)
        
        await update.message.reply_text(
            user_msg,
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        
        # ===== ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ АДМИНУ =====
        admin_msg_lines = [
            f"*🚨 Новая заявка!*",
            "",
            f"*📋 Детали записи:*",
            f"• Номер записи: #{booking_id}",
            f"• Пользователь: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}"
        ]
        
        # Добавляем тип услуги для админа (без смайликов)
        if clean_type:
            admin_msg_lines.append(f"• Тип: {clean_type}")
        
        if clean_date_display and 'Не указана' not in clean_date_display:
            admin_msg_lines.append(f"• Дата: {clean_date_display}")
        
        if display_time and display_time not in ['Не указано', 'Не указано (договорная)']:
            if is_12_hours:
                admin_msg_lines.append(f"• Время: {display_time} (12 часов)")
            elif is_track_creation:
                admin_msg_lines.append(f"• Время: {display_time} (4 часа)")
            elif duration and duration > 0:
                formatted_duration = PriceCalculator.format_hours_ru(duration)
                admin_msg_lines.append(f"• Время: {display_time} ({formatted_duration})")
            else:
                admin_msg_lines.append(f"• Время: {display_time}")
        
        # ===== ЦЕНА ДЛЯ АДМИНА =====
        if is_12_hours == 1:
            rent_price = 6500 if context.user_data.get('12_hours_type') and 'Ночь' in context.user_data.get('12_hours_type') else 7000
            final_price = price_result.get('final_price', rent_price)
            admin_msg_lines.append(f"• Стоимость: {final_price}₽ + залог (по договору)")
        elif price_result['final_price'] == "Договорная" or price_result.get('is_contractual'):
            admin_msg_lines.append(f"• Стоимость: Договорная")
        elif price_result.get('free_service_applied', False):
            admin_msg_lines.append(f"• Стоимость: 0₽ (Бесплатная услуга)")
        elif price_result['final_price'] == 0:
            admin_msg_lines.append(f"• Стоимость: 0₽")
        else:
            admin_msg_lines.append(f"• Стоимость: {price_result['final_price']}₽")
        
        # Добавляем скидки для админа
        admin_discount_lines = []
        if level_discount_percent and level_discount_percent > 0:
            admin_discount_lines.append(f"• Скидка по уровню: {level_discount_percent}%")
        if promo_discount_percent and promo_discount_percent > 0:
            admin_discount_lines.append(f"• Промокод: {promo_discount_percent}%")
        if price_result.get('free_hours_applied', 0) > 0:
            free_hours = price_result['free_hours_applied']
            if free_hours == 1:
                hours_text = "бесплатный час"
            elif free_hours in [2, 3, 4]:
                hours_text = f"{free_hours} бесплатных часа"
            else:
                hours_text = f"{free_hours} бесплатных часов"
            admin_discount_lines.append(f"• Промокод: {hours_text}")
        if price_result.get('free_service_applied', False):
            admin_discount_lines.append(f"• Промокод: Бесплатная услуга")
        if promo_code_used:
            admin_discount_lines.append(f"• Код промокода: {promo_code_used}")
        
        if admin_discount_lines:
            admin_msg_lines.extend(admin_discount_lines)
        
        admin_msg_lines.append("")
        admin_msg_lines.append("*👇 Подтвердить или отклонить?*")
        
        admin_msg = "\n".join(admin_msg_lines)
        
        for admin_id in Config.ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{booking_id}"),
                     InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{booking_id}")]
                ])
                
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                logger.info(f"✅ Уведомление отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")
        
        # ===== ПРОВЕРЯЕМ РЕФЕРАЛЬНЫЙ БОНУС =====
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS booking_referral_bonuses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    referrer_id TEXT NOT NULL,
                    bonus_type TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            
            cursor.execute('SELECT referred_by FROM users WHERE telegram_id = ?', (str(user_id),))
            referred_data = cursor.fetchone()
            
            if referred_data and referred_data[0]:
                cursor.execute('''
                    SELECT COUNT(*) FROM booking_referral_bonuses 
                    WHERE user_id = ? AND referrer_id = (SELECT telegram_id FROM users WHERE referral_code = ?)
                ''', (str(user_id), referred_data[0]))
                already_awarded_bonus = cursor.fetchone()[0] > 0
                
                if not already_awarded_bonus:
                    cursor.execute('SELECT telegram_id FROM users WHERE referral_code = ?', (referred_data[0],))
                    referrer = cursor.fetchone()
                    
                    if referrer:
                        referrer_id = referrer[0]
                        
                        cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(referrer_id),))
                        referrer_vinyl_row = cursor.fetchone()
                        referrer_old_vinyls = referrer_vinyl_row[0] if referrer_vinyl_row else 0
                        
                        cursor.execute('UPDATE users SET vinyls = vinyls + 25 WHERE telegram_id = ?', (str(referrer_id),))
                        
                        cursor.execute('INSERT INTO booking_referral_bonuses (user_id, referrer_id, bonus_type) VALUES (?, ?, ?)', (str(user_id), str(referrer_id), 'first_booking'))
                        
                        conn.commit()
                        
                        cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(referrer_id),))
                        referrer_new_vinyl_row = cursor.fetchone()
                        referrer_new_vinyls = referrer_new_vinyl_row[0] if referrer_new_vinyl_row else 0
                        
                        logger.info(f"🎉 Рефереру {referrer_id} начислено +25 пластинок за реферала {user_id}")
                        
                        try:
                            await context.bot.send_message(
                                chat_id=int(referrer_id),
                                text=(
                                    f"*🎉 Добавлено 25 пластинок за реферала!*\n\n"
                                    f"*✨ Продолжайте приглашать друзей! 🔥*\n\n"
                                    f"*💰 Пластинок после начисления: {referrer_new_vinyls} 💿*"
                                ),
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logger.error(f"Не удалось отправить уведомление рефереру: {e}")
                        
                        await AchievementSystem.check_and_award_achievements(str(referrer_id), context, update)
                        await AchievementSystem.update_user_level(str(referrer_id), context)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в confirm_booking: {e}")
        import traceback
        traceback.print_exc()
        
        await update.message.reply_text(
            "*💡 Пожалуйста, попробуйте позже!*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
    
    context.user_data.clear()
    return ConversationHandler.END

def parse_booking_row(row):
    (booking_id, service, time_slot, date_str, status, price,
     is_mixing, mixing_type, is_track_creation, track_type,
     is_12_hours, twelve_hours_type, with_engineer, name, contact,
     duration) = row
    
    status_lower = status.lower() if status else ""
    if 'rejected' in status_lower or 'отклонен' in status_lower:
        status_emoji, status_text = "❌", "Отклонена"
    elif 'confirmed' in status_lower or 'подтвержден' in status_lower:
        status_emoji, status_text = "✅", "Подтверждена"
    elif 'cancelled' in status_lower or 'отменен' in status_lower:
        status_emoji, status_text = "❌", "Отменена"
    else:
        status_emoji, status_text = "⏳", "Ожидает подтверждения"
    
    is_contractual = (
        'Не указана' in str(date_str) or 
        'договорная' in str(date_str).lower() or
        time_slot in ['Не указано', 'Не указано (договорная)']
    )
    
    return {
        'id': booking_id,
        'status_emoji': status_emoji,
        'status_text': status_text,
        'name': name,
        'contact': contact,
        'service': service,
        'is_12_hours': is_12_hours,
        'twelve_hours_type': twelve_hours_type,
        'is_mixing': is_mixing,
        'mixing_type': mixing_type,
        'is_track_creation': is_track_creation,
        'track_type': track_type,
        'date_str': date_str,
        'time_slot': time_slot,
        'price': price,
        'duration': duration,
        'is_contractual': is_contractual
    }


def format_booking_display(booking):
    response = f"{booking['status_emoji']} Запись #{booking['id']}\n"
    response += f"• Имя: {booking['name']}\n"
    response += f"• Контакт: {booking['contact']}\n"
    response += f"• Услуга: {booking['service']}\n"
    
    if booking['is_12_hours'] and booking['twelve_hours_type']:
        response += f"• Тип: {booking['twelve_hours_type']}\n"
    
    if booking['date_str']:
        clean_date = booking['date_str'].split('(')[0].strip()
        response += f"• Дата: {clean_date}\n"
    
    if booking['time_slot'] and booking['time_slot'] not in ['Не указано', 'Не указано (договорная)']:
        display_time = DateTimeUtils.format_time_for_display(booking['time_slot'])
        response += f"• Время: {display_time}\n"
    
    if booking['price'] and str(booking['price']) != '0':
        if 'договорная' in str(booking['price']).lower():
            response += "• Стоимость: Договорная\n"
        else:
            try:
                price_int = int(float(booking['price']))
                formatted_price = f"{price_int:,}₽".replace(',', ' ')
                response += f"• Стоимость: {formatted_price}\n"
            except:
                response += f"• Стоимость: {booking['price']}₽\n"
    
    response += f"• Статус: {booking['status_text']}\n\n"
    
    return response

async def show_my_bookings_in_message(message_obj, context, user_id):
    """Показывает записи пользователя в сообщении (для редактирования)"""
    try:
        if hasattr(message_obj, 'message'):
            message_obj = message_obj.message
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT username, unique_id FROM users WHERE telegram_id = ?', (str(user_id),))
            user_info = cursor.fetchone()
            if user_info:
                current_user_display = get_user_display_name({
                    'username': user_info[0],
                    'unique_id': user_info[1],
                    'telegram_id': user_id
                })
            else:
                current_user_display = f"ID: ...{str(user_id)[-4:]}"
            
            # ===== SQL ЗАПРОС =====
            cursor.execute('''
                SELECT id, service, time_slot, date_str, status, price,
                    is_mixing, mixing_type, is_track_creation, track_type,
                    is_12_hours, twelve_hours_type, with_engineer, name, contact,
                    duration, timestamp, is_contractual, is_admin_booking,
                    level_discount_percent, promo_discount_percent, promo_code_used,
                    level_coupon_id
                FROM bookings 
                WHERE telegram_id = ? 
                AND status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен', 'completed')
                AND (
                    (is_contractual = 0 AND is_admin_booking = 0 AND is_mixing = 0)
                    OR
                    (is_mixing = 1 AND status = 'pending')
                    OR
                    (is_contractual = 1 AND is_admin_booking = 0 AND status = 'pending')
                )
                ORDER BY 
                    CASE 
                        WHEN status = 'pending' THEN 0 
                        ELSE 1 
                    END,
                    id ASC
            ''', (str(user_id),))
            
            rows = cursor.fetchall()
            
            if not rows:
                await message_obj.edit_text(
                    text=(
                        f"*📭 У Вас нет активных записей*"
                    ),
                    parse_mode="Markdown"
                )
                return
            
            dated_bookings = []
            contract_bookings = []
            
            for row in rows:
                (booking_id, service, time_slot, date_str, status, price,
                 is_mixing, mixing_type, is_track_creation, track_type,
                 is_12_hours, twelve_hours_type, with_engineer, name, contact,
                 duration, timestamp, is_contractual_db, is_admin_booking_db,
                 level_discount_percent, promo_discount_percent, promo_code_used,
                 level_coupon_id) = row
                
                is_contractual = is_contractual_db == 1
                is_admin_booking = is_admin_booking_db == 1
                
                status_lower = status.lower() if status else ""
                
                if 'pending' in status_lower or 'ожидает' in status_lower:
                    status_emoji = "⏳"
                    status_text = "Ожидает подтверждения"
                elif 'confirmed' in status_lower or 'подтвержден' in status_lower:
                    status_emoji = "✅"
                    status_text = "Подтверждена"
                else:
                    status_emoji = "⏳"
                    status_text = status
                
                safe_service = SecurityUtils.safe_markdown_text(service) if service else ""
                safe_name = SecurityUtils.safe_markdown_text(name) if name else ""
                safe_contact = SecurityUtils.safe_markdown_text(contact) if contact else ""
                
                if is_admin_booking:
                    safe_name = "Администратор"
                
                # ===== ИСПРАВЛЕННОЕ ФОРМИРОВАНИЕ ТЕКСТА КУПОНА / СКИДКИ ПО УРОВНЮ =====
                coupon_text = ""
                
                # Сначала проверяем level_discount_percent из записи
                if level_discount_percent and level_discount_percent > 0:
                    # Пытаемся найти купон в user_coupons для деталей
                    if level_coupon_id:
                        cursor.execute('''
                            SELECT level, discount_percent FROM user_coupons WHERE id = ?
                        ''', (level_coupon_id,))
                        coupon_info = cursor.fetchone()
                        if coupon_info:
                            level, discount = coupon_info
                            coupon_text = f"• Купон уровня {level}: {discount}%"
                        else:
                            # Купон удалён, но скидка была применена
                            coupon_text = f"• Скидка по уровню: {level_discount_percent}%"
                    else:
                        # Нет ID купона, но скидка была применена
                        coupon_text = f"• Скидка по уровню: {level_discount_percent}%"
                
                # ===== ФОРМИРУЕМ ТЕКСТ ПРОМОКОДА =====
                promo_text = ""
                if promo_code_used:
                    cursor.execute('''
                        SELECT discount_type, discount_value, target_service 
                        FROM promo_codes WHERE code = ?
                    ''', (promo_code_used,))
                    promo_info = cursor.fetchone()
                    
                    if promo_info:
                        discount_type, discount_value, target_service = promo_info
                        
                        if discount_type == 'percent_all':
                            promo_text = f"• Промокод: {discount_value}% на всё (код: {promo_code_used})"
                        elif discount_type == 'percent_service':
                            service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                            promo_text = f"• Промокод: {discount_value}% на {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                        elif discount_type == 'free_hours':
                            if discount_value == 1:
                                hours_text = "1 час"
                            elif discount_value in [2, 3, 4]:
                                hours_text = f"{discount_value} часа"
                            else:
                                hours_text = f"{discount_value} часов"
                            promo_text = f"• Промокод: {hours_text} бесплатно (код: {promo_code_used})"
                        elif discount_type == 'free_service':
                            service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                            promo_text = f"• Промокод: бесплатно: {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                
                booking_info = {
                    'id': booking_id,
                    'status_emoji': status_emoji,
                    'status_text': status_text,
                    'service': safe_service,
                    'is_12_hours': is_12_hours,
                    'twelve_hours_type': twelve_hours_type,
                    'is_mixing': is_mixing,
                    'mixing_type': mixing_type,
                    'is_track_creation': is_track_creation,
                    'track_type': track_type,
                    'date_str': date_str,
                    'time_slot': time_slot,
                    'price': price,
                    'duration': duration,
                    'is_contractual': is_contractual,
                    'is_admin_booking': is_admin_booking,
                    'timestamp': timestamp,
                    'name': safe_name,
                    'contact': safe_contact,
                    'coupon_text': coupon_text,
                    'promo_text': promo_text
                }
                
                # ===== РАЗДЕЛЯЕМ ЗАПИСИ =====
                if is_mixing == 1 or is_contractual:
                    contract_bookings.append(booking_info)
                else:
                    dated_bookings.append(booking_info)
            
            dated_bookings.sort(key=lambda x: x['id'])
            contract_bookings.sort(key=lambda x: x['id'])
            
            message = f"*📅 Мои записи*\n\n*👤 Профиль: {SecurityUtils.safe_markdown_text(current_user_display)}*\n\n"
            
            # ===== ОБЫЧНЫЕ ЗАПИСИ =====
            if dated_bookings:
                message += "*📋 Записи в студии:*\n\n"
                for booking in dated_bookings:
                    message += f"{booking['status_emoji']} *Запись #{booking['id']}*\n"
                    message += f"• Имя: {booking['name']}\n"
                    message += f"• Контакт: {booking['contact']}\n"
                    message += f"• Услуга: {booking['service']}\n"
                    
                    if booking['is_12_hours'] and booking['twelve_hours_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['twelve_hours_type']))
                        message += f"• Тип: {safe_type}\n"
                    elif booking['is_mixing'] and booking['mixing_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['mixing_type']))
                        message += f"• Тип: {safe_type}\n"
                    elif booking['is_track_creation'] and booking['track_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['track_type']))
                        message += f"• Тип: {safe_type}\n"
                    
                    if booking['date_str'] and 'Не указана' not in booking['date_str'] and booking['date_str'] != 'Запись в студии':
                        clean_date = booking['date_str'].split('(')[0].strip() if '(' in booking['date_str'] else booking['date_str']
                        message += f"• Дата: {clean_date}\n"
                    
                    if (booking['time_slot'] and 
                        booking['time_slot'] not in ['Не указано', 'Не указано (договорная)', 'Запись в студии']):
                        display_time = DateTimeUtils.format_time_for_display(booking['time_slot'])
                        safe_display_time = SecurityUtils.safe_markdown_text(display_time)
                        if booking['is_12_hours']:
                            message += f"• Время: {safe_display_time} (12 часов)\n"
                        elif booking['duration'] and booking['duration'] > 0:
                            formatted_duration = PriceCalculator.format_hours_ru(booking['duration'])
                            message += f"• Время: {safe_display_time} ({formatted_duration})\n"
                        else:
                            message += f"• Время: {safe_display_time}\n"
                    
                    if booking['is_12_hours']:
                        rent_price = 7000 if booking.get('twelve_hours_type', '').startswith('День') else 6500
                        message += f"• Стоимость аренды: {rent_price}₽ + залог (по договору)\n"
                    elif booking['price'] and str(booking['price']) != '0':
                        if 'договорная' in str(booking['price']).lower():
                            message += "• Стоимость: Договорная\n"
                        else:
                            try:
                                price_int = int(float(booking['price']))
                                formatted_price = f"{price_int}₽"
                                message += f"• Стоимость: {formatted_price}\n"
                            except:
                                safe_price = SecurityUtils.safe_markdown_text(str(booking['price']))
                                message += f"• Стоимость: {safe_price}\n"
                    
                    # ===== ДОБАВЛЯЕМ КУПОН / СКИДКУ ПО УРОВНЮ =====
                    if booking.get('coupon_text'):
                        message += f"{booking['coupon_text']}\n"
                    
                    # ===== ДОБАВЛЯЕМ ПРОМОКОД =====
                    if booking.get('promo_text'):
                        message += f"{booking['promo_text']}\n"
                    
                    message += f"• Статус: {booking['status_text']}\n\n"
            
            # ===== ДОГОВОРНЫЕ ЗАПИСИ (ТОЛЬКО PENDING) =====
            if contract_bookings:
                message += "*📝 Ожидающие договорные записи:*\n\n"
                for booking in contract_bookings:
                    message += f"{booking['status_emoji']} *Запись #{booking['id']}*\n"
                    message += f"• Имя: {booking['name']}\n"
                    message += f"• Контакт: {booking['contact']}\n"
                    message += f"• Услуга: {booking['service']}\n"
                    
                    if booking['is_mixing'] and booking['mixing_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['mixing_type']))
                        message += f"• Тип: {safe_type}\n"
                    elif booking['is_track_creation'] and booking['track_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['track_type']))
                        message += f"• Тип: {safe_type}\n"
                    
                    if booking['price'] and str(booking['price']) != '0':
                        if 'договорная' in str(booking['price']).lower():
                            message += "• Стоимость: Договорная\n"
                        else:
                            try:
                                price_int = int(float(booking['price']))
                                formatted_price = f"{price_int}₽"
                                message += f"• Стоимость: {formatted_price}\n"
                            except:
                                safe_price = SecurityUtils.safe_markdown_text(str(booking['price']))
                                message += f"• Стоимость: {safe_price}\n"
                    
                    # ===== ДОБАВЛЯЕМ КУПОН / СКИДКУ ПО УРОВНЮ =====
                    if booking.get('coupon_text'):
                        message += f"{booking['coupon_text']}\n"
                    
                    # ===== ДОБАВЛЯЕМ ПРОМОКОД =====
                    if booking.get('promo_text'):
                        message += f"{booking['promo_text']}\n"
                    
                    message += f"• Статус: {booking['status_text']}\n\n"
            
            message += "*👇 Отменить записи в студии:*"
            
            # ===== КНОПКИ ТОЛЬКО ДЛЯ dated_bookings =====
            keyboard_buttons = []
            for booking in dated_bookings:
                if booking['status_text'] != "Завершена":
                    button_text = f"❌ Отменить #{booking['id']}"
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text=button_text,
                            callback_data=f"cancel_{booking['id']}"
                        )
                    ])
            
            if keyboard_buttons:
                keyboard_buttons.sort(key=lambda x: int(x[0].callback_data.split('_')[1]))
            
            reply_markup = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
            
            await message_obj.edit_text(
                text=message,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"Ошибка в show_my_bookings_in_message: {e}")
        try:
            await message_obj.edit_text(
                text="*❌ Ошибка при загрузке записей*",
                parse_mode="Markdown"
            )
        except:
            pass

@handle_errors_with_rate_limit
async def handle_admin_cancel_start(update: Update, context):
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    context.user_data['is_admin_cancel'] = True
    context.user_data['_conversation_state'] = ADMIN_CANCEL_USER_ID
    context.user_data['nav_sent'] = False
    
    await update.message.reply_text(
        "*👑 Шаг 1/2: Ввод имени пользователя*\n\n"
        "*📋 Варианты ввода:*\n"
        "• Уникальный ID (MC...): `MC1772377294899374`\n"
        "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
        "*💡 Где найти Уникальный ID:*\n"
        "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
        "*✏️ Введите данные:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_CANCEL_USER_ID

@handle_errors_with_rate_limit
async def handle_admin_cancel_user_id(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_cancel_user_id: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    search_term = text.replace('@', '').strip().lower()
    found_user = None
    search_method = ""

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # ===== 1. Поиск по уникальному ID (MC...) =====
            if search_term.startswith("mc"):
                logger.info(f"🔍 Ищем по уникальному ID: {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE LOWER(unique_id) = ?
                ''', (search_term,))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "уникальному ID"

            # ===== 2. Поиск по username (точное) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (точное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE LOWER(username) = ? OR LOWER(username) = ?
                ''', (search_term, f'@{search_term}'))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "username (точное)"

            # ===== 3. Поиск по username (частичное) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (частичное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE 
                    LOWER(username) LIKE ? OR 
                    LOWER(username) LIKE ? OR
                    LOWER(first_name) LIKE ? OR
                    LOWER(unique_id) LIKE ?
                ''', (f'%{search_term}%', f'%@{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "частичному совпадению"

            if not found_user:
                await update.message.reply_text(
                    f"*❌ Пользователь не найден!*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню"]
                    ], resize_keyboard=True)
                )
                return ADMIN_CANCEL_USER_ID

            telegram_id, username, first_name, unique_id = found_user
            
            user_display = get_user_display_name({
                'username': username,
                'unique_id': unique_id,
                'telegram_id': telegram_id
            })
            
            context.user_data['target_user_id'] = telegram_id
            context.user_data['target_unique_id'] = unique_id
            context.user_data['target_username'] = username or first_name or "Неизвестный"
            context.user_data['target_display'] = user_display

            logger.info(f"✅ Админ нашел пользователя по {search_method}: {unique_id} (отображается как: {user_display}")

            # Проверяем, есть ли записи у пользователя
            cursor.execute('''
                SELECT COUNT(*) FROM bookings 
                WHERE telegram_id = ? 
                AND status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
            ''', (str(telegram_id),))
            
            bookings_count = cursor.fetchone()[0] or 0
            
            if bookings_count == 0:
                await update.message.reply_text(
                    f"*📋 Записи пользователя*\n\n"
                    f"*👤 @{username or 'Неизвестный'} {unique_id}*\n\n"
                    f"*📭 У пользователя нет записей*",
                    parse_mode="Markdown"
                )
                
                await update.message.reply_text(
                    "*🏠 Возвращаемся в главное меню*\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
                    parse_mode="Markdown"
                )
                
                context.user_data.clear()
                return ConversationHandler.END
            
            await admin_show_user_bookings(
                update,
                context,
                target_user_id=telegram_id,
                target_unique_id=unique_id,
                target_username=username or first_name
            )
            return ADMIN_CANCEL_SHOW_BOOKINGS

    except Exception as e:
        logger.error(f"❌ Ошибка поиска пользователя: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "❌ Ошибка при поиске пользователя!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_CANCEL_USER_ID

@handle_errors_with_rate_limit
async def profile_handler(update: Update, context):
    """Показывает профиль пользователя - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or "Не указан"
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT telegram_id FROM users WHERE telegram_id = ?', (user_id,))
            exists = cursor.fetchone()
            
            if not exists:
                unique_id = f"MC{int(time.time())}{user_id[-6:]}"
                registration_date = DateTimeUtils.now().strftime('%d.%m.%Y')
                referral_code = AchievementSystem.generate_referral_code(user_id)
                
                cursor.execute('''
                    INSERT INTO users 
                    (telegram_id, username, unique_id, registration_date, referral_code, vinyls)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, username, unique_id, registration_date, referral_code, 0))
                
                conn.commit()
            
            cursor.execute('''
                SELECT unique_id, registration_date, total_spent, vinyls, level,
                       permanent_discount, temporary_discount, discount_expiry,
                       referral_code, referred_by
                FROM users 
                WHERE telegram_id = ?
            ''', (user_id,))
            
            user_record = cursor.fetchone()
            
            if not user_record:
                user_unique_id = f"MC{int(time.time())}{user_id[-6:]}"
                user_registration_date = DateTimeUtils.now().strftime('%d.%m.%Y')
                total_spent = 0
                vinyls = 0
                level = 1
                permanent_discount = 0
                temporary_discount = 0
                discount_expiry = None
                referral_code = "Не указан"
                referred_by = None
            else:
                user_unique_id = user_record[0] or f"MC{int(time.time())}{user_id[-6:]}"
                user_registration_date = user_record[1] or DateTimeUtils.now().strftime('%d.%m.%Y')
                total_spent = user_record[2] or 0
                vinyls = user_record[3] or 0
                level = user_record[4] or 1
                permanent_discount = user_record[5] or 0
                temporary_discount = user_record[6] or 0
                discount_expiry = user_record[7]
                referral_code = user_record[8] or "Не указан"
                referred_by = user_record[9]
            
            level_info = AchievementSystem.get_level_info(vinyls)
            current_level_name = level_info['current_level_name']
            
            # ===== ПОЛУЧАЕМ РЕАЛЬНУЮ ДОСТУПНУЮ СКИДКУ ИЗ КУПОНОВ =====
            coupons_summary = AchievementSystem.get_user_coupons_summary(user_id)
            available_discount = coupons_summary['total_discount'] if coupons_summary['total_discount'] > 0 else 0
            
            # Получаем все записи
            cursor.execute('''
                SELECT 
                    is_contractual,
                    service,
                    date_str,
                    price,
                    status,
                    is_12_hours,
                    twelve_hours_type,
                    is_mixing,
                    mixing_type,
                    is_track_creation,
                    track_type,
                    is_admin_booking
                FROM bookings 
                WHERE telegram_id = ? 
            ''', (user_id,))
            
            all_bookings = cursor.fetchall()
            
            # ===== СЧЁТЧИКИ =====
            studio_count = 0          # Записи в студии (completed + админские confirmed)
            contract_count = 0        # Договорные услуги (confirmed)
            total_spent_calc = 0      # Общая стоимость
            confirmed_count = 0       # Подтверждено (confirmed + completed)
            cancelled_count = 0       # Отменено пользователем (cancelled_by_user)
            
            for booking in all_bookings:
                (is_contractual, service, date_str, price, status, is_12_hours, 
                 twelve_hours_type, is_mixing, mixing_type, is_track_creation, track_type,
                 is_admin_booking) = booking
                
                status_lower = status.lower() if status else ""
                is_admin = is_admin_booking == 1
                is_contract = (
                    is_contractual == 1 or
                    'Не указана' in str(date_str) or 
                    'договорная' in str(date_str).lower()
                )
                
                # ===== ПОДСЧЁТ СТАТИСТИКИ =====
                if status_lower in ['confirmed', 'подтвержден']:
                    confirmed_count += 1
                elif status_lower == 'completed':
                    confirmed_count += 1
                elif status_lower == 'cancelled_by_user':
                    cancelled_count += 1
                
                # ===== ИСТОРИЯ ЗАПИСЕЙ И СТОИМОСТЬ =====
                # 1. Обычные записи: ТОЛЬКО completed
                if status_lower == 'completed' and not is_admin:
                    studio_count += 1
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
                            
                # 2. Админские записи: confirmed
                elif is_admin and status_lower in ['confirmed', 'подтвержден']:
                    if is_contract:
                        contract_count += 1
                    else:
                        studio_count += 1
                    
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
                            
                # 3. Договорные записи (не админские): confirmed
                elif is_contract and status_lower in ['confirmed', 'подтвержден'] and not is_admin:
                    contract_count += 1
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
                            
                # 4. Сведение/мастеринг: confirmed
                elif is_mixing == 1 and status_lower in ['confirmed', 'подтвержден']:
                    contract_count += 1
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
                            
                # 5. Создание альбома: confirmed
                elif is_track_creation == 1 and track_type and 'Альбом' in track_type and status_lower in ['confirmed', 'подтвержден']:
                    contract_count += 1
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
            
            # Обновляем total_spent если нужно
            if total_spent_calc != total_spent:
                cursor.execute('UPDATE users SET total_spent = ? WHERE telegram_id = ?', 
                             (total_spent_calc, user_id))
                conn.commit()
                total_spent = total_spent_calc
            
            # ===== ЛИМИТЫ =====
            # Записей с датой: X/2
            cursor.execute('''
                SELECT COUNT(*) 
                FROM bookings 
                WHERE telegram_id = ? 
                AND status IN ('pending', 'confirmed', 'подтвержден')
                AND is_contractual = 0
                AND is_admin_booking = 0
                AND is_mixing = 0
                AND is_track_creation = 0
                AND date_str NOT LIKE '%Не указана%'
                AND date_str NOT LIKE '%договорная%'
                AND date_str != 'Запись в студии'
            ''', (user_id,))
            active_dated_count = cursor.fetchone()[0] or 0
            
            # Договорных записей: X/3 (ТОЛЬКО PENDING!)
            cursor.execute('''
                SELECT COUNT(*) 
                FROM bookings 
                WHERE telegram_id = ? 
                AND status = 'pending'
                AND (
                    is_contractual = 1
                    OR is_admin_booking = 1
                    OR is_mixing = 1
                    OR is_track_creation = 1
                    OR date_str LIKE '%Не указана%'
                    OR date_str LIKE '%договорная%'
                    OR date_str = 'Запись в студии'
                )
            ''', (user_id,))
            active_contract_count = cursor.fetchone()[0] or 0
            
            # ===== ПРОЦЕНТЫ =====
            total_processed = confirmed_count + cancelled_count
            approved_percentage = 0
            cancelled_percentage = 0
            
            if total_processed > 0:
                approved_percentage = int((confirmed_count / total_processed) * 100)
                cancelled_percentage = 100 - approved_percentage
        
        # ===== ФОРМИРУЕМ ТЕКСТ ПРОФИЛЯ =====
        profile_text = (
            f"*👤 Ваш профиль:*\n"
            f"• Username: @{username}\n"
            f"• Telegram ID: `{user_id}`\n"
            f"• Уникальный ID: `{user_unique_id}`\n"
            f"• Дата регистрации: {user_registration_date}\n\n"
            
            f"*💿 Реферальная программа:*\n"
            f"• Уровень: {current_level_name}\n"
            f"• Пластинок: {vinyls}\n"
            f"• Доступная скидка: {available_discount}%\n\n"
            
            f"*📊 История записей:*\n"
            f"• Записи в студии: {studio_count}\n"
            f"• Договорные услуги: {contract_count}\n"
            f"• Стоимость ваших записей: {format_number(total_spent)} ₽\n\n"
            
            f"*📈 Статистика обработки записей:*\n"
            f"• Подтверждено: {format_number(confirmed_count)}\n"
            f"• Отменено вами: {format_number(cancelled_count)}\n"
            f"• Соотношение: {approved_percentage}% / {cancelled_percentage}%\n\n"
            
            f"*🎯 Текущие лимиты:*\n"
            f"• Записей с датой: {active_dated_count}/2\n"
            f"• Договорных записей: {active_contract_count}/3"
        )
        
        await update.message.reply_text(
            profile_text,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения профиля: {e}")
        import traceback
        traceback.print_exc()
        
        fallback_text = (
            f"*👤 Ваш профиль*\n\n"
            f"• Telegram ID: `{user_id}`\n"
            f"• Username: @{username}\n\n"
            f"📞 По вопросам: @mothman32"
        )
        
        await update.message.reply_text(
            fallback_text,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

async def admin_show_user_bookings(update: Update, context, target_user_id: int, target_unique_id: str = None, target_username: str = None, edit_mode: bool = False):
    """Показать записи пользователя для админа с информацией о промокодах и купонах"""
    try:
        logger.info(f"🔍 admin_show_user_bookings для пользователя: {target_user_id}, edit_mode: {edit_mode}")
        
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            await query.answer()
            message_obj = query.message
            chat_id = message_obj.chat_id
            is_callback = True
        else:
            message_obj = update.message
            chat_id = message_obj.chat_id
            is_callback = False
            query = None
        
        safe_target_username = SecurityUtils.safe_markdown_text(target_username) if target_username else 'Неизвестный'
        safe_target_unique_id = SecurityUtils.safe_markdown_text(target_unique_id) if target_unique_id else ''
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT b.id, b.service, b.time_slot, b.date_str, b.status, b.price,
                       b.is_mixing, b.mixing_type, b.is_track_creation, b.track_type,
                       b.is_12_hours, b.twelve_hours_type, b.with_engineer, b.name, b.contact,
                       b.duration, b.timestamp, b.is_contractual, b.is_admin_booking,
                       b.level_discount_percent, b.promo_discount_percent, b.promo_code_used,
                       b.level_coupon_id
                FROM bookings b
                WHERE b.telegram_id = ? 
                AND b.status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
                ORDER BY b.id ASC
            ''', (str(target_user_id),))
            
            rows = cursor.fetchall()
            
            if not rows:
                message_text = (
                    f"*📋 Записи пользователя*\n\n"
                    f"*👤 @{safe_target_username} {safe_target_unique_id}*\n\n"
                    f"*📭 У пользователя нет записей*"
                )
                
                if is_callback:
                    try:
                        await message_obj.edit_reply_markup(reply_markup=None)
                    except:
                        pass
                    
                    await message_obj.edit_text(
                        text=message_text,
                        parse_mode="Markdown"
                    )
                else:
                    await message_obj.reply_text(
                        text=message_text,
                        parse_mode="Markdown"
                    )
                
                menu_message = (
                    "*🏠 Возвращаемся в главное меню*\n\n"
                    "*👇 Выберите подходящий вариант:*"
                )
                
                if is_callback:
                    try:
                        await message_obj.edit_text(
                            text=menu_message,
                            parse_mode="Markdown",
                            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка редактирования: {e}")
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=menu_message,
                            parse_mode="Markdown",
                            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                        )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=menu_message,
                        parse_mode="Markdown",
                        reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                    )
                
                context.user_data.clear()
                return
            
            # Получаем ID первой платной записи (не договорной и не альбом)
            cursor.execute('''
                SELECT MIN(id) FROM bookings 
                WHERE telegram_id = ? 
                AND status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
                AND price != 'Договорная'
                AND price NOT LIKE '%договорная%'
                AND (mixing_type IS NULL OR mixing_type NOT LIKE '%Альбом%')
                AND (track_type IS NULL OR track_type NOT LIKE '%Альбом%')
            ''', (str(target_user_id),))
            first_paid_booking_row = cursor.fetchone()
            first_paid_booking_id = first_paid_booking_row[0] if first_paid_booking_row else None
            
            dated_bookings = []
            contract_bookings = []
            admin_bookings = []
            
            for row in rows:
                (booking_id, service, time_slot, date_str, status, price,
                 is_mixing, mixing_type, is_track_creation, track_type,
                 is_12_hours, twelve_hours_type, with_engineer, name, contact,
                 duration, timestamp, is_contractual_db, is_admin_booking_db,
                 level_discount_percent, promo_discount_percent, promo_code_used,
                 level_coupon_id) = row
                
                is_contractual = is_contractual_db == 1
                is_admin_booking = is_admin_booking_db == 1
                
                status_lower = status.lower() if status else ""
                
                if 'pending' in status_lower or 'ожидает' in status_lower:
                    status_emoji = "⏳"
                    status_text = "Ожидает подтверждения"
                elif 'confirmed' in status_lower or 'подтвержден' in status_lower:
                    status_emoji = "✅"
                    status_text = "Подтверждена"
                elif 'completed' in status_lower or 'завершен' in status_lower:
                    status_emoji = "✅"
                    status_text = "Завершена"
                else:
                    status_emoji = "⏳"
                    status_text = status
                
                safe_name = SecurityUtils.safe_markdown_text(name) if name else ""
                safe_contact = SecurityUtils.safe_markdown_text(contact) if contact else ""
                safe_service = SecurityUtils.safe_markdown_text(service) if service else ""
                
                if is_admin_booking:
                    safe_name = "Администратор"
                
                # ===== НОВАЯ ЛОГИКА ДЛЯ КУПОНА =====
                coupon_text = ""
                
                # Проверяем — это первая платная запись?
                is_first_paid_booking = (booking_id == first_paid_booking_id)
                
                if is_first_paid_booking:
                    coupon_text = "• Купон уровня 1: 50%"
                    logger.info(f"✅ Первая платная запись пользователя #{booking_id} — купон 50%")
                elif level_coupon_id:
                    cursor.execute('''
                        SELECT level, discount_percent FROM user_coupons WHERE id = ?
                    ''', (level_coupon_id,))
                    coupon_info = cursor.fetchone()
                    if coupon_info:
                        level, discount = coupon_info
                        if not promo_code_used:
                            coupon_text = f"• Купон уровня {level}: {discount}%"
                        logger.info(f"✅ Найден купон для записи #{booking_id}: уровень {level}, скидка {discount}%")
                elif level_discount_percent and level_discount_percent > 0 and not promo_code_used:
                    coupon_text = "• Купон уровня 1: 50%"
                    logger.info(f"ℹ️ Старая запись #{booking_id} со скидкой 50%")
                elif price and not promo_code_used:
                    try:
                        price_str = str(price).replace('₽', '').replace(' ', '').strip()
                        if price_str and price_str != '0' and 'договорная' not in price_str.lower():
                            current_price = int(float(price_str))
                            base_price = None
                            
                            if is_mixing == 1:
                                if mixing_type and "Альбом" in mixing_type:
                                    base_price = None
                                else:
                                    base_price = 2500
                            elif is_track_creation == 1:
                                if track_type and "Альбом" in track_type:
                                    base_price = None
                                else:
                                    base_price = 9000
                            elif is_12_hours == 1:
                                if twelve_hours_type and ("Ночь" in twelve_hours_type or "ночь" in twelve_hours_type.lower()):
                                    base_price = 6500
                                else:
                                    base_price = 7000
                            elif "вокал" in str(service).lower() or "инструмент" in str(service).lower():
                                if with_engineer == 1:
                                    if duration >= 6:
                                        base_price = duration * 1200
                                    elif duration >= 3:
                                        base_price = duration * 1300
                                    else:
                                        base_price = duration * 1500
                                else:
                                    if duration >= 6:
                                        base_price = duration * 1000
                                    elif duration >= 3:
                                        base_price = duration * 1200
                                    else:
                                        base_price = duration * 1400
                            
                            if base_price and current_price < base_price:
                                discount_percent = int((base_price - current_price) / base_price * 100)
                                if discount_percent > 0:
                                    coupon_text = "• Купон уровня 1: 50%"
                                    logger.info(f"💡 Первая платная запись #{booking_id}: скидка 50% (база={base_price}, цена={current_price})")
                    except Exception as e:
                        logger.error(f"Ошибка вычисления скидки для #{booking_id}: {e}")
                
                # ===== ФОРМИРУЕМ ТЕКСТ ПРОМОКОДА =====
                promo_text = ""
                if promo_code_used:
                    cursor.execute('''
                        SELECT discount_type, discount_value, target_service 
                        FROM promo_codes WHERE code = ?
                    ''', (promo_code_used,))
                    promo_info = cursor.fetchone()
                    
                    if promo_info:
                        discount_type, discount_value, target_service = promo_info
                        
                        if discount_type == 'percent_all':
                            promo_text = f"• Промокод: {discount_value}% на всё (код: {promo_code_used})"
                        elif discount_type == 'percent_service':
                            service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                            promo_text = f"• Промокод: {discount_value}% на {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                        elif discount_type == 'free_hours':
                            if discount_value == 1:
                                hours_text = "1 час"
                            elif discount_value in [2, 3, 4]:
                                hours_text = f"{discount_value} часа"
                            else:
                                hours_text = f"{discount_value} часов"
                            promo_text = f"• Промокод: {hours_text} бесплатно (код: {promo_code_used})"
                        elif discount_type == 'free_service':
                            service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                            promo_text = f"• Промокод: бесплатно: {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                
                booking_info = {
                    'id': booking_id,
                    'status_emoji': status_emoji,
                    'status_text': status_text,
                    'name': safe_name,
                    'contact': safe_contact,
                    'service': safe_service,
                    'is_12_hours': is_12_hours,
                    'twelve_hours_type': twelve_hours_type,
                    'is_mixing': is_mixing,
                    'mixing_type': mixing_type,
                    'is_track_creation': is_track_creation,
                    'track_type': track_type,
                    'date_str': date_str,
                    'time_slot': time_slot,
                    'price': price,
                    'duration': duration,
                    'is_contractual': is_contractual,
                    'is_admin_booking': is_admin_booking,
                    'coupon_text': coupon_text,
                    'promo_text': promo_text
                }
                
                if is_admin_booking:
                    admin_bookings.append(booking_info)
                elif is_contractual:
                    contract_bookings.append(booking_info)
                else:
                    dated_bookings.append(booking_info)
            
            dated_bookings.sort(key=lambda x: x['id'])
            contract_bookings.sort(key=lambda x: x['id'])
            admin_bookings.sort(key=lambda x: x['id'])
            
            all_bookings = dated_bookings + contract_bookings + admin_bookings
            context.user_data['user_bookings_list'] = []
            for booking in all_bookings:
                context.user_data['user_bookings_list'].append({
                    'id': booking['id'],
                    'service': booking['service'],
                    'name': booking['name']
                })
            
            keyboard_buttons = []
            for booking in all_bookings:
                button_text = f"❌ Отменить #{booking['id']}"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"admin_cancel_{booking['id']}"
                    )
                ])
            
            if keyboard_buttons:
                keyboard_buttons.sort(key=lambda x: int(x[0].callback_data.split('_')[2]))
            
            inline_keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
            
            header = (
                "*📋 Записи пользователя*\n\n"
                f"*👤 @{safe_target_username} {safe_target_unique_id}*\n\n"
            )
            
            message_parts = []
            current_part = header
            
            # ===== ОБЫЧНЫЕ ЗАПИСИ =====
            if dated_bookings:
                if len(current_part + "*📅 Записи в студии:*\n\n") > 3500:
                    message_parts.append(current_part)
                    current_part = "*📅 Записи в студии:*\n\n"
                else:
                    current_part += "*📅 Записи в студии:*\n\n"
                
                for booking in dated_bookings:
                    booking_text = f"{booking['status_emoji']} *Запись #{booking['id']}*\n"
                    booking_text += f"• Имя: {booking['name']}\n"
                    booking_text += f"• Контакт: {booking['contact']}\n"
                    booking_text += f"• Услуга: {booking['service']}\n"
                    
                    if booking['is_12_hours'] and booking['twelve_hours_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['twelve_hours_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    elif booking['is_mixing'] and booking['mixing_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['mixing_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    elif booking['is_track_creation'] and booking['track_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['track_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    
                    if booking['date_str'] and 'Не указана' not in booking['date_str'] and booking['date_str'] != 'Запись в студии':
                        clean_date = booking['date_str'].split('(')[0].strip() if '(' in booking['date_str'] else booking['date_str']
                        safe_clean_date = SecurityUtils.safe_markdown_text(clean_date)
                        if '(' in booking['date_str']:
                            day_part = booking['date_str'].split('(')[1].replace(')', '').strip()
                            safe_day_part = SecurityUtils.safe_markdown_text(day_part)
                            booking_text += f"• Дата: {safe_clean_date} ({safe_day_part})\n"
                        else:
                            booking_text += f"• Дата: {safe_clean_date}\n"
                    
                    # ===== ИСПРАВЛЕНО: format_time_for_display() нормализует 24→00 =====
                    if (booking['time_slot'] and 
                        booking['time_slot'] not in ['Не указано', 'Не указано (договорная)', 'Запись в студии']):
                        display_time = DateTimeUtils.format_time_for_display(booking['time_slot'])
                        safe_display_time = SecurityUtils.safe_markdown_text(display_time)
                        if booking['is_12_hours']:
                            booking_text += f"• Время: {safe_display_time} (12 часов)\n"
                        elif booking['duration'] and booking['duration'] > 0:
                            formatted_duration = PriceCalculator.format_hours_ru(booking['duration'])
                            booking_text += f"• Время: {safe_display_time} ({formatted_duration})\n"
                        else:
                            booking_text += f"• Время: {safe_display_time}\n"
                    
                    # ===== ЦЕНА ИЗ БД =====
                    if booking['is_12_hours']:
                        price_from_db = booking.get('price', 0)
                        if price_from_db and price_from_db != '0':
                            try:
                                price_int = int(float(price_from_db))
                                booking_text += f"• Стоимость аренды: {price_int}₽ + залог (по договору)\n"
                            except:
                                booking_text += f"• Стоимость: {price_from_db}₽\n"
                        else:
                            rent_price = 7000 if booking.get('twelve_hours_type', '').startswith('День') else 6500
                            booking_text += f"• Стоимость аренды: {rent_price}₽ + залог (по договору)\n"
                    else:
                        if booking['price'] is not None:
                            price_str = str(booking['price'])
                            if price_str == '':
                                booking_text += "• Стоимость: 0₽\n"
                            elif 'договорная' in price_str.lower():
                                booking_text += "• Стоимость: Договорная\n"
                            else:
                                try:
                                    price_int = int(float(price_str))
                                    formatted_price = f"{price_int:,}₽".replace(',', ' ')
                                    booking_text += f"• Стоимость: {formatted_price}\n"
                                except:
                                    safe_price = SecurityUtils.safe_markdown_text(price_str)
                                    booking_text += f"• Стоимость: {safe_price}\n"
                        else:
                            booking_text += "• Стоимость: 0₽\n"
                    
                    # ===== ДОБАВЛЯЕМ КУПОН =====
                    if booking.get('coupon_text'):
                        booking_text += f"{booking['coupon_text']}\n"
                    
                    # ===== ДОБАВЛЯЕМ ПРОМОКОД =====
                    if booking.get('promo_text'):
                        booking_text += f"{booking['promo_text']}\n"
                    
                    booking_text += f"• Статус: {booking['status_text']}\n\n"
                    
                    if len(current_part + booking_text) > 3500:
                        message_parts.append(current_part)
                        current_part = booking_text
                    else:
                        current_part += booking_text
            
            # ===== ДОГОВОРНЫЕ ЗАПИСИ =====
            if contract_bookings:
                if len(current_part + "*📝 Договорные записи:*\n\n") > 3500:
                    message_parts.append(current_part)
                    current_part = "*📝 Договорные записи:*\n\n"
                else:
                    current_part += "*📝 Договорные записи:*\n\n"
                
                for booking in contract_bookings:
                    booking_text = f"{booking['status_emoji']} *Запись #{booking['id']}*\n"
                    booking_text += f"• Имя: {booking['name']}\n"
                    booking_text += f"• Контакт: {booking['contact']}\n"
                    booking_text += f"• Услуга: {booking['service']}\n"
                    
                    if booking['is_mixing'] and booking['mixing_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['mixing_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    elif booking['is_track_creation'] and booking['track_type']:
                        safe_type = SecurityUtils.safe_markdown_text(str(booking['track_type']))
                        booking_text += f"• Тип: {safe_type}\n"
                    
                    if booking['price'] is not None:
                        price_str = str(booking['price'])
                        if price_str == '':
                            booking_text += "• Стоимость: 0₽\n"
                        elif 'договорная' in price_str.lower():
                            booking_text += "• Стоимость: Договорная\n"
                        else:
                            try:
                                price_int = int(float(price_str))
                                formatted_price = f"{price_int:,}₽".replace(',', ' ')
                                booking_text += f"• Стоимость: {formatted_price}\n"
                            except:
                                safe_price = SecurityUtils.safe_markdown_text(price_str)
                                booking_text += f"• Стоимость: {safe_price}\n"
                    else:
                        booking_text += "• Стоимость: 0₽\n"
                    
                    # ===== ДОБАВЛЯЕМ КУПОН =====
                    if booking.get('coupon_text'):
                        booking_text += f"{booking['coupon_text']}\n"
                    
                    # ===== ДОБАВЛЯЕМ ПРОМОКОД =====
                    if booking.get('promo_text'):
                        booking_text += f"{booking['promo_text']}\n"
                    
                    booking_text += f"• Статус: {booking['status_text']}\n\n"
                    
                    if len(current_part + booking_text) > 3500:
                        message_parts.append(current_part)
                        current_part = booking_text
                    else:
                        current_part += booking_text
            
            # ===== АДМИНСКИЕ ЗАПИСИ =====
            if admin_bookings:
                if len(current_part + "*👑 Админские записи:*\n\n") > 3500:
                    message_parts.append(current_part)
                    current_part = "*👑 Админские записи:*\n\n"
                else:
                    current_part += "*👑 Админские записи:*\n\n"
                
                for booking in admin_bookings:
                    booking_text = f"{booking['status_emoji']} *Запись #{booking['id']}*\n"
                    booking_text += f"• Тип: 👑 Админская запись\n"
                    booking_text += f"• Имя: {booking['name']}\n"
                    booking_text += f"• Контакт: {booking['contact']}\n"
                    booking_text += f"• Услуга: {booking['service']}\n"
                    
                    if booking['date_str'] and 'Не указана' not in booking['date_str'] and booking['date_str'] != 'Запись в студии':
                        clean_date = booking['date_str'].split('(')[0].strip() if '(' in booking['date_str'] else booking['date_str']
                        safe_clean_date = SecurityUtils.safe_markdown_text(clean_date)
                        booking_text += f"• Дата: {safe_clean_date}\n"
                    
                    # ===== ИСПРАВЛЕНО: format_time_for_display() нормализует 24→00 =====
                    if (booking['time_slot'] and 
                        booking['time_slot'] not in ['Не указано', 'Не указано (договорная)', 'Запись в студии']):
                        display_time = DateTimeUtils.format_time_for_display(booking['time_slot'])
                        safe_display_time = SecurityUtils.safe_markdown_text(display_time)
                        booking_text += f"• Время: {safe_display_time}\n"
                    
                    if booking['price'] is not None:
                        price_str = str(booking['price'])
                        if price_str == '':
                            booking_text += "• Стоимость: 0₽\n"
                        elif 'договорная' in price_str.lower():
                            booking_text += "• Стоимость: Договорная\n"
                        else:
                            try:
                                price_int = int(float(price_str))
                                formatted_price = f"{price_int:,}₽".replace(',', ' ')
                                booking_text += f"• Стоимость: {formatted_price}\n"
                            except:
                                safe_price = SecurityUtils.safe_markdown_text(price_str)
                                booking_text += f"• Стоимость: {safe_price}\n"
                    else:
                        booking_text += "• Стоимость: 0₽\n"
                    
                    booking_text += f"• Статус: {booking['status_text']}\n\n"
                    
                    if len(current_part + booking_text) > 3500:
                        message_parts.append(current_part)
                        current_part = booking_text
                    else:
                        current_part += booking_text
            
            if current_part:
                message_parts.append(current_part)
            
            if edit_mode and query:
                try:
                    await query.edit_message_text(
                        text=message_parts[-1],
                        parse_mode="Markdown",
                        reply_markup=inline_keyboard
                    )
                    logger.info(f"✅ Последнее сообщение отредактировано с кнопками")
                except Exception as e:
                    logger.error(f"❌ Ошибка редактирования: {e}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message_parts[-1],
                        parse_mode="Markdown",
                        reply_markup=inline_keyboard
                    )
            else:
                for i, part in enumerate(message_parts):
                    if i == len(message_parts) - 1:
                        if is_callback:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=part,
                                parse_mode="Markdown",
                                reply_markup=inline_keyboard
                            )
                        else:
                            await message_obj.reply_text(
                                text=part,
                                parse_mode="Markdown",
                                reply_markup=inline_keyboard
                            )
                    else:
                        if is_callback:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=part,
                                parse_mode="Markdown"
                            )
                        else:
                            await message_obj.reply_text(
                                text=part,
                                parse_mode="Markdown"
                            )
        
        context.user_data['_conversation_state'] = ADMIN_CANCEL_SHOW_BOOKINGS
        context.user_data['target_user_id'] = target_user_id
        context.user_data['target_unique_id'] = target_unique_id
        context.user_data['target_username'] = target_username
        
    except Exception as e:
        logger.error(f"❌ Ошибка в admin_show_user_bookings: {e}")
        import traceback
        traceback.print_exc()
        
        error_message = "❌ Произошла ошибка при загрузке записей\n\nПожалуйста, попробуйте позже."
        
        try:
            if is_callback:
                await message_obj.edit_text(
                    text=error_message,
                    parse_mode="Markdown"
                )
            else:
                await message_obj.reply_text(
                    text=error_message,
                    parse_mode="Markdown"
                )
            
            menu_message = (
                "*🏠 Возвращаемся в главное меню*\n\n"
                "*👇 Выберите подходящий вариант:*"
            )
            
            if is_callback:
                try:
                    await message_obj.edit_text(
                        text=menu_message,
                        parse_mode="Markdown",
                        reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                    )
                except Exception as e:
                    logger.error(f"Ошибка редактирования: {e}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=menu_message,
                        parse_mode="Markdown",
                        reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=menu_message,
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                )
        except:
            pass
        
        context.user_data.clear()

async def admin_cancel_callback_handler(update: Update, context):
    """Обработка нажатия на кнопку отмены записи админом"""
    query = update.callback_query
    data = query.data
    
    try:
        booking_id = int(data.split('_')[2])
    except (IndexError, ValueError):
        await query.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    booking_info = None
    for booking in context.user_data.get('user_bookings_list', []):
        if booking['id'] == booking_id:
            booking_info = booking
            break
    
    if not booking_info:
        await query.answer("❌ Запись не найдена!", show_alert=True)
        return
    
    context.user_data['admin_cancel_booking_id'] = booking_id
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, contact, service, date_str, time_slot, status, price,
                   telegram_id, is_12_hours, twelve_hours_type, is_mixing, mixing_type,
                   is_track_creation, track_type, with_engineer, duration, is_contractual
            FROM bookings 
            WHERE id = ?
        ''', (booking_id,))
        
        booking = cursor.fetchone()
        
        if not booking:
            await query.answer("❌ Запись не найдена!", show_alert=True)
            return
        
        (db_id, name, contact, service, date_str, time_slot, status, price,
         telegram_id, is_12_hours, twelve_hours_type, is_mixing, mixing_type,
         is_track_creation, track_type, with_engineer, duration, is_contractual) = booking
        
        status_lower = status.lower() if status else ""
        
        clean_date = date_str
        if date_str and '(' in date_str:
            clean_date = date_str.split('(')[0].strip()
        if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
            clean_date = clean_date[2:].strip()
        
        display_time = time_slot
        if time_slot and '-' in time_slot:
            display_time = DateTimeUtils.format_time_for_display(time_slot)
        
        # Формируем отображение цены БЕЗ лишнего ₽
        price_text = ""
        if is_12_hours:
            rent_price = 7000 if twelve_hours_type and 'День' in twelve_hours_type else 6500
            price_text = f"{rent_price}₽ + залог (по договору)"
        elif price and str(price) != '0':
            if 'договорная' in str(price).lower():
                price_text = "Договорная"
            else:
                try:
                    price_int = int(float(price))
                    price_text = f"{price_int:,}".replace(',', ' ')  # Без ₽
                except:
                    price_text = str(price).replace('₽', '').strip()  # Убираем ₽ если есть
        else:
            price_text = "0"
        
        if 'completed' in status_lower or 'завершен' in status_lower:
            status_display = 'Завершена'
        elif 'confirmed' in status_lower or 'подтвержден' in status_lower:
            status_display = 'Подтверждена'
        elif 'pending' in status_lower or 'ожидает' in status_lower:
            status_display = 'Ожидает подтверждения'
        elif 'rejected' in status_lower or 'отклонен' in status_lower:
            status_display = 'Отклонена'
        elif 'cancelled' in status_lower or 'отменен' in status_lower:
            status_display = 'Отменена'
        else:
            status_display = status
        
        confirmation_text = (
            f"*⚠️ Вы уверены, что хотите отменить запись?*\n\n"
            f"*📋 Детали записи:*\n"
            f"• Имя: {name}\n"
            f"• Контакт: {contact}\n"
            f"• Услуга: {service}\n"
        )
        
        if is_12_hours and twelve_hours_type:
            confirmation_text += f"• Тип: {twelve_hours_type}\n"
        elif is_mixing and mixing_type:
            confirmation_text += f"• Тип: {mixing_type}\n"
        elif is_track_creation and track_type:
            confirmation_text += f"• Тип: {track_type}\n"
        
        if clean_date and 'Не указана' not in clean_date:
            confirmation_text += f"• Дата: {clean_date}\n"
        
        if display_time and display_time not in ['Не указано', 'Не указано (договорная)']:
            if is_12_hours:
                confirmation_text += f"• Время: {display_time} (12 часов)\n"
            elif duration and duration > 0:
                formatted_duration = PriceCalculator.format_hours_ru(duration)
                confirmation_text += f"• Время: {display_time} ({formatted_duration})\n"
            else:
                confirmation_text += f"• Время: {display_time}\n"
        
        if price_text:
            confirmation_text += f"• Стоимость: {price_text}\n"
        
        confirmation_text += f"• Статус: {status_display}\n\n"
        confirmation_text += f"*❌ Отменить запись?*"
        
        context.user_data['admin_cancel_booking_data'] = {
            'name': name,
            'contact': contact,
            'service': service,
            'date_str': clean_date,
            'time_slot': display_time,
            'price': price_text,
            'telegram_id': telegram_id,
            'is_12_hours': is_12_hours,
            'twelve_hours_type': twelve_hours_type,
            'is_mixing': is_mixing,
            'mixing_type': mixing_type,
            'is_track_creation': is_track_creation,
            'track_type': track_type,
            'duration': duration,
            'is_contractual': is_contractual
        }
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, отменить", callback_data=f"admin_cancel_confirm_{booking_id}"),
                InlineKeyboardButton("❌ Нет, оставить", callback_data="admin_cancel_keep")
            ]
        ])
        
        await query.edit_message_text(
            text=confirmation_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def admin_cancel_keep_handler(update: Update, context):
    """Отмена удаления записи (оставить) - возвращает админский список записей"""
    query = update.callback_query
    
    if query.data != "admin_cancel_keep":
        return
    
    await query.answer()
    
    target_user_id = context.user_data.get('target_user_id')
    target_unique_id = context.user_data.get('target_unique_id')
    target_username = context.user_data.get('target_username')
    
    if target_user_id:
        # ВЫЗЫВАЕМ АДМИНСКУЮ ФУНКЦИЮ, А НЕ ПОЛЬЗОВАТЕЛЬСКУЮ
        await admin_show_user_bookings(
            update, context,
            target_user_id=target_user_id,
            target_unique_id=target_unique_id,
            target_username=target_username,
            edit_mode=True  # Важно: передаём edit_mode=True, чтобы обновить существующее сообщение
        )

@handle_errors_with_rate_limit
async def handle_admin_cancel_back(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_cancel_back: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        context.user_data.clear()
        context.user_data['is_admin_cancel'] = True
        context.user_data['_conversation_state'] = ADMIN_CANCEL_USER_ID
        context.user_data['nav_sent'] = False
        
        await update.message.reply_text(
            "*👑 Шаг 1/2: Ввод имени пользователя*\n\n"
            "🔍 Введите данные пользователя, чью запись нужно отменить:\n\n"
            "📋 Варианты ввода:\n"
            "• Уникальный ID (MC...): `MC1772377294899374`\n"
            "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
            "💡 Где найти Уникальный ID:\n"
            "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
            "*✏️ Введите данные:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_CANCEL_USER_ID
    
    await update.message.reply_text(
        "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True)
    )
    return ADMIN_CANCEL_SHOW_BOOKINGS

@handle_errors_with_rate_limit
async def handle_admin_award_achievement_start(update: Update, context):
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    context.user_data['is_admin_achievement'] = True
    context.user_data['_conversation_state'] = ADMIN_ACHIEVEMENT_USER_ID
    
    await update.message.reply_text(
        "*👑 Шаг 1/3: Ввод имени пользователя*\n\n"
        "*📋 Варианты ввода:*\n"
        "• Уникальный ID (MC...): `MC1772377294899374`\n"
        "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
        "*💡 Где найти Уникальный ID:*\n"
        "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
        "*✏️ Введите данные:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_ACHIEVEMENT_USER_ID

@handle_errors_with_rate_limit
async def handle_admin_achievement_user_id(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_achievement_user_id: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    search_term = text.replace('@', '').strip().lower()
    found_user = None

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # ===== 1. Поиск по уникальному ID (MC...) =====
            if search_term.startswith("mc"):
                logger.info(f"🔍 Ищем по уникальному ID: {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE LOWER(unique_id) = ?
                ''', (search_term,))
                found_user = cursor.fetchone()

            # ===== 2. Поиск по username (точное) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (точное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE LOWER(username) = ? OR LOWER(username) = ?
                ''', (search_term, f'@{search_term}'))
                found_user = cursor.fetchone()

            # ===== 3. Поиск по username (частичное) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (частичное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE 
                    LOWER(username) LIKE ? OR 
                    LOWER(username) LIKE ? OR
                    LOWER(first_name) LIKE ? OR
                    LOWER(unique_id) LIKE ?
                ''', (f'%{search_term}%', f'%@{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                found_user = cursor.fetchone()

            if not found_user:
                await update.message.reply_text(
                    f"*❌ Пользователь не найден!*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню"]
                    ], resize_keyboard=True)
                )
                return ADMIN_ACHIEVEMENT_USER_ID

            telegram_id, username, first_name, unique_id = found_user
            
            user_display = get_user_display_name({
                'username': username,
                'unique_id': unique_id,
                'telegram_id': telegram_id
            })
            
            context.user_data['target_achievement_user_id'] = telegram_id
            context.user_data['target_achievement_unique_id'] = unique_id
            context.user_data['target_achievement_username'] = username or first_name or "Неизвестный"
            context.user_data['target_achievement_display'] = user_display

            logger.info(f"✅ Админ нашел пользователя для выдачи достижения: {unique_id} (отображается как: {user_display}")

    except Exception as e:
        logger.error(f"❌ Ошибка поиска пользователя: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "❌ Ошибка при поиске пользователя!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_ACHIEVEMENT_USER_ID

    await update.message.reply_text(
        "*👑 Шаг 2/3: Выбор достижения*\n\n"
        f"*✅ Найден пользователь: {context.user_data['target_achievement_display']}*\n\n"
        f"*📋 Уникальный ID: {context.user_data['target_achievement_unique_id']}*\n\n"
        f"*✏️ Введите название:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_ACHIEVEMENT_NAME

@handle_errors_with_rate_limit
async def handle_admin_achievement_name(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_achievement_name: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*👑 Шаг 1/3: Ввод имени пользователя*\n\n"
            "*📋 Варианты ввода:*\n"
            "• Уникальный ID (MC...): `MC1772377294899374`\n"
            "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
            "*💡 Где найти Уникальный ID:*\n"
            "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
            "*✏️ Введите данные:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_ACHIEVEMENT_USER_ID
    
    achievement_map = {
        "Добро пожаловать": "first_booking",
        "Новичок": "novice",
        "Любитель": "amateur",
        "Профи": "pro",
        "Ветеран": "veteran",
        "Легенда студии": "studio_legend",
        "Вокалист": "vocalist",
        "Виртуоз": "virtuoso",
        "Арендатор": "renter",
        "Золотые уши": "golden_ears",
        "Автор": "author",
        "Универсал": "universal",
        "Позвал друга": "friend_inviter",
        "Социальный": "social",
        "Звезда": "star",
        "Магнат": "magnate",
        "Сетевой гигант": "network_giant",
        "Имя на стене": "name_on_wall",
        "Godspeed Legend": "godspeed_legend",
        "Золотой микрофон": "golden_mic"
    }
    
    achievement_id = None
    found_name = None
    
    if text in achievement_map:
        achievement_id = achievement_map[text]
        found_name = text
    else:
        text_lower = text.lower()
        for name, ach_id in achievement_map.items():
            if text_lower in name.lower() or name.lower() in text_lower:
                achievement_id = ach_id
                found_name = name
                break
    
    if not achievement_id:
        achievements_list = []
        achievements_list.append("Записи в студии:")
        for item in ["Добро пожаловать", "Новичок", "Любитель", "Профи", "Ветеран", "Легенда студии"]:
            achievements_list.append(f"• {item}")
        
        achievements_list.append("\nТипы услуг:")
        for item in ["Вокалист", "Виртуоз", "Арендатор", "Золотые уши", "Автор", "Универсал"]:
            achievements_list.append(f"• {item}")
        
        achievements_list.append("\nРефералы:")
        for item in ["Позвал друга", "Социальный", "Звезда", "Магнат", "Сетевой гигант"]:
            achievements_list.append(f"• {item}")
        
        achievements_list.append("\nОсобые:")
        for item in ["Имя на стене", "Godspeed Legend", "Золотой микрофон"]:
            achievements_list.append(f"• {item}")
        
        await update.message.reply_text(
            f"*❌ Достижение не найдено!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_ACHIEVEMENT_NAME
    
    target_user_id = context.user_data.get('target_achievement_user_id')
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM user_achievements 
            WHERE user_id = ? AND achievement_id = ?
        ''', (target_user_id, achievement_id))
        
        existing = cursor.fetchone()
        
        if existing:
            ach_info = AchievementSystem.ACHIEVEMENTS.get(achievement_id, {})
            emoji = ach_info.get('emoji', '🏆')
            
            await update.message.reply_text(
                f"*❌ У пользователя уже есть это достижение!*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
            return ADMIN_ACHIEVEMENT_NAME
    
    context.user_data['achievement_name'] = found_name
    context.user_data['achievement_id'] = achievement_id
    
    ach_info = AchievementSystem.ACHIEVEMENTS.get(achievement_id, {})
    vinyls_reward = ach_info.get('vinyls', 0)
    emoji = ach_info.get('emoji', '🏆')
    
    confirmation_text = (
        f"*👑 Шаг 3/3: Подтверждение*\n\n"
        f"*✅ Проверьте данные:*\n\n"
        f"*📋 Данные:\n*"
        f"• Уникальный ID: {context.user_data['target_achievement_unique_id']}\n"
        f"• Достижение: {emoji} {found_name}\n"
        f"• Награда: +{vinyls_reward} пластинок 💿\n\n"
        f"*👇 Всё верно?*"
    )
    
    await update.message.reply_text(
        confirmation_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["✅ Да, выдать достижение", "✏️ Исправить данные"],
            ["❌ Отменить"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_ACHIEVEMENT_CONFIRM

@handle_errors_with_rate_limit
async def handle_admin_achievement_confirm(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_achievement_confirm: '{text}'")
    
    target_user_id = context.user_data.get('target_achievement_user_id')
    target_unique_id = context.user_data.get('target_achievement_unique_id')
    target_username = context.user_data.get('target_achievement_username')
    achievement_id = context.user_data.get('achievement_id')
    achievement_name = context.user_data.get('achievement_name')
    admin_id = str(update.effective_user.id)
    admin_username = update.effective_user.username or "Администратор"
    
    # ПОЛУЧАЕМ USERNAME ЕСЛИ ОН НЕ БЫЛ СОХРАНЕН
    if not target_username and target_user_id:
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT username, first_name FROM users WHERE telegram_id = ?', (target_user_id,))
                user_data = cursor.fetchone()
                if user_data:
                    target_username = user_data[0] or user_data[1] or str(target_user_id)
                    context.user_data['target_achievement_username'] = target_username
        except Exception as e:
            logger.error(f"Ошибка получения username: {e}")
            target_username = target_unique_id or str(target_user_id)
    
    if text == "↩️ Главное меню" or text == "❌ Отменить":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "✏️ Исправить данные":
        await update.message.reply_text(
            "*👑 Шаг 2/3: Выбор достижения*\n\n"
            f"*✅ Найден пользователь: @{target_username}*\n\n"
            f"*📋 Уникальный ID: {target_unique_id}\n\n*"
            f"*✏️ Введите название:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_ACHIEVEMENT_NAME
    
    if text != "✅ Да, выдать достижение":
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Да, выдать достижение", "✏️ Исправить данные"],
                ["❌ Отменить"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_ACHIEVEMENT_CONFIRM
    
    success, message = await AchievementSystem.award_manual_achievement(
        target_user_id, achievement_id, admin_id, context
    )
    
    if success:
        # ИСПРАВЛЕНО - используем username или unique_id как запасной вариант
        if target_username and target_username != "None":
            admin_message = f"*✅ Достижение создано для пользователя @{target_username}*"
        else:
            admin_message = f"*✅ Достижение создано для пользователя {target_unique_id}*"
        
        await update.message.reply_text(
            admin_message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        
        logger.info(f"✅ Админ @{admin_username} выдал достижение {achievement_name} пользователю {target_user_id}")
        
    else:
        await update.message.reply_text(
            f"❌ Ошибка при выдаче достижения: {message}",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
    
    context.user_data.clear()
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def handle_admin_remove_achievement_start(update: Update, context):
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    context.user_data['is_admin_remove_achievement'] = True
    context.user_data['_conversation_state'] = ADMIN_REMOVE_ACHIEVEMENT_USER_ID
    context.user_data['nav_sent'] = False
    
    await update.message.reply_text(
        "*👑 Шаг 1/2: Ввод имени пользователя*\n\n"
        "*📋 Варианты ввода:*\n"
        "• Уникальный ID (MC...): `MC1772377294899374`\n"
        "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
        "*💡 Где найти Уникальный ID:*\n"
        "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
        "*✏️ Введите данные:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_REMOVE_ACHIEVEMENT_USER_ID

@handle_errors_with_rate_limit
async def handle_admin_remove_achievement_user_id(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_remove_achievement_user_id: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    search_term = text.replace('@', '').strip().lower()
    found_user = None

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # ===== 1. Поиск по уникальному ID (MC...) =====
            if search_term.startswith("mc"):
                logger.info(f"🔍 Ищем по уникальному ID: {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE LOWER(unique_id) = ?
                ''', (search_term,))
                found_user = cursor.fetchone()
                if found_user:
                    logger.info(f"✅ Найден пользователь по уникальному ID: {search_term}")

            # ===== 2. Поиск по username (точное) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (точное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE LOWER(username) = ? OR LOWER(username) = ?
                ''', (search_term, f'@{search_term}'))
                found_user = cursor.fetchone()
                if found_user:
                    logger.info(f"✅ Найден пользователь по username (точное): {search_term}")

            # ===== 3. Поиск по username (частичное) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (частичное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE 
                    LOWER(username) LIKE ? OR 
                    LOWER(username) LIKE ? OR
                    LOWER(first_name) LIKE ? OR
                    LOWER(unique_id) LIKE ?
                ''', (f'%{search_term}%', f'%@{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                found_user = cursor.fetchone()
                if found_user:
                    logger.info(f"✅ Найден пользователь по частичному совпадению: {search_term}")

            if not found_user:
                await update.message.reply_text(
                    f"*❌ Пользователь не найден!*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню"]
                    ], resize_keyboard=True)
                )
                return ADMIN_REMOVE_ACHIEVEMENT_USER_ID

            telegram_id, username, first_name, unique_id = found_user
            context.user_data['target_remove_achievement_user_id'] = telegram_id
            context.user_data['target_remove_achievement_unique_id'] = unique_id
            context.user_data['target_remove_achievement_username'] = username or first_name or "Неизвестный"

            logger.info(f"✅ Админ нашел пользователя для удаления достижения: {unique_id} (TG: {telegram_id})")

            await admin_show_user_achievements(
                update, context,
                target_user_id=telegram_id,
                target_unique_id=unique_id,
                target_username=username or first_name
            )
            return ADMIN_REMOVE_ACHIEVEMENT_SHOW

    except Exception as e:
        logger.error(f"❌ Ошибка поиска пользователя: {e}")
        import traceback
        traceback.print_exc()
        
        await update.message.reply_text(
            "❌ Ошибка при поиске пользователя!\n\n"
            "Пожалуйста, попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_REMOVE_ACHIEVEMENT_USER_ID

async def admin_show_user_achievements(update: Update, context, target_user_id: int, target_unique_id: str = None, target_username: str = None):
    """Показать достижения пользователя для админа"""
    try:
        logger.info(f"🔍 admin_show_user_achievements для пользователя: {target_user_id}")
        
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            await query.answer()
            message_obj = query.message
            chat_id = message_obj.chat_id
            is_callback = True
        else:
            message_obj = update.message
            chat_id = message_obj.chat_id
            is_callback = False
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, achievement_id, achievement_name, achievement_type, awarded_at
                FROM user_achievements 
                WHERE user_id = ?
                ORDER BY awarded_at DESC
            ''', (str(target_user_id),))
            
            achievements = cursor.fetchall()
            
            if not achievements:
                message_text = (
                    f"*📋 Достижения пользователя*\n\n"
                    f"*👤 @{target_username if target_username else 'Неизвестный'} {target_unique_id if target_unique_id else ''}*\n\n"
                    f"*📭 У пользователя нет достижений*"
                )
                
                if is_callback:
                    try:
                        await message_obj.edit_reply_markup(reply_markup=None)
                        await message_obj.edit_text(
                            text=message_text,
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка редактирования: {e}")
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=message_text,
                            parse_mode="Markdown"
                        )
                else:
                    await message_obj.reply_text(
                        text=message_text,
                        parse_mode="Markdown"
                    )
                
                menu_message = (
                    "*🏠 Возвращаемся в главное меню*\n\n"
                    "*👇 Выберите подходящий вариант:*"
                )
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=menu_message,
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                )
                
                context.user_data.clear()
                return ConversationHandler.END
            
            response = f"*📋 Достижения пользователя*\n\n"
            response += f"*👤 @{target_username if target_username else 'Неизвестный'} {target_unique_id if target_unique_id else ''}*\n\n"
            response += "*📝 Список достижений:*\n\n"
            
            achievements_list = []
            
            for i, ach in enumerate(achievements, 1):
                db_id, achievement_id, achievement_name, achievement_type, awarded_at = ach
                
                ach_info = AchievementSystem.ACHIEVEMENTS.get(achievement_id, {})
                emoji = ach_info.get('emoji', '🏆')
                vinyls = ach_info.get('vinyls', 0)
                
                response += f"{i}. {emoji} *{achievement_name}* (+{vinyls}💿)\n"
                
                if awarded_at:
                    awarded_date = datetime.strptime(awarded_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
                    response += f"   📅 Получено: {awarded_date}\n"
                
                response += "\n"
                
                achievements_list.append({
                    'db_id': db_id,
                    'achievement_id': achievement_id,
                    'name': achievement_name,
                    'type': achievement_type,
                    'number': i
                })
            
            context.user_data['user_achievements_list'] = achievements_list
            
            keyboard_buttons = []
            for ach in achievements_list:
                button_text = f"❌ Удалить #{ach['number']}"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"admin_remove_achievement_{ach['db_id']}"
                    )
                ])
            
            inline_keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            if is_callback:
                await message_obj.edit_reply_markup(reply_markup=None)
                await message_obj.edit_text(
                    text=response,
                    parse_mode="Markdown",
                    reply_markup=inline_keyboard
                )
            else:
                await message_obj.reply_text(
                    text=response,
                    parse_mode="Markdown",
                    reply_markup=inline_keyboard
                )
        
        context.user_data['_conversation_state'] = ADMIN_REMOVE_ACHIEVEMENT_SHOW
        context.user_data['target_remove_user_id'] = target_user_id
        context.user_data['target_remove_unique_id'] = target_unique_id
        context.user_data['target_remove_username'] = target_username
        
    except Exception as e:
        logger.error(f"❌ Ошибка в admin_show_user_achievements: {e}")
        import traceback
        traceback.print_exc()
        
        error_message = "❌ Произошла ошибка при загрузке достижений\n\nПожалуйста, попробуйте позже."
        
        try:
            if is_callback:
                await message_obj.edit_text(
                    text=error_message,
                    parse_mode="Markdown"
                )
            else:
                await message_obj.reply_text(
                    text=error_message,
                    parse_mode="Markdown"
                )
        except:
            pass
        
        context.user_data.clear()
        return ConversationHandler.END

@handle_errors_with_rate_limit
async def admin_remove_achievement_callback(update: Update, context):
    query = update.callback_query
    data = query.data
    
    try:
        achievement_db_id = int(data.split('_')[3])
    except (IndexError, ValueError):
        await query.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    achievement_info = None
    achievements_list = context.user_data.get('user_achievements_list', [])
    
    for ach in achievements_list:
        if ach['db_id'] == achievement_db_id:
            achievement_info = ach
            break
    
    if not achievement_info:
        await query.answer("*❌ Достижение не найдено!*", show_alert=True)
        return
    
    context.user_data['remove_achievement_db_id'] = achievement_db_id
    context.user_data['remove_achievement_id'] = achievement_info['achievement_id']
    context.user_data['remove_achievement_name'] = achievement_info['name']
    
    target_user_id = context.user_data.get('target_remove_user_id')
    target_unique_id = context.user_data.get('target_remove_unique_id')
    target_username = context.user_data.get('target_remove_username')
    
    achievement_number = None
    for i, ach in enumerate(achievements_list, 1):
        if ach['db_id'] == achievement_db_id:
            achievement_number = i
            break
    
    confirmation_text = (
        f"*⚠️ Вы уверены, что хотите удалить достижение?*\n\n"
        f"*📋 Детали:*\n"
        f"• Уникальный ID: {target_unique_id}\n"
        f"• Название достижения: 🏆 {achievement_info['name']}\n"
        f"• Номер в списке: #{achievement_number}\n\n"
        f"*❌ Удалить достижение?*"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_remove_achievement_confirm_{achievement_db_id}"),
            InlineKeyboardButton("❌ Нет, оставить", callback_data="admin_remove_achievement_cancel")
        ]
    ])
    
    await query.edit_message_text(
        text=confirmation_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def admin_remove_achievement_confirm(update: Update, context):
    """Подтверждение удаления достижения"""
    query = update.callback_query
    data = query.data

    try:
        achievement_db_id = int(data.split('_')[4])
    except (IndexError, ValueError):
        await query.answer("❌ Неверный формат данных!", show_alert=True)
        return

    target_user_id = context.user_data.get('target_remove_user_id')
    target_unique_id = context.user_data.get('target_remove_unique_id')
    target_username = context.user_data.get('target_remove_username')
    achievement_id = context.user_data.get('remove_achievement_id')
    achievement_name = context.user_data.get('remove_achievement_name')
    admin_id = str(update.effective_user.id)

    ach_info = AchievementSystem.ACHIEVEMENTS.get(achievement_id, {})
    vinyls_to_remove = ach_info.get('vinyls', 0)
    
    # Получаем номер достижения в списке
    achievement_number = None
    achievements_list = context.user_data.get('user_achievements_list', [])
    for i, ach in enumerate(achievements_list, 1):
        if ach['db_id'] == achievement_db_id:
            achievement_number = i
            break
    
    # Получаем старые пластинки до удаления
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(target_user_id),))
        user_row = cursor.fetchone()
        old_vinyls = user_row[0] if user_row else 0
    
    # Выполняем удаление
    success, message = await AchievementSystem.remove_achievement(
        str(target_user_id), achievement_id, admin_id, None
    )
    
    if success:
        # Получаем новые пластинки после удаления
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(target_user_id),))
            user_row = cursor.fetchone()
            new_vinyls = user_row[0] if user_row else 0
        
        # Отправляем уведомление об изменении уровня (если уровень изменился)
        await AchievementSystem.notify_level_change(str(target_user_id), old_vinyls, new_vinyls, context)
        
        # Отправляем уведомление об удалении достижения (С ЖИРНЫМ ТЕКСТОМ)
        try:
            delete_message = (
                f"*❌ Администратор удалил достижение*\n\n"
                f"*Достижение «{achievement_name}» было удалено.*\n"
                f"*📉 У вас отозвано {vinyls_to_remove} пластинок.*\n"
                f"*💰 Текущее количество пластинок: {new_vinyls} 💿*\n\n"
                f"*📞 Свяжитесь с администратором @mothman32 для уточнения*"
            )
            
            await context.bot.send_message(
                chat_id=int(target_user_id),
                text=delete_message,
                parse_mode="Markdown"
            )
            logger.info(f"✅ Уведомление об удалении достижения отправлено пользователю {target_user_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление об удалении: {e}")
        
        # Сообщение админу (С ВОЗВРАТОМ НОМЕРА)
        if achievement_number:
            admin_success_message = f"*✅ Достижение #{achievement_number} удалено из базы пользователя*"
        else:
            admin_success_message = f"*✅ Достижение «{achievement_name}» удалено из базы пользователя*"
        
        await context.bot.send_message(
            chat_id=int(admin_id),
            text=admin_success_message,
            parse_mode="Markdown"
        )
        
        # Проверяем, остались ли достижения
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM user_achievements WHERE user_id = ?
            ''', (str(target_user_id),))
            remaining = cursor.fetchone()[0] or 0

        if remaining == 0:
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except:
                pass
            
            no_achievements_text = (
                f"*📋 Достижения пользователя*\n\n"
                f"*👤 @{target_username if target_username else 'Неизвестный'} {target_unique_id if target_unique_id else ''}*\n\n"
                f"*📭 У пользователя нет достижений*"
            )
            
            await query.edit_message_text(
                text=no_achievements_text,
                parse_mode="Markdown"
            )
            
            menu_message = (
                "*🏠 Возвращаемся в главное меню*\n\n"
                "*👇 Выберите подходящий вариант:*"
            )
            
            await context.bot.send_message(
                chat_id=int(admin_id),
                text=menu_message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            
            context.user_data.clear()
            
        else:
            await admin_show_user_achievements(
                update, context,
                target_user_id=target_user_id,
                target_unique_id=target_unique_id,
                target_username=target_username
            )

    else:
        await query.edit_message_text(
            text=f"❌ Ошибка: {message}",
            parse_mode="Markdown"
        )

@staticmethod
async def remove_achievement(user_id: str, achievement_id: str, admin_id: str, context=None):
    """Удаляет достижение (БЕЗ отправки уведомлений - только удаление)"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем информацию о достижении
            cursor.execute('''
                SELECT achievement_name, achievement_type FROM user_achievements 
                WHERE user_id = ? AND achievement_id = ?
            ''', (user_id, achievement_id))
            
            result = cursor.fetchone()
            if not result:
                return False, "❌ Достижение не найдено у пользователя"
            
            achievement_name, achievement_type = result
            
            ach = AchievementSystem.ACHIEVEMENTS.get(achievement_id, {})
            vinyls_to_remove = ach.get('vinyls', 0)
            
            # Удаляем достижение
            cursor.execute('''
                DELETE FROM user_achievements 
                WHERE user_id = ? AND achievement_id = ?
            ''', (user_id, achievement_id))
            
            # Списываем пластинки
            cursor.execute('''
                UPDATE users SET vinyls = vinyls - ? WHERE telegram_id = ? AND vinyls >= ?
            ''', (vinyls_to_remove, user_id, vinyls_to_remove))
            
            conn.commit()
            
            # Обновляем уровень (БЕЗ отправки уведомлений)
            await AchievementSystem.update_user_level(user_id, None, send_notification=False)
            
            return True, f"❌ Достижение «{achievement_name}» удалено"
            
    except Exception as e:
        logger.error(f"Ошибка удаления достижения: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

async def admin_remove_achievement_cancel(update: Update, context):
    """Отмена удаления достижения"""
    query = update.callback_query
    
    target_user_id = context.user_data.get('target_remove_user_id')
    target_unique_id = context.user_data.get('target_remove_unique_id')
    target_username = context.user_data.get('target_remove_username')
    
    await query.answer()  # Без текста, без alert
    
    await admin_show_user_achievements(
        update, context,
        target_user_id=target_user_id,
        target_unique_id=target_unique_id,
        target_username=target_username
    )

@handle_errors_with_rate_limit
async def handle_admin_remove_achievement_back(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_remove_achievement_back: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        context.user_data.clear()
        context.user_data['is_admin_remove_achievement'] = True
        context.user_data['_conversation_state'] = ADMIN_REMOVE_ACHIEVEMENT_USER_ID
        context.user_data['nav_sent'] = False
        
        await update.message.reply_text(
            "*👑 Шаг 1/2: Ввод имени пользователя*\n\n"
            "*📋 Варианты ввода:*\n"
            "• Уникальный ID (MC...): `MC1772377294899374`\n"
            "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
            "*💡 Где найти Уникальный ID:*\n"
            "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
            "*✏️ Введите данные:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_REMOVE_ACHIEVEMENT_USER_ID
    
    await update.message.reply_text(
        "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True)
    )
    return ADMIN_REMOVE_ACHIEVEMENT_SHOW

@handle_errors_with_rate_limit
async def handle_admin_create_booking(update: Update, context):
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "*❌ У вас нет прав для этого действия!*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    context.user_data['is_admin_booking'] = True
    context.user_data['admin_telegram_id'] = str(user_id)
    
    await update.message.reply_text(
        "*👑 Шаг 1/4: Ввод имени пользователя*\n\n"
        "*📋 Варианты ввода:*\n"
        "• Уникальный ID (MC...): `MC1772377294899374`\n"
        "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
        "*💡 Где найти Уникальный ID:*\n"
        "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
        "*✏️ Введите данные:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_USER_ID

@handle_errors_with_rate_limit
async def handle_admin_user_id(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_user_id: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    search_term = text.replace('@', '').strip().lower()
    found_user = None

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            if search_term.startswith("mc"):
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE LOWER(unique_id) = ?
                ''', (search_term,))
                found_user = cursor.fetchone()

            if not found_user:
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE LOWER(username) = ? OR LOWER(username) = ?
                ''', (search_term, f'@{search_term}'))
                found_user = cursor.fetchone()

            if not found_user:
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id
                    FROM users WHERE 
                    LOWER(username) LIKE ? OR 
                    LOWER(username) LIKE ? OR
                    LOWER(first_name) LIKE ? OR
                    LOWER(unique_id) LIKE ?
                ''', (f'%{search_term}%', f'%@{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                found_user = cursor.fetchone()

            if not found_user:
                await update.message.reply_text(
                    f"*❌ Пользователь не найден!*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню"]
                    ], resize_keyboard=True)
                )
                return ADMIN_USER_ID

            telegram_id, username, first_name, unique_id = found_user
            
            user_display = get_user_display_name({
                'username': username,
                'unique_id': unique_id,
                'telegram_id': telegram_id
            })
            
            context.user_data['target_unique_id'] = unique_id
            context.user_data['target_telegram_id'] = telegram_id
            context.user_data['target_username'] = username or first_name or "Неизвестный"
            context.user_data['target_display'] = user_display

    except Exception as e:
        logger.error(f"❌ Ошибка поиска пользователя: {e}")
        await update.message.reply_text(
            "*❌ Ошибка при поиске пользователя!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_USER_ID

    await update.message.reply_text(
        "*👑 Шаг 2/4: Выбор типа записи*\n\n"
        f"*✅ Найден пользователь: @{context.user_data['target_username']}*\n\n"
        f"*📋 Уникальный ID: {context.user_data['target_unique_id']}*\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["📝 Договорная запись", "🎤 Запись в студии"],
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_RECORD_TYPE

@handle_errors_with_rate_limit
async def handle_admin_record_type(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_record_type: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*👑 Шаг 1/4: Ввод имени пользователя*\n\n"
            "*📋 Варианты ввода:*\n"
            "• Уникальный ID (MC...): `MC1772377294899374`\n"
            "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
            "*💡 Где найти Уникальный ID:*\n"
            "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
            "*✏️ Введите данные:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_USER_ID
    
    if text not in ["📝 Договорная запись", "🎤 Запись в студии"]:
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["📝 Договорная запись", "🎤 Запись в студии"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_RECORD_TYPE
    
    context.user_data['admin_record_type'] = text
    
    await update.message.reply_text(
        "*👑 Шаг 3/4: Ввод стоимости*\n\n"
        "*📋 Правила ввода:*\n"
        "• Только цифры от 0 до 10 000 000\n"
        "• Для договорной стоимости можно указать 0\n\n"
        "*✏️ Введите стоимость:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_PRICE

@handle_errors_with_rate_limit
async def handle_admin_price(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_price: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        target_username = context.user_data.get('target_username', 'Неизвестный')
        unique_id = context.user_data.get('target_unique_id', 'Неизвестно')
        
        await update.message.reply_text(
            "*👑 Шаг 2/4: Выбор типа записи*\n\n"
            f"*✅ Найден пользователь: @{target_username}*\n\n"
            f"*📋 Уникальный ID: {unique_id}*\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["📝 Договорная запись", "🎤 Запись в студии"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_RECORD_TYPE
    
    try:
        if not text.isdigit():
            raise ValueError("Ввод должен содержать только цифры")
        
        price = int(text)
        
        if price < 0 or price > 10000000:
            raise ValueError("Стоимость должна быть от 0 до 10 000 000")
        
        context.user_data['admin_price'] = price
        context.user_data['admin_price_str'] = str(price)
        
        logger.info(f"✅ Админ ввел стоимость: {price}₽")
        
    except ValueError as e:
        await update.message.reply_text(
            "*❌ Неверный формат стоимости!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_PRICE
    
    record_type = context.user_data.get('admin_record_type', 'Не указан')
    unique_id = context.user_data.get('target_unique_id', 'Не указан')
    price_str = context.user_data.get('admin_price_str', '0')
    
    try:
        price_int = int(price_str)
        formatted_price = f"{price_int:,}₽".replace(',', ' ')
        if price_int == 0:
            formatted_price = "0₽ (Договорная)"
    except:
        formatted_price = f"{price_str}₽"
    
    # Очищаем тип записи от смайликов
    clean_record_type = record_type.replace('📝', '').replace('🎤', '').strip()
    
    # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ =====
    confirmation_lines = [
        f"*👑 Шаг 4/4: Подтверждение*",
        "",
        f"*✨ Проверьте правильность Ваших данных:*",
        "",
        f"• Уникальный ID: {unique_id}",
        f"• Тип записи: {clean_record_type}",
        f"• Стоимость: {formatted_price}",
        "",
        f"*📝 Дополнительная информация:*",
        f"• Запись будет создана от имени администратора",
        f"• Пользователь увидит запись в своем профиле",
        "",
        "*👇 Всё верно?*"
    ]
    
    confirmation_text = "\n".join(confirmation_lines)
    
    await update.message.reply_text(
        confirmation_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["✅ Да, создать запись", "✏️ Исправить данные"],
            ["❌ Отменить"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_CONFIRM

@handle_errors_with_rate_limit
async def handle_admin_confirm(update: Update, context):
    """Подтверждение создания админской записи"""
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_confirm: '{text}'")
    
    unique_id = context.user_data.get('target_unique_id', 'Неизвестно')
    record_type = context.user_data.get('admin_record_type', 'Неизвестно')
    price = context.user_data.get('admin_price', 0)
    target_telegram_id = context.user_data.get('target_telegram_id')
    target_username = context.user_data.get('target_username', 'Неизвестный')
    admin_telegram_id = context.user_data.get('admin_telegram_id', 'Неизвестно')
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*👑 Шаг 3/4: Ввод стоимости*\n\n"
            "*📋 Правила ввода:*\n"
            "• Только цифры от 0 до 10 000 000\n"
            "• Для договорной стоимости можно указать 0\n\n"
            "*✏️ Введите стоимость:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_PRICE
    
    if text == "❌ Отменить":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "✏️ Исправить данные":
        await update.message.reply_text(
            "*👑 Шаг 2/4: Выбор типа записи*\n\n"
            f"*✅ Найден пользователь: @{target_username}*\n\n"
            f"*📋 Уникальный ID: {unique_id}*\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["📝 Договорная запись", "🎤 Запись в студии"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_RECORD_TYPE
    
    if text != "✅ Да, создать запись":
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Да, создать запись", "✏️ Исправить данные"],
                ["❌ Отменить"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_CONFIRM
    
    logger.info(f"🔍 Админ подтвердил создание записи: {unique_id}, тип: {record_type}, цена: {price}")
    
    try:
        if record_type == "📝 Договорная запись":
            service_name = f"Договорная запись (Админ)"
            date_str_for_db = "Не указана (договорная)"
            time_slot_for_db = "Не указано (договорная)"
            is_contractual = True
        else:
            service_name = f"Запись в студии (Админ)"
            date_str_for_db = "Запись в студии"
            time_slot_for_db = "Запись в студии"
            is_contractual = False
        
        booking_data = {
            'is_admin_booking': True,
            'target_telegram_id': target_telegram_id,
            'target_unique_id': unique_id,
            'name': f"Админская запись для {target_username}",
            'contact': f"ID: {unique_id}",
            'service': service_name,
            'date_str': date_str_for_db,
            'time_slot': time_slot_for_db,
            'price': str(price),
            'status': 'confirmed',
            'is_mixing': False,
            'is_track_creation': False,
            'is_12_hours': False,
            'with_engineer': False,
            'duration': 0,
            'start_hour': None,
            'end_hour': None,
            'is_contractual': is_contractual,
            'admin_record_type': record_type
        }
        
        success, booking_id = BookingManager.save_to_sheets(
            booking_data,
            user_id=target_telegram_id if target_telegram_id else 0,
            return_row_index=True
        )
        
        if not success:
            raise Exception("Не удалось сохранить запись в базу")
        
        logger.info(f"✅ Админская запись #{booking_id} сохранена в базу")
        
        # ===== НАЧИСЛЕНИЕ ПЛАСТИНОК ДЛЯ АДМИНСКОЙ ЗАПИСИ =====
        if target_telegram_id:
            booking_data_for_vinyls = {
                'id': booking_id,
                'is_admin_booking': True,
                'is_contractual': is_contractual,
                'status': 'confirmed',
                'date_str': date_str_for_db,
                'service': service_name
            }
            
            vinyls_added, new_vinyls = await AchievementSystem.add_vinyls_for_booking(
                str(target_telegram_id), context, booking_data_for_vinyls
            )
            
            if vinyls_added:
                logger.info(f"✅ Пользователю {target_telegram_id} начислено +25 пластинок за админскую запись #{booking_id}")
            
            await AchievementSystem.check_and_award_achievements(str(target_telegram_id), context, update)
        
        if target_telegram_id and price > 0:
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT total_spent FROM users WHERE telegram_id = ?', (str(target_telegram_id),))
                    user_data = cursor.fetchone()
                    
                    if user_data:
                        current_total = user_data[0] or 0
                        new_total = current_total + price
                        cursor.execute('UPDATE users SET total_spent = ? WHERE telegram_id = ?', (new_total, str(target_telegram_id)))
                        logger.info(f"💰 Обновлен total_spent для {target_telegram_id}: {current_total} -> {new_total}₽")
                    else:
                        registration_date = DateTimeUtils.now().strftime('%d.%m.%Y')
                        cursor.execute('''
                            INSERT INTO users (telegram_id, username, unique_id, registration_date, total_spent)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (str(target_telegram_id), target_username, unique_id, registration_date, price))
                        logger.info(f"💰 Создан новый пользователь {target_telegram_id} с total_spent: {price}₽")
                    conn.commit()
            except Exception as e:
                logger.error(f"❌ Ошибка обновления total_spent: {e}")
        
        # Очищаем тип записи от смайликов
        clean_record_type = record_type.replace('📝', '').replace('🎤', '').strip()
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ =====
        confirmation_lines = [
            f"*👑 Шаг 4/4: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Уникальный ID: {unique_id}",
            f"• Тип записи: {clean_record_type}",
            f"• Стоимость: {formatted_price}",
            "",
            f"*📝 Дополнительная информация:*",
            f"• Запись будет создана от имени администратора",
            f"• Пользователь увидит запись в своем профиле",
            "",
            "*👇 Всё верно?*"
        ]
        
        confirmation_text = "\n".join(confirmation_lines)
        
        await update.message.reply_text(
            confirmation_text,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Да, создать запись", "✏️ Исправить данные"],
                ["❌ Отменить"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_CONFIRM
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при создании админской записи: {e}")
        import traceback
        traceback.print_exc()
        
        await update.message.reply_text(
            "*❌ Произошла ошибка при создании записи!*\n\n"
            "*💡 Пожалуйста, попробуйте позже*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
    
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def pending_command(update: Update, context):
    """Команда /pending - показать все ожидающие записи (только для админов)"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этой команды!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text(
        "*🔍 Ищу ожидающие подтверждения записи...*",
        parse_mode="Markdown"
    )
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, timestamp, name, contact, service, date_str, time_slot, price,
                       is_mixing, mixing_type, is_track_creation, track_type,
                       is_12_hours, twelve_hours_type, with_engineer, duration,
                       telegram_id, level_discount_percent, promo_discount_percent, promo_code_used
                FROM bookings 
                WHERE status = 'pending'
                AND service NOT LIKE '%Админ%'
                AND service NOT LIKE '%админ%'
                ORDER BY timestamp ASC
            ''')
            
            pending_bookings = cursor.fetchall()
            
            if not pending_bookings:
                await update.message.reply_text(
                    "*✅ Нет ожидающих подтверждения заявок*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
                )
                return
            
            sent_count = 0
            for booking in pending_bookings:
                (booking_id, timestamp, name, contact, service, date_str, time_slot, price,
                 is_mixing, mixing_type, is_track_creation, track_type,
                 is_12_hours, twelve_hours_type, with_engineer, duration,
                 telegram_id, level_discount_percent, promo_discount_percent, promo_code_used) = booking
                
                display_date = date_str
                if date_str and '(' in date_str:
                    display_date = date_str.split('(')[0].strip()
                
                # ===== ИСПРАВЛЕНО: format_time_for_display() уже нормализует 24→00 =====
                display_time = time_slot
                if time_slot and '-' in time_slot:
                    display_time = DateTimeUtils.format_time_for_display(time_slot)
                
                # ===== ФОРМИРУЕМ ТЕКСТ СО СКИДКАМИ (БЕЗ ЛИШНИХ ПРОБЕЛОВ) =====
                discount_lines = []
                if level_discount_percent and level_discount_percent > 0:
                    discount_lines.append(f"🎟 Скидка по уровню: {level_discount_percent}%")
                if promo_discount_percent and promo_discount_percent > 0:
                    discount_lines.append(f"🎟 Промокод: {promo_discount_percent}%")
                if promo_code_used:
                    discount_lines.append(f"🎟 Код промокода: {promo_code_used}")
                
                discount_text = ""
                if discount_lines:
                    discount_text = "\n" + "\n".join(discount_lines)
                
                # Формируем сообщение в зависимости от типа услуги
                if is_12_hours:
                    try:
                        price_int = int(float(price)) if price else 0
                        rent_price_display = f"{price_int}₽ + залог"
                    except:
                        rent_price_display = f"{price}₽ + залог" if price else "0₽ + залог"
                    
                    message_text = (
                        f"🚨 Новая заявка! #{booking_id}\n\n"
                        f"👤 Пользователь: {name}\n"
                        f"📱 Контакт: {contact}\n"
                        f"🎧 Услуга: {service}\n"
                        f"⏰ Тип аренды: {twelve_hours_type}\n"
                        f"📅 Дата: {display_date}\n"
                        f"🕐 Время: {display_time} (12 часов)\n"
                        f"💰 Стоимость аренды: {rent_price_display}{discount_text}\n\n"
                        f"📅 Создана: {timestamp}\n\n"
                        f"*👇 Подтвердить или отклонить?*"
                    )
                    
                elif is_mixing:
                    mix_type = mixing_type if mixing_type else "Не указан"
                    try:
                        price_int = int(float(price)) if price else 0
                        price_text = "Договорная" if price_int == 0 else f"{price_int}₽"
                    except:
                        price_text = "Договорная" if "Договорная" in str(price) else f"{price}₽"
                    
                    message_text = (
                        f"🚨 Новая заявка! #{booking_id}\n\n"
                        f"👤 Пользователь: {name}\n"
                        f"📱 Контакт: {contact}\n"
                        f"🎧 Услуга: {service}\n"
                        f"🎚️ Тип работы: {mix_type}\n"
                        f"💰 Стоимость: {price_text}{discount_text}\n\n"
                        f"📅 Создана: {timestamp}\n\n"
                        f"*👇 Подтвердить или отклонить?*"
                    )
                    
                elif is_track_creation:
                    track_type_text = track_type if track_type else "Не указан"
                    try:
                        price_int = int(float(price)) if price else 0
                        price_text = "Договорная" if price_int == 0 else f"{price_int}₽"
                    except:
                        price_text = "Договорная" if "Договорная" in str(price) else f"{price}₽"
                    
                    message_text = f"🚨 Новая заявка! #{booking_id}\n\n"
                    message_text += f"👤 Пользователь: {name}\n"
                    message_text += f"📱 Контакт: {contact}\n"
                    message_text += f"🎧 Услуга: {service}\n"
                    message_text += f"🎵 Тип: {track_type_text}\n"
                    
                    if date_str and 'Не указана' not in date_str:
                        message_text += f"📅 Дата: {display_date}\n"
                    if time_slot and time_slot not in ['Не указано', 'Не указано (договорная)']:
                        message_text += f"⏰ Время: {display_time} (4 часа)\n"
                    
                    message_text += f"💰 Стоимость: {price_text}{discount_text}\n\n"
                    message_text += f"📅 Создана: {timestamp}\n\n"
                    message_text += f"*👇 Подтвердить или отклонить?*"
                    
                else:
                    duration_text = ""
                    if duration and duration > 0:
                        duration_text = f" ({PriceCalculator.format_hours_ru(duration)})"
                    
                    try:
                        price_int = int(float(price)) if price else 0
                        price_text = f"{price_int}₽" if price_int > 0 else "0₽"
                    except:
                        price_text = f"{price}₽"
                    
                    message_text = f"🚨 Новая заявка! #{booking_id}\n\n"
                    message_text += f"👤 Пользователь: {name}\n"
                    message_text += f"📱 Контакт: {contact}\n"
                    message_text += f"🎧 Услуга: {service}\n"
                    
                    if date_str and 'Не указана' not in date_str:
                        message_text += f"📅 Дата: {display_date}\n"
                    if time_slot and time_slot not in ['Не указано', 'Не указано (договорная)']:
                        message_text += f"⏰ Время: {display_time}{duration_text}\n"
                    if price and price != '0':
                        message_text += f"💰 Стоимость: {price_text}{discount_text}\n"
                    
                    message_text += f"\n📅 Создана: {timestamp}\n\n"
                    message_text += f"*👇 Подтвердить или отклонить?*"
                
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{booking_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{booking_id}")
                    ]
                ])
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                sent_count += 1
            
            await update.message.reply_text(
                f"*✅ Найдено и отправлено {sent_count} ожидающих заявок*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка в pending_command: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            f"❌ Ошибка при получении заявок: {str(e)}",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )

async def show_block_confirmation(update: Update, context):
    """Показать подтверждение блокировки/разблокировки"""
    
    username = context.user_data.get('target_block_username', 'Неизвестный')
    unique_id = context.user_data.get('target_block_unique_id', '')
    action = context.user_data.get('block_action')
    is_blocked = context.user_data.get('target_block_is_blocked', 0)
    
    logger.info(f"🔍 show_block_confirmation ВЫЗВАНА: action={action}, username={username}")
    
    if action == 'unblock':
        confirmation_text = (
            f"*👑 Шаг 3/3: Подтверждение*\n\n"
            f"*✅ Проверьте данные:*\n\n"
            f"*📋 Данные:*\n"
            f"• Пользователь: @{username}\n"
            f"• Уникальный ID: {unique_id}\n"
            f"• Действие: 🔓 Разблокировать\n\n"
            f"*👇 Всё верно?*"
        )
    elif action == 'block_permanent':
        # Если пользователь уже заблокирован - шаг 3/3, иначе 4/4
        if is_blocked == 1:
            confirmation_text = (
                f"*👑 Шаг 3/3: Подтверждение*\n\n"
                f"*✅ Проверьте данные:*\n\n"
                f"*📋 Данные:*\n"
                f"• Пользователь: @{username}\n"
                f"• Уникальный ID: {unique_id}\n"
                f"• Действие: 🔒 Заблокировать навсегда\n\n"
                f"*👇 Всё верно?*"
            )
        else:
            confirmation_text = (
                f"*👑 Шаг 3/3: Подтверждение*\n\n"
                f"*✅ Проверьте данные:*\n\n"
                f"*📋 Данные:*\n"
                f"• Пользователь: @{username}\n"
                f"• Уникальный ID: {unique_id}\n"
                f"• Действие: 🔒 Заблокировать навсегда\n\n"
                f"*👇 Всё верно?*"
            )
    else:
        duration_text = context.user_data.get('block_duration_text', 'указанное время')
        confirmation_text = (
            f"*👑 Шаг 4/4: Подтверждение*\n\n"
            f"*✅ Проверьте данные:*\n\n"
            f"*📋 Данные:*\n"
            f"• Пользователь: @{username}\n"
            f"• Уникальный ID: {unique_id}\n"
            f"• Действие: 🔒 Заблокировать на {duration_text}\n\n"
            f"*👇 Всё верно?*"
        )
    
    keyboard = ReplyKeyboardMarkup([
        ["✅ Да, подтвердить", "✏️ Исправить данные"],
        ["❌ Отменить"]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        confirmation_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    return ADMIN_BLOCK_CONFIRM

@handle_errors_with_rate_limit
async def handle_admin_block_start(update: Update, context):
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    context.user_data['is_admin_block'] = True
    context.user_data['_conversation_state'] = ADMIN_BLOCK_USER_ID
    
    await update.message.reply_text(
        "*👑 Шаг 1/4: Ввод имени пользователя*\n\n"
        "*📋 Варианты ввода:*\n"
        "• Уникальный ID (MC...): `MC1772377294899374`\n"
        "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
        "*💡 Где найти Уникальный ID:*\n"
        "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
        "*✏️ Введите данные:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_BLOCK_USER_ID

@handle_errors_with_rate_limit
async def handle_admin_block_user_id(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_block_user_id: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    search_term = text.replace('@', '').strip().lower()
    
    if not search_term:
        await update.message.reply_text(
            "❌ Введите корректные данные!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_BLOCK_USER_ID

    found_user = None
    search_method = ""

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # ===== 1. Поиск по уникальному ID (MC...) =====
            if search_term.startswith("mc"):
                logger.info(f"🔍 Ищем по уникальному ID: {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, is_blocked, blocked_until
                    FROM users WHERE LOWER(unique_id) = ?
                ''', (search_term,))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "уникальному ID"

            # ===== 2. Поиск по username (точное) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (точное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, is_blocked, blocked_until
                    FROM users WHERE LOWER(username) = ? OR LOWER(username) = ?
                ''', (search_term, f'@{search_term}'))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "username (точное)"

            # ===== 3. Поиск по username (частичное) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (частичное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, is_blocked, blocked_until
                    FROM users WHERE 
                    LOWER(username) LIKE ? OR 
                    LOWER(username) LIKE ? OR
                    LOWER(first_name) LIKE ? OR
                    LOWER(unique_id) LIKE ?
                ''', (f'%{search_term}%', f'%@{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "частичному совпадению"

            if not found_user:
                await update.message.reply_text(
                    f"*❌ Пользователь не найден!*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню"]
                    ], resize_keyboard=True)
                )
                return ADMIN_BLOCK_USER_ID

            (telegram_id, username, first_name, unique_id, 
             is_blocked, blocked_until) = found_user

            current_status = "🔓 Разблокирован"
            if is_blocked == 1:
                if blocked_until:
                    try:
                        blocked_time = datetime.strptime(blocked_until, '%Y-%m-%d %H:%M:%S')
                        now_moscow = to_moscow_time()
                        
                        if blocked_time > now_moscow:
                            time_left = blocked_time - now_moscow
                            days = time_left.days
                            hours = time_left.seconds // 3600
                            minutes = (time_left.seconds % 3600) // 60
                            
                            time_text = format_duration(days, hours, minutes)
                            
                            current_status = f"🔒 Заблокирован до {blocked_time.strftime('%d.%m.%Y %H:%M')} (осталось {time_text})"
                        else:
                            current_status = "🔓 Разблокирован (блокировка истекла)"
                    except Exception as e:
                        logger.error(f"Ошибка форматирования статуса: {e}")
                        current_status = "🔒 Заблокирован перманентно"
                else:
                    current_status = "🔒 Заблокирован перманентно"

            context.user_data['target_block_telegram_id'] = telegram_id
            context.user_data['target_block_username'] = username or first_name or "Неизвестный"
            context.user_data['target_block_unique_id'] = unique_id
            context.user_data['target_block_current_status'] = current_status
            context.user_data['target_block_is_blocked'] = is_blocked

            logger.info(f"✅ Админ нашел пользователя по {search_method}: {unique_id} (TG: {telegram_id})")

    except Exception as e:
        logger.error(f"❌ Ошибка поиска пользователя: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "❌ Ошибка при поиске пользователя!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_BLOCK_USER_ID

    # Формируем кнопки
    if is_blocked == 1:
        keyboard_buttons = [
            ["🔓 Разблокировать"],
            ["↩️ Главное меню", "↩️ Назад"]
        ]
        step_display = "2/3"
    else:
        keyboard_buttons = [
            ["🔒 Перманентно", "⏱ На время"],
            ["↩️ Главное меню", "↩️ Назад"]
        ]
        step_display = "2/4"

    await update.message.reply_text(
        f"*👑 Шаг {step_display}: Выбор действия*\n\n"
        f"*✅ Найден пользователь: @{context.user_data['target_block_username']}*\n"
        f"*📊 Текущий статус: {current_status}*\n\n"
        f"*📋 Уникальный ID: {unique_id}*\n\n"
        f"*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_BLOCK_TYPE

@handle_errors_with_rate_limit
async def handle_admin_block_type(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_block_type: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*👑 Шаг 1/4: Ввод имени пользователя*\n\n"
            "*📋 Варианты ввода:*\n"
            "• Уникальный ID (MC...): `MC1772377294899374`\n"
            "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
            "*💡 Где найти Уникальный ID:*\n"
            "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
            "*✏️ Введите данные:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_BLOCK_USER_ID
    
    valid_options = ["🔒 Перманентно", "⏱ На время", "🔓 Разблокировать"]
    
    username = context.user_data.get('target_block_username', 'Неизвестный')
    unique_id = context.user_data.get('target_block_unique_id', '')
    current_status = context.user_data.get('target_block_current_status', '🔓 Разблокирован')
    is_blocked = context.user_data.get('target_block_is_blocked', 0)
    
    # ОПРЕДЕЛЯЕМ НОМЕР ШАГА В ЗАВИСИМОСТИ ОТ СТАТУСА
    if is_blocked == 1:
        step_display = "2/3"
    else:
        step_display = "2/4"
    
    if text not in valid_options:
        if is_blocked == 1:
            keyboard_buttons = [
                ["🔓 Разблокировать"],
                ["↩️ Главное меню", "↩️ Назад"]
            ]
        else:
            keyboard_buttons = [
                ["🔒 Перманентно", "⏱ На время"],
                ["↩️ Главное меню", "↩️ Назад"]
            ]
        
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_BLOCK_TYPE
    
    if text == "🔓 Разблокировать":
        context.user_data['block_action'] = 'unblock'
        context.user_data['block_duration'] = None
        return await show_block_confirmation(update, context)
    
    elif text == "🔒 Перманентно":
        context.user_data['block_action'] = 'block_permanent'
        context.user_data['block_duration'] = 'permanent'
        return await show_block_confirmation(update, context)
    
    elif text == "⏱ На время":
        context.user_data['block_action'] = 'block_temporary'
        
        await update.message.reply_text(
            "*👑 Шаг 3/4: Ввод длительности*\n\n"
            "*📋 Форматы ввода:*\n"
            "• `24ч` — на 24 часа\n"
            "• `7д` — на 7 дней\n"
            "• `1мес` — на 1 месяц\n\n"
            "*✏️ Введите длительность:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_BLOCK_DURATION

@handle_errors_with_rate_limit
async def handle_admin_block_duration(update: Update, context):
    text = update.message.text.strip().lower()
    logger.info(f"🔍 handle_admin_block_duration: '{text}'")
    
    if text == "↩️ главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ назад":
        username = context.user_data.get('target_block_username', 'Неизвестный')
        unique_id = context.user_data.get('target_block_unique_id', '')
        current_status = context.user_data.get('target_block_current_status', '🔓 Разблокирован')
        is_blocked = context.user_data.get('target_block_is_blocked', 0)
        
        if is_blocked == 1:
            keyboard_buttons = [
                ["🔓 Разблокировать"],
                ["↩️ Главное меню", "↩️ Назад"]
            ]
        else:
            keyboard_buttons = [
                ["🔒 Перманентно", "⏱ На время"],
                ["↩️ Главное меню", "↩️ Назад"]
            ]
        
        await update.message.reply_text(
            f"*👑 Шаг 2/4: Выбор действия*\n\n"
            f"*✅ Найден пользователь: @{username}*\n"
            f"*📊 Текущий статус: {current_status}*\n\n"
            f"*📋 Уникальный ID: {unique_id}*\n\n"
            f"*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_BLOCK_TYPE
    
    import re
    
    hours = None
    days = None
    months = None
    
    match_hours = re.match(r'^(\d+)\s*ч$', text)
    if match_hours:
        hours = int(match_hours.group(1))
        if hours < 1 or hours > 8760:
            await update.message.reply_text(
                "*❌ Неверный формат!*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
            return ADMIN_BLOCK_DURATION
    
    match_days = re.match(r'^(\d+)\s*д$', text)
    if match_days:
        days = int(match_days.group(1))
        if days < 1 or days > 365:
            await update.message.reply_text(
                "*❌ Неверный формат!*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
            return ADMIN_BLOCK_DURATION
    
    match_months = re.match(r'^(\d+)\s*мес$', text)
    if match_months:
        months = int(match_months.group(1))
        if months < 1 or months > 12:
            await update.message.reply_text(
                "*❌ Неверный формат!*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
            return ADMIN_BLOCK_DURATION
    
    if not (hours or days or months):
        await update.message.reply_text(
            "*❌ Неверный формат!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True)
        )
        return ADMIN_BLOCK_DURATION
    
    if hours:
        context.user_data['block_duration_value'] = hours
        context.user_data['block_duration_unit'] = 'hours'
        context.user_data['block_duration_text'] = f"{hours} {get_hours_word(hours)}"
    elif days:
        context.user_data['block_duration_value'] = days
        context.user_data['block_duration_unit'] = 'days'
        context.user_data['block_duration_text'] = f"{days} {get_days_word(days)}"
    elif months:
        context.user_data['block_duration_value'] = months
        context.user_data['block_duration_unit'] = 'months'
        context.user_data['block_duration_text'] = f"{months} {get_months_word(months)}"
    
    return await show_block_confirmation(update, context)

@handle_errors_with_rate_limit
async def handle_admin_block_confirm(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_block_confirm: '{text}'")
    
    username = context.user_data.get('target_block_username')
    telegram_id = context.user_data.get('target_block_telegram_id')
    unique_id = context.user_data.get('target_block_unique_id')
    action = context.user_data.get('block_action')
    admin_username = update.effective_user.username or "Администратор"
    
    if text == "↩️ Главное меню" or text == "❌ Отменить":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "✏️ Исправить данные":
        is_blocked = context.user_data.get('target_block_is_blocked', 0)
        current_status = context.user_data.get('target_block_current_status', '🔓 Разблокирован')
        
        if is_blocked == 1:
            keyboard_buttons = [
                ["🔓 Разблокировать"],
                ["↩️ Главное меню", "↩️ Назад"]
            ]
            step_display = "2/3"
        else:
            keyboard_buttons = [
                ["🔒 Перманентно", "⏱ На время"],
                ["↩️ Главное меню", "↩️ Назад"]
            ]
            step_display = "2/4"
        
        await update.message.reply_text(
            f"*👑 Шаг {step_display}: Выбор действия*\n\n"
            f"*✅ Найден пользователь: @{username}*\n"
            f"*📊 Текущий статус: {current_status}*\n\n"
            f"*📋 Уникальный ID: {unique_id}*\n\n"
            f"*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_BLOCK_TYPE
    
    if text != "✅ Да, подтвердить":
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Да, подтвердить", "✏️ Исправить данные"],
                ["❌ Отменить"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_BLOCK_CONFIRM
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            now_moscow = to_moscow_time()
            blocked_until = None
            action_text = ""
            user_notification = ""
            admin_action_text = ""
            
            if action == 'unblock':
                cursor.execute('''
                    UPDATE users 
                    SET is_blocked = 0, blocked_until = NULL 
                    WHERE telegram_id = ?
                ''', (str(telegram_id),))
                
                action_text = "🔓 Разблокирован"
                admin_action_text = "разблокирован"
                user_notification = "*🔓 Вы были разблокированы*"
                
            elif action == 'block_permanent':
                cursor.execute('''
                    UPDATE users 
                    SET is_blocked = 1, blocked_until = NULL 
                    WHERE telegram_id = ?
                ''', (str(telegram_id),))
                
                action_text = "🔒 Заблокирован навсегда"
                admin_action_text = "заблокирован навсегда"
                user_notification = "*🔒 Вы были заблокированы навсегда*"
                
            else:
                duration_value = context.user_data.get('block_duration_value')
                duration_unit = context.user_data.get('block_duration_unit')
                
                if duration_unit == 'hours':
                    blocked_until = now_moscow + timedelta(hours=duration_value)
                    formatted_duration = f"{duration_value} {get_hours_word(duration_value)}"
                elif duration_unit == 'days':
                    blocked_until = now_moscow + timedelta(days=duration_value)
                    formatted_duration = f"{duration_value} {get_days_word(duration_value)}"
                elif duration_unit == 'months':
                    blocked_until = now_moscow + timedelta(days=30 * duration_value)
                    formatted_duration = f"{duration_value} {get_months_word(duration_value)}"
                else:
                    formatted_duration = f"{duration_value} {duration_unit}"
                
                blocked_until_str = blocked_until.strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                    UPDATE users 
                    SET is_blocked = 1, blocked_until = ? 
                    WHERE telegram_id = ?
                ''', (blocked_until_str, str(telegram_id)))
                
                action_text = f"🔒 Заблокирован на {formatted_duration}"
                admin_action_text = f"заблокирован на {formatted_duration}"
                user_notification = f"*🔒 Вы были заблокированы на {formatted_duration}*"
                
                if blocked_until:
                    display_time = blocked_until.strftime('%d.%m.%Y %H:%M')
                    user_notification += f"\n*📅 Срок действия до: {display_time}*"
            
            conn.commit()
        
        # ОТПРАВКА СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЮ
        try:
            user_message = (
                f"{user_notification}\n\n"
                f"*👤 Ваш профиль: @{username}*\n"
                f"*📋 Уникальный ID: {unique_id}*\n\n"
                f"*📞 По вопросам обращайтесь к администратору: @mothman32*"
            )
            
            await context.bot.send_message(
                chat_id=int(telegram_id),
                text=user_message,
                parse_mode="Markdown"
            )
            logger.info(f"✅ Уведомление отправлено пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление пользователю: {e}")
        
        # ИЗМЕНЕННОЕ СООБЩЕНИЕ ДЛЯ АДМИНИСТРАТОРА
        # Стало
        if action == 'unblock':
            admin_message = f"*✅ Пользователь @{username} разблокирован*"
        else:
            admin_message = f"*✅ Пользователь @{username} заблокирован*"
        
        await update.message.reply_text(
            admin_message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        
        logger.info(f"👑 Админ @{admin_username} {action_text} пользователя @{username}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении действия: {e}")
        import traceback
        traceback.print_exc()
        
        await update.message.reply_text(
            f"❌ Ошибка при выполнении действия!\n\n"
            f"💡 Попробуйте еще раз или свяжитесь с разработчиком",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
    
    context.user_data.clear()
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def error_callback(update: Update, context):
    if update and update.message:
        try:
            await update.message.reply_text(
                "⚠️ Упс! Что-то пошло не так\n\n"
                "✨ Пожалуйста, вернитесь в главное меню и попробуйте снова",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
                parse_mode="Markdown"
            )
        except:
            pass


async def handle_back_to_previous_step(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    logger.info(f"🔍 handle_back_to_previous_step вызван")
    
    service = context.user_data.get('service', '')
    is_track_creation = context.user_data.get('is_track_creation', False)
    is_12_hours = context.user_data.get('is_12_hours', False)
    is_mixing = context.user_data.get('is_mixing', False)
    
    logger.info(f"🔍 ОБЫЧНАЯ запись: handle_back_to_previous_step")
    logger.info(f"   service: {service}, is_track_creation: {is_track_creation}")
    logger.info(f"   is_12_hours: {is_12_hours}, is_mixing: {is_mixing}")
    
    if is_track_creation:
        await update.message.reply_text(
            "*🎵 Шаг 4/7: Выбор формата*\n\n"
            "*✨ Что Вам требуется создать?*\n\n"
            "*Трек — 9000₽*\n"
            "• Работа с инженером звукозаписи\n"
            "• Создание трека с нуля\n"
            "• Профессиональный подход\n\n"
            "*Альбом — договорная*\n"
            "• Обсуждение работы\n"
            "• Индивидуальный подход\n"
            "• Специальные условия\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_track_creation_options()
        )
        return TRACK_CREATION_TYPE
        
    elif is_12_hours:
        await update.message.reply_text(
            "*⏰ Шаг 4/6: Выбор формата*\n\n"
            "*✨ Когда для Вас забронировать студию?*\n\n"
            "*День — 7000₽ + залог (по договору)*\n"  
            "• Работа с 9:00 до 21:00\n"
            "• Полный контроль студии\n\n"
            "*Ночь — 6500₽ + залог (по договору)*\n"
            "• Работа с 21:00 до 9:00\n"
            "• Специальная ночная цена\n\n"
            "*👇 Выберите подходящий вариант:*", 
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_12_hours_options()
        )
        return TWELVE_HOURS_OPTION
        
    elif is_mixing:
        await update.message.reply_text(
            "*🎚️ Шаг 4/5: Выбор сведения*\n\n",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_mixing()
        )
        return MIXING_TYPE
        
    elif service == "🎤 Запись вокала" or service == "🎸 Запись инструментов":
        await update.message.reply_text(
            "*👨‍🔧 Шаг 4/7: Выбор формата*\n\n"
            "*✨ Вам требуется помощь звукорежиссера?*\n\n"
            "*С инженером — рекомендуем:*\n"
            "• Профессиональная настройка оборудования\n"
            "• Помощь в процессе записи\n"
            "• Консультации по исполнению\n\n"
            "*Без инженера — для опытных:*\n"
            "• Самостоятельная работа в студии\n"
            "• Экономия 200₽ в час\n"
            "• Полный творческий контроль\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_engineer_options()
        )
        return ENGINEER_OPTION
        
    else:
        await update.message.reply_text(
            "*🎧 Шаг 3/7: Выбор услуги*\n\n"
            "*✨ Какая услуга Вас интересует?*\n\n"
            "*Вы можете выбрать:*\n"
            "• Запись вокала — профессиональная запись\n"
            "• Запись инструментов — электро-гитара, акустическая гитара\n"
            "• 12-часовая аренда — полный доступ к студии\n"
            "• Сведение/мастеринг — доведение до идеала\n"
            "• Создание трека — создание трека с нуля\n"
            "• Аранжировка/Биты — готовые решения\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_services()
        )
        return SERVICE


async def handle_edit_data(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    name = context.user_data.get('name', '')
    safe_name = context.user_data.get('safe_name', '')
    contact = context.user_data.get('contact', '')
    safe_contact = context.user_data.get('safe_contact', '')
    
    context.user_data.clear()
    
    if name:
        context.user_data['name'] = name
        context.user_data['safe_name'] = safe_name
    if contact:
        context.user_data['contact'] = contact
        context.user_data['safe_contact'] = safe_contact
    
    await update.message.reply_text(
        "*🎧 Шаг 3/7: Выбор услуги*\n\n"
        "*✨ Какая услуга Вас интересует?*\n\n"
        "*Вы можете выбрать:*\n"
        "• Запись вокала — профессиональная запись\n"
        "• Запись инструментов — электро-гитара, акустическая гитара\n"
        "• 12-часовая аренда — полный доступ к студии\n"
        "• Сведение/мастеринг — доведение до идеала\n"
        "• Создание трека — создание трека с нуля\n"
        "• Аранжировка/Биты — готовые решения\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=KeyboardManager.get_services()
    )
    return SERVICE


async def handle_cancel_booking(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    await update.message.reply_text(
        "*🏠 Возвращаемся в главное меню*\n\n"
        "*✨ Процесс записи завершён*\n"
        "*💾 Все введённые данные очищены*\n\n"
        "*👇 Выберите подходящий вариант:*",
        reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
        parse_mode="Markdown"
    )
    
    context.user_data.clear()
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def show_slots(update: Update, context):
    """Показывает доступные слоты и применяет промокод (БЕЗ списания купона)"""
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    logger.info(f"🔍 show_slots ВЫЗВАН!")
    logger.info(f"🔍 Текст: {update.message.text}")
    
    user_input = update.message.text.strip()
    user_id = str(update.effective_user.id)
    
    logger.info("=" * 60)
    logger.info("SHOW_SLOTS - НАЧАЛО")
    logger.info(f"Ввод пользователя: {user_input}")
    
    if user_input == "↩️ Назад":
        logger.info(f"Пользователь нажал 'Назад' в SHOW_SLOTS")
        
        is_track_creation = context.user_data.get('is_track_creation', False)
        is_12_hours = context.user_data.get('is_12_hours', False)
        with_engineer = context.user_data.get('with_engineer', False)
        
        if is_track_creation:
            await update.message.reply_text(
                "*📅 Шаг 5/7: Выбор даты*\n\n"
                "*✨ Когда для Вас забронировать студию?*\n\n"
                "*Правила для создания трека:*\n"
                "• Запись минимально за 72 часа\n"
                "• От 4 часов работы в студии\n"
                "• Обязательно с инженером звукозаписи\n\n"
                "*Легенда цветов:*\n"
                "🟢 — Есть 4-часовые слоты\n"
                "🟠 — Есть 4-часовые слоты только через полночь\n"
                "🔴 — Нет 4-часовых слотов\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("track_creation", True)
            )
            return DATE
            
        elif is_12_hours:
            service_type = "12_hours_day" if context.user_data.get('12_hours_type', '').startswith('День') else "12_hours_night"
            await update.message.reply_text(
                "*📅 Шаг 5/6: Выбор даты*\n\n"
                "*✨ Когда для Вас забронировать студию?*\n\n"
                "*Правила для аренды студии:*\n"
                "• Аренда минимально за 72 часа\n"
                "• Ровно 12 часов работы в студии\n"
                "• Без инженера звукозаписи\n\n"
                "*Легенда цветов:*\n"
                "🟢 — Слот доступен для бронирования\n"
                "🔴 — Слот недоступен для бронирования\n\n"
                "*👇 Выберите подходящий вариант:*", 
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates(service_type, False)
            )
            return DATE
            
        else:
            if with_engineer:
                await update.message.reply_text(
                    "*📅 Шаг 5/7: Выбор даты*\n\n"
                    "*✨ Когда планируете запись?*\n\n"
                    "*Правила для работы с инженером:*\n"
                    "• Запись минимально за 48 часов\n\n"
                    "*Легенда цветов:*\n"
                    "🟢 — Свободно более 18 часов \n"
                    "🟡 — Свободно более 12 часов\n"
                    "🟠 — Свободно более 6 часов\n"
                    "🔴 — Свободно менее 6 часов\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_dates("vocal", True)
                )
            else:
                await update.message.reply_text(
                    "*📅 Шаг 5/7: Выбор даты*\n\n"
                    "*✨ Когда планируете запись?*\n\n"
                    "*Правила для работы без инженера:*\n"
                    "• Запись минимально за 24 часа\n\n"
                    "*Легенда цветов:*\n"
                    "🟢 — Свободно более 18 часов \n"
                    "🟡 — Свободно более 12 часов\n"
                    "🟠 — Свободно более 6 часов\n"
                    "🔴 — Свободно менее 6 часов\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_dates("vocal", False)
                )
            return DATE
    
    if user_input == "↩️ Главное меню":
        return await handle_main_menu_button(update, context)
    
    # ===== ПРОВЕРКА: ЕСЛИ УЖЕ ПОКАЗАНО ПОДТВЕРЖДЕНИЕ =====
    if context.user_data.get('_conversation_state') == CONFIRM:
        keyboard = KeyboardManager.get_confirmation()
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return CONFIRM
    
    # ===== УСТАНАВЛИВАЕМ СОСТОЯНИЕ =====
    context.user_data['_conversation_state'] = SHOW_SLOTS
    
    # ===== ПРОВЕРКА НА 24 =====
    if user_input.startswith('24') or '-24' in user_input:
        await update.message.reply_text(
            "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_time_input()
        )
        return SHOW_SLOTS
    
    # ===== ДЛЯ 12-ЧАСОВОЙ АРЕНДЫ (НЕ ЖДЁМ ВВОД ВРЕМЕНИ) =====
    is_12_hours = context.user_data.get('is_12_hours', False)
    
    if is_12_hours:
        logger.info(f"🔍 12-часовая аренда, переходим к подтверждению")
        
        selected_date = context.user_data.get('date', '')
        time_slot = context.user_data.get('time', '9-21')
        
        if not time_slot or time_slot == 'Не указано':
            twelve_hours_type = context.user_data.get('12_hours_type', 'День')
            if 'Ночь' in twelve_hours_type or 'ночь' in twelve_hours_type.lower():
                time_slot = '21-9'
            else:
                time_slot = '9-21'
            context.user_data['time'] = time_slot
        
        display_time = DateTimeUtils.format_time_for_display(time_slot)
        context.user_data['display_time'] = display_time
        
        if '-' in time_slot:
            parts = time_slot.split('-')
            context.user_data['start_hour'] = int(parts[0].strip())
            context.user_data['end_hour'] = int(parts[1].strip())
        
        context.user_data['duration'] = 12
        
        price_result = PriceCalculator.calculate(
            service=context.user_data['service'],
            duration=12,
            is_12_hours=True,
            twelve_hours_type=context.user_data.get('12_hours_type'),
            user_id=user_id,
            consume_coupon=False
        )
        context.user_data['price_result'] = price_result
        context.user_data['price'] = price_result['final_price']
        
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        display_date = context.user_data.get('date_with_color', context.user_data['date'])
        
        # ===== ОЧИЩАЕМ УСЛУГУ ОТ СМАЙЛИКОВ =====
        clean_service = clean_service_text(context.user_data['service'])
        
        # ===== ОЧИЩАЕМ ДАТУ ОТ СМАЙЛИКОВ =====
        clean_date_display = display_date
        if clean_date_display:
            for emoji in ['🟢', '🟡', '🟠', '🔴', '⚪️']:
                clean_date_display = clean_date_display.replace(emoji, '').strip()
            if '(' in clean_date_display:
                clean_date_display = clean_date_display.split('(')[0].strip()
        
        # ===== ОЧИЩАЕМ ТИП ОТ СМАЙЛИКОВ =====
        clean_type = ""
        twelve_hours_type_raw = context.user_data.get('12_hours_type', 'Не указан')
        clean_type = clean_service_text(twelve_hours_type_raw)
        
        # ===== ФОРМИРУЕМ ТЕКСТ О СКИДКАХ =====
        discount_text = ""
        if price_result.get('level_discount_percent', 0) > 0:
            discount_text += f"\n• Скидка по уровню: {price_result['level_discount_percent']}%"
        if price_result.get('promo_discount_percent', 0) > 0:
            discount_text += f"\n• Промокод: {price_result['promo_discount_percent']}%"
        if price_result.get('free_hours_applied', 0) > 0:
            free_hours = price_result['free_hours_applied']
            if free_hours == 1:
                hours_text = "бесплатный час"
            elif free_hours in [2, 3, 4]:
                hours_text = f"{free_hours} бесплатных часа"
            else:
                hours_text = f"{free_hours} бесплатных часов"
            discount_text += f"\n• Промокод: {hours_text}"
        if price_result.get('free_service_applied', False):
            discount_text += f"\n• Промокод: Бесплатная услуга"
        
        # ===== Цена для аренды (итоговая со скидкой) =====
        rent_price = 6500 if context.user_data.get('12_hours_type') and 'Ночь' in context.user_data.get('12_hours_type') else 7000
        final_price = price_result.get('final_price', rent_price)
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ (БЕЗ СМАЙЛИКОВ В УСЛУГЕ И ДАТЕ) =====
        confirmation_lines = [
            f"*✅ Шаг 6/6: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}",
            f"• Тип: {clean_type}",
            f"• Дата: {clean_date_display}",
            f"• Время: {display_time} (12 часов)",
            f"• Стоимость: {final_price}₽ + залог (по договору)"
        ]
        
        if discount_text:
            confirmation_lines.append(discount_text.lstrip('\n'))
        
        confirmation_lines.append("")
        confirmation_lines.append("*👇 Выберите подходящий вариант:*")
        
        confirmation_text = "\n".join(confirmation_lines)
        
        context.user_data['_conversation_state'] = CONFIRM
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM
    
    # ===== НОРМАЛИЗУЕМ ВВОД ВРЕМЕНИ =====
    normalized_input = DateTimeUtils.normalize_time_input(user_input)
    logger.info(f"Нормализованный ввод: {normalized_input}")
    
    is_track_creation = context.user_data.get('is_track_creation', False)
    with_engineer = context.user_data.get('with_engineer', False)
    is_mixing = context.user_data.get('is_mixing', False)
    
    free_intervals = context.user_data.get('free_intervals', [])
    free_interval = context.user_data.get('free_interval')
    suitable_intervals = context.user_data.get('suitable_intervals', [])
    
    logger.info(f"is_track_creation: {is_track_creation}")
    logger.info(f"with_engineer: {with_engineer}")
    logger.info(f"is_mixing: {is_mixing}")
    
    # ===== ДЛЯ ТРЕКА =====
    if is_track_creation:
        if '-' not in normalized_input:
            await update.message.reply_text(
                "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_time_input()
            )
            return SHOW_SLOTS
        
        try:
            start_hour_str, end_hour_str = normalized_input.split('-')
            start_hour = int(start_hour_str.strip())
            end_hour = int(end_hour_str.strip())
        except ValueError:
            await update.message.reply_text(
                "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_time_input()
            )
            return SHOW_SLOTS
        
        if end_hour > start_hour:
            duration = end_hour - start_hour
        elif end_hour < start_hour:
            duration = (24 - start_hour) + end_hour
        else:
            duration = 0
        
        logger.info(f"🔍 Проверка трека: {normalized_input}, duration={duration}")
        
        selected_date = context.user_data['date']
        display_time = DateTimeUtils.format_time_for_display(normalized_input)
        booking_datetime = DateTimeUtils.get_booking_datetime(selected_date, display_time)
        
        if booking_datetime:
            can_book, min_hours = DateTimeUtils.can_book_in_advance(
                booking_datetime, 
                start_hour, 
                True,
                is_12_hours=False, 
                is_track_creation=True
            )
            
            if not can_book:
                await update.message.reply_text(
                    "*❌ Время должно начинаться в доступном интервале! Выберите время из предложенных свободных слотов!*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_time_input()
                )
                return SHOW_SLOTS
        
        if duration != 4:
            await update.message.reply_text(
                "*❌ Для создания трека требуется ровно 4 часа! Выберите длительность 4 часа!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_time_input()
            )
            return SHOW_SLOTS
        
        # ================================================================
        # ===== НОВАЯ ПРОВЕРКА ДОСТУПНОСТИ ДЛЯ ТРЕКА =====
        # ================================================================
        is_available = BookingManager.check_time_slot_available(
            selected_date, 
            normalized_input, 
            "track_creation"
        )
        
        if not is_available:
            await update.message.reply_text(
                "*❌ Этот слот занят! Выберите другое время из предложенных свободных слотов!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_time_input()
            )
            return SHOW_SLOTS
        
        # ================================================================
        # ===== ПРОВЕРКА ЧЕРЕЗ SUITABLE_INTERVALS =====
        # ================================================================
        is_in_any_interval = False
        
        for interval in suitable_intervals:
            if interval['duration'] >= 4:
                if interval['start'] <= start_hour and end_hour <= interval['end']:
                    is_in_any_interval = True
                    break
                elif interval['end'] == 24 and start_hour >= interval['start']:
                    hours_before_midnight = 24 - start_hour
                    if hours_before_midnight <= 4:
                        is_in_any_interval = True
                        break
            else:
                if interval['end'] == 24 and start_hour >= interval['start']:
                    hours_before_midnight = 24 - start_hour
                    hours_after_midnight = end_hour
                    total_hours = hours_before_midnight + hours_after_midnight
                    
                    if total_hours == 4:
                        is_in_any_interval = True
                        break
        
        if not is_in_any_interval:
            await update.message.reply_text(
                "*❌ Время должно начинаться в доступном интервале! Выберите время из предложенных свободных слотов!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_time_input()
            )
            return SHOW_SLOTS
        
        # ===== СОХРАНЯЕМ ДАННЫЕ И ПЕРЕХОДИМ К ПОДТВЕРЖДЕНИЮ =====
        context.user_data['time'] = normalized_input
        context.user_data['display_time'] = DateTimeUtils.format_time_for_display(normalized_input)
        context.user_data['start_hour'] = start_hour
        context.user_data['end_hour'] = end_hour
        context.user_data['duration'] = 4
        
        price_result = PriceCalculator.calculate(
            service=context.user_data['service'],
            duration=4,
            is_mixing=False,
            mixing_type=None,
            is_12_hours=False,
            is_track_creation=True,
            track_type=context.user_data.get('track_type'),
            twelve_hours_type=None,
            start_hour=start_hour,
            end_hour=end_hour,
            with_engineer=True,
            user_id=user_id,
            consume_coupon=False
        )
        
        context.user_data['price_result'] = price_result
        context.user_data['price'] = price_result['final_price']
        
        logger.info(f"✅ Трек: время подтверждено, переходим к показу подтверждения")
        
        # Переходим к подтверждению
        safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
        safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
        display_date = context.user_data.get('date_with_color', context.user_data['date'])
        display_time = context.user_data.get('display_time', context.user_data['time'])
        
        # ===== ОЧИЩАЕМ УСЛУГУ ОТ СМАЙЛИКОВ =====
        clean_service = clean_service_text(context.user_data['service'])
        
        # ===== ОЧИЩАЕМ ДАТУ ОТ СМАЙЛИКОВ =====
        clean_date_display = display_date
        if clean_date_display:
            for emoji in ['🟢', '🟡', '🟠', '🔴', '⚪️']:
                clean_date_display = clean_date_display.replace(emoji, '').strip()
            if '(' in clean_date_display:
                clean_date_display = clean_date_display.split('(')[0].strip()
        
        # ===== ОЧИЩАЕМ ТИП ОТ СМАЙЛИКОВ =====
        clean_type = ""
        track_type_raw = context.user_data.get('track_type', 'Один трек')
        clean_type = clean_service_text(track_type_raw)
        
        # ===== ФОРМИРУЕМ ТЕКСТ О СКИДКАХ =====
        discount_text = ""
        if price_result.get('level_discount_percent', 0) > 0:
            discount_text += f"\n• Скидка по уровню: {price_result['level_discount_percent']}%"
        if price_result.get('promo_discount_percent', 0) > 0:
            discount_text += f"\n• Промокод: {price_result['promo_discount_percent']}%"
        if price_result.get('free_hours_applied', 0) > 0:
            free_hours = price_result['free_hours_applied']
            if free_hours == 1:
                hours_text = "бесплатный час"
            elif free_hours in [2, 3, 4]:
                hours_text = f"{free_hours} бесплатных часа"
            else:
                hours_text = f"{free_hours} бесплатных часов"
            discount_text += f"\n• Промокод: {hours_text}"
        if price_result.get('free_service_applied', False):
            discount_text += f"\n• Промокод: Бесплатная услуга"
        
        # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ (БЕЗ СМАЙЛИКОВ В УСЛУГЕ И ДАТЕ) =====
        confirmation_lines = [
            f"*✅ Шаг 7/7: Подтверждение*",
            "",
            f"*✨ Проверьте правильность Ваших данных:*",
            "",
            f"• Имя: {safe_name}",
            f"• Контакт: {safe_contact}",
            f"• Услуга: {clean_service}",
            f"• Тип: {clean_type}",
            f"• Дата: {clean_date_display}",
            f"• Время: {display_time} (4 часа)",
            f"• Стоимость: {price_result['final_price']}₽"
        ]
        
        if discount_text:
            confirmation_lines.append(discount_text.lstrip('\n'))
        
        confirmation_lines.append("")
        confirmation_lines.append("*👇 Выберите подходящий вариант:*")
        
        confirmation_text = "\n".join(confirmation_lines)
        
        context.user_data['_conversation_state'] = CONFIRM
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=KeyboardManager.get_confirmation(),
            parse_mode="Markdown"
        )
        return CONFIRM
    
    # ===== ДЛЯ ВОКАЛА И ИНСТРУМЕНТА =====
    if not is_mixing:
        is_valid, error_msg = DateTimeUtils.is_valid_booking_time(
            normalized_input, with_engineer, is_12_hours=False, is_track_creation=False
        )
        
        if not is_valid:
            if "Максимальное время" in error_msg:
                await update.message.reply_text(
                    "*❌ Максимальное время записи — 6 часов! Выберите длительность от 1 до 6 часов!*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_time_input()
                )
                return SHOW_SLOTS
            elif "Минимальное время" in error_msg or "минимально" in error_msg.lower():
                await update.message.reply_text(
                    "*❌ Минимальное время записи — 1 час! Выберите длительность от 1 до 6 часов!*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_time_input()
                )
                return SHOW_SLOTS
            elif "Неверный формат" in error_msg:
                await update.message.reply_text(
                    "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_time_input()
                )
                return SHOW_SLOTS
            else:
                await update.message.reply_text(
                    "*❌ Неверный формат времени! Используйте формат час-час, например: 14-18 или 22-2!*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_time_input()
                )
                return SHOW_SLOTS
        
        is_in_any_interval = False
        interval_error = ""
        suitable_interval = None
        
        if free_intervals and not is_mixing:
            for interval in free_intervals:
                is_in_interval, error = FreeIntervalCalculator.is_time_in_interval(
                    normalized_input, interval, is_track_creation
                )
                
                if is_in_interval:
                    is_in_any_interval = True
                    suitable_interval = interval
                    break
                else:
                    interval_error = error
        elif free_interval and not is_mixing:
            is_in_any_interval, interval_error = FreeIntervalCalculator.is_time_in_interval(
                normalized_input, free_interval, is_track_creation
            )
            suitable_interval = free_interval
        elif is_mixing:
            is_in_any_interval = True
        
        if not is_in_any_interval:
            await update.message.reply_text(
                "*❌ Время должно начинаться в доступном интервале! Выберите время из предложенных свободных слотов!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_time_input()
            )
            return SHOW_SLOTS
    
    # ===== ОБЩАЯ ЧАСТЬ ДЛЯ ВОКАЛА/ИНСТРУМЕНТА (ПРОВЕРКА ДОСТУПНОСТИ) =====
    selected_date = context.user_data['date']
    service_type = "vocal"
    
    logger.info(f"Проверка доступности: дата={selected_date}, время={normalized_input}, тип={service_type}")
    
    if not BookingManager.check_time_slot_available(selected_date, normalized_input, service_type):
        display_time = DateTimeUtils.format_time_for_display(normalized_input)
        logger.info(f"Слот НЕ доступен: {display_time}")
        
        await update.message.reply_text(
            "*❌ Время должно начинаться в доступном интервале! Выберите время из предложенных свободных слотов!*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_time_input()
        )
        return SHOW_SLOTS
    
    start_hour_str, end_hour_str = map(str.strip, normalized_input.split('-'))
    start_hour = int(start_hour_str.strip())
    end_hour = int(end_hour_str.strip())
    
    display_time = DateTimeUtils.format_time_for_display(normalized_input)
    logger.info(f"Отображаемое время: {display_time}")
    
    start_datetime = DateTimeUtils.get_booking_datetime(selected_date, display_time)
    logger.info(f"start_datetime: {start_datetime}")
    
    if start_datetime and not is_mixing:
        can_book, min_hours = DateTimeUtils.can_book_in_advance(
            start_datetime, start_hour, with_engineer, 
            is_12_hours=False, is_track_creation=is_track_creation
        )
        
        if not can_book:
            await update.message.reply_text(
                "*❌ Время должно начинаться в доступном интервале! Выберите время из предложенных свободных слотов!*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_time_input()
            )
            return SHOW_SLOTS
    
    # ===== СОХРАНЯЕМ ДАННЫЕ ДЛЯ ВОКАЛА/ИНСТРУМЕНТА =====
    context.user_data['time'] = normalized_input
    context.user_data['display_time'] = DateTimeUtils.format_time_for_display(normalized_input)
    context.user_data['start_hour'] = start_hour
    context.user_data['end_hour'] = end_hour
    
    duration = DateTimeUtils.calculate_duration(start_hour, end_hour)
    context.user_data['duration'] = duration
    
    price_result = PriceCalculator.calculate(
        service=context.user_data['service'],
        duration=duration,
        is_mixing=False,
        mixing_type=None,
        is_12_hours=False,
        is_track_creation=False,
        track_type=None,
        twelve_hours_type=None,
        start_hour=start_hour,
        end_hour=end_hour,
        with_engineer=with_engineer,
        user_id=user_id,
        consume_coupon=False
    )
    
    context.user_data['price_result'] = price_result
    context.user_data['price'] = price_result['final_price']
    
    logger.info(f"Длительность: {duration}")
    logger.info(f"Базовая цена: {price_result['base_price']}")
    logger.info(f"Скидка уровня: {price_result['level_discount_percent']}%")
    logger.info(f"Скидка промокода: {price_result['promo_discount_percent']}%")
    logger.info(f"Бесплатных часов: {price_result.get('free_hours_applied', 0)}")
    logger.info(f"Итоговая цена: {price_result['final_price']}")
    
    safe_name = context.user_data.get('safe_name', context.user_data.get('name', ''))
    safe_contact = context.user_data.get('safe_contact', context.user_data.get('contact', ''))
    display_date = context.user_data.get('date_with_color', context.user_data['date'])
    display_time = context.user_data.get('display_time', context.user_data['time'])
    
    # ===== ОЧИЩАЕМ УСЛУГУ ОТ СМАЙЛИКОВ =====
    clean_service = clean_service_text(context.user_data['service'])
    
    # ===== ОЧИЩАЕМ ДАТУ ОТ СМАЙЛИКОВ =====
    clean_date_display = display_date
    if clean_date_display:
        for emoji in ['🟢', '🟡', '🟠', '🔴', '⚪️']:
            clean_date_display = clean_date_display.replace(emoji, '').strip()
        if '(' in clean_date_display:
            clean_date_display = clean_date_display.split('(')[0].strip()
    
    # ===== ОЧИЩАЕМ ТИП ОТ СМАЙЛИКОВ =====
    clean_type = ""
    if is_track_creation and context.user_data.get('track_type'):
        track_type_raw = context.user_data.get('track_type')
        clean_type = clean_service_text(track_type_raw)
    elif is_mixing and context.user_data.get('mixing_type'):
        mixing_type_raw = context.user_data.get('mixing_type')
        clean_type = clean_service_text(mixing_type_raw)
    elif is_12_hours and context.user_data.get('12_hours_type'):
        twelve_hours_type_raw = context.user_data.get('12_hours_type')
        clean_type = clean_service_text(twelve_hours_type_raw)
    
    # ===== ФОРМИРУЕМ ТЕКСТ О СКИДКАХ =====
    discount_text = ""
    
    if price_result.get('level_discount_percent', 0) > 0:
        discount_text += f"\n• Скидка по уровню: {price_result['level_discount_percent']}%"
    
    if price_result.get('promo_discount_percent', 0) > 0:
        discount_text += f"\n• Промокод: {price_result['promo_discount_percent']}%"
    
    if price_result.get('free_hours_applied', 0) > 0:
        free_hours = price_result['free_hours_applied']
        if free_hours == 1:
            hours_text = "бесплатный час"
        elif free_hours in [2, 3, 4]:
            hours_text = f"{free_hours} бесплатных часа"
        else:
            hours_text = f"{free_hours} бесплатных часов"
        discount_text += f"\n• Промокод: {hours_text}"
    
    if price_result.get('free_service_applied', False):
        discount_text += f"\n• Промокод: Бесплатная услуга"
    
    # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ =====
    # Определяем шаг
    if is_mixing:
        step_text = "Шаг 5/5"
    elif is_track_creation:
        step_text = "Шаг 7/7"
    else:
        step_text = "Шаг 7/7"
    
    # Формируем цену
    if price_result['final_price'] == "Договорная" or price_result.get('is_contractual'):
        price_text = "Договорная"
    elif price_result.get('free_service_applied', False):
        price_text = "0₽ (Бесплатная услуга)"
    elif price_result['final_price'] == 0:
        price_text = "0₽"
    else:
        price_text = f"{price_result['final_price']}₽"
    
    # Формируем время
    if is_12_hours:
        time_text = f"{display_time} (12 часов)"
    elif is_track_creation:
        time_text = f"{display_time} (4 часа)"
    elif duration and duration > 0:
        formatted_duration = PriceCalculator.format_hours_ru(duration)
        time_text = f"{display_time} ({formatted_duration})"
    else:
        time_text = display_time
    
    # ===== НОВЫЙ ФОРМАТ ПОДТВЕРЖДЕНИЯ (БЕЗ СМАЙЛИКОВ В УСЛУГЕ И ДАТЕ) =====
    confirmation_lines = [
        f"*✅ {step_text}: Подтверждение*",
        "",
        f"*✨ Проверьте правильность Ваших данных:*",
        "",
        f"• Имя: {safe_name}",
        f"• Контакт: {safe_contact}",
        f"• Услуга: {clean_service}"
    ]
    
    # Добавляем дополнительную информацию в зависимости от услуги (без смайликов)
    if clean_type:
        confirmation_lines.append(f"• Тип: {clean_type}")
    
    confirmation_lines.append(f"• Дата: {clean_date_display}")
    confirmation_lines.append(f"• Время: {time_text}")
    confirmation_lines.append(f"• Стоимость: {price_text}")
    
    if discount_text:
        confirmation_lines.append(discount_text.lstrip('\n'))
    
    confirmation_lines.append("")
    confirmation_lines.append("*👇 Выберите подходящий вариант:*")
    
    confirmation_text = "\n".join(confirmation_lines)
    
    context.user_data['_conversation_state'] = CONFIRM
    
    logger.info(f"SHOW_SLOTS - УСПЕШНО ЗАВЕРШЕНО")
    logger.info("=" * 60)
    
    await update.message.reply_text(
        confirmation_text,
        reply_markup=KeyboardManager.get_confirmation(),
        parse_mode="Markdown"
    )
    return CONFIRM

async def handle_back_button(update: Update, context):
    logger.info(f"🔍 handle_back_button вызван")
    
    current_state = context.user_data.get('_conversation_state', None)
    
    if current_state == SHOW_SLOTS or context.user_data.get('date'):
        logger.info(f"🔍 Возврат из SHOW_SLOTS к DATE")
        
        context.user_data.pop('time', None)
        context.user_data.pop('display_time', None)
        context.user_data.pop('duration', None)
        context.user_data.pop('price', None)
        context.user_data.pop('start_hour', None)
        context.user_data.pop('end_hour', None)
        context.user_data.pop('free_intervals', None)
        context.user_data.pop('suitable_intervals', None)
        context.user_data.pop('free_interval', None)
        
        date_with_color = context.user_data.get('date_with_color', '')
        is_track_creation = context.user_data.get('is_track_creation', False)
        is_12_hours = context.user_data.get('is_12_hours', False)
        with_engineer = context.user_data.get('with_engineer', False)
        
        if not date_with_color:
            logger.error("❌ Не найдена дата для возврата!")
            await update.message.reply_text(
                "❌ Ошибка: не найдена выбранная дата!\n\n"
                "🏠 Возвращаю в главное меню...",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        if is_track_creation:
            await update.message.reply_text(
                "*📅 Шаг 5/7: Выбор даты*\n\n"
                "*✨ Когда для Вас забронировать студию?*\n\n"
                "*Правила для создания трека:*\n"
                "• Запись минимально за 72 часа\n"
                "• От 4 часов работы в студии\n"
                "• Обязательно с инженером звукозаписи\n\n"
                "*Легенда цветов:*\n"
                "🟢 — Есть 4-часовые слоты\n"
                "🟠 — Есть 4-часовые слоты только через полночь\n"
                "🔴 — Нет 4-часовых слотов\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("track_creation", True)
            )
            return DATE
            
        elif is_12_hours:
            service_type = "12_hours_day" if context.user_data.get('12_hours_type', '').startswith('День') else "12_hours_night"
            await update.message.reply_text(
                "*📅 Шаг 5/6: Выбор даты*\n\n"
                "*✨ Когда для Вас забронировать студию?*\n\n"
                "*Правила для аренды студии:*\n"
                "• Аренда минимально за 72 часа\n"
                "• Ровно 12 часов работы в студии\n"
                "• Без инженера звукозаписи\n\n"
                "*Легенда цветов:*\n"
                "🟢 — Слот доступен для бронирования\n"
                "🔴 — Слот недоступен для бронирования\n\n"
                "*👇 Выберите подходящий вариант:*", 
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates(service_type, False)
            )
            return DATE
            
        else:
            if with_engineer:
                await update.message.reply_text(
                    "*📅 Шаг 5/7: Выбор даты*\n\n"
                    "*✨ Когда планируете запись?*\n\n"
                    "*Правила для работы с инженером:*\n"
                    "• Запись минимально за 48 часов\n\n"
                    "*Легенда цветов:*\n"
                    "🟢 — Свободно более 18 часов \n"
                    "🟡 — Свободно более 12 часов\n"
                    "🟠 — Свободно более 6 часов\n"
                    "🔴 — Свободно менее 6 часов\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_dates("vocal", True)
                )
            else:
                await update.message.reply_text(
                    "*📅 Шаг 5/7: Выбор даты*\n\n"
                    "*✨ Когда планируете запись?*\n\n"
                    "*Правила для работы без инженера:*\n"
                    "• Запись минимально за 24 часа\n\n"
                    "*Легенда цветов:*\n"
                    "🟢 — Свободно более 18 часов \n"
                    "🟡 — Свободно более 12 часов\n"
                    "🟠 — Свободно более 6 часов\n"
                    "🔴 — Свободно менее 6 часов\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=KeyboardManager.get_dates("vocal", False)
                )
            return DATE
    
    else:
        service = context.user_data.get('service', '')
        
        if service == "🎤 Запись вокала" or service == "🎸 Запись инструментов":
            await update.message.reply_text(
                "*👨‍🔧 Шаг 4/7: Выбор формата*\n\n"
                "*✨ Вам требуется помощь звукорежиссера?*\n\n"
                "*С инженером — рекомендуем:*\n"
                "• Профессиональная настройка оборудования\n"
                "• Помощь в процессе записи\n"
                "• Консультации по исполнению\n\n"
                "*Без инженера — для опытных:*\n"
                "• Самостоятельная работа в студии\n"
                "• Экономия 200₽ в час\n"
                "• Полный творческий контроль\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["👨‍🔧 С инженером", "💪 Без инженера"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
            return ENGINEER_OPTION
        elif service == "⏰ 12-часовая аренда":
            await update.message.reply_text(
                "*⏰ Шаг 4/6: Выбор формата*\n\n"
                "*✨ Когда для Вас забронировать студию?*\n\n"
                "*День — 7000₽ + залог (по договору)*\n"  
                "• Работа с 9:00 до 21:00\n"
                "• Полный контроль студии\n\n"
                "*Ночь — 6500₽ + залог (по договору)*\n"
                "• Работа с 21:00 до 9:00\n"
                "• Специальная ночная цена\n\n"
            "*👇 Выберите подходящий вариант:*", 
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["☀️ День (9-21)", "🌙 Ночь (21-9)"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
            return TWELVE_HOURS_OPTION
        elif service == "🎚️ Сведение/мастеринг":
            await update.message.reply_text(
                "*🎚️ Шаг 4/5: Выбор сведения*\n\n"
                "*✨ Что Вам требуется свести?*\n\n"
                "*Трек — 2500₽*\n"
                "• Профессиональное сведение\n"
                "• Мастеринг готового микса\n\n"
                "*Альбом — договорная*\n"
                "• Обсуждение проекта\n"
                "• Индивидуальный подход\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["🎵 Трек", "💿 Альбом"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
            return MIXING_TYPE
        elif service == "🎵 Создание трека":
            await update.message.reply_text(
                "*🎵 Шаг 4/7: Выбор формата*\n\n"
                "*✨ Что Вам требуется создать?*\n\n"
                "*Трек — 9000₽*\n"
                "• Работа с инженером звукозаписи\n"
                "• Создание трека с нуля\n"
                "• Профессиональный подход\n\n"
                "*Альбом — договорная*\n"
                "• Обсуждение работы\n"
                "• Индивидуальный подход\n"
                "• Специальные условия\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["🎵 Трек", "💿 Альбом"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
            return TRACK_CREATION_TYPE
        else:
            await update.message.reply_text(
                "🎧 Шаг 3/7: Выберитее услугу\n\n"
                "✨ Какая услуга вас интересует:\n\n"
                "🎤 Запись вокала — профессиональная запись\n"
                "🎸 Запись инструментов — гитара, клавиши, ударные\n"
                "⏰ 12-часовая аренда — полный доступ к студии\n"
                "🎚️ Сведение/мастеринг — доведение до идеала\n"
                "🎵 Создание трека — производство с нуля\n"
                "🎹 Аранжировка/Биты — готовые решения\n\n"
                "👇 Выберите подходящий вариант:",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["🎤 Запись вокала", "🎸 Запись инструментов"],
                    ["⏰ 12-часовая аренда", "🎚️ Сведение/мастеринг"],
                    ["🎵 Создание трека", "🎹 Аранжировка/Биты"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
            return SERVICE

@handle_errors_with_rate_limit
async def test_award(update: Update, context):
    """Полная диагностика записи (время, статус, сравнение)"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("❌ /testaward 1")
        return
    
    try:
        booking_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!")
        return
    
    await update.message.reply_text(f"🔍 *Диагностика записи #{booking_id}...*\n\nПодожди...", parse_mode="Markdown")
    
    try:
        import sqlite3
        import pytz
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(db.db_path, timeout=10.0)
        cursor = conn.cursor()
        
        # Получаем ВСЕ данные записи
        cursor.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,))
        row = cursor.fetchone()
        
        if not row:
            await update.message.reply_text(f"❌ Запись #{booking_id} не найдена!")
            conn.close()
            return
        
        columns = [description[0] for description in cursor.description]
        conn.close()
        
        # ===== ОСНОВНЫЕ ДАННЫЕ =====
        data = dict(zip(columns, row))
        
        date_str = data.get('date_str', '')
        time_slot = data.get('time_slot', '')
        status = data.get('status', '')
        vinyls_awarded = data.get('vinyls_awarded', 0)
        telegram_id = data.get('telegram_id', '')
        service = data.get('service', '')
        
        # ===== ТЕКУЩЕЕ ВРЕМЯ =====
        now = DateTimeUtils.now()
        now_utc = now.astimezone(pytz.UTC)
        
        # ===== ПАРСИМ ДАТУ И ВРЕМЯ ОКОНЧАНИЯ =====
        clean_date = date_str
        if '(' in clean_date:
            clean_date = clean_date.split('(')[0].strip()
        if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
            clean_date = clean_date[2:].strip()
        
        try:
            day, month, year = map(int, clean_date.split('.'))
            
            end_hour = 0
            if time_slot and '-' in time_slot:
                norm_time = DateTimeUtils.normalize_time_input(time_slot)
                start_str, end_str = norm_time.split('-')
                end_hour = int(end_str)
                if end_hour == 0:
                    end_hour = 24
            
            end_datetime = datetime(year, month, day, end_hour, 0, 0)
            end_datetime = Config.TIMEZONE.localize(end_datetime)
            end_utc = end_datetime.astimezone(pytz.UTC)
            
            time_passed = now_utc >= end_utc
            time_diff = now_utc - end_utc
            minutes_passed = int(time_diff.total_seconds() / 60)
            
        except Exception as e:
            end_datetime = None
            end_utc = None
            time_passed = False
            minutes_passed = 0
        
        # ===== ФОРМИРУЕМ СООБЩЕНИЕ =====
        message = f"📋 *ДИАГНОСТИКА ЗАПИСИ #{booking_id}*\n\n"
        
        message += "*📌 ОСНОВНЫЕ ДАННЫЕ:*\n"
        message += f"• Услуга: {service}\n"
        message += f"• Дата: {date_str}\n"
        message += f"• Время: {time_slot}\n"
        message += f"• Статус: {status}\n"
        message += f"• vinyls_awarded: {vinyls_awarded}\n"
        message += f"• Пользователь: {telegram_id}\n\n"
        
        message += "*⏰ ВРЕМЯ:*\n"
        message += f"• Сейчас (МСК): {now.strftime('%d.%m.%Y %H:%M:%S')}\n"
        message += f"• Сейчас (UTC): {now_utc.strftime('%d.%m.%Y %H:%M:%S')}\n"
        
        if end_datetime:
            message += f"• Окончание (МСК): {end_datetime.strftime('%d.%m.%Y %H:%M:%S')}\n"
            message += f"• Окончание (UTC): {end_utc.strftime('%d.%m.%Y %H:%M:%S')}\n"
            message += f"• end_hour: {end_hour}\n\n"
            
            message += "*🔍 СРАВНЕНИЕ:*\n"
            message += f"• now_utc >= end_utc: {time_passed}\n"
            if time_passed:
                message += f"• Прошло минут: {minutes_passed}\n"
            else:
                message += f"• Осталось минут: {abs(minutes_passed)}\n"
        else:
            message += "• Окончание: НЕ ОПРЕДЕЛЕНО\n"
        
        # ===== ЕСЛИ ВРЕМЯ ПРОШЛО, НО ПЛАСТИНКИ НЕ НАЧИСЛЕНЫ =====
        if time_passed and vinyls_awarded == 0 and status in ['confirmed', 'подтвержден']:
            message += "\n*⚠️ ВРЕМЯ ПРОШЛО, НО ПЛАСТИНКИ НЕ НАЧИСЛЕНЫ!*\n"
            message += "Проверь функцию update_completed_bookings\n"
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ *Ошибка:* {str(e)[:300]}", parse_mode="Markdown")

@handle_errors_with_rate_limit
async def force_complete(update: Update, context):
    """Принудительно завершить запись и начислить пластинки"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("❌ /forcecomplete 1")
        return
    
    booking_id = int(args[0])
    
    await update.message.reply_text(f"🔄 *Принудительно завершаю запись #{booking_id}...*", parse_mode="Markdown")
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем данные записи
            cursor.execute('''
                SELECT id, telegram_id, status, service, date_str, time_slot, name, contact, price,
                       duration, is_mixing, is_admin_booking, is_contractual, is_12_hours, is_track_creation
                FROM bookings WHERE id = ?
            ''', (booking_id,))
            
            booking = cursor.fetchone()
            
            if not booking:
                await update.message.reply_text(f"❌ Запись #{booking_id} не найдена!")
                return
            
            (b_id, telegram_id, status, service, date_str, time_slot, name, contact, price,
             duration, is_mixing, is_admin_booking, is_contractual, is_12_hours, is_track_creation) = booking
            
            # Проверяем дубль
            cursor.execute('SELECT vinyls_awarded FROM bookings WHERE id = ?', (booking_id,))
            result = cursor.fetchone()
            if result and result[0] == 1:
                await update.message.reply_text(f"ℹ️ Пластинки уже начислены!")
                return
            
            booking_data = {
                'id': booking_id,
                'telegram_id': telegram_id,
                'status': status,
                'service': service,
                'date_str': date_str,
                'time_slot': time_slot,
                'name': name,
                'contact': contact,
                'price': price,
                'duration': duration,
                'is_mixing': is_mixing,
                'is_admin_booking': is_admin_booking,
                'is_contractual': is_contractual,
                'is_12_hours': is_12_hours,
                'is_track_creation': is_track_creation
            }
            
            vinyls_added, new_vinyls = await AchievementSystem.add_vinyls_for_booking(
                str(telegram_id), context, booking_data
            )
            
            if vinyls_added:
                cursor.execute('UPDATE bookings SET status = "completed" WHERE id = ?', (booking_id,))
                conn.commit()
                await update.message.reply_text(
                    f"✅ *Пластинки начислены!*\n\n"
                    f"📋 Запись #{booking_id}\n"
                    f"💰 Всего пластинок: {new_vinyls} 💿\n\n"
                    f"*Проверь /level*",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(f"❌ *Не удалось начислить пластинки!*", parse_mode="Markdown")
                
    except Exception as e:
        await update.message.reply_text(f"❌ *Ошибка:* {str(e)[:200]}", parse_mode="Markdown")

async def handle_back_in_date(update: Update, context):
    if await check_user_blocked(update, context):
        return ConversationHandler.END
    
    logger.info(f"🔍 handle_back_in_date вызван")
    
    keys_to_remove = [
        'free_intervals', 'free_interval', 'time', 'display_time',
        'duration', 'price', 'date_with_color', 'display_period',
        'start_hour', 'end_hour', 'suitable_intervals', 'date'
    ]
    for key in keys_to_remove:
        context.user_data.pop(key, None)
    
    is_track_creation = context.user_data.get('is_track_creation', False)
    is_12_hours = context.user_data.get('is_12_hours', False)
    with_engineer = context.user_data.get('with_engineer', False)
    is_mixing = context.user_data.get('is_mixing', False)
    
    if is_track_creation:
        track_type = context.user_data.get('track_type', '')
        if "Альбом" in track_type or "Договорная" in str(track_type):
            await update.message.reply_text(
            "*🎵 Шаг 4/7: Выбор формата*\n\n"
            "*✨ Что Вам требуется создать?*\n\n"
            "*Трек — 9000₽*\n"
            "• Работа с инженером звукозаписи\n"
            "• Создание трека с нуля\n"
            "• Профессиональный подход\n\n"
            "*Альбом — договорная*\n"
            "• Обсуждение работы\n"
            "• Индивидуальный подход\n"
            "• Специальные условия\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_track_creation_options()
        )
            return TRACK_CREATION_TYPE
        else:
            await update.message.reply_text(
                "*📅 Шаг 5/7: Выбор даты*\n\n"
                "*✨ Когда для Вас забронировать студию?*\n\n"
                "*Правила для создания трека:*\n"
                "• Запись минимально за 72 часа\n"
                "• От 4 часов работы в студии\n"
                "• Обязательно с инженером звукозаписи\n\n"
                "*Легенда цветов:*\n"
                "🟢 — Есть 4-часовые слоты\n"
                "🟠 — Есть 4-часовые слоты только через полночь\n"
                "🔴 — Нет 4-часовых слотов\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("track_creation", True)
            )
            return DATE
    
    elif is_12_hours:
        await update.message.reply_text(
            "*📅 Шаг 5/6: Выбор даты*\n\n"
            "*✨ Когда для Вас забронировать студию?*\n\n"
            "*Правила для аренды студии:*\n"
            "• Аренда минимально за 72 часа\n"
            "• Ровно 12 часов работы в студии\n"
            "• Без инженера звукозаписи\n\n"
            "*Легенда цветов:*\n"
            "🟢 — Слот доступен для бронирования\n"
            "🔴 — Слот недоступен для бронирования\n\n"
            "*👇 Выберите подходящий вариант:*", 
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_12_hours_options()
        )
        return TWELVE_HOURS_OPTION
    
    elif is_mixing:
        await update.message.reply_text(
            "*🎚️ Шаг 4/5: Выбор сведения*\n\n"
            "*✨ Что Вам требуется свести?*\n\n"
            "*Трек — 2500₽*\n"
            "• Профессиональное сведение\n"
            "• Мастеринг готового микса\n\n"
            "*Альбом — договорная*\n"
            "• Обсуждение проекта\n"
            "• Индивидуальный подход\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_mixing()
        )
        return MIXING_TYPE
    
    else:
        service_type = context.user_data.get('service_type', 'vocal')
        
        if with_engineer:
            await update.message.reply_text(
                "*📅 Шаг 5/7: Выбор даты*\n\n"
                "*✨ Когда планируете запись?*\n\n"
                "*Правила для работы с инженером:*\n"
                "• Запись минимально за 48 часов\n\n"
                "*Легенда цветов:*\n"
                "🟢 — Свободно более 18 часов \n"
                "🟡 — Свободно более 12 часов\n"
                "🟠 — Свободно более 6 часов\n"
                "🔴 — Свободно менее 6 часов\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("vocal", True)
            )
        else:
            await update.message.reply_text(
                "*📅 Шаг 5/7: Выбор даты*\n\n"
                "*✨ Когда планируете запись?*\n\n"
                "Правила для работы без инженера:\n"
                "• Запись минимально за 24 часа\n\n"
                "*Легенда цветов:*\n"
                "🟢 — Свободно более 18 часов \n"
                "🟡 — Свободно более 12 часов\n"
                "🟠 — Свободно более 6 часов\n"
                "🔴 — Свободно менее 6 часов\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_dates("vocal", False)
            )
        return DATE


async def handle_time_input_format(update: Update, context, text: str):
    normalized_input = DateTimeUtils.normalize_time_input(text)
    context.user_data['time'] = normalized_input
    context.user_data['display_time'] = DateTimeUtils.format_time_for_display(normalized_input)
    return await show_slots(update, context)


@handle_errors_with_rate_limit
async def admin_promo_start(update: Update, context):
    """Начало создания промокода - выбор типа (общий или персональный)"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    context.user_data['is_admin_promo'] = True
    
    await update.message.reply_text(
        "*👑 Шаг 1/8: Выбор типа промокода*\n\n"
        "*🌍 Общий промокод:*\n"
        "• Может использовать любой пользователь\n"
        "• Не требует ввода ID пользователя\n\n"
        "*👤 Персональный промокод:*\n"
        "• Только для конкретного пользователя\n"
        "• Потребуется ввести ID или username\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["🌍 Общий промокод", "👤 Персональный промокод"],
            ["↩️ Главное меню"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_PROMO_START


@handle_errors_with_rate_limit
async def admin_promo_select_type(update: Update, context):
    """Обработка выбора типа промокода (общий/персональный)"""
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "🌍 Общий промокод":
        context.user_data['promo_target_type'] = 'global'
        context.user_data['promo_code'] = PromoCodeManager.generate_code()
        
        await update.message.reply_text(
            "*👑 Шаг 2/7: Выбор длительности*\n\n"
            "*♾️ Бессрочный:*\n"
            "• Действует постоянно\n"
            "• Не истекает\n\n"
            "*⏱️ Временный:*\n"
            "• Действует ограниченное время\n"
            "• После истечения пропадает\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["♾️ Бессрочный", "⏱️ Временный"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_PROMO_DURATION
    
    elif text == "👤 Персональный промокод":
        context.user_data['promo_target_type'] = 'personal'
        context.user_data['promo_code'] = PromoCodeManager.generate_code()
        
        await update.message.reply_text(
            "*👑 Шаг 2/8: Ввод имени пользователя*\n\n"
            "*📋 Варианты ввода:*\n"
            "• Уникальный ID (MC...): `MC1772377294899374`\n"
            "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
            "*💡 Где найти Уникальный ID:*\n"
            "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
            "*✏️ Введите данные:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_PROMO_USER_ID
    
    await update.message.reply_text(
        "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["🌍 Общий промокод", "👤 Персональный промокод"],
            ["↩️ Главное меню"]
        ], resize_keyboard=True)
    )
    return ADMIN_PROMO_START

@handle_errors_with_rate_limit
async def admin_promo_find_user(update: Update, context):
    """Поиск пользователя для персонального промокода"""
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*👑 Шаг 1/8: Выбор типа промокода*\n\n"
            "*🌍 Общий промокод:*\n"
            "• Может использовать любой пользователь\n"
            "• Не требует ввода ID пользователя\n\n"
            "*👤 Персональный промокод:*\n"
            "• Только для конкретного пользователя\n"
            "• Потребуется ввести ID или username\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["🌍 Общий промокод", "👤 Персональный промокод"],
                ["↩️ Главное меню"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_PROMO_START
    
    search_term = text.replace('@', '').strip().lower()
    found_user = None
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # ===== 1. Поиск по уникальному ID =====
            if search_term.startswith("mc"):
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id 
                    FROM users WHERE LOWER(unique_id) = ?
                ''', (search_term,))
                found_user = cursor.fetchone()
            
            # ===== 2. Поиск по username =====
            if not found_user:
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id 
                    FROM users WHERE LOWER(username) = ? OR LOWER(username) = ?
                ''', (search_term, f'@{search_term}'))
                found_user = cursor.fetchone()
            
            # ===== 3. Поиск по частичному совпадению =====
            if not found_user:
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id 
                    FROM users WHERE 
                    LOWER(username) LIKE ? OR 
                    LOWER(username) LIKE ? OR
                    LOWER(first_name) LIKE ? OR
                    LOWER(unique_id) LIKE ?
                ''', (f'%{search_term}%', f'%@{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                found_user = cursor.fetchone()
            
            if not found_user:
                await update.message.reply_text(
                    f"*❌ Пользователь не найден!*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
                return ADMIN_PROMO_USER_ID
            
            telegram_id, username, first_name, unique_id = found_user
            context.user_data['target_user_id'] = telegram_id
            context.user_data['target_username'] = username or first_name or "Неизвестный"
            context.user_data['target_display'] = get_user_display_name({
                'username': username, 
                'unique_id': unique_id, 
                'telegram_id': telegram_id
            })
            
            logger.info(f"✅ Найден пользователь: {unique_id}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка поиска: {e}")
        await update.message.reply_text(
            "❌ Ошибка при поиске пользователя!\n\n"
            "💡 Попробуйте позже или свяжитесь с администратором",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True)
        )
        return ADMIN_PROMO_USER_ID
    
    await update.message.reply_text(
        "*👑 Шаг 3/8: Выбор длительности*\n\n"
        "*♾️ Бессрочный:*\n"
        "• Действует постоянно\n"
        "• Не истекает\n\n"
        "*⏱️ Временный:*\n"
        "• Действует ограниченное время\n"
        "• После истечения пропадает\n\n"
        "*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["♾️ Бессрочный", "⏱️ Временный"],
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_PROMO_DURATION

@handle_errors_with_rate_limit
async def admin_promo_duration(update: Update, context):
    """Выбор срока действия промокода"""
    text = update.message.text.strip()
    promo_target_type = context.user_data.get('promo_target_type')
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        from_promo_type_back = context.user_data.get('from_promo_type_back', False)
        
        if from_promo_type_back:
            context.user_data.pop('from_promo_type_back', None)
            
            if promo_target_type == 'personal':
                await update.message.reply_text(
                    "*👑 Шаг 3/8: Выбор длительности*\n\n"
                    "*♾️ Бессрочный:*\n"
                    "• Действует постоянно\n"
                    "• Не истекает\n\n"
                    "*⏱️ Временный:*\n"
                    "• Действует ограниченное время\n"
                    "• После истечения пропадает\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["♾️ Бессрочный", "⏱️ Временный"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "*👑 Шаг 2/7: Выбор длительности*\n\n"
                    "*♾️ Бессрочный:*\n"
                    "• Действует постоянно\n"
                    "• Не истекает\n\n"
                    "*⏱️ Временный:*\n"
                    "• Действует ограниченное время\n"
                    "• После истечения пропадает\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["♾️ Бессрочный", "⏱️ Временный"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            return ADMIN_PROMO_DURATION
        else:
            if promo_target_type == 'personal':
                await update.message.reply_text(
                    "*👑 Шаг 2/8: Ввод имени пользователя*\n\n"
                    "*📋 Варианты ввода:*\n"
                    "• Уникальный ID (MC...): `MC1772377294899374`\n"
                    "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
                    "*💡 Где найти Уникальный ID:*\n"
                    "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
                    "*✏️ Введите данные:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
                return ADMIN_PROMO_USER_ID
            else:
                await update.message.reply_text(
                    "*👑 Шаг 1/8: Выбор типа промокода*\n\n"
                    "*🌍 Общий промокод:*\n"
                    "• Может использовать любой пользователь\n"
                    "• Не требует ввода ID пользователя\n\n"
                    "*👤 Персональный промокод:*\n"
                    "• Только для конкретного пользователя\n"
                    "• Потребуется ввести ID или username\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["🌍 Общий промокод", "👤 Персональный промокод"],
                        ["↩️ Главное меню"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
                return ADMIN_PROMO_START
    
    if text == "♾️ Бессрочный":
        context.user_data['expiry_date'] = None
        
        if promo_target_type == 'personal':
            await update.message.reply_text(
                "*👑 Шаг 4/7: Выбор типа промокода*\n\n"
                "*💰 % на все:*\n"
                "• Скидка на все услуги\n\n"
                "*🎯 % на услугу:*\n"
                "• Скидка на конкретную услугу\n\n"
                "*⏱️ Бесплатный час:*\n"
                "• Бесплатный час для вокала/инструмента\n\n"
                "*🎵 Бесплатная услуга:*\n"
                "• Конкретная услуга бесплатно\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["💰 % на все", "🎯 % на услугу"],
                    ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "*👑 Шаг 3/6: Выбор типа промокода*\n\n"
                "*💰 % на все:*\n"
                "• Скидка на все услуги\n\n"
                "*🎯 % на услугу:*\n"
                "• Скидка на конкретную услугу\n\n"
                "*⏱️ Бесплатный час:*\n"
                "• Бесплатный час для вокала/инструмента\n\n"
                "*🎵 Бесплатная услуга:*\n"
                "• Конкретная услуга бесплатно\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["💰 % на все", "🎯 % на услугу"],
                    ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
        return ADMIN_PROMO_TYPE
    
    elif text == "⏱️ Временный":
        context.user_data.pop('from_promo_type_back', None)
        
        if promo_target_type == 'personal':
            await update.message.reply_text(
                "*👑 Шаг 4/8: Ввод длительности*\n\n"
                "*📋 Форматы ввода:*\n"
                "• `1ч` — на 1 час\n"
                "• `3д` — на 3 дня\n"
                "• `1мес` — на 1 месяц\n\n"
                "*✏️ Введите длительность:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "*👑 Шаг 3/7: Ввод длительности*\n\n"
                "*📋 Форматы ввода:*\n"
                "• `1ч` — на 1 час\n"
                "• `3д` — на 3 дня\n"
                "• `1мес` — на 1 месяц\n\n"
                "*✏️ Введите длительность:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
        return ADMIN_PROMO_DURATION_INPUT
    
    await update.message.reply_text(
        "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["♾️ Бессрочный", "⏱️ Временный"],
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True)
    )
    return ADMIN_PROMO_DURATION


@handle_errors_with_rate_limit
async def admin_promo_duration_input(update: Update, context):
    """Ввод срока действия для временного промокода"""
    text = update.message.text.strip().lower()
    promo_target_type = context.user_data.get('promo_target_type')
    
    if text == "↩️ главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ назад":
        if promo_target_type == 'personal':
            await update.message.reply_text(
                "*👑 Шаг 3/8: Выбор длительности*\n\n"
                "*♾️ Бессрочный:*\n"
                "• Действует постоянно\n"
                "• Не истекает\n\n"
                "*⏱️ Временный:*\n"
                "• Действует ограниченное время\n"
                "• После истечения пропадает\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["♾️ Бессрочный", "⏱️ Временный"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "*👑 Шаг 2/7: Выбор длительности*\n\n"
                "*♾️ Бессрочный:*\n"
                "• Действует постоянно\n"
                "• Не истекает\n\n"
                "*⏱️ Временный:*\n"
                "• Действует ограниченное время\n"
                "• После истечения пропадает\n\n"
                "*👇 Выберите подходящий вариант:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["♾️ Бессрочный", "⏱️ Временный"],
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
        return ADMIN_PROMO_DURATION
    
    import re
    now = DateTimeUtils.now().replace(tzinfo=None)
    expiry_date = None
    
    match_hours = re.match(r'^(\d+)\s*ч$', text)
    if match_hours:
        hours = int(match_hours.group(1))
        if 1 <= hours <= 8760:
            expiry_date = now + timedelta(hours=hours)
    
    match_days = re.match(r'^(\d+)\s*д$', text)
    if match_days and not expiry_date:
        days = int(match_days.group(1))
        if 1 <= days <= 365:
            expiry_date = now + timedelta(days=days)
    
    match_months = re.match(r'^(\d+)\s*мес$', text)
    if match_months and not expiry_date:
        months = int(match_months.group(1))
        if 1 <= months <= 12:
            expiry_date = now + timedelta(days=30 * months)
    
    if not expiry_date:
        context.user_data.pop('from_promo_type_back', None)
        
        await update.message.reply_text(
            "*❌ Неверный формат!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True)
        )
        return ADMIN_PROMO_DURATION_INPUT
    
    context.user_data['expiry_date'] = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
    context.user_data.pop('from_promo_type_back', None)
    
    if promo_target_type == 'personal':
        await update.message.reply_text(
            "*👑 Шаг 5/8: Выбор типа промокода*\n\n"
            "*💰 % на все:*\n"
            "• Скидка на все услуги\n\n"
            "*🎯 % на услугу:*\n"
            "• Скидка на конкретную услугу\n\n"
            "*⏱️ Бесплатный час:*\n"
            "• Бесплатный час для вокала/инструмента\n\n"
            "*🎵 Бесплатная услуга:*\n"
            "• Конкретная услуга бесплатно\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["💰 % на все", "🎯 % на услугу"],
                ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "*👑 Шаг 4/7: Выбор типа промокода*\n\n"
            "*💰 % на все:*\n"
            "• Скидка на все услуги\n\n"
            "*🎯 % на услугу:*\n"
            "• Скидка на конкретную услугу\n\n"
            "*⏱️ Бесплатный час:*\n"
            "• Бесплатный час для вокала/инструмента\n\n"
            "*🎵 Бесплатная услуга:*\n"
            "• Конкретная услуга бесплатно\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["💰 % на все", "🎯 % на услугу"],
                ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
    return ADMIN_PROMO_TYPE


@handle_errors_with_rate_limit
async def admin_promo_type(update: Update, context):
    """Выбор типа скидки"""
    text = update.message.text.strip()
    promo_target_type = context.user_data.get('promo_target_type')
    discount_type_map = {
        "💰 % на все": "percent_all",
        "🎯 % на услугу": "percent_service",
        "⏱️ Бесплатный час": "free_hours",
        "🎵 Бесплатная услуга": "free_service"
    }
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        expiry_date = context.user_data.get('expiry_date')
        
        if promo_target_type == 'personal':
            if expiry_date is None:
                await update.message.reply_text(
                    "*👑 Шаг 3/8: Выбор длительности*\n\n"
                    "*♾️ Бессрочный:*\n"
                    "• Действует постоянно\n"
                    "• Не истекает\n\n"
                    "*⏱️ Временный:*\n"
                    "• Действует ограниченное время\n"
                    "• После истечения пропадает\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["♾️ Бессрочный", "⏱️ Временный"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
                return ADMIN_PROMO_DURATION
            else:
                await update.message.reply_text(
                    "*👑 Шаг 4/8: Ввод длительности*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `1ч` — на 1 час\n"
                    "• `3д` — на 3 дня\n"
                    "• `1мес` — на 1 месяц\n\n"
                    "*✏️ Введите длительность:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
                return ADMIN_PROMO_DURATION_INPUT
        else:
            if expiry_date is None:
                await update.message.reply_text(
                    "*👑 Шаг 2/7: Выбор длительности*\n\n"
                    "*♾️ Бессрочный:*\n"
                    "• Действует постоянно\n"
                    "• Не истекает\n\n"
                    "*⏱️ Временный:*\n"
                    "• Действует ограниченное время\n"
                    "• После истечения пропадает\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["♾️ Бессрочный", "⏱️ Временный"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
                return ADMIN_PROMO_DURATION
            else:
                await update.message.reply_text(
                    "*👑 Шаг 3/7: Ввод длительности*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `1ч` — на 1 час\n"
                    "• `3д` — на 3 дня\n"
                    "• `1мес` — на 1 месяц\n\n"
                    "*✏️ Введите длительность:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
                return ADMIN_PROMO_DURATION_INPUT
    
    if text not in discount_type_map:
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["💰 % на все", "🎯 % на услугу"],
                ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True)
        )
        return ADMIN_PROMO_TYPE
    
    context.user_data['discount_type'] = discount_type_map[text]
    
    if text in ["🎯 % на услугу", "🎵 Бесплатная услуга"]:
        expiry = context.user_data.get('expiry_date')
        
        if promo_target_type == 'personal':
            if text == "🎵 Бесплатная услуга" and expiry is None:
                await update.message.reply_text(
                    "*👑 Шаг 5/6: Выбор услуги*\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                        ["🎚️ Сведение", "🎵 Создание трека"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            elif text == "🎵 Бесплатная услуга" and expiry is not None:
                await update.message.reply_text(
                    "*👑 Шаг 6/7: Выбор услуги*\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                        ["🎚️ Сведение", "🎵 Создание трека"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            elif text == "🎯 % на услугу" and expiry is None:
                await update.message.reply_text(
                    "*👑 Шаг 5/7: Выбор услуги*\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                        ["🎚️ Сведение", "🎵 Создание трека"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "*👑 Шаг 6/8: Выбор услуги*\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                        ["🎚️ Сведение", "🎵 Создание трека"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
        else:
            if text == "🎵 Бесплатная услуга":
                if expiry is None:
                    await update.message.reply_text(
                        "*👑 Шаг 4/5: Выбор услуги*\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                            ["🎚️ Сведение", "🎵 Создание трека"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
                else:
                    await update.message.reply_text(
                        "*👑 Шаг 5/6: Выбор услуги*\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                            ["🎚️ Сведение", "🎵 Создание трека"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
            else:
                if expiry is None:
                    await update.message.reply_text(
                        "*👑 Шаг 4/6: Выбор услуги*\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                            ["🎚️ Сведение", "🎵 Создание трека"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
                else:
                    await update.message.reply_text(
                        "*👑 Шаг 5/7: Выбор услуги*\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                            ["🎚️ Сведение", "🎵 Создание трека"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
        return ADMIN_PROMO_SERVICE
    
    if text == "⏱️ Бесплатный час":
        expiry = context.user_data.get('expiry_date')
        
        if promo_target_type == 'personal':
            if expiry is None:
                await update.message.reply_text(
                    "*👑 Шаг 5/6: Ввод количества*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `1` — 1 час\n"
                    "• `3` — 3 часа\n\n"
                    "*✏️ Введите количество:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "*👑 Шаг 6/7: Ввод количества*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `1` — 1 час\n"
                    "• `3` — 3 часа\n\n"
                    "*✏️ Введите количество:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
        else:
            if expiry is None:
                await update.message.reply_text(
                    "*👑 Шаг 4/5: Ввод количества*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `1` — 1 час\n"
                    "• `3` — 3 часа\n\n"
                    "*✏️ Введите количество:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "*👑 Шаг 5/6: Ввод количества*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `1` — 1 час\n"
                    "• `3` — 3 часа\n\n"
                    "*✏️ Введите количество:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
    else:
        expiry = context.user_data.get('expiry_date')
        
        if promo_target_type == 'personal':
            if expiry is None:
                await update.message.reply_text(
                    "*👑 Шаг 5/6: Ввод процента скидки*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `10` — на 10% скидка\n"
                    "• `100` — на 100% скидка\n\n"
                    "*✏️ Введите количество:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "*👑 Шаг 6/7: Ввод процента скидки*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `10` — на 10% скидка\n"
                    "• `100` — на 100% скидка\n\n"
                    "*✏️ Введите количество:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
        else:
            if expiry is None:
                await update.message.reply_text(
                    "*👑 Шаг 4/5: Ввод процента скидки*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `10` — на 10% скидка\n"
                    "• `100` — на 100% скидка\n\n"
                    "*✏️ Введите количество:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "*👑 Шаг 5/6: Ввод процента скидки*\n\n"
                    "*📋 Форматы ввода:*\n"
                    "• `10` — на 10% скидка\n"
                    "• `100` — на 100% скидка\n\n"
                    "*✏️ Введите количество:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True)
                )
    return ADMIN_PROMO_VALUE


@handle_errors_with_rate_limit
async def admin_promo_service(update: Update, context):
    """Выбор услуги для промокода"""
    text = update.message.text.strip()
    promo_target_type = context.user_data.get('promo_target_type')
    discount_type = context.user_data.get('discount_type')
    service_map = {
        "🎤 Вокал": "вокал",
        "🎸 Инструмент": "инструмент",
        "⏰ Аренда": "аренда",
        "🎚️ Сведение": "сведение",
        "🎵 Создание трека": "трек"
    }
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        expiry = context.user_data.get('expiry_date')
        
        if promo_target_type == 'personal':
            if expiry is None:
                await update.message.reply_text(
                    "*👑 Шаг 4/7: Выбор типа промокода*\n\n"
                    "*💰 % на все:*\n"
                    "• Скидка на все услуги\n\n"
                    "*🎯 % на услугу:*\n"
                    "• Скидка на конкретную услугу\n\n"
                    "*⏱️ Бесплатный час:*\n"
                    "• Бесплатный час для вокала/инструмента\n\n"
                    "*🎵 Бесплатная услуга:*\n"
                    "• Конкретная услуга бесплатно\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["💰 % на все", "🎯 % на услугу"],
                        ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "*👑 Шаг 5/8: Выбор типа промокода*\n\n"
                    "*💰 % на все:*\n"
                    "• Скидка на все услуги\n\n"
                    "*🎯 % на услугу:*\n"
                    "• Скидка на конкретную услугу\n\n"
                    "*⏱️ Бесплатный час:*\n"
                    "• Бесплатный час для вокала/инструмента\n\n"
                    "*🎵 Бесплатная услуга:*\n"
                    "• Конкретная услуга бесплатно\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["💰 % на все", "🎯 % на услугу"],
                        ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
        else:
            if expiry is None:
                await update.message.reply_text(
                    "*👑 Шаг 3/6: Выбор типа промокода*\n\n"
                    "*💰 % на все:*\n"
                    "• Скидка на все услуги\n\n"
                    "*🎯 % на услугу:*\n"
                    "• Скидка на конкретную услугу\n\n"
                    "*⏱️ Бесплатный час:*\n"
                    "• Бесплатный час для вокала/инструмента\n\n"
                    "*🎵 Бесплатная услуга:*\n"
                    "• Конкретная услуга бесплатно\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["💰 % на все", "🎯 % на услугу"],
                        ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "*👑 Шаг 4/7: Выбор типа промокода*\n\n"
                    "*💰 % на все:*\n"
                    "• Скидка на все услуги\n\n"
                    "*🎯 % на услугу:*\n"
                    "• Скидка на конкретную услугу\n\n"
                    "*⏱️ Бесплатный час:*\n"
                    "• Бесплатный час для вокала/инструмента\n\n"
                    "*🎵 Бесплатная услуга:*\n"
                    "• Конкретная услуга бесплатно\n\n"
                    "*👇 Выберите подходящий вариант:*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["💰 % на все", "🎯 % на услугу"],
                        ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                        ["↩️ Главное меню", "↩️ Назад"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
        return ADMIN_PROMO_TYPE
    
    if text not in service_map:
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                ["🎚️ Сведение", "🎵 Создание трека"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True)
        )
        return ADMIN_PROMO_SERVICE
    
    context.user_data['target_service'] = service_map[text]
    service_name_display = text.replace("🎤 ", "").replace("🎸 ", "").replace("⏰ ", "").replace("🎚️ ", "").replace("🎵 ", "")
    
    if discount_type == "free_service":
        context.user_data['discount_value'] = 1
        expiry = context.user_data.get('expiry_date')
        
        if promo_target_type == 'personal':
            if expiry is None:
                await update.message.reply_text(
                    f"*👑 Шаг 6/6: Подтверждение*\n\n"
                    f"*✅ Проверьте данные:*\n\n"
                    f"👤 Пользователь: {context.user_data.get('target_display')}\n"
                    f"🎟️ Код: `{context.user_data.get('promo_code')}`\n"
                    f"🎁 Бонус: 🎵 Бесплатно: {service_name_display}\n"
                    f"⏰ Срок: ♾️ Бессрочный\n\n"
                    f"*👇 Всё верно ?*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["✅ Да, создать промокод", "✏️ Исправить данные"],
                        ["❌ Отменить"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    f"*👑 Шаг 7/7: Подтверждение*\n\n"
                    f"*✅ Проверьте данные:*\n\n"
                    f"👤 Пользователь: {context.user_data.get('target_display')}\n"
                    f"🎟️ Код: `{context.user_data.get('promo_code')}`\n"
                    f"🎁 Бонус: 🎵 Бесплатно: {service_name_display}\n"
                    f"⏰ Срок: ⏱️ Временный\n\n"
                    f"*👇 Всё верно ?*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["✅ Да, создать промокод", "✏️ Исправить данные"],
                        ["❌ Отменить"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
        else:
            if expiry is None:
                await update.message.reply_text(
                    f"*👑 Шаг 5/5: Подтверждение*\n\n"
                    f"*✅ Проверьте данные:*\n\n"
                    f"🌍 Тип: Общий для всех\n"
                    f"🎟️ Код: `{context.user_data.get('promo_code')}`\n"
                    f"🎁 Бонус: 🎵 Бесплатно: {service_name_display}\n"
                    f"⏰ Срок: ♾️ Бессрочный\n\n"
                    f"*👇 Всё верно ?*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["✅ Да, создать промокод", "✏️ Исправить данные"],
                        ["❌ Отменить"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    f"*👑 Шаг 6/6: Подтверждение*\n\n"
                    f"*✅ Проверьте данные:*\n\n"
                    f"🌍 Тип: Общий для всех\n"
                    f"🎟️ Код: `{context.user_data.get('promo_code')}`\n"
                    f"🎁 Бонус: 🎵 Бесплатно: {service_name_display}\n"
                    f"⏰ Срок: ⏱️ Временный\n\n"
                    f"*👇 Всё верно ?*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["✅ Да, создать промокод", "✏️ Исправить данные"],
                        ["❌ Отменить"]
                    ], resize_keyboard=True, one_time_keyboard=True)
                )
        return ADMIN_PROMO_CONFIRM
    
    expiry = context.user_data.get('expiry_date')
    
    if promo_target_type == 'personal':
        if expiry is None:
            await update.message.reply_text(
                "*👑 Шаг 6/7: Ввод процента скидки*\n\n"
                "*📋 Форматы ввода:*\n"
                "• `10` — на 10% скидка\n"
                "• `100` — на 100% скидка\n\n"
                "*✏️ Введите количество:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "*👑 Шаг 7/8: Ввод процента скидки*\n\n"
                "*📋 Форматы ввода:*\n"
                "• `10` — на 10% скидка\n"
                "• `100` — на 100% скидка\n\n"
                "*✏️ Введите количество:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
    else:
        if expiry is None:
            await update.message.reply_text(
                "*👑 Шаг 5/6: Ввод процента скидки*\n\n"
                "*📋 Форматы ввода:*\n"
                "• `10` — на 10% скидка\n"
                "• `100` — на 100% скидка\n\n"
                "*✏️ Введите количество:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "*👑 Шаг 6/7: Ввод процента скидки*\n\n"
                "*📋 Форматы ввода:*\n"
                "• `10` — на 10% скидка\n"
                "• `100` — на 100% скидка\n\n"
                "*✏️ Введите количество:*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["↩️ Главное меню", "↩️ Назад"]
                ], resize_keyboard=True)
            )
    return ADMIN_PROMO_VALUE


@handle_errors_with_rate_limit
async def admin_promo_value(update: Update, context):
    """Ввод значения скидки"""
    text = update.message.text.strip()
    promo_target_type = context.user_data.get('promo_target_type')
    discount_type = context.user_data.get('discount_type')
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        expiry = context.user_data.get('expiry_date')
        
        if discount_type in ['percent_service', 'free_service']:
            if promo_target_type == 'personal':
                if expiry is None:
                    await update.message.reply_text(
                        "*👑 Шаг 5/7: Выбор услуги*\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                            ["🎚️ Сведение", "🎵 Создание трека"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
                else:
                    await update.message.reply_text(
                        "*👑 Шаг 6/8: Выбор услуги*\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                            ["🎚️ Сведение", "🎵 Создание трека"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
            else:
                if expiry is None:
                    await update.message.reply_text(
                        "*👑 Шаг 4/6: Выбор услуги*\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                            ["🎚️ Сведение", "🎵 Создание трека"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
                else:
                    await update.message.reply_text(
                        "*👑 Шаг 5/7: Выбор услуги*\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["🎤 Вокал", "🎸 Инструмент", "⏰ Аренда"],
                            ["🎚️ Сведение", "🎵 Создание трека"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
            return ADMIN_PROMO_SERVICE
        
        else:
            if promo_target_type == 'personal':
                if expiry is None:
                    await update.message.reply_text(
                        "*👑 Шаг 4/7: Выбор типа промокода*\n\n"
                        "*💰 % на все:*\n"
                        "• Скидка на все услуги\n\n"
                        "*🎯 % на услугу:*\n"
                        "• Скидка на конкретную услугу\n\n"
                        "*⏱️ Бесплатный час:*\n"
                        "• Бесплатный час для вокала/инструмента\n\n"
                        "*🎵 Бесплатная услуга:*\n"
                        "• Конкретная услуга бесплатно\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["💰 % на все", "🎯 % на услугу"],
                            ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
                else:
                    await update.message.reply_text(
                        "*👑 Шаг 5/8: Выбор типа промокода*\n\n"
                        "*💰 % на все:*\n"
                        "• Скидка на все услуги\n\n"
                        "*🎯 % на услугу:*\n"
                        "• Скидка на конкретную услугу\n\n"
                        "*⏱️ Бесплатный час:*\n"
                        "• Бесплатный час для вокала/инструмента\n\n"
                        "*🎵 Бесплатная услуга:*\n"
                        "• Конкретная услуга бесплатно\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["💰 % на все", "🎯 % на услугу"],
                            ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
            else:
                if expiry is None:
                    await update.message.reply_text(
                        "*👑 Шаг 3/6: Выбор типа промокода*\n\n"
                        "*💰 % на все:*\n"
                        "• Скидка на все услуги\n\n"
                        "*🎯 % на услугу:*\n"
                        "• Скидка на конкретную услугу\n\n"
                        "*⏱️ Бесплатный час:*\n"
                        "• Бесплатный час для вокала/инструмента\n\n"
                        "*🎵 Бесплатная услуга:*\n"
                        "• Конкретная услуга бесплатно\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["💰 % на все", "🎯 % на услугу"],
                            ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
                else:
                    await update.message.reply_text(
                        "*👑 Шаг 4/7: Выбор типа промокода*\n\n"
                        "*💰 % на все:*\n"
                        "• Скидка на все услуги\n\n"
                        "*🎯 % на услугу:*\n"
                        "• Скидка на конкретную услугу\n\n"
                        "*⏱️ Бесплатный час:*\n"
                        "• Бесплатный час для вокала/инструмента\n\n"
                        "*🎵 Бесплатная услуга:*\n"
                        "• Конкретная услуга бесплатно\n\n"
                        "*👇 Выберите подходящий вариант:*",
                        parse_mode="Markdown",
                        reply_markup=ReplyKeyboardMarkup([
                            ["💰 % на все", "🎯 % на услугу"],
                            ["⏱️ Бесплатный час", "🎵 Бесплатная услуга"],
                            ["↩️ Главное меню", "↩️ Назад"]
                        ], resize_keyboard=True, one_time_keyboard=True)
                    )
            return ADMIN_PROMO_TYPE
    
    try:
        value = int(text)
        
        if discount_type == "free_hours":
            if value < 1 or value > 24:
                raise ValueError("от 1 до 24")
        else:
            if value < 1 or value > 100:
                raise ValueError("от 1 до 100")
        
        context.user_data['discount_value'] = value
        
    except ValueError as e:
        await update.message.reply_text(
            "*❌ Неверный формат!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True)
        )
        return ADMIN_PROMO_VALUE
    
    return await admin_promo_confirm_show(update, context)

async def admin_promo_confirm_show(update: Update, context):
    """Показать подтверждение создания промокода"""
    promo_target_type = context.user_data.get('promo_target_type')
    promo_code = context.user_data.get('promo_code')
    discount_type = context.user_data.get('discount_type')
    discount_value = context.user_data.get('discount_value')
    target_service = context.user_data.get('target_service')
    expiry = context.user_data.get('expiry_date')
    target_display = context.user_data.get('target_display')
    
    # Форматируем бонус
    if discount_type == "percent_all":
        type_text = f"💰 {discount_value}% на всё"
    elif discount_type == "percent_service":
        service_name = PromoCodeManager.SERVICES.get(target_service, target_service)
        type_text = f"🎯 {discount_value}% на {service_name}"
    elif discount_type == "free_hours":
        hours_word = get_hours_word(discount_value)
        type_text = f"⏱️ {discount_value} бесплатных {hours_word} (вокал/инструмент)"
    else:  # free_service
        service_name = PromoCodeManager.SERVICES.get(target_service, target_service)
        type_text = f"🎵 Бесплатно: {service_name}"
    
    # Форматируем дату окончания с временем
    if not expiry:
        expiry_text = "♾️ Бессрочный"
    else:
        try:
            expiry_date_obj = datetime.strptime(expiry, '%Y-%m-%d %H:%M:%S')
            # Форматируем с временем до часов и минут
            expiry_text = f"⏱️ Действует до: {expiry_date_obj.strftime('%d.%m.%Y %H:%M')}"
        except Exception as e:
            logger.error(f"Ошибка форматирования даты: {e}")
            expiry_text = f"⏱️ Действует до: {expiry[:10]}"
    
    # Определяем номер шага для отображения
    if promo_target_type == 'personal':
        if expiry is None:
            if discount_type == "free_service":
                step_text = "👑 Шаг 6/6: Подтверждение"
            elif discount_type == "free_hours":
                step_text = "👑 Шаг 6/6: Подтверждение"
            elif discount_type == "percent_all":
                step_text = "👑 Шаг 6/6: Подтверждение"
            else:  # percent_service
                step_text = "👑 Шаг 7/7: Подтверждение"
        else:
            if discount_type == "free_service":
                step_text = "👑 Шаг 7/7: Подтверждение"
            elif discount_type == "free_hours":
                step_text = "👑 Шаг 7/7: Подтверждение"
            elif discount_type == "percent_all":
                step_text = "👑 Шаг 7/7: Подтверждение"
            else:  # percent_service
                step_text = "👑 Шаг 8/8: Подтверждение"
    else:  # global
        if discount_type == "free_service":
            if expiry is None:
                step_text = "👑 Шаг 5/5: Подтверждение"
            else:
                step_text = "👑 Шаг 6/6: Подтверждение"
        elif discount_type == "free_hours":
            if expiry is None:
                step_text = "👑 Шаг 5/5: Подтверждение"
            else:
                step_text = "👑 Шаг 6/6: Подтверждение"
        elif discount_type == "percent_all":
            if expiry is None:
                step_text = "👑 Шаг 5/5: Подтверждение"
            else:
                step_text = "👑 Шаг 6/6: Подтверждение"
        else:  # percent_service
            if expiry is None:
                step_text = "👑 Шаг 6/6: Подтверждение"
            else:
                step_text = "👑 Шаг 7/7: Подтверждение"
    
    # Формируем сообщение в зависимости от типа промокода
    if promo_target_type == 'personal':
        await update.message.reply_text(
            f"*{step_text}*\n\n"
            f"*✅ Проверьте данные:*\n\n"
            f"👤 Пользователь: {target_display}\n"
            f"🎟️ Код: `{promo_code}`\n"
            f"🎁 Бонус: {type_text}\n"
            f"⏰ Срок: {expiry_text}\n\n"
            f"*👇 Всё верно?*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Да, создать промокод", "✏️ Исправить данные"],
                ["❌ Отменить"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
    else:
        await update.message.reply_text(
            f"*{step_text}*\n\n"
            f"*✅ Проверьте данные:*\n\n"
            f"🌍 Тип: Общий для всех\n"
            f"🎟️ Код: `{promo_code}`\n"
            f"🎁 Бонус: {type_text}\n"
            f"⏰ Срок: {expiry_text}\n\n"
            f"*👇 Всё верно?*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Да, создать промокод", "✏️ Исправить данные"],
                ["❌ Отменить"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
    return ADMIN_PROMO_CONFIRM

@handle_errors_with_rate_limit
async def admin_promo_confirm(update: Update, context):
    """Подтверждение создания промокода с рассылкой пользователям"""
    text = update.message.text.strip()
    
    if text == "↩️ Главное меню" or text == "❌ Отменить":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "✏️ Исправить данные":
        await update.message.reply_text(
            "*👑 Шаг 1/8: Выбор типа промокода*\n\n"
            "*🌍 Общий промокод:*\n"
            "• Может использовать любой пользователь\n"
            "• Не требует ввода ID пользователя\n\n"
            "*👤 Персональный промокод:*\n"
            "• Только для конкретного пользователя\n"
            "• Потребуется ввести ID или username\n\n"
            "*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["🌍 Общий промокод", "👤 Персональный промокод"],
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_PROMO_START
    
    if text != "✅ Да, создать промокод":
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Да, создать промокод", "✏️ Исправить данные"],
                ["❌ Отменить"]
            ], resize_keyboard=True)
        )
        return ADMIN_PROMO_CONFIRM
    
    admin_id = str(update.effective_user.id)
    admin_username = update.effective_user.username or "Администратор"
    
    promo_data = {
        'code': context.user_data.get('promo_code'),
        'target_user_id': context.user_data.get('target_user_id'),
        'discount_type': context.user_data.get('discount_type'),
        'discount_value': context.user_data.get('discount_value'),
        'target_service': context.user_data.get('target_service'),
        'expiry_date': context.user_data.get('expiry_date')
    }
    
    # ПОЛУЧАЕМ USERNAME ДЛЯ ПЕРСОНАЛЬНОГО ПРОМОКОДА
    target_username = None
    if promo_data['target_user_id']:
        target_username = context.user_data.get('target_username')
        if not target_username or target_username == "Неизвестный":
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT username, first_name FROM users WHERE telegram_id = ?', (promo_data['target_user_id'],))
                    user_data = cursor.fetchone()
                    if user_data:
                        target_username = user_data[0] or user_data[1] or str(promo_data['target_user_id'])
                        context.user_data['target_username'] = target_username
            except Exception as e:
                logger.error(f"Ошибка получения username: {e}")
                target_username = str(promo_data['target_user_id'])
    
    success, message, promo_info = await PromoCodeManager.create_promo_code(admin_id, promo_data)
    
    if success:
        promo_type_display = "Персональный" if promo_data['target_user_id'] else "Общий"
        promo_bonus = PromoCodeManager.format_promo_info(promo_data)
        
        if promo_data['target_user_id']:
            target_info = context.user_data.get('target_display', 'Неизвестный')
            target_line = f"👤 Кому: {target_info}\n"
            
            try:
                await context.bot.send_message(
                    chat_id=int(promo_data['target_user_id']),
                    text=(
                        f"*🎉 Новый промокод!*\n\n"
                        f"*✨ Действует только для вас!*\n\n"
                        f"*🎟️ Промокод:* `{promo_data['code']}`\n"
                        f"*🎁 Бонус: {promo_bonus}\n\n*"
                        f"*🔥 Успейте активировать!*"
                    ),
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Уведомление отправлено пользователю {promo_data['target_user_id']}")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить уведомление: {e}")
        else:
            target_line = ""
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT telegram_id FROM users')
                all_users = cursor.fetchall()
            
            expiry_text = ""
            if promo_data['expiry_date']:
                try:
                    expiry = datetime.strptime(promo_data['expiry_date'], '%Y-%m-%d %H:%M:%S')
                    expiry_text = f"\n⏰ Действует до: {expiry.strftime('%d.%m.%Y')}"
                except:
                    pass
            
            broadcast_message = (
                f"*🎉 Новый промокод!*\n\n"
                f"*✨ Действует для всех пользователей!*\n\n"
                f"*🎟️ Промокод:* `{promo_data['code']}`\n"
                f"*🎁 Бонус: {promo_bonus}{expiry_text}*\n\n"
                f"*🔥 Успейте активировать!*"
            )
            
            success_count = 0
            fail_count = 0
            
            for user in all_users:
                user_telegram_id = user[0]
                try:
                    await context.bot.send_message(
                        chat_id=int(user_telegram_id),
                        text=broadcast_message,
                        parse_mode="Markdown"
                    )
                    success_count += 1
                    await asyncio.sleep(0.05)
                except Exception as e:
                    fail_count += 1
                    logger.error(f"❌ Не удалось отправить уведомление пользователю {user_telegram_id}: {e}")
            
            logger.info(f"✅ Рассылка промокода {promo_data['code']}: отправлено {success_count} пользователям, ошибок: {fail_count}")
            
            broadcast_info = f"\n📊 Рассылка: отправлено {success_count} пользователям"
            if fail_count > 0:
                broadcast_info += f"\n⚠️ Ошибок: {fail_count}"
        
        # ИСПРАВЛЕННОЕ СООБЩЕНИЕ ДЛЯ АДМИНИСТРАТОРА
        if promo_data['target_user_id']:
            if target_username and target_username != "Неизвестный":
                admin_message = f"*✅ Создан промокод для пользваотеля @{target_username}*"
            else:
                admin_message = f"*✅ Создан промокод для пользователя {promo_data['target_user_id']}*"
        else:
            admin_message = "*✅ Создан общий промокод*"
        
        await update.message.reply_text(
            admin_message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        
        logger.info(f"✅ Админ @{admin_username} создал промокод {promo_data['code']}")
        
    else:
        await update.message.reply_text(
            f"❌ Ошибка: {message}",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
    
    context.user_data.clear()
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def admin_promo_delete_start(update: Update, context):
    """Начало удаления промокода - показываем все промокоды"""
    user_id = update.effective_user.id
    
    logger.info(f"🔍 admin_promo_delete_start вызвана пользователем {user_id}")
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return
    
    context.user_data.clear()
    
    await show_promo_list(update, context)

async def show_promo_list(update: Update, context, edit_mode: bool = False, message_obj=None):
    """Показать список промокодов с кнопками по реальному ID и статусом использования"""
    
    logger.info("🔍 show_promo_list вызвана")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, code, discount_type, discount_value, target_service, expiry_date, target_user_id
            FROM promo_codes 
            WHERE is_active = 1
            ORDER BY id ASC
        ''')
        promos = cursor.fetchall()
    
    logger.info(f"🔍 Найдено активных промокодов: {len(promos)}")
    
    now = DateTimeUtils.now().replace(tzinfo=None)
    
    if not promos:
        message = "*📭 В системе нет активных промокодов*"
        
        if edit_mode and message_obj:
            await message_obj.edit_text(text=message, parse_mode="Markdown")
        else:
            await update.message.reply_text(message, parse_mode="Markdown")
        return
    
    # Группируем промокоды
    general_promos = []
    personal_promos = []
    
    for promo in promos:
        promo_id = promo[0]
        code = promo[1]
        discount_type = promo[2]
        discount_value = promo[3]
        target_service = promo[4]
        expiry_date = promo[5]
        target_user_id = promo[6]
        
        # Форматируем бонус
        if discount_type == "percent_all":
            bonus = f"{discount_value}% на всё"
        elif discount_type == "percent_service":
            service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренда", "сведение": "сведение", "трек": "трек"}
            bonus = f"{discount_value}% на {service_names.get(target_service, target_service)}"
        elif discount_type == "free_hours":
            hours_word = get_hours_word(discount_value)
            bonus = f"{discount_value} бесплатных {hours_word} (вокал/инструмент)"
        else:
            service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
            bonus = f"Бесплатно: {service_names.get(target_service, target_service)}"
        
        # Форматируем дату окончания
        if expiry_date:
            try:
                expiry = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
                if expiry > now:
                    formatted_date = expiry.strftime('%d.%m.%Y %H:%M')
                    bonus += f" (до {formatted_date})"
            except:
                pass
        
        promo_data = {
            'id': promo_id,
            'code': code,
            'bonus': bonus,
            'target_user_id': target_user_id
        }
        
        if target_user_id:
            # Проверяем статус использования промокода
            usage_status = "не использован"
            with db.get_connection() as conn2:
                cursor2 = conn2.cursor()
                cursor2.execute('''
                    SELECT u.status, b.is_mixing
                    FROM user_promo_usage u
                    LEFT JOIN bookings b ON u.booking_id = b.id
                    WHERE u.promo_code = ? AND u.user_id = ?
                    ORDER BY u.id DESC LIMIT 1
                ''', (code, target_user_id))
                usage = cursor2.fetchone()
                
                if usage:
                    status = usage[0]
                    is_mixing_booking = usage[1] if len(usage) > 1 else 0
                    
                    if status == 'used':
                        usage_status = "использован"
                    elif status == 'pending':
                        if is_mixing_booking == 1:
                            usage_status = "использован"
                        else:
                            usage_status = "ожидает прохождения"
                    elif status == 'active':
                        usage_status = "активен"
                
                cursor2.execute('SELECT username, first_name, unique_id FROM users WHERE telegram_id = ?', (target_user_id,))
                user_info = cursor2.fetchone()
                if user_info:
                    username, first_name, unique_id = user_info
                    promo_data['user_display'] = get_user_display_name({
                        'username': username,
                        'unique_id': unique_id,
                        'telegram_id': target_user_id
                    })
                else:
                    promo_data['user_display'] = "Неизвестный"
            
            promo_data['usage_status'] = usage_status
            personal_promos.append(promo_data)
        else:
            general_promos.append(promo_data)
    
    # Формируем сообщение
    message = "*🎟️ Список промокодов*\n\n"
    
    if general_promos:
        message += "*🌍 Общие промокоды:*\n\n"
        for promo in general_promos:
            message += f"#{promo['id']}. `{promo['code']}` — {promo['bonus']}\n\n"
    
    if personal_promos:
        if general_promos:
            message += "\n"
        message += "*👤 Персональные промокоды:*\n\n"
        for promo in personal_promos:
            status_text = f"({promo['usage_status']})"
            message += f"#{promo['id']}. `{promo['code']}` — {promo['bonus']} 👤 {promo['user_display']} {status_text}\n\n"
    
    message = message.rstrip('\n')
    
    # Сохраняем список в user_data
    context.user_data['promo_list'] = general_promos + personal_promos
    
    # Создаём кнопки
    keyboard = []
    for promo in general_promos + personal_promos:
        keyboard.append([InlineKeyboardButton(f"❌ Удалить #{promo['id']}", callback_data=f"admin_del_promo_{promo['id']}")])
    
    logger.info(f"🔍 Создано {len(keyboard)} кнопок удаления")
    
    if edit_mode and message_obj:
        await message_obj.edit_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )
    else:
        await update.message.reply_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )

@handle_errors_with_rate_limit
async def admin_promo_delete_callback_handler(update: Update, context):
    """Обработчик нажатия на кнопку удаления промокода"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    logger.info(f"🔍 admin_promo_delete_callback_handler: data={data}")
    
    if not data.startswith('admin_del_promo_'):
        logger.warning(f"❌ Неизвестный callback: {data}")
        return
    
    # Получаем реальный ID промокода
    try:
        promo_id = int(data.replace('admin_del_promo_', ''))
        logger.info(f"🔍 Удаление промокода с ID: {promo_id}")
    except ValueError:
        logger.error(f"❌ Ошибка: не удалось получить ID из {data}")
        await query.answer("❌ Ошибка формата данных!", show_alert=True)
        return
    
    # Получаем данные промокода из БД
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, code, discount_type, discount_value, target_service, expiry_date, target_user_id
            FROM promo_codes 
            WHERE id = ? AND is_active = 1
        ''', (promo_id,))
        promo = cursor.fetchone()
    
    if not promo:
        logger.warning(f"❌ Промокод с ID {promo_id} не найден или уже удалён")
        await query.answer("❌ Промокод не найден!", show_alert=True)
        await show_promo_list(update, context, edit_mode=True, message_obj=query.message)
        return
    
    promo_code = promo[1]
    discount_type = promo[2]
    discount_value = promo[3]
    target_service = promo[4]
    expiry_date = promo[5]
    target_user_id = promo[6]
    
    # Формируем бонус для отображения
    if discount_type == "percent_all":
        bonus = f"{discount_value}% на всё"
    elif discount_type == "percent_service":
        service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренда", "сведение": "сведение", "трек": "трек"}
        bonus = f"{discount_value}% на {service_names.get(target_service, target_service)}"
    elif discount_type == "free_hours":
        hours_word = get_hours_word(discount_value)
        bonus = f"{discount_value} бесплатных {hours_word} (вокал/инструмент)"
    else:
        service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
        bonus = f"Бесплатно: {service_names.get(target_service, target_service)}"
    
    if expiry_date:
        try:
            expiry = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
            now = DateTimeUtils.now().replace(tzinfo=None)
            if expiry > now:
                formatted_date = expiry.strftime('%d.%m.%Y %H:%M')
                bonus += f" (до {formatted_date})"
        except:
            pass
    
    promo_type = "персональный" if target_user_id else "общий"
    
    # Сохраняем в user_data
    context.user_data['delete_promo_id'] = promo_id
    context.user_data['delete_promo_code'] = promo_code
    
    # Показываем подтверждение
    message = (
        f"*⚠️ Вы уверены, что хотите удалить промокод?*\n\n"
        f"*📋 Детали:*\n"
        f"• ID: #{promo_id}\n"
        f"• Код: `{promo_code}`\n"
        f"• Тип: {promo_type}\n"
        f"• Бонус: {bonus}\n\n"
        f"*❌ Удалить промокод?*"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_confirm_del_{promo_id}"),
            InlineKeyboardButton("❌ Нет, оставить", callback_data="admin_cancel_del")
        ]
    ])
    
    await query.edit_message_text(
        text=message,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@handle_errors_with_rate_limit
async def admin_promo_delete_confirm_handler(update: Update, context):
    """Подтверждение удаления промокода"""
    query = update.callback_query
    data = query.data
    
    logger.info(f"🔍 admin_promo_delete_confirm_handler: data={data}")
    
    await query.answer()
    
    if data == "admin_cancel_del":
        logger.info("🔍 Пользователь отменил удаление")
        await show_promo_list(update, context, edit_mode=True, message_obj=query.message)
        return
    
    if data.startswith('admin_confirm_del_'):
        try:
            promo_id = int(data.replace('admin_confirm_del_', ''))
            logger.info(f"🔍 Подтверждение удаления промокода с ID: {promo_id}")
        except ValueError:
            logger.error(f"❌ Ошибка: не удалось получить ID из {data}")
            await query.edit_message_text(
                text="❌ Ошибка: неверный формат данных",
                parse_mode="Markdown"
            )
            return
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, code, target_user_id, discount_type, discount_value, target_service, expiry_date
                FROM promo_codes 
                WHERE id = ? AND is_active = 1
            ''', (promo_id,))
            promo = cursor.fetchone()
        
        if not promo:
            logger.warning(f"❌ Промокод с ID {promo_id} уже удалён")
            await query.answer("❌ Промокод уже удалён!", show_alert=True)
            await show_promo_list(update, context, edit_mode=True, message_obj=query.message)
            return
        
        promo_id_db, promo_code, target_user_id, discount_type, discount_value, target_service, expiry_date = promo
        admin_username = update.effective_user.username or "администратор"
        
        # ===== ПРОВЕРЯЕМ СТАТУС ПРОМОКОДА ДЛЯ ПОЛЬЗОВАТЕЛЯ =====
        should_notify_user = True
        user_status = None
        
        if target_user_id:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT status FROM user_promo_usage 
                    WHERE promo_code = ? AND user_id = ?
                    ORDER BY id DESC LIMIT 1
                ''', (promo_code, target_user_id))
                usage = cursor.fetchone()
                
                if usage:
                    user_status = usage[0]
                    # Если промокод использован или ожидает прохождения - НЕ отправляем уведомление
                    if user_status in ['used', 'pending']:
                        should_notify_user = False
                        logger.info(f"ℹ️ Промокод {promo_code} в статусе {user_status}, уведомление пользователю НЕ отправляется")
        
        # ===== УДАЛЯЕМ ПРОМОКОД =====
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Удаляем записи об использовании промокода у пользователей
            cursor.execute('DELETE FROM user_promo_usage WHERE promo_code = ?', (promo_code,))
            deleted_usage = cursor.rowcount
            logger.info(f"🗑️ Удалено {deleted_usage} записей об использовании промокода {promo_code}")
            
            # Деактивируем сам промокод
            cursor.execute('UPDATE promo_codes SET is_active = 0 WHERE id = ?', (promo_id_db,))
            conn.commit()
        
        logger.info(f"✅ Промокод #{promo_id} {promo_code} удалён админом {admin_username}")
        
        # ===== ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ ПОЛЬЗОВАТЕЛЮ ТОЛЬКО ЕСЛИ ПРОМОКОД БЫЛ В СТАТУСЕ 'active' =====
        if target_user_id and should_notify_user:
            # Формируем бонус для отображения
            if discount_type == "percent_all":
                bonus_text = f"{discount_value}% на всё"
            elif discount_type == "percent_service":
                service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренда", "сведение": "сведение", "трек": "трек"}
                bonus_text = f"{discount_value}% на {service_names.get(target_service, target_service)}"
            elif discount_type == "free_hours":
                hours_word = get_hours_word(discount_value)
                bonus_text = f"{discount_value} бесплатных {hours_word} (вокал/инструмент)"
            else:
                service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                bonus_text = f"Бесплатно: {service_names.get(target_service, target_service)}"
            
            if expiry_date:
                try:
                    expiry = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
                    if expiry > DateTimeUtils.now().replace(tzinfo=None):
                        bonus_text += f" (до {expiry.strftime('%d.%m.%Y')})"
                except:
                    pass
            
            try:
                await context.bot.send_message(
                    chat_id=int(target_user_id),
                    text=(
                        f"*❌ Промокод деактивирован администратором*\n\n"
                        f"*🎟️ Промокод:* `{promo_code}`\n"
                        f"*🎁 Бонус:* {bonus_text}\n\n"
                        f"*📞 По вопросам обращайтесь к администратору @mothman32*"
                    ),
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Уведомление об удалении промокода отправлено пользователю {target_user_id} (статус был active)")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить уведомление пользователю: {e}")
        else:
            if target_user_id and not should_notify_user:
                logger.info(f"ℹ️ Уведомление НЕ отправлено пользователю {target_user_id}, так как промокод был в статусе {user_status}")
        
        # Сообщение админу
        admin_message = f"*✅ Промокод #{promo_id}* `{promo_code}` *удалён из базы*"
        
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=admin_message,
            parse_mode="Markdown"
        )
        
        # Проверяем, остались ли промокоды
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM promo_codes WHERE is_active = 1')
            remaining_count = cursor.fetchone()[0]
        
        if remaining_count == 0:
            logger.info("📭 Активных промокодов не осталось")
            
            await query.edit_message_text(
                text="*📭 В системе нет активных промокодов*",
                parse_mode="Markdown"
            )
            
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=("*🏠 Возвращаемся в главное меню*\n\n"
                      "*👇 Выберите подходящий вариант:*"),
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            
            context.user_data.clear()
            return
        
        # Обновляем список
        await show_promo_list(update, context, edit_mode=True, message_obj=query.message)
        return
    
    logger.warning(f"❌ Неизвестный callback в confirm_handler: {data}")
    await query.answer("❌ Неизвестная команда!", show_alert=True)

@handle_errors_with_rate_limit
async def handle_admin_vinyl_start(update: Update, context):
    """Начало процесса управления пластинками"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    context.user_data['is_admin_vinyl'] = True
    context.user_data['_conversation_state'] = ADMIN_VINYL_USER_ID
    
    await update.message.reply_text(
        "*👑 Шаг 1/4: Ввод имени пользователя*\n\n"
        "*📋 Варианты ввода:*\n"
        "• Уникальный ID (MC...): `MC1772377294899374`\n"
        "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
        "*💡 Где найти Уникальный ID:*\n"
        "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
        "*✏️ Введите данные:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_VINYL_USER_ID

@handle_errors_with_rate_limit
async def handle_admin_vinyl_user_id(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_vinyl_user_id: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    search_term = text.replace('@', '').strip().lower()

    if not search_term:
        await update.message.reply_text(
            "❌ Введите корректные данные!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_VINYL_USER_ID

    found_user = None

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # ===== 1. Поиск по уникальному ID (MC...) =====
            if search_term.startswith("mc"):
                logger.info(f"🔍 Ищем по уникальному ID: {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, vinyls
                    FROM users WHERE LOWER(unique_id) = ?
                ''', (search_term,))
                found_user = cursor.fetchone()
                if found_user:
                    logger.info(f"✅ Найден по уникальному ID: {search_term}")

            # ===== 2. Поиск по username (точное совпадение) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (точное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, vinyls
                    FROM users WHERE LOWER(username) = ? OR LOWER(username) = ?
                ''', (search_term, f'@{search_term}'))
                found_user = cursor.fetchone()
                if found_user:
                    logger.info(f"✅ Найден по username (точное): {search_term}")

            # ===== 3. Поиск по username (частичное совпадение) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (частичное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, vinyls
                    FROM users WHERE 
                    LOWER(username) LIKE ? OR 
                    LOWER(username) LIKE ? OR
                    LOWER(first_name) LIKE ? OR
                    LOWER(unique_id) LIKE ?
                ''', (f'%{search_term}%', f'%@{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                found_user = cursor.fetchone()
                if found_user:
                    logger.info(f"✅ Найден по частичному совпадению: {search_term}")

            # ===== 4. Поиск по first_name =====
            if not found_user:
                logger.info(f"🔍 Ищем по имени: {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, vinyls
                    FROM users WHERE LOWER(first_name) LIKE ?
                ''', (f'%{search_term}%',))
                found_user = cursor.fetchone()
                if found_user:
                    logger.info(f"✅ Найден по имени: {search_term}")

            if not found_user:
                await update.message.reply_text(
                    f"*❌ Пользователь не найден!*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню"]
                    ], resize_keyboard=True)
                )
                return ADMIN_VINYL_USER_ID

            telegram_id, username, first_name, unique_id, vinyls = found_user
            
            display_name = username or first_name or unique_id
            
            context.user_data['target_vinyl_user_id'] = telegram_id
            context.user_data['target_vinyl_username'] = display_name
            context.user_data['target_vinyl_unique_id'] = unique_id
            context.user_data['target_vinyl_current'] = vinyls or 0

            logger.info(f"✅ Админ нашел пользователя: {unique_id} (TG: {telegram_id}), пластинок: {vinyls}")

    except Exception as e:
        logger.error(f"❌ Ошибка поиска пользователя: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            "❌ Ошибка при поиске пользователя!\n\n"
            "💡 Попробуйте позже",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_VINYL_USER_ID

    await update.message.reply_text(
        f"*👑 Шаг 2/4: Выбор действия*\n\n"
        f"*✅ Найден пользователь: @{context.user_data['target_vinyl_username']}*\n"
        f"*💿 Текущее количество пластинок: {context.user_data['target_vinyl_current']}*\n\n"
        f"*📋 Уникальный ID: {unique_id}*\n\n"
        f"*👇 Выберите подходящий вариант:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["➕ Начислить", "➖ Удалить"],
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_VINYL_ACTION

@handle_errors_with_rate_limit
async def handle_admin_vinyl_action(update: Update, context):
    """Выбор действия: начислить или удалить"""
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_vinyl_action: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        await update.message.reply_text(
            "*👑 Шаг 1/4: Ввод имени пользователя*\n\n"
            "*📋 Варианты ввода:*\n"
            "• Уникальный ID (MC...): `MC1772377294899374`\n"
            "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
            "*💡 Где найти Уникальный ID:*\n"
            "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
            "*✏️ Введите данные:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_VINYL_USER_ID
    
    if text not in ["➕ Начислить", "➖ Удалить"]:
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["➕ Начислить", "➖ Удалить"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_VINYL_ACTION
    
    context.user_data['vinyl_action'] = 'add' if text == "➕ Начислить" else 'remove'
    action_text = "добавить" if text == "➕ Начислить" else "удалить"
    
    await update.message.reply_text(
        f"*👑 Шаг 3/4: Ввод количества*\n\n"
        f"*📋 Форматы ввода:*\n"
        f"• `1000` - 1000 пластинок\n"
        f"• `100` - 100 пластинок\n\n"
        f"*✏️ Введите количество:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню", "↩️ Назад"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_VINYL_AMOUNT


@handle_errors_with_rate_limit
async def handle_admin_vinyl_amount(update: Update, context):
    """Ввод количества пластинок"""
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_vinyl_amount: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "↩️ Назад":
        username = context.user_data.get('target_vinyl_username')
        unique_id = context.user_data.get('target_vinyl_unique_id')
        current = context.user_data.get('target_vinyl_current', 0)
        
        await update.message.reply_text(
            f"*👑 Шаг 2/4: Выбор действия*\n\n"
            f"*✅ Найден пользователь: @{username}*\n"
            f"*💿 Текущее количество пластинок: {current}*\n\n"
            f"*📋 Уникальный ID: {unique_id}*\n\n"
            f"*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["➕ Начислить", "➖ Удалить"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_VINYL_ACTION
    
    try:
        amount = int(text)
        
        if amount <= 0:
            raise ValueError("Количество должно быть положительным")
        
        if amount > 1000000:
            raise ValueError("Слишком большое количество (макс. 1 000 000)")
        
        context.user_data['vinyl_amount'] = amount
        
    except ValueError as e:
        error_text = "Введите целое число"
        
        action_text = "добавить" if context.user_data.get('vinyl_action') == 'add' else "удалить"
        
        await update.message.reply_text(
            f"*❌ Неверный формат!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True)
        )
        return ADMIN_VINYL_AMOUNT
    
    return await show_vinyl_confirmation(update, context)


async def show_vinyl_confirmation(update: Update, context):
    """Показать подтверждение операции с пластинками"""
    
    username = context.user_data.get('target_vinyl_username')
    unique_id = context.user_data.get('target_vinyl_unique_id')
    current = context.user_data.get('target_vinyl_current', 0)
    amount = context.user_data.get('vinyl_amount')
    action = context.user_data.get('vinyl_action')
    
    action_text = "Добавить" if action == 'add' else "Удалить"
    new_total = current + amount if action == 'add' else max(0, current - amount)
    
    confirmation_text = (
        f"*👑 Шаг 4/4: Подтверждение*\n\n"
        f"*✅ Проверьте данные:*\n\n"
        f"*📋 Данные:*\n"
        f"• Пользователь: @{username}\n"
        f"• Уникальный ID: {unique_id}\n"
        f"• Текущее количество: {current} 💿\n"
        f"• Действие: {action_text} {amount} 💿\n"
        f"• После операции: {new_total} 💿\n\n"
        f"*👇 Всё верно?*"
    )
    
    await update.message.reply_text(
        confirmation_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["✅ Да, подтвердить", "✏️ Исправить данные"],
            ["❌ Отменить"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_VINYL_CONFIRM

@handle_errors_with_rate_limit
async def handle_admin_vinyl_confirm(update: Update, context):
    """Подтверждение операции с пластинками"""
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_vinyl_confirm: '{text}'")
    
    target_user_id = context.user_data.get('target_vinyl_user_id')
    target_username = context.user_data.get('target_vinyl_username')
    target_unique_id = context.user_data.get('target_vinyl_unique_id')
    current = context.user_data.get('target_vinyl_current', 0)
    amount = context.user_data.get('vinyl_amount')
    action = context.user_data.get('vinyl_action')
    admin_id = str(update.effective_user.id)
    admin_username = update.effective_user.username or "Администратор"
    
    if text == "↩️ Главное меню" or text == "❌ Отменить":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    if text == "✏️ Исправить данные":
        username = context.user_data.get('target_vinyl_username')
        unique_id = context.user_data.get('target_vinyl_unique_id')
        current = context.user_data.get('target_vinyl_current', 0)
        
        await update.message.reply_text(
            f"*👑 Шаг 2/4: Выбор действия*\n\n"
            f"*✅ Найден пользователь: @{username}*\n"
            f"*💿 Текущее количество пластинок: {current}*\n\n"
            f"*📋 Уникальный ID: {unique_id}*\n\n"
            f"*👇 Выберите подходящий вариант:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["➕ Начислить", "➖ Удалить"],
                ["↩️ Главное меню", "↩️ Назад"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_VINYL_ACTION
    
    if text != "✅ Да, подтвердить":
        await update.message.reply_text(
            "*❌ Пожалуйста, используйте кнопки! Выберите подходящий вариант из предложенных!*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Да, подтвердить", "✏️ Исправить данные"],
                ["❌ Отменить"]
            ], resize_keyboard=True, one_time_keyboard=True)
        )
        return ADMIN_VINYL_CONFIRM
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            if action == 'add':
                new_total = current + amount
                cursor.execute('''
                    UPDATE users SET vinyls = ? WHERE telegram_id = ?
                ''', (new_total, str(target_user_id)))
                action_text = "начислено"
                emoji = "➕"
            else:
                new_total = max(0, current - amount)
                cursor.execute('''
                    UPDATE users SET vinyls = ? WHERE telegram_id = ?
                ''', (new_total, str(target_user_id)))
                action_text = "удалено"
                emoji = "➖"
            
            conn.commit()
        
        await AchievementSystem.notify_level_change(str(target_user_id), current, new_total, context)
        
        await AchievementSystem.update_user_level(str(target_user_id), context)
        
        logger.info(f"✅ Админ @{admin_username} {action_text} {amount} пластинок пользователю {target_user_id} (было {current}, стало {new_total})")
        
        try:
            if action == 'add':
                user_message = (
                    f"*➕ Вам начислены пластинки!*\n\n"
                    f"*🎁 Количество: +{amount} 💿*\n"
                    f"*💰 Всего пластинок: {new_total} 💿*\n\n"
                    f"*👑 Администратор: @{admin_username}*\n\n"
                    f"*Продолжайте записываться! 🔥*"
                )
            else:
                user_message = (
                    f"*➖ У вас удалили пластинки*\n\n"
                    f"*📉 Количество: -{amount} 💿*\n"
                    f"*💰 Осталось пластинок: {new_total} 💿*\n\n"
                    f"*👑 Администратор: @{admin_username}*\n\n"
                    f"*📞 По вопросам обращайтесь к @mothman32*"
                )
            
            await context.bot.send_message(
                chat_id=int(target_user_id),
                text=user_message,
                parse_mode="Markdown"
            )
            logger.info(f"✅ Уведомление о пластинках отправлено пользователю {target_user_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление о пластинках: {e}")
        
        # ИЗМЕНЕННОЕ СООБЩЕНИЕ ДЛЯ АДМИНИСТРАТОРА
        admin_message = f"*✅ Пластинки изменены для пользователя @{target_username}*"
        
        await update.message.reply_text(
            admin_message,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении операции с пластинками: {e}")
        import traceback
        traceback.print_exc()
        
        await update.message.reply_text(
            f"❌ Ошибка при выполнении операции!\n\n"
            f"💡 Попробуйте еще раз или свяжитесь с разработчиком",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
    
    context.user_data.clear()
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def handle_admin_profile_start(update: Update, context):
    """Начало процесса просмотра профиля пользователя"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для этого действия!",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    context.user_data['is_admin_profile'] = True
    context.user_data['_conversation_state'] = ADMIN_PROFILE_USER_ID
    
    await update.message.reply_text(
        "*👑 Шаг 1/2: Ввод имени пользователя*\n\n"
        "*📋 Варианты ввода:*\n"
        "• Уникальный ID (MC...): `MC1772377294899374`\n"
        "• Username (с @ или без): `@mothman32` или `mothman32`\n\n"
        "*💡 Где найти Уникальный ID:*\n"
        "Попросите пользователя нажать 👤 \"Мой профиль\" и скопировать данные\n\n"
        "*✏️ Введите данные:*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["↩️ Главное меню"]
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ADMIN_PROFILE_USER_ID

@handle_errors_with_rate_limit
async def handle_admin_profile_user_id(update: Update, context):
    """Админ смотрит профиль пользователя (поиск только по @username и MC...)"""
    text = update.message.text.strip()
    logger.info(f"🔍 handle_admin_profile_user_id: '{text}'")
    
    if text == "↩️ Главное меню":
        context.user_data.clear()
        await update.message.reply_text(
            "*🏠 Возвращаемся в главное меню*\n\n"
            "*👇 Выберите подходящий вариант:*",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    search_term = text.replace('@', '').strip().lower()
    
    if not search_term:
        await update.message.reply_text(
            "*❌ Введите данные для поиска!*\n\n"
            "*📋 Варианты ввода:*\n"
            "• Уникальный ID (MC...): `MC1772377294899374`\n"
            "• Username (с @ или без): `@mothman32` или `mothman32`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["↩️ Главное меню"]
            ], resize_keyboard=True)
        )
        return ADMIN_PROFILE_USER_ID

    found_user = None
    search_method = ""

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # ===== 1. Поиск по уникальному ID (MC...) =====
            if search_term.startswith("mc"):
                logger.info(f"🔍 Ищем по уникальному ID: {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, vinyls, level, 
                           permanent_discount, temporary_discount, discount_expiry,
                           total_spent, registration_date, referred_by, referral_code
                    FROM users WHERE LOWER(unique_id) = ?
                ''', (search_term,))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "уникальному ID"

            # ===== 2. Поиск по username (точное совпадение) =====
            if not found_user:
                logger.info(f"🔍 Ищем по username (точное): {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, vinyls, level,
                           permanent_discount, temporary_discount, discount_expiry,
                           total_spent, registration_date, referred_by, referral_code
                    FROM users WHERE LOWER(username) = ? OR LOWER(username) = ?
                ''', (search_term, f'@{search_term}'))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "username (точное)"

            # ===== 3. Поиск по частичному совпадению =====
            if not found_user:
                logger.info(f"🔍 Ищем по частичному совпадению: {search_term}")
                cursor.execute('''
                    SELECT telegram_id, username, first_name, unique_id, vinyls, level,
                           permanent_discount, temporary_discount, discount_expiry,
                           total_spent, registration_date, referred_by, referral_code
                    FROM users WHERE 
                    LOWER(username) LIKE ? OR 
                    LOWER(first_name) LIKE ? OR
                    LOWER(unique_id) LIKE ?
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                found_user = cursor.fetchone()
                if found_user:
                    search_method = "частичному совпадению"

            if not found_user:
                await update.message.reply_text(
                    f"*❌ Пользователь не найден!*",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardMarkup([
                        ["↩️ Главное меню"]
                    ], resize_keyboard=True)
                )
                return ADMIN_PROFILE_USER_ID

            (telegram_id, username, first_name, unique_id, vinyls, level, 
             permanent_discount, temporary_discount, discount_expiry,
             total_spent, registration_date, referred_by, referral_code) = found_user
            
            username = username or first_name or "Неизвестный"
            vinyls = vinyls or 0
            level = level or 1
            total_spent = total_spent or 0
            
            logger.info(f"✅ Админ нашел пользователя по {search_method}: {unique_id} (TG: {telegram_id})")
            
            # Получаем информацию об уровне
            level_info = AchievementSystem.get_level_info(vinyls)
            current_level_name = level_info['current_level_name']
            current_discount = level_info['current_discount']
            
            # Получаем все записи пользователя
            cursor.execute('''
                SELECT 
                    is_contractual,
                    service,
                    date_str,
                    price,
                    status,
                    is_12_hours,
                    twelve_hours_type,
                    is_mixing,
                    mixing_type,
                    is_track_creation,
                    track_type,
                    is_admin_booking
                FROM bookings 
                WHERE telegram_id = ?
            ''', (str(telegram_id),))
            
            all_bookings = cursor.fetchall()
            
            # ===== СЧЁТЧИКИ =====
            studio_count = 0          # Записи в студии (completed + админские confirmed)
            contract_count = 0        # Договорные услуги (confirmed)
            total_spent_calc = 0      # Общая стоимость
            confirmed_count = 0       # Подтверждено (confirmed + completed)
            cancelled_count = 0       # Отменено пользователем (cancelled_by_user)
            
            for booking in all_bookings:
                (is_contractual, service, date_str, price, status, is_12_hours, 
                 twelve_hours_type, is_mixing, mixing_type, is_track_creation, track_type,
                 is_admin_booking) = booking
                
                status_lower = status.lower() if status else ""
                is_admin = is_admin_booking == 1
                is_contract = (
                    is_contractual == 1 or
                    'Не указана' in str(date_str) or 
                    'договорная' in str(date_str).lower()
                )
                
                # ===== ПОДСЧЁТ СТАТИСТИКИ =====
                if status_lower in ['confirmed', 'подтвержден']:
                    confirmed_count += 1
                elif status_lower == 'completed':
                    confirmed_count += 1
                elif status_lower == 'cancelled_by_user':
                    cancelled_count += 1
                
                # ===== ИСТОРИЯ ЗАПИСЕЙ И СТОИМОСТЬ =====
                # 1. Обычные записи: ТОЛЬКО completed
                if status_lower == 'completed' and not is_admin:
                    studio_count += 1
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
                            
                # 2. Админские записи: confirmed
                elif is_admin and status_lower in ['confirmed', 'подтвержден']:
                    if is_contract:
                        contract_count += 1
                    else:
                        studio_count += 1
                    
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
                            
                # 3. Договорные записи (не админские): confirmed
                elif is_contract and status_lower in ['confirmed', 'подтвержден'] and not is_admin:
                    contract_count += 1
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
                            
                # 4. Сведение/мастеринг: confirmed
                elif is_mixing == 1 and status_lower in ['confirmed', 'подтвержден']:
                    contract_count += 1
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
                            
                # 5. Создание альбома: confirmed
                elif is_track_creation == 1 and track_type and 'Альбом' in track_type and status_lower in ['confirmed', 'подтвержден']:
                    contract_count += 1
                    if price and price not in ['0', 'Договорная'] and 'договорная' not in str(price).lower():
                        try:
                            price_num = int(''.join(filter(str.isdigit, str(price))))
                            total_spent_calc += price_num
                        except:
                            pass
            
            # Обновляем total_spent если нужно
            if total_spent_calc != total_spent:
                cursor.execute('UPDATE users SET total_spent = ? WHERE telegram_id = ?', 
                             (total_spent_calc, str(telegram_id)))
                conn.commit()
                total_spent = total_spent_calc
            
            # ===== ЛИМИТЫ =====
            # Записей с датой: X/2
            cursor.execute('''
                SELECT COUNT(*) 
                FROM bookings 
                WHERE telegram_id = ? 
                AND status IN ('pending', 'confirmed', 'подтвержден')
                AND is_contractual = 0
                AND is_admin_booking = 0
                AND is_mixing = 0
                AND is_track_creation = 0
                AND date_str NOT LIKE '%Не указана%'
                AND date_str NOT LIKE '%договорная%'
                AND date_str != 'Запись в студии'
            ''', (str(telegram_id),))
            active_dated_count = cursor.fetchone()[0] or 0
            
            # Договорных записей: X/3 (ТОЛЬКО PENDING!)
            cursor.execute('''
                SELECT COUNT(*) 
                FROM bookings 
                WHERE telegram_id = ? 
                AND status = 'pending'
                AND (
                    is_contractual = 1
                    OR is_admin_booking = 1
                    OR is_mixing = 1
                    OR is_track_creation = 1
                    OR date_str LIKE '%Не указана%'
                    OR date_str LIKE '%договорная%'
                    OR date_str = 'Запись в студии'
                )
            ''', (str(telegram_id),))
            active_contract_count = cursor.fetchone()[0] or 0
            
            # ===== ПРОЦЕНТЫ =====
            total_processed = confirmed_count + cancelled_count
            approved_percentage = 0
            cancelled_percentage = 0
            
            if total_processed > 0:
                approved_percentage = int((confirmed_count / total_processed) * 100)
                cancelled_percentage = 100 - approved_percentage
            
            # Форматируем дату регистрации
            if registration_date:
                try:
                    reg_date_obj = datetime.strptime(registration_date, '%d.%m.%Y')
                    formatted_reg_date = reg_date_obj.strftime('%d.%m.%Y')
                except:
                    formatted_reg_date = registration_date
            else:
                formatted_reg_date = "Не указана"
        
        # ===== ФОРМИРУЕМ ТЕКСТ ПРОФИЛЯ ДЛЯ АДМИНА =====
        profile_text = (
            f"*👤 Профиль пользователя:*\n"
            f"• Username: @{username}\n"
            f"• Telegram ID: `{telegram_id}`\n"
            f"• Уникальный ID: `{unique_id}`\n"
            f"• Дата регистрации: {formatted_reg_date}\n\n"
            
            f"*💿 Реферальная программа:*\n"
            f"• Уровень: {current_level_name}\n"
            f"• Пластинок: {vinyls}\n"
            f"• Доступная скидка: {current_discount}%\n\n"
            
            f"*📊 История записей:*\n"
            f"• Записи в студии: {studio_count}\n"
            f"• Договорные услуги: {contract_count}\n"
            f"• Стоимость записей: {format_number(total_spent)} ₽\n\n"
            
            f"*📈 Статистика обработки записей:*\n"
            f"• Подтверждено: {format_number(confirmed_count)}\n"
            f"• Отменено пользователем: {format_number(cancelled_count)}\n"
            f"• Соотношение: {approved_percentage}% / {cancelled_percentage}%\n\n"
            
            f"*🎯 Текущие лимиты:*\n"
            f"• Записей с датой: {active_dated_count}/2\n"
            f"• Договорных записей: {active_contract_count}/3"
        )
        
        await update.message.reply_text(
            profile_text,
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
        
        logger.info(f"✅ Админ @{update.effective_user.username} просмотрел профиль пользователя @{username}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения профиля пользователя: {e}")
        import traceback
        traceback.print_exc()
        
        await update.message.reply_text(
            "❌ Ошибка при получении профиля пользователя!\n\n"
            "💡 Пожалуйста, попробуйте позже",
            parse_mode="Markdown",
            reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
        )
    
    context.user_data.clear()
    return ConversationHandler.END

@handle_errors_with_rate_limit
async def handle_unknown(update: Update, context):
    """Обработчик для неизвестных команд/сообщений - ПРОСТО ИГНОРИРУЕТ"""
    text = update.message.text.strip()
    
    # Проверяем, не является ли сообщение промокодом
    if text.lower().startswith('promo '):
        return await process_promo_code_message(update, context)
    
    # Проверяем, не является ли сообщение реферальным кодом
    if len(text) >= 6 and text.isalnum() and not text.startswith(('🎤', '📅', '💰', '👥', '📍', '🔔', '❓', '🏆', '🎁', '👑', '↩️', '✅', '✏️', '❌', '👨‍🔧', '💪', '☀️', '🌙', '🎵', '💿', '🎚️', '⏰', '🎸', '➕', '➖', '📅')):
        return await process_referral_code_message(update, context)
    
    # ===== УБРАНО СООБЩЕНИЕ О НЕИЗВЕСТНОЙ КОМАНДЕ =====
    # Просто игнорируем любое другое сообщение
    return

@handle_errors_with_rate_limit
async def check_coupons_command(update: Update, context):
    """Проверяет купоны пользователя (только для админа)"""
    user_id = str(update.effective_user.id)
    
    if user_id not in [str(admin_id) for admin_id in Config.ADMIN_IDS]:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("❌ Укажите ID пользователя\nПример: /checkcoupons 123456789")
        return
    
    target_id = args[0]
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_coupons WHERE user_id = ?', (target_id,))
            rows = cursor.fetchall()
            
            if rows:
                message = f"📊 Купоны пользователя {target_id}:\n\n"
                for row in rows:
                    message += f"ID: {row[0]}, Level: {row[2]}, Discount: {row[3]}%, Remaining: {row[4]}, Permanent: {row[5]}\n"
                await update.message.reply_text(message, parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ У пользователя {target_id} нет купонов!")
    except Exception as e:
        logger.error(f"Ошибка проверки купонов: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def button_callback_handler(update: Update, context):
    """Обработчик всех inline-кнопок"""
    query = update.callback_query
    
    try:
        data = query.data
        user_id = update.effective_user.id
        
        logger.info(f"🔍 button_callback_handler: data={data}, user_id={user_id}")
        
        # ===== ВАЖНО: ОТВЕЧАЕМ НА ВСЕ CALLBACK СРАЗУ (УБИРАЕТ ПЕСОЧНЫЕ ЧАСЫ) =====
        await query.answer()
        
        # Проверка блокировки для не-админов
        if user_id not in Config.ADMIN_IDS:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT is_blocked, blocked_until FROM users WHERE telegram_id = ?', (str(user_id),))
                result = cursor.fetchone()
                if result:
                    is_blocked, blocked_until = result
                    if is_blocked == 1:
                        if blocked_until:
                            try:
                                blocked_time = datetime.strptime(blocked_until, '%Y-%m-%d %H:%M:%S')
                                now = DateTimeUtils.now().replace(tzinfo=None)
                                if blocked_time > now:
                                    time_left = blocked_time - now
                                    hours = time_left.seconds // 3600
                                    minutes = (time_left.seconds % 3600) // 60
                                    time_text = f"{hours} ч. {minutes} мин." if hours > 0 and minutes > 0 else f"{hours} ч." if hours > 0 else f"{minutes} мин."
                                    await query.edit_message_text(text=f"🔒 Вы заблокированы!\n\n⏳ До разблокировки осталось: {time_text}\n\n📞 По вопросам обращайтесь к администратору: @mothman32", parse_mode="Markdown")
                                    return
                                else:
                                    cursor.execute('UPDATE users SET is_blocked = 0, blocked_until = NULL WHERE telegram_id = ?', (str(user_id),))
                                    conn.commit()
                            except:
                                await query.edit_message_text(text=f"🔒 Вы заблокированы!\n\n⏳ Тип блокировки: Навсегда\n\n📞 По вопросам обращайтесь к администратору: @mothman32", parse_mode="Markdown")
                                return
                        else:
                            await query.edit_message_text(text=f"🔒 Вы заблокированы!\n\n⏳ Тип блокировки: Навсегда\n\n📞 По вопросам обращайтесь к администратору: @mothman32", parse_mode="Markdown")
                            return
        
        # ========== РЕФЕРАЛЫ ==========
        if data == "enter_referral_code":
            await enter_referral_code_callback(update, context)
            return
        
        if data == "show_my_referrals":
            await show_my_referrals_callback(update, context)
            return
        
        if data == "back_to_referral":
            await back_to_referral_callback(update, context)
            return
        
        # ========== ОТМЕНА ЗАПИСИ (ПОЛЬЗОВАТЕЛЬ) ==========
        if data == "keep_booking":
            await show_my_bookings_in_message(query.message, context, update.effective_user.id)
            return
        
        if data == "back_to_bookings":
            await show_my_bookings_in_message(query.message, context, update.effective_user.id)
            return
        
        # ========== ВЫРУЧКА ==========
        if data.startswith('revenue_'):
            await handle_revenue_period_selection(update, context)
            return
        
        # ========== ПРОМОКОДЫ ==========
        if data.startswith('promo_'):
            await promo_callback_handler(update, context)
            return
        
        if data.startswith('admin_del_promo_'):
            await admin_promo_delete_callback_handler(update, context)
            return
        
        if data.startswith('admin_confirm_del_') or data == "admin_cancel_del":
            await admin_promo_delete_confirm_handler(update, context)
            return
        
        # ========== АДМИНСКАЯ ОТМЕНА ==========
        if data.startswith('admin_cancel_confirm_'):
            await admin_cancel_confirm_handler(update, context)
            return
        
        if data == "admin_cancel_keep":
            target_user_id = context.user_data.get('target_user_id')
            if target_user_id:
                await show_my_bookings_in_message(query.message, context, target_user_id)
            return
        
        if data.startswith('admin_cancel_') and data != "admin_cancel_keep":
            await admin_cancel_callback_handler(update, context)
            return
        
        # ========== УДАЛЕНИЕ ДОСТИЖЕНИЙ ==========
        if data.startswith('admin_remove_achievement_'):
            if data.startswith('admin_remove_achievement_confirm_'):
                await admin_remove_achievement_confirm(update, context)
                return
            if data.startswith('admin_remove_achievement_cancel'):
                await admin_remove_achievement_cancel(update, context)
                return
            await admin_remove_achievement_callback(update, context)
            return
        
        # ========== ПОДТВЕРЖДЕНИЕ ЗАПИСИ АДМИНОМ ==========
        if data.startswith('confirm_'):
            booking_id = int(data.split('_')[1])
            chat_id = query.message.chat_id
            message_id = query.message.message_id
            
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception as e:
                logger.error(f"Ошибка при ответе на callback: {e}")
            
            asyncio.create_task(process_booking_confirmation(
                booking_id=booking_id,
                admin_id=user_id,
                context=context,
                chat_id=chat_id,
                message_id=message_id
            ))
            return
        
        # ========== ОТКЛОНЕНИЕ ЗАПИСИ ==========
        if data.startswith('reject_'):
            booking_id = int(data.split('_')[1])
            chat_id = query.message.chat_id
            message_id = query.message.message_id
            
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception as e:
                logger.error(f"Ошибка при ответе на callback: {e}")
            
            asyncio.create_task(process_booking_rejection(
                booking_id=booking_id,
                admin_id=user_id,
                context=context,
                chat_id=chat_id,
                message_id=message_id
            ))
            return
        
        # ========== ОТМЕНА ЗАПИСИ ПОЛЬЗОВАТЕЛЕМ (ЗАПРОС) ==========
        if data.startswith('cancel_'):
            try:
                parts = data.split('_')
                if len(parts) < 2 or parts[1] == 'cancel':
                    await query.edit_message_text(
                        text="*❌ Ошибка формата!*",
                        parse_mode="Markdown"
                    )
                    return
                booking_id = int(parts[1])
                
                # ===== ПОЛУЧАЕМ ПОЛНЫЕ ДАННЫЕ ДЛЯ ПОДТВЕРЖДЕНИЯ =====
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, service, date_str, time_slot, status, price, is_mixing,
                               is_12_hours, is_track_creation, is_contractual, duration,
                               name, contact, level_discount_percent, promo_discount_percent,
                               promo_code_used, level_coupon_id, twelve_hours_type, mixing_type, track_type
                        FROM bookings WHERE id = ? AND telegram_id = ?
                    ''', (booking_id, str(user_id)))
                    booking = cursor.fetchone()
                    
                    if not booking:
                        await query.edit_message_text(
                            text="*❌ Запись не найдена!*",
                            parse_mode="Markdown"
                        )
                        return
                    
                    current_status = booking[4]
                    if current_status in ['cancelled', 'cancelled_by_user', 'completed', 'rejected']:
                        await query.edit_message_text(
                            text="*❌ Эту запись уже нельзя отменить!*",
                            parse_mode="Markdown"
                        )
                        return
                    
                    service = booking[1]
                    date_str = booking[2] or "дата не указана"
                    time_slot = booking[3] or "время не указано"
                    price = booking[5] or "0"
                    is_mixing = booking[6] == 1 if len(booking) > 6 and booking[6] else False
                    is_12_hours = booking[7] == 1 if len(booking) > 7 and booking[7] else False
                    is_track_creation = booking[8] == 1 if len(booking) > 8 and booking[8] else False
                    is_contractual = booking[9] == 1 if len(booking) > 9 and booking[9] else False
                    duration = booking[10] if len(booking) > 10 else 0
                    name = booking[11] if booking[11] else "Не указан"
                    contact = booking[12] if booking[12] else "Не указан"
                    level_discount_percent = booking[13] if len(booking) > 13 else 0
                    promo_discount_percent = booking[14] if len(booking) > 14 else 0
                    promo_code_used = booking[15] if len(booking) > 15 else None
                    level_coupon_id = booking[16] if len(booking) > 16 else None
                    twelve_hours_type = booking[17] if len(booking) > 17 else None
                    mixing_type = booking[18] if len(booking) > 18 else None
                    track_type = booking[19] if len(booking) > 19 else None
                    
                    if is_contractual:
                        await query.edit_message_text(
                            text="*❌ Договорные записи нельзя отменить!*",
                            parse_mode="Markdown"
                        )
                        return
                    
                    if is_mixing:
                        await query.edit_message_text(
                            text="*❌ Сведение/мастеринг нельзя отменить!*",
                            parse_mode="Markdown"
                        )
                        return
                    
                    hours_until = DateTimeUtils.get_hours_until_booking(date_str, time_slot)
                    
                    # ===== ПРОВЕРКА НА 12 ЧАСОВ =====
                    if hours_until < 12 and hours_until != -1 and not is_12_hours and not is_track_creation:
                        error_text = (
                            f"*❌ Отмена записи недоступна!*\n\n"
                            f"*⏰ До начала менее 12 часов*\n\n"
                            f"*📋 Детали записи #{booking_id}:*\n"
                            f"• Услуга: {service}\n"
                            f"• Дата: {date_str}\n"
                            f"• Время: {time_slot}\n"
                        )
                        if price != '0':
                            error_text += f"• Стоимость: {price}₽\n"
                        error_text += f"\n*📞 Для отмены обратитесь к администратору @mothman32*"
                        
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("↩️ Вернуться к списку", callback_data="back_to_bookings")]
                        ])
                        
                        await query.edit_message_text(
                            text=error_text,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                        return
                    
                    safe_name = SecurityUtils.safe_markdown_text(name)
                    safe_contact = SecurityUtils.safe_markdown_text(contact)
                    
                    # ===== ФОРМИРУЕМ ТЕКСТ СКИДКИ ПО УРОВНЮ =====
                    coupon_text = ""
                    if level_discount_percent and level_discount_percent > 0:
                        if level_coupon_id:
                            cursor.execute('''
                                SELECT level, discount_percent FROM user_coupons WHERE id = ?
                            ''', (level_coupon_id,))
                            coupon_info = cursor.fetchone()
                            if coupon_info:
                                level, discount = coupon_info
                                coupon_text = f"• Купон уровня {level}: {discount}%"
                            else:
                                coupon_text = f"• Скидка по уровню: {level_discount_percent}%"
                        else:
                            coupon_text = f"• Скидка по уровню: {level_discount_percent}%"
                    
                    # ===== ФОРМИРУЕМ ТЕКСТ ПРОМОКОДА =====
                    promo_text = ""
                    if promo_code_used:
                        cursor.execute('''
                            SELECT discount_type, discount_value, target_service 
                            FROM promo_codes WHERE code = ?
                        ''', (promo_code_used,))
                        promo_info = cursor.fetchone()
                        if promo_info:
                            discount_type, discount_value, target_service = promo_info
                            if discount_type == 'percent_all':
                                promo_text = f"• Промокод: {discount_value}% на всё (код: {promo_code_used})"
                            elif discount_type == 'percent_service':
                                service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                                promo_text = f"• Промокод: {discount_value}% на {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                            elif discount_type == 'free_hours':
                                if discount_value == 1:
                                    hours_text = "1 час"
                                elif discount_value in [2, 3, 4]:
                                    hours_text = f"{discount_value} часа"
                                else:
                                    hours_text = f"{discount_value} часов"
                                promo_text = f"• Промокод: {hours_text} бесплатно (код: {promo_code_used})"
                            elif discount_type == 'free_service':
                                service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                                promo_text = f"• Промокод: бесплатно: {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                    
                    # ===== ФОРМАТИРУЕМ ДАТУ И ВРЕМЯ =====
                    clean_date_display = date_str
                    if clean_date_display and '(' in clean_date_display:
                        clean_date_display = clean_date_display.split('(')[0].strip()
                    if clean_date_display and clean_date_display[0] in "🟢🟡🟠🔴⚪️":
                        clean_date_display = clean_date_display[2:].strip()
                    
                    time_display = time_slot
                    if time_display and '-' in time_display:
                        time_display = DateTimeUtils.format_time_for_display(time_display)
                    
                    # ===== ФОРМИРУЕМ СТАТУС ДЛЯ ОТОБРАЖЕНИЯ =====
                    status_lower = current_status.lower() if current_status else ""
                    if 'pending' in status_lower or 'ожидает' in status_lower:
                        status_display = "Ожидает подтверждения"
                    elif 'confirmed' in status_lower or 'подтвержден' in status_lower:
                        status_display = "Подтверждена"
                    elif 'completed' in status_lower or 'завершен' in status_lower:
                        status_display = "Завершена"
                    elif 'cancelled' in status_lower or 'отменен' in status_lower:
                        status_display = "Отменена"
                    elif 'rejected' in status_lower or 'отклонен' in status_lower:
                        status_display = "Отклонена"
                    else:
                        status_display = current_status or "Неизвестен"
                    
                    # ===== ФОРМИРУЕМ ТЕКСТ ПОДТВЕРЖДЕНИЯ =====
                    confirm_text = f"*⚠️ Вы уверены, что хотите отменить запись?*\n\n"
                    confirm_text += f"*📋 Детали записи #{booking_id}:*\n"
                    confirm_text += f"• Имя: {safe_name}\n"
                    confirm_text += f"• Контакт: {safe_contact}\n"
                    confirm_text += f"• Услуга: {service}\n"
                    
                    if is_12_hours and twelve_hours_type:
                        safe_type = SecurityUtils.safe_markdown_text(str(twelve_hours_type))
                        confirm_text += f"• Тип: {safe_type}\n"
                    elif is_mixing and mixing_type:
                        safe_type = SecurityUtils.safe_markdown_text(str(mixing_type))
                        confirm_text += f"• Тип: {safe_type}\n"
                    elif is_track_creation and track_type:
                        safe_type = SecurityUtils.safe_markdown_text(str(track_type))
                        confirm_text += f"• Тип: {safe_type}\n"
                    
                    if clean_date_display and 'Не указана' not in clean_date_display:
                        confirm_text += f"• Дата: {clean_date_display}\n"
                    
                    if time_display and time_display not in ['Не указано', 'Не указано (договорная)']:
                        if is_12_hours:
                            confirm_text += f"• Время: {time_display} (12 часов)\n"
                        elif duration and duration > 0:
                            formatted_duration = PriceCalculator.format_hours_ru(duration)
                            confirm_text += f"• Время: {time_display} ({formatted_duration})\n"
                        else:
                            confirm_text += f"• Время: {time_display}\n"
                    
                    if price and price != '0':
                        if 'договорная' in str(price).lower():
                            confirm_text += "• Стоимость: Договорная\n"
                        else:
                            try:
                                price_int = int(float(price))
                                formatted_price = f"{price_int}₽"
                                confirm_text += f"• Стоимость: {formatted_price}\n"
                            except:
                                confirm_text += f"• Стоимость: {price}₽\n"
                    
                    if coupon_text:
                        confirm_text += f"{coupon_text}\n"
                    
                    if promo_text:
                        confirm_text += f"{promo_text}\n"
                    
                    confirm_text += f"• Статус: {status_display}\n"
                    
                    confirm_text += f"\n*❌ Отменить запись?*"
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Да, отменить", callback_data=f"do_cancel_{booking_id}"),
                         InlineKeyboardButton("❌ Нет, оставить", callback_data="keep_booking")]
                    ])
                    await query.edit_message_text(text=confirm_text, parse_mode="Markdown", reply_markup=keyboard)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при запросе отмены: {e}")
                await query.edit_message_text(
                    text="*❌ Ошибка при отмене!*",
                    parse_mode="Markdown"
                )
            return
        
        # ========== ВЫПОЛНЕНИЕ ОТМЕНЫ ПОЛЬЗОВАТЕЛЕМ ==========
        if data.startswith('do_cancel_'):
            try:
                parts = data.split('_')
                if len(parts) < 3:
                    await query.edit_message_text(
                        text="*❌ Ошибка формата!*",
                        parse_mode="Markdown"
                    )
                    return
                booking_id = int(parts[2])
                
                # ===== ПОКАЗЫВАЕМ ПРОЦЕСС ОТМЕНЫ =====
                await query.edit_message_text(
                    text=f"⏳ Отмена записи #{booking_id}...",
                    parse_mode="Markdown"
                )
                
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT status, telegram_id, service, is_mixing, name, contact, date_str, time_slot, price,
                               is_12_hours, is_track_creation, duration, is_contractual, level_coupon_id,
                               promo_code_used, mixing_type, twelve_hours_type, track_type
                        FROM bookings WHERE id = ? AND telegram_id = ?
                    ''', (booking_id, str(user_id)))
                    booking = cursor.fetchone()
                    
                    if not booking:
                        await query.edit_message_text(
                            text="*❌ Запись не найдена!*",
                            parse_mode="Markdown"
                        )
                        return
                    
                    current_status = booking[0]
                    telegram_id_db = booking[1]
                    service = booking[2]
                    is_mixing = booking[3] == 1 if booking[3] else False
                    name = booking[4] if booking[4] else "Не указан"
                    contact = booking[5] if booking[5] else "Не указан"
                    date_str = booking[6] if booking[6] else ""
                    time_slot = booking[7] if booking[7] else ""
                    price = booking[8] if booking[8] else "0"
                    is_12_hours = booking[9] == 1 if len(booking) > 9 and booking[9] else False
                    is_track_creation = booking[10] == 1 if len(booking) > 10 and booking[10] else False
                    duration = booking[11] if len(booking) > 11 else 0
                    is_contractual = booking[12] == 1 if len(booking) > 12 else False
                    level_coupon_id = booking[13] if len(booking) > 13 else None
                    promo_code_used = booking[14] if len(booking) > 14 else None
                    mixing_type = booking[15] if len(booking) > 15 else None
                    twelve_hours_type = booking[16] if len(booking) > 16 else None
                    track_type = booking[17] if len(booking) > 17 else None
                    
                    if current_status in ['cancelled', 'cancelled_by_user', 'completed', 'rejected']:
                        await query.edit_message_text(
                            text="*❌ Эту запись уже нельзя отменить!*",
                            parse_mode="Markdown"
                        )
                        return
                    
                    if is_mixing:
                        await query.edit_message_text(
                            text="*❌ Сведение/мастеринг нельзя отменить!*",
                            parse_mode="Markdown"
                        )
                        return
                    
                    if is_contractual:
                        await query.edit_message_text(
                            text="*❌ Договорные записи нельзя отменить!*",
                            parse_mode="Markdown"
                        )
                        return
                    
                    hours_until = DateTimeUtils.get_hours_until_booking(date_str, time_slot)
                    
                    if hours_until < 12 and hours_until != -1 and not is_12_hours and not is_track_creation:
                        await query.edit_message_text(
                            text=(
                                f"*❌ Отмена записи недоступна!*\n\n"
                                f"*⏰ До начала менее 12 часов*\n\n"
                                f"*📞 Для отмены обратитесь к администратору @mothman32*"
                            ),
                            parse_mode="Markdown"
                        )
                        return
                    
                    # ===== ФОРМИРУЕМ ТЕКСТ КУПОНА =====
                    coupon_text = ""
                    if level_coupon_id:
                        cursor.execute('''
                            SELECT level, discount_percent FROM user_coupons WHERE id = ?
                        ''', (level_coupon_id,))
                        coupon_info = cursor.fetchone()
                        if coupon_info:
                            level, discount = coupon_info
                            coupon_text = f"• Купон уровня {level}: {discount}%"
                    
                    # ===== ФОРМИРУЕМ ТЕКСТ ПРОМОКОДА =====
                    promo_text = ""
                    if promo_code_used:
                        cursor.execute('''
                            SELECT discount_type, discount_value, target_service 
                            FROM promo_codes WHERE code = ?
                        ''', (promo_code_used,))
                        promo_info = cursor.fetchone()
                        
                        if promo_info:
                            discount_type, discount_value, target_service = promo_info
                            
                            if discount_type == 'percent_all':
                                promo_text = f"• Промокод: {discount_value}% на всё (код: {promo_code_used})"
                            elif discount_type == 'percent_service':
                                service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                                promo_text = f"• Промокод: {discount_value}% на {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                            elif discount_type == 'free_hours':
                                if discount_value == 1:
                                    hours_text = "1 час"
                                elif discount_value in [2, 3, 4]:
                                    hours_text = f"{discount_value} часа"
                                else:
                                    hours_text = f"{discount_value} часов"
                                promo_text = f"• Промокод: {hours_text} бесплатно (код: {promo_code_used})"
                            elif discount_type == 'free_service':
                                service_names = {"вокал": "вокал", "инструмент": "инструмент", "аренда": "аренду", "сведение": "сведение", "трек": "трек"}
                                promo_text = f"• Промокод: бесплатно: {service_names.get(target_service, target_service)} (код: {promo_code_used})"
                    
                    # ===== ЛОГИКА КУПОНА ПРИ ОТМЕНЕ =====
                    if level_coupon_id:
                        cursor.execute('SELECT remaining_uses, is_permanent FROM user_coupons WHERE id = ?', (level_coupon_id,))
                        coupon_check = cursor.fetchone()
                        
                        if coupon_check:
                            remaining_uses, is_permanent = coupon_check
                            
                            if remaining_uses == 0 and not is_permanent:
                                logger.info(f"ℹ️ Купон {level_coupon_id} уже использован, не возвращаем при отмене")
                            else:
                                if hours_until >= 12 or hours_until == -1:
                                    cursor.execute('UPDATE user_coupons SET remaining_uses = remaining_uses + 1 WHERE id = ? AND is_permanent = 0', (level_coupon_id,))
                                    logger.info(f"🔄 Купон {level_coupon_id} ВОЗВРАЩЁН при отмене пользователем (> 12ч) #{booking_id}")
                                else:
                                    cursor.execute('DELETE FROM user_coupons WHERE id = ?', (level_coupon_id,))
                                    logger.info(f"🔥 Купон {level_coupon_id} СГОРЕЛ при отмене пользователем (< 12ч) #{booking_id}")
                    
                    # Обработка промокода
                    handle_promo_code_on_cancellation(booking_id, str(user_id), hours_until, context)
                    
                    # Получаем текущие пластинки
                    cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(user_id),))
                    vinyl_row = cursor.fetchone()
                    old_vinyls = vinyl_row[0] if vinyl_row else 0
                    
                    # Проверяем, были ли начислены пластинки
                    try:
                        cursor.execute('ALTER TABLE bookings ADD COLUMN vinyls_awarded INTEGER DEFAULT 0')
                        conn.commit()
                    except:
                        pass
                    
                    cursor.execute('SELECT vinyls_awarded FROM bookings WHERE id = ?', (booking_id,))
                    award_row = cursor.fetchone()
                    was_awarded = award_row[0] == 1 if award_row else False
                    
                    # Списываем пластинки если были начислены
                    if was_awarded and not is_mixing:
                        cursor.execute('UPDATE users SET vinyls = vinyls - 25 WHERE telegram_id = ? AND vinyls >= 25', (str(user_id),))
                        cursor.execute('UPDATE bookings SET vinyls_awarded = 0 WHERE id = ?', (booking_id,))
                        logger.info(f"💰 Списано 25 пластинок у {user_id} за отмену записи #{booking_id}")
                        
                        cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(user_id),))
                        new_vinyl_row = cursor.fetchone()
                        new_vinyls = new_vinyl_row[0] if new_vinyl_row else 0
                        await AchievementSystem.notify_level_change(str(user_id), old_vinyls, new_vinyls, context)
                    
                    # Обновляем статус записи
                    cursor.execute('UPDATE bookings SET status = "cancelled_by_user" WHERE id = ?', (booking_id,))
                    cursor.execute('DELETE FROM notifications WHERE booking_id = ?', (booking_id,))
                    
                    # ================================================================
                    # ===== ИСПРАВЛЕННАЯ ОЧИСТКА КЭША =====
                    # ================================================================
                    if date_str:
                        clean_date = date_str.split('(')[0].strip()
                        if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                            clean_date = clean_date[2:].strip()
                        
                        # Очищаем текущую дату
                        MemoryCache.invalidate_date(clean_date)
                        
                        # Если запись кросс-ночная - очищаем предыдущий и следующий день
                        if time_slot and '-' in time_slot:
                            try:
                                start_str, end_str = time_slot.split('-')
                                start_hour_check = int(start_str.strip())
                                end_hour_check = int(end_str.strip())
                                
                                if end_hour_check <= start_hour_check:
                                    day, month, year = map(int, clean_date.split('.'))
                                    current_date = datetime(year, month, day)
                                    
                                    # Следующий день
                                    next_date = current_date + timedelta(days=1)
                                    MemoryCache.invalidate_date(next_date.strftime("%d.%m.%Y"))
                                    
                                    # Предыдущий день
                                    prev_date = current_date - timedelta(days=1)
                                    MemoryCache.invalidate_date(prev_date.strftime("%d.%m.%Y"))
                            except:
                                pass
                    
                    conn.commit()
                    await AchievementSystem.check_and_award_achievements(str(user_id), context, None)
                    await AchievementSystem.update_user_level(str(user_id), context)
                
                # ===== ФОРМАТИРУЕМ ДАННЫЕ ДЛЯ СООБЩЕНИЯ =====
                safe_name = SecurityUtils.safe_markdown_text(name)
                safe_contact = SecurityUtils.safe_markdown_text(contact)
                
                clean_date_display = date_str
                if clean_date_display and '(' in clean_date_display:
                    clean_date_display = clean_date_display.split('(')[0].strip()
                if clean_date_display and clean_date_display[0] in "🟢🟡🟠🔴⚪️":
                    clean_date_display = clean_date_display[2:].strip()
                
                time_display = time_slot
                if time_display and '-' in time_display:
                    time_display = DateTimeUtils.format_time_for_display(time_display)
                
                # ===== ОТПРАВКА ОТДЕЛЬНОГО СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЮ =====
                try:
                    user_message = f"*✅ Запись #{booking_id} успешно отменена!*\n\n"
                    user_message += f"*✨ Благодарим вас, {safe_name}!*\n\n"
                    user_message += f"*📋 Детали отменённой записи №{booking_id}:*\n"
                    user_message += f"• Имя: {safe_name}\n"
                    user_message += f"• Контакт: {safe_contact}\n"
                    user_message += f"• Услуга: {service}\n"
                    
                    if is_12_hours and twelve_hours_type:
                        safe_type = SecurityUtils.safe_markdown_text(str(twelve_hours_type))
                        user_message += f"• Тип: {safe_type}\n"
                    elif is_mixing and mixing_type:
                        safe_type = SecurityUtils.safe_markdown_text(str(mixing_type))
                        user_message += f"• Тип: {safe_type}\n"
                    elif is_track_creation and track_type:
                        safe_type = SecurityUtils.safe_markdown_text(str(track_type))
                        user_message += f"• Тип: {safe_type}\n"
                    
                    if clean_date_display and 'Не указана' not in clean_date_display:
                        user_message += f"• Дата: {clean_date_display}\n"
                    
                    if time_display and time_display not in ['Не указано', 'Не указано (договорная)']:
                        if is_12_hours:
                            user_message += f"• Время: {time_display} (12 часов)\n"
                        elif duration and duration > 0:
                            formatted_duration = PriceCalculator.format_hours_ru(duration)
                            user_message += f"• Время: {time_display} ({formatted_duration})\n"
                        else:
                            user_message += f"• Время: {time_display}\n"
                    
                    if price and price != '0':
                        if 'договорная' in str(price).lower():
                            user_message += "• Стоимость: Договорная\n"
                        else:
                            try:
                                price_int = int(float(price))
                                user_message += f"• Стоимость: {price_int}₽\n"
                            except:
                                user_message += f"• Стоимость: {price}₽\n"
                    
                    if coupon_text:
                        user_message += f"{coupon_text}\n"
                    
                    if promo_text:
                        user_message += f"{promo_text}\n"
                    
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=user_message,
                        parse_mode="Markdown"
                    )
                    logger.info(f"✅ Сообщение об отмене отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки сообщения об отмене: {e}")
                
                # ===== ОТПРАВКА УВЕДОМЛЕНИЯ АДМИНАМ =====
                clean_date_for_admin = date_str
                if clean_date_for_admin and '(' in clean_date_for_admin:
                    clean_date_for_admin = clean_date_for_admin.split('(')[0].strip()
                if clean_date_for_admin and clean_date_for_admin[0] in "🟢🟡🟠🔴⚪️":
                    clean_date_for_admin = clean_date_for_admin[2:].strip()
                
                clean_time_for_admin = time_slot
                if clean_time_for_admin and '-' in clean_time_for_admin:
                    clean_time_for_admin = DateTimeUtils.format_time_for_display(clean_time_for_admin)
                
                admin_message = f"*❌ Пользователь отменил запись #{booking_id}*\n\n"
                admin_message += f"👤 Пользователь: {name}\n"
                admin_message += f"📱 Контакт: {contact}\n"
                admin_message += f"🎧 Услуга: {service}\n"
                
                if clean_date_for_admin and 'Не указана' not in clean_date_for_admin:
                    admin_message += f"📅 Дата: {clean_date_for_admin}\n"
                
                if clean_time_for_admin and clean_time_for_admin not in ['Не указано', 'Не указано (договорная)']:
                    if duration and duration > 0:
                        formatted_duration = PriceCalculator.format_hours_ru(duration)
                        admin_message += f"⏰ Время: {clean_time_for_admin} ({formatted_duration})\n"
                    else:
                        admin_message += f"⏰ Время: {clean_time_for_admin}\n"
                
                if price and price != '0':
                    if 'договорная' in str(price).lower():
                        admin_message += f"💰 Стоимость: Договорная\n"
                    else:
                        try:
                            price_int = int(float(price))
                            formatted_price = f"{price_int:,}₽".replace(',', ' ')
                            admin_message += f"💰 Стоимость: {formatted_price}\n"
                        except:
                            admin_message += f"💰 Стоимость: {price}₽\n"
                
                admin_message += f"\n*⏳ Статус: Отменена пользователем*"
                
                for admin_id in Config.ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            chat_id=int(admin_id), 
                            text=admin_message, 
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Уведомление об отмене отправлено админу {admin_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")
                
                # Показываем сообщение об успешной отмене и обновляем список записей
                await query.edit_message_text(
                    text=f"*✅ Запись #{booking_id} успешно отменена!*",
                    parse_mode="Markdown"
                )
                
                # Обновляем список записей
                await show_my_bookings_in_message(query.message, context, update.effective_user.id)
                
            except Exception as e:
                logger.error(f"❌ Ошибка выполнения отмены: {e}")
                import traceback
                traceback.print_exc()
                await query.edit_message_text(
                    text="*❌ Ошибка при отмене записи!*\n\nПожалуйста, попробуйте позже или обратитесь к администратору.",
                    parse_mode="Markdown"
                )
            return
        
        logger.warning(f"⚠️ Неизвестный callback: {data}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка callback: {e}")
        import traceback
        traceback.print_exc()
        try:
            await query.edit_message_text(
                text="*❌ Произошла ошибка!*\n\nПожалуйста, попробуйте позже.",
                parse_mode="Markdown"
            )
        except:
            pass

@handle_errors_with_rate_limit
async def debug_add_vinyls(update: Update, context):
    """Прямой вызов add_vinyls_for_booking с диагностикой"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("❌ /debugadd 1")
        return
    
    booking_id = int(args[0])
    
    await update.message.reply_text(f"🔍 Прямой вызов add_vinyls_for_booking для #{booking_id}...")
    
    try:
        import sqlite3
        conn = sqlite3.connect(db.db_path, timeout=10.0)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,))
        row = cursor.fetchone()
        
        if not row:
            await update.message.reply_text(f"❌ Запись #{booking_id} не найдена!")
            conn.close()
            return
        
        columns = [description[0] for description in cursor.description]
        data = dict(zip(columns, row))
        conn.close()
        
        booking_data = {
            'id': data.get('id'),
            'telegram_id': data.get('telegram_id'),
            'status': data.get('status'),
            'service': data.get('service'),
            'date_str': data.get('date_str'),
            'time_slot': data.get('time_slot'),
            'name': data.get('name'),
            'contact': data.get('contact'),
            'price': data.get('price'),
            'duration': data.get('duration'),
            'is_mixing': data.get('is_mixing', 0),
            'is_admin_booking': data.get('is_admin_booking', 0),
            'is_contractual': data.get('is_contractual', 0),
            'is_12_hours': data.get('is_12_hours', 0),
            'is_track_creation': data.get('is_track_creation', 0),
            'twelve_hours_type': data.get('twelve_hours_type'),
            'track_type': data.get('track_type')
        }
        
        # Отправляем сообщение БЕЗ маркдауна
        msg = f"📋 Данные для начисления:\n\n"
        msg += f"id: {booking_data['id']}\n"
        msg += f"telegram_id: {booking_data['telegram_id']}\n"
        msg += f"status: {booking_data['status']}\n"
        msg += f"service: {booking_data['service']}\n"
        msg += f"date_str: {booking_data['date_str']}\n"
        msg += f"time_slot: {booking_data['time_slot']}\n"
        msg += f"is_admin_booking: {booking_data['is_admin_booking']}\n"
        msg += f"is_contractual: {booking_data['is_contractual']}\n"
        msg += f"is_mixing: {booking_data['is_mixing']}\n"
        msg += f"is_12_hours: {booking_data['is_12_hours']}\n"
        msg += f"is_track_creation: {booking_data['is_track_creation']}\n\n"
        msg += "Пытаюсь начислить..."
        
        await update.message.reply_text(msg)
        
        # ПРЯМОЙ ВЫЗОВ
        result, new_vinyls = await AchievementSystem.add_vinyls_for_booking(
            str(booking_data['telegram_id']), 
            context, 
            booking_data
        )
        
        if result:
            await update.message.reply_text(
                f"✅ УСПЕШНО!\n\n"
                f"💰 Всего пластинок: {new_vinyls} 💿",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ НЕ УДАЛОСЬ!\n\n"
                f"add_vinyls_for_booking вернула False\n"
                f"Проверь логи на наличие ошибок."
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ ОШИБКА:\n\n{str(e)[:300]}")
        import traceback
        traceback.print_exc()

async def process_booking_confirmation(booking_id: int, admin_id: int, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    """Фоновая обработка подтверждения записи с созданием уведомлений и начислением пластинок"""
    try:
        logger.info(f"🔄 Начинаем обработку подтверждения записи #{booking_id}")
        
        with db.get_connection(timeout=30.0) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT telegram_id, name, contact, service, date_str, time_slot, price,
                       is_mixing, is_contractual, is_admin_booking, status,
                       level_discount_percent, promo_discount_percent, promo_code_used,
                       duration, start_hour, end_hour, with_engineer, is_12_hours, twelve_hours_type,
                       is_track_creation, track_type, mixing_type, free_service_applied,
                       level_coupon_id
                FROM bookings WHERE id = ?
            ''', (booking_id,))
            result = cursor.fetchone()
            
            if not result:
                logger.error(f"❌ Запись #{booking_id} не найдена")
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text="❌ Запись не найдена!", parse_mode="Markdown"
                )
                return
            
            (telegram_id, name, contact, service, date_str, time_slot, price,
             is_mixing, is_contractual, is_admin_booking, current_status,
             level_discount_percent, promo_discount_percent, promo_code_used,
             duration, start_hour, end_hour, with_engineer, is_12_hours, twelve_hours_type,
             is_track_creation, track_type, mixing_type, free_service_applied,
             level_coupon_id) = result
            
            if current_status in ['confirmed', 'подтвержден']:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text="✅ Запись уже подтверждена!", parse_mode="Markdown"
                )
                return
            
            if current_status in ['rejected', 'отклонен']:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text="❌ Запись уже отклонена!", parse_mode="Markdown"
                )
                return
            
            cursor.execute('UPDATE bookings SET status = "confirmed" WHERE id = ?', (booking_id,))
            
            # ================================================================
            # ===== ОЧИЩАЕМ КЭШ ДЛЯ ВСЕХ ЗАТРОНУТЫХ ДАТ =====
            # ================================================================
            if date_str and 'Не указана' not in date_str:
                clean_date = date_str.split('(')[0].strip()
                if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                    clean_date = clean_date[2:].strip()
                
                # Очищаем текущую дату
                MemoryCache.invalidate_date(clean_date)
                
                # Если запись кросс-ночная - очищаем предыдущий и следующий день
                if time_slot and '-' in time_slot:
                    try:
                        start_str, end_str = time_slot.split('-')
                        start_hour_check = int(start_str.strip())
                        end_hour_check = int(end_str.strip())
                        
                        if end_hour_check <= start_hour_check:
                            day, month, year = map(int, clean_date.split('.'))
                            current_date = datetime(year, month, day)
                            
                            # Следующий день
                            next_date = current_date + timedelta(days=1)
                            MemoryCache.invalidate_date(next_date.strftime("%d.%m.%Y"))
                            
                            # Предыдущий день
                            prev_date = current_date - timedelta(days=1)
                            MemoryCache.invalidate_date(prev_date.strftime("%d.%m.%Y"))
                    except:
                        pass
            
            # ===== СЖИГАЕМ КУПОН ДЛЯ СВЕДЕНИЯ (трек 2500₽) =====
            if is_mixing == 1 and not is_contractual and level_coupon_id:
                cursor.execute('DELETE FROM user_coupons WHERE id = ?', (level_coupon_id,))
                logger.info(f"🔥 Купон {level_coupon_id} сгорел при подтверждении сведения #{booking_id}")
            
            conn.commit()
            
            # ===== НАЧИСЛЯЕМ ПЛАСТИНКИ ДЛЯ ДОГОВОРНЫХ ЗАПИСЕЙ И СВЕДЕНИЯ/МАСТЕРИНГА =====
            if is_contractual == 1 or is_mixing == 1 or is_admin_booking == 1:
                booking_data_for_vinyls = {
                    'id': booking_id,
                    'telegram_id': telegram_id,
                    'is_admin_booking': is_admin_booking,
                    'is_contractual': is_contractual,
                    'status': 'confirmed',
                    'service': service,
                    'is_mixing': is_mixing,
                    'date_str': date_str
                }
                
                vinyls_added, new_vinyls = await AchievementSystem.add_vinyls_for_booking(
                    str(telegram_id), context, booking_data_for_vinyls
                )
                
                if vinyls_added:
                    logger.info(f"✅ Пользователю {telegram_id} начислено +25 пластинок за {service} #{booking_id}")
            
            # ===== ПРОВЕРЯЕМ РЕФЕРАЛЬНЫЙ БОНУС =====
            if not is_admin_booking:
                try:
                    with db.get_connection() as conn_ref:
                        cursor_ref = conn_ref.cursor()
                        
                        cursor_ref.execute('''
                            CREATE TABLE IF NOT EXISTS booking_referral_bonuses (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id TEXT NOT NULL,
                                referrer_id TEXT NOT NULL,
                                bonus_type TEXT NOT NULL,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        conn_ref.commit()
                        
                        cursor_ref.execute('SELECT referred_by FROM users WHERE telegram_id = ?', (str(telegram_id),))
                        referred_data = cursor_ref.fetchone()
                        
                        if referred_data and referred_data[0]:
                            cursor_ref.execute('''
                                SELECT COUNT(*) FROM booking_referral_bonuses 
                                WHERE user_id = ? AND referrer_id = (SELECT telegram_id FROM users WHERE referral_code = ?)
                            ''', (str(telegram_id), referred_data[0]))
                            already_awarded_bonus = cursor_ref.fetchone()[0] > 0
                            
                            if not already_awarded_bonus:
                                cursor_ref.execute('SELECT telegram_id FROM users WHERE referral_code = ?', (referred_data[0],))
                                referrer = cursor_ref.fetchone()
                                
                                if referrer:
                                    referrer_id = referrer[0]
                                    
                                    cursor_ref.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(referrer_id),))
                                    referrer_vinyl_row = cursor_ref.fetchone()
                                    referrer_old_vinyls = referrer_vinyl_row[0] if referrer_vinyl_row else 0
                                    
                                    cursor_ref.execute('UPDATE users SET vinyls = vinyls + 25 WHERE telegram_id = ?', (str(referrer_id),))
                                    
                                    cursor_ref.execute('INSERT INTO booking_referral_bonuses (user_id, referrer_id, bonus_type) VALUES (?, ?, ?)', (str(telegram_id), str(referrer_id), 'first_booking'))
                                    
                                    conn_ref.commit()
                                    
                                    cursor_ref.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(referrer_id),))
                                    referrer_new_vinyl_row = cursor_ref.fetchone()
                                    referrer_new_vinyls = referrer_new_vinyl_row[0] if referrer_new_vinyl_row else 0
                                    
                                    logger.info(f"🎉 Рефереру {referrer_id} начислено +25 пластинок за реферала {telegram_id}")
                                    
                                    try:
                                        await context.bot.send_message(
                                            chat_id=int(referrer_id),
                                            text=(
                                                f"*🎉 Добавлено 25 пластинок за реферала!*\n\n"
                                                f"*✨ Продолжайте приглашать друзей! 🔥*\n\n"
                                                f"*💰 Пластинок после начисления: {referrer_new_vinyls} 💿*"
                                            ),
                                            parse_mode="Markdown"
                                        )
                                    except Exception as e:
                                        logger.error(f"Не удалось отправить уведомление рефереру: {e}")
                                    
                                    await AchievementSystem.check_and_award_achievements(str(referrer_id), context, None)
                                    await AchievementSystem.update_user_level(str(referrer_id), context)
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки реферального бонуса: {e}")
        
        # ===== ОТПРАВКА СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЮ =====
        # ===== ОЧИЩАЕМ УСЛУГУ ОТ СМАЙЛИКОВ =====
        clean_service = clean_service_text(service)
        
        # ===== ОЧИЩАЕМ ДАТУ ОТ СМАЙЛИКОВ =====
        clean_date = date_str
        if clean_date:
            for emoji in ['🟢', '🟡', '🟠', '🔴', '⚪️']:
                clean_date = clean_date.replace(emoji, '').strip()
            if '(' in clean_date:
                clean_date = clean_date.split('(')[0].strip()
        
        display_time = time_slot
        if time_slot and '-' in time_slot:
            display_time = DateTimeUtils.format_time_for_display(time_slot)
        
        # ===== ОЧИЩАЕМ ТИП ОТ СМАЙЛИКОВ =====
        clean_type = ""
        if is_12_hours and twelve_hours_type:
            clean_type = clean_service_text(twelve_hours_type)
        elif is_mixing and mixing_type:
            clean_type = clean_service_text(mixing_type)
        elif is_track_creation and track_type:
            clean_type = clean_service_text(track_type)
        
        # ===== ФОРМИРУЕМ ТЕКСТ СКИДОК =====
        discount_lines = []
        if level_discount_percent and level_discount_percent > 0:
            discount_lines.append(f"• Скидка по уровню: {level_discount_percent}%")
        if promo_discount_percent and promo_discount_percent > 0:
            discount_lines.append(f"• Промокод: {promo_discount_percent}%")
        if promo_code_used:
            discount_lines.append(f"• Код промокода: {promo_code_used}")
        if free_service_applied == 1 and promo_code_used:
            discount_lines.append(f"• Промокод: Бесплатная услуга")
        
        discount_text = ""
        if discount_lines:
            discount_text = "\n" + "\n".join(discount_lines)
        
        # ===== НОВЫЙ ФОРМАТ СООБЩЕНИЯ =====
        user_msg_lines = [
            f"*✅ Ваша заявка подтверждена!*",
            "",
            f"*📋 Детали вашей записи:*",
            f"• Номер записи: #{booking_id}",
            f"• Имя: {name}",
            f"• Контакт: {contact}",
            f"• Услуга: {clean_service}"
        ]
        
        if clean_type:
            user_msg_lines.append(f"• Тип: {clean_type}")
        
        if clean_date and 'Не указана' not in clean_date:
            user_msg_lines.append(f"• Дата: {clean_date}")
        
        if display_time and display_time not in ['Не указано', 'Не указано (договорная)']:
            if is_12_hours:
                user_msg_lines.append(f"• Время: {display_time} (12 часов)")
            elif is_track_creation:
                user_msg_lines.append(f"• Время: {display_time} (4 часа)")
            elif duration and duration > 0:
                formatted_duration = PriceCalculator.format_hours_ru(duration)
                user_msg_lines.append(f"• Время: {display_time} ({formatted_duration})")
            else:
                user_msg_lines.append(f"• Время: {display_time}")
        
        # ===== ЦЕНА =====
        if is_12_hours == 1:
            rent_price = 6500 if twelve_hours_type and 'Ночь' in twelve_hours_type else 7000
            if price and price != '0' and price != str(rent_price):
                try:
                    price_int = int(float(price))
                    user_msg_lines.append(f"• Стоимость: {price_int}₽ + залог (по договору)")
                except:
                    user_msg_lines.append(f"• Стоимость: {rent_price}₽ + залог (по договору)")
            else:
                user_msg_lines.append(f"• Стоимость: {rent_price}₽ + залог (по договору)")
        elif (is_mixing == 1 and mixing_type and "Альбом" in mixing_type) or \
             (is_track_creation == 1 and track_type and "Альбом" in track_type):
            user_msg_lines.append(f"• Стоимость: Договорная")
        elif free_service_applied == 1:
            user_msg_lines.append(f"• Стоимость: 0₽")
        elif price == '0' and promo_code_used:
            user_msg_lines.append(f"• Стоимость: 0₽")
        elif price and price != '0' and 'договорная' not in str(price).lower():
            try:
                price_int = int(float(price))
                user_msg_lines.append(f"• Стоимость: {price_int}₽")
            except:
                user_msg_lines.append(f"• Стоимость: {price}₽")
        else:
            if is_mixing == 1:
                user_msg_lines.append(f"• Стоимость: 2500₽")
            elif is_track_creation == 1:
                user_msg_lines.append(f"• Стоимость: 9000₽")
            else:
                user_msg_lines.append(f"• Стоимость: Договорная")
        
        if discount_text:
            user_msg_lines.append(discount_text.lstrip('\n'))
        
        user_msg_lines.append("")
        user_msg_lines.append(f"*📍 Адрес: Садовая ул., 91*")
        user_msg_lines.append(f"*📞 Контакты: @mothman32*")
        
        user_message = "\n".join(user_msg_lines)
        
        await context.bot.send_message(
            chat_id=int(telegram_id),
            text=user_message,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Сообщение пользователю {telegram_id} отправлено")
        
        # ===== СОЗДАНИЕ УВЕДОМЛЕНИЙ =====
        if (clean_date and 'Не указана' not in clean_date and 
            display_time and display_time not in ['Не указано', 'Не указано (договорная)']):
            
            booking_datetime = DateTimeUtils.get_booking_datetime(clean_date, display_time)
            
            if booking_datetime:
                service_type = None
                
                if is_12_hours == 1:
                    service_type = 'rental'
                    intervals = [48, 24, 12]
                elif is_track_creation == 1:
                    service_type = 'track_creation'
                    intervals = [48, 24, 12]
                elif is_mixing == 1:
                    service_type = 'mixing'
                    intervals = []
                else:
                    service_lower = service.lower() if service else ""
                    if 'вокал' in service_lower:
                        if with_engineer == 1:
                            service_type = 'vocal_with_engineer'
                        else:
                            service_type = 'vocal_without_engineer'
                    elif 'инструмент' in service_lower:
                        if with_engineer == 1:
                            service_type = 'instruments_with_engineer'
                        else:
                            service_type = 'instruments_without_engineer'
                    else:
                        service_type = 'default'
                    
                    intervals = Config.NOTIFICATION_INTERVALS.get(service_type, [24, 12, 3])
                
                for hours_before in intervals:
                    success = NotificationManager.create_notification(
                        booking_id=booking_id,
                        user_id=str(telegram_id),
                        service_type=service_type,
                        booking_datetime=booking_datetime,
                        notification_type=f"{hours_before}h_before",
                        hours_before=hours_before
                    )
                    if success:
                        logger.info(f"✅ Создано уведомление за {hours_before} часов для записи #{booking_id}")
        
        # ===== ОБНОВЛЯЕМ СООБЩЕНИЕ АДМИНА =====
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=f"*✅ Запись #{booking_id} подтверждена!*", parse_mode="Markdown"
        )
        
        logger.info(f"✅ Запись #{booking_id} успешно подтверждена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в process_booking_confirmation: {e}")
        import traceback
        traceback.print_exc()
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text="❌ Ошибка при подтверждении", parse_mode="Markdown"
            )
        except:
            pass
            
async def process_booking_rejection(booking_id: int, admin_id: int, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    """Фоновая обработка отклонения записи - ВОЗВРАЩАЕМ ПРОМОКОД И КУПОН"""
    try:
        logger.info(f"🔄 Начинаем обработку отклонения записи #{booking_id}")
        
        with db.get_connection(timeout=30.0) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT telegram_id, name, contact, service, date_str, time_slot, price,
                       is_mixing, status, duration, is_12_hours, twelve_hours_type,
                       level_discount_percent, promo_discount_percent, promo_code_used,
                       with_engineer, mixing_type, is_track_creation, track_type, is_contractual,
                       start_hour, end_hour, free_service_applied, level_coupon_id
                FROM bookings WHERE id = ?
            ''', (booking_id,))
            result = cursor.fetchone()
            
            if not result:
                logger.error(f"❌ Запись #{booking_id} не найдена")
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text="❌ Запись не найдена!", parse_mode="Markdown"
                )
                return
            
            (telegram_id, name, contact, service, date_str, time_slot, price,
             is_mixing, current_status, duration, is_12_hours, twelve_hours_type,
             level_discount_percent, promo_discount_percent, promo_code_used,
             with_engineer, mixing_type, is_track_creation, track_type, is_contractual,
             start_hour, end_hour, free_service_applied, level_coupon_id) = result
            
            if current_status in ['confirmed', 'подтвержден']:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text="✅ Запись уже подтверждена!", parse_mode="Markdown"
                )
                return
            
            if current_status in ['rejected', 'отклонен']:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text="❌ Запись уже отклонена!", parse_mode="Markdown"
                )
                return
            
            # ================================================================
            # ===== ОЧИЩАЕМ КЭШ ДЛЯ ВСЕХ ЗАТРОНУТЫХ ДАТ =====
            # ================================================================
            if date_str and 'Не указана' not in date_str:
                clean_date = date_str.split('(')[0].strip()
                if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
                    clean_date = clean_date[2:].strip()
                
                # Очищаем текущую дату
                MemoryCache.invalidate_date(clean_date)
                
                # Если запись кросс-ночная - очищаем предыдущий и следующий день
                if time_slot and '-' in time_slot:
                    try:
                        start_str, end_str = time_slot.split('-')
                        start_hour_check = int(start_str.strip())
                        end_hour_check = int(end_str.strip())
                        
                        if end_hour_check <= start_hour_check:
                            day, month, year = map(int, clean_date.split('.'))
                            current_date = datetime(year, month, day)
                            
                            # Следующий день
                            next_date = current_date + timedelta(days=1)
                            MemoryCache.invalidate_date(next_date.strftime("%d.%m.%Y"))
                            
                            # Предыдущий день
                            prev_date = current_date - timedelta(days=1)
                            MemoryCache.invalidate_date(prev_date.strftime("%d.%m.%Y"))
                    except:
                        pass
            
            # ===== ВОЗВРАЩАЕМ ПРОМОКОД (ЕСЛИ БЫЛ) =====
            if promo_code_used:
                cursor.execute('''
                    UPDATE user_promo_usage 
                    SET status = 'active', booking_id = NULL 
                    WHERE promo_code = ? AND user_id = ?
                ''', (promo_code_used, str(telegram_id)))
                logger.info(f"🔄 Промокод {promo_code_used} ВОЗВРАЩЁН пользователю {telegram_id} при отклонении записи #{booking_id}")
            
            # ===== ВОЗВРАЩАЕМ КУПОН (ЕСЛИ БЫЛ) =====
            if level_coupon_id:
                cursor.execute('SELECT id FROM user_coupons WHERE id = ?', (level_coupon_id,))
                exists = cursor.fetchone()
                
                if exists:
                    cursor.execute('''
                        UPDATE user_coupons SET remaining_uses = remaining_uses + 1 
                        WHERE id = ? AND is_permanent = 0
                    ''', (level_coupon_id,))
                    logger.info(f"🔄 Купон {level_coupon_id} ВОЗВРАЩЁН (обновлён) при отклонении записи #{booking_id}")
                else:
                    cursor.execute('''
                        INSERT INTO user_coupons (user_id, level, discount_percent, remaining_uses, is_permanent)
                        VALUES (?, 1, 50, 1, 0)
                    ''', (str(telegram_id),))
                    logger.info(f"🔄 Создан НОВЫЙ купон 50% для пользователя {telegram_id} при отклонении записи #{booking_id}")
            
            cursor.execute('UPDATE bookings SET status = "rejected" WHERE id = ?', (booking_id,))
            cursor.execute('DELETE FROM notifications WHERE booking_id = ?', (booking_id,))
            conn.commit()
        
        # ===== ОТПРАВЛЯЕМ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ =====
        # ===== ОЧИЩАЕМ УСЛУГУ ОТ СМАЙЛИКОВ =====
        clean_service = clean_service_text(service)
        
        # ===== ОЧИЩАЕМ ДАТУ ОТ СМАЙЛИКОВ =====
        clean_date = date_str
        if clean_date:
            for emoji in ['🟢', '🟡', '🟠', '🔴', '⚪️']:
                clean_date = clean_date.replace(emoji, '').strip()
            if '(' in clean_date:
                clean_date = clean_date.split('(')[0].strip()
        
        display_time = time_slot
        if time_slot and '-' in time_slot:
            display_time = DateTimeUtils.format_time_for_display(time_slot)
        
        # ===== ОЧИЩАЕМ ТИП ОТ СМАЙЛИКОВ =====
        clean_type = ""
        if is_12_hours and twelve_hours_type:
            clean_type = clean_service_text(twelve_hours_type)
        elif is_mixing and mixing_type:
            clean_type = clean_service_text(mixing_type)
        elif is_track_creation and track_type:
            clean_type = clean_service_text(track_type)
        
        # ===== ФОРМИРУЕМ ТЕКСТ СКИДОК =====
        discount_lines = []
        if level_discount_percent and level_discount_percent > 0:
            discount_lines.append(f"• Скидка по уровню: {level_discount_percent}%")
        if promo_discount_percent and promo_discount_percent > 0:
            discount_lines.append(f"• Промокод: {promo_discount_percent}%")
        if promo_code_used:
            discount_lines.append(f"• Код промокода: {promo_code_used}")
        if free_service_applied == 1 and promo_code_used:
            discount_lines.append(f"• Промокод: Бесплатная услуга")
        
        discount_text = ""
        if discount_lines:
            discount_text = "\n" + "\n".join(discount_lines)
        
        # ===== НОВЫЙ ФОРМАТ СООБЩЕНИЯ =====
        user_msg_lines = [
            f"*❌ Ваша заявка отклонена*",
            "",
            f"*📋 Детали вашей записи:*",
            f"• Номер записи: #{booking_id}",
            f"• Имя: {name}",
            f"• Контакт: {contact}",
            f"• Услуга: {clean_service}"
        ]
        
        if clean_type:
            user_msg_lines.append(f"• Тип: {clean_type}")
        
        if clean_date and 'Не указана' not in clean_date:
            user_msg_lines.append(f"• Дата: {clean_date}")
        
        if display_time and display_time not in ['Не указано', 'Не указано (договорная)']:
            if is_12_hours:
                user_msg_lines.append(f"• Время: {display_time} (12 часов)")
            elif is_track_creation:
                user_msg_lines.append(f"• Время: {display_time} (4 часа)")
            elif duration and duration > 0:
                formatted_duration = PriceCalculator.format_hours_ru(duration)
                user_msg_lines.append(f"• Время: {display_time} ({formatted_duration})")
            else:
                user_msg_lines.append(f"• Время: {display_time}")
        
        # ===== ЦЕНА =====
        if is_12_hours == 1:
            rent_price = 6500 if twelve_hours_type and 'Ночь' in twelve_hours_type else 7000
            if price and price != '0' and price != str(rent_price):
                try:
                    price_int = int(float(price))
                    user_msg_lines.append(f"• Стоимость: {price_int}₽ + залог (по договору)")
                except:
                    user_msg_lines.append(f"• Стоимость: {rent_price}₽ + залог (по договору)")
            else:
                user_msg_lines.append(f"• Стоимость: {rent_price}₽ + залог (по договору)")
        elif (is_mixing == 1 and mixing_type and "Альбом" in mixing_type) or \
             (is_track_creation == 1 and track_type and "Альбом" in track_type):
            user_msg_lines.append(f"• Стоимость: Договорная")
        elif free_service_applied == 1:
            user_msg_lines.append(f"• Стоимость: 0₽")
        elif price == '0' and promo_code_used:
            user_msg_lines.append(f"• Стоимость: 0₽")
        elif price and price != '0' and 'договорная' not in str(price).lower():
            try:
                price_int = int(float(price))
                user_msg_lines.append(f"• Стоимость: {price_int}₽")
            except:
                user_msg_lines.append(f"• Стоимость: {price}₽")
        else:
            if is_mixing == 1:
                user_msg_lines.append(f"• Стоимость: 2500₽")
            elif is_track_creation == 1:
                user_msg_lines.append(f"• Стоимость: 9000₽")
            else:
                user_msg_lines.append(f"• Стоимость: Договорная")
        
        if discount_text:
            user_msg_lines.append(discount_text.lstrip('\n'))
        
        user_msg_lines.append("")
        user_msg_lines.append(f"*📞 Свяжитесь с администратором @mothman32*")
        
        user_message = "\n".join(user_msg_lines)
        
        await context.bot.send_message(
            chat_id=int(telegram_id),
            text=user_message,
            parse_mode="Markdown"
        )
        logger.info(f"✅ Сообщение об отклонении отправлено пользователю {telegram_id}")
        
        # ===== ОБНОВЛЯЕМ СООБЩЕНИЕ АДМИНА =====
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=f"*❌ Запись #{booking_id} отклонена!*", parse_mode="Markdown"
        )
        
        logger.info(f"❌ Запись #{booking_id} отклонена, промокод и купон возвращены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в process_booking_rejection: {e}")
        import traceback
        traceback.print_exc()
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text="❌ Ошибка при отклонении", parse_mode="Markdown"
            )
        except:
            pass

async def admin_cancel_confirm_handler(update: Update, context):
    """Подтверждение отмены записи админом с правильной логикой купона"""
    query = update.callback_query
    data = query.data
    
    try:
        booking_id = int(data.split('_')[3])
    except (IndexError, ValueError):
        await query.answer("❌ Неверный формат данных!", show_alert=True)
        return
    
    await query.answer()
    
    booking_data = context.user_data.get('admin_cancel_booking_data', {})
    
    date_str = booking_data.get('date_str', '')
    time_slot = booking_data.get('time_slot', '')
    
    hours_until = DateTimeUtils.get_hours_until_booking(date_str, time_slot)
    
    telegram_id = booking_data.get('telegram_id')
    target_user_id = context.user_data.get('target_user_id')
    target_unique_id = context.user_data.get('target_unique_id')
    target_username = context.user_data.get('target_username')
    admin_id = update.effective_user.id
    
    client_name = booking_data.get('name', 'Не указан')
    client_contact = booking_data.get('contact', 'Не указан')
    service = booking_data.get('service', 'Не указана')
    mixing_type = booking_data.get('mixing_type', '')
    price = booking_data.get('price', '0')
    
    # Формируем отображение цены
    if price and price != '0' and 'Договорная' not in str(price):
        try:
            price_int = int(float(price))
            price_display = f"{price_int}₽"
        except:
            price_display = str(price).replace('₽', '').strip()
    else:
        price_display = "Договорная"
    
    vinyls_deducted = 0
    current_vinyls_before = 0
    current_vinyls_after = 0
    is_mixing_db = False
    is_track_creation_db = False
    level_coupon_id = None
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT level_coupon_id, promo_code_used, status, service, is_mixing, is_track_creation
            FROM bookings WHERE id = ?
        ''', (booking_id,))
        result = cursor.fetchone()
        
        if result:
            level_coupon_id, promo_code_used, current_status, service_db, is_mixing_db, is_track_creation_db = result
            
            try:
                cursor.execute('ALTER TABLE bookings ADD COLUMN vinyls_awarded INTEGER DEFAULT 0')
                conn.commit()
            except:
                pass
            
            cursor.execute('SELECT vinyls_awarded FROM bookings WHERE id = ?', (booking_id,))
            award_row = cursor.fetchone()
            was_awarded = award_row[0] == 1 if award_row else False
            
            cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(telegram_id),))
            user_row = cursor.fetchone()
            current_vinyls_before = user_row[0] if user_row else 0
            
            if was_awarded:
                vinyls_deducted = 25
                cursor.execute('UPDATE users SET vinyls = vinyls - 25 WHERE telegram_id = ? AND vinyls >= 25', (str(telegram_id),))
                logger.info(f"💰 Списано 25 пластинок у пользователя {telegram_id} за отмену записи #{booking_id}")
                cursor.execute('UPDATE bookings SET vinyls_awarded = 0 WHERE id = ?', (booking_id,))
            
            # ===== ЛОГИКА КУПОНА ПРИ ОТМЕНЕ АДМИНОМ =====
            if level_coupon_id:
                # Определяем, нужно ли сжечь или вернуть купон
                should_burn = False
                
                # Для сведения/мастеринга
                if is_mixing_db:
                    if current_status in ['confirmed', 'подтвержден']:
                        should_burn = True
                        logger.info(f"🔥 Купон {level_coupon_id} сгорает: сведение, статус confirmed")
                    else:
                        should_burn = False
                        logger.info(f"🔄 Купон {level_coupon_id} возвращается: сведение, статус {current_status}")
                else:
                    # Для услуг с датой (вокал, инструменты, трек, аренда)
                    if current_status in ['confirmed', 'подтвержден'] and hours_until < 12:
                        should_burn = True
                        logger.info(f"🔥 Купон {level_coupon_id} сгорает: confirmed, < 12ч до начала")
                    elif current_status in ['pending', 'ожидает'] and hours_until < 12:
                        should_burn = False
                        logger.info(f"🔄 Купон {level_coupon_id} возвращается: pending, < 12ч до начала")
                    elif hours_until >= 12:
                        should_burn = False
                        logger.info(f"🔄 Купон {level_coupon_id} возвращается: > 12ч до начала")
                    else:
                        should_burn = False
                        logger.info(f"🔄 Купон {level_coupon_id} возвращается (по умолчанию)")
                
                if should_burn:
                    cursor.execute('DELETE FROM user_coupons WHERE id = ?', (level_coupon_id,))
                    logger.info(f"🔥 Купон {level_coupon_id} СГОРЕЛ при отмене записи #{booking_id}")
                else:
                    # Проверяем, существует ли купон в user_coupons
                    cursor.execute('SELECT id FROM user_coupons WHERE id = ?', (level_coupon_id,))
                    exists = cursor.fetchone()
                    
                    if exists:
                        # Купон существует - увеличиваем remaining_uses
                        cursor.execute('''
                            UPDATE user_coupons SET remaining_uses = remaining_uses + 1 
                            WHERE id = ? AND is_permanent = 0
                        ''', (level_coupon_id,))
                        logger.info(f"🔄 Купон {level_coupon_id} ВОЗВРАЩЁН (обновлён) при отмене записи #{booking_id}")
                    else:
                        # Купон был удалён - создаём новый
                        cursor.execute('''
                            INSERT INTO user_coupons (user_id, level, discount_percent, remaining_uses, is_permanent)
                            VALUES (?, 1, 50, 1, 0)
                        ''', (str(telegram_id),))
                        logger.info(f"🔄 Создан НОВЫЙ купон 50% для пользователя {telegram_id} при отмене записи #{booking_id}")
            
            if telegram_id:
                handle_promo_code_on_cancellation(booking_id, str(telegram_id), hours_until, context)
        
        cursor.execute('SELECT vinyls FROM users WHERE telegram_id = ?', (str(telegram_id),))
        new_row = cursor.fetchone()
        current_vinyls_after = new_row[0] if new_row else 0
        
        cursor.execute('DELETE FROM notifications WHERE booking_id = ?', (booking_id,))
        cursor.execute('DELETE FROM cache_slots WHERE booking_id = ?', (booking_id,))
        cursor.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
        
        conn.commit()
    
    # ===== ОЧИЩАЕМ КЭШ ДАТЫ =====
    if date_str and 'Не указана' not in date_str:
        clean_date = date_str
        if '(' in clean_date:
            clean_date = clean_date.split('(')[0].strip()
        if clean_date and clean_date[0] in "🟢🟡🟠🔴⚪️":
            clean_date = clean_date[2:].strip()
        
        MemoryCache.invalidate_date(clean_date)
        logger.info(f"🗑️ Кэш очищен для даты: {clean_date}")
    
    if vinyls_deducted > 0:
        await AchievementSystem.check_and_award_achievements(str(telegram_id), context, None)
        await AchievementSystem.update_user_level(str(telegram_id), context)
    
    # Отправляем уведомление пользователю
    if telegram_id:
        try:
            service_type_display = ""
            if is_mixing_db:
                service_type_display = f"\n• Тип: {mixing_type}" if mixing_type else "\n• Тип: Трек"
            elif is_track_creation_db:
                service_type_display = "\n• Тип: 🎵 Создание трека"
            
            user_message = f"""*❌ Администратор отменил запись #{booking_id}*

*👤 Пользователь: {client_name}*
*📱 Контакт: {client_contact}*
*🎧 Услуга: {service}{service_type_display}*
*💰 Стоимость: {price_display}*"""

            if vinyls_deducted > 0:
                user_message += f"""

*📉 Списано {vinyls_deducted} пластинок за отмену записи*
*💰 Пластинок после отмены: {current_vinyls_after} 💿*"""

            user_message += """

*📞 По вопросам: @mothman32*"""
            
            await context.bot.send_message(chat_id=int(telegram_id), text=user_message, parse_mode="Markdown")
            logger.info(f"✅ Уведомление об отмене отправлено пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления пользователю: {e}")
    
    # Отправляем сообщение админу об успешном удалении
    admin_message = f"*✅ Запись #{booking_id} удалена из базы*"
    await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode="Markdown")
    logger.info(f"✅ Уведомление админу отправлено")
    
    # ===== ОБНОВЛЯЕМ СПИСОК ЗАПИСЕЙ (АДМИНСКИЙ) =====
    if target_user_id:
        await asyncio.sleep(0.5)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM bookings 
                WHERE telegram_id = ? 
                AND status NOT IN ('rejected', 'отклонен', 'cancelled_by_user', 'cancelled', 'отменен')
            ''', (str(target_user_id),))
            remaining_row = cursor.fetchone()
            remaining_bookings = remaining_row[0] if remaining_row else 0
        
        if remaining_bookings == 0:
            try:
                await query.edit_message_text(
                    text=f"*📋 Записи пользователя*\n\n"
                         f"*👤 @{target_username if target_username else 'Неизвестный'} {target_unique_id if target_unique_id else ''}*\n\n"
                         f"*📭 У пользователя нет записей*",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"*📋 Записи пользователя*\n\n"
                         f"*👤 @{target_username if target_username else 'Неизвестный'} {target_unique_id if target_unique_id else ''}*\n\n"
                         f"*📭 У пользователя нет записей*",
                    parse_mode="Markdown"
                )
            
            menu_message = (
                "*🏠 Возвращаемся в главное меню*\n\n"
                "*👇 Выберите подходящий вариант:*"
            )
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=menu_message,
                parse_mode="Markdown",
                reply_markup=KeyboardManager.get_main_keyboard(update.effective_user)
            )
            
            context.user_data.clear()
        else:
            await admin_show_user_bookings(
                update, context,
                target_user_id=target_user_id,
                target_unique_id=target_unique_id,
                target_username=target_username,
                edit_mode=True
            )

# ===== ОТЛАДОЧНЫЕ КОМАНДЫ ДЛЯ ПРОВЕРКИ КУПОНОВ =====
async def check_coupons_debug(update: Update, context):
    """Проверяет купоны пользователя в БД"""
    user_id = str(update.effective_user.id)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, level, discount_percent, remaining_uses, is_permanent, created_at
            FROM user_coupons WHERE user_id = ?
        ''', (user_id,))
        rows = cursor.fetchall()
        
        if rows:
            message = "📊 *Купоны в БД:*\n\n"
            for row in rows:
                if row[4]:
                    perm = "вечный"
                else:
                    perm = f"осталось {row[3]} использований"
                message += f"• Уровень {row[1]}: {row[2]}% ({perm})\n"
            await update.message.reply_text(message, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Нет купонов в БД!", parse_mode="Markdown")

async def reset_my_coupons(update: Update, context):
    """Сбрасывает купоны текущего пользователя"""
    user_id = str(update.effective_user.id)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_coupons WHERE user_id = ?', (user_id,))
        conn.commit()
    
    # Заново добавляем купон уровня 1
    CouponManager.add_level_coupons(user_id, 1)
    
    await update.message.reply_text("✅ Твои купоны сброшены! Теперь у тебя снова есть скидка 50% 1 раз.", parse_mode="Markdown")

async def manual_check(update: Update, context):
    user_id = update.effective_user.id
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    await update.message.reply_text("🔄 Запускаю проверку...")
    await update_completed_bookings(context)
    await update.message.reply_text("✅ Проверка выполнена!")

@handle_errors_with_rate_limit
async def manual_check_completed(update: Update, context):
    """Ручная проверка завершенных записей (только для админов)"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    await update.message.reply_text("🔄 Запускаю проверку завершенных записей...")
    await update_completed_bookings(context)
    await update.message.reply_text("✅ Проверка выполнена!")

@handle_errors_with_rate_limit
async def check_pending_status(update: Update, context):
    """Проверка статуса pending записей (только для админов)"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, date_str, time_slot, service, status 
            FROM bookings 
            WHERE status = 'pending'
            ORDER BY id ASC
        ''')
        pending = cursor.fetchall()
        
        if not pending:
            await update.message.reply_text("✅ Нет pending записей!")
            return
        
        message = "📋 *Pending записи:*\n\n"
        for b in pending:
            message += f"#{b[0]} | {b[1]} | {b[2]} | {b[3]} | {b[4]}\n"
        
        await update.message.reply_text(message, parse_mode="Markdown")

@handle_errors_with_rate_limit
async def check_time(update: Update, context):
    """Проверка времени для записи"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    # Получаем аргументы
    args = context.args
    if not args:
        await update.message.reply_text("❌ /checktime 1")
        return
    
    try:
        booking_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!")
        return
    
    import sqlite3
    import pytz
    from datetime import datetime, timedelta
    
    conn = sqlite3.connect(db.db_path, timeout=10.0)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, date_str, time_slot, status, vinyls_awarded
        FROM bookings WHERE id = ?
    ''', (booking_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        await update.message.reply_text(f"❌ Запись #{booking_id} не найдена!")
        return
    
    b_id, date_str, time_slot, status, awarded = row
    
    now = DateTimeUtils.now()
    now_utc = now.astimezone(pytz.UTC)
    
    # Парсим дату и время
    clean_date = date_str.split('(')[0].strip()
    day, month, year = map(int, clean_date.split('.'))
    
    end_hour = 0
    if time_slot and '-' in time_slot:
        norm_time = DateTimeUtils.normalize_time_input(time_slot)
        start_str, end_str = norm_time.split('-')
        end_hour = int(end_str)
        if end_hour == 0:
            end_hour = 24
    
    end_datetime = datetime(year, month, day, end_hour, 0, 0)
    end_datetime = Config.TIMEZONE.localize(end_datetime)
    end_utc = end_datetime.astimezone(pytz.UTC)
    
    message = f"📋 *Время для записи #{booking_id}:*\n\n"
    message += f"• Дата: {date_str}\n"
    message += f"• Время: {time_slot}\n"
    message += f"• Статус: {status}\n"
    message += f"• vinyls_awarded: {awarded}\n\n"
    message += f"• Сейчас (МСК): {now.strftime('%H:%M:%S')}\n"
    message += f"• Сейчас (UTC): {now_utc.strftime('%H:%M:%S')}\n"
    message += f"• Окончание (МСК): {end_datetime.strftime('%H:%M:%S')}\n"
    message += f"• Окончание (UTC): {end_utc.strftime('%H:%M:%S')}\n"
    message += f"• Прошло? {now_utc >= end_utc}\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

def setup_handlers(application):
    """Настройка всех обработчиков бота"""
    
    # ============================================================
    # 1. КОМАНДЫ (САМЫЙ ВЫСОКИЙ ПРИОРИТЕТ)
    # ============================================================
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(CommandHandler("fixcoupons", fix_my_coupons))
    application.add_handler(CommandHandler("checkcoupons", check_coupons_table))
    application.add_handler(CommandHandler("coupons", check_coupons_debug))
    application.add_handler(CommandHandler("resetcoupons", reset_my_coupons))
    application.add_handler(CommandHandler("check", manual_check))
    application.add_handler(CommandHandler("testaward", test_award))
    application.add_handler(CommandHandler("checkcompleted", manual_check_completed))
    application.add_handler(CommandHandler("pendingstatus", check_pending_status))
    application.add_handler(CommandHandler("checktime", check_time))
    application.add_handler(CommandHandler("forcecomplete", force_complete))
    application.add_handler(CommandHandler("debugadd", debug_add_vinyls))
    
    # ============================================================
    # 2. НОВЫЕ КНОПКИ (ВЫСОКИЙ ПРИОРИТЕТ) - ВСЁ УБРАНО!
    # ============================================================
    # ❓ Помощь и ❗️ Полезная информация обрабатываются в handle_global_buttons
    
    # ============================================================
    # 3. CALLBACK QUERY HANDLERS
    # ============================================================
    application.add_handler(CallbackQueryHandler(handle_revenue_period_selection, pattern="^revenue_"))
    application.add_handler(CallbackQueryHandler(promo_callback_handler, pattern="^promo_"))
    application.add_handler(CallbackQueryHandler(admin_promo_delete_callback_handler, pattern="^admin_del_promo_"))
    application.add_handler(CallbackQueryHandler(admin_promo_delete_confirm_handler, pattern="^admin_confirm_del_"))
    application.add_handler(CallbackQueryHandler(admin_promo_delete_confirm_handler, pattern="^admin_cancel_del$"))
    application.add_handler(CallbackQueryHandler(enter_referral_code_callback, pattern="^enter_referral_code$"))
    application.add_handler(CallbackQueryHandler(show_my_referrals_callback, pattern="^show_my_referrals$"))
    application.add_handler(CallbackQueryHandler(back_to_referral_callback, pattern="^back_to_referral$"))
    application.add_handler(CallbackQueryHandler(admin_cancel_confirm_handler, pattern="^admin_cancel_confirm_"))
    application.add_handler(CallbackQueryHandler(admin_cancel_keep_handler, pattern="^admin_cancel_keep$"))
    application.add_handler(CallbackQueryHandler(admin_cancel_callback_handler, pattern="^admin_cancel_\\d+$"))
    application.add_handler(CallbackQueryHandler(admin_remove_achievement_callback, pattern="^admin_remove_achievement_\\d+$"))
    application.add_handler(CallbackQueryHandler(admin_remove_achievement_confirm, pattern="^admin_remove_achievement_confirm_"))
    application.add_handler(CallbackQueryHandler(admin_remove_achievement_cancel, pattern="^admin_remove_achievement_cancel$"))
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    
    # ============================================================
    # 4. ПРОМОКОДЫ (ВВОД)
    # ============================================================
    application.add_handler(
        MessageHandler(
            filters.Regex(r'^promo\s+\w+') | filters.Regex(r'^PROMO\s+\w+'),
            process_promo_code_message
        ),
        group=0
    )
    
    # ============================================================
    # 5. РЕФЕРАЛЬНЫЕ КОДЫ
    # ============================================================
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & 
            ~filters.Regex(r'^promo\s+\w+') & 
            ~filters.Regex(r'^PROMO\s+\w+') &
            ~filters.Regex(r'^(🎤|📅|👤|🔔|🏆|🎁|👥|📊|👑|↩️|✅|✏️|❌|👨‍🔧|💪|☀️|🌙|🎵|💿|🎚️|⏰|🎸|➕|➖|❓|❗️|/)') &
            filters.Regex(r'^[A-Za-z0-9]{6,10}$'),
            process_referral_code_message
        ),
        group=1
    )
    
    # ============================================================
    # 6. CONVERSATION HANDLERS
    # ============================================================
    
    # 6.1 Бронирование
    booking_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(🎤 Записаться в студию)$'), start_booking),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CONTACT: [MessageHandler(filters.TEXT | filters.CONTACT, get_contact)],
            CONTACT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_contact_input)],
            SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_service)],
            ENGINEER_OPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_engineer_option)],
            TWELVE_HOURS_OPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_twelve_hours_option)],
            MIXING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mixing_type)],
            TRACK_CREATION_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_track_creation_type)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            SHOW_SLOTS: [
                MessageHandler(filters.Regex('^(✅ Всё верно, отправить)$'), handle_confirmation_text),
                MessageHandler(filters.Regex('^(✏️ Исправить данные)$'), handle_confirmation_text),
                MessageHandler(filters.Regex('^(❌ Отменить)$'), handle_confirmation_text),
                MessageHandler(filters.TEXT & ~filters.COMMAND, show_slots),
            ],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation_text)],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            MessageHandler(filters.Regex('^(↩️ Назад)$'), handle_back_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="booking_conversation"
    )
    application.add_handler(booking_conv_handler)
    
    # 6.2 Админская запись
    admin_booking_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(👑 Создать запись)$'), handle_admin_create_booking),
        ],
        states={
            ADMIN_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_user_id)],
            ADMIN_RECORD_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_record_type)],
            ADMIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_price)],
            ADMIN_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="admin_booking_conversation"
    )
    application.add_handler(admin_booking_conv_handler)
    
    # 6.3 Админская отмена записи
    admin_cancel_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(👑 Отменить запись)$'), handle_admin_cancel_start),
        ],
        states={
            ADMIN_CANCEL_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_cancel_user_id)],
            ADMIN_CANCEL_SHOW_BOOKINGS: [
                MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
                MessageHandler(filters.Regex('^(↩️ Назад)$'), handle_admin_cancel_back)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="admin_cancel_conversation"
    )
    application.add_handler(admin_cancel_conv_handler)
    
    # 6.4 Админская блокировка
    admin_block_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(👑 Заблокировать)$'), handle_admin_block_start),
        ],
        states={
            ADMIN_BLOCK_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_block_user_id)],
            ADMIN_BLOCK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_block_type)],
            ADMIN_BLOCK_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_block_duration)],
            ADMIN_BLOCK_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_block_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="admin_block_conversation"
    )
    application.add_handler(admin_block_conv_handler)
    
    # 6.5 Админская выдача достижения
    admin_achievement_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(👑 Выдать достижение)$'), handle_admin_award_achievement_start),
        ],
        states={
            ADMIN_ACHIEVEMENT_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_achievement_user_id)],
            ADMIN_ACHIEVEMENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_achievement_name)],
            ADMIN_ACHIEVEMENT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_achievement_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="admin_achievement_conversation"
    )
    application.add_handler(admin_achievement_conv_handler)
    
    # 6.6 Админское удаление достижения
    admin_remove_achievement_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(👑 Удалить достижение)$'), handle_admin_remove_achievement_start),
        ],
        states={
            ADMIN_REMOVE_ACHIEVEMENT_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_remove_achievement_user_id)],
            ADMIN_REMOVE_ACHIEVEMENT_SHOW: [
                MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
                MessageHandler(filters.Regex('^(↩️ Назад)$'), handle_admin_remove_achievement_back)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="admin_remove_achievement_conversation"
    )
    application.add_handler(admin_remove_achievement_conv_handler)
    
    # 6.7 Админское управление пластинками
    admin_vinyl_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(👑 Пластинки)$'), handle_admin_vinyl_start),
        ],
        states={
            ADMIN_VINYL_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_vinyl_user_id)],
            ADMIN_VINYL_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_vinyl_action)],
            ADMIN_VINYL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_vinyl_amount)],
            ADMIN_VINYL_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_vinyl_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="admin_vinyl_conversation"
    )
    application.add_handler(admin_vinyl_conv_handler)
    
    # 6.8 Админский просмотр профиля
    admin_profile_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(👑 Профиль)$'), handle_admin_profile_start),
        ],
        states={
            ADMIN_PROFILE_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_profile_user_id)],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="admin_profile_conversation"
    )
    application.add_handler(admin_profile_conv_handler)
    
    # 6.9 Админское создание промокода
    admin_promo_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(👑 Создать промокод)$'), admin_promo_start),
        ],
        states={
            ADMIN_PROMO_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_promo_select_type)],
            ADMIN_PROMO_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_promo_find_user)],
            ADMIN_PROMO_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_promo_duration)],
            ADMIN_PROMO_DURATION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_promo_duration_input)],
            ADMIN_PROMO_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_promo_type)],
            ADMIN_PROMO_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_promo_service)],
            ADMIN_PROMO_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_promo_value)],
            ADMIN_PROMO_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_promo_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^(↩️ Главное меню)$'), handle_main_menu_button),
            CommandHandler('cancel', lambda update, context: ConversationHandler.END),
        ],
        allow_reentry=True,
        name="admin_promo_conversation"
    )
    application.add_handler(admin_promo_conv_handler)
    
    # ============================================================
    # 7. ПОЛЬЗОВАТЕЛЬСКИЙ ПЕРИОД ДЛЯ ВЫРУЧКИ
    # ============================================================
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.User(user_id=Config.ADMIN_IDS),
            handle_custom_revenue_period_inline
        )
    )
    
    # ============================================================
    # 8. ГЛОБАЛЬНЫЙ ОБРАБОТЧИК КНОПОК (НИЗКИЙ ПРИОРИТЕТ)
    # ============================================================
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_global_buttons),
        group=2
    )
    
    # ============================================================
    # 9. ОБРАБОТЧИК ОШИБОК
    # ============================================================
    application.add_error_handler(error_callback)
    
    logger.info("✅ Все обработчики успешно настроены")

def run_bot():
    try:
        verify_data_directory()
        
        # ===== ПРИНУДИТЕЛЬНОЕ ВКЛЮЧЕНИЕ WAL РЕЖИМА ДЛЯ ВСЕХ БД =====
        import sqlite3
        for db_path in [MAIN_DB_PATH, PERSISTENT_DB_PATH]:
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path, timeout=60.0)
                    conn.execute('PRAGMA journal_mode=WAL')
                    conn.execute('PRAGMA synchronous=NORMAL')
                    conn.execute('PRAGMA busy_timeout=60000')
                    conn.execute('PRAGMA cache_size=-20000')
                    result = conn.execute('PRAGMA journal_mode').fetchone()
                    conn.close()
                    logger.info(f"✅ WAL режим включен для {db_path}: {result[0]}")
                except Exception as e:
                    logger.error(f"❌ Ошибка WAL для {db_path}: {e}")
        
        logger.info("🔧 Включение WAL режима для баз данных...")
        db._enable_wal_mode()
        if hasattr(persistent_db, 'enable_wal_mode'):
            persistent_db.enable_wal_mode()
        
        logger.info("Создание Application...")
        application = Application.builder() \
            .token(Config.TOKEN) \
            .concurrent_updates(True) \
            .build()
        
        logger.info("🔧 Проверка и миграция базы данных...")
        migration_success = migrate_database()
        if not migration_success:
            logger.warning("⚠️ Миграция базы данных завершилась с ошибками, но продолжаем работу")
        
        logger.info("Настройка обработчиков...")
        setup_handlers(application)
        
        logger.info("Проверка JobQueue...")
        
        try:
            from telegram.ext import JobQueue
            import datetime as dt
            
            job_queue = application.job_queue
            logger.info(f"JobQueue доступен: {job_queue is not None}")
            
            if job_queue:
                # Проверка уведомлений каждую минуту
                job_queue.run_repeating(
                    callback=process_notifications,
                    interval=60.0,
                    first=10.0,
                    name="notifications_checker"
                )
                
                # Мониторинг каждый час
                job_queue.run_repeating(
                    callback=lambda context: Monitor.run_all_checks(),
                    interval=3600.0,
                    first=60.0,
                    name="monitoring_checker"
                )
                
                # Очистка старых записей каждый день в 3:00
                job_queue.run_daily(
                    callback=lambda context: cleanup_old_bookings(context),
                    time=dt.time(hour=3, minute=0),
                    days=(0, 1, 2, 3, 4, 5, 6),
                    name="cleanup_old_bookings"
                )
                
                # Проверка завершившихся записей каждую минуту (ВАЖНО!)
                job_queue.run_repeating(
                    callback=update_completed_bookings,
                    interval=60.0,
                    first=10.0,
                    name="completed_bookings_checker"
                )
                
                # Проверка истекших блокировок каждую минуту
                job_queue.run_repeating(
                    callback=check_expired_blocks,
                    interval=60.0,
                    first=15.0,
                    name="expired_blocks_checker"
                )
                
                # Очистка истекших промокодов каждый час
                job_queue.run_repeating(
                    callback=cleanup_expired_promocodes,
                    interval=3600.0,
                    first=60.0,
                    name="cleanup_expired_promocodes"
                )
                
                logger.info("✅ Все задачи добавлены в JobQueue")
            else:
                logger.warning("⚠️ JobQueue не инициализирован")
                
        except Exception as e:
            logger.error(f"❌ Ошибка настройки JobQueue: {e}")
        
        logger.info("🚀 Запуск бота...")
        logger.info("✅ Бот готов к работе!")
        
        # Запуск с правильными параметрами
        application.run_polling(
            poll_interval=1.0,
            timeout=30,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except telegram.error.InvalidToken:
        logger.error("❌ Неверный токен бота! Проверьте .env файл")
        sys.exit(1)
    except telegram.error.NetworkError as e:
        logger.error(f"❌ Ошибка сети: {e}")
        logger.info("🔄 Попытка переподключения через 10 секунд...")
        time.sleep(10)
        run_bot()
    except KeyboardInterrupt:
        logger.info("\n👋 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.info("🔄 Попытка перезапуска через 10 секунд...")
        time.sleep(10)
        run_bot()

if __name__ == '__main__':
    run_bot()
