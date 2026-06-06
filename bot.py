import os
import json
import requests
from datetime import datetime, timedelta, time as dtime
import pytz
from icalendar import Calendar
import recurring_ical_events
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

LISBON = pytz.timezone("Europe/Lisbon")
DATA_FILE = "data.json"

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
            "Белок: рыба / яйца\n"
            "Много овощей, минимум углеводов\n\n"
            "💧 Не забывай про воду — 3л в день!"
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
            "💧 Не забывай про воду — 3л в день!"
        )

# --- Фоновые задачи ---

async def job_calendar_check(context):
    """Проверяет Google Calendar каждую минуту, уведомляет за 15 минут до события"""
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
            time_str = dtstart.strftime("%H:%M")
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"⏰ Через 15 минут: *{summary}*\n🕐 {time_str}",
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"Ошибка проверки календаря: {e}")

async def job_water_reminder(context):
    """Напоминание выпить 250мл воды"""
    if not CHAT_ID:
        return
    d = get_weekday()
    if d == 6:
        return
    data = load_data()
    today = datetime.now(LISBON).strftime("%Y-%m-%d")
    glasses = data.get("water", 0) if data.get("water_date") == today else 0
    liters = glasses * 0.25
    keyboard = [[InlineKeyboardButton("✅ Выпил 250мл", callback_data="water_add")]]
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"💧 Выпей 250мл воды!\n\nСегодня уже: {liters:.2f}л из 3л",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def job_meal_breakfast(context):
    """Напоминание о завтраке"""
    if not CHAT_ID:
        return
    d = get_weekday()
    if d in [5, 6]:
        return
    if not SCHEDULE[d]["pilates"]:
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=build_meal_text("breakfast"),
            parse_mode="Markdown"
        )

async def job_meal_snack(context):
    """Напоминание о перекусе (только дни с залом)"""
    if not CHAT_ID:
        return
    d = get_weekday()
    if SCHEDULE[d]["gym"]:
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=build_meal_text("snack"),
            parse_mode="Markdown"
        )

async def job_meal_pilates_breakfast(context):
    """Напоминание о завтраке в дни пилатеса (11:45)"""
    if not CHAT_ID:
        return
    d = get_weekday()
    if SCHEDULE[d]["pilates"]:
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=build_meal_text("breakfast"),
            parse_mode="Markdown"
        )

async def job_meal_lunch(context):
    """Напоминание об обеде"""
    if not CHAT_ID:
        return
    d = get_weekday()
    if d in [5, 6]:
        return
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=build_meal_text("lunch"),
        parse_mode="Markdown"
    )

async def job_meal_dinner(context):
    """Напоминание об ужине"""
    if not CHAT_ID:
        return
    d = get_weekday()
    if d == 6:
        return
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=build_meal_text("dinner"),
        parse_mode="Markdown"
    )

