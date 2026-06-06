import os
import json
import asyncio
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Load token from .env file or environment
def load_token():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("BOT_TOKEN="):
                    return line.split("=", 1)[1]
    return os.environ.get("BOT_TOKEN", "")

TOKEN = load_token()
DATA_FILE = "data.json"

SCHEDULE = {
    0: {"name": "Понедельник", "emoji": "🧘", "pilates": True,  "gym": False, "deep_work": "🤖 ИИ / приложения", "lang": "🇬🇧 Английский"},
    1: {"name": "Вторник",    "emoji": "🏋️", "pilates": False, "gym": True,  "deep_work": "🎬 Видеомейкерство", "lang": "🇵🇹 Португальский"},
    2: {"name": "Среда",      "emoji": "🏋️", "pilates": False, "gym": True,  "deep_work": "🤖 ИИ / приложения", "lang": "🇬🇧 Английский"},
    3: {"name": "Четверг",    "emoji": "🏋️", "pilates": False, "gym": True,  "deep_work": "🎬 Видеомейкерство", "lang": "🇵🇹 Португальский"},
    4: {"name": "Пятница",    "emoji": "🧘", "pilates": True,  "gym": False, "deep_work": "🤖 ИИ / приложения", "lang": "🇵🇹 Португальский"},
    5: {"name": "Суббота",    "emoji": "🌿", "pilates": False, "gym": False, "deep_work": "🎬 Видеомейкерство", "lang": "🌍 Язык на выбор"},
    6: {"name": "Воскресенье","emoji": "😴", "pilates": False, "gym": False, "deep_work": None, "lang": None},
}

SHOP_ITEMS = [
    {"id": "bacalhau",  "name": "Треска / Pescada",        "qty": "800г",  "price": 6.80},
    {"id": "salmao",    "name": "Лосось / Salmão",         "qty": "400г",  "price": 5.20},
    {"id": "atum",      "name": "Тунец в воде / Atum",     "qty": "6 банок", "price": 5.10},
    {"id": "ovos",      "name": "Яйца / Ovos",             "qty": "18 шт", "price": 4.03},
    {"id": "sardinhas", "name": "Сардины / Sardinhas",     "qty": "300г",  "price": 1.50},
    {"id": "arroz",     "name": "Рис интегральный",        "qty": "1 кг",  "price": 1.39},
    {"id": "batata",    "name": "Батат / Batata-doce",     "qty": "1 кг",  "price": 1.60},
    {"id": "massa",     "name": "Паста интегральная",      "qty": "500г",  "price": 0.99},
    {"id": "tomates",   "name": "Помидоры / Tomates",      "qty": "1 кг",  "price": 2.19},
    {"id": "pepinos",   "name": "Огурцы / Pepinos",        "qty": "4 шт",  "price": 1.20},
    {"id": "alface",    "name": "Салат / Alface",          "qty": "2 упак","price": 2.76},
    {"id": "brocoulos", "name": "Брокколи / Brócolos",    "qty": "1 кг",  "price": 1.49},
    {"id": "cenouras",  "name": "Морковь / Cenouras",      "qty": "1 кг",  "price": 1.09},
    {"id": "bananas",   "name": "Бананы / Bananas",        "qty": "1 кг",  "price": 1.28},
    {"id": "peras",     "name": "Груши / Peras",           "qty": "1 кг",  "price": 1.89},
    {"id": "laranjas",  "name": "Апельсины / Laranjas",   "qty": "1 кг",  "price": 1.61},
    {"id": "nozes",     "name": "Орехи / Frutos secos",   "qty": "200г",  "price": 2.49},
    {"id": "iogurte",   "name": "Йогурт греческий",       "qty": "1 кг",  "price": 2.25},
    {"id": "azeite",    "name": "Оливковое масло",         "qty": "500мл", "price": 3.99},
    {"id": "mozza",     "name": "Моцарелла / Mozzarella", "qty": "125г",  "price": 0.99},
    {"id": "agua",      "name": "Вода / Água",             "qty": "6×1,5л","price": 2.00},
]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"shop": {}, "water": 0, "water_date": ""}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_today():
    return datetime.now()

