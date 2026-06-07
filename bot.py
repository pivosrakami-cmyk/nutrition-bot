import os
import json
import re
import requests
import ephem
from datetime import datetime, timedelta, time as dtime, date
import pytz
from icalendar import Calendar
import recurring_ical_events
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

LISBON = pytz.timezone("Europe/Lisbon")
DATA_FILE = "data.json"

BIRTH_DATE = date(1982, 4, 1)  # Денис, Овен

def load_env():
    env = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

_env = load_env()
TOKEN = _env.get("BOT_TOKEN") or os.environ.get("BOT_TOKEN", "")
CHAT_ID = int(_env.get("CHAT_ID") or os.environ.get("CHAT_ID", "0"))
CALENDAR_URL = _env.get("CALENDAR_ICAL_URL") or os.environ.get("CALENDAR_ICAL_URL", "")

SCHEDULE = {
    0: {"name": "Понедельник", "emoji": "🧘", "pilates": True,  "gym": False},
    1: {"name": "Вторник",    "emoji": "🏋️", "pilates": False, "gym": True},
    2: {"name": "Среда",      "emoji": "🏋️", "pilates": False, "gym": True},
    3: {"name": "Четверг",    "emoji": "🏋️", "pilates": False, "gym": True},
    4: {"name": "Пятница",    "emoji": "🧘", "pilates": True,  "gym": False},
    5: {"name": "Суббота",    "emoji": "🌿", "pilates": False, "gym": False},
    6: {"name": "Воскресенье","emoji": "😴", "pilates": False, "gym": False},
}

SHOP_ITEMS = [
    {"id": "bacalhau",  "name": "Треска / Pescada",        "qty": "800г",    "price": 6.80},
    {"id": "salmao",    "name": "Лосось / Salmão",         "qty": "400г",    "price": 5.20},
    {"id": "atum",      "name": "Тунец в воде / Atum",     "qty": "6 банок", "price": 5.10},
    {"id": "ovos",      "name": "Яйца / Ovos",             "qty": "18 шт",   "price": 4.03},
    {"id": "sardinhas", "name": "Сардины / Sardinhas",     "qty": "300г",    "price": 1.50},
    {"id": "arroz",     "name": "Рис интегральный",        "qty": "1 кг",    "price": 1.39},
    {"id": "batata",    "name": "Батат / Batata-doce",     "qty": "1 кг",    "price": 1.60},
    {"id": "massa",     "name": "Паста интегральная",      "qty": "500г",    "price": 0.99},
    {"id": "tomates",   "name": "Помидоры / Tomates",      "qty": "1 кг",    "price": 2.19},
    {"id": "pepinos",   "name": "Огурцы / Pepinos",        "qty": "4 шт",    "price": 1.20},
    {"id": "alface",    "name": "Салат / Alface",          "qty": "2 упак",  "price": 2.76},
    {"id": "brocoulos", "name": "Брокколи / Brócolos",    "qty": "1 кг",    "price": 1.49},
    {"id": "cenouras",  "name": "Морковь / Cenouras",      "qty": "1 кг",    "price": 1.09},
    {"id": "bananas",   "name": "Бананы / Bananas",        "qty": "1 кг",    "price": 1.28},
    {"id": "peras",     "name": "Груши / Peras",           "qty": "1 кг",    "price": 1.89},
    {"id": "laranjas",  "name": "Апельсины / Laranjas",   "qty": "1 кг",    "price": 1.61},
    {"id": "nozes",     "name": "Орехи / Frutos secos",   "qty": "200г",    "price": 2.49},
    {"id": "iogurte",   "name": "Йогурт греческий",       "qty": "1 кг",    "price": 2.25},
    {"id": "azeite",    "name": "Оливковое масло",         "qty": "500мл",   "price": 3.99},
    {"id": "mozza",     "name": "Моцарелла / Mozzarella", "qty": "125г",    "price": 0.99},
    {"id": "agua",      "name": "Вода / Água",             "qty": "6×1,5л",  "price": 2.00},
]

# --- Лунный календарь ---

