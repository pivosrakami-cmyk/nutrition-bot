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

# --- Лунный календарь (стиль рекомендаций) ---

LUNAR_DAYS = {
    1:  {"symbol": "🌑", "phase": "new",
         "energy": "Начало нового цикла. Энергия тихая, направлена внутрь — хорошее время чтобы остановиться и почувствовать что действительно важно.",
         "tips": "Составь список целей на месяц, помедитируй, побудь в тишине. Тяжёлые тренировки и крупные запуски лучше отложить на пару дней.",
         "aries": "Запиши одно главное намерение на месяц. Твоя сила Овна сейчас направлена на формирование, а не действие."},
    2:  {"symbol": "🌒", "phase": "waxing",
         "energy": "День накопления ресурсов. Тихая, собирающая энергия — хорошо для финансовых и бытовых дел.",
         "tips": "Займись планированием бюджета, готовкой на несколько дней, порядком в делах. Спешка сегодня скорее мешает чем помогает.",
         "aries": "Притормози свою скорость — этот день хорош для создания запаса, а не для рывка."},
    3:  {"symbol": "🌒", "phase": "waxing",
         "energy": "Энергия начинает расти. Хороший день для активных дел и общения.",
         "tips": "Начинай новые дела, выходи на связь, занимайся физической активностью. Следи за тем чтобы не перегореть с непривычки.",
         "aries": "Твой день! Энергия совпадает с твоей природой — действуй, запускай, тренируйся."},
    4:  {"symbol": "🌒", "phase": "waxing",
         "energy": "День с неоднозначной энергией — внутри могут быть противоречия.",
         "tips": "Хорошо подходит для рутины и уборки. Важные встречи и переговоры лучше перенести на день-два.",
         "aries": "Сдержи импульсы — сегодня лучше навести порядок внутри, чем атаковать снаружи."},
    5:  {"symbol": "🌒", "phase": "waxing",
         "energy": "Творческий и чувственный день. Хорошая энергия для создания чего-то нового.",
         "tips": "Займись творчеством, готовь что-то особенное, уделяй время близким. Сладкое лучше не злоупотреблять.",
         "aries": "Твоя творческая искра сегодня особенно яркая. Создавай, рисуй, придумывай."},
    6:  {"symbol": "🌓", "phase": "waxing",
         "energy": "День гармонии и красоты. Мягкая, приятная энергия для отношений.",
         "tips": "Встречайся с друзьями, ухаживай за собой, делай стрижку. Конфликты сегодня лучше не разжигать.",
         "aries": "Позволь себе замедлиться и насладиться. Хороший день для социального общения."},
    7:  {"symbol": "🌓", "phase": "waxing",
         "energy": "День слова и информации. Коммуникации особенно эффективны.",
         "tips": "Проводи переговоры, пиши тексты, учись новому. Слова сегодня имеют больший вес — выбирай их осознанно.",
         "aries": "День для твоих идей. Говори прямо — Марс даёт тебе убедительность."},
    8:  {"symbol": "🌓", "phase": "waxing",
         "energy": "День силы и воли. Энергия на хорошем подъёме.",
         "tips": "Берись за сложные задачи, проводи важные встречи, тренируйся интенсивно. Хороший день для решительных шагов.",
         "aries": "Один из твоих лучших дней! Берись за самое сложное — силы есть."},
    9:  {"symbol": "🌔", "phase": "waxing",
         "energy": "День внутренней работы. Энергия немного напряжённая.",
         "tips": "Уделяй время духовным практикам, анализу прошлого, прощению. Новые крупные начинания лучше отложить.",
         "aries": "Не иди напролом сегодня. День для внутренней работы, а не внешних побед."},
    10: {"symbol": "🌔", "phase": "waxing",
         "energy": "День семьи и корней. Тёплая, объединяющая энергия.",
         "tips": "Проводи время с близкими, готовь домашнюю еду, занимайся домом. Хороший день для укрепления связей.",
         "aries": "Позвони близким. Этот день усиливает связи с теми кто важен."},
    11: {"symbol": "🌔", "phase": "waxing",
         "energy": "Творческий пик растущей луны. Яркая вдохновляющая энергия.",
         "tips": "Занимайся творчеством, музыкой, искусством. Позволяй себе генерировать идеи без фильтра.",
         "aries": "Взрыв идей! Записывай всё что приходит — потом отберёшь лучшее."},
    12: {"symbol": "🌔", "phase": "waxing",
         "energy": "День интуиции. Чувства и ощущения особенно точны.",
         "tips": "Доверяй внутренним сигналам, общайся с природой, медитируй. Большие финансовые решения лучше отложить.",
         "aries": "Доверяй чутью сегодня больше чем логике. Твоя интуиция сейчас точна."},
    13: {"symbol": "🌕", "phase": "full",
         "energy": "Энергия нарастает к полнолунию. День трансформации.",
         "tips": "Завершай начатые дела, подводи промежуточные итоги. Новые крупные начинания лучше стартовать после полнолуния.",
         "aries": "Доведи до конца незакрытые дела — завтра полнолуние потребует твоей полной энергии."},
    14: {"symbol": "🌕", "phase": "full",
         "energy": "Канун полнолуния. Энергия на максимуме — всё усиливается.",
         "tips": "Хороший день для важных встреч и творческих прорывов. Алкоголь и споры лучше оставить на другой день — реакции будут острее.",
         "aries": "Огонь в огне! Энергия максимальная. Направь её в дело, иначе выльется в конфликты."},
    15: {"symbol": "🌕", "phase": "full",
         "energy": "Полнолуние. Кульминация месячного цикла — пик энергии и эмоций.",
         "tips": "Медитируй на благодарность, отпускай то что больше не служит. Алкоголь и интенсивные тренировки лучше перенести.",
         "aries": "Ты сейчас как факел. Направь энергию на медитацию и отпускание — полнолуние очищает."},
    16: {"symbol": "🌖", "phase": "waning",
         "energy": "День после пика. Энергия начинает убывать — время переосмысления.",
         "tips": "Отдыхай, анализируй прошедшее, занимайся лёгкими делами. Важные решения лучше принимать на свежую голову завтра.",
         "aries": "Выдохни. После пика нужно восстановление — не гони."},
    17: {"symbol": "🌖", "phase": "waning",
         "energy": "День дисциплины и труда. Хорошая рабочая энергия.",
         "tips": "Занимайся рутинными задачами, учёбой, системной работой. День хорошо поддерживает постоянство.",
         "aries": "Хороший день для системной работы. Твоя энергия + дисциплина дня = результат."},
    18: {"symbol": "🌖", "phase": "waning",
         "energy": "День внимательности. Стоит быть чуть осторожнее в незнакомых ситуациях.",
         "tips": "Хорош для тихой исследовательской работы и анализа документов. В незнакомых местах и с новыми людьми стоит проявлять чуть больше внимания.",
         "aries": "Не типичный для тебя день — замедлись и проверь детали. Интуиция важнее скорости."},
    19: {"symbol": "🌗", "phase": "waning",
         "energy": "День активности с элементом нестабильности.",
         "tips": "Хорошо для физической активности и срочных дел. Финансовые решения и долгосрочное планирование лучше отложить.",
         "aries": "Энергия есть, но хаотичная. Направь её в зал или прогулку."},
    20: {"symbol": "🌗", "phase": "waning",
         "energy": "День физической силы. Тело в фокусе.",
         "tips": "Отличный день для спорта, массажа, работы с телом. Умственное перенапряжение лучше оставить на другой день.",
         "aries": "Твой день для тела. Тренировка сегодня будет особенно эффективной."},
    21: {"symbol": "🌗", "phase": "waning",
         "energy": "День тишины и духовности.",
         "tips": "Медитируй, проводи время в природе, занимайся духовными практиками. Шумные места и толпа сегодня лучше не твои союзники.",
         "aries": "Редкий для тебя медитативный день. Попробуй 20 минут тишины — будешь удивлён результатом."},
    22: {"symbol": "🌘", "phase": "waning",
         "energy": "День материи и бизнеса.",
         "tips": "Хорош для финансовых решений, переговоров и деловых встреч. Импульсивные траты лучше отложить.",
         "aries": "Хороший день для финансовых решений. Марс добавляет напористости в переговорах."},
    23: {"symbol": "🌘", "phase": "waning",
         "energy": "День рефлексии и анализа.",
         "tips": "Анализируй прошедшее, планируй в одиночестве. Публичные выступления и важные встречи лучше перенести.",
         "aries": "Время честного разговора с собой: что работает в твоей жизни, а что нет?"},
    24: {"symbol": "🌘", "phase": "waning",
         "energy": "День сердца и творчества.",
         "tips": "Уделяй время отношениям, романтике, музыке. Критику и разборы полётов лучше оставить на другой день.",
         "aries": "Тёплый день для сердца. Скажи важным людям что они важны."},
    25: {"symbol": "🌘", "phase": "waning",
         "energy": "День восстановления и покоя.",
         "tips": "Отдыхай, спи, проводи время на природе. Перегрузки и тяжёлая еда сегодня лучше не лучшие друзья.",
         "aries": "Дай себе отдохнуть — это не слабость, это стратегия."},
    26: {"symbol": "🌘", "phase": "waning",
         "energy": "День завершений. Хорошее время закрыть незаконченное.",
         "tips": "Завершай проекты, прощай обиды, расставайся с ненужным. Новые крупные начинания лучше отложить до новолуния.",
         "aries": "Что ты давно откладывал закрыть? Сегодня хороший день для этого."},
    27: {"symbol": "🌘", "phase": "waning",
         "energy": "День очищения. Отпускай лишнее.",
         "tips": "Убирайся, делай детокс, работай с тем что накопилось. Накапливать новое сегодня не лучшая идея.",
         "aries": "Очисти пространство — физическое и ментальное. Освободи место для нового."},
    28: {"symbol": "🌑", "phase": "new",
         "energy": "День тишины перед новым циклом.",
         "tips": "Занимайся тихими делами, планируй, отдыхай. Важные решения лучше принять после новолуния.",
         "aries": "Накапливай силы — скоро новолуние и новый старт."},
    29: {"symbol": "🌑", "phase": "new",
         "energy": "Предпоследний день цикла. Энергия на минимуме.",
         "tips": "Только рутина, отдых и тихие дела. Сделки, операции и важные начинания лучше отложить — завтра новолуние.",
         "aries": "Переживи этот день спокойно. Не форсируй. Завтра всё изменится."},
    30: {"symbol": "🌑", "phase": "new",
         "energy": "Завершение цикла. Тишина перед рождением нового.",
         "tips": "Медитируй, благодари за прошедший месяц, ешь легко. Сегодня хорошо подводить итоги а не начинать.",
         "aries": "Подведи итог месяца. Что получил? Что отпустил? Завтра всё начнётся заново."},
}

