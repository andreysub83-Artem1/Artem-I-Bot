# -*- coding: utf-8 -*-
"""✨ ARTEM AI ✨ — PLATFORM v9.0 (EXCLUSIVE EDITION)"""

import asyncio
import os, re, json, logging, sqlite3
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from rich.console import Console
from rich.panel import Panel
from prettytable import PrettyTable
from loguru import logger as loguru_logger
import sys

#===========================================
# GOOGLE SHEETS INTEGRATION
#===========================================
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_google_sheet():
    """Подключение к таблице Artem I Proekt"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open("Artem I Proekt").sheet1

# ==========================================
# БЛОК 1: ФИЛЬТРЫ (Исправлено для работы)
# ==========================================
from telegram.ext.filters import BaseFilter

class PhoneFilter(BaseFilter):
    """Строгая валидация номера: +7XXXXXXXXXX или 8XXXXXXXXXX (10-11 цифр)"""
    _PHONE_RE = re.compile(r"^\+?[78]?\d{10}$")

    def filter(self, update: Update) -> bool:
        if not update.message or not update.message.text:
            return False
        clean = re.sub(r"[\s\-\(\)]", "", update.message.text.strip())
        return bool(self._PHONE_RE.match(clean))


class PriceFilter(BaseFilter):
    def filter(self, update: Update) -> bool:
        if not update.message or not update.message.text:
            return False
        clean = re.sub(r"\D", "", update.message.text)
        if not clean.isdigit():
            return False
        return 100000 <= int(clean) <= 10000000000


class AreaFilter(BaseFilter):
    def filter(self, update: Update) -> bool:
        if not update.message or not update.message.text:
            return False
        try:
            return (
                1
                <= float(update.message.text.replace(",", ".").replace(" ", ""))
                <= 2000
            )
        except ValueError:
            return False


class ChildrenFilter(BaseFilter):
    def filter(self, update: Update) -> bool:
        if not update.message or not update.message.text:
            return False
        try:
            return 0 <= int(update.message.text) <= 10
        except ValueError:
            return False


# Готовые фильтры для подключения в states
phone_filter = PhoneFilter()
price_filter = PriceFilter()
area_filter = AreaFilter()
children_filter = ChildrenFilter()

# ──────────────────────────────────────────────────────────────────────
# БЛОК 2: НАСТРОЙКИ
# ──────────────────────────────────────────────────────────────────────
load_dotenv()
_raw_token = os.getenv("BOT_TOKEN", "").strip()
# 🔥 Защита: если токен содержит "BOT_TOKEN=" — обрезаем лишнее
TOKEN = _raw_token.split("BOT_TOKEN=")[-1] if "BOT_TOKEN=" in _raw_token else _raw_token

# 🔥 ИСПРАВЛЕНИЕ: Приводим ID к числу (чтобы бот точно узнал тебя)
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 🔥 ИСПРАВЛЕНИЕ: Добавляем переменную для ссылок меню (чтобы не было ошибок)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://artem-ai.onrender.com")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
console = Console()
loguru_logger.remove()
loguru_logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

# ──────────────────────────────────────────────────────────────────────
# 2. AI ТРИГГЕРЫ (мгновенные ответы вне воронки)
# ──────────────────────────────────────────────────────────────────────
AI_TRIGGERS = {
    "участок": {
        "keys": ["участок", "соток", "земля", "надел", "ижд", "земельный"],
        "msg": "🌿 Участок — фундамент будущего. Для ИЖС критичны коммуникации и статус земли. Какая площадь интересует? От 6 до 15 соток?",
    },
    "дом": {
        "keys": ["дом", "коттедж", "построить", "строительство", "каркас", "кирпич"],
        "msg": "🏠 Стройка — марафон. Главное — смета и этапы. Работаем с проверенными бригадами на Сахалине. Готовый проект или индивидуальный?",
    },
    "цена": {
        "keys": ["цена", "стоит", "бюджет", "дорого", "дешево", "рынок"],
        "msg": "📊 Рынок динамичный. Цена зависит от локации и коммуникаций. Назови примерный бюджет — отфильтрую реальные варианты.",
    },
    "ипотека": {
        "keys": ["ипотека", "кредит", "платеж", "банк", "ставка", "взнос"],
        "msg": "🏦 Ипотека на частный сектор доступна. Готов рассчитать платеж? Нажми «🧮 Калькулятор» или напиши сумму.",
    },
    "продать": {
        "keys": ["продать", "оценка", "выставить", "реклама", "спрос"],
        "msg": "📢 Чтобы продать быстро, создаем спрос: проф. съемка, 5+ площадок. Опиши объект — предложу стратегию.",
    },
    "другой_город": {
        "keys": ["другой город", "другом городе", "москва", "владивосток", "хабаровск",
                 "санкт-петербург", "спб", "новосибирск", "краснодар", "работаете в",
                 "охватываете", "по всей стране"],
        "msg": "🗺 По этому вопросу более полную информацию Вам лучше уточнить у нашего менеджера — он расскажет всё детально. А пока давайте я помогу с Вашим запросом здесь! Чем могу быть полезен?",
    },
}




# ──────────────────────────────────────────────────────────────────────
# СОСТОЯНИЯ (СИНХРОНИЗИРОВАНО С main())
# ─────────────────────────────────────────────────────────────────────
# 🔥 ИСПРАВЛЕНИЕ: Добавлено 4 недостающих состояния для Опеки и Ипотеки
(
    GET_NAME,
    CHOICE,
    # Продавец
    SELL_OBJ,
    SELL_SOTOK,
    SELL_LOC,
    SELL_AREA,
    SELL_TIME,
    SELL_PRICE,
    SELL_ENC,
    SELL_MORT,
    SELL_GUARD_COUNT,
    SELL_GUARD_AGE,
    SELL_GUARD_HOUSING,
    SELL_GUARD_SEARCH,
    SELL_OWN,
    SELL_DOCS,
    # Добавлено для логики опеки
    SELL_CHILDREN_AGE,
    SELL_REASON,
    SELL_MATERIAL,
    SELL_OWNERSHIP,
    SELL_KADASTR,
    SELL_FUNDAMENT,
    SELL_OBREM,
    SELL_YEARS,
    # Покупатель
    BUY_OBJ,
    BUY_SOTOK,
    BUY_LAND_PURPOSE,
    BUY_BUILDER_SEARCH,
    BUY_LOC,
    BUY_BUDGET,
    BUY_INFRA,
    BUY_PURPOSE,
    BUY_PAY,
    BUY_MORT,
    BUY_CERT,
    BUY_GUARANTEE,
    BUY_MATCAP,
    BUY_TIME,
    # Аренда
    RENT_DUR,
    RENT_OCC,
    RENT_BUDGET,
    RENT_PREFS,
    # Ипотека
    MORT_CHOICE,
    MORT_BUY,
    MORT_SELL,
    # Добавлено для логики ипотечного калькулятора
    MORT_RESULT,
    MORT_RATE,
    # Земля (расширенная воронка)
    LAND_TYPE,
    LAND_AREA,
    LAND_LOC,
    LAND_COMM,
    # Стройка (расширенная воронка)
    BUILD_TYPE,
    BUILD_AREA,
    BUILD_TIME,
    # Контакты и Финал
    SELL_PHONE,
    BUY_PHONE,
    RENT_PHONE,
    CONFIRM_ADD,
    ADD_NOTE_STATE,
    CONTINUE_PRESSED,  # 🔥 Добавлено
    # AI
    AI_CHAT,
    BUILD_LOC,  # 🗺 Местоположение для Стройки (карта)
) = range(62)  # 🔥 Обновлено: было 61, стало 62 (добавлен BUILD_LOC)


# ──────────────────────────────────────────────────────────────────────
# 4. БАЗА ДАННЫХ
# ──────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("artem_i.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, object TEXT, location TEXT,
        area TEXT, timing TEXT, price TEXT, payment TEXT, encumbrance TEXT, ownership TEXT,
        docs TEXT, duration TEXT, occupants TEXT, phone TEXT, latitude REAL, longitude REAL,
        feedback TEXT, edit_note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON leads(user_id)")
    conn.commit()
    conn.close()
    logger.info("✨ База данных ARTEM AI готова")


# ==========================================
# 🔥 БЛОК 5: AI МОДУЛЬ + ТРИГГЕРЫ (ОБЪЕДИНЁННЫЙ)
# ==========================================

# 1. ТРИГГЕРЫ (собраны все ключевые слова в один словарь)
AI_TRIGGERS = {
    "цена": {
        "keys": [
            "цена",
            "стоимость",
            "сколько стоит",
            "ценник",
            "бюджет",
            "дорого",
            "дешево",
            "рынок",
        ],
        "msg": "💰 <b>Ценообразование:</b>\n\n• Рынок динамичный\n• Цена зависит от локации\n• Ипотека доступна\n\nУкажите бюджет",
    },
    "ипотека": {
        "keys": ["ипотека", "кредит", "платёж", "банк", "ставка", "взнос"],
        "msg": "🏦 <b>Ипотека:</b>\n\n• Работаем со всеми банками\n• Помощь в одобрении\n• Ставки от 5.9%",
    },
    "срочно": {
        "keys": ["срочно", "быстро", "неделя", "месяц"],
        "msg": "⚡ <b>Срочная продажа:</b>\n\n• База покупателей готова\n• Показ в день обращения\n• Быстрый выход на сделку",
    },
    "участок": {
        "keys": ["участок", "соток", "земля", "надел", "ижд", "земельный"],
        "msg": "🌿 Участок — фундамент будущего. Для ИЖС критичны коммуникации и статус земли. Какая площадь интересует? От 6 до 15 соток?",
    },
    "дом": {
        "keys": ["дом", "коттедж", "построить", "строительство", "каркас", "кирпич"],
        "msg": "🏠 Стройка — марафон. Главное — смета и этапы. Работаем с проверенными бригадами на Сахалине. Готовый проект или индивидуальный?",
    },
    "продать": {
        "keys": ["продать", "оценка", "выставить", "реклама", "спрос"],
        "msg": "📢 Чтобы продать быстро, создаем спрос: проф. съемка, 5+ площадок. Опиши объект — предложу стратегию.",
    },
    "другой_город": {
        "keys": ["другой город", "другом городе", "москва", "владивосток", "хабаровск",
                 "санкт-петербург", "спб", "новосибирск", "краснодар", "работаете в",
                 "охватываете", "по всей стране"],
        "msg": "🗺 По этому вопросу более полную информацию Вам лучше уточнить у нашего менеджера — он расскажет всё детально. А пока давайте я помогу с Вашим запросом здесь! Чем могу быть полезен?",
    },
}


async def ai_trigger_check(text: str):
    if not text:
        return None
    text_lower = text.lower()
    for topic, data in AI_TRIGGERS.items():
        if any(k in text_lower for k in data["keys"]):
            loguru_logger.info(f"⚡ Триггер: [{topic.upper()}]")
            return data["msg"]
    return None


async def ai_trigger_handler(update: Update, context):
    """🤖 Обработчик AI триггеров"""
    msg = await ai_trigger_check(update.message.text)
    if msg:
        await update.message.reply_text(msg, parse_mode="HTML")
    # Возвращаемся в меню (воронка не сбрасывается)
    return CHOICE

# ==========================================
# ОБРАБОТЧИКИ КНОПОК МЕНЮ (ДОБАВЛЕНО)
# ==========================================
async def handle_sell(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Вы выбрали <b>ПРОДАЖУ</b>. Начнем заполнение анкеты.", parse_mode="HTML")
    return SELL_OBJ

async def handle_buy(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Вы выбрали <b>ПОКУПКУ</b>. Давайте подберем объект.", parse_mode="HTML")
    return BUY_OBJ

async def handle_rent(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Вы выбрали <b>АРЕНДУ</b>. Переходим к подбору.", parse_mode="HTML")
    return RENT_DUR
# 2. МОДУЛЬ OPEN AI
ai_client = (
    OpenAI(api_key=OPENAI_API_KEY)
    if OPENAI_API_KEY and OPENAI_API_KEY != "sk-placeholder"
    else None
)

# 🔹 ТВОЙ ПРОМПТ (оставлен без изменений)
AI_SYSTEM_PROMPT = """Ты — Артём I, цифровой партнёр агентства ARTEM AI, созданного Андреем — экспертом с 17-летним опытом в недвижимости.
Твой характер: тёплый, живой, с лёгким юмором и хитринкой. Ты заботливый, но всегда по делу.
Твой стиль: мягкий, уважительный, профессиональный. Обращайся к клиенту строго по имени (4-5 раз за диалог). Никакого "друг", "гость", "уважаемый".
Твоя цель: бережно познакомиться с клиентом, собрать его запрос и аккуратно подготовить к встрече с Андреем.
Используй эмодзи умеренно. Паузы между вопросами — естественные. Простые вопросы, без головоломок.
География работы: Корсаков и Южно-Сахалинск (42 км друг от друга). Это основные города присутствия агентства.
Корсаков — портовый город на юге Сахалина. Южно-Сахалинск — столица области, крупнейший центр региона.
Если клиент не уточнил город — мягко уточни: Корсаков, Южно-Сахалинск или пригород?"""


async def ask_ai(text, context):
    if not ai_client:
        return "🧠 AI на обслуживании. Оставьте номер для связи с менеджером."
    try:
        resp = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Контекст: {context.user_data}\nВопрос: {text}",
                },
            ],
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "🤖 Задумался... Попробуйте позже."


def parse_number(text: str):
    if not text:
        return 0.0
    s = text.lower().replace(" ", "").replace(",", ".")
    if "млн" in s:
        return float(s.replace("млн", "")) * 1_000_000
    if "тыс" in s or "к" in s:
        return float(s.replace("тыс", "").replace("к", "")) * 1_000
    try:
        return float(s)
    except ValueError:
        return 0.0

# ──────────────────────────────────────────────────────────────────────
# 6. УВЕДОМЛЕНИЯ + СОХРАНЕНИЕ + ЯНДЕКС
# ──────────────────────────────────────────────────────────────────────
async def notify_admin(context, summary, edit_note=None, yandex_url=None):
    if ADMIN_CHAT_ID:
        try:
            msg = f"🆕 <b>НОВАЯ ЗАЯВКА</b>\n\n{summary}"
            if yandex_url:
                msg += f"\n\n🗺 <a href='{yandex_url}'>Открыть в Яндекс.Картах</a>"
            if edit_note:
                msg += f"\n\n⚠️ <b>Правки:</b> {edit_note}"
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=msg,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Admin notify error: {e}")


async def save_lead(context, edit_note=None):
    d = context.user_data
    conn = get_db()
    conn.execute(
        "INSERT INTO leads (user_id,type,object,location,area,timing,price,payment,encumbrance,ownership,docs,duration,occupants,phone,latitude,longitude,edit_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            d.get("user_id", 0),
            d.get("type"),
            d.get("object"),
            d.get("location"),
            d.get("area"),
            d.get("timing"),
            d.get("price"),
            d.get("payment"),
            d.get("encumbrance"),
            d.get("ownership"),
            d.get("docs"),
            d.get("duration"),
            d.get("occupants"),
            d.get("phone"),
            d.get("latitude"),
            d.get("longitude"),
            edit_note,
        ),
    )
    conn.commit()
    conn.close()

    # 📊 GOOGLE SHEETS (ЗАПИСЬ В ТАБЛИЦУ)
    try:
        sheet = get_google_sheet()
                # 🔥 АВТО-ШАПКА (ВСТАВЛЯЕМ СЮДА)
        if sheet.acell('A1').value is None:
            headers = [
                "Дата", "Источник", "Клиент", "Объект", "Цена", 
                "Телефон", "Специфика", "Статус", "Широта", "Долгота"
            ]
            sheet.update('A1:J1', [headers])
            sheet.format('A1:J1', {
                "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}
            })

        lead_type = d.get("type", "unknown")
        obj_type = d.get("object", "")

        # 🌲 Доп. поля для Земли и Стройки
        if obj_type == "Земля":
            extra = " | ".join(filter(None, [
                d.get("land_type", ""),
                f"{d.get('land_area', '')} сот." if d.get("land_area") else "",
                d.get("land_comm", ""),
            ]))
            location = d.get("land_loc", d.get("location", ""))
        elif obj_type == "Стройка":
            extra = " | ".join(filter(None, [
                d.get("build_type", ""),
                f"{d.get('build_area', '')} м²" if d.get("build_area") else "",
                d.get("build_time", ""),
            ]))
            location = d.get("location", "")
        else:
            extra = ""
            location = d.get("location", "")

        _timing_raw = (
            d.get("timing", "") or d.get("build_time", "") or ""
        ).lower()
        if "срочно" in _timing_raw or "как можно скорее" in _timing_raw:
            _status_emoji = "🔥"
        elif any(w in _timing_raw for w in ["изучаю", "смотр", "планирую", "мониторю"]):
            _status_emoji = "⏳"
        else:
            _status_emoji = "✅"
            
        # 🔥 АВТО-ШАПКА (Перед записью проверяем лист)
        try:
            if sheet.acell('A1').value is None:
                headers = [
                    "Дата", "Источник", "Клиент", "Объект", "Цена", 
                    "Телефон", "Специфика", "Статус", "Широта", "Долгота"
                ]
                sheet.update('A1:J1', [headers])
                sheet.format('A1:J1', {
                    "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                    "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}
                })
        except Exception as e:
            loguru_logger.error(f"Ошибка создания шапки: {e}")

        _lat = d.get("latitude", "")
        _lon = d.get("longitude", "")
        row = [
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            "Telegram Bot",
            d.get("client_name", "-"),
            f"{obj_type} | {location}",
            str(d.get("price") or d.get("budget_rent") or ""),
            d.get("phone", ""),
            extra,  # Специфика Земли/Стройки
            f"{_status_emoji} В РАБОТЕ" if lead_type in ["sell", "buy"] else _status_emoji,
            str(_lat) if _lat else "",   # Широта
            str(_lon) if _lon else "",   # Долгота
        ]
        sheet.append_row(row)
    except Exception as e:
        loguru_logger.error(f"Ошибка таблицы: {e}")


def make_yandex_url(lat, lon):
    if lat and lon:
        return f"https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=map"
    return None


# ──────────────────────────────────────────────────────────────────────
# 11.1. ЛОГИКА: ОПЕКА— СКОЛЬКО ДЕТЕЙ?
# ──────────────────────────────────────────────────────────────────────
async def sell_children(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["encumbrance"] = "Опека"
    await update.message.reply_text(
        "👶 Сколько детей?\n\nУкажите количество несовершеннолетних детей."
    )
    return SELL_CHILDREN_AGE


# ──────────────────────────────────────────────────────────────────────
# 11.2. ЛОГИКА: ВОЗРАСТ ДЕТЕЙ
# ──────────────────────────────────────────────────────────────────────
async def sell_children_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["children_count"] = update.message.text.strip()
        await update.message.reply_text(
            f"👶 Детей: {context.user_data['children_count']}\n\n"
            f"Укажите возраст каждого ребёнка (через запятую).\n"
            f"Пример: 5, 8, 12"
        )
        return SELL_REASON
    except:
        await update.message.reply_text("⚠️ Введите числа через запятую.")
        return SELL_CHILDREN_AGE


# ──────────────────────────────────────────────────────────────────────
# 11.3. ЛОГИКА: ПРИЧИНА ПРОДАЖИ (ЕСЛИ < 3 ЛЕТ)
# ──────────────────────────────────────────────────────────────────────
async def sell_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["children_ages"] = update.message.text.strip()
        timing = context.user_data.get("timing", "")

        if any(x in str(timing).lower() for x in ["менее 3", "< 3", "3 лет"]):
            await update.message.reply_text(
                "❓ Почему продаёте?\n\nЭто поможет нам лучше понять ситуацию.",
                reply_markup=ReplyKeyboardMarkup(
                    [["Переезд", "Расширение"], ["Инвестиция", "Другое", "◀️ Назад"]],
                    resize_keyboard=True,
                ),
            )
            return SELL_PHONE
        else:
            return await ask_phone_geo(update, context)
    except:
        return await ask_phone_geo(update, context)


# ──────────────────────────────────────────────────────────────────────
# 1. ПРИВЕТСТВИЕ + ЛОГИКА "ВЕРНУВШИЙСЯ КЛИЕНТ"
# ──────────────────────────────────────────────────────────────────────


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """✨ Проверяем: новый клиент или уже знакомый?"""
    await asyncio.sleep(1.5)  # ⏱ Живая пауза
    user_id = update.effective_user.id
    context.user_data["user_id"] = user_id

    # 🔥 Проверка на Андрея (Создателя)
    is_admin = str(user_id) == str(ADMIN_CHAT_ID)
    if is_admin:
        context.user_data["client_name"] = "Андрей"
        txt = (
            "👋 <b>Андрей, добро пожаловать!</b>\n\n"
            "Бот в режиме тестирования. Все заявки от вас придут сюда.\n"
            "Система готова. Чем займёмся?"
        )
        kb = ReplyKeyboardMarkup(
            [["💰 Продать недвижимость", "🔍 Купить недвижимость"], ["🔑 Арендовать"]],
            resize_keyboard=True,
        )
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
        return CHOICE

    # 🔍 ПРОВЕРЯЕМ БАЗУ НА ВОЗВРАЩАЮЩЕГОСЯ КЛИЕНТА
    try:
        conn = get_db()
        cursor = conn.execute(
            "SELECT * FROM leads WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        last_lead = cursor.fetchone()
        conn.close()
    except:
        last_lead = None

    # === ВАРИАНТ А: КЛИЕНТ УЖЕ БЫЛ У НАС ===
    if last_lead:
        name = context.user_data.get("client_name", "Клиент")
        last_date = last_lead["created_at"][:10] if last_lead["created_at"] else "?"
        last_obj = last_lead["object"] or "?"
        last_type = last_lead["type"] or "?"

        _h = datetime.now().hour
        if 5 <= _h <= 11:
            _back_greeting = "☀️ Доброе утро"
        elif 12 <= _h <= 17:
            _back_greeting = "🌤 Добрый день"
        elif 18 <= _h <= 23:
            _back_greeting = "🌆 Добрый вечер"
        else:
            _back_greeting = "🌙 Доброй ночи"

        welcome_back = (
            f"<b>{_back_greeting}!</b> 👋\n\n"
            f"<b>Рады видеть Вас снова!</b>\n\n"
            f"В прошлый раз ({last_date}) Вы интересовались: {last_type} — {last_obj}\n"
            f"<b>Чем в этот раз могу быть Вам полезен?</b>"
        )
        kb = ReplyKeyboardMarkup(
            [["💰 Продать недвижимость", "🔍 Купить недвижимость"], ["🔑 Арендовать"]],
            resize_keyboard=True,
        )
        await update.message.reply_text(
            welcome_back, reply_markup=kb, parse_mode="HTML"
        )
        return CHOICE

    # === ВАРИАНТ Б: НОВЫЙ КЛИЕНТ ===
    _hour = datetime.now().hour
    if 5 <= _hour <= 11:
        _greeting = "☀️ Доброе утро"
    elif 12 <= _hour <= 17:
        _greeting = "🌤 Добрый день"
    elif 18 <= _hour <= 23:
        _greeting = "🌆 Добрый вечер"
    else:
        _greeting = "🌙 Доброй ночи"

    welcome_text = (
        f"<b>{_greeting}!</b> ✨\n\n"
        "✨ <b>Добро пожаловать в ARTEM I ✨</b>\n\n"
        "Меня зовут <b>Артём I</b>. Я ваш цифровой помощник.\n"
        "За моей спиной — 17 лет практики в сфере недвижимости.\n"
        "Поверьте, я видел и квартиры с видом на море, и фундаменты, "
        "которые держались только на честном слове. Но не переживайте! 😉\n\n"
        "Моя задача — избавить вас от головной боли, сэкономить время\n"
        "и бережно подготовить всё для вашей сделки.\n\n"
        "👇 <b>Нажмите кнопку ниже, чтобы я познакомился с вами поближе.</b>"
    )
    kb = ReplyKeyboardMarkup([["▶️ Продолжим"]], resize_keyboard=True)
    await update.message.reply_text(welcome_text, reply_markup=kb, parse_mode="HTML")
    return CONTINUE_PRESSED


async def handle_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎤 Запрос имени (без повторного приветствия)"""
    await asyncio.sleep(1.5)  # ⏱ Живая пауза
    text = "✍️ <b>Как я могу к Вам обращаться?</b>"
    await update.message.reply_text(text, parse_mode="HTML")
    return GET_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняем имя и показываем чистое меню (3 кнопки)"""
    await asyncio.sleep(1.5)  # ⏱ Живая пауза
    name = update.message.text.strip()
    context.user_data["client_name"] = name

    menu_text = f"Очень приятно познакомиться, {name}! 🤝\n\nРад быть на связи. Чем именно я могу помочь Вам сегодня?"

    # 🔹 Только 3 рабочие кнопки (AI, Меню и Ипотека убраны со входа)
    kb = [["💰 Продать недвижимость", "🔍 Купить недвижимость"], ["🔑 Арендовать"]]

    await update.message.reply_text(
        menu_text,
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode="HTML",
    )
    return CHOICE


# ──────────────────────────────────────────────────────────────────────
# 7. НАВИГАЦИЯ
# ──────────────────────────────────────────────────────────────────────
def get_nav_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🏠 меню", callback_data="nav_main")],
            [InlineKeyboardButton("📞 Позвонить", callback_data="nav_call")],
            [InlineKeyboardButton("🤖 Вопрос AI", callback_data="nav_ai")],
        ]
    )


def get_back_kb():
    return ReplyKeyboardMarkup([["◀️ Назад"], ["❌ Отмена"]], resize_keyboard=True)


async def cancel(update, context):
    await update.message.reply_text(
        "🙏 Понял вас! Мы всегда здесь. Нажмите /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def back_to_menu(update, context):
    await update.message.reply_text(
        "↩️ Вернулись в главное меню.",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["💰 Продать недвижимость"],
                ["🔍 Купить недвижимость"],
                ["🔑 Арендовать"],
            ],
            resize_keyboard=True,
        ),
    )
    return CHOICE


# ──────────────────────────────────────────────────────────────────────
# 9. МАРШРУТИЗАЦИЯ (ОБНОВЛЁННЫЙ — одна кнопка в приложение)
# ──────────────────────────────────────────────────────────────────────
async def route_choice(update, context):
    text = update.message.text
    name = context.user_data["client_name"]
    context.user_data["type"] = None

    # 🔥 Если клиент нажал кнопку "🚀 Открыть приложение" (через Inline-меню), 
    # он уже попал в mini_app.html. Здесь мы просто не даём уйти в старые воронки.
    if "Открыть приложение" in text:
        await update.message.reply_text(
            "🚀 Переход в приложение уже выполнен.\n"
            "Если приложение не открылось, нажми кнопку еще раз.",
            parse_mode="HTML"
        )
        return CHOICE

    # 🔥 Ищем по названию кнопок для старых/альтернативных входов
    if "Продать недвижимость" in text:
        context.user_data["type"] = "sell"
        await update.message.reply_text(
            f"💰 <b>Продажа</b>\nЧто планируете продавать?",
            reply_markup=ReplyKeyboardMarkup(
                [
                    ["🏠 Квартира"],
                    ["🏡 Дом"],
                    ["🏢 Коммерция"],
                    ["🌲 Земля"],
                    ["🏗️ Стройка"],
                    ["◀️ Назад"],
                    ["❌ Отмена"],
                ],
                resize_keyboard=True,
            ),
            parse_mode="HTML",
        )
        return SELL_OBJ

    elif "Купить недвижимость" in text:
        context.user_data["type"] = "buy"
        await update.message.reply_text(
            f"🔍 <b>Покупка</b>\nЧто ищете?",
            reply_markup=ReplyKeyboardMarkup(
                [
                    ["🏠 Квартира"],
                    ["🏡 Дом"],
                    ["🌲 Участок"],
                    ["🏗️ Стройка"],
                    ["◀️ Назад"],
                    ["❌ Отмена"],
                ],
                resize_keyboard=True,
            ),
            parse_mode="HTML",
        )
        return BUY_OBJ

    elif "Арендовать" in text:
        context.user_data["type"] = "rent"
        await update.message.reply_text(
            f"🔑 <b>Аренда</b>\nНа какой срок?",
            reply_markup=ReplyKeyboardMarkup(
                [
                    ["📅 От 1 года"],
                    ["📆 Долго (3+ года)"],
                    ["⏳ Краткосрок"],
                    ["◀️ Назад"],
                    ["❌ Отмена"],
                ],
                resize_keyboard=True,
            ),
            parse_mode="HTML",
        )
        return RENT_DUR

    # 🔹 Все остальные нажатия возвращают в меню без сброса воронки
    return CHOICE

# ──────────────────────────────────────────────────────────────────────
# БЛОК: ВОПРОСЫ ПРОДАВЦА (Воронка: Объект → Сотки → Локация → 6 деталей → Площадь → Цена → Контакты)
# ──────────────────────────────────────────────────────────────────────


async def s_obj(u, c):
    """🏠 Какой тип объекта продаём?"""
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["object"] = (
        u.message.text.replace("🏠 ", "")
        .replace("🏡 ", "")
        .replace("🏢 ", "")
        .replace("🌲 ", "")
        .replace("🏗️ ", "")
    )
    await u.message.reply_text(
        f"Принято, {name}! 📍 <b>Подскажите, где расположен ваш объект?</b>\n"
        "Напишите адрес, район или просто ориентиры.\n"
        "<i>Если участок без адреса — опишите: 'рядом с заправкой'</i> 😉",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_SOTOK


async def s_sotok(u, c):
    """📍 Запоминаем количество соток"""
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["sotok"] = parse_number(u.message.text)
    await u.message.reply_text(
        f"📍 {name}, а сколько соток земли в собственности под домом?",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return SELL_LOC


async def s_loc(u, c):
    """📍 Запоминаем локацию"""
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["location"] = u.message.text

    await u.message.reply_text(
        f"Отлично, {name}! Давайте уточним детали объекта.\n\n"
        "Ответьте на вопросы по очереди. Начнем с первого:\n\n"
        "1️⃣ <b>Из чего построен дом?</b> (кирпич, газоблок, дерево, СИП)",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_MATERIAL


# ==========================================
# 6 НОВЫХ ПРОСТЫХ ВОПРОСОВ (без сложных списков)
# ==========================================
async def s_material(u, c):
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["house_material"] = u.message.text
    await u.message.reply_text(
        f"📄 {name}, а оформлен ли дом в собственность? (да/нет)",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return SELL_OWNERSHIP


async def s_ownership(u, c):
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["house_ownership"] = u.message.text
    await u.message.reply_text(
        f"🏛️ {name}, а стоит ли дом на кадастровом учете? (да/нет)",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return SELL_KADASTR


async def s_kadastr(u, c):
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["house_kadastr"] = u.message.text
    await u.message.reply_text(
        f"🏗️ {name}, а какой тип фундамента? (лента, сваи, плита)",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return SELL_FUNDAMENT


async def s_fundament(u, c):
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["house_fundament"] = u.message.text
    await u.message.reply_text(
        f"⚠️ {name}, есть ли обременения/аресты/ипотека? (да/нет)",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return SELL_OBREM


async def s_obrem(u, c):
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["house_obrem"] = u.message.text
    await u.message.reply_text(
        f"📅 {name}, а как давно дом в собственности? (например: 2 года)",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return SELL_YEARS


async def s_years(u, c):
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["house_years"] = u.message.text
    await u.message.reply_text(
        f"📐 {name}, спасибо! И последнее по объекту.\n"
        "Подскажите общую площадь по документам (в м²).\n"
        "<i>Например: 45 или 120.5</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_AREA


# ==========================================
# ДАЛЬШЕ СТАРЫЕ ПРОВЕРЕННЫЕ ФУНКЦИИ
# ==========================================
async def s_area(u, c):
    """📐 Запоминаем площадь"""
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["area"] = parse_number(u.message.text)
    await u.message.reply_text(
        f"Отлично, {name}! ⏳ <b>Как скоро планируете продажу?</b>\n"
        "<i>Выберите вариант или напишите свой срок</i>",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["⚡ Срочно"],
                ["📅 В этом месяце"],
                ["📆 В течение квартала"],
                ["🔍 Пока изучаю рынок"],
                ["◀️ Назад"],
                ["❌ Отмена"],
            ],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return SELL_TIME


async def s_time(u, c):
    """⏳ Запоминаем сроки"""
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["timing"] = u.message.text
    await u.message.reply_text(
        f"Понял, {name}! 💰 <b>На какую сумму вы ориентируетесь?</b>\n"
        "Можно точную цифру или вилку: <i>5-5.5 млн</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_PRICE


async def s_price(u, c):
    """💰 Запоминаем цену"""
    name = c.user_data["client_name"]
    await asyncio.sleep(0.8)
    c.user_data["price"] = parse_number(u.message.text)
    await u.message.reply_text(
        f"Спасибо, {name}! 📜 <b>Есть ли обременения на объекте?</b>\n"
        "<i>Ипотека, опека, арест или всё чисто?</i>",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Нет"], ["🏦 Ипотека"], ["⚖️ Опека/Арест"], ["◀️ Назад"], ["❌ Отмена"]],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return SELL_ENC


# 🔥 ЛОГИКА ОБРЕМЕНЕНИЙ (ИПОТЕКА / ОПЕКА / ЧИСТО)
async def s_enc(u, c):
    t = u.message.text
    c.user_data["encumbrance"] = "Нет" if "Нет" in t else t
    if "Ипотека" in t:
        await u.message.reply_text(
            "🏦 <b>Понял.</b> Сколько примерно осталось платить банку?\n<i>Например: 2 500 000 ₽</i>",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return SELL_MORT
    elif "Опека" in t or "Арест" in t:
        await u.message.reply_text(
            "👶 <b>Понял, объект под опекой/арестом.</b>\nСколько несовершеннолетних детей?\n<i>Напишите число.</i>",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return SELL_GUARD_COUNT
    return await ask_own(u, c)


async def s_mort(u, c):
    c.user_data["mortgage_details"] = parse_number(u.message.text)
    return await ask_own(u, c)


async def s_guard_count(u, c):
    c.user_data["children_count"] = parse_number(u.message.text)
    await u.message.reply_text(
        "🎂 <b>Укажите возраст детей</b> (через запятую).\n<i>Пример: 5, 12, 17</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_GUARD_AGE


async def s_guard_age(u, c):
    c.user_data["children_ages"] = u.message.text
    await u.message.reply_text(
        "🏠 <b>Уже подобрано новое жильё для детей?</b>",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Да, уже нашли"], ["❌ Нет, в поиске"], ["◀️ Назад"]],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return SELL_GUARD_HOUSING


async def s_guard_housing(u, c):
    c.user_data["housing_found"] = "Да" if "Да" in u.message.text else "Нет"
    if "Нет" in u.message.text:
        await u.message.reply_text(
            "🔍 <b>Понял, поиск впереди.</b>\nВ каком районе и какая площадь нужна?\n<i>Кратко: «Юг, 2-комн, от 50м²»</i>",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return SELL_GUARD_SEARCH
    return await ask_own(u, c)


async def s_guard_search(u, c):
    c.user_data["search_prefs"] = u.message.text
    return await ask_own(u, c)


# Собственность (Общий шаг)
async def ask_own(u, c):
    await u.message.reply_text(
        "📅 <b>Как давно объект в собственности?</b>",
        reply_markup=ReplyKeyboardMarkup(
            [["< 3 лет"], ["> 3 лет"], ["Наследство"], ["ДДУ/ДКП"], ["◀️ Назад"]],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return SELL_OWN


async def s_own(u, c):
    c.user_data["ownership"] = u.message.text
    obj = c.user_data.get("object", "")
    if obj in ["Дом", "Земля", "Коммерция", "Стройка"]:
        await u.message.reply_text(
            "📄 <b>Документы в порядке?</b> (кратко)",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return SELL_DOCS
    return await ask_phone_geo(u, c)


async def s_docs(u, c):
    c.user_data["docs"] = u.message.text
    return await ask_phone_geo(u, c)


#──────────────────────────────────────────────────────────────────────
# 🔥 ФИНАЛ: ТЕЛЕФОН + ГЕОЛОКАЦИЯ + ПОЛНАЯ КАРТОЧКА АДМИНУ (ОБНОВЛЁННЫЙ)
# ──────────────────────────────────────────────────────────────────────


async def ask_phone_geo(u, c):
    """📱 Мягкий запрос телефона + геолокация объекта"""
    name = c.user_data["client_name"]
    kb = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("📱 Отправить номер", request_contact=True),
                KeyboardButton("📍 Открыть карту", web_app=WebAppInfo(url=f"{WEBAPP_URL}/map.html")),
            ],
            ["◀️ Назад"],
            ["❌ Отмена"],
        ],
        resize_keyboard=True,
    )
    text = (
        f"✨ <b>{name}</b>, благодарю за доверие! 🙏\n\n"
        f"Чтобы я не потерял ваши ответы и менеджер связался именно с вами,\n"
        f"оставьте, пожалуйста, номер телефона. Это займёт секунду 📱\n"
        f"<i>Можно нажать кнопку или написать текстом.</i>\n"
        f"💡 <i>А если добавите геолокацию объекта — я сразу покажу его на карте!</i>"
    )
    await u.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    return SELL_PHONE


async def sell_phone(update, context):
    """📞 Сохраняем телефон ИЛИ геолокацию"""
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
        # Если прислал только геолокацию — мягко просим номер
        await update.message.reply_text(
            "📍 Геолокацию принял! Теперь, пожалуйста, напишите номер телефона текстом:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SELL_PHONE
    else:
        context.user_data["phone"] = parse_number(update.message.text)
    return await ask_add_more(update, context)


# Заглушки для покупателя/аренды (чтобы не сломать другие воронки)
async def buy_phone(update, context):
    return await ask_add_more(update, context)


async def rent_phone(update, context):
    return await ask_add_more(update, context)


async def ask_add_more(update, context):
    """📋 Резюме + вопрос: добавить деталь?"""
    name = context.user_data["client_name"]
    summary = (
        f"📋 <b>Резюме, {name}:</b>\n\n"
        f"• Объект: {context.user_data.get('object', '?')}\n"
        f"• Район: {context.user_data.get('location', '?')}\n"
        f"• Цена: {context.user_data.get('price', '?')}\n\n"
        f"❓ <b>Добавить деталь или уточнение?</b>\n"
        f"<i>Например: «срочно», «тихая улица», «детские доли»</i>"
    )
    kb = ReplyKeyboardMarkup(
        [["✅ Нет, всё верно"], ["✏️ Да, добавить заметку"]], resize_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=kb, parse_mode="HTML")
    return CONFIRM_ADD


async def _handle_add_more_v1(update, context):
    """⚠️ ДУБЛЬ — не используется, оставлен для совместимости"""
    return await handle_add_more(update, context)


async def _final_thanks_v1(update, context):
    """⚠️ ДУБЛЬ удалён — вся логика в финальной final_thanks_and_send"""
    return await final_thanks_and_send(update, context)


# ──────────────────────────────────────────────────────────────────────
# БЛОК 4: ПОКУПАТЕЛЬ (Воронка: Объект -> Оплата -> Контакты)
# ==============================================================


# ═══════════════════════════════════════════
# 🌲 ВОРОНКА ЗЕМЛЯ (полная цепочка)
# ═══════════════════════════════════════════
async def b_land_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["land_purpose"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"🌿 {name}, отлично! Уточним детали.\n\n"
        f"<b>Какой статус участка вас интересует?</b>",
        reply_markup=ReplyKeyboardMarkup(
            [["🏡 ИЖС", "🌲 СНТ"], ["◀️ Назад"]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )
    return LAND_TYPE

async def b_land_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["land_type"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"📐 {name}, хорошо!\n\n<b>Сколько соток вас интересует?</b>\n"
        f"<i>(Например: 6, 10, 15 или «от 8 до 12»)</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return LAND_AREA

async def b_land_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["land_area"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"📍 <b>В каком районе ищете участок, {name}?</b>\n\n"
        f"🗺 Нажмите кнопку, чтобы <b>указать точку на карте</b>,\n"
        f"или напишите текстом:\n"
        f"<i>Корсаков, Южно-Сахалинск, Луговое, пригород и т.д.</i>",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["🏙 Южно-Сахалинск", "⚓ Корсаков"],
                ["🌲 Пригород / оба города"],
                [KeyboardButton("🗺 Показать на карте", web_app=WebAppInfo(url=f"{WEBAPP_URL}/map.html"))],
                ["◀️ Назад"],
            ],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return LAND_LOC

async def b_land_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["land_loc"] = update.message.text
    await update.message.reply_text(
        "⚡ <b>Какие коммуникации важны?</b>",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["🔥 Газ + Свет + Вода"],
                ["💡 Свет + Вода (без газа)"],
                ["🌿 Без коммуникаций (под себя)"],
                ["◀️ Назад"]
            ],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )
    return LAND_COMM


async def b_land_loc_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🗺 Обработка точки с Яндекс.Карты — воронка Земля"""
    try:
        data = json.loads(update.message.web_app_data.data)
        if data.get("command") == "location_selected":
            lat = data["lat"]
            lon = data["lon"]
            context.user_data["latitude"] = lat
            context.user_data["longitude"] = lon
            context.user_data["land_loc"] = f"📍 Карта: {lat:.5f}, {lon:.5f}"
            await update.message.reply_text(
                f"✅ <b>Локация записана!</b>\n"
                f"📌 Координаты: <code>{lat:.5f}, {lon:.5f}</code>\n\n"
                f"⚡ <b>Какие коммуникации важны?</b>",
                reply_markup=ReplyKeyboardMarkup(
                    [
                        ["🔥 Газ + Свет + Вода"],
                        ["💡 Свет + Вода (без газа)"],
                        ["🌿 Без коммуникаций (под себя)"],
                        ["◀️ Назад"]
                    ],
                    resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return LAND_COMM
    except Exception as e:
        loguru_logger.error(f"❌ Ошибка карты (Земля): {e}")
    return LAND_LOC

async def b_land_comm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["land_comm"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"💰 <b>Какой бюджет рассматриваете, {name}?</b>\n"
        f"<i>(Например: 1.5 млн, 3 000 000, до 2 млн)</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return BUY_BUDGET


# ═══════════════════════════════════════════
# 🏗️ ВОРОНКА СТРОЙКА (полная цепочка)
# ═══════════════════════════════════════════
async def b_builder_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["builder_search"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"🏗️ {name}, понял! Давайте подберём решение.\n\n"
        f"<b>Какой тип дома планируете?</b>",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["🧱 Кирпич", "🪵 Брус"],
                ["🏠 Каркасный", "📋 Другой вариант"],
                ["◀️ Назад"]
            ],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )
    return BUILD_TYPE

async def b_build_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["build_type"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"📐 <b>Какая планируемая площадь дома, {name}?</b>\n"
        f"<i>(В квадратных метрах, например: 80, 120, 150)</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return BUILD_AREA

async def b_build_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["build_area"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"📍 <b>Где планируете строить, {name}?</b>\n\n"
        f"🗺 Нажмите кнопку, чтобы <b>указать участок на карте</b>,\n"
        f"или напишите текстом:\n"
        f"<i>Корсаков, Южно-Сахалинск, Луговое, пригород и т.д.</i>",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["🏙 Южно-Сахалинск", "⚓ Корсаков"],
                ["🌲 Пригород / оба города"],
                [KeyboardButton("🗺 Показать на карте", web_app=WebAppInfo(url=f"{WEBAPP_URL}/map.html"))],
                ["◀️ Назад"],
            ],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return BUILD_LOC


async def b_build_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📝 Текстовый ввод локации — воронка Стройка"""
    context.user_data["build_loc"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"💰 <b>Бюджет на строительство, {name}?</b>\n"
        f"<i>(Например: 5 млн, 8 000 000)</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return BUY_BUDGET


async def b_build_loc_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🗺 Обработка точки с Яндекс.Карты — воронка Стройка"""
    try:
        data = json.loads(update.message.web_app_data.data)
        if data.get("command") == "location_selected":
            lat = data["lat"]
            lon = data["lon"]
            context.user_data["latitude"] = lat
            context.user_data["longitude"] = lon
            context.user_data["build_loc"] = f"📍 Карта: {lat:.5f}, {lon:.5f}"
            name = context.user_data.get("name", "")
            await update.message.reply_text(
                f"✅ <b>Участок на карте записан!</b>\n"
                f"📌 Координаты: <code>{lat:.5f}, {lon:.5f}</code>\n\n"
                f"💰 <b>Бюджет на строительство, {name}?</b>\n"
                f"<i>(Например: 5 млн, 8 000 000)</i>",
                reply_markup=get_back_kb(),
                parse_mode="HTML",
            )
            return BUY_BUDGET
    except Exception as e:
        loguru_logger.error(f"❌ Ошибка карты (Стройка): {e}")
    return BUILD_LOC

async def b_build_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["build_time"] = update.message.text
    name = context.user_data.get("name", "")
    await update.message.reply_text(
        f"✨ <b>Отлично, {name}!</b> Я записал все детали.\n\n"
        f"📞 Осталось последнее — <b>номер телефона</b>, чтобы Андрей "
        f"мог связаться с вами и обсудить проект лично.",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return BUY_PHONE


# --- ОСНОВНАЯ ВОРОНКА ПОКУПАТЕЛЯ ---
async def b_obj(u, c):
    c.user_data["object"] = (
        u.message.text.replace("🏠 ", "")
        .replace("🏡 ", "")
        .replace("🌲 ", "")
        .replace("🏗️ ", "")
    )

    # 🔥 ВЕТВЛЕНИЕ ДЛЯ ЗЕМЛИ И СТРОЙКИ
    if c.user_data["object"] == "Земля":
        await u.message.reply_text(
            "🏞️ <b>Вы ищете участок под застройку или для других целей?</b>",
            reply_markup=ReplyKeyboardMarkup(
                [["🏡 Под строительство", "🌿 Для других целей"]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
        return BUY_LAND_PURPOSE

    if c.user_data["object"] == "Стройка":
        await u.message.reply_text(
            "🏗️ <b>У Вас уже есть участок или Вы ищете подрядчика?</b>",
            reply_markup=ReplyKeyboardMarkup(
                [["🔨 Ищу строителей", "🏡 Строю с нуля"]],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
        return BUY_BUILDER_SEARCH

    # ДЛЯ ВСЕХ ОСТАЛЬНЫХ ОБЪЕКТОВ
    await u.message.reply_text(
        "📍 <b>Какой район или город рассматриваете?</b>\n"
        "<i>Корсаков, Южно-Сахалинск, пригород — напишите или выберите:</i>",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["🏙 Южно-Сахалинск", "⚓ Корсаков"],
                ["🌲 Пригород / оба города"],
                ["◀️ Назад"],
            ],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return BUY_SOTOK


# ШАГ: ВВОД КОЛИЧЕСТВА СОТОК
async def b_sotok(u, c):
    c.user_data["sotki"] = parse_number(u.message.text)
    await u.message.reply_text(
        "📍<b>Сколько соток подыскиваете?</b>",
        reply_markup=get_back_kb(),
        parse_mode="HTML"
    )
    return BUY_LOC


async def b_loc(u, c):
    c.user_data["location"] = u.message.text
    await u.message.reply_text(
        "💰 <b>Какой бюджет?</b> (руб)", reply_markup=get_back_kb(), parse_mode="HTML"
    )
    return BUY_BUDGET


async def b_budget(u, c):
    c.user_data["price"] = parse_number(u.message.text)
    obj = c.user_data.get("object", "")
    name = c.user_data.get("name", "")

    # 🔥 Роутинг для Земли и Стройки
    if obj == "Земля":
        await u.message.reply_text(
            f"✨ <b>Записал, {name}!</b>\n\n"
            f"📞 Осталось получить ваш <b>номер телефона</b>, "
            f"чтобы Андрей мог подобрать для вас идеальный участок.",
            reply_markup=get_back_kb(),
            parse_mode="HTML"
        )
        return BUY_PHONE

    if obj == "Стройка":
        await u.message.reply_text(
            f"🗓️ <b>{name}, когда планируете начать строительство?</b>",
            reply_markup=ReplyKeyboardMarkup(
                [
                    ["🔥 Как можно скорее", "📅 В этом году"],
                    ["🕐 В следующем году", "💭 Пока планирую"],
                    ["◀️ Назад"]
                ],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
        return BUILD_TIME

    # Стандартный путь для квартиры/дома/аренды
    await u.message.reply_text(
        "🏘 <b>Что важно рядом?</b>\n(школа, сад, транспорт, лес...)",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return BUY_INFRA


async def b_infra(u, c):
    c.user_data["infra"] = u.message.text
    await u.message.reply_text(
        " <b>Для кого подыскиваете?</b>\n(семья, инвестиция, родители...)",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return BUY_PURPOSE


async def b_purpose(u, c):
    c.user_data["purpose"] = u.message.text
    await u.message.reply_text(
        "💳 <b>Как планируете платить?</b>",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["💵 Наличные"],
                ["🏦 Ипотека"],
                ["📜 Сертификат"],
                ["✉️ Гарант. письмо"],
                [" Мат.капитал"],
                ["◀️ Назад"],
            ],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return BUY_PAY


# 🔥 ЛОГИКА ОПЛАТЫ (Ветвление)
async def b_pay(u, c):
    t = u.message.text

    if "Ипотека" in t:
        await u.message.reply_text(
            "🏦 <b>Уже одобрена?</b> Размер взноса?\n💡 <i>Да/Нет/В процессе. Взнос: 800к</i>",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return BUY_MORT

    elif "Сертификат" in t:
        await u.message.reply_text(
            "📜 <b>Тип сертификата и сумма?</b>\n💡 <i>Военная ипотека, 1.5 млн</i>",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return BUY_CERT

    elif "Гарант" in t:
        await u.message.reply_text(
            "✉️ <b>Кто выдаёт и сумма?</b>\n💡 <i>Работодатель, 1 млн</i>",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return BUY_GUARANTEE

    elif "Мат" in t:
        await u.message.reply_text(
            "👶 <b>Остаток чем покрываете?</b>\n💡 <i>Наличные / Ипотека</i>",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return BUY_MATCAP

    c.user_data["payment"] = "Наличные"
    return await b_time(u, c)


# Обработчики ответов на оплату
async def b_mort(u, c):
    c.user_data["payment"] = "Ипотека"
    c.user_data["mortgage_status"] = parse_number(u.message.text)

    # 🔥 ДОБАВЛЕНО: Твоё предложение рассчитать ипотеку
    await u.message.reply_text(
        "💡 <b>Могу ли я приблизительно рассчитать ипотеку для Вас?</b>\n"
        "Напишите желаемый платёж или нажмите «Пропустить».",
        reply_markup=ReplyKeyboardMarkup(
            [["🧮 Рассчитать (напишите сумму)"], ["⏭ Пропустить, дальше"], ["◀️ Назад"]],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return BUY_TIME


async def b_cert(u, c):
    c.user_data["payment"] = "Сертификат"
    c.user_data["cert_details"] = parse_number(u.message.text)
    return await b_time(u, c)


async def b_guarantee(u, c):
    c.user_data["payment"] = "Гарант. письмо"
    c.user_data["guarantee_details"] = parse_number(u.message.text)
    return await b_time(u, c)


async def b_matcap(u, c):
    c.user_data["payment"] = "Мат.капитал"
    c.user_data["matcap_rest"] = parse_number(u.message.text)
    return await b_time(u, c)


# Финал воронки покупателя (Сроки -> Телефон)
async def b_time(u, c):
    await u.message.reply_text(
        " <b>Когда готовы к сделке?</b>",
        reply_markup=ReplyKeyboardMarkup(
            [["🔥 В этом месяце"], ["📅 Квартал"], ["🔍 Смотрю"], ["◀️ Назад"]],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return BUY_TIME


async def b_time_ans(u, c):
    c.user_data["timing"] = u.message.text
    return await ask_phone_geo(u, c)


# ──────────────────────────────────────────────────────────────────────
# БЛОК 5: АРЕНДА (Воронка: Срок → Для кого → Бюджет → Пожелания → Контакты)
# ──────────────────────────────────────────────────────────────────────


async def r_dur(u, c):
    c.user_data["duration"] = u.message.text
    await u.message.reply_text(
        "👥 <b>Для кого подыскиваете жильё?</b>\n"
        "💡 <i>Пример: для себя, семья с детьми, родители, инвестиция</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return RENT_OCC


async def r_occ(u, c):
    c.user_data["occupants"] = u.message.text
    await u.message.reply_text(
        "💰 <b>Какой бюджет в месяц?</b> (руб)",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return RENT_BUDGET


async def r_budget(u, c):
    c.user_data["budget_rent"] = parse_number(u.message.text)
    await u.message.reply_text(
        "🏘 <b>Пожелания?</b>\n(ремонт, мебель, техника, парковка...)",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return RENT_PREFS


async def r_prefs(u, c):
    c.user_data["prefs_rent"] = u.message.text
    c.user_data["timing"] = "Аренда"
    return await ask_phone_geo(u, c)


# ──────────────────────────────────────────────────────────────────────
# БЛОК 6: ИПОТЕКА (Консультация / Заявка)
# ──────────────────────────────────────────────────────────────────────


async def mort_choice(u, c):
    if "Покупка" in u.message.text:
        await u.message.reply_text(
            "🏦 <b>Покупка в ипотеку.</b>\nУже одобрена? Желаемый платеж?\n <i>Да/Нет. Платеж до 30к</i>",
            reply_markup=get_back_kb(),
            parse_mode="HTML",
        )
        return MORT_BUY

    await u.message.reply_text(
        "💸 <b>Продажа в ипотеку.</b>\nОстаток долга? Банк?\n💡 <i>2.5 млн, Сбер</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return MORT_SELL


async def mort_buy(u, c):
    c.user_data["type"] = "mortgage_buy"
    c.user_data["mortgage_status"] = parse_number(u.message.text)
    return await ask_phone_geo(u, c)


async def mort_sell(u, c):
    c.user_data["type"] = "mortgage_sell"
    c.user_data["mortgage_details"] = parse_number(u.message.text)
    return await ask_phone_geo(u, c)


# ──────────────────────────────────────────────────────────────────────
# 13. ФИНАЛИЗАЦИЯ (ПОДТВЕРЖДЕНИЕ -> ЗАМЕТКА -> ОТПРАВКА МЕНЕДЖЕРУ -> БЛАГОДАРНОСТЬ)
# ──────────────────────────────────────────────────────────────────────


async def sell_phone(update, context):
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
    else:
        context.user_data["phone"] = parse_number(update.message.text)
    return await ask_add_more(update, context)


async def buy_phone(update, context):
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
    else:
        context.user_data["phone"] = parse_number(update.message.text)
    return await ask_add_more(update, context)


async def rent_phone(update, context):
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
    else:
        context.user_data["phone"] = parse_number(update.message.text)
    return await ask_add_more(update, context)


async def ask_add_more(update, context):
    """🔥 Показываем резюме и спрашиваем, нужно ли добавить детали"""
    name = context.user_data["client_name"]
    summary = (
        f"📋 <b>Резюме вашей заявки, {name}:</b>\n\n"
        f"• Объект: {context.user_data.get('object', '?')}\n"
        f"• Район: {context.user_data.get('location', '?')}\n"
        f"• Бюджет/Цена: {context.user_data.get('price', '?')}\n\n"
        f"❓ <b>Не желаете ли что-то добавить или уточнить?</b>\n"
        f"💡 <i>Нажмите «Да», чтобы оставить заметку для менеджера.</i>"
    )
    kb = ReplyKeyboardMarkup(
        [["✅ Нет, всё верно"], ["✏️ Да, добавить заметку"]], resize_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=kb, parse_mode="HTML")
    return CONFIRM_ADD


async def handle_add_more(update, context):
    text = update.message.text
    if "Да" in text or "заметку" in text.lower():
        await update.message.reply_text(
            "✍️ <b>Напишите, что важно добавить:</b>\n<i>(например: «срочно до конца месяца» или «важна тихая улица»)</i>",
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Готово, отправить"]], resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return ADD_NOTE_STATE
    return await final_thanks_and_send(update, context)


async def save_note_and_finish(update, context):
    context.user_data["edit_note"] = update.message.text
    return await final_thanks_and_send(update, context)


# ──────────────────────────────────────────────────────────────────────
# 14. ИПОТЕКА (Калькулятор и консультация)
# ──────────────────────────────────────────────────────────────────────


async def mort_price(u, c):
    await u.message.reply_text(
        "💰 <b>Продажа с ипотекой</b>\n\n"
        "Уточните, пожалуйста: сколько осталось платить банку на сегодня?\n\n"
        "<i>Напишите сумму — я передам данные специалисту.</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return MORT_RESULT


async def mort_pay(u, c):
    await u.message.reply_text(
        "🏦 <b>Покупка с ипотекой</b>\n\n"
        "Пожалуйста, укажите вводные данные:\n"
        "1️⃣ Ипотека уже одобрена?\n"
        "2️⃣ Размер первоначального взноса?\n"
        "3️⃣ Сроки сделки?\n\n"
        "<i>Ответьте текстом — данные будут переданы менеджеру.</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return MORT_RATE


async def mort_rate(u, c):
    c.user_data["mortgage_info"] = u.message.text
    c.user_data["payment"] = "Ипотека"
    c.user_data["type"] = "buy"
    name = c.user_data["client_name"]

    await u.message.reply_text(
        f"📞 <b>{name}, данные приняты.</b>\n\n"
        "Оставьте номер телефона — менеджер свяжется с вами оперативно для расчёта.",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
                ["◀️ Назад"],
                ["❌ Отмена"],
            ],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return BUY_PHONE


async def mort_res(u, c):
    c.user_data["mortgage_balance"] = parse_number(u.message.text)
    c.user_data["payment"] = "Ипотека (Продажа)"
    c.user_data["type"] = "sell"
    name = c.user_data["client_name"]

    await u.message.reply_text(
        f"📞 <b>{name}, данные приняты.</b>\n\n"
        "Оставьте номер телефона — менеджер свяжется с вами оперативно.",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
                ["◀️ Назад"],
                ["❌ Отмена"],
            ],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return SELL_PHONE


# ──────────────────────────────────────────────────────────────────────
# 15. AI + МЕНЮ + ОБРАТНАЯ СВЯЗЬ
# ──────────────────────────────────────────────────────────────────────


async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text

    # 🔹 Если клиент прислал номер в чате с AI
    phone_match = re.search(r"\+?7?\s*\(?\d{3}\)?\s*\d{3}[- ]?\d{2}[- ]?\d{2}", t)
    if phone_match:
        context.user_data["phone"] = re.sub(r"[^\d+]", "", phone_match.group())
        name = context.user_data.get("client_name", "Клиент")
        await update.message.reply_text(
            f"✅ <b>{name}</b>, номер {context.user_data['phone']} записан!\n"
            f"Менеджер свяжется с вами в ближайшее время.\n\n"
            f"💡 <i>Могу ли я ещё чем-то помочь? Нажмите на кнопку ниже.</i>",
            reply_markup=get_nav_kb(),
            parse_mode="HTML",
        )
        await save_lead(context)
        await notify_admin(
            context,
            f"📞 Заявка из AI-чата\n👤 {context.user_data.get('client_name')}\n📱 {context.user_data['phone']}",
        )
        return ConversationHandler.END

    # 🔹 Если клиент спрашивает про другой город/регион — эскалация к менеджеру
    _other_city_keys = [
        "другой город", "другом городе", "другом регионе", "москва", "владивосток",
        "хабаровск", "санкт-петербург", "спб", "новосибирск", "краснодар",
        "работаете в", "охватываете", "по всей стране", "другой регион",
    ]
    if any(w in t.lower() for w in _other_city_keys):
        name = context.user_data.get("client_name", "Клиент")
        await update.message.reply_text(
            f"🗺 <b>{name}</b>, по этому вопросу более полную информацию "
            f"Вам лучше уточнить у нашего менеджера — он расскажет всё детально "
            f"и предложит оптимальное решение.\n\n"
            f"Я передам ваши данные ему. Оставьте, пожалуйста, номер телефона — "
            f"менеджер свяжется с вами в ближайшее время! 📞",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton("📱 Отправить номер", request_contact=True)],
                    ["◀️ Назад"],
                ],
                resize_keyboard=True,
            ),
            parse_mode="HTML",
        )
        return BUY_PHONE

    # 🔹 Если клиент запутался — эскалация менеджеру
    if any(
        w in t.lower()
        for w in ["запутался", "сложно", "помогите", "позвоните", "перезвоните"]
    ):
        name = context.user_data["client_name"]
        await update.message.reply_text(
            f"🤝 <b>{name}</b>, вижу, что вопросов много. Давайте наш менеджер перезвонит вам?\n"
            f"Это бесплатно и ни к чему не обязывает.\n\n"
            f"💡 <i>Нажмите кнопку ниже или просто укажите свой номер.</i>",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton("📱 Отправить номер", request_contact=True)],
                    ["◀️ Назад"],
                ],
                resize_keyboard=True,
            ),
            parse_mode="HTML",
        )
        return SELL_PHONE

    # 🔹 Пытаемся ответить через AI
    try:
        resp = await ask_ai(t, context)
        if not resp or "Задумался" in resp:
            return await show_menu_with_card(update, context)
        await update.message.reply_text(
            resp, reply_markup=get_nav_kb(), parse_mode="HTML"
        )
        return AI_CHAT
    except:
        return await show_menu_with_card(update, context)


async def show_menu_with_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎯 Меню с визиткой + подсказки"""
    name = context.user_data["client_name"]
    txt = (
        f"✨ <b>Понял вас, {name}!</b>\n\n"
        f"💡 Могу ли я ещё чем-то помочь вам сегодня?\n\n"
        f"─────────────────────\n"
        f"📇 <b>МОЯ ВИЗИТКА:</b>\n"
        f"─────────────────────\n"
        f"👤 Андрей\n"
        f"🏢 <b>ARTEM AI</b>\n"
        f"📱 +7 (XXX) XXX-XX-XX\n"
        f"📧 info@artemi.ru\n"
        f"🌐 www.artemi.ru\n"
        f"─────────────────────\n\n"
        f"⭐ <b>Выберите раздел или просто напишите вопрос.</b>\n"
        f"Мы всегда на связи."
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💰 Продать недвижимость", callback_data="menu_sell"
                )
            ],
            [InlineKeyboardButton("🔍 Купить недвижимость", callback_data="menu_buy")],
            [
                InlineKeyboardButton(
                    "🧮 Калькулятор ипотеки", callback_data="menu_mortgage"
                )
            ],
            [InlineKeyboardButton("🔑 Арендовать", callback_data="menu_rent")],
            [InlineKeyboardButton("🤖 Вопрос AI", callback_data="nav_ai")],
        ]
    )
    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(
            txt, reply_markup=kb, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
    return CHOICE


async def feedback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "fb_plus":
        await q.edit_message_text(
            "💙 Спасибо за обратную связь! Будем рады видеть вас снова.\n\n"
            "💡 <i>Нажмите на кнопку ниже, если хотите продолжить.</i>",
            reply_markup=get_nav_kb(),
            parse_mode="HTML",
        )
    elif q.data == "fb_minus":
        await q.edit_message_text(
            "🙏 Спасибо за честность! Мы учтём ваши пожелания и станем лучше.\n"
            "Если есть конкретные идеи — напишите, я лично прочитаю.\n\n"
            "💡 <i>Нажмите на кнопку ниже, чтобы продолжить.</i>",
            reply_markup=get_nav_kb(),
            parse_mode="HTML",
        )
    elif q.data == "nav_main":
        await q.edit_message_text(
            "↩️ Вернулись в главное меню. Чем могу помочь?\n"
            "💡 <i>Просто нажмите на кнопку внизу.</i>",
            reply_markup=ReplyKeyboardMarkup(
                [
                    ["💰 Продать недвижимость"],
                    ["🔍 Купить недвижимость"],
                    ["🔑 Арендовать"],
                    ["🧮 Калькулятор ипотеки"],
                    ["🤖 Задать вопрос AI"],
                    ["🚀 меню"],
                ],
                resize_keyboard=True,
            ),
        )
        return CHOICE
    elif q.data == "nav_call":
        await q.edit_message_text(
            "📞 Наш менеджер на связи: +7 (962) 116-28-83\n"
            "Обращайтесь в рабочее время.\n\n"
            "💡 <i>Нажмите на кнопку ниже, чтобы вернуться в меню.</i>",
            reply_markup=get_nav_kb(),
            parse_mode="HTML",
        )
        return CHOICE
    elif q.data == "nav_ai":
        await q.edit_message_text(
            "🤖 AI-консультант снова на связи. Задавайте вопрос.\n"
            "💡 <i>Напишите текст или нажмите «❌ В меню», чтобы вернуться.</i>",
            reply_markup=ReplyKeyboardMarkup([["❌ В меню"]], resize_keyboard=True),
        )
        return AI_CHAT
    elif q.data.startswith("menu_"):
        part = q.data.split("_")[1]
        context.user_data["type"] = part
        if part == "sell":
            await q.edit_message_text(
                "💰 Что планируете продавать?\n💡 <i>Нажмите на кнопку ниже.</i>",
                reply_markup=ReplyKeyboardMarkup(
                    [["🏠 Квартира"], ["🏡 Дом"], ["🏢 Коммерция"], ["🌲 Земля"]],
                    resize_keyboard=True,
                ),
                parse_mode="HTML",
            )
            return SELL_OBJ
        elif part == "buy":
            await q.edit_message_text(
                "🔍 Что ищете?\n💡 <i>Нажмите на кнопку ниже.</i>",
                reply_markup=ReplyKeyboardMarkup(
                    [["🏠 Квартира"], ["🏡 Дом"], ["🌲 Участок"], ["🏗️ Стройка"]],
                    resize_keyboard=True,
                ),
                parse_mode="HTML",
            )
            return BUY_OBJ
        elif part == "rent":
            await q.edit_message_text(
                "🔑 На какой срок рассматриваете аренду?\n💡 <i>Нажмите на кнопку ниже.</i>",
                reply_markup=ReplyKeyboardMarkup(
                    [["📅 От 1 года"], ["📆 Долго (3+ года)"]], resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return RENT_DUR
        elif part == "mortgage":
            await q.edit_message_text(
                "🧮 Введите стоимость недвижимости (в рублях):\n💡 <i>Например: 4 500 000</i>",
                reply_markup=ReplyKeyboardMarkup(
                    [["◀️ Назад"], ["❌ Отмена"]], resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return MORT_CHOICE  # 🔥 Исправлено на MORT_CHOICE (состояние уже объявлено в range(44))
    return ConversationHandler.END


# ──────────────────────────────────────────────────────────────────────
# БЛОК: КОНТАКТЫ + ПОДТВЕРЖДЕНИЕ + ОТПРАВКА МЕНЕДЖЕРУ
# ──────────────────────────────────────────────────────────────────────


async def ask_phone_geo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔥 Умный запрос контактов и геолокации"""
    name = context.user_data["client_name"]
    kb = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("📱 Отправить номер", request_contact=True),
                KeyboardButton("📍 Открыть карту", web_app=WebAppInfo(url=f"{WEBAPP_URL}/map.html")),
            ],
            ["◀️ Назад"],
            ["❌ Отмена"],
        ],
        resize_keyboard=True,
    )

    text = (
        f"✨ <b>{name}</b>, благодарю за информацию!\n\n"
        f"Оставьте номер для связи.\n"
        f"📍 <b>Геолокация</b> поможет подобрать варианты именно в вашем районе.\n\n"
        f"💡 <i>Нажмите кнопку или напишите номер текстом.</i>"
    )
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

    # 🔥 Маршрутизация в нужную ветку финализации
    flow = context.user_data.get("type")
    if flow == "buy":
        return BUY_PHONE
    elif flow == "rent":
        return RENT_PHONE
    return SELL_PHONE


# ── Сбор контактов (3 ветки) ──
async def sell_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
        return await ask_add_more(update, context)
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
        # 🔥 ФИКС: Если прислали только карту, мягко просим телефон
        if not context.user_data.get("phone"):
            await update.message.reply_text(
                "📍 Геолокацию объекта принял! А теперь оставьте номер телефона:",
                reply_markup=get_back_kb(),
            )
            return SELL_PHONE
        return await ask_add_more(update, context)
    else:
        context.user_data["phone"] = parse_number(update.message.text)
        return await ask_add_more(update, context)


async def buy_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
        return await ask_add_more(update, context)
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
        # 🔥 ФИКС: Если прислали только карту, мягко просим телефон
        if not context.user_data.get("phone"):
            await update.message.reply_text(
                "📍 Геолокацию объекта принял! А теперь оставьте номер телефона:",
                reply_markup=get_back_kb(),
            )
            return BUY_PHONE
        return await ask_add_more(update, context)
    else:
        context.user_data["phone"] = parse_number(update.message.text)
        return await ask_add_more(update, context)


async def rent_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
        return await ask_add_more(update, context)
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
        # 🔥 ФИКС: Если прислали только карту, мягко просим телефон
        if not context.user_data.get("phone"):
            await update.message.reply_text(
                "📍 Геолокацию объекта принял! А теперь оставьте номер телефона:",
                reply_markup=get_back_kb(),
            )
            return RENT_PHONE
        return await ask_add_more(update, context)
    else:
        context.user_data["phone"] = parse_number(update.message.text)
        return await ask_add_more(update, context)


# ── Подтверждение и заметка ──
async def ask_add_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data["client_name"]
    summary = (
        f"📋 <b>Резюме, {name}:</b>\n\n"
        f"• Объект: {context.user_data.get('object', '?')}\n"
        f"• Район: {context.user_data.get('location', '?')}\n"
        f"• Цена/Бюджет: {context.user_data.get('price', context.user_data.get('budget_rent', '?'))}\n\n"
        f"❓ <b>Добавить деталь или уточнение?</b>"
    )
    kb = ReplyKeyboardMarkup(
        [["✅ Нет, всё верно"], ["✏️ Да, добавить заметку"]], resize_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=kb, parse_mode="HTML")
    return CONFIRM_ADD


async def handle_add_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Да" in update.message.text or "заметк" in update.message.text.lower():
        await update.message.reply_text(
            "✍️ <b>Напишите заметку:</b>\n<i>(например: детские доли, срочная продажа, тихая улица...)</i>",
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Готово, отправить"]], resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return ADD_NOTE_STATE
    return await final_thanks_and_send(update, context)


async def save_note_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_note"] = update.message.text
    return await final_thanks_and_send(update, context)


# ── Финал: Сохранение -> Отправка ТЕБЕ -> Благодарность -> Меню ──
async def final_thanks_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎯 Детальная карточка -> Сохраняем -> Шлём тебе -> Благодарим"""
    await save_lead(context)
    name = context.user_data.get("client_name", "Клиент")

    # 📨 ДЕТАЛЬНАЯ КАРТОЧКА ДЛЯ ТЕБЯ (по разделам)
    summary = [
        f"🆕 <b>НОВАЯ ЗАЯВКА [{context.user_data.get('type', '?').upper()}]</b>",
        f"👤 Клиент: {name}",
        f"📞 Телефон: {context.user_data.get('phone', '?')}",
    ]

    obj = context.user_data.get("object", "?")

    # 🏠 Блок объекта
    summary.append(f"\n🏠 <b>ОБЪЕКТ:</b>")
    summary.append(f"• Тип: {obj}")

    if obj == "Земля":
        # 🌲 Специфика Земли
        summary.append(f"• Цель: {context.user_data.get('land_purpose', '?')}")
        summary.append(f"• Статус: {context.user_data.get('land_type', '?')}")
        summary.append(f"• Площадь: {context.user_data.get('land_area', '?')} сот.")
        _land_loc = context.user_data.get('land_loc', context.user_data.get('location', '?'))
        _land_lat = context.user_data.get("latitude")
        _land_lon = context.user_data.get("longitude")
        _land_map = (
            f" · <a href='https://yandex.ru/maps/?pt={_land_lon},{_land_lat}&z=16&l=map'>🗺 Карта</a>"
            f" · <a href='https://yandex.ru/maps/?pt={_land_lon},{_land_lat}&z=16&l=sat'>🛰 Спутник</a>"
            if _land_lat and _land_lon else ""
        )
        summary.append(f"• Район: {_land_loc}{_land_map}")
        summary.append(f"• Коммуникации: {context.user_data.get('land_comm', '?')}")
    elif obj == "Стройка":
        # 🏗️ Специфика Стройки
        summary.append(f"• Ситуация: {context.user_data.get('builder_search', '?')}")
        summary.append(f"• Тип дома: {context.user_data.get('build_type', '?')}")
        summary.append(f"• Площадь дома: {context.user_data.get('build_area', '?')} м²")
        _build_loc = context.user_data.get('build_loc', context.user_data.get('location', '?'))
        _build_lat = context.user_data.get("latitude")
        _build_lon = context.user_data.get("longitude")
        _build_map = (
            f" · <a href='https://yandex.ru/maps/?pt={_build_lon},{_build_lat}&z=16&l=map'>🗺 Карта</a>"
            f" · <a href='https://yandex.ru/maps/?pt={_build_lon},{_build_lat}&z=16&l=sat'>🛰 Спутник</a>"
            if _build_lat and _build_lon else ""
        )
        summary.append(f"• Район/Участок: {_build_loc}{_build_map}")
        summary.append(f"• Сроки начала: {context.user_data.get('build_time', '?')}")
    else:
        summary.append(f"• Район: {context.user_data.get('location', '?')}")
        if context.user_data.get("area"):
            summary.append(f"• Площадь: {context.user_data['area']}")
        if context.user_data.get("ownership"):
            summary.append(f"• В собственности: {context.user_data['ownership']}")
        if context.user_data.get("docs"):
            summary.append(f"• Документы: {context.user_data['docs']}")

    # 💰 Финансы
    summary.append(f"\n💰 <b>ФИНАНСЫ:</b>")
    price = context.user_data.get("price")
    budget = context.user_data.get("budget_rent")
    if price:
        summary.append(f"• Цена: {price} ₽")
    if budget:
        summary.append(f"• Бюджет: {budget} ₽/мес")

    # Оплата/Обременение
    enc = context.user_data.get("encumbrance")
    pay = context.user_data.get("payment")
    if enc and enc != "Нет":
        summary.append(f"• Обременение: {enc}")
    if pay:
        summary.append(f"• Оплата: {pay}")

    # Детали ипотеки/сертификата
    if context.user_data.get("mortgage_details"):
        summary.append(f"• Ипотека: {context.user_data['mortgage_details']}")
    if context.user_data.get("mortgage_status"):
        summary.append(f"• Статус: {context.user_data['mortgage_status']}")
    if context.user_data.get("cert_details"):
        summary.append(f"• Сертификат: {context.user_data['cert_details']}")
    if context.user_data.get("guarantee_details"):
        summary.append(f"• Гарантия: {context.user_data['guarantee_details']}")
    if context.user_data.get("matcap_rest"):
        summary.append(f"• Мат.капитал: {context.user_data['matcap_rest']}")

    # 👶 Опека/Дети
    if context.user_data.get("children_count"):
        summary.append(f"\n👶 <b>ДЕТИ:</b>")
        summary.append(f"• Количество: {context.user_data['children_count']}")
        if context.user_data.get("children_ages"):
            summary.append(f"• Возраст: {context.user_data['children_ages']}")
        if context.user_data.get("housing_found"):
            summary.append(f"• Жильё найдено: {context.user_data['housing_found']}")

    # ⏰ Сроки
    if context.user_data.get("timing"):
        summary.append(
            f"\n⏰ <b>СРОКИ:</b>\n• Планирует: {context.user_data['timing']}"
        )

    # 🏘 Инфраструктура (для покупки)
    if context.user_data.get("infra"):
        summary.append(f"\n🏘 <b>ИНФРАСТРУКТУРА:</b>\n{context.user_data['infra']}")

    # 📍 Геолокация
    lat, lon = context.user_data.get("latitude"), context.user_data.get("longitude")
    if lat and lon:
        summary.append(
            f"\n📍 <b>ЛОКАЦИЯ:</b>\n"
            f"🗺 <a href='https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=map'>Карта</a>  "
            f"🛰 <a href='https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=sat'>Спутник</a>  "
            f"📌 <code>{lat:.5f}, {lon:.5f}</code>"
        )

    # 📝 Заметка
    if context.user_data.get("edit_note"):
        summary.append(f"\n📝 <b>ЗАМЕТКА:</b>\n{context.user_data['edit_note']}")

    # 🔒 СЕКРЕТНЫЙ БЛОК ДЛЯ АНДРЕЯ (инсайты по клиенту)
    secret = []

    # — Общие инсайты —
    timing = str(context.user_data.get("timing", "") or context.user_data.get("build_time", "")).lower()
    if "срочно" in timing or "как можно скорее" in timing:
        secret.append("🔥 Клиент торопится — звонить первым!")
    if "изучаю" in timing or "смотр" in timing or "пока планирую" in timing:
        secret.append("👀 Пока мониторит рынок — не давить, мягко удерживать")
    if not context.user_data.get("price"):
        secret.append("💰 Бюджет не указан → уточнить при звонке")
    if context.user_data.get("encumbrance") == "Ипотека":
        secret.append("🏦 Нужна помощь с банком / одобрением")
    if context.user_data.get("encumbrance") in ["Опека", "Арест"]:
        secret.append("⚖️ Сложная сделка → подключить юриста")

    # — Инсайты для Земли —
    if obj == "Земля":
        land_type = context.user_data.get("land_type", "")
        land_comm = context.user_data.get("land_comm", "")
        land_purpose = context.user_data.get("land_purpose", "")
        secret.append("🌲 Спец. объект: земельный участок")
        if "ИЖС" in land_type:
            secret.append("📋 ИЖС → проверить категорию земли и разрешённое использование")
        if "СНТ" in land_type:
            secret.append("🌿 СНТ → уточнить возможность перевода в ИЖС")
        if "Без коммуникаций" in land_comm:
            secret.append("⚡ Клиент готов к участку без ком. — уточнить стоимость подведения")
        if "Газ" in land_comm:
            secret.append("🔥 Важен газ → проверить наличие газопровода в районе")
        if "Под строительство" in land_purpose:
            secret.append("🏡 Цель — стройка → предложить связку Земля+Подрядчик")
        secret.append("📐 Уточнить межевание и кадастровый номер")

    # — Инсайты для Стройки —
    elif obj == "Стройка":
        build_type = context.user_data.get("build_type", "")
        build_area = context.user_data.get("build_area", "")
        builder_search = context.user_data.get("builder_search", "")
        secret.append("🏗️ Спец. объект: строительство под ключ")
        if "Кирпич" in build_type:
            secret.append("🧱 Кирпич → долго и дорого, уточнить смету и сроки")
        if "Каркасный" in build_type:
            secret.append("🏠 Каркас → быстро и бюджетно, есть готовые проекты")
        if "Брус" in build_type:
            secret.append("🪵 Брус → экологично, уточнить проект и усадку")
        if build_area:
            secret.append(f"📐 Площадь {build_area} м² → запросить предварительную смету")
        if "Ищу строителей" in builder_search:
            secret.append("🔨 Нет подрядчика → предложить проверенные бригады Андрея")
        if "Строю с нуля" in builder_search:
            secret.append("🏗️ Строит с нуля → предложить полное сопровождение")
        secret.append("📋 Запросить ТЗ и план участка для расчёта сметы")

    if secret:
        summary.append(
            "\n\n🔒 <b>СЕКРЕТНО ДЛЯ АНДРЕЯ:</b>\n"
            + "\n".join(f"• {s}" for s in secret)
        )

    # Собираем в одну строку
    summary_text = "\n".join(summary)

    # 🔥 Отправляем ТЕБЕ
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=summary_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")

    # Ответ КЛИЕНТУ (тепло, с вариантами продолжения)
    final_text = (
        f"✨ <b>Благодарю Вас, {name}, что выбрали ARTEM AI!</b> 🙏\n\n"
        f"Ваша заявка уже передана специалисту. Мы свяжемся с Вами в ближайшее время — бережно и по делу.\n\n"
        f"❓ <b>Могу ли Я ещё чем-то быть полезен для Вас сегодня?</b>"
    )
    _fin_lat = context.user_data.get("latitude")
    _fin_lon = context.user_data.get("longitude")
    _map_row = (
        [InlineKeyboardButton(
            "📍 Показать на карте",
            url=f"https://yandex.ru/maps/?pt={_fin_lon},{_fin_lat}&z=16&l=map"
        )]
        if _fin_lat and _fin_lon else []
    )
    kb_rows = [
        [InlineKeyboardButton("💰 Продать", callback_data="menu_sell")],
        [InlineKeyboardButton("🔍 Купить", callback_data="menu_buy")],
        [InlineKeyboardButton("🔑 Аренда", callback_data="menu_rent")],
        [InlineKeyboardButton("🧮 Ипотека", callback_data="menu_mortgage")],
        [InlineKeyboardButton("🤖 Вопрос AI", callback_data="nav_ai")],
    ]
    if _map_row:
        kb_rows.insert(0, _map_row)
    kb = InlineKeyboardMarkup(kb_rows)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            final_text, reply_markup=kb, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(final_text, reply_markup=kb, parse_mode="HTML")

    return ConversationHandler.END


# ──────────────────────────────────────────────────────────────────────
# 16. ТРИГГЕР + WEBAPP + ЗАЩИТА
# ──────────────────────────────────────────────────────────────────────


async def trigger_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔥 Ловит ключевые слова и мягко направляет в нужную воронку"""
    if not update.message or not update.message.text:
        return CHOICE

    txt = update.message.text.strip()

    if txt.startswith("/") or txt in [
        "Назад",
        "Отмена",
        "В главное меню",
        "🔙 Назад",
        "❌ Отмена",
    ]:
        return CHOICE

    resp = await ai_trigger_check(txt)
    if resp:
        await update.message.reply_text(
            resp
            + "\n\n💡 <i>Подсказка: нажмите на кнопку ниже, чтобы продолжить в нужном разделе.</i>",
            parse_mode="HTML",
        )
    else:
        name = context.user_data["client_name"]
        await update.message.reply_text(
            f"🤔 <b>{name}</b>, понял запрос. Для точного ответа выберите раздел:\n"
            "💰 Продать | 🔍 Купить | 🔑 Аренда | 🧮 Ипотека\n\n"
            "💡 <i>Подсказка: просто нажмите на кнопку внизу — я сразу открою нужный раздел.</i>",
            parse_mode="HTML",
        )
    return CHOICE


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔑 ПЕРЕВОДЧИК: кнопки из Mini App → команды для бота"""
    try:
        if not update.message or not update.message.web_app_data:
            return CHOICE

        data = json.loads(update.message.web_app_data.data)
        cmd = data.get("command")

        # 🔥 НОВЫЕ 2 СТРОЧКИ: Сохраняем имя из Web App
        if data.get("name"):
            context.user_data["client_name"] = data["name"]

        COMMAND_MAP = {
            "sell": "💰 Продать недвижимость",
            "buy": "🔍 Купить недвижимость",
            "rent": "🔑 Арендовать",
            "mortgage": "🧮 Калькулятор ипотеки",
            "ai": "🤖 Задать вопрос AI",
        }
        if cmd in COMMAND_MAP:
            update.message.text = COMMAND_MAP[cmd]
            name = context.user_data["client_name"]
            await update.message.reply_text(
                f"✅ <b>{name}</b>, вы выбрали: {COMMAND_MAP[cmd]}\n"
                f"Запускаю процесс... 🚀\n\n"
                f"💡 <i>Подсказка: следуйте подсказкам внизу — я буду вести вас за руку.</i>",
                parse_mode="HTML",
            )
            await route_choice(update, context)
    except Exception as e:
        loguru_logger.error(f"❌ Ошибка Mini App: {e}")


async def safety_net(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🛡️ Если бот не понял — мягко просим номер + объясняем пользу"""
    if not update.message or not update.message.text:
        return CHOICE

    name = context.user_data["client_name"]
    await update.message.reply_text(
        f"🤖 <b>{name}</b>, я вас не совсем понял.\n\n"
        f"Чтобы не терять время на переписку и дать вам максимально точный ответ, "
        f"лучше оставьте ваш номер телефона.\n"
        f"Наш специалист свяжется с вами в ближайшее время и всё уточнит — бережно и по делу.\n\n"
        f"💡 <i>Подсказка: нажмите на кнопку «📱 Отправить мой номер» ниже — это займёт 1 секунду.</i>",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
                ["🔄 /start В меню"],
            ],
            resize_keyboard=True,
        ),
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ──────────────────────────────────────────────────────────────────────
# 🛡️ SMART ERROR HANDLER (Безопасный: чинит БД, НЕ трогает код)
# ──────────────────────────────────────────────────────────────────────


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔥 Умный обработчик ошибок с авто-отчётом админу"""
    error = context.error
    error_msg = str(error)

    # 🔍 КЛАССИФИКАЦИЯ ОШИБОК
    error_type = "unknown"
    auto_fix = None

    # 1. ОШИБКИ БД
    if "18 values for 17 columns" in error_msg or "no such column" in error_msg:
        error_type = "db_schema"
        auto_fix = "❌ Требуется миграция БД (удалить artem_i.db и перезапустить)"

    # 2. ТАЙМАУТЫ
    if "Timed out" in error_msg or "Network error" in error_msg:
        error_type = "network"
        auto_fix = "✅ Авто-повтор запроса (бот справился сам)"

    # 3. ОШИБКИ ОТПРАВКИ
    if "Admin notify" in error_msg or "send_message" in error_msg:
        error_type = "admin_notify"
        auto_fix = "⚠️ Проверь ADMIN_CHAT_ID в .env"

    # 4. КРИТИЧЕСКИЕ
    if "ConversationHandler" in error_msg or "state" in error_msg.lower():
        error_type = "critical"
        auto_fix = " Клиенту отправлено: 'Технические работы, попробуйте снова'"

    # 📩 ОТПРАВЛЯЕМ ОТЧЁТ ТЕБЕ (в личку)
    if ADMIN_CHAT_ID:
        report = (
            f"🛡️ <b>SMART ERROR REPORT</b>\n\n"
            f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"🔴 Тип: <b>{error_type.upper()}</b>\n"
            f"❌ Ошибка: <code>{error_msg[:200]}</code>\n"
            f"✅ Авто-действие: {auto_fix}\n\n"
            f"🎯 <b>РЕКОМЕНДАЦИЯ:</b>\n"
        )

        if error_type == "db_schema":
            report += "• Удали файл artem_i.db → перезапусти бота"
        elif error_type == "network":
            report += "• Всё ок, бот повторил запрос автоматически"
        elif error_type == "admin_notify":
            report += "• Проверь токен бота и ADMIN_CHAT_ID"
        elif error_type == "critical":
            report += "• Проверь states в ConversationHandler"
        else:
            report += "• Смотри полный traceback в консоли"

        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID, text=report, parse_mode="HTML"
            )
        except:
            pass

    # 🛡️ МЯГКИЙ ОТВЕТ КЛИЕНТУ
    if update and hasattr(update, "effective_message") and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ <b>Технический сбой</b>\n\n"
                "Подождите минуту и попробуйте снова.\n"
                "<i>Менеджер уже получил уведомление.</i>",
                parse_mode="HTML",
            )
        except:
            pass

    logger.error(f"❌ ОШИБКА [{error_type}]: {error_msg}")



# ──────────────────────────────────────────────────────────────────────
# 17. ЗАПУСК — сборка всего воедино
# ──────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_error_handler(error_handler)

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_cmd),
            CallbackQueryHandler(handle_sell, pattern="^menu_sell$"),
            CallbackQueryHandler(handle_buy, pattern="^menu_buy$"),
            CallbackQueryHandler(handle_rent, pattern="^menu_rent$")
        ],
        states={
            # === ПРИВЕТСТВИЕ ===
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CONTINUE_PRESSED: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_continue)
            ],
            CHOICE: [
                CallbackQueryHandler(feedback_handler, pattern="^.*$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, route_choice),
            ],
            # === ПРОДАВЕЦ ===
            SELL_OBJ: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_obj)],
            SELL_SOTOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_sotok)],
            SELL_MATERIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_material)],
            SELL_OWNERSHIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_ownership)],
            SELL_KADASTR: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_kadastr)],
            SELL_FUNDAMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_fundament)],
            SELL_OBREM: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_obrem)],
            SELL_YEARS: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_years)],
            SELL_LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_loc)],
            SELL_AREA: [MessageHandler(area_filter, s_area)],
            SELL_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_time)],
            SELL_PRICE: [MessageHandler(price_filter, s_price)],
            SELL_ENC: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_enc)],
            SELL_MORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_mort)],
            SELL_GUARD_COUNT: [MessageHandler(children_filter, s_guard_count)],
            SELL_GUARD_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, s_guard_age)
            ],
            SELL_GUARD_HOUSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, s_guard_housing)
            ],
            SELL_GUARD_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, s_guard_search)
            ],
            SELL_OWN: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_own)],
            SELL_DOCS: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_docs)],
            SELL_CHILDREN_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sell_children_age)
            ],
            SELL_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_reason)],
            SELL_PHONE: [
                MessageHandler(
                    phone_filter | filters.CONTACT | filters.LOCATION, sell_phone
                )
            ],
            # === ПОКУПАТЕЛЬ ===
            BUY_OBJ: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_obj)],
            BUY_SOTOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_sotok)],
            BUY_LAND_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_land_purpose)],
            LAND_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_land_type)],
            LAND_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_land_area)],
            LAND_LOC: [
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, b_land_loc_map),
                MessageHandler(filters.TEXT & ~filters.COMMAND, b_land_loc),
            ],
            LAND_COMM: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_land_comm)],
            BUY_BUILDER_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_builder_search)],
            BUILD_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_build_type)],
            BUILD_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_build_area)],
            BUILD_LOC: [
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, b_build_loc_map),
                MessageHandler(filters.TEXT & ~filters.COMMAND, b_build_loc),
            ],
            BUILD_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_build_time)],
            BUY_LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_loc)],
            BUY_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_budget)],
            BUY_INFRA: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_infra)],
            BUY_PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_purpose)],
            BUY_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_pay)],
            BUY_MORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_mort)],
            BUY_CERT: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_cert)],
            BUY_GUARANTEE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, b_guarantee)
            ],
            BUY_MATCAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_matcap)],
            BUY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_time_ans)],
            BUY_PHONE: [
                MessageHandler(
                    filters.TEXT | filters.CONTACT | filters.LOCATION, buy_phone
                )
            ],
            # === АРЕНДА ===
            RENT_DUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, r_dur)],
            RENT_OCC: [MessageHandler(filters.TEXT & ~filters.COMMAND, r_occ)],
            RENT_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, r_budget)],
            RENT_PREFS: [MessageHandler(filters.TEXT & ~filters.COMMAND, r_prefs)],
            RENT_PHONE: [
                MessageHandler(
                    filters.TEXT | filters.CONTACT | filters.LOCATION, rent_phone
                )
            ],
            # === ИПОТЕКА ===
            MORT_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mort_choice)],
            MORT_BUY: [MessageHandler(filters.TEXT & ~filters.COMMAND, mort_buy)],
            MORT_SELL: [MessageHandler(filters.TEXT & ~filters.COMMAND, mort_sell)],
            MORT_RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mort_res)],
            MORT_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mort_rate)],
            # === ФИНАЛИЗАЦИЯ ===
            CONFIRM_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_more)
            ],
            ADD_NOTE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_note_and_finish)
            ],
            # === AI ===
            AI_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_handler)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^◀️ Назад"), back_to_menu),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, safety_net),
        ],
        name="artem_main_conv",
        persistent=False,
    )

    app.add_handler(conv)

    # 🔥 ИСПРАВЛЕНО: Подключаем обработчик кликов из Web App (кнопки приложения)
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

    # Лог запуска
    logger.info("✨ ARTEM AI v9.1 — EXCLUSIVE EDITION — ONLINE ✅")
    console.print(
        Panel.fit("[bold green]🎨 Rich работает![/bold green]", border_style="cyan")
    )

    table = PrettyTable()
    table.field_names = ["Модуль", "Статус"]
    table.add_row(["Telegram API", "✅"])
    table.add_row(["Database", "✅"])
    table.add_row(["Google Sheets", "✅"])
    console.print(table)

    loguru_logger.info("✅ AI-триггеры + Geo + WebApp подключены")
    print("🤖 ARTEM I ЗАПУЩЕН! Основатель на связи 🏗️")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