LUNAR_DAYS = {
    1:  {"symbol": "🌑", "energy": "День новых начинаний. Мощный старт нового цикла — сей намерения.",
         "favorable": "Планирование, загадывание желаний, медитация, постановка целей на месяц",
         "avoid": "Конфликты, переедание, тяжёлый физический труд, важные решения",
         "aries": "Овен — твоя огненная природа получает свежий заряд. Запиши главную цель месяца утром."},
    2:  {"symbol": "🌒", "energy": "День накопления. Тихая, собирающая энергия.",
         "favorable": "Финансовые дела, копить силы, планировать бюджет, готовить",
         "avoid": "Спешка, импульсивные решения, конфликты",
         "aries": "Овен — притормози свою скорость, этот день требует терпения. Собирай, а не трать."},
    3:  {"symbol": "🌒", "energy": "День активности и движения. Энергия нарастает.",
         "favorable": "Физические нагрузки, начало новых дел, общение, переговоры",
         "avoid": "Переутомление, алкоголь, резкие решения",
         "aries": "Твой день! Энергия совпадает с твоей природой — действуй, тренируйся, запускай."},
    4:  {"symbol": "🌒", "energy": "День противоречий. Непростая энергия.",
         "favorable": "Рутинные дела, уборка, разбор накопившегося",
         "avoid": "Важные встречи, подписание договоров, споры",
         "aries": "Овен — сдержи импульсы. День не для атаки, а для наведения порядка внутри."},
    5:  {"symbol": "🌒", "energy": "День творчества и плодородия. Хорошая энергия.",
         "favorable": "Творческая работа, секс, начало отношений, посадка растений",
         "avoid": "Переедание сладкого, лень",
         "aries": "Твоя творческая искра сегодня особенно яркая. Создавай, рисуй, придумывай."},
    6:  {"symbol": "🌓", "energy": "День гармонии и красоты. Мягкая, приятная энергия.",
         "favorable": "Встречи с друзьями, уход за собой, стрижка волос, косметические процедуры",
         "avoid": "Ссоры, негатив, перегрузки",
         "aries": "Овен — позволь себе замедлиться и насладиться. Хороший день для социального."},
    7:  {"symbol": "🌓", "energy": "День информации и коммуникации. Слова имеют силу.",
         "favorable": "Переговоры, учёба, написание текстов, важные разговоры",
         "avoid": "Ложь, пустые разговоры, переизбыток информации",
         "aries": "День для твоих идей. Говори прямо — Марс даёт тебе убедительность."},
    8:  {"symbol": "🌓", "energy": "День силы и воли. Энергия на подъёме.",
         "favorable": "Тяжёлые нагрузки, важные решения, деловые встречи, операции",
         "avoid": "Конфликты, расточительность",
         "aries": "Один из твоих лучших дней! Берись за самое сложное — силы есть."},
    9:  {"symbol": "🌔", "energy": "День испытаний. Сложная, кармическая энергия.",
         "favorable": "Духовные практики, прощение, работа с прошлым",
         "avoid": "Новые начинания, важные сделки, конфликты",
         "aries": "Овен — не иди напролом сегодня. День для внутренней работы, а не внешних побед."},
    10: {"symbol": "🌔", "energy": "День рода и традиций. Тёплая семейная энергия.",
         "favorable": "Семья, дом, встречи с близкими, приготовление еды",
         "avoid": "Одиночество, разрывы отношений",
         "aries": "Позвони близким. Этот день усиливает связи с теми, кто важен."},
    11: {"symbol": "🌔", "energy": "День творческого пика. Яркая, вдохновляющая энергия.",
         "favorable": "Творчество, музыка, искусство, романтика, новые идеи",
         "avoid": "Скука, рутина, отказ от вдохновения",
         "aries": "Взрыв идей! Записывай всё что приходит — потом отберёшь лучшее."},
    12: {"symbol": "🌔", "energy": "День интуиции и чувств. Эмоциональный день.",
         "favorable": "Медитация, интуитивные решения, общение с природой",
         "avoid": "Логические расчёты, финансовые решения, операции",
         "aries": "Доверяй чутью сегодня больше чем логике. Твоя интуиция точна."},
    13: {"symbol": "🌕", "energy": "День трансформации. Энергия меняется, нарастает к полнолунию.",
         "favorable": "Завершение дел, подведение итогов, чистка пространства",
         "avoid": "Начинать новое, хирургические операции",
         "aries": "Доведи до конца незакрытые дела — завтра полнолуние потребует твоей полной силы."},
    14: {"symbol": "🌕", "energy": "Канун полнолуния. Пиковая энергия, всё усиливается.",
         "favorable": "Важные встречи, творчество, физическая активность, ритуалы благодарности",
         "avoid": "Переедание, алкоголь, ссоры — всё будет острее",
         "aries": "Огонь в огне! Энергия максимальная. Направь её в дело, иначе выльется в конфликты."},
    15: {"symbol": "🌕", "energy": "Полнолуние. Кульминация месячного цикла.",
         "favorable": "Медитация на благодарность, подведение итогов, отпускание старого",
         "avoid": "Алкоголь, конфликты, переработка, важные операции",
         "aries": "Ты сейчас как факел. Медитируй на то, что хочешь отпустить — полнолуние очищает."},
    16: {"symbol": "🌖", "energy": "День после пика. Спад, отдых, переосмысление.",
         "favorable": "Отдых, анализ прошедшего, лёгкие дела",
         "avoid": "Перегрузки, важные решения, споры",
         "aries": "Овен — выдохни. После пика нужно восстановление. Не гони."},
    17: {"symbol": "🌖", "energy": "День труда и дисциплины. Серьёзная, рабочая энергия.",
         "favorable": "Рутинная работа, учёба, технические дела, спорт",
         "avoid": "Прокрастинация, безделье",
         "aries": "Хороший день для системной работы. Твоя энергия + дисциплина дня = результат."},
    18: {"symbol": "🌖", "energy": "День осторожности. Скрытые процессы, будь внимателен.",
         "favorable": "Тихая работа, исследования, работа с документами",
         "avoid": "Ночные прогулки, сомнительные предложения, риск",
         "aries": "Не типичный для тебя день — замедлись и проверь детали. Интуиция важнее скорости."},
    19: {"symbol": "🌗", "energy": "День активности и некоторой нестабильности.",
         "favorable": "Физическая активность, срочные дела",
         "avoid": "Финансовые решения, операции, долгосрочное планирование",
         "aries": "Энергия есть, но хаотичная. Канализируй её в зал или прогулку."},
    20: {"symbol": "🌗", "energy": "День физической силы. Тело в фокусе.",
         "favorable": "Спорт, массаж, работа с телом, уборка, ремонт",
         "avoid": "Умственное перенапряжение",
         "aries": "Твой день для тела. Тренировка сегодня будет особенно эффективной."},
    21: {"symbol": "🌗", "energy": "День духовности и тишины.",
         "favorable": "Медитация, молитва, духовные практики, природа",
         "avoid": "Шум, толпа, пустые развлечения",
         "aries": "Редкий для тебя медитативный день. Попробуй 20 минут тишины — будешь удивлён результатом."},
    22: {"symbol": "🌘", "energy": "День материи и бизнеса.",
         "favorable": "Финансовые дела, бизнес-планирование, покупки, переговоры",
         "avoid": "Расточительность, импульсивные траты",
         "aries": "Хороший день для финансовых решений. Марс добавляет напористости в переговорах."},
    23: {"symbol": "🌘", "energy": "День рефлексии и анализа.",
         "favorable": "Анализ прошлого, планирование, работа в одиночестве",
         "avoid": "Важные встречи, публичные выступления",
         "aries": "Время оглянуться: что работает в твоей жизни, а что нет? Честный разговор с собой."},
    24: {"symbol": "🌘", "energy": "День любви и творчества.",
         "favorable": "Отношения, романтика, творчество, красота, музыка",
         "avoid": "Ссоры, критика близких",
         "aries": "Тёплый день для сердца. Скажи важным людям что они важны."},
    25: {"symbol": "🌘", "energy": "День восстановления и покоя.",
         "favorable": "Отдых, сон, природа, лёгкое питание",
         "avoid": "Перегрузки, жирная еда, алкоголь",
         "aries": "Овен, дай себе отдохнуть — это не слабость, это стратегия."},
    26: {"symbol": "🌘", "energy": "День завершений. Закрывай циклы.",
         "favorable": "Завершение проектов, прощение обид, расставание с ненужным",
         "avoid": "Новые начинания, важные знакомства",
         "aries": "Что ты давно откладывал закрыть? Сегодня сделай это."},
    27: {"symbol": "🌘", "energy": "День очищения. Отпускай лишнее.",
         "favorable": "Чистка дома, детокс, прощение, работа с психологом",
         "avoid": "Накопление вещей, негативные мысли",
         "aries": "Очисти пространство — физическое и ментальное. Освободи место для нового."},
    28: {"symbol": "🌑", "energy": "День тишины и подготовки к новому циклу.",
         "favorable": "Тихие дела, планирование, отдых, природа",
         "avoid": "Важные решения, конфликты, операции",
         "aries": "Предпоследний день цикла. Накапливай силы — скоро новолуние и новый старт."},
    29: {"symbol": "🌑", "energy": "Самый сложный день месяца. Старое умирает, новое ещё не родилось.",
         "favorable": "Только рутина, отдых, духовные практики",
         "avoid": "Всё важное: сделки, встречи, операции, начинания",
         "aries": "Переживи этот день спокойно. Не форсируй. Завтра будет новолуние и всё изменится."},
    30: {"symbol": "🌑", "energy": "Завершение цикла. Тишина перед бурей.",
         "favorable": "Медитация, благодарность за прошедший месяц, лёгкое питание",
         "avoid": "Новые начинания, перегрузки",
         "aries": "Подведи итог месяца. Что получил? Что отпустил? Завтра всё начнётся заново."},
}