PHASE_NAMES = {
    "new":    "🌑 Новолуние",
    "waxing": "🌒 Растущая луна",
    "full":   "🌕 Полнолуние",
    "waning": "🌘 Убывающая луна",
}

PHASE_ENERGY = {
    "new":    "Вдох · Планирование · Тишина",
    "waxing": "Действие · Накопление · Рост",
    "full":   "Пик · Творчество · Осторожность",
    "waning": "Выдох · Завершение · Анализ",
}

MONTHS_RU = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "май": 5, "мая": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"shop": {}, "water": 0, "water_date": "", "energy_log": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_weekday():
    return datetime.now(LISBON).weekday()

def get_lunar_day(for_date=None):
    if for_date is None:
        dt = datetime.now(LISBON).replace(tzinfo=None)
    else:
        dt = datetime.combine(for_date, datetime.min.time())
    prev_new = ephem.previous_new_moon(dt)
    diff = dt - prev_new.datetime()
    return min(max(int(diff.total_seconds() / 86400) + 1, 1), 30)

def build_lunar_text(for_date=None):
    lunar_day = get_lunar_day(for_date)
    info = LUNAR_DAYS.get(lunar_day, LUNAR_DAYS[1])
    phase_name = PHASE_NAMES[info["phase"]]
    phase_energy = PHASE_ENERGY[info["phase"]]
    label = for_date.strftime("%d.%m.%Y") if for_date else datetime.now(LISBON).strftime("%d.%m.%Y")
    return (
        f"{info['symbol']} *{lunar_day}-й лунный день* | {label}\n"
        f"{phase_name} · {phase_energy}\n\n"
        f"*Энергия дня:*\n{info['energy']}\n\n"
        f"💡 *Совет:*\n{info['tips']}\n\n"
        f"♈ *Для тебя (Овен):*\n{info['aries']}"
    )

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

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Расписание", callback_data="cmd_today"),
         InlineKeyboardButton("🥗 Рацион", callback_data="cmd_meal")],
        [InlineKeyboardButton("💧 Вода", callback_data="cmd_water"),
         InlineKeyboardButton("🛒 Покупки", callback_data="cmd_shop")],
        [InlineKeyboardButton("🌙 Луна", callback_data="cmd_luna"),
         InlineKeyboardButton("📊 Паттерны", callback_data="cmd_patterns")],
    ])

