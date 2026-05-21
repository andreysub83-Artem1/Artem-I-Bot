# -*- coding: utf-8 -*-
"""✨ ARTEM AI ✨ — PLATFORM v9.0 (FULL & FINAL)"""
import os
import logging
import sqlite3
import re
import asyncio

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
# ──────────────────────────────────────────────────────────────────────
# 0. НОВЫЕ ИНСТРУМЕНТЫ: Rich, PrettyTable, Loguru
# ──────────────────────────────────────────────────────────────────────
from rich.console import Console
from rich.panel import Panel
from prettytable import PrettyTable
from loguru import logger as loguru_logger
import sys

# ──────────────────────────────────────────────────────────────────────
# 1. НАСТРОЙКИ
# ──────────────────────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID')) if os.getenv('ADMIN_CHAT_ID') else None
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
# ──────────────────────────────────────────────────────────────────
# 🤖 БЛОК 1: БЫСТРЫЕ ТРИГГЕРЫ (без OpenAI, мгновенный ответ)
# ──────────────────────────────────────────────────────────────────
AI_TRIGGERS = {
    "участок": {
        "keys": ["участок", "соток", "земля", "надел", "ижд", "земельный"],
        "msg": " Участок — фундамент будущего. Для ИЖС критичны коммуникации и статус земли. Какая площадь интересует? От 6 до 15 соток?"
    },
    "дом": {
        "keys": ["дом", "коттедж", "построить", "строительство", "каркас", "кирпич"],
        "msg": "🏠 Стройка — марафон. Главное — смета и этапы. Работаем с проверенными бригадами на Сахалине. Готовый проект или индивидуальный?"
    },
    "цена": {
        "keys": ["цена", "стоит", "бюджет", "дорого", "дешево", "рынок"],
        "msg": "📊 Рынок динамичный. Цена зависит от локации и коммуникаций. Назови примерный бюджет — отфильтрую реальные варианты, не «воздух»."
    },
    "ипотека": {
        "keys": ["ипотека", "кредит", "платеж", "банк", "ставка", "взнос"],
        "msg": " Ипотека на частный сектор доступна, но банки смотрят на документы. Готов рассчитать платеж? Нажми «🧮 Калькулятор» или напиши сумму."
    },
    "продать": {
        "keys": ["продать", "оценка", "выставить", "реклама", "спрос"],
        "msg": "📢 Чтобы продать быстро, создаем спрос: проф. съемка, 5+ площадок, прогрев аудитории. Опиши объект (район, площадь, состояние) — предложу стратегию."
    }
}

def ai_trigger_check(text: str):
    if not text: return None
    t = text.lower()
    for topic, data in AI_TRIGGERS.items():
        if any(k in t for k in data["keys"]):
            loguru_logger.info(f"⚡ Триггер сработал: [{topic.upper()}]")
            return data["msg"]
    return None
# ──────────────────────────────────────────────────────────────────────
# 0.1. Инициализация новых инструментов
# ──────────────────────────────────────────────────────────────────────
console = Console()  # Для красивого вывода в консоль

# Настройка Loguru (чтобы не дублировалось со стандартным logging)
loguru_logger.remove()
loguru_logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", level="INFO")

# ──────────────────────────────────────────────────────────────────────
# 2. СОСТОЯНИЯ (States)
# ──────────────────────────────────────────────────────────────────────
CHOICE, ASK_NAME, GET_NAME = 0, 1, 2
SELL_OBJ, SELL_LOC, SELL_AREA, SELL_TIME, SELL_PRICE, SELL_ENC, SELL_OWN, SELL_DOCS, SELL_PHONE, SELL_EDIT, SELL_FB = range(3, 14)
BUY_OBJ, BUY_PAY, BUY_TIME, BUY_MORTGAGE_DOWN, BUY_MATERNITY_REST, BUY_PHONE, BUY_EDIT, BUY_FB = range(14, 22)
RENT_DUR, RENT_OCC, RENT_PHONE, RENT_EDIT, RENT_FB = range(22, 27)
AI_CHAT = 27
MORTGAGE_PRICE, MORTGAGE_PAYMENT, MORTGAGE_RATE, MORTGAGE_RESULT = range(28, 32)

# ──────────────────────────────────────────────────────────────────────
# 3. БАЗА ДАННЫХ
# ──────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect('artem_i.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, object TEXT, location TEXT, area TEXT, timing TEXT, price TEXT,
        payment TEXT, encumbrance TEXT, ownership TEXT, docs TEXT, duration TEXT, occupants TEXT, phone TEXT, feedback TEXT, edit_note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON leads(user_id)")
    conn.commit()
    conn.close()
    logger.info("✨ База данных ARTEM AI готова")

# ──────────────────────────────────────────────────────────────────────
# 4. AI МОДУЛЬ
# ──────────────────────────────────────────────────────────────────────
ai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY and OPENAI_API_KEY != 'sk-placeholder' else None

AI_SYSTEM_PROMPT = """
Ты — профессиональный ассистент агентства ARTEM AI во главе с Андреем. 
Твой стиль: мягкий, уважительный, ласковый, гибкий, профессиональный, специалист в сфере недвижимости.
Твоя цель: бережно взять номер телефона клиента и акуратно вывести на встречу с менеджером.
Если не знаешь ответа — вежливо предложи оставить номер для связи с живым менеджером.
"""

async def ask_ai(text, context):
    if not ai_client:
        return "🧠 AI на обслуживании. Пожалуйста, оставьте номер для связи с менеджером."
    try:
        resp = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": f"Контекст: {context.user_data}\nВопрос: {text}"}
            ],
            max_tokens=400
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "🤖 Задумался... Попробуйте позже."

def clean(t):
    return re.sub(r'[^\w\s\.\-\/]', '', t).strip()
    # ──────────────────────────────────────────────────────────────────────
    # 5. УВЕДОМЛЕНИЯ И СОХРАНЕНИЕ
    # ──────────────────────────────────────────────────────────────────────
    async def notify_admin(context, summary, edit_note=None):
        if ADMIN_CHAT_ID:
            try:
                msg = f"🆕 <b>НОВАЯ ЗАЯВКА</b>\n\n{summary}"
                if edit_note:
                    msg += f"\n\n⚠️ <b>Правки:</b> {edit_note}"
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Admin notify error: {e}")

    async def save_lead(context, edit_note=None):
        d = context.user_data
        conn = get_db()
        conn.execute("INSERT INTO leads (user_id,type,object,location,area,timing,price,payment,encumbrance,ownership,docs,duration,occupants,phone,edit_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.get('user_id',0), d.get('type'), d.get('object'), d.get('location'), d.get('area'), d.get('timing'), d.get('price'), d.get('payment'), d.get('encumbrance'), d.get('ownership'), d.get('docs'), d.get('duration'), d.get('occupants'), d.get('phone'), edit_note))
        conn.commit()
        conn.close()
# ──────────────────────────────────────────────────────────────────────
# 5. НАВИГАЦИЯ
# ──────────────────────────────────────────────────────────────────────
def get_nav_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="nav_main")],
        [InlineKeyboardButton("📞 Позвонить", callback_data="nav_call")],
        [InlineKeyboardButton("🤖 Вопрос AI", callback_data="nav_ai")]
    ])