MOON_PHASES = [
    (1, 3, "🌑 Новолуние"),
    (4, 7, "🌒 Растущий серп"),
    (8, 10, "🌓 Первая четверть"),
    (11, 13, "🌔 Растущая луна"),
    (14, 16, "🌕 Полнолуние"),
    (17, 20, "🌖 Убывающая луна"),
    (21, 24, "🌗 Последняя четверть"),
    (25, 30, "🌘 Убывающий серп"),
]

def get_lunar_day(for_date=None):
    if for_date is None:
        dt = datetime.now(LISBON).replace(tzinfo=None)
    else:
        dt = datetime.combine(for_date, datetime.min.time())
    prev_new = ephem.previous_new_moon(dt)
    diff = dt - prev_new.datetime()
    lunar_day = int(diff.total_seconds() / 86400) + 1
    return min(max(lunar_day, 1), 30)

def get_phase_name(lunar_day):
    for start, end, name in MOON_PHASES:
        if start <= lunar_day <= end:
            return name
    return "🌑 Новолуние"

def build_lunar_text(for_date=None):
    lunar_day = get_lunar_day(for_date)
    info = LUNAR_DAYS.get(lunar_day, LUNAR_DAYS[1])
    phase = get_phase_name(lunar_day)
    label = f"{for_date.strftime('%d.%m.%Y')}" if for_date else datetime.now(LISBON).strftime("%d.%m.%Y")
    return (
        f"{info['symbol']} *{lunar_day}-й лунный день* | {label}\n"
        f"{phase}\n\n"
        f"*Энергия дня:*\n{info['energy']}\n\n"
        f"✅ *Благоприятно:*\n{info['favorable']}\n\n"
        f"❌ *Избегать:*\n{info['avoid']}\n\n"
        f"♈ *Для тебя (Овен):*\n{info['aries']}"
    )

