# -*- coding: utf-8 -*-
"""✨ ARTEM AI ✨ — PLATFORM v9.0 (EXCLUSIVE EDITION)"""
import os, re, json, logging, sqlite3, asyncio
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, WebAppInfo)
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler,
                          ConversationHandler, filters, ContextTypes)
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
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()
loguru_logger.remove()
loguru_logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", level="INFO")

# ──────────────────────────────────────────────────────────────────────
# 2. AI ТРИГГЕРЫ (мгновенные ответы вне воронки)
# ──────────────────────────────────────────────────────────────────────
AI_TRIGGERS = {
    "участок": {"keys": ["участок","соток","земля","надел","ижд","земельный"],
                "msg": "🌿 Участок — фундамент будущего. Для ИЖС критичны коммуникации и статус земли. Какая площадь интересует? От 6 до 15 соток?"},
    "дом": {"keys": ["дом","коттедж","построить","строительство","каркас","кирпич"],
            "msg": "🏠 Стройка — марафон. Главное — смета и этапы. Работаем с проверенными бригадами на Сахалине. Готовый проект или индивидуальный?"},
    "цена": {"keys": ["цена","стоит","бюджет","дорого","дешево","рынок"],
             "msg": "📊 Рынок динамичный. Цена зависит от локации и коммуникаций. Назови примерный бюджет — отфильтрую реальные варианты."},
    "ипотека": {"keys": ["ипотека","кредит","платеж","банк","ставка","взнос"],
                "msg": "🏦 Ипотека на частный сектор доступна. Готов рассчитать платеж? Нажми «🧮 Калькулятор» или напиши сумму."},
    "продать": {"keys": ["продать","оценка","выставить","реклама","спрос"],
                "msg": "📢 Чтобы продать быстро, создаем спрос: проф. съемка, 5+ площадок. Опиши объект — предложу стратегию."}
}

def ai_trigger_check(text: str):
    if not text: return None
    t = text.lower()
    for topic, data in AI_TRIGGERS.items():
        if any(k in t for k in data["keys"]):
            loguru_logger.info(f"⚡ Триггер: [{topic.upper()}]")
            return data["msg"]
    return None

# ──────────────────────────────────────────────────────────────────────
# 3. СОСТОЯНИЯ (35 шагов)
# ──────────────────────────────────────────────────────────────────────
(ASK_NAME, GET_NAME, CHOICE,
 SELL_OBJ, SELL_LOC, SELL_AREA, SELL_TIME, SELL_PRICE, SELL_ENC, SELL_OWN, SELL_DOCS, SELL_PHONE, SELL_FB,
 BUY_OBJ, BUY_LOC, BUY_BUDGET, BUY_INFRA, BUY_PURPOSE, BUY_PAY, BUY_MORT_DOWN, BUY_MAT_REST, BUY_TIME, BUY_PHONE, BUY_FB,
 RENT_DUR, RENT_OCC, RENT_PHONE, RENT_FB,
 AI_CHAT, MORT_PRICE, MORT_PAY, MORT_RATE, MORT_RESULT) = range(35)

# ──────────────────────────────────────────────────────────────────────
# 4. БАЗА ДАННЫХ
# ──────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect('artem_i.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, object TEXT, location TEXT,
        area TEXT, timing TEXT, price TEXT, payment TEXT, encumbrance TEXT, ownership TEXT,
        docs TEXT, duration TEXT, occupants TEXT, phone TEXT, latitude REAL, longitude REAL,
        feedback TEXT, edit_note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON leads(user_id)")
    conn.commit()
    conn.close()
    logger.info("✨ База данных ARTEM AI готова")
# ──────────────────────────────────────────────────────────────────────
# 5. AI МОДУЛЬ
# ──────────────────────────────────────────────────────────────────────
ai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY and OPENAI_API_KEY != 'sk-placeholder' else None
AI_SYSTEM_PROMPT = """Ты — профессиональный ассистент агентства ARTEM AI во главе с Андреем.
Твой стиль: мягкий, уважительный, ласковый, гибкий, профессиональный, специалист в сфере недвижимости.
Твоя цель: бережно взять номер телефона клиента и аккуратно вывести на встречу с менеджером."""