def energy_keyboard(prefix):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(str(i), callback_data=f"{prefix}_{i}") for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=f"{prefix}_{i}") for i in range(6, 11)],
    ])

def save_energy(kind, score):
    data = load_data()
    today = datetime.now(LISBON).strftime("%Y-%m-%d")
    lunar_day = get_lunar_day()
    info = LUNAR_DAYS.get(lunar_day, LUNAR_DAYS[1])
    log = data.get("energy_log", [])
    entry = next((e for e in log if e["date"] == today), None)
    if entry is None:
        entry = {"date": today, "lunar_day": lunar_day, "phase": info["phase"]}
        log.append(entry)
    entry[kind] = score
    data["energy_log"] = log
    save_data(data)

def build_patterns_text():
    data = load_data()
    log = data.get("energy_log", [])
    if len(log) < 7:
        days_left = 7 - len(log)
        return (
            f"📊 *Твои паттерны*\n\n"
            f"Данных пока мало — нужно минимум 7 дней оценок.\n"
            f"Осталось собрать: *{days_left} дней*\n\n"
            f"Оценивай энергию каждое утро и вечер — и через пару лунных циклов увидишь свои личные закономерности."
        )

    phase_scores = {"new": [], "waxing": [], "full": [], "waning": []}
    morning_scores = []
    evening_scores = []

    for e in log:
        phase = e.get("phase")
        if phase in phase_scores:
            if "morning" in e:
                phase_scores[phase].append(e["morning"])
                morning_scores.append(e["morning"])
            if "evening" in e:
                phase_scores[phase].append(e["evening"])
                evening_scores.append(e["evening"])

    text = f"📊 *Твои паттерны* (на основе {len(log)} дней)\n\n"

    phase_avgs = {}
    for phase, scores in phase_scores.items():
        if scores:
            avg = sum(scores) / len(scores)
            phase_avgs[phase] = avg

    if phase_avgs:
        best = max(phase_avgs, key=phase_avgs.get)
        worst = min(phase_avgs, key=phase_avgs.get)
        text += "*Энергия по фазам луны:*\n"
        for phase, avg in sorted(phase_avgs.items(), key=lambda x: -x[1]):
            bar = "⭐" * round(avg / 2)
            text += f"{PHASE_NAMES[phase]}: *{avg:.1f}/10* {bar}\n"
        text += f"\n✨ Твой лучший период: {PHASE_NAMES[best]}\n"
        if len(phase_avgs) > 1:
            text += f"😴 Период для отдыха: {PHASE_NAMES[worst]}\n"

    if morning_scores and evening_scores:
        text += f"\n*Среднее утро:* {sum(morning_scores)/len(morning_scores):.1f}/10\n"
        text += f"*Среднее вечер:* {sum(evening_scores)/len(evening_scores):.1f}/10\n"

    if len(log) < 60:
        text += f"\n_Для полной картины нужно ~60 дней. Собрано: {len(log)}_"

    return text