# --- Команды ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет, Den!\n\n"
        "Я твой личный трекер. Вот что я умею:\n\n"
        "📅 /today — расписание на сегодня\n"
        "🥗 /meal — рацион на сегодня\n"
        "🛒 /shop — список покупок\n"
        "💧 /water — трекер воды\n"
        "📊 /report — вечерний отчёт\n\n"
        "Автоматически:\n"
        "💧 Напоминания выпить воду — каждые 1-1.5ч\n"
        "🍽️ Напоминания о еде — за 15 мин до приёма\n"
        "⏰ Уведомления из Google Calendar — за 15 мин"
    )

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = get_weekday()
    day = SCHEDULE[d]
    now = datetime.now(LISBON)
    text = f"📅 *{day['name']}, {now.strftime('%d.%m')}* {day['emoji']}\n\n"

    if d == 6:
        text += "😴 Воскресенье — полный отдых!\nБез задач, без расписания. Заслужил."
    elif day["pilates"]:
        text += "🌅 *6:30* — Подъём, выпей воду\n"
        text += "🧘 *9:00–12:00* — Пилатес + дорога\n"
        text += "🍳 *12:00–12:45* — Завтрак / обед\n"
        text += "⚙️ *12:45–18:00* — Фриланс\n"
        text += "🌙 *19:00* — Ужин\n"
        text += "📚 *21:00–22:00* — Чтение\n"
    elif d == 5:
        text += "🌅 Суббота — свободный день\n"
        text += "📚 *21:00–22:00* — Чтение\n"
    else:
        text += "🌅 *6:30* — Подъём, выпей воду\n"
        text += "🍳 *6:30–7:00* — Завтрак\n"
        text += "⚙️ *7:00–13:00* — Работа\n"
        text += "🏋️ *13:00–14:30* — Зал\n"
        text += "🍽️ *14:30–15:15* — Обед\n"
        text += "⚙️ *15:15–18:00* — Работа\n"
        text += "🌙 *19:00* — Ужин\n"
        text += "📚 *21:00–22:00* — Чтение\n"

    text += "\n💧 Цель: 3л воды сегодня"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_full_meal_text(), parse_mode="Markdown")

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    shop = data.get("shop", {})
    needed = [i for i in SHOP_ITEMS if shop.get(i["id"]) == "needed"]
    total = sum(i["price"] for i in needed)

    if not needed:
        keyboard = [[InlineKeyboardButton("📋 Полный список", callback_data="shop_full")]]
        await update.message.reply_text(
            "✅ Список покупок пуст!\nВсё куплено или ничего не отмечено.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    text = f"🛒 *Нужно купить* ({len(needed)} позиций):\n\n"
    keyboard = []
    for item in needed:
        text += f"• {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
        keyboard.append([InlineKeyboardButton(f"✅ {item['name']}", callback_data=f"bought_{item['id']}")])

    text += f"\n💰 *Итого: {total:.2f}€*"
    keyboard.append([InlineKeyboardButton("📋 Полный список", callback_data="shop_full")])
    keyboard.append([InlineKeyboardButton("🔄 Отметить всё нужным", callback_data="shop_all")])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

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

    keyboard = [
        [InlineKeyboardButton("+ 250мл", callback_data="water_add"),
         InlineKeyboardButton("- 250мл", callback_data="water_remove")],
        [InlineKeyboardButton("Сбросить", callback_data="water_reset")]
    ]
    await update.message.reply_text(
        f"💧 *Вода сегодня*\n\n{bar}\n\nВыпито: *{liters:.2f}л* из 3л ({pct}%)\nСтаканов: {glasses} из {goal}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        f"Как прошёл день?\nНапиши мне пару строк 💪",
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    today = datetime.now(LISBON).strftime("%Y-%m-%d")
    cb = query.data

    if cb in ("water_add", "water_remove", "water_reset"):
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
        keyboard = [
            [InlineKeyboardButton("+ 250мл", callback_data="water_add"),
             InlineKeyboardButton("- 250мл", callback_data="water_remove")],
            [InlineKeyboardButton("Сбросить", callback_data="water_reset")]
        ]
        await query.edit_message_text(
            f"💧 *Вода сегодня*\n\n{bar}\n\nВыпито: *{liters:.2f}л* из 3л ({pct}%)\nСтаканов: {glasses} из {goal}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif cb.startswith("bought_"):
        item_id = cb.replace("bought_", "")
        data["shop"][item_id] = "done"
        save_data(data)
        needed = [i for i in SHOP_ITEMS if data["shop"].get(i["id"]) == "needed"]
        if not needed:
            await query.edit_message_text("✅ Всё куплено! Молодец 🎉")
        else:
            total = sum(i["price"] for i in needed)
            text = f"🛒 *Нужно купить* ({len(needed)} позиций):\n\n"
            keyboard = []
            for item in needed:
                text += f"• {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
                keyboard.append([InlineKeyboardButton(f"✅ {item['name']}", callback_data=f"bought_{item['id']}")])
            text += f"\n💰 *Итого: {total:.2f}€*"
            keyboard.append([InlineKeyboardButton("📋 Полный список", callback_data="shop_full")])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif cb == "shop_all":
        for item in SHOP_ITEMS:
            data["shop"][item["id"]] = "needed"
        save_data(data)
        needed = SHOP_ITEMS
        total = sum(i["price"] for i in needed)
        text = f"🛒 *Нужно купить* ({len(needed)} позиций):\n\n"
        keyboard = []
        for item in needed:
            text += f"• {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
            keyboard.append([InlineKeyboardButton(f"✅ {item['name']}", callback_data=f"bought_{item['id']}")])
        text += f"\n💰 *Итого: {total:.2f}€*"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif cb == "shop_full":
        text = "📋 *Полный список покупок на неделю:*\n\n"
        for item in SHOP_ITEMS:
            status = data["shop"].get(item["id"], "none")
            icon = "✅" if status == "done" else "🟡" if status == "needed" else "⬜"
            text += f"{icon} {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
        keyboard = [
            [InlineKeyboardButton("🔄 Отметить всё нужным", callback_data="shop_all")],
            [InlineKeyboardButton("🗑 Сбросить всё", callback_data="shop_reset")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif cb == "shop_reset":
        data["shop"] = {}
        save_data(data)
        await query.edit_message_text("✅ Список сброшен!")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(w in text for w in ["купить", "купи", "нужно"]):
        await update.message.reply_text("🛒 Чтобы добавить в список — используй /shop")
    elif any(w in text for w in ["вода", "воды", "выпил"]):
        await cmd_water(update, context)
    elif any(w in text for w in ["сегодня", "расписание", "план"]):
        await cmd_today(update, context)
    elif any(w in text for w in ["еда", "есть", "рацион", "завтрак", "обед", "ужин"]):
        await cmd_meal(update, context)
    else:
        await update.message.reply_text(
            "Привет! Вот что я умею:\n\n"
            "📅 /today — расписание\n"
            "🥗 /meal — рацион\n"
            "🛒 /shop — покупки\n"
            "💧 /water — вода\n"
            "📊 /report — отчёт дня"
        )

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("meal", cmd_meal))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("water", cmd_water))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    jq = app.job_queue

    # Проверка Google Calendar каждую минуту
    jq.run_repeating(job_calendar_check, interval=60, first=10)

    # Напоминания о воде — 12 раз в день по 250мл = 3л (пн-сб)
    water_times = [
        (6, 30), (7, 30), (8, 30), (9, 30), (10, 30), (11, 30),
        (13, 0), (14, 30), (16, 0), (17, 30), (19, 0), (20, 30),
    ]
    for h, m in water_times:
        jq.run_daily(job_water_reminder, time=dtime(hour=h, minute=m, tzinfo=LISBON))

    # Напоминания о еде (за 15 мин до приёма)
    # Завтрак в 6:15 — только дни с залом (вт,ср,чт)
    jq.run_daily(job_meal_breakfast, time=dtime(hour=6, minute=15, tzinfo=LISBON))
    # Перекус в 10:45 — только дни с залом
    jq.run_daily(job_meal_snack, time=dtime(hour=10, minute=45, tzinfo=LISBON))
    # Завтрак в 11:45 — только дни пилатеса (пн,пт)
    jq.run_daily(job_meal_pilates_breakfast, time=dtime(hour=11, minute=45, tzinfo=LISBON))
    # Обед в 14:15 (зал) / 14:45 (пилатес)
    jq.run_daily(job_meal_lunch, time=dtime(hour=14, minute=15, tzinfo=LISBON))
    # Ужин в 18:45 — все дни кроме вс
    jq.run_daily(job_meal_dinner, time=dtime(hour=18, minute=45, tzinfo=LISBON))

    print("Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