async def ask_ai(text, context):
    if not ai_client: return "🧠 AI на обслуживании. Оставьте номер для связи с менеджером."
    try:
        resp = ai_client.chat.completions.create(model="gpt-4o-mini", messages=[
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": f"Контекст: {context.user_data}\nВопрос: {text}"}], max_tokens=400)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "🤖 Задумался... Попробуйте позже."

def clean(t): return re.sub(r'[^\w\s\.\-\/]', '', t).strip()

# ──────────────────────────────────────────────────────────────────────
# 6. УВЕДОМЛЕНИЯ + СОХРАНЕНИЕ + ЯНДЕКС
# ──────────────────────────────────────────────────────────────────────
async def notify_admin(context, summary, edit_note=None, yandex_url=None):
    if ADMIN_CHAT_ID:
        try:
            msg = f"🆕 <b>НОВАЯ ЗАЯВКА</b>\n\n{summary}"
            if yandex_url: msg += f"\n\n🗺 <a href='{yandex_url}'>Открыть в Яндекс.Картах</a>"
            if edit_note: msg += f"\n\n⚠️ <b>Правки:</b> {edit_note}"
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg, parse_mode='HTML', disable_web_page_preview=True)
        except Exception as e: logger.error(f"Admin notify error: {e}")

async def save_lead(context, edit_note=None):
    d = context.user_data
    conn = get_db()
    conn.execute("INSERT INTO leads (user_id,type,object,location,area,timing,price,payment,encumbrance,ownership,docs,duration,occupants,phone,latitude,longitude,edit_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (d.get('user_id',0), d.get('type'), d.get('object'), d.get('location'), d.get('area'), d.get('timing'),
         d.get('price'), d.get('payment'), d.get('encumbrance'), d.get('ownership'), d.get('docs'),
         d.get('duration'), d.get('occupants'), d.get('phone'), d.get('latitude'), d.get('longitude'), edit_note))
    conn.commit()
    conn.close()

def make_yandex_url(lat, lon):
    if lat and lon: return f"https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=map"
    return None

# ──────────────────────────────────────────────────────────────────────
# 7. НАВИГАЦИЯ
# ──────────────────────────────────────────────────────────────────────
def get_nav_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 меню", callback_data="nav_main")],
        [InlineKeyboardButton("📞 Позвонить", callback_data="nav_call")],
        [InlineKeyboardButton("🤖 Вопрос AI", callback_data="nav_ai")]])

def get_back_kb():
    return ReplyKeyboardMarkup([["◀️ Назад"], ["❌ Отмена"]], resize_keyboard=True)

async def cancel(update, context):
    await update.message.reply_text("🙏 Понял вас! Мы всегда здесь. Нажмите /start.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def back_to_menu(update, context):
    await update.message.reply_text("↩️ Вернулись в главное меню.", reply_markup=ReplyKeyboardMarkup([
        ["💰 Продать недвижимость"], ["🔍 Купить недвижимость"], ["🔑 Арендовать"],
        ["🧮 Калькулятор ипотеки"], ["🤖 Задать вопрос AI"], ["🚀 меню"]], resize_keyboard=True))
    return CHOICE
    # ──────────────────────────────────────────────────────────────────────
# 8. ПРИВЕТСТВИЕ + СБОР ИМЕНИ
# ──────────────────────────────────────────────────────────────────────
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['user_id'] = update.effective_user.id
    await update.message.reply_text("✨ ARTEM AI\n\nПрежде чем начнём, позвольте узнать — как к вам обращаться?", reply_markup=ReplyKeyboardRemove())
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✨ Как к вам обращаться?", reply_markup=ReplyKeyboardRemove())
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['client_name'] = update.message.text.strip()
    name = context.user_data['client_name']
    text = (f"✨ Приятно познакомиться, {name}!\n\n"
            f"Меня зовут <b>Андрей</b>. Я основатель ARTEM AI.\n"
            f"Проект создан на основе 20-летней практики в недвижимости.\n\n"
            f"🎉 <b>Добро пожаловать!</b>\n👇 Выберите направление:")
    kb = [["💰 Продать недвижимость"], ["🔍 Купить недвижимость"], ["🔑 Арендовать"], ["🧮 Калькулятор ипотеки"], ["🤖 Задать вопрос AI"], ["🚀 меню"]]
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='HTML')
    return CHOICE