# --- Парсинг русских дат ---

MONTHS_RU = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "май": 5, "мая": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}

def parse_russian_date(text):
    pattern = r'(\d{1,2})\s+(январ\w*|феврал\w*|март\w*|апрел\w*|май\w*|мая|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)\s*(\d{4})?'
    match = re.search(pattern, text.lower())
    if not match:
        return None
    day = int(match.group(1))
    month_str = match.group(2)
    year = int(match.group(3)) if match.group(3) else datetime.now(LISBON).year
    for key, month in MONTHS_RU.items():
        if month_str.startswith(key[:4]):
            try:
                return date(year, month, day)
            except Exception:
                return None
    return None

# --- Вспомогательные функции ---

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"shop": {}, "water": 0, "water_date": ""}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_weekday():
    return datetime.now(LISBON).weekday()

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Расписание", callback_data="cmd_today"),
         InlineKeyboardButton("🥗 Рацион", callback_data="cmd_meal")],
        [InlineKeyboardButton("💧 Вода", callback_data="cmd_water"),
         InlineKeyboardButton("🛒 Покупки", callback_data="cmd_shop")],
        [InlineKeyboardButton("🌙 Луна", callback_data="cmd_luna"),
         InlineKeyboardButton("📊 Отчёт", callback_data="cmd_report")],
    ])

def build_meal_text(meal_type, d=None):
    if d is None:
        d = get_weekday()
    is_pilates = d in [0, 4]

    if meal_type == "breakfast":
        if is_pilates:
            return (
                "🍳 *Завтрак / Обед через 15 минут* (12:00)\n\n"
                "Первый приём после пилатеса!\n\n"
                "Белок: лосось 150г / треска 200г / 3 яйца\n"
                "Углеводы: рис 150г / батат\n"
                "Овощи + оливковое масло + 1 фрукт\n"
                "~600 ккал"
            )
        else:
            return (
                "🌅 *Завтрак через 15 минут* (6:30)\n\n"
                "Белок: лосось 120г / треска 150г / 3 яйца\n"
                "Углеводы: рис/батат 150г\n"
                "Овощи + 1 фрукт\n"
                "~500 ккал"
            )
    elif meal_type == "snack":
        return (
            "🍎 *Перекус через 15 минут* (~11:00)\n\n"
            "1 фрукт + горсть орехов\n"
            "или 1 фрукт + греческий йогурт\n"
            "~200 ккал"
        )
    elif meal_type == "lunch":
        if is_pilates:
            return (
                "🍽️ *Обед через 15 минут* (15:00)\n\n"
                "Белок: треска / тунец 200г\n"
                "Углеводы: рис 100г / батат\n"
                "Овощи + моцарелла\n"
                "~600 ккал"
            )
        else:
            return (
                "🍽️ *Обед через 15 минут* (14:30)\n\n"
                "Белок: рыба 200г / 3 яйца\n"
                "Углеводы: 100г риса / батат\n"
                "Овощи + оливковое масло + 1 фрукт\n"
                "~600 ккал"
            )
    elif meal_type == "dinner":
        return (
            "🌙 *Ужин через 15 минут* (19:00)\n\n"
            "Белок: рыба / яйца\n"
            "Много овощей, минимум углеводов\n"
            "~600 ккал"
        )
    return ""