async def cancel(update, context):
    await update.message.reply_text("🙏 Понял вас! Мы всегда здесь. Нажмите /start.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def back_to_menu(update, context):
    await update.message.reply_text("↩️ Вернулись в главное меню.", reply_markup=ReplyKeyboardMarkup([
        ["💰 Продать недвижимость"], ["🔍 Купить недвижимость"],
        ["🔑 Арендовать"], ["🧮 Калькулятор ипотеки"],
        ["🤖 Задать вопрос AI"], ["🚀 Открыть красивое меню"]
    ], resize_keyboard=True))
    return CHOICE
# ──────────────────────────────────────────────────────────────────────
# 6. ПРИВЕТСТВИЕ (ГЛАВНЫЙ ЭКРАН)
# ──────────────────────────────────────────────────────────────────────
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем память
    context.user_data.clear()
    context.user_data['user_id'] = update.effective_user.id

    # Ссылка на Mini App
    app_url = "https://Artem-1-bazovyi.andreysub83.repl.co/index.html" 

    text = (

        "🌿 <b>Здравствуйте, уважаемый гость!</b>\n\n"
        "Меня зовут <b>Андрей</b>.\n"
        "Я основатель и руководитель проекта.\n"
        "Проект создан основываясь на 20-летнюю практику в сфере недвижимости.\n\n"
        "🎉 <b>Добро пожаловать!</b>\n\n"
        "👇   👇   👇"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Перейти", web_app=WebAppInfo(url=app_url))]
    ])

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode='HTML')
    return CHOICE