def build_meal_text(meal_type, d=None):
    if d is None:
        d = get_weekday()
    is_pilates = d in [0, 4]
    if meal_type == "breakfast":
        if is_pilates:
            return "🍳 *Завтрак через 15 минут* (12:00)\nПервый приём после пилатеса!\n\nБелок: лосось 150г / треска 200г / 3 яйца\nУглеводы: рис 150г / батат\nОвощи + масло + фрукт · ~600 ккал"
        return "🌅 *Завтрак через 15 минут* (6:30)\nБелок: лосось 120г / треска 150г / 3 яйца\nУглеводы: рис/батат 150г\nОвощи + фрукт · ~500 ккал"
    elif meal_type == "snack":
        return "🍎 *Перекус через 15 минут* (~11:00)\n1 фрукт + орехи / йогурт · ~200 ккал"
    elif meal_type == "lunch":
        if is_pilates:
            return "🍽️ *Обед через 15 минут* (15:00)\nБелок: треска / тунец 200г\nУглеводы: рис 100г / батат\nОвощи + моцарелла · ~600 ккал"
        return "🍽️ *Обед через 15 минут* (14:30)\nБелок: рыба 200г / 3 яйца\nУглеводы: 100г риса / батат\nОвощи + масло + фрукт · ~600 ккал"
    elif meal_type == "dinner":
        return "🌙 *Ужин через 15 минут* (19:00)\nБелок: рыба / яйца\nМного овощей, минимум углеводов · ~600 ккал"
    return ""