def get_weekday():
    return datetime.now().weekday()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет, Den!\n\n"
        "Я твой личный трекер. Вот что я умею:\n\n"
        "📅 /today — расписание на сегодня\n"
        "🥗 /meal — рацион на сегодня\n"
        "🛒 /shop — список покупок\n"
        "💧 /water — трекер воды\n"
        "📊 /report — вечерний отчёт\n\n"
        "Просто напиши мне в любое время!"
    )

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = get_weekday()
    day = SCHEDULE[d]
    now = get_today()
    text = f"📅 *{day['name']}, {now.strftime('%d.%m')}* {day['emoji']}\n\n"

    if d == 6:
        text += "😴 Воскресенье — полный отдых!\nБез задач, без расписания. Заслужил."
    else:
        if day["pilates"]:
            text += "🌅 *6:30* — Подъём, 1,5л воды\n"
            text += f"🧠 *6:30–8:15* — {day['deep_work']}\n"
            text += f"🌍 *8:15–9:00* — {day['lang']}\n"
            text += "🧘 *9:00–12:00* — Пилатес + дорога\n"
            text += "🍳 *12:00–12:45* — Завтрак / обед\n"
            text += "⚙️ *12:45–18:00* — Фриланс\n"
        else:
            text += "🌅 *6:30* — Подъём, 1,5л воды\n"
            text += "🍳 *6:30–7:00* — Быстрый завтрак\n"
            text += f"🧠 *7:00–9:00* — {day['deep_work']}\n"
            text += f"🌍 *9:00–9:45* — {day['lang']}\n"
            text += "⚙️ *9:45–13:00* — Фриланс\n"
            text += "🏋️ *13:00–14:30* — Зал\n"
            text += "🍽️ *14:30–15:15* — Обед\n"
            text += "⚙️ *15:15–18:00* — Фриланс\n"
        if d == 5:
            text += "🎬 *8:00–10:00* — Видеомейкерство\n"
            text += "🌿 Остаток дня — свободно\n"
        text += "📚 *21:00–22:00* — Чтение\n"
        text += "\n💧 Цель: минимум 3л воды сегодня"

    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = get_weekday()
    is_pilates = d in [0, 4]

    if d == 6:
        text = "😴 Воскресенье — ешь что хочешь, отдыхай!"
    elif is_pilates:
        text = (
            "🧘 *День пилатеса* — натощак до занятия!\n\n"
            "🍳 *12:00 — Завтрак/обед* (~600 ккал)\n"
            "Белок: лосось 150г / треска 200г / 3 яйца\n"
            "Углеводы: рис 150г / батат\n"
            "Овощи: салат + оливковое масло\n"
            "+ 1 фрукт\n\n"
            "🍽️ *15:00 — Обед* (~600 ккал)\n"
            "Белок: треска / тунец 200г\n"
            "Углеводы: рис 100г / батат\n"
            "Овощи + моцарелла\n\n"
            "🌙 *19:00 — Ужин* (~600 ккал)\n"
            "Белок: рыба / яйца\n"
            "Много овощей, минимум углеводов"
        )
    else:
        text = (
            "🌅 *Завтрак* 6:30 (~500 ккал)\n"
            "Белок: лосось 120г / треска 150г / 3 яйца\n"
            "Углеводы: рис/батат 150г\n"
            "Овощи + 1 фрукт\n\n"
            "🍎 *Перекус* ~11:00 (~200 ккал)\n"
            "Фрукт + орехи / йогурт\n\n"
            "🍽️ *Обед* 14:30 (~600 ккал)\n"
            "Белок: рыба 200г / 3 яйца\n"
            "Углеводы: меньше! 100г риса / батат\n"
            "Овощи + оливковое масло + 1 фрукт\n\n"
            "🌙 *Ужин* 19:00 (~600 ккал)\n"
            "Белок: рыба / яйца\n"
            "Много овощей, минимум углеводов"
        )

    text += "\n\n💧 Не забывай про воду — 3л в день!"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    shop = data.get("shop", {})
    needed = [i for i in SHOP_ITEMS if shop.get(i["id"]) == "needed"]
    total = sum(i["price"] for i in needed)

    if not needed:
        keyboard = [[InlineKeyboardButton("📋 Полный список", callback_data="shop_full")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "✅ Список покупок пуст!\nВсё куплено или ничего не отмечено.",
            reply_markup=reply_markup
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

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def cmd_water(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")
    if data.get("water_date") != today:
        data["water"] = 0
        data["water_date"] = today
        save_data(data)

    glasses = data.get("water", 0)
    liters = glasses * 0.25
    goal = 12  # 3 litres / 0.25

    bar = "💧" * glasses + "⬜" * (goal - glasses)
    pct = int(liters / 3.0 * 100)

    keyboard = [
        [InlineKeyboardButton("+ 250мл", callback_data="water_add"),
         InlineKeyboardButton("- 250мл", callback_data="water_remove")],
        [InlineKeyboardButton("Сбросить", callback_data="water_reset")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"💧 *Вода сегодня*\n\n"
        f"{bar}\n\n"
        f"Выпито: *{liters:.2f}л* из 3л ({pct}%)\n"
        f"Стаканов: {glasses} из {goal}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")
    glasses = data.get("water", 0) if data.get("water_date") == today else 0
    liters = glasses * 0.25
    d = get_weekday()
    day = SCHEDULE[d]

    water_ok = "✅" if liters >= 3 else "⚠️"

    text = (
        f"📊 *Отчёт за {datetime.now().strftime('%d.%m')}*\n\n"
        f"{water_ok} Вода: {liters:.2f}л / 3л\n\n"
        f"Как прошёл день?\n"
        f"Напиши мне пару строк — это помогает не терять неделю незаметно 💪"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")
    cb = query.data

    if cb == "water_add":
        if data.get("water_date") != today:
            data["water"] = 0
            data["water_date"] = today
        data["water"] = min(data.get("water", 0) + 1, 20)
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

    elif cb == "water_remove":
        if data.get("water_date") != today:
            data["water"] = 0
            data["water_date"] = today
        data["water"] = max(data.get("water", 0) - 1, 0)
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

    elif cb == "water_reset":
        data["water"] = 0
        data["water_date"] = today
        save_data(data)
        keyboard = [
            [InlineKeyboardButton("+ 250мл", callback_data="water_add"),
             InlineKeyboardButton("- 250мл", callback_data="water_remove")],
            [InlineKeyboardButton("Сбросить", callback_data="water_reset")]
        ]
        await query.edit_message_text(
            "💧 *Вода сегодня*\n\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜\n\nВыпито: *0.00л* из 3л (0%)\nСтаканов: 0 из 12",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif cb.startswith("bought_"):
        item_id = cb.replace("bought_", "")
        data["shop"][item_id] = "done"
        save_data(data)
        needed = [i for i in SHOP_ITEMS if data["shop"].get(i["id"]) == "needed"]
        total = sum(i["price"] for i in needed)
        if not needed:
            await query.edit_message_text("✅ Всё куплено! Молодец 🎉")
        else:
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
        await update.message.reply_text(
            "🛒 Чтобы добавить в список — используй /shop\nТам можно отметить что нужно купить."
        )
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

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("meal", cmd_meal))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("water", cmd_water))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("Bot started!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