# ──────────────────────────────────────────────────────────────────────
# 7. МАРШРУТИЗАЦИЯ
# ──────────────────────────────────────────────────────────────────────
async def route_choice(update, context):
    text = update.message.text
    context.user_data['type'] = None
    if "Продать" in text:
        context.user_data['type']='sell'
        await update.message.reply_text("💰 <b>Продажа</b>\nЧто планируете продавать?", reply_markup=ReplyKeyboardMarkup([
            ["🏠 Квартира"],["🏡 Дом"],["🏢 Коммерция"],["🌲 Земля"],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True), parse_mode='HTML')
        return SELL_OBJ
    elif "Купить" in text:
        context.user_data['type']='buy'
        await update.message.reply_text("🔍 <b>Покупка</b>\nЧто ищете?", reply_markup=ReplyKeyboardMarkup([
            ["🏠 Квартира"],["🏡 Дом"],["🌲 Участок"],["🏗️ Стройка"],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True), parse_mode='HTML')
        return BUY_OBJ
    elif "Арендовать" in text:
        context.user_data['type']='rent'
        await update.message.reply_text("🔑 <b>Аренда</b>\nНа какой срок?", reply_markup=ReplyKeyboardMarkup([
            ["📅 От 1 года"],["📆 Долго (3+ года)"],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True), parse_mode='HTML')
        return RENT_DUR
    elif "Калькулятор" in text:
        await update.message.reply_text("🧮 <b>Ипотека</b>\nСтоимость (руб):", reply_markup=ReplyKeyboardMarkup([
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True), parse_mode='HTML')
        return MORTGAGE_PRICE
    elif "Задать вопрос" in text:
        await update.message.reply_text("🤖 <b>AI на связи</b>\nСпрашивайте!", reply_markup=ReplyKeyboardMarkup([
            ["❌ Отмена"]
        ], resize_keyboard=True), parse_mode='HTML')
        return AI_CHAT
    elif "Открыть красивое меню" in text:
        link = "https://andreysub83-artem-1-bazovyj.repl.co"
        await update.message.reply_text("🚀 Открываю меню...", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎮 ARTEM AI App", web_app=WebAppInfo(url=link))]
        ]))
        return CHOICE
    return CHOICE

# ──────────────────────────────────────────────────────────────────────
# 8. ПРОДАЖА
# ──────────────────────────────────────────────────────────────────────
async def s_obj(u,c):
    c.user_data['object']=u.message.text.replace("🏠 ","").replace("🏡 ","").replace("🏢 ","").replace("🌲 ","")
    await u.message.reply_text("📍 Где объект?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return SELL_LOC

async def s_loc(u,c):
    c.user_data['location']=clean(u.message.text)
    await u.message.reply_text("📐 Площадь?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return SELL_AREA

async def s_area(u,c):
    c.user_data['area']=clean(u.message.text)
    await u.message.reply_text("⏳ Сроки?", reply_markup=ReplyKeyboardMarkup([["⚡ Срочно"],["📅 Месяц"],["🔍 Изучаю"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return SELL_TIME

async def s_time(u,c):
    c.user_data['timing']=u.message.text
    await u.message.reply_text("💭 Цена?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return SELL_PRICE

async def s_price(u,c):
    c.user_data['price']=clean(u.message.text)
    await u.message.reply_text("📜 Обременения?", reply_markup=ReplyKeyboardMarkup([["✅ Нет"],["🏦 Ипотека"],["⚖️ Арест"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return SELL_ENC

async def s_enc(u,c):
    c.user_data['encumbrance']="Нет" if "Нет" in u.message.text else u.message.text
    await u.message.reply_text("📅 Срок владения?", reply_markup=ReplyKeyboardMarkup([["<3 лет"],[">3 лет"],["Наследство"],["ДДУ"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return SELL_OWN

async def s_own(u,c):
    c.user_data['ownership']=u.message.text
    obj=c.user_data.get('object','')
    if obj in ['Дом','Коммерция','Земля']:
        await u.message.reply_text("🏡 Документы в порядке?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
        return SELL_DOCS
    return await ask_phone(u,c)

async def s_docs(u,c):
    c.user_data['docs']=clean(u.message.text)
    return await ask_phone(u,c)

# ──────────────────────────────────────────────────────────────────────
# 9. ПОКУПКА
# ──────────────────────────────────────────────────────────────────────
async def b_obj(u,c):
    c.user_data['object']=u.message.text.replace("🏠 ","").replace("🏡 ","").replace("🌲 ","").replace("🏗️ ","")
    await u.message.reply_text("💳 Оплата?", reply_markup=ReplyKeyboardMarkup([["💵 Наличные"],["🏦 Ипотека"],["👶 Мат.капитал"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return BUY_PAY

# ──────────────────────────────────────────────────────────────────────
# 9. ПОКУПКА (ОПЛАТА И ВЕТКИ)
# ──────────────────────────────────────────────────────────────────────
async def b_pay(u,c):
    text = u.message.text

    # Ветка 1: Ипотека
    if "Ипотека" in text:
        await u.message.reply_text(
            "🏦 <b>Отлично, ипотека!</b>\n\n"
            "Скажите, пожалуйста, какую сумму вы планируете внести как <b>первоначальный взнос</b>? (в рублях)",
            reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True),
            parse_mode='HTML'
        )
        return BUY_MORTGAGE_DOWN

    # Ветка 2: МатКапитал
    elif "Мат.капитал" in text:
        await u.message.reply_text(
            "👶 <b>Понял, используем маткапитал.</b>\n\n"
            "А какую часть суммы планируете покрыть оставшимися средствами: <b>наличными</b> или <b>ипотекой</b>?",
            reply_markup=ReplyKeyboardMarkup([["💵 Наличные"],["🏦 Ипотека"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True),
            parse_mode='HTML'
        )
        return BUY_MATERNITY_REST

    # Ветка 3: Наличные (сразу идём к срокам)
    else:
        c.user_data['payment'] = "Наличные"
        await u.message.reply_text(
            "⏳ <b>Когда вы готовы выйти на сделку?</b>\n\n"
            "Реальные сроки помогают нам работать быстрее.",
            reply_markup=ReplyKeyboardMarkup([["🔥 Сейчас"],["📅 До полугода"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True),
            parse_mode='HTML'
        )
        return BUY_TIME

# ──────────────────────────────────────────────────────────────────────
# НОВАЯ ФУНКЦИЯ: Обработка взноса (для ипотеки)
# ──────────────────────────────────────────────────────────────────────
async def mortgage_down(u,c):
    c.user_data['mortgage_down'] = clean(u.message.text)
    c.user_data['payment'] = "Ипотека"
    await u.message.reply_text(
        "⏳ <b>Когда вы готовы выйти на сделку?</b>\n\n"
        "Реальные сроки помогают нам работать быстрее.",
        reply_markup=ReplyKeyboardMarkup([["🔥 Сейчас"],[" До полугода"],["️ Назад"],["❌ Отмена"]], resize_keyboard=True),
        parse_mode='HTML'
    )
    return BUY_TIME

# ──────────────────────────────────────────────────────────────────────
# НОВАЯ ФУНКЦИЯ: Обработка остатка (для маткапитала)
# ──────────────────────────────────────────────────────────────────────
async def maternity_rest(u,c):
    c.user_data['maternity_rest'] = u.message.text
    if "Ипотека" in u.message.text:
        c.user_data['payment'] = "Маткапитал + Ипотека"
    else:
        c.user_data['payment'] = "Маткапитал + Наличные"

    await u.message.reply_text(
        "⏳ <b>Когда вы готовы выйти на сделку?</b>\n\n"
        "Реальные сроки помогают нам работать быстрее.",
        reply_markup=ReplyKeyboardMarkup([["🔥 Сейчас"],["📅 До полугода"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True),
        parse_mode='HTML'
    )
    return BUY_TIME
async def b_time(u,c):
    c.user_data['timing']=u.message.text
    return await ask_phone(u,c)

# ──────────────────────────────────────────────────────────────────────
# 10. АРЕНДА
# ──────────────────────────────────────────────────────────────────────
async def r_dur(u,c):
    c.user_data['duration']=u.message.text
    await u.message.reply_text("👥 С кем проживать?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return RENT_OCC

async def r_occ(u,c):
    c.user_data['occupants']=clean(u.message.text)
    return await ask_phone(u,c)
# ──────────────────────────────────────────────────────────────────────
# 11. ФИНАЛ И ТЕЛЕФОН
# ──────────────────────────────────────────────────────────────────────
async def ask_phone(u,c):
    name = c.user_data.get('client_name', 'друг')
    await u.message.reply_text(
        f"📞 <b>{name}, спасибо за подробную информацию!</b>\n\n"
        f"Мы уже начали подбирать для вас варианты и хотим убедиться, что ничего не упустили.\n\n"
        f"📱 <b>Оставьте, пожалуйста, ваш номер телефона</b> (или нажмите кнопку ниже).\n\n"
        f"Это займёт одну секунду. Менеджер свяжется с вами лично, в ближайшее время.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить номер", request_contact=True)],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return SELL_PHONE

async def finish_flow(u,c,next_state,edit=False):
    edit_note = c.user_data.get('edit_note') if edit else None
    await save_lead(c, edit_note)
    summary = f"👤 {c.user_data.get('client_name','?')}\n📞 {c.user_data.get('phone','?')}\n📋 {c.user_data.get('type','?')}\n🏠 {c.user_data.get('object','?')}\n📍 {c.user_data.get('location','?')}\n💰 {c.user_data.get('price','?')}"
    await notify_admin(c, summary, edit_note)
    name = c.user_data.get('client_name', 'друг')
    card = f"✨ <b>Искренне благодарю вас, {name}!</b>\n\nВаши данные уже у нашего специалиста. Мы свяжемся с вами в самое ближайшее время.\n\n📇 <b>МОЯ ВИЗИТКА:</b>\n👤 Андрей |  ARTEM AI\n +7 (XXX) XXX-XX-XX\n─────────────\n💡 Могу Я ещё чем-то Вам помочь?\nЯ буду рад видеть вас снова в любое время! 🌿"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👍 Всё отлично!",callback_data="fb_plus"),InlineKeyboardButton("👎 Есть замечания",callback_data="fb_minus")],
        [InlineKeyboardButton("💰 Продать",callback_data="menu_sell"),InlineKeyboardButton("🔍 Купить",callback_data="menu_buy")],
        [InlineKeyboardButton("🔑 Аренда",callback_data="menu_rent"),InlineKeyboardButton("🧮 Ипотека",callback_data="menu_mort")]
    ])
    if u.callback_query:
        await u.callback_query.edit_message_text(card, reply_markup=kb, parse_mode='HTML')
    else:
        await u.message.reply_text(card, reply_markup=kb, parse_mode='HTML')
    return next_state

async def sell_phone(u,c):
    c.user_data['phone'] = u.message.contact.phone_number if u.message.contact else clean(u.message.text)
    return await finish_flow(u,c,SELL_FB)

async def buy_phone(u,c):
    c.user_data['phone'] = u.message.contact.phone_number if u.message.contact else clean(u.message.text)
    return await finish_flow(u,c,BUY_FB)

async def rent_phone(u,c):
    c.user_data['phone'] = u.message.contact.phone_number if u.message.contact else clean(u.message.text)
    return await finish_flow(u,c,RENT_FB)

# ──────────────────────────────────────────────────────────────────────
# 12. ИПОТЕКА
# ──────────────────────────────────────────────────────────────────────
#1. Старт ипотеки (Покупка)
async def mort_pay(u,c):
    await u.message.reply_text(
        "🏦 <b>Покупка с ипотекой</b>\n\n"
        "Напишите кратко по пунктам:\n"
        "1️⃣ Ипотека уже одобрена?\n"
        "2️⃣ Размер первоначального взноса?\n"
        "3️⃣ Сроки сделки?\n\n"
        "<i>Ответьте текстом, я запомню.</i>",
        reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True),
        parse_mode='HTML'
    )
    return MORTGAGE_RATE

# 2. Ответ на ипотеку -> Переход на телефон (Покупка)
async def mort_rate(u,c):
    c.user_data['mortgage_info'] = u.message.text
    c.user_data['payment'] = "Ипотека"
    c.user_data['type'] = "buy" # Помечаем, что это покупка

    # Просим телефон (копируем текст из ask_phone, но возвращаем BUY_PHONE)
    name = c.user_data.get('client_name', 'друг')
    await u.message.reply_text(
        f"📞 <b>{name}, спасибо!</b> Данные приняты.\n\n"
        "Оставьте номер телефона — менеджер свяжется в ближайшее время.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return BUY_PHONE # Важно! Чтобы сработал handler buy_phone

# 3. Старт ипотеки (Продажа / Обременение)
async def mort_price(u,c):
    await u.message.reply_text(
        "💰 <b>Продажа с ипотекой</b>\n\n"
        "Уточните: сколько осталось платить банку на сегодня?\n\n"
        "<i>Напишите сумму остатка.</i>",
        reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True),
        parse_mode='HTML'
    )
    return MORTGAGE_RESULT

# 4. Ответ по продаже -> Переход на телефон (Продажа)
async def mort_res(u,c):
    c.user_data['mortgage_balance'] = u.message.text
    c.user_data['payment'] = "Ипотека (Продажа)"
    c.user_data['type'] = "sell" # Помечаем, что это продажа

    # Просим телефон (копируем текст, возвращаем SELL_PHONE)
    name = c.user_data.get('client_name', 'друг')
    await u.message.reply_text(
        f"📞 <b>{name}, спасибо!</b> Данные приняты.\n\n"
        "Оставьте номер телефона — менеджер свяжется в ближайшее время.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return SELL_PHONE # Важно! Чтобы сработал handler sell_phone

# ──────────────────────────────────────────────────────────────────────
# 13. AI И МЕНЮ
# ──────────────────────────────────────────────────────────────────────
async def ai_handler(u,c):
    t = clean(u.message.text)
    phone_match = re.search(r'\+?7?\s*\(?\d{3}\)?\s*\d{3}[- ]?\d{2}[- ]?\d{2}', t)
    if phone_match:
        c.user_data['phone'] = re.sub(r'[^\d+]', '', phone_match.group())
        await u.message.reply_text(f"✅ Номер {c.user_data['phone']} записан! Менеджер свяжется с вами в ближайшее время. Спасибо за доверие! 🙏", reply_markup=get_nav_kb())
        await save_lead(c)
        await notify_admin(c, f"📞 Заявка из AI\n👤 {c.user_data.get('client_name')}\n📱 {c.user_data['phone']}")
        return ConversationHandler.END
    if any(w in t.lower() for w in ['запутался','сложно','помогите','позвоните','перезвоните']):
        await u.message.reply_text("🤝 Вижу, что вопросов много и ситуация требует внимания. Давайте наш менеджер перезвонит вам? Это бесплатно и ни к чему не обязывает.\n\nНажмите кнопку или просто напишите номер. Мы будем рады помочь! 🌿", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📱 Отправить номер", request_contact=True)],["◀️ Назад"]], resize_keyboard=True))
        return SELL_PHONE
    try:
        resp = await ask_ai(t,c)
        if not resp or "Задумался" in resp:
            return await show_menu_with_card(u,c)
        await u.message.reply_text(resp, reply_markup=get_nav_kb())
        return AI_CHAT
    except:
        return await show_menu_with_card(u,c)

async def show_menu_with_card(u,c):
    name = c.user_data.get('client_name', 'друг')
    txt = f"✨ <b>Понял вас, {name}!</b>\n\n💡 Могу ли я ещё чем-то помочь вам сегодня?\n\n─────────────────────\n📇 <b>МОЯ ВИЗИТКА:</b>\n─────────────────────\n👤 Андрей\n🏢 <b>ARTEM AI</b>\n📱 +7 (XXX) XXX-XX-XX\n📧 info@artemi.ru\n🌐 www.artemi.ru\n─────────────────────\n\n⭐ <b>Выберите раздел или просто напишите вопрос.</b>\nМы всегда на связи и будем рады видеть вас снова! 🌿"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продать недвижимость",callback_data="menu_sell")],
        [InlineKeyboardButton("🔍 Купить недвижимость",callback_data="menu_buy")],
        [InlineKeyboardButton("🧮 Калькулятор ипотеки",callback_data="menu_mortgage")],
        [InlineKeyboardButton("🔑 Арендовать",callback_data="menu_rent")]
    ])
    if hasattr(u,'callback_query') and u.callback_query:
        await u.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode='HTML')
    else:
        await u.message.reply_text(txt, reply_markup=kb, parse_mode='HTML')
    return CHOICE

async def feedback_handler(u,c):
    q=u.callback_query
    await q.answer()
    if q.data=="fb_plus":
        await q.edit_message_text("💙 Спасибо за тёплые слова! Это очень ценно для нас. Хорошего вам дня! Будем рады видеть вас снова! 🌿", reply_markup=get_nav_kb())
    elif q.data=="fb_minus":
        await q.edit_message_text("🙏 Спасибо за честность! Мы обязательно учтём ваши пожелания и станем лучше. Если есть конкретные идеи — напишите, я лично прочитаю. 🤝", reply_markup=get_nav_kb())
    elif q.data=="nav_main":
        await q.edit_message_text("↩️ Вернулись в главное меню. Чем ещё могу порадовать вас?", reply_markup=ReplyKeyboardMarkup([
            ["💰 Продать недвижимость"],["🔍 Купить недвижимость"],
            ["🔑 Арендовать"],["🧮 Калькулятор ипотеки"],
            ["🤖 Задать вопрос AI"],["🚀 Открыть красивое меню"]
        ], resize_keyboard=True))
        return CHOICE
    elif q.data=="nav_call":
        await q.edit_message_text("📞 Наш менеджер на связи: +7 (XXX) XXX-XX-XX\nЗвоните в любое время, мы всегда рады помочь! 🌿", reply_markup=get_nav_kb())
        return ConversationHandler.END
    elif q.data=="nav_ai":
        await q.edit_message_text("🤖 AI-консультант снова на связи. Задавайте вопрос, я внимательно слушаю:", reply_markup=ReplyKeyboardMarkup([["❌ В меню"]], resize_keyboard=True))
        return AI_CHAT
    elif q.data.startswith("menu_"):
        part=q.data.split("_")[1]
        c.user_data['type']=part
        if part=="sell":
            await q.edit_message_text("💰 Что планируете продавать?", reply_markup=ReplyKeyboardMarkup([["🏠 Квартира"],["🏡 Дом"],[" Коммерция"],[" Земля"]], resize_keyboard=True))
            return SELL_OBJ
        elif part=="buy":
            await q.edit_message_text("🔍 Что ищете?", reply_markup=ReplyKeyboardMarkup([["🏠 Квартира"],["🏡 Дом"],[" Участок"],["🏗️ Стройка"]], resize_keyboard=True))
            return BUY_OBJ
        elif part=="rent":
            await q.edit_message_text("🔑 На какой срок рассматриваете аренду?", reply_markup=ReplyKeyboardMarkup([["📅 От 1 года"],["📆 Долго (3+ года)"]], resize_keyboard=True))
            return RENT_DUR
        elif part=="mortgage":
            await q.edit_message_text("🧮 Введите стоимость недвижимости (в рублях):", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
            return MORTGAGE_PRICE
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────────────────
# 14. ЗАПУСК БОТА
# ──────────────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_cmd)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, route_choice)],
            SELL_OBJ: [MessageHandler(filters.TEXT, s_obj)],
            SELL_LOC: [MessageHandler(filters.TEXT, s_loc)],
            SELL_AREA: [MessageHandler(filters.TEXT, s_area)],
            SELL_TIME: [MessageHandler(filters.TEXT, s_time)],
            SELL_PRICE: [MessageHandler(filters.TEXT, s_price)],
            SELL_ENC: [MessageHandler(filters.TEXT, s_enc)],
            SELL_OWN: [MessageHandler(filters.TEXT, s_own)],
            SELL_DOCS: [MessageHandler(filters.TEXT, s_docs)],
            SELL_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT, sell_phone)],
            SELL_FB: [CallbackQueryHandler(feedback_handler)],
            BUY_OBJ: [MessageHandler(filters.TEXT, b_obj)],
            BUY_PAY: [MessageHandler(filters.TEXT, b_pay)],
            BUY_TIME: [MessageHandler(filters.TEXT, b_time)],
            BUY_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT, buy_phone)],
            BUY_FB: [CallbackQueryHandler(feedback_handler)],
            RENT_DUR: [MessageHandler(filters.TEXT, r_dur)],
            RENT_OCC: [MessageHandler(filters.TEXT, r_occ)],
            RENT_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT, rent_phone)],
            RENT_FB: [CallbackQueryHandler(feedback_handler)],
            AI_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_handler)],
            MORTGAGE_PRICE: [MessageHandler(filters.TEXT, mort_price)],
            MORTGAGE_PAYMENT: [MessageHandler(filters.TEXT, mort_pay)],
            MORTGAGE_RATE: [MessageHandler(filters.TEXT, mort_rate)],
            MORTGAGE_RESULT: [MessageHandler(filters.TEXT, mort_res)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^◀️ Назад"), back_to_menu),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            MessageHandler(filters.Regex("^◀️ Назад в меню$"), back_to_menu),
            MessageHandler(filters.Regex("^◀️ В главное меню$"), back_to_menu),
        ]
    )
    app.add_handler(conv)
    logger.info("✨ ARTEM AI v9.0 — FULL & FINAL — ONLINE ✅")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
 # ──────────────────────────────────────────────────────────────────────
 # 8. МАРШРУТИЗАЦИЯ
 # ──────────────────────────────────────────────────────────────────────
 async def route_choice(update, context):
    text = update.message.text
    context.user_data['type'] = None
    if "Продать" in text:
         context.user_data['type']='sell'
         await update.message.reply_text("💰 <b>Продажа</b>\nЧто планируете продавать?", reply_markup=ReplyKeyboardMarkup([
             ["🏠 Квартира"],["🏡 Дом"],["🏢 Коммерция"],["🌲 Земля"],
             ["◀️ Назад"],["❌ Отмена"]
         ], resize_keyboard=True), parse_mode='HTML')
         return SELL_OBJ
    elif "Купить" in text:
         context.user_data['type']='buy'
         await update.message.reply_text("🔍 <b>Покупка</b>\nЧто ищете?", reply_markup=ReplyKeyboardMarkup([
             ["🏠 Квартира"],["🏡 Дом"],["🌲 Участок"],["🏗️ Стройка"],
             ["◀️ Назад"],["❌ Отмена"]
         ], resize_keyboard=True), parse_mode='HTML')
         return BUY_OBJ
    elif "Арендовать" in text:
         context.user_data['type']='rent'
         await update.message.reply_text("🔑 <b>Аренда</b>\nНа какой срок?", reply_markup=ReplyKeyboardMarkup([
             ["📅 От 1 года"],["📆 Долго (3+ года)"],
             ["◀️ Назад"],["❌ Отмена"]
         ], resize_keyboard=True), parse_mode='HTML')
         return RENT_DUR
    elif "Калькулятор" in text:
         await update.message.reply_text("🧮 <b>Ипотека</b>\nСтоимость (руб):", reply_markup=ReplyKeyboardMarkup([
             ["◀️ Назад"],["❌ Отмена"]
         ], resize_keyboard=True), parse_mode='HTML')
         return MORTGAGE_PRICE
    elif "Задать вопрос" in text:
            await update.message.reply_text("🤖 <b>AI на связи</b>\nСпрашивайте!", parse_mode='HTML')
            return AI_CHAT
    elif "Открыть красивое меню" in text:
            link = "https://Artem-1-bazovyi.andreysub83.repl.co/index.html"
            await update.message.reply_text("🚀 Открываю меню...", 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌐 ARTEM AI App", web_app=WebAppInfo(url=link))]
                ]))
            return CHOICE

 # ──────────────────────────────────────────────────────────────────────
 # 9. ПРОДАЖА
 # ──────────────────────────────────────────────────────────────────────
 async def s_obj(u,c):
     c.user_data['object']=u.message.text.replace("🏠 ","").replace("🏡 ","").replace("🏢 ","").replace("🌲 ","")
     await u.message.reply_text("📍 Где объект?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return SELL_LOC

 async def s_loc(u,c):
     c.user_data['location']=clean(u.message.text)
     await u.message.reply_text("📐 Площадь?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return SELL_AREA

 async def s_area(u,c):
     c.user_data['area']=clean(u.message.text)
     await u.message.reply_text("⏳ Сроки?", reply_markup=ReplyKeyboardMarkup([["⚡ Срочно"],["📅 Месяц"],["🔍 Изучаю"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return SELL_TIME

 async def s_time(u,c):
     c.user_data['timing']=u.message.text
     await u.message.reply_text("💭 Цена?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return SELL_PRICE

 async def s_price(u,c):
     c.user_data['price']=clean(u.message.text)
     await u.message.reply_text("📜 Обременения?", reply_markup=ReplyKeyboardMarkup([["✅ Нет"],["🏦 Ипотека"],["⚖️ Арест"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return SELL_ENC

 async def s_enc(u,c):
     c.user_data['encumbrance']="Нет" if "Нет" in u.message.text else u.message.text
     await u.message.reply_text("📅 Срок владения?", reply_markup=ReplyKeyboardMarkup([["<3 лет"],[">3 лет"],["Наследство"],["ДДУ"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return SELL_OWN

 async def s_own(u,c):
     c.user_data['ownership']=u.message.text
     obj=c.user_data.get('object','')
     if obj in ['Дом','Коммерция','Земля']:
         await u.message.reply_text("🏡 Документы в порядке?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
         return SELL_DOCS
     return await ask_phone(u,c)

 async def s_docs(u,c):
     c.user_data['docs']=clean(u.message.text)
     return await ask_phone(u,c)

 # ──────────────────────────────────────────────────────────────────────
 # 10. ПОКУПКА
 # ──────────────────────────────────────────────────────────────────────
 async def b_obj(u,c):
     c.user_data['object']=u.message.text.replace("🏠 ","").replace("🏡 ","").replace("🌲 ","").replace("🏗️ ","")
     await u.message.reply_text("💳 Оплата?", reply_markup=ReplyKeyboardMarkup([["💵 Наличные"],["🏦 Ипотека"],["👶 Мат.капитал"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return BUY_PAY

 async def b_pay(u,c):
     c.user_data['payment']=u.message.text
     await u.message.reply_text("⏳ Готовность?", reply_markup=ReplyKeyboardMarkup([["🔥 Сейчас"],["📅 До полугода"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return BUY_TIME

 async def b_time(u,c):
     c.user_data['timing']=u.message.text
     return await ask_phone(u,c)

 # ──────────────────────────────────────────────────────────────────────
 # 11. АРЕНДА
 # ──────────────────────────────────────────────────────────────────────
 async def r_dur(u,c):
     c.user_data['duration']=u.message.text
     await u.message.reply_text("👥 С кем проживать?", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
     return RENT_OCC

 async def r_occ(u,c):
     c.user_data['occupants']=clean(u.message.text)
     return await ask_phone(u,c)

 # ──────────────────────────────────────────────────────────────────────
 # 12. ФИНАЛ И ТЕЛЕФОН
 # ──────────────────────────────────────────────────────────────────────
 async def ask_phone(u,c):
     name = c.user_data.get('client_name', 'друг')
     await u.message.reply_text(
         f"📞 <b>{name}, спасибо за подробную информацию!</b>\n\n"
         f"Мы уже начали подбирать для вас варианты и хотим убедиться, что ничего не упустили.\n\n"
         f"📱 <b>Оставьте, пожалуйста, ваш номер телефона</b> (или нажмите кнопку ниже).\n\n"
         f"Это займёт одну секунду. Менеджер свяжется с вами лично, бережно и в удобное время. Обещаю, не буду надоедать! 🙏",
         reply_markup=ReplyKeyboardMarkup([
             [KeyboardButton("📱 Отправить номер", request_contact=True)],
             ["◀️ Назад"],["❌ Отмена"]
         ], resize_keyboard=True),
         parse_mode='HTML'
     )
     return SELL_PHONE

 async def finish_flow(u,c,next_state,edit=False):
     edit_note = c.user_data.get('edit_note') if edit else None
     await save_lead(c, edit_note)
     summary = f"👤 {c.user_data.get('client_name','?')}\n📞 {c.user_data.get('phone','?')}\n📋 {c.user_data.get('type','?')}\n🏠 {c.user_data.get('object','?')}\n📍 {c.user_data.get('location','?')}\n💰 {c.user_data.get('price','?')}"
     await notify_admin(c, summary, edit_note)
     name = c.user_data.get('client_name', 'друг')
     card = f"✨ <b>Искренне благодарю вас, {name}!</b>\n\nВаши данные уже у нашего специалиста. Мы свяжемся с вами в самое ближайшее время.\n\n📇 <b>МОЯ ВИЗИТКА:</b>\n👤 Андрей |  ARTEM AI\n📱 +7 (XXX) XXX-XX-XX\n─────────────\n💡 Могу ещё чем-то помочь вам сегодня?\nМы будем рады видеть вас снова в любое время! 🌿"
     kb = InlineKeyboardMarkup([
         [InlineKeyboardButton("👍 Всё отлично!",callback_data="fb_plus"),InlineKeyboardButton("👎 Есть замечания",callback_data="fb_minus")],
         [InlineKeyboardButton("💰 Продать",callback_data="menu_sell"),InlineKeyboardButton("🔍 Купить",callback_data="menu_buy")],
         [InlineKeyboardButton("🔑 Аренда",callback_data="menu_rent"),InlineKeyboardButton("🧮 Ипотека",callback_data="menu_mort")]
     ])
     if u.callback_query:
         await u.callback_query.edit_message_text(card, reply_markup=kb, parse_mode='HTML')
     else:
         await u.message.reply_text(card, reply_markup=kb, parse_mode='HTML')
     return next_state

 async def sell_phone(u,c):
     c.user_data['phone'] = u.message.contact.phone_number if u.message.contact else clean(u.message.text)
     return await finish_flow(u,c,SELL_FB)

 async def buy_phone(u,c):
     c.user_data['phone'] = u.message.contact.phone_number if u.message.contact else clean(u.message.text)
     return await finish_flow(u,c,BUY_FB)

 async def rent_phone(u,c):
     c.user_data['phone'] = u.message.contact.phone_number if u.message.contact else clean(u.message.text)
     return await finish_flow(u,c,RENT_FB)

# ──────────────────────────────────────────────────────────────────────
# 12. ИПОТЕКА (Новая быстрая воронка)
# ──────────────────────────────────────────────────────────────────────

# 1. Старт ипотеки (Покупка)
async def mort_pay(u,c):
    await u.message.reply_text(
        "🏦 <b>Покупка с ипотекой</b>\n\n"
        "Напишите кратко по пунктам:\n"
        "1️⃣ Ипотека уже одобрена?\n"
        "2️⃣ Размер первоначального взноса?\n"
        "3️⃣ Сроки сделки?\n\n"
        "<i>Ответьте текстом, я запомню.</i>",
        reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True),
        parse_mode='HTML'
    )
    return MORTGAGE_RATE

# 2. Ответ на ипотеку -> Переход на телефон (Покупка)
async def mort_rate(u,c):
    c.user_data['mortgage_info'] = u.message.text
    c.user_data['payment'] = "Ипотека"
    c.user_data['type'] = "buy"

    name = c.user_data.get('client_name', 'друг')
    await u.message.reply_text(
        f"📞 <b>{name}, спасибо!</b> Данные приняты.\n\n"
        "Оставьте номер телефона — менеджер свяжется в ближайшее время.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return BUY_PHONE

# 3. Старт ипотеки (Продажа / Обременение)
async def mort_price(u,c):
    await u.message.reply_text(
        "💰 <b>Продажа с ипотекой</b>\n\n"
        "Уточните: сколько осталось платить банку на сегодня?\n\n"
        "<i>Напишите сумму остатка.</i>",
        reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True),
        parse_mode='HTML'
    )
    return MORTGAGE_RESULT

# 4. Ответ по продаже -> Переход на телефон (Продажа)
async def mort_res(u,c):
    c.user_data['mortgage_balance'] = u.message.text
    c.user_data['payment'] = "Ипотека (Продажа)"
    c.user_data['type'] = "sell"

    name = c.user_data.get('client_name', 'друг')
    await u.message.reply_text(
        f"📞 <b>{name}, спасибо!</b> Данные приняты.\n\n"
        "Оставьте номер телефона — менеджер свяжется в ближайшее время.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return SELL_PHONE
 # ──────────────────────────────────────────────────────────────────────
 # 14. AI И МЕНЮ
 # ──────────────────────────────────────────────────────────────────────
async def ai_handler(u,c):
     t = clean(u.message.text)
     phone_match = re.search(r'\+?7?\s*\(?\d{3}\)?\s*\d{3}[- ]?\d{2}[- ]?\d{2}', t)
     if phone_match:
         c.user_data['phone'] = re.sub(r'[^\d+]', '', phone_match.group())
         await u.message.reply_text(f"✅ Номер {c.user_data['phone']} записан! Менеджер свяжется с вами в ближайшее время. Спасибо за доверие! 🙏", reply_markup=get_nav_kb())
         await save_lead(c)
         await notify_admin(c, f"📞 Заявка из AI\n👤 {c.user_data.get('client_name')}\n📱 {c.user_data['phone']}")
         return ConversationHandler.END
     if any(w in t.lower() for w in ['запутался','сложно','помогите','позвоните','перезвоните']):
         await u.message.reply_text("🤝 Вижу, что вопросов много и ситуация требует внимания. Давайте наш менеджер перезвонит вам? Это бесплатно и ни к чему не обязывает.\n\nНажмите кнопку или просто напишите номер. Мы будем рады помочь! 🌿", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📱 Отправить номер", request_contact=True)],["◀️ Назад"]], resize_keyboard=True))
         return SELL_PHONE
     try:
         resp = await ask_ai(t,c)
         if not resp or "Задумался" in resp:
             return await show_menu_with_card(u,c)
         await u.message.reply_text(resp, reply_markup=get_nav_kb())
         return AI_CHAT
     except:
         return await show_menu_with_card(u,c)

async def show_menu_with_card(u,c):
     name = c.user_data.get('client_name', 'друг')
     txt = f"✨ <b>Понял вас, {name}!</b>\n\n💡 Могу ли я ещё чем-то помочь вам сегодня?\n\n─────────────────────\n📇 <b>МОЯ ВИЗИТКА:</b>\n─────────────────────\n👤 Андрей\n🏢 <b>ARTEM AI</b>\n📱 +7 (XXX) XXX-XX-XX\n📧 info@artemi.ru\n🌐 www.artemi.ru\n─────────────────────\n\n⭐ <b>Выберите раздел или просто напишите вопрос.</b>\nМы всегда на связи и будем рады видеть вас снова! 🌿"
     kb = InlineKeyboardMarkup([
         [InlineKeyboardButton("💰 Продать недвижимость",callback_data="menu_sell")],
         [InlineKeyboardButton("🔍 Купить недвижимость",callback_data="menu_buy")],
         [InlineKeyboardButton("🧮 Калькулятор ипотеки",callback_data="menu_mortgage")],
         [InlineKeyboardButton("🔑 Арендовать",callback_data="menu_rent")]
     ])
     if hasattr(u,'callback_query') and u.callback_query:
         await u.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode='HTML')
     else:
         await u.message.reply_text(txt, reply_markup=kb, parse_mode='HTML')
     return CHOICE
# ──────────────────────────────────────────────────────────────────────
# 🛡️ ФУНКЦИЯ ЗАЩИТЫ (Сетка от зависания)
# ──────────────────────────────────────────────────────────────────────
async def safety_net(u, c):
    await u.message.reply_text(
        "🤖 <b>Я вас не совсем понял.</b>\n\n"
        "Чтобы не терять время на переписку, лучше оставьте ваш номер телефона.\n"
        "Наш специалист свяжется с вами в ближайшее время и всё уточнит.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
            ["◀️ Назад"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return ConversationHandler.END
async def feedback_handler(u,c):
     q=u.callback_query
     await q.answer()
     if q.data=="fb_plus":
         await q.edit_message_text("💙 Спасибо за тёплые слова! Это очень ценно для нас. Хорошего вам дня! Будем рады видеть вас снова! 🌿", reply_markup=get_nav_kb())
     elif q.data=="fb_minus":
         await q.edit_message_text("🙏 Спасибо за честность! Мы обязательно учтём ваши пожелания и станем лучше. Если есть конкретные идеи — напишите, я лично прочитаю. 🤝", reply_markup=get_nav_kb())
     elif q.data=="nav_main":
         await q.edit_message_text("↩️ Вернулись в главное меню. Чем ещё могу порадовать вас?", reply_markup=ReplyKeyboardMarkup([
             ["💰 Продать недвижимость"],["🔍 Купить недвижимость"],
             ["🔑 Арендовать"],["🧮 Калькулятор ипотеки"],
             ["🤖 Задать вопрос AI"],["🚀 Открыть красивое меню"]
         ], resize_keyboard=True))
         return CHOICE
     elif q.data=="nav_call":
         await q.edit_message_text("📞 Наш менеджер на связи: +7 (962) 116-28-83\nЗвоните в любое время, мы всегда рады помочь! 🌿", reply_markup=get_nav_kb())
         return ConversationHandler.END
     elif q.data=="nav_ai":
         await q.edit_message_text("🤖 AI-консультант снова на связи. Задавайте вопрос, я внимательно слушаю:", reply_markup=ReplyKeyboardMarkup([["❌ В меню"]], resize_keyboard=True))
         return AI_CHAT
     elif q.data.startswith("menu_"):
         part=q.data.split("_")[1]
         c.user_data['type']=part
         if part=="sell":
             await q.edit_message_text("💰 Что планируете продавать?", reply_markup=ReplyKeyboardMarkup([["🏠 Квартира"],["🏡 Дом"],[" Коммерция"],[" Земля"]], resize_keyboard=True))
             return SELL_OBJ
         elif part=="buy":
             await q.edit_message_text("🔍 Что ищете?", reply_markup=ReplyKeyboardMarkup([["🏠 Квартира"],["🏡 Дом"],["🌲 Участок"],["🏗️ Стройка"]], resize_keyboard=True))
             return BUY_OBJ
         elif part=="rent":
             await q.edit_message_text("🔑 На какой срок рассматриваете аренду?", reply_markup=ReplyKeyboardMarkup([["📅 От 1 года"],["📆 Долго (3+ года)"]], resize_keyboard=True))
             return RENT_DUR
         elif part=="mortgage":
             await q.edit_message_text("🧮 Введите стоимость недвижимости (в рублях):", reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
             return MORTGAGE_PRICE
     return ConversationHandler.END

 # ──────────────────────────────────────────────────────────────────────
 # 15. ЗАПУСК БОТА
 # ──────────────────────────────────────────────────────────────────────

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_cmd)],
        states={

            CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, route_choice)],
            SELL_OBJ: [MessageHandler(filters.TEXT, s_obj)],
            SELL_LOC: [MessageHandler(filters.TEXT, s_loc)],
            SELL_AREA: [MessageHandler(filters.TEXT, s_area)],
            SELL_TIME: [MessageHandler(filters.TEXT, s_time)],
            SELL_PRICE: [MessageHandler(filters.TEXT, s_price)],
            SELL_ENC: [MessageHandler(filters.TEXT, s_enc)],
            SELL_OWN: [MessageHandler(filters.TEXT, s_own)],
            SELL_DOCS: [MessageHandler(filters.TEXT, s_docs)],
            SELL_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT, sell_phone)],
            SELL_FB: [CallbackQueryHandler(feedback_handler)],
            BUY_OBJ: [MessageHandler(filters.TEXT, b_obj)],
            BUY_PAY: [MessageHandler(filters.TEXT, b_pay)],
            BUY_MORTGAGE_DOWN: [MessageHandler(filters.TEXT, mortgage_down)],
            BUY_MATERNITY_REST: [MessageHandler(filters.TEXT, maternity_rest)],
            BUY_TIME: [MessageHandler(filters.TEXT, b_time)],
            BUY_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT, buy_phone)],
            BUY_FB: [CallbackQueryHandler(feedback_handler)],
            RENT_DUR: [MessageHandler(filters.TEXT, r_dur)],
            RENT_OCC: [MessageHandler(filters.TEXT, r_occ)],
            RENT_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT, rent_phone)],
            RENT_FB: [CallbackQueryHandler(feedback_handler)],
            AI_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_handler)],
            MORTGAGE_PRICE: [MessageHandler(filters.TEXT, mort_price)],
            MORTGAGE_PAYMENT: [MessageHandler(filters.TEXT, mort_pay)],
            MORTGAGE_RATE: [MessageHandler(filters.TEXT, mort_rate)],
            MORTGAGE_RESULT: [MessageHandler(filters.TEXT, mort_res)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^◀️ Назад"), back_to_menu),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            MessageHandler(filters.Regex("^◀️ Назад в меню$"), back_to_menu),
            MessageHandler(filters.Regex("^◀️ В главное меню$"), back_to_menu),
            MessageHandler(filters.TEXT & ~filters.COMMAND, safety_net),
        ]
    )
    app.add_handler(conv)

    # Стандартный лог
    logger.info("✨ ARTEM AI v9.0 — FULL & FINAL — ONLINE ✅")

    # ──────────────────────────────────────────────────────────────────
    # 🧪 ТЕСТ НОВЫХ БИБЛИОТЕК (Rich, PrettyTable, Loguru)
    # ──────────────────────────────────────────────────────────────────
    console.print(Panel.fit("[bold green]🎨 Rich работает![/bold green]", border_style="cyan"))

    test_table = PrettyTable()
    test_table.field_names = ["Модуль", "Статус"]
    test_table.add_row(["Telegram API", "✅"])
    test_table.add_row(["Database", "✅"])
    test_table.add_row(["New Tools", "✅"])
    console.print(test_table)
    # ──────────────────────────────────────────────────────────────────
    # 🤖 БЛОК 2: СЛУШАТЕЛЬ (Обрабатывает текст и применяет Триггеры)
    # ──────────────────────────────────────────────────────────────────
    async def trigger_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Берем текст сообщения
        txt = update.message.text.strip()

        # Если это команда (например /start) или кнопка "Назад" — пропускаем, 
        # чтобы не мешать работе основного меню
        if txt.startswith('/') or txt in ["Назад", "Отмена", "В главное меню", "🔙 Назад", " Отмена"]:
            return

        # Проверяем текст через наши триггеры (из Блока 1)
        resp = ai_trigger_check(txt)

        if resp:
            # Если триггер сработал — отвечаем мгновенно
            await update.message.reply_text(resp)
        else:
            # Если не поняли — вежливо просим уточнить или выбрать меню
            await update.message.reply_text(
                "🤔 Понял запрос. Для точного ответа выбери раздел или уточни задачу:\n"
                "💰 Продать |  Купить | 🔑 Аренда | 🧮 Ипотека"
            )

    # Подключаем слушатель (ставим его последним, чтобы не перебивать кнопки)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, trigger_handler))
    loguru_logger.info("✅ AI-триггеры подключены (Блок 2 активен)")

    # ──────────────────────────────────────────────────────────────────
    # 📱 ОБРАБОТЧИК MINI APP
    # ──────────────────────────────────────────────────────────────────
    async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            import json
            data = json.loads(update.message.web_app_data.data)
            cmd = data.get('command')
            if cmd:
                await update.message.reply_text(f"✅ Вы выбрали: <b>{cmd}</b>\nЗапускаю процесс...", parse_mode='HTML')
                update.message.text = cmd
                await route_choice(update, context)
        except Exception as e:
            loguru_logger.error(f"❌ Ошибка Mini App: {e}")

    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    loguru_logger.info("✅ Mini App обработчик подключён")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
# ─────────────────────────────────────────────────────────────
# 🌐 МИНИ-СЕРВЕР ДЛЯ MINI APP
# 
from flask import Flask, send_from_directory
import threading

web_app = Flask(__name__)

@web_app.route('/')
@web_app.route('/index.html')
def serve_app():
    return send_from_directory('.', 'index.html')

def start_web():
    web_app.run(host='0.0.0.0', port=5000, debug=False)

# 
# ГЛАВНЫЙ ЗАПУСК
# 
if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=start_web, daemon=True).start()
    print("🌐 Сайт запущен на порту 5000!")
    # Запускаем бота
    main()