def build_full_meal_text(d=None):
    if d is None:
        d = get_weekday()
    is_pilates = d in [0, 4]

    if d == 6:
        return "😴 Воскресенье — ешь что хочешь, отдыхай!\n\n💧 Не забывай про воду — 3л в день!"
    elif is_pilates:
        return (
            "🧘 *День пилатеса* — натощак до занятия!\n\n"
            "🍳 *12:00 — Завтрак/обед* (~600 ккал)\n"
            "Белок: лосось 150г / треска 200г / 3 яйца\n"
            "Углеводы: рис 150г / батат\n"
            "Овощи + оливковое масло + 1 фрукт\n\n"
            "🍽️ *15:00 — Обед* (~600 ккал)\n"
            "Белок: треска / тунец 200г\n"
            "Углеводы: рис 100г / батат\n"
            "Овощи + моцарелла\n\n"
            "🌙 *19:00 — Ужин* (~600 ккал)\n"
            "Белок: рыба / яйца + много овощей\n\n"
            "💧 Цель: 3л воды"
        )
    else:
        return (
            "🌅 *Завтрак* 6:30 (~500 ккал)\n"
            "Белок: лосось 120г / треска 150г / 3 яйца\n"
            "Углеводы: рис/батат 150г + овощи + 1 фрукт\n\n"
            "🍎 *Перекус* ~11:00 (~200 ккал)\n"
            "Фрукт + орехи / йогурт\n\n"
            "🍽️ *Обед* 14:30 (~600 ккал)\n"
            "Белок: рыба 200г / 3 яйца\n"
            "Углеводы: 100г риса / батат + овощи + 1 фрукт\n\n"
            "🌙 *Ужин* 19:00 (~600 ккал)\n"
            "Белок: рыба / яйца + много овощей\n\n"
            "💧 Цель: 3л воды"
        )

# --- Фоновые задачи ---

async def job_calendar_check(context):
    if not CALENDAR_URL or not CHAT_ID:
        return
    try:
        now = datetime.now(LISBON)
        window_start = now + timedelta(minutes=14)
        window_end = now + timedelta(minutes=16)
        response = requests.get(CALENDAR_URL, timeout=10)
        cal = Calendar.from_ical(response.content)
        events = recurring_ical_events.of(cal).between(window_start, window_end)
        for event in events:
            summary = str(event.get("SUMMARY", "Событие"))
            dtstart = event.get("DTSTART").dt
            if not hasattr(dtstart, 'hour'):
                continue
            if dtstart.tzinfo:
                dtstart = dtstart.astimezone(LISBON)
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"⏰ Через 15 минут: *{summary}*\n🕐 {dtstart.strftime('%H:%M')}",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
    except Exception as e:
        print(f"Ошибка проверки календаря: {e}")

async def job_luna_morning(context):
    if not CHAT_ID:
        return
    text = "🌙 *Лунный день — доброе утро, Den!*\n\n" + build_lunar_text()
    await context.bot.send_message(
        chat_id=CHAT_ID, text=text,
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

async def job_water_reminder(context):
    if not CHAT_ID:
        return
    if get_weekday() == 6:
        return
    data = load_data()
    today = datetime.now(LISBON).strftime("%Y-%m-%d")
    glasses = data.get("water", 0) if data.get("water_date") == today else 0
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Выпил 250мл", callback_data="water_add")],
        [InlineKeyboardButton("💧 Трекер воды", callback_data="cmd_water")],
    ])
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"💧 Выпей 250мл воды!\n\nСегодня уже: {glasses * 0.25:.2f}л из 3л",
        reply_markup=keyboard
    )