# ──────────────────────────────────────────────────────────────────────
# 9. МАРШРУТИЗАЦИЯ
# ──────────────────────────────────────────────────────────────────────
async def route_choice(update, context):
    text = update.message.text
    context.user_data['type'] = None
    if "Продать" in text:
        context.user_data['type']='sell'
        await update.message.reply_text("💰 <b>Продажа</b>\nЧто планируете продавать?", reply_markup=ReplyKeyboardMarkup([
            ["🏠 Квартира"],["🏡 Дом"],["🏢 Коммерция"],["🌲 Земля"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True), parse_mode='HTML')
        return SELL_OBJ
    elif "Купить" in text:
        context.user_data['type']='buy'
        await update.message.reply_text("🔍 <b>Покупка</b>\nЧто ищете?", reply_markup=ReplyKeyboardMarkup([
            ["🏠 Квартира"],["🏡 Дом"],["🌲 Участок"],["🏗️ Стройка"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True), parse_mode='HTML')
        return BUY_OBJ
    elif "Арендовать" in text:
        context.user_data['type']='rent'
        await update.message.reply_text("🔑 <b>Аренда</b>\nНа какой срок?", reply_markup=ReplyKeyboardMarkup([
            ["📅 От 1 года"],["📆 Долго (3+ года)"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True), parse_mode='HTML')
        return RENT_DUR
    elif "Калькулятор" in text:
        await update.message.reply_text("🧮 <b>Ипотека</b>\nСтоимость (руб):", reply_markup=get_back_kb(), parse_mode='HTML')
        return MORT_PRICE
    elif "Задать вопрос" in text:
        await update.message.reply_text("🤖 <b>AI на связи</b>\nСпрашивайте!", reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True), parse_mode='HTML')
        return AI_CHAT
    elif "меню" in text:
        link = os.getenv('WEBAPP_URL', 'https://artem-ai.onrender.com')
        await update.message.reply_text("🚀 Открываю меню...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 ARTEM AI App", web_app=WebAppInfo(url=link))]]))
        return CHOICE
    return CHOICE

# ──────────────────────────────────────────────────────────────────────
# 10. ПРОДАВЕЦ
# ──────────────────────────────────────────────────────────────────────
async def s_obj(u,c): c.user_data['object']=u.message.text.replace("🏠 ","").replace("🏡 ","").replace("🏢 ","").replace("🌲 ",""); await u.message.reply_text("📍 Где находится объект? (район или адрес)", reply_markup=get_back_kb()); return SELL_LOC
async def s_loc(u,c): c.user_data['location']=clean(u.message.text); await u.message.reply_text("📐 Какая общая площадь?", reply_markup=get_back_kb()); return SELL_AREA
async def s_area(u,c): c.user_data['area']=clean(u.message.text); await u.message.reply_text("⏳ Как скоро планируете продажу?", reply_markup=ReplyKeyboardMarkup([["⚡ Срочно"],["📅 В этом месяце"],["📆 В течение квартала"],["🔍 Пока изучаю рынок"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)); return SELL_TIME
async def s_time(u,c): c.user_data['timing']=u.message.text; await u.message.reply_text("💭 На какую сумму рассчитываете при продаже?", reply_markup=get_back_kb()); return SELL_PRICE
async def s_price(u,c): c.user_data['price']=clean(u.message.text); await u.message.reply_text("📜 Есть ли обременения?", reply_markup=ReplyKeyboardMarkup([["✅ Нет"],["🏦 Ипотека"],["⚖️ Арест/Опека"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)); return SELL_ENC
async def s_enc(u,c): c.user_data['encumbrance']="Нет" if "Нет" in u.message.text else u.message.text; await u.message.reply_text("📅 Как давно объект в собственности?", reply_markup=ReplyKeyboardMarkup([["< 3 лет"],["> 3 лет"],["Наследство"],["ДДУ"],["ДКП"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)); return SELL_OWN
async def s_own(u,c): 
    c.user_data['ownership']=u.message.text
    obj=c.user_data.get('object','')
    if obj in ['Дом','Коммерция','Земля']: 
        await u.message.reply_text("🏡 Документы в порядке?", reply_markup=get_back_kb()); return SELL_DOCS
    return await ask_phone_geo(u,c)
async def s_docs(u,c): c.user_data['docs']=clean(u.message.text); return await ask_phone_geo(u,c)

# ──────────────────────────────────────────────────────────────────────
# 11. ПОКУПАТЕЛЬ (полная воронка: Район → Бюджет → Инфра → Цель → Оплата → Срок)
# ──────────────────────────────────────────────────────────────────────
async def b_obj(u,c): c.user_data['object']=u.message.text.replace("🏠 ","").replace("🏡 ","").replace("🌲 ","").replace("🏗️ ",""); await u.message.reply_text("📍 Какой район или населённый пункт рассматриваете?", reply_markup=get_back_kb()); return BUY_LOC
async def b_location(u,c): c.user_data['location']=clean(u.message.text); await u.message.reply_text("💰 Какой бюджет рассматриваете?", reply_markup=get_back_kb()); return BUY_BUDGET
async def b_budget(u,c): c.user_data['price']=clean(u.message.text); await u.message.reply_text("🏘 Что важно рядом в приоритете? (школа, сад, магазины, транспорт, лес...)", reply_markup=get_back_kb()); return BUY_INFRA
async def b_infra(u,c): c.user_data['infra']=clean(u.message.text); await u.message.reply_text("🤫 Если не секрет, для кого подыскиваете объект? (для семьи, инвестиция, родители...)", reply_markup=get_back_kb()); return BUY_PURPOSE
async def b_purpose(u,c):
    txt = u.message.text.strip().lower()
    if "секрет" in txt or "не скажу" in txt:
        c.user_data['purpose'] = "Не указано (клиент предпочёл не раскрывать)"
        await u.message.reply_text("✅ Понял! Агент подберёт варианты без лишних вопросов. Главное — чтобы вам было комфортно! 💫\n\n💳 Какой вид оплаты планируете?", reply_markup=ReplyKeyboardMarkup([["💵 Наличные"],["🏦 Ипотека"],["👶 Мат.капитал"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    else:
        c.user_data['purpose'] = u.message.text
        await u.message.reply_text("💳 Какой вид оплаты планируете?", reply_markup=ReplyKeyboardMarkup([["💵 Наличные"],["🏦 Ипотека"],["👶 Мат.капитал"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True))
    return BUY_PAY
async def b_pay(u,c):
    text = u.message.text
    if "Ипотека" in text:
        c.user_data['payment'] = "Ипотека"
        await u.message.reply_text("🏦 Размер первоначального взноса?", reply_markup=get_back_kb()); return BUY_MORT_DOWN
    elif "Мат.капитал" in text:
        c.user_data['payment'] = "Маткапитал"
        await u.message.reply_text("👶 Остаток покрываете наличными или ипотекой?", reply_markup=ReplyKeyboardMarkup([["💵 Наличные"],["🏦 Ипотека"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)); return BUY_MAT_REST
    else:
        c.user_data['payment'] = "Наличные"
        await u.message.reply_text("⏳ Когда готовы к сделке?", reply_markup=ReplyKeyboardMarkup([["🔥 В этом месяце"],["📅 В течение квартала"],["🔍 Пока смотрю"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)); return BUY_TIME
async def mortgage_down(u,c): c.user_data['mort_down']=clean(u.message.text); await u.message.reply_text("⏳ Когда готовы к сделке?", reply_markup=ReplyKeyboardMarkup([["🔥 В этом месяце"],["📅 В течение квартала"],["🔍 Пока смотрю"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)); return BUY_TIME
async def maternity_rest(u,c): c.user_data['mat_rest']=u.message.text; c.user_data['payment']+=" + Ипотека" if "Ипотека" in u.message.text else " + Наличные"; await u.message.reply_text("⏳ Когда готовы к сделке?", reply_markup=ReplyKeyboardMarkup([["🔥 В этом месяце"],["📅 В течение квартала"],["🔍 Пока смотрю"],["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)); return BUY_TIME
async def b_time(u,c): c.user_data['timing']=u.message.text; return await ask_phone_geo(u,c)

# ──────────────────────────────────────────────────────────────────────
# 12. АРЕНДА + ФИНАЛ СБОРА
# ──────────────────────────────────────────────────────────────────────
async def r_dur(u,c): c.user_data['duration']=u.message.text; await u.message.reply_text("👥 С кем планируете проживать?", reply_markup=get_back_kb()); return RENT_OCC
async def r_occ(u,c): c.user_data['occupants']=clean(u.message.text); return await ask_phone_geo(u,c)
async def ask_phone_geo(u,c):
    name = c.user_data.get('client_name', 'друг')
    kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Отправить номер", request_contact=True), KeyboardButton("📍 Отправить геолокацию", request_location=True)], ["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)
    await u.message.reply_text(f"📞 {name}, благодарю за информацию! Оставьте, пожалуйста, номер для связи и, если удобно, отправьте геолокацию объекта.", reply_markup=kb)
    return SELL_PHONE
    # ──────────────────────────────────────────────────────────────────────
# 13. ФИНАЛИЗАЦИЯ (СОХРАНЕНИЕ + КАРТОЧКА МЕНЕДЖЕРУ + ОТВЕТ КЛИЕНТУ)
# ──────────────────────────────────────────────────────────────────────
async def finish_flow(u,c,next_state,edit=False):
    edit_note = c.user_data.get('edit_note') if edit else None
    await save_lead(c, edit_note)
    
    lat, lon = c.user_data.get('latitude'), c.user_data.get('longitude')
    yandex_url = make_yandex_url(lat, lon)
    
    # Формируем премиум-карточку с душой
    summary = (
        f"👤 Клиент: {c.user_data.get('client_name','?')}\n"
        f"📞 Телефон: {c.user_data.get('phone','?')}\n"
        f"📋 Тип: {c.user_data.get('type','?')}\n"
        f"🏠 Объект: {c.user_data.get('object','?')}\n"
        f"📍 Район/Адрес: {c.user_data.get('location','?')}\n"
        f"💰 Цена/Бюджет: {c.user_data.get('price','?')}\n"
        f"🏘 Инфраструктура: {c.user_data.get('infra','Не указано')}\n"
        f"🎯 Цель: {c.user_data.get('purpose','Не указано')}\n"
        f"💳 Оплата: {c.user_data.get('payment','?')}\n"
        f"⏰ Срок: {c.user_data.get('timing','?')}"
    )
    if lat and lon: summary += f"\n🗺 Геолокация: {lat}, {lon}"
    
    # СРАЗУ отправляем карточку тебе
    await notify_admin(c, summary, edit_note, yandex_url)
    
    # Отвечаем клиенту — с теплом и благодарностью
    name = c.user_data.get('client_name', 'друг')
    card = (
        f"✨ <b>Искренне благодарю вас, {name}!</b>\n\n"
        f"Ваши данные уже у нашего специалиста. Мы свяжемся с вами в самое ближайшее время.\n\n"
        f"📇 <b>МОЯ ВИЗИТКА:</b>\n"
        f"👤 Андрей | ARTEM AI\n"
        f"📱 +7 (XXX) XXX-XX-XX\n"
        f"─────────────\n"
        f"💡 Могу Я ещё чем-то помочь вам сегодня?\n"
        f"Мы будем рады видеть вас снова в любое время! 🌿"
    )
    kb_inline = InlineKeyboardMarkup([
        [InlineKeyboardButton("👍 Всё отлично!",callback_data="fb_plus"),
         InlineKeyboardButton("👎 Есть замечания",callback_data="fb_minus")],
        [InlineKeyboardButton("💰 Продать",callback_data="menu_sell"),
         InlineKeyboardButton("🔍 Купить",callback_data="menu_buy")],
        [InlineKeyboardButton("🔑 Аренда",callback_data="menu_rent"),
         InlineKeyboardButton("🧮 Ипотека",callback_data="menu_mort")]
    ])
    if u.callback_query:
        await u.callback_query.edit_message_text(card, reply_markup=kb_inline, parse_mode='HTML')
    else:
        await u.message.reply_text(card, reply_markup=kb_inline, parse_mode='HTML')
    return next_state

async def sell_phone(u,c):
    if u.message.contact:
        c.user_data['phone'] = u.message.contact.phone_number
    elif u.message.location:
        c.user_data['latitude'], c.user_data['longitude'] = u.message.location.latitude, u.message.location.longitude
        return await ask_phone_geo(u,c)
    else:
        c.user_data['phone'] = clean(u.message.text)
    return await finish_flow(u,c,SELL_FB)

async def buy_phone(u,c):
    if u.message.contact:
        c.user_data['phone'] = u.message.contact.phone_number
    elif u.message.location:
        c.user_data['latitude'], c.user_data['longitude'] = u.message.location.latitude, u.message.location.longitude
        return await ask_phone_geo(u,c)
    else:
        c.user_data['phone'] = clean(u.message.text)
    return await finish_flow(u,c,BUY_FB)

async def rent_phone(u,c):
    if u.message.contact:
        c.user_data['phone'] = u.message.contact.phone_number
    elif u.message.location:
        c.user_data['latitude'], c.user_data['longitude'] = u.message.location.latitude, u.message.location.longitude
        return await ask_phone_geo(u,c)
    else:
        c.user_data['phone'] = clean(u.message.text)
    return await finish_flow(u,c,RENT_FB)

# ──────────────────────────────────────────────────────────────────────
# 14. ИПОТЕКА (Калькулятор) — с заботой и пониманием
# ──────────────────────────────────────────────────────────────────────
async def mort_price(u,c):
    await u.message.reply_text(
        "💰 <b>Продажа с ипотекой</b>\n\n"
        "Понимаю, вопрос деликатный. Уточните, пожалуйста: сколько осталось платить банку на сегодня?\n\n"
        "<i>Напишите сумму — я запомню и передам специалисту.</i>",
        reply_markup=get_back_kb(),
        parse_mode='HTML'
    )
    return MORT_RESULT

async def mort_pay(u,c):
    await u.message.reply_text(
        "🏦 <b>Покупка с ипотекой</b>\n\n"
        "Отлично, что рассматриваете этот вариант! Напишите кратко по пунктам:\n"
        "1️⃣ Ипотека уже одобрена?\n"
        "2️⃣ Размер первоначального взноса?\n"
        "3️⃣ Сроки сделки?\n\n"
        "<i>Ответьте текстом — я всё запомню и передам дальше.</i>",
        reply_markup=get_back_kb(),
        parse_mode='HTML'
    )
    return MORT_RATE

async def mort_rate(u,c):
    c.user_data['mortgage_info'] = u.message.text
    c.user_data['payment'] = "Ипотека"
    c.user_data['type'] = "buy"
    name = c.user_data.get('client_name', 'друг')
    await u.message.reply_text(
        f"📞 <b>{name}, спасибо!</b> Данные приняты.\n\n"
        "Оставьте, пожалуйста, номер телефона — менеджер свяжется в ближайшее время, бережно и по делу.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return BUY_PHONE

async def mort_res(u,c):
    c.user_data['mortgage_balance'] = u.message.text
    c.user_data['payment'] = "Ипотека (Продажа)"
    c.user_data['type'] = "sell"
    name = c.user_data.get('client_name', 'друг')
    await u.message.reply_text(
        f"📞 <b>{name}, спасибо!</b> Данные приняты.\n\n"
        "Оставьте, пожалуйста, номер телефона — менеджер свяжется в ближайшее время, бережно и по делу.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
            ["◀️ Назад"],["❌ Отмена"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return SELL_PHONE

# ──────────────────────────────────────────────────────────────────────
# 15. AI + МЕНЮ + ОБРАТНАЯ СВЯЗЬ — с теплом и профессионализмом
# ──────────────────────────────────────────────────────────────────────
async def ai_handler(u,c):
    t = clean(u.message.text)
    # Если клиент прислал номер в чате с AI
    phone_match = re.search(r'\+?7?\s*\(?\d{3}\)?\s*\d{3}[- ]?\d{2}[- ]?\d{2}', t)
    if phone_match:
        c.user_data['phone'] = re.sub(r'[^\d+]', '', phone_match.group())
        await u.message.reply_text(
            f"✅ Номер {c.user_data['phone']} записан! Менеджер свяжется с вами в ближайшее время. "
            f"Спасибо за доверие! 🙏",
            reply_markup=get_nav_kb()
        )
        await save_lead(c)
        await notify_admin(c, f"📞 Заявка из AI\n👤 {c.user_data.get('client_name')}\n📱 {c.user_data['phone']}")
        return ConversationHandler.END
    
    # Если клиент запутался — мягко эскалируем
    if any(w in t.lower() for w in ['запутался','сложно','помогите','позвоните','перезвоните']):
        await u.message.reply_text(
            "🤝 Вижу, что вопросов много и ситуация требует внимания. "
            "Давайте наш менеджер перезвонит вам? Это бесплатно и ни к чему не обязывает.\n\n"
            "Нажмите кнопку или просто напишите номер. Мы будем рады помочь! 🌿",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("📱 Отправить номер", request_contact=True)],
                ["◀️ Назад"]
            ], resize_keyboard=True)
        )
        return SELL_PHONE
    
    # Пытаемся ответить через AI
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
        f"Мы всегда на связи и будем рады видеть вас снова! 🌿"
    )
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
    q = u.callback_query
    await q.answer()
    if q.data == "fb_plus":
        await q.edit_message_text(
            "💙 Спасибо за тёплые слова! Это очень ценно для нас. "
            "Хорошего вам дня! Будем рады видеть вас снова! 🌿",
            reply_markup=get_nav_kb()
        )
    elif q.data == "fb_minus":
        await q.edit_message_text(
            "🙏 Спасибо за честность! Мы обязательно учтём ваши пожелания и станем лучше. "
            "Если есть конкретные идеи — напишите, я лично прочитаю. 🤝",
            reply_markup=get_nav_kb()
        )
    elif q.data == "nav_main":
        await q.edit_message_text(
            "↩️ Вернулись в главное меню. Чем ещё могу порадовать вас?",
            reply_markup=ReplyKeyboardMarkup([
                ["💰 Продать недвижимость"],["🔍 Купить недвижимость"],
                ["🔑 Арендовать"],["🧮 Калькулятор ипотеки"],
                ["🤖 Задать вопрос AI"],["🚀 меню"]
            ], resize_keyboard=True)
        )
        return CHOICE
    elif q.data == "nav_call":
        await q.edit_message_text(
            "📞 Наш менеджер на связи: +7 (962) 116-28-83\n"
            "Звоните в любое время, мы всегда рады помочь! 🌿",
            reply_markup=get_nav_kb()
        )
        return ConversationHandler.END
    elif q.data == "nav_ai":
        await q.edit_message_text(
            "🤖 AI-консультант снова на связи. Задавайте вопрос, я внимательно слушаю:",
            reply_markup=ReplyKeyboardMarkup([["❌ В меню"]], resize_keyboard=True)
        )
        return AI_CHAT
    elif q.data.startswith("menu_"):
        part = q.data.split("_")[1]
        c.user_data['type'] = part
        if part == "sell":
            await q.edit_message_text(
                "💰 Что планируете продавать?",
                reply_markup=ReplyKeyboardMarkup([
                    ["🏠 Квартира"],["🏡 Дом"],["🏢 Коммерция"],["🌲 Земля"]
                ], resize_keyboard=True)
            )
            return SELL_OBJ
        elif part == "buy":
            await q.edit_message_text(
                "🔍 Что ищете?",
                reply_markup=ReplyKeyboardMarkup([
                    ["🏠 Квартира"],["🏡 Дом"],["🌲 Участок"],["🏗️ Стройка"]
                ], resize_keyboard=True)
            )
            return BUY_OBJ
        elif part == "rent":
            await q.edit_message_text(
                "🔑 На какой срок рассматриваете аренду?",
                reply_markup=ReplyKeyboardMarkup([
                    ["📅 От 1 года"],["📆 Долго (3+ года)"]
                ], resize_keyboard=True)
            )
            return RENT_DUR
        elif part == "mortgage":
            await q.edit_message_text(
                "🧮 Введите стоимость недвижимости (в рублях):",
                reply_markup=ReplyKeyboardMarkup([["◀️ Назад"],["❌ Отмена"]], resize_keyboard=True)
            )
            return MORT_PRICE
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────────────────
# 16. ТРИГГЕР + WEBAPP + ЗАЩИТА — с юмором и заботой
# ──────────────────────────────────────────────────────────────────────
async def trigger_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    # Пропускаем команды и кнопки навигации
    if txt.startswith('/') or txt in ["Назад","Отмена","В главное меню","🔙 Назад","❌ Отмена"]:
        return
    resp = ai_trigger_check(txt)
    if resp:
        await update.message.reply_text(resp)
    else:
        # Мягко направляем в нужное русло
        await update.message.reply_text(
            "🤔 Понял запрос. Для точного ответа выбери раздел или уточни задачу:\n"
            "💰 Продать | 🔍 Купить | 🔑 Аренда | 🧮 Ипотека"
        )

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔑 ПЕРЕВОДЧИК: кнопки из Mini App → команды для бота"""
    try:
        data = json.loads(update.message.web_app_data.data)
        cmd = data.get('command')
        COMMAND_MAP = {
            "sell": "💰 Продать недвижимость",
            "buy": "🔍 Купить недвижимость",
            "rent": "🔑 Арендовать",
            "mortgage": "🧮 Калькулятор ипотеки",
            "ai": "🤖 Задать вопрос AI"
        }
        if cmd in COMMAND_MAP:
            # Подменяем текст, чтобы бот понял команду
            update.message.text = COMMAND_MAP[cmd]
            await update.message.reply_text(
                f"✅ Вы выбрали: <b>{COMMAND_MAP[cmd]}</b>\nЗапускаю процесс...",
                parse_mode='HTML'
            )
            await route_choice(update, context)
    except Exception as e:
        loguru_logger.error(f"❌ Ошибка Mini App: {e}")

async def safety_net(u, c):
    """🛡️ Если бот не понял — мягко просим номер"""
    await u.message.reply_text(
        "🤖 <b>Я вас не совсем понял.</b>\n\n"
        "Чтобы не терять время на переписку, лучше оставьте ваш номер телефона.\n"
        "Наш специалист свяжется с вами в ближайшее время и всё уточнит — бережно и по делу.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
            ["◀️ Назад"]
        ], resize_keyboard=True),
        parse_mode='HTML'
    )
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────────────────
# 17. ЗАПУСК — сборка всего воедино
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
            SELL_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT | filters.LOCATION, sell_phone)],
            SELL_FB: [CallbackQueryHandler(feedback_handler)],
            BUY_OBJ: [MessageHandler(filters.TEXT, b_obj)],
            BUY_LOC: [MessageHandler(filters.TEXT, b_location)],
            BUY_BUDGET: [MessageHandler(filters.TEXT, b_budget)],
            BUY_INFRA: [MessageHandler(filters.TEXT, b_infra)],
            BUY_PURPOSE: [MessageHandler(filters.TEXT, b_purpose)],
            BUY_PAY: [MessageHandler(filters.TEXT, b_pay)],
            BUY_MORT_DOWN: [MessageHandler(filters.TEXT, mortgage_down)],
            BUY_MAT_REST: [MessageHandler(filters.TEXT, maternity_rest)],
            BUY_TIME: [MessageHandler(filters.TEXT, b_time)],
            BUY_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT | filters.LOCATION, buy_phone)],
            BUY_FB: [CallbackQueryHandler(feedback_handler)],
            RENT_DUR: [MessageHandler(filters.TEXT, r_dur)],
            RENT_OCC: [MessageHandler(filters.TEXT, r_occ)],
            RENT_PHONE: [MessageHandler(filters.TEXT | filters.CONTACT | filters.LOCATION, rent_phone)],
            RENT_FB: [CallbackQueryHandler(feedback_handler)],
            AI_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_handler)],
            MORT_PRICE: [MessageHandler(filters.TEXT, mort_price)],
            MORT_PAY: [MessageHandler(filters.TEXT, mort_pay)],
            MORT_RATE: [MessageHandler(filters.TEXT, mort_rate)],
            MORT_RESULT: [MessageHandler(filters.TEXT, mort_res)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^◀️ Назад"), back_to_menu),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, safety_net),
        ]
    )
    
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, trigger_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    
    # Красивый лог при запуске
    logger.info("✨ ARTEM AI v9.0 — EXCLUSIVE EDITION — ONLINE ✅")
    console.print(Panel.fit("[bold green]🎨 Rich работает![/bold green]", border_style="cyan"))
    table = PrettyTable()
    table.field_names = ["Модуль", "Статус"]
    table.add_row(["Telegram API", "✅"])
    table.add_row(["Database", "✅"])
    table.add_row(["Yandex Geo", "✅"])
    console.print(table)
    loguru_logger.info("✅ AI-триггеры + Geo + WebApp подключены")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