def build_full_meal_text(d=None):
    if d is None:
        d = get_weekday()
    is_pilates = d in [0, 4]
    if d == 6:
        return "😴 Воскресенье — ешь что хочешь!\n\n💧 Не забывай про воду — 3л в день!"
    elif is_pilates:
        return (
            "🧘 *День пилатеса* — натощак до занятия!\n\n"
            "🍳 *12:00* (~600 ккал)\nЛосось 150г / треска 200г / 3 яйца\nРис 150г / батат + овощи + фрукт\n\n"
            "🍽️ *15:00* (~600 ккал)\nТреска / тунец 200г\nРис 100г / батат + овощи + моцарелла\n\n"
            "🌙 *19:00* (~600 ккал)\nРыба / яйца + много овощей\n\n💧 Цель: 3л воды"
        )
    return (
        "🌅 *Завтрак* 6:30 (~500 ккал)\nЛосось 120г / треска 150г / 3 яйца\nРис/батат 150г + овощи + фрукт\n\n"
        "🍎 *Перекус* ~11:00 (~200 ккал)\nФрукт + орехи / йогурт\n\n"
        "🍽️ *Обед* 14:30 (~600 ккал)\nРыба 200г / 3 яйца\n100г риса / батат + овощи + фрукт\n\n"
        "🌙 *Ужин* 19:00 (~600 ккал)\nРыба / яйца + много овощей\n\n💧 Цель: 3л воды"
    )

# --- Фоновые задачи ---

async def job_calendar_check(context):
    if not CALENDAR_URL or not CHAT_ID:
        return
    try:
        now = datetime.now(LISBON)
        response = requests.get(CALENDAR_URL, timeout=10)
        cal = Calendar.from_ical(response.content)
        events = recurring_ical_events.of(cal).between(now + timedelta(minutes=14), now + timedelta(minutes=16))

        # Дедупликация — не слать одно событие дважды
        sent = context.bot_data.get("sent_notifications", {})
        # Чистим старые записи (старше 2 часов)
        sent = {k: v for k, v in sent.items() if (now - datetime.fromisoformat(v)).total_seconds() < 7200}

        for event in events:
            summary = str(event.get("SUMMARY", "Событие"))
            dtstart = event.get("DTSTART").dt
            if not hasattr(dtstart, 'hour'):
                continue
            if dtstart.tzinfo:
                dtstart = dtstart.astimezone(LISBON)
            # Ключ = название + время начала
            key = f"{summary}_{dtstart.strftime('%Y-%m-%d_%H:%M')}"
            if key in sent:
                continue
            sent[key] = now.isoformat()
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"⏰ Через 15 минут: *{summary}*\n🕐 {dtstart.strftime('%H:%M')}",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )

        context.bot_data["sent_notifications"] = sent
    except Exception as e:
        print(f"Ошибка календаря: {e}")

async def job_luna_morning(context):
    """Утреннее сообщение в 6:00 — луна + оценка энергии при пробуждении"""
    if not CHAT_ID:
        return
    lunar_day = get_lunar_day()
    info = LUNAR_DAYS.get(lunar_day, LUNAR_DAYS[1])
    phase_name = PHASE_NAMES[info["phase"]]
    phase_energy = PHASE_ENERGY[info["phase"]]
    now = datetime.now(LISBON)
    text = (
        f"☀️ *Доброе утро, Den! {now.strftime('%d.%m')}*\n\n"
        f"{info['symbol']} *{lunar_day}-й лунный день*\n"
        f"{phase_name} · {phase_energy}\n\n"
        f"{info['energy']}\n\n"
        f"💡 {info['tips']}\n\n"
        f"♈ {info['aries']}\n\n"
        f"*Как проснулся? Оцени энергию:*"
    )
    await context.bot.send_message(
        chat_id=CHAT_ID, text=text,
        parse_mode="Markdown",
        reply_markup=energy_keyboard("morning")
    )

async def job_evening_checkin(context):
    """Вечерний чек-ин в 21:00"""
    if not CHAT_ID:
        return
    lunar_day = get_lunar_day()
    info = LUNAR_DAYS.get(lunar_day, LUNAR_DAYS[1])
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"🌙 *Как прошёл день, Den?*\n\n{info['symbol']} {lunar_day}-й лунный день\n\nОцени итог дня:",
        parse_mode="Markdown",
        reply_markup=energy_keyboard("evening")
    )

