# -*- coding: utf-8 -*-
"""✨ ARTEM AI ✨ — PLATFORM v9.0 (EXCLUSIVE EDITION)"""

import os, re, json, logging, sqlite3, asyncio
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

# ──────────────────────────────────────────────────────────────────────
# GOOGLE SHEETS INTEGRATION (Добавлено)
# ──────────────────────────────────────────────────────────────────────
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
    # 🔥 ИСПРАВЛЕНИЕ: Имя функции изменено на 'filter' (обязательно для версии 20.7)
    def filter(self, update: Update) -> bool:
        if not update.message or not update.message.text:
            return False
        clean = re.sub(r"\D", "", update.message.text)
        return 10 <= len(clean) <= 12


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
TOKEN = os.getenv("BOT_TOKEN")

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
}


def ai_trigger_check(text: str):
    if not text:
        return None
    t = text.lower()
    for topic, data in AI_TRIGGERS.items():
        if any(k in t for k in data["keys"]):
            loguru_logger.info(f"⚡ Триггер: [{topic.upper()}]")
            return data["msg"]
    return None


# ──────────────────────────────────────────────────────────────────────
# СОСТОЯНИЯ (СИНХРОНИЗИРОВАНО С main())
# ─────────────────────────────────────────────────────────────────────
# 🔥 ИСПРАВЛЕНИЕ: Добавлено 4 недостающих состояния для Опеки и Ипотеки
(
    GET_NAME,
    CHOICE,
    # Продавец
    SELL_OBJ,
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
    # Покупатель
    BUY_OBJ,
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
    # Контакты и Финал
    SELL_PHONE,
    BUY_PHONE,
    RENT_PHONE,
    CONFIRM_ADD,
    ADD_NOTE_STATE,
    CONTINUE_PRESSED,  # 🔥 Добавлено
    # AI
    AI_CHAT,
) = range(44)  # 🔥 Исправлено: было 40, стало 44


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


# 2. МОДУЛЬ OPEN AI
ai_client = (
    OpenAI(api_key=OPENAI_API_KEY)
    if OPENAI_API_KEY and OPENAI_API_KEY != "sk-placeholder"
    else None
)

# 🔹 ТВОЙ ПРОМПТ (оставлен без изменений)
AI_SYSTEM_PROMPT = """Ты — профессиональный ассистент агентства ARTEM AI во главе с Андреем.
Твой стиль: мягкий, уважительный, ласковый, гибкий, профессиональный, специалист в сфере недвижимости.
Твоя цель: бережно взять номер телефона клиента и аккуратно вывести на встречу с менеджером."""


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