async def job_meal_breakfast(context):
    if not CHAT_ID:
        return
    d = get_weekday()
    if d in [5, 6] or SCHEDULE[d]["pilates"]:
        return
    await context.bot.send_message(
        chat_id=CHAT_ID, text=build_meal_text("breakfast"),
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

async def job_meal_snack(context):
    if not CHAT_ID:
        return
    if SCHEDULE[get_weekday()]["gym"]:
        await context.bot.send_message(
            chat_id=CHAT_ID, text=build_meal_text("snack"),
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

async def job_meal_pilates_breakfast(context):
    if not CHAT_ID:
        return
    if SCHEDULE[get_weekday()]["pilates"]:
        await context.bot.send_message(
            chat_id=CHAT_ID, text=build_meal_text("breakfast"),
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

async def job_meal_lunch(context):
    if not CHAT_ID:
        return
    if get_weekday() not in [5, 6]:
        await context.bot.send_message(
            chat_id=CHAT_ID, text=build_meal_text("lunch"),
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

async def job_meal_dinner(context):
    if not CHAT_ID:
        return
    if get_weekday() != 6:
        await context.bot.send_message(
            chat_id=CHAT_ID, text=build_meal_text("dinner"),
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

# --- Команды ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет, Den!\n\n"
        "Я твой личный трекер:\n\n"
        "📅 /today — расписание\n"
        "🥗 /meal — рацион\n"
        "🛒 /shop — покупки\n"
        "💧 /water — трекер воды\n"
        "🌙 /luna — лунный день\n"
        "📊 /report — отчёт дня\n\n"
        "Просто напиши дату — проверю по лунному календарю.",
        reply_markup=main_keyboard()
    )

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = get_weekday()
    day = SCHEDULE[d]
    now = datetime.now(LISBON)
    text = f"📅 *{day['name']}, {now.strftime('%d.%m')}* {day['emoji']}\n\n"
    if d == 6:
        text += "😴 Воскресенье — полный отдых!"
    elif day["pilates"]:
        text += "🌅 *6:30* — Подъём, выпей воду\n🧘 *9:00–12:00* — Пилатес\n🍳 *12:00* — Завтрак/обед\n⚙️ *12:45–18:00* — Работа\n🌙 *19:00* — Ужин\n📚 *21:00* — Чтение"
    elif d == 5:
        text += "🌿 Суббота — свободный день\n📚 *21:00* — Чтение"
    else:
        text += "🌅 *6:30* — Подъём\n🍳 *6:30* — Завтрак\n⚙️ *7:00–13:00* — Работа\n🏋️ *13:00* — Зал\n🍽️ *14:30* — Обед\n⚙️ *15:15–18:00* — Работа\n🌙 *19:00* — Ужин\n📚 *21:00* — Чтение"
    text += "\n\n💧 Цель: 3л воды"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def cmd_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_full_meal_text(), parse_mode="Markdown", reply_markup=main_keyboard())

async def cmd_luna(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_lunar_text(), parse_mode="Markdown", reply_markup=main_keyboard())

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    shop = data.get("shop", {})
    needed = [i for i in SHOP_ITEMS if shop.get(i["id"]) == "needed"]
    total = sum(i["price"] for i in needed)

    if not needed:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Полный список", callback_data="shop_full")],
            [InlineKeyboardButton("🔄 Отметить всё нужным", callback_data="shop_all")],
        ])
        await update.message.reply_text("✅ Список покупок пуст!", reply_markup=keyboard)
        return

    text = f"🛒 *Нужно купить* ({len(needed)} позиций):\n\n"
    keyboard_rows = []
    for item in needed:
        text += f"• {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
        keyboard_rows.append([InlineKeyboardButton(f"✅ {item['name']}", callback_data=f"bought_{item['id']}")])
    text += f"\n💰 *Итого: {total:.2f}€*"
    keyboard_rows.append([InlineKeyboardButton("📋 Полный список", callback_data="shop_full")])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_rows))