async def job_water_reminder(context):
    if not CHAT_ID or get_weekday() == 6:
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
    await context.bot.send_message(chat_id=CHAT_ID, text=build_meal_text("breakfast"), parse_mode="Markdown", reply_markup=main_keyboard())

async def job_meal_snack(context):
    if not CHAT_ID:
        return
    if SCHEDULE[get_weekday()]["gym"]:
        await context.bot.send_message(chat_id=CHAT_ID, text=build_meal_text("snack"), parse_mode="Markdown", reply_markup=main_keyboard())

async def job_meal_pilates_breakfast(context):
    if not CHAT_ID:
        return
    if SCHEDULE[get_weekday()]["pilates"]:
        await context.bot.send_message(chat_id=CHAT_ID, text=build_meal_text("breakfast"), parse_mode="Markdown", reply_markup=main_keyboard())

async def job_meal_lunch(context):
    if not CHAT_ID:
        return
    if get_weekday() not in [5, 6]:
        await context.bot.send_message(chat_id=CHAT_ID, text=build_meal_text("lunch"), parse_mode="Markdown", reply_markup=main_keyboard())

async def job_meal_dinner(context):
    if not CHAT_ID:
        return
    if get_weekday() != 6:
        await context.bot.send_message(chat_id=CHAT_ID, text=build_meal_text("dinner"), parse_mode="Markdown", reply_markup=main_keyboard())

# --- Команды ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет, Den!\n\n"
        "📅 /today — расписание\n"
        "🥗 /meal — рацион\n"
        "🛒 /shop — покупки\n"
        "💧 /water — трекер воды\n"
        "🌙 /luna — лунный день\n"
        "📊 /patterns — твои паттерны\n"
        "📊 /report — отчёт дня\n\n"
        "Напиши дату — проверю по лунному календарю.\nПример: _планирую встречу на 15 июля_",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = get_weekday()
    day = SCHEDULE[d]
    now = datetime.now(LISBON)
    text = f"📅 *{day['name']}, {now.strftime('%d.%m')}* {day['emoji']}\n\n"
    if d == 6:
        text += "😴 Воскресенье — полный отдых!"
    elif day["pilates"]:
        text += "🌅 *6:30* — Подъём\n🧘 *9:00–12:00* — Пилатес\n🍳 *12:00* — Завтрак\n⚙️ *12:45–18:00* — Работа\n🌙 *19:00* — Ужин\n📚 *21:00* — Чтение"
    elif d == 5:
        text += "🌿 Свободный день\n📚 *21:00* — Чтение"
    else:
        text += "🌅 *6:30* — Подъём\n🍳 *6:30* — Завтрак\n⚙️ *7:00–13:00* — Работа\n🏋️ *13:00* — Зал\n🍽️ *14:30* — Обед\n⚙️ *15:15–18:00* — Работа\n🌙 *19:00* — Ужин\n📚 *21:00* — Чтение"
    text += "\n\n💧 Цель: 3л воды"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def cmd_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_full_meal_text(), parse_mode="Markdown", reply_markup=main_keyboard())

async def cmd_luna(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = build_lunar_text() + "\n\n*Оцени сегодняшнюю энергию:*"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=energy_keyboard("morning"))

async def cmd_patterns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(build_patterns_text(), parse_mode="Markdown", reply_markup=main_keyboard())

def shop_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Мой список", callback_data="shop_mylist"),
         InlineKeyboardButton("📋 Полный список", callback_data="shop_full")],
        [InlineKeyboardButton("🗑 Сбросить всё", callback_data="shop_reset"),
         InlineKeyboardButton("◀️ Меню", callback_data="cmd_menu")],
    ])

def build_shop_mylist(data):
    shop = data.get("shop", {})
    needed = [i for i in SHOP_ITEMS if shop.get(i["id"]) == "needed"]
    if not needed:
        return "✅ Список пуст — отметь нужное в полном списке", InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Полный список", callback_data="shop_full")],
            [InlineKeyboardButton("◀️ Меню", callback_data="cmd_menu")],
        ])
    total = sum(i["price"] for i in needed)
    text = f"🛒 *Мой список* ({len(needed)} позиций):\n\n"
    rows = []
    for item in needed:
        text += f"🟡 {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
        rows.append([InlineKeyboardButton(f"✅ Купил: {item['name']}", callback_data=f"bought_{item['id']}")])
    text += f"\n💰 *Итого: {total:.2f}€*"
    rows.append([InlineKeyboardButton("📋 Полный список", callback_data="shop_full"),
                 InlineKeyboardButton("◀️ Меню", callback_data="cmd_menu")])
    return text, InlineKeyboardMarkup(rows)