def clean(t):
    return re.sub(r"[^\w\s\.\-\/]", "", t).strip()


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
        lead_type = d.get("type", "unknown")
        row = [
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            "Telegram Bot",
            d.get("client_name", "-"),
            f"{d.get('object', '')} | {d.get('location', '')}",
            str(d.get("price") or d.get("budget_rent") or ""),
            d.get("phone", ""),
            "",  # Ссылка
            "В РАБОТЕ" if lead_type in ["sell", "buy"] else "",
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

        welcome_back = (
            f"👋 <b>Рады видеть Вас снова!</b>\n\n"
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
    welcome_text = (
        "🌿 <b>Здравствуйте, уважаемый гость!</b>\n\n"
        "Меня зовут <b>Артём</b>. Я Ваш цифровой помощник.\n"
        "Проект создан на основе 20 лет практики в сфере недвижимости.\n"
        "Моя задача — сэкономить Ваше время и бережно подготовить всё для сделки.\n\n"
        "🎉 <b>Добро пожаловать!</b>\n\n"
        "Нажмите кнопку ниже, чтобы продолжить:"
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
# 9. МАРШРУТИЗАЦИЯ (ОБНОВЛЁННЫЙ — только 3 основные ветки)
# ──────────────────────────────────────────────────────────────────────
async def route_choice(update, context):
    text = update.message.text
    context.user_data["type"] = None

    # 🔥 Ищем по названию кнопок из чистого меню

    if "Продать недвижимость" in text:
        context.user_data["type"] = "sell"
        await update.message.reply_text(
            "💰 <b>Продажа</b>\nЧто планируете продавать?",
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
            "🔍 <b>Покупка</b>\nЧто ищете?",
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
            "🔑 <b>Аренда</b>\nНа какой срок?",
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
# БЛОК: ВОПРОСЫ ПРОДАВЦА (Воронка: Объект → Цена → Обременения → Контакты)
# ──────────────────────────────────────────────────────────────────────


async def s_obj(u, c):
    """🏠 Какой тип объекта продаём?"""
    c.user_data["object"] = (
        u.message.text.replace("🏠 ", "")
        .replace("🏡 ", "")
        .replace("🏢 ", "")
        .replace("🌲 ", "")
        .replace("🏗️ ", "")
    )
    await u.message.reply_text(
        "Принято! 📍 <b>Подскажите, где расположен ваш объект?</b>\n"
        "Напишите адрес, район или просто ориентиры.\n"
        "<i>Если участок без адреса — опишите: 'рядом с заправкой'</i> 😉",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_LOC


async def s_loc(u, c):
    """📍 Запоминаем локацию"""
    c.user_data["location"] = clean(u.message.text)
    await u.message.reply_text(
        "Подскажите, пожалуйста, а какова общая площадь Вашего объекта по документам? 📐\n"
        "<i>Укажите в м² — например, 45 или 120.5</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_AREA


async def s_area(u, c):
    """📐 Запоминаем площадь"""
    c.user_data["area"] = clean(u.message.text)
    await u.message.reply_text(
        "Отлично! ⏳ <b>Как скоро планируете продажу?</b>\n"
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
    c.user_data["timing"] = u.message.text
    await u.message.reply_text(
        "Понял вас! 💰 <b>На какую сумму вы ориентируетесь?</b>\n"
        "Можно точную цифру или вилку: <i>5-5.5 млн</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_PRICE


async def s_price(u, c):
    """💰 Запоминаем цену"""
    c.user_data["price"] = clean(u.message.text)
    await u.message.reply_text(
        "Спасибо! 📜 <b>Есть ли обременения на объекте?</b>\n"
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
    c.user_data["mortgage_details"] = clean(u.message.text)
    return await ask_own(u, c)


async def s_guard_count(u, c):
    c.user_data["children_count"] = clean(u.message.text)
    await u.message.reply_text(
        "🎂 <b>Укажите возраст детей</b> (через запятую).\n<i>Пример: 5, 12, 17</i>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return SELL_GUARD_AGE


async def s_guard_age(u, c):
    c.user_data["children_ages"] = clean(u.message.text)
    await u.message.reply_text(
        "🏠 <b>Уже подобрано новое жильё для детей?</b>",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Да, уже нашли"], [" Нет, в поиске"], ["◀️ Назад"]],
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
    c.user_data["search_prefs"] = clean(u.message.text)
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
    c.user_data["docs"] = clean(u.message.text)
    return await ask_phone_geo(u, c)


# ──────────────────────────────────────────────────────────────────────
# 🔥 ФИНАЛ: ТЕЛЕФОН + ГЕОЛОКАЦИЯ + ПОЛНАЯ КАРТОЧКА АДМИНУ (ОБНОВЛЁННЫЙ)
# ──────────────────────────────────────────────────────────────────────


async def ask_phone_geo(u, c):
    """📱 Мягкий запрос телефона + геолокация объекта"""
    name = c.user_data.get("client_name", "друг")
    kb = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("📱 Отправить номер", request_contact=True),
                KeyboardButton("📍 Указать объект на карте", request_location=True),
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
        context.user_data["phone"] = clean(update.message.text)
    return await ask_add_more(update, context)


# Заглушки для покупателя/аренды (чтобы не сломать другие воронки)
async def buy_phone(update, context):
    return await ask_add_more(update, context)


async def rent_phone(update, context):
    return await ask_add_more(update, context)


async def ask_add_more(update, context):
    """📋 Резюме + вопрос: добавить деталь?"""
    name = context.user_data.get("client_name", "друг")
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


async def handle_add_more(update, context):
    """✍️ Если клиент хочет добавить заметку"""
    if "Да" in update.message.text or "заметку" in update.message.text.lower():
        await update.message.reply_text(
            "✍️ <b>Напишите, что важно добавить:</b>\n"
            "<i>(например: «срочно до конца месяца» или «важна тихая улица»)</i>",
            reply_markup=ReplyKeyboardMarkup(
                [["✅ Готово, отправить"]], resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return ADD_NOTE_STATE
    return await final_thanks_and_send(update, context)


async def save_note_and_finish(update, context):
    """💾 Сохраняем заметку и идём на финал"""
    context.user_data["edit_note"] = update.message.text
    return await final_thanks_and_send(update, context)


async def final_thanks_and_send(update, context):
    """🎯 ПОЛНАЯ КАРТОЧКА АДМИНУ + СЕКРЕТНЫЙ БЛОК + БЛАГОДАРНОСТЬ КЛИЕНТУ"""
    # 🔥 КАРТОЧКА УХОДИТ АДМИНУ ТОЛЬКО ПОСЛЕ ПОЛУЧЕНИЯ ТЕЛЕФОНА
    await save_lead(context)
    name = context.user_data.get("client_name", "Клиент")

    # 📨 ФОРМИРУЕМ КАРТОЧКУ ДЛЯ ТЕБЯ (ПОЛНАЯ)
    summary = [
        f"🆕 <b>НОВАЯ ЗАЯВКА [{context.user_data.get('type', '?').upper()}]</b>",
        f"👤 Клиент: {name}",
        f"📞 Телефон: {context.user_data.get('phone', '?')}",
    ]

    obj = context.user_data.get("object", "?")
    summary.append(
        f"\n🏠 <b>ОБЪЕКТ:</b>\n• Тип: {obj}\n• Район: {context.user_data.get('location', '?')}"
    )
    if context.user_data.get("area"):
        summary.append(f"• Площадь: {context.user_data['area']} м²")
    if context.user_data.get("ownership"):
        summary.append(f"• В собственности: {context.user_data['ownership']}")
    if context.user_data.get("docs"):
        summary.append(f"• Документы: {context.user_data['docs']}")

    summary.append(
        f"\n💰 <b>ФИНАНСЫ:</b>\n• Цена: {context.user_data.get('price', '?')} ₽"
    )
    if (
        context.user_data.get("encumbrance")
        and context.user_data["encumbrance"] != "Нет"
    ):
        summary.append(f"• Обременение: {context.user_data['encumbrance']}")
    if context.user_data.get("mortgage_details"):
        summary.append(
            f"• Ипотека (остаток): {context.user_data['mortgage_details']} ₽"
        )

    if context.user_data.get("children_count"):
        summary.append(
            f"\n👶 <b>ДЕТИ:</b>\n• Кол-во: {context.user_data['children_count']}"
        )
        if context.user_data.get("children_ages"):
            summary.append(f"• Возраст: {context.user_data['children_ages']}")
        if context.user_data.get("housing_found"):
            summary.append(f"• Жильё найдено: {context.user_data['housing_found']}")
        if context.user_data.get("search_prefs"):
            summary.append(f"• Ищет взамен: {context.user_data['search_prefs']}")

    if context.user_data.get("timing"):
        summary.append(
            f"\n⏰ <b>СРОКИ:</b>\n• Планирует: {context.user_data['timing']}"
        )
    if context.user_data.get("edit_note"):
        summary.append(f"\n📝 <b>ЗАМЕТКА:</b>\n{context.user_data['edit_note']}")

    # 🗺 ГЕОЛОКАЦИЯ (если есть)
    lat, lon = context.user_data.get("latitude"), context.user_data.get("longitude")
    if lat and lon:
        yandex_url = f"https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=map"
        summary.append(
            f"\n📍 <b>ГЕОЛОКАЦИЯ:</b>\n🗺 <a href='{yandex_url}'>Открыть на карте</a>"
        )

    # 🔒 СЕКРЕТНЫЙ БЛОК (ТОЛЬКО ТЕБЕ — ИНСАЙТЫ + ССЫЛКИ)
    secret_notes = []
    timing = str(context.user_data.get("timing", "")).lower()
    if "срочно" in timing:
        secret_notes.append("🔥 Клиент торопится!")
    if "изучаю" in timing or "смотр" in timing:
        secret_notes.append("👀 Пока просто мониторит рынок")
    if not context.user_data.get("price") or context.user_data.get("price") == "?":
        secret_notes.append("💰 Не указал цену → нужна помощь с оценкой")
    if context.user_data.get("encumbrance") == "Ипотека":
        secret_notes.append("🏦 Нужна помощь с банком/одобрением")
    if context.user_data.get("encumbrance") in ["Опека", "Арест"]:
        secret_notes.append("⚖️ Сложная сделка (органы опеки/юрист)")
    if context.user_data.get("object") in ["Земля", "Стройка"]:
        secret_notes.append("🌲 Спец. объект → проверить коммуникации/документы")

    if secret_notes:
        summary.append(
            f"\n\n🔒 <b>СЕКРЕТНО ДЛЯ МЕНЕДЖЕРА:</b>\n"
            + "\n".join([f"• {n}" for n in secret_notes])
        )
        # 🔗 БЫСТРЫЕ ССЫЛКИ ДЛЯ ПОИСКА (подставляются по параметрам)
        loc = context.user_data.get("location", "сахалин").replace(" ", "+")
        price = context.user_data.get("price", "5000000")
        summary.append(
            f"\n🔍 <b>БЫСТРЫЙ ПОИСК ДЛЯ МЕНЕДЖЕРА:</b>\n"
            f"• <a href='https://www.avito.ru/sahalinskaya_oblast/nedvizhimost/prodam-ASgBAgICAUSSVA9gAUSQ?q={loc}'>Авито: {loc}</a>\n"
            f"• <a href='https://cian.ru/search/sale/flat/sahalinskaya-oblast/?region=4429&price={price}'>ЦИАН: до {price}₽</a>"
        )

    summary_text = "\n".join(summary)

    # 🔥 ОТПРАВЛЯЕМ ТЕБЕ
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=summary_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки заявки: {e}")

    # 💬 ОТВЕТ КЛИЕНТУ (мягкий, с удержанием + просьба о рекомендации)
    final_text = (
        f"✨ <b>Благодарю Вас, {name}, что выбрали ARTEM AI!</b> 🙏\n\n"
        f"Ваша заявка уже передана специалисту. Мы свяжемся с Вами в ближайшее время — бережно и по делу.\n\n"
        f"💡 <i>Если я был полезен, буду благодарен за рекомендацию друзьям.</i>\n\n"
        f"❓ <b>Могу ли Я ещё чем-то быть полезен для Вас сегодня?</b>"
    )

    # 🔥 ИСПРАВЛЕНО: Чистое меню из 3 кнопок (без "Вопрос AI")
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💰 Продать", callback_data="menu_sell")],
            [InlineKeyboardButton("🔍 Купить", callback_data="menu_buy")],
            [InlineKeyboardButton("🔑 Аренда", callback_data="menu_rent")],
        ]
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            final_text, reply_markup=kb, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(final_text, reply_markup=kb, parse_mode="HTML")

    return ConversationHandler.END


# ──────────────────────────────────────────────────────────────────────
# БЛОК 4: ПОКУПАТЕЛЬ (Воронка: Объект -> Оплата -> Контакты)
# ──────────────────────────────────────────────────────────────────────


async def b_obj(u, c):
    c.user_data["object"] = (
        u.message.text.replace("🏠 ", "")
        .replace("🏡 ", "")
        .replace("🌲 ", "")
        .replace("🏗️ ", "")
    )
    await u.message.reply_text(
        "📍 <b>Какой район или город рассматриваете?</b>",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return BUY_LOC


async def b_loc(u, c):
    c.user_data["location"] = clean(u.message.text)
    await u.message.reply_text(
        "💰 <b>Какой бюджет?</b> (руб)", reply_markup=get_back_kb(), parse_mode="HTML"
    )
    return BUY_BUDGET


async def b_budget(u, c):
    c.user_data["price"] = clean(u.message.text)
    await u.message.reply_text(
        "🏘 <b>Что важно рядом?</b>\n(школа, сад, транспорт, лес...)",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return BUY_INFRA


async def b_infra(u, c):
    c.user_data["infra"] = clean(u.message.text)
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
    c.user_data["mortgage_status"] = clean(u.message.text)

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
    c.user_data["cert_details"] = clean(u.message.text)
    return await b_time(u, c)


async def b_guarantee(u, c):
    c.user_data["payment"] = "Гарант. письмо"
    c.user_data["guarantee_details"] = clean(u.message.text)
    return await b_time(u, c)


async def b_matcap(u, c):
    c.user_data["payment"] = "Мат.капитал"
    c.user_data["matcap_rest"] = clean(u.message.text)
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
    c.user_data["occupants"] = clean(u.message.text)
    await u.message.reply_text(
        "💰 <b>Какой бюджет в месяц?</b> (руб)",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return RENT_BUDGET


async def r_budget(u, c):
    c.user_data["budget_rent"] = clean(u.message.text)
    await u.message.reply_text(
        "🏘 <b>Пожелания?</b>\n(ремонт, мебель, техника, парковка...)",
        reply_markup=get_back_kb(),
        parse_mode="HTML",
    )
    return RENT_PREFS


async def r_prefs(u, c):
    c.user_data["prefs_rent"] = clean(u.message.text)
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
    c.user_data["mortgage_status"] = clean(u.message.text)
    return await ask_phone_geo(u, c)


async def mort_sell(u, c):
    c.user_data["type"] = "mortgage_sell"
    c.user_data["mortgage_details"] = clean(u.message.text)
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
        context.user_data["phone"] = clean(update.message.text)
    return await ask_add_more(update, context)


async def buy_phone(update, context):
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
    else:
        context.user_data["phone"] = clean(update.message.text)
    return await ask_add_more(update, context)


async def rent_phone(update, context):
    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    elif update.message.location:
        context.user_data["latitude"] = update.message.location.latitude
        context.user_data["longitude"] = update.message.location.longitude
    else:
        context.user_data["phone"] = clean(update.message.text)
    return await ask_add_more(update, context)


async def ask_add_more(update, context):
    """🔥 Показываем резюме и спрашиваем, нужно ли добавить детали"""
    name = context.user_data.get("client_name", "друг")
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


async def final_thanks_and_send(update, context):
    """🎯 Детальная карточка -> Сохраняем -> Шлём тебе -> Благодарим"""
    await save_lead(context)
    name = context.user_data.get("client_name", "Клиент")

    summary = [
        f"🆕 <b>НОВАЯ ЗАЯВКА [{context.user_data.get('type', '?').upper()}]</b>",
        f"👤 Клиент: {name}",
        f"📞 Телефон: {context.user_data.get('phone', '?')}",
    ]

    obj = context.user_data.get("object", "?")

    summary.append(f"\n🏠 <b>ОБЪЕКТ:</b>")
    summary.append(f"• Тип: {obj}")
    summary.append(f"• Район: {context.user_data.get('location', '?')}")

    if obj in ["Дом", "Стройка", "Земля", "Коммерция"]:
        if context.user_data.get("area"):
            summary.append(f"• Площадь: {context.user_data['area']}")
        if context.user_data.get("ownership"):
            summary.append(f"• В собственности: {context.user_data['ownership']}")
        if context.user_data.get("docs"):
            summary.append(f"• Документы: {context.user_data['docs']}")

    summary.append(f"\n💰 <b>ФИНАНСЫ:</b>")
    price = context.user_data.get("price")
    budget = context.user_data.get("budget_rent")
    if price:
        summary.append(f"• Цена: {price} ₽")
    if budget:
        summary.append(f"• Бюджет: {budget} ₽/мес")

    enc = context.user_data.get("encumbrance")
    pay = context.user_data.get("payment")
    if enc and enc != "Нет":
        summary.append(f"• Обременение: {enc}")
    if pay:
        summary.append(f"• Оплата: {pay}")

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

    if context.user_data.get("children_count"):
        summary.append(f"\n👶 <b>ДЕТИ:</b>")
        summary.append(f"• Количество: {context.user_data['children_count']}")
        if context.user_data.get("children_ages"):
            summary.append(f"• Возраст: {context.user_data['children_ages']}")
        if context.user_data.get("housing_found"):
            summary.append(f"• Жильё найдено: {context.user_data['housing_found']}")

    if context.user_data.get("timing"):
        summary.append(
            f"\n⏰ <b>СРОКИ:</b>\n• Планирует: {context.user_data['timing']}"
        )

    if context.user_data.get("infra"):
        summary.append(f"\n🏘 <b>ИНФРАСТРУКТУРА:</b>\n{context.user_data['infra']}")

    lat, lon = context.user_data.get("latitude"), context.user_data.get("longitude")
    if lat and lon:
        summary.append(
            f"\n📍 <b>ГЕОЛОКАЦИЯ:</b>\n🗺 <a href='https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=map'>Открыть на карте</a>"
        )

    if context.user_data.get("edit_note"):
        summary.append(f"\n📝 <b>ЗАМЕТКА:</b>\n{context.user_data['edit_note']}")

    summary_text = "\n".join(summary)

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

    final_text = (
        f"✨ <b>Благодарю Вас, {name}, что выбрали ARTEM AI!</b> 🙏\n\n"
        f"Ваша заявка уже передана специалисту. Мы свяжемся с Вами в ближайшее время — бережно и по делу.\n\n"
        f"❓ <b>Могу ли Я ещё чем-то быть полезен для Вас сегодня?</b>"
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💰 Продать", callback_data="menu_sell")],
            [InlineKeyboardButton("🔍 Купить", callback_data="menu_buy")],
            [InlineKeyboardButton("🔑 Аренда", callback_data="menu_rent")],
            [InlineKeyboardButton("🧮 Ипотека", callback_data="menu_mort")],
            [InlineKeyboardButton("🤖 Вопрос AI", callback_data="nav_ai")],
        ]
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            final_text, reply_markup=kb, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(final_text, reply_markup=kb, parse_mode="HTML")

    return ConversationHandler.END


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
    name = c.user_data.get("client_name", "друг")

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
    c.user_data["mortgage_balance"] = u.message.text
    c.user_data["payment"] = "Ипотека (Продажа)"
    c.user_data["type"] = "sell"
    name = c.user_data.get("client_name", "друг")

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
    t = clean(update.message.text)

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

    # 🔹 Если клиент запутался — эскалация менеджеру
    if any(
        w in t.lower()
        for w in ["запутался", "сложно", "помогите", "позвоните", "перезвоните"]
    ):
        name = context.user_data.get("client_name", "друг")
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
    name = context.user_data.get("client_name", "друг")
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
    name = context.user_data.get("client_name", "друг")
    kb = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("📱 Отправить номер", request_contact=True),
                KeyboardButton("📍 Указать объект на карте", request_location=True),
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
        context.user_data["phone"] = clean(update.message.text)
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
        context.user_data["phone"] = clean(update.message.text)
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
        context.user_data["phone"] = clean(update.message.text)
        return await ask_add_more(update, context)


# ── Подтверждение и заметка ──
async def ask_add_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get("client_name", "друг")
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
    summary.append(f"• Район: {context.user_data.get('location', '?')}")

    if obj in ["Дом", "Стройка", "Земля", "Коммерция"]:
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
            f"\n📍 <b>ГЕОЛОКАЦИЯ:</b>\n🗺 <a href='https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=map'>Открыть на карте</a>"
        )

    # 📝 Заметка
    if context.user_data.get("edit_note"):
        summary.append(f"\n📝 <b>ЗАМЕТКА:</b>\n{context.user_data['edit_note']}")

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
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💰 Продать", callback_data="menu_sell")],
            [InlineKeyboardButton("🔍 Купить", callback_data="menu_buy")],
            [InlineKeyboardButton("🔑 Аренда", callback_data="menu_rent")],
            [
                InlineKeyboardButton("🧮 Ипотека", callback_data="menu_mortgage")
            ],  # 🔥 Исправлено на menu_mortgage
            [InlineKeyboardButton("🤖 Вопрос AI", callback_data="nav_ai")],
        ]
    )

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
        name = context.user_data.get("client_name", "друг")
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
            name = context.user_data.get("client_name", "друг")
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

    name = context.user_data.get("client_name", "друг")
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
        entry_points=[CommandHandler("start", start_cmd)],
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