async def cmd_water(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = datetime.now(LISBON).strftime("%Y-%m-%d")
    if data.get("water_date") != today:
        data["water"] = 0
        data["water_date"] = today
        save_data(data)
    glasses = data.get("water", 0)
    liters = glasses * 0.25
    goal = 12
    bar = "💧" * glasses + "⬜" * (goal - glasses)
    pct = int(liters / 3.0 * 100)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("+ 250мл", callback_data="water_add"),
         InlineKeyboardButton("- 250мл", callback_data="water_remove")],
        [InlineKeyboardButton("Сбросить", callback_data="water_reset")],
    ])
    await update.message.reply_text(
        f"💧 *Вода сегодня*\n\n{bar}\n\nВыпито: *{liters:.2f}л* из 3л ({pct}%)\nСтаканов: {glasses} из {goal}",
        parse_mode="Markdown", reply_markup=keyboard
    )

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = datetime.now(LISBON).strftime("%Y-%m-%d")
    glasses = data.get("water", 0) if data.get("water_date") == today else 0
    liters = glasses * 0.25
    water_ok = "✅" if liters >= 3 else "⚠️"
    await update.message.reply_text(
        f"📊 *Отчёт за {datetime.now(LISBON).strftime('%d.%m')}*\n\n"
        f"{water_ok} Вода: {liters:.2f}л / 3л\n\n"
        f"Как прошёл день? Напиши пару строк 💪",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    today = datetime.now(LISBON).strftime("%Y-%m-%d")
    cb = query.data

    # Команды через кнопки
    if cb == "cmd_today":
        d = get_weekday()
        day = SCHEDULE[d]
        now = datetime.now(LISBON)
        text = f"📅 *{day['name']}, {now.strftime('%d.%m')}* {day['emoji']}\n\n"
        if d == 6:
            text += "😴 Воскресенье — полный отдых!"
        elif day["pilates"]:
            text += "🧘 *9:00–12:00* — Пилатес\n🍳 *12:00* — Завтрак\n⚙️ *12:45–18:00* — Работа\n🌙 *19:00* — Ужин"
        elif d == 5:
            text += "🌿 Свободный день"
        else:
            text += "🍳 *6:30* — Завтрак\n🏋️ *13:00* — Зал\n🍽️ *14:30* — Обед\n🌙 *19:00* — Ужин"
        text += "\n\n💧 Цель: 3л воды"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

    elif cb == "cmd_meal":
        await query.edit_message_text(build_full_meal_text(), parse_mode="Markdown", reply_markup=main_keyboard())

    elif cb == "cmd_luna":
        await query.edit_message_text(build_lunar_text(), parse_mode="Markdown", reply_markup=main_keyboard())

    elif cb == "cmd_report":
        glasses = data.get("water", 0) if data.get("water_date") == today else 0
        liters = glasses * 0.25
        water_ok = "✅" if liters >= 3 else "⚠️"
        await query.edit_message_text(
            f"📊 *Отчёт за {datetime.now(LISBON).strftime('%d.%m')}*\n\n"
            f"{water_ok} Вода: {liters:.2f}л / 3л\n\nКак прошёл день? Напиши 💪",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

    elif cb == "cmd_water":
        if data.get("water_date") != today:
            data["water"] = 0
            data["water_date"] = today
            save_data(data)
        glasses = data.get("water", 0)
        liters = glasses * 0.25
        goal = 12
        bar = "💧" * glasses + "⬜" * max(0, goal - glasses)
        pct = int(liters / 3.0 * 100)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("+ 250мл", callback_data="water_add"),
             InlineKeyboardButton("- 250мл", callback_data="water_remove")],
            [InlineKeyboardButton("Сбросить", callback_data="water_reset")],
        ])
        await query.edit_message_text(
            f"💧 *Вода сегодня*\n\n{bar}\n\nВыпито: *{liters:.2f}л* из 3л ({pct}%)\nСтаканов: {glasses} из {goal}",
            parse_mode="Markdown", reply_markup=keyboard
        )

    elif cb == "cmd_shop":
        shop = data.get("shop", {})
        needed = [i for i in SHOP_ITEMS if shop.get(i["id"]) == "needed"]
        if not needed:
            await query.edit_message_text(
                "✅ Список покупок пуст!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 Полный список", callback_data="shop_full")]])
            )
        else:
            total = sum(i["price"] for i in needed)
            text = f"🛒 *Нужно купить* ({len(needed)} позиций):\n\n"
            keyboard_rows = []
            for item in needed:
                text += f"• {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
                keyboard_rows.append([InlineKeyboardButton(f"✅ {item['name']}", callback_data=f"bought_{item['id']}")])
            text += f"\n💰 *Итого: {total:.2f}€*"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_rows))

    elif cb in ("water_add", "water_remove", "water_reset"):
        if data.get("water_date") != today:
            data["water"] = 0
            data["water_date"] = today
        if cb == "water_add":
            data["water"] = min(data.get("water", 0) + 1, 20)
        elif cb == "water_remove":
            data["water"] = max(data.get("water", 0) - 1, 0)
        else:
            data["water"] = 0
        save_data(data)
        glasses = data["water"]
        liters = glasses * 0.25
        goal = 12
        bar = "💧" * glasses + "⬜" * max(0, goal - glasses)
        pct = int(liters / 3.0 * 100)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("+ 250мл", callback_data="water_add"),
             InlineKeyboardButton("- 250мл", callback_data="water_remove")],
            [InlineKeyboardButton("Сбросить", callback_data="water_reset")],
        ])
        await query.edit_message_text(
            f"💧 *Вода сегодня*\n\n{bar}\n\nВыпито: *{liters:.2f}л* из 3л ({pct}%)\nСтаканов: {glasses} из {goal}",
            parse_mode="Markdown", reply_markup=keyboard
        )

    elif cb.startswith("bought_"):
        item_id = cb.replace("bought_", "")
        data["shop"][item_id] = "done"
        save_data(data)
        needed = [i for i in SHOP_ITEMS if data["shop"].get(i["id"]) == "needed"]
        if not needed:
            await query.edit_message_text("✅ Всё куплено! Молодец 🎉", reply_markup=main_keyboard())
        else:
            total = sum(i["price"] for i in needed)
            text = f"🛒 *Нужно купить* ({len(needed)} позиций):\n\n"
            keyboard_rows = []
            for item in needed:
                text += f"• {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
                keyboard_rows.append([InlineKeyboardButton(f"✅ {item['name']}", callback_data=f"bought_{item['id']}")])
            text += f"\n💰 *Итого: {total:.2f}€*"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_rows))

    elif cb == "shop_all":
        for item in SHOP_ITEMS:
            data["shop"][item["id"]] = "needed"
        save_data(data)
        total = sum(i["price"] for i in SHOP_ITEMS)
        text = f"🛒 *Нужно купить* ({len(SHOP_ITEMS)} позиций):\n\n"
        keyboard_rows = []
        for item in SHOP_ITEMS:
            text += f"• {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
            keyboard_rows.append([InlineKeyboardButton(f"✅ {item['name']}", callback_data=f"bought_{item['id']}")])
        text += f"\n💰 *Итого: {total:.2f}€*"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_rows))

    elif cb == "shop_full":
        text = "📋 *Полный список покупок:*\n\n"
        for item in SHOP_ITEMS:
            status = data["shop"].get(item["id"], "none")
            icon = "✅" if status == "done" else "🟡" if status == "needed" else "⬜"
            text += f"{icon} {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Всё нужно купить", callback_data="shop_all"),
             InlineKeyboardButton("🗑 Сброс", callback_data="shop_reset")],
        ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif cb == "shop_reset":
        data["shop"] = {}
        save_data(data)
        await query.edit_message_text("✅ Список сброшен!", reply_markup=main_keyboard())

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Проверка даты по лунному календарю
    parsed_date = parse_russian_date(text)
    if parsed_date:
        lunar_day = get_lunar_day(parsed_date)
        info = LUNAR_DAYS.get(lunar_day, LUNAR_DAYS[1])
        phase = get_phase_name(lunar_day)
        reply = (
            f"🔍 *Проверка даты: {parsed_date.strftime('%d.%m.%Y')}*\n\n"
            f"{info['symbol']} *{lunar_day}-й лунный день* | {phase}\n\n"
            f"*Энергия:* {info['energy']}\n\n"
            f"✅ *Благоприятно:* {info['favorable']}\n\n"
            f"❌ *Избегать:* {info['avoid']}\n\n"
            f"♈ *Для тебя:* {info['aries']}"
        )
        await update.message.reply_text(reply, parse_mode="Markdown", reply_markup=main_keyboard())
        return

    tl = text.lower()
    if any(w in tl for w in ["купить", "купи", "нужно"]):
        await update.message.reply_text("🛒 Используй /shop", reply_markup=main_keyboard())
    elif any(w in tl for w in ["вода", "воды", "выпил"]):
        await cmd_water(update, context)
    elif any(w in tl for w in ["сегодня", "расписание", "план"]):
        await cmd_today(update, context)
    elif any(w in tl for w in ["еда", "рацион", "завтрак", "обед", "ужин"]):
        await cmd_meal(update, context)
    elif any(w in tl for w in ["луна", "лунный", "лун"]):
        await cmd_luna(update, context)
    else:
        await update.message.reply_text(
            "Привет! Используй меню или напиши дату — проверю по лунному календарю.\n\nПример: *планирую встречу на 15 июля*",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

async def post_init(app):
    """Устанавливает команды и кнопку меню при запуске"""
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("today", "Расписание на сегодня"),
        BotCommand("meal", "Рацион на сегодня"),
        BotCommand("water", "Трекер воды"),
        BotCommand("luna", "Лунный день"),
        BotCommand("shop", "Список покупок"),
        BotCommand("report", "Отчёт дня"),
    ]
    await app.bot.set_my_commands(commands)
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("meal", cmd_meal))
    app.add_handler(CommandHandler("luna", cmd_luna))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("water", cmd_water))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    jq = app.job_queue

    # Google Calendar — каждую минуту
    jq.run_repeating(job_calendar_check, interval=60, first=10)

    # Лунный календарь — 6:00 утром
    jq.run_daily(job_luna_morning, time=dtime(hour=6, minute=0, tzinfo=LISBON))

    # Вода — 12 раз в день
    water_times = [
        (6, 30), (7, 30), (8, 30), (9, 30), (10, 30), (11, 30),
        (13, 0), (14, 30), (16, 0), (17, 30), (19, 0), (20, 30),
    ]
    for h, m in water_times:
        jq.run_daily(job_water_reminder, time=dtime(hour=h, minute=m, tzinfo=LISBON))

    # Еда — за 15 мин до приёма
    jq.run_daily(job_meal_breakfast,         time=dtime(hour=6,  minute=15, tzinfo=LISBON))
    jq.run_daily(job_meal_snack,             time=dtime(hour=10, minute=45, tzinfo=LISBON))
    jq.run_daily(job_meal_pilates_breakfast, time=dtime(hour=11, minute=45, tzinfo=LISBON))
    jq.run_daily(job_meal_lunch,             time=dtime(hour=14, minute=15, tzinfo=LISBON))
    jq.run_daily(job_meal_dinner,            time=dtime(hour=18, minute=45, tzinfo=LISBON))

    print("Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