def build_shop_full(data):
    shop = data.get("shop", {})
    text = "📋 *Полный список* (нажми чтобы отметить):\n\n"
    rows = []
    for item in SHOP_ITEMS:
        status = shop.get(item["id"], "none")
        icon = "✅" if status == "done" else "🟡" if status == "needed" else "⬜"
        text += f"{icon} {item['name']} — {item['qty']} ({item['price']:.2f}€)\n"
        label = f"{icon} {item['name']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"shop_toggle_{item['id']}")])
    rows.append([InlineKeyboardButton("🛒 Мой список", callback_data="shop_mylist"),
                 InlineKeyboardButton("◀️ Меню", callback_data="cmd_menu")])
    return text, InlineKeyboardMarkup(rows)

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    shop = data.get("shop", {})
    needed_count = sum(1 for i in SHOP_ITEMS if shop.get(i["id"]) == "needed")
    done_count = sum(1 for i in SHOP_ITEMS if shop.get(i["id"]) == "done")
    text = (
        f"🛒 *Список покупок*\n\n"
        f"🟡 Нужно купить: {needed_count}\n"
        f"✅ Куплено: {done_count}\n\n"
        f"В *полном списке* нажимай на товары чтобы отметить нужное 🟡\n"
        f"В *моём списке* нажимай ✅ когда купил"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=shop_main_keyboard())

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
        [InlineKeyboardButton("Сбросить", callback_data="water_reset"),
         InlineKeyboardButton("◀️ Меню", callback_data="cmd_menu")],
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
        f"{water_ok} Вода: {liters:.2f}л / 3л\n\nКак прошёл день? Напиши 💪",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

def water_tracker_text_and_keyboard(glasses):
    liters = glasses * 0.25
    goal = 12
    bar = "💧" * glasses + "⬜" * max(0, goal - glasses)
    pct = int(liters / 3.0 * 100)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("+ 250мл", callback_data="water_add"),
         InlineKeyboardButton("- 250мл", callback_data="water_remove")],
        [InlineKeyboardButton("Сбросить", callback_data="water_reset"),
         InlineKeyboardButton("◀️ Меню", callback_data="cmd_menu")],
    ])
    text = f"💧 *Вода сегодня*\n\n{bar}\n\nВыпито: *{liters:.2f}л* из 3л ({pct}%)\nСтаканов: {glasses} из {goal}"
    return text, keyboard

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    today = datetime.now(LISBON).strftime("%Y-%m-%d")
    cb = query.data

    # Оценка энергии утром
    if cb.startswith("morning_"):
        score = int(cb.split("_")[1])
        save_energy("morning", score)
        await query.edit_message_text(
            query.message.text.split("\n\n*Как проснулся")[0] +
            f"\n\n✅ *Утренняя энергия записана: {score}/10*\nХорошего дня!",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

    # Оценка энергии вечером
    elif cb.startswith("evening_"):
        score = int(cb.split("_")[1])
        save_energy("evening", score)
        await query.edit_message_text(
            f"🌙 *Итог дня записан: {score}/10*\n\nСпокойной ночи, Den! 😴",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

    # Меню
    elif cb == "cmd_menu":
        await query.edit_message_text(
            "Выбери раздел:", reply_markup=main_keyboard()
        )

    elif cb == "cmd_today":
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
        text = build_lunar_text() + "\n\n*Оцени сегодняшнюю энергию:*"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=energy_keyboard("morning"))

    elif cb == "cmd_patterns":
        await query.edit_message_text(build_patterns_text(), parse_mode="Markdown", reply_markup=main_keyboard())

    elif cb == "cmd_report":
        glasses = data.get("water", 0) if data.get("water_date") == today else 0
        liters = glasses * 0.25
        water_ok = "✅" if liters >= 3 else "⚠️"
        await query.edit_message_text(
            f"📊 *Отчёт за {datetime.now(LISBON).strftime('%d.%m')}*\n\n{water_ok} Вода: {liters:.2f}л / 3л\n\nКак прошёл день? Напиши 💪",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

    elif cb == "cmd_water":
        if data.get("water_date") != today:
            data["water"] = 0
            data["water_date"] = today
            save_data(data)
        text, keyboard = water_tracker_text_and_keyboard(data.get("water", 0))
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif cb == "cmd_shop":
        shop = data.get("shop", {})
        needed_count = sum(1 for i in SHOP_ITEMS if shop.get(i["id"]) == "needed")
        done_count = sum(1 for i in SHOP_ITEMS if shop.get(i["id"]) == "done")
        text = (
            f"🛒 *Список покупок*\n\n"
            f"🟡 Нужно купить: {needed_count}\n"
            f"✅ Куплено: {done_count}\n\n"
            f"В *полном списке* нажимай на товары чтобы отметить нужное 🟡\n"
            f"В *моём списке* нажимай ✅ когда купил"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=shop_main_keyboard())

    elif cb == "shop_mylist":
        text, keyboard = build_shop_mylist(data)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif cb == "shop_full":
        text, keyboard = build_shop_full(data)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif cb.startswith("shop_toggle_"):
        item_id = cb.replace("shop_toggle_", "")
        current = data.get("shop", {}).get(item_id, "none")
        # Цикл: none → needed → done → none
        next_status = {"none": "needed", "needed": "done", "done": "none"}
        if "shop" not in data:
            data["shop"] = {}
        data["shop"][item_id] = next_status.get(current, "needed")
        save_data(data)
        text, keyboard = build_shop_full(data)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

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
        text, keyboard = water_tracker_text_and_keyboard(data["water"])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif cb.startswith("bought_"):
        item_id = cb.replace("bought_", "")
        if "shop" not in data:
            data["shop"] = {}
        data["shop"][item_id] = "done"
        save_data(data)
        text, keyboard = build_shop_mylist(data)
        if not any(i for i in SHOP_ITEMS if data["shop"].get(i["id"]) == "needed"):
            await query.edit_message_text("✅ Всё куплено! Молодец 🎉", reply_markup=shop_main_keyboard())
        else:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif cb == "shop_reset":
        data["shop"] = {}
        save_data(data)
        await query.edit_message_text("✅ Список сброшен!", reply_markup=shop_main_keyboard())

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    parsed_date = parse_russian_date(text)
    if parsed_date:
        lunar_day = get_lunar_day(parsed_date)
        info = LUNAR_DAYS.get(lunar_day, LUNAR_DAYS[1])
        phase_name = PHASE_NAMES[info["phase"]]
        phase_energy = PHASE_ENERGY[info["phase"]]
        reply = (
            f"🔍 *Проверка даты: {parsed_date.strftime('%d.%m.%Y')}*\n\n"
            f"{info['symbol']} *{lunar_day}-й лунный день*\n"
            f"{phase_name} · {phase_energy}\n\n"
            f"{info['energy']}\n\n"
            f"💡 {info['tips']}\n\n"
            f"♈ {info['aries']}"
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
    elif any(w in tl for w in ["луна", "лунный"]):
        await cmd_luna(update, context)
    elif any(w in tl for w in ["паттерн", "статистик", "аналитик"]):
        await cmd_patterns(update, context)
    else:
        await update.message.reply_text(
            "Напиши дату — проверю по лунному календарю.\nПример: _планирую встречу на 15 июля_",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

async def post_init(app):
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("today", "Расписание на сегодня"),
        BotCommand("meal", "Рацион на сегодня"),
        BotCommand("water", "Трекер воды"),
        BotCommand("luna", "Лунный день"),
        BotCommand("patterns", "Мои паттерны энергии"),
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
    app.add_handler(CommandHandler("patterns", cmd_patterns))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("water", cmd_water))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    jq = app.job_queue

    # Google Calendar — каждую минуту
    jq.run_repeating(job_calendar_check, interval=60, first=10)

    # Утро 6:00 — луна + оценка энергии
    jq.run_daily(job_luna_morning, time=dtime(hour=6, minute=0, tzinfo=LISBON))

    # Вечер 21:00 — оценка дня
    jq.run_daily(job_evening_checkin, time=dtime(hour=21, minute=0, tzinfo=LISBON))

    # Вода — 12 раз в день
    for h, m in [(6,30),(7,30),(8,30),(9,30),(10,30),(11,30),(13,0),(14,30),(16,0),(17,30),(19,0),(20,30)]:
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
