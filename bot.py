import os
import base64
import json
import gspread
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ROMAN_ID = 148945798

MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["🔎 Поиск поставщика", "🏭 Инспекция фабрики"],
    ["🚚 Посчитать доставку", "🎨 Брендирование"],
    ["💬 Консультация", "🏠 В меню"]
], resize_keyboard=True, is_persistent=True)

SKIP_STEPS = {
    "supplier": [1, 4, 5, 6],
    "inspection": [2, 4],
    "delivery": [8],
    "branding": [],
    "consultation": []
}

SUPPLIER_QUESTIONS = [
    "1️⃣ Опишите товар подробно (название, характеристики):",
    "2️⃣ Пришлите фото товара (можно несколько):",
    "3️⃣ Какое количество нужно?",
    "4️⃣ Какой бюджет на закупку?",
    "5️⃣ Доп. требования к товару? (можно голосовым)",
    "6️⃣ Ссылка на похожий товар (Alibaba, 1688)?",
    "7️⃣ Нужны доп. услуги? (доставка, проверка, брендирование)",
    "8️⃣ Ваши контакты (имя + телефон или Telegram):"
]

INSPECTION_QUESTIONS = [
    "1️⃣ Город где находится производство:",
    "2️⃣ ТЗ на проверку — цель, нюансы, вопросы поставщику (можно голосовым):",
    "3️⃣ Вид отчёта — фото / видео / комментарии?",
    "4️⃣ Срок — до какого числа нужна проверка?",
    "5️⃣ Нужны доп. услуги?",
    "6️⃣ Ваши контакты (имя + телефон или Telegram):"
]

DELIVERY_QUESTIONS = [
    "1️⃣ Откуда везём? (город в Китае)",
    "2️⃣ Куда везём? (город в России)",
    "3️⃣ Какой товар?",
    "4️⃣ Количество мест (коробок, паллет):",
    "5️⃣ Нужна доп. упаковка или страховка?",
    "6️⃣ Объём груза (м³):",
    "7️⃣ Вес груза (кг):",
    "8️⃣ Срочность — до какого числа нужен груз?",
    "9️⃣ Нужны доп. услуги?",
    "🔟 Ваши контакты (имя + телефон или Telegram):"
]

BRANDING_QUESTIONS = [
    "1️⃣ Опишите задачу (логотип, упаковка, этикетка):",
    "2️⃣ Референсы — фото или ссылки:",
    "3️⃣ Количество товара для брендирования:",
    "4️⃣ Срок — до какого числа нужно?",
    "5️⃣ Ваши контакты (имя + телефон или Telegram):"
]

CONSULTATION_QUESTIONS = [
    "1️⃣ Опишите ваш запрос (можно голосовым):",
    "2️⃣ Ваш уровень опыта в работе с Китаем:",
    "3️⃣ Ваши контакты (имя + телефон или Telegram):"
]

SECTION_NAMES = {
    "supplier": "🔎 Поиск поставщика",
    "inspection": "🏭 Инспекция фабрики",
    "delivery": "🚚 Доставка товара",
    "branding": "🎨 Брендирование",
    "consultation": "💬 Консультация"
}

QUESTIONS_MAP = {
    "supplier": SUPPLIER_QUESTIONS,
    "inspection": INSPECTION_QUESTIONS,
    "delivery": DELIVERY_QUESTIONS,
    "branding": BRANDING_QUESTIONS,
    "consultation": CONSULTATION_QUESTIONS
}

MENU_ROW = ["🏠 В меню"]
SKIP_ROW = ["⏭ Пропустить", "🏠 В меню"]
LEVEL_ROW = ["🌱 Новичок", "📈 Опытный", "🏆 Мастер"]

def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    creds_json = base64.b64decode(creds_b64).decode("utf-8")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("Заявки бот").sheet1
    return sheet

def get_keyboard_for_step(section, step):
    skippable = SKIP_STEPS.get(section, [])
    if section == "consultation" and step == 1:
        return ReplyKeyboardMarkup(
            [LEVEL_ROW, MENU_ROW], resize_keyboard=True, is_persistent=True
        )
    if step in skippable:
        return ReplyKeyboardMarkup(
            [SKIP_ROW], resize_keyboard=True, is_persistent=True
        )
    return ReplyKeyboardMarkup(
        [MENU_ROW], resize_keyboard=True, is_persistent=True
    )

async def ask_next_question(update, context, section):
    questions = QUESTIONS_MAP.get(section, [])
    step = context.user_data.get("step", 0)
    if step < len(questions):
        keyboard = get_keyboard_for_step(section, step)
        await update.message.reply_text(questions[step], reply_markup=keyboard)
    else:
        await finish_section(update, context, section)

async def send_collected_data(context, user, section_key, answers):
    section_name = SECTION_NAMES.get(section_key, section_key)
    questions = QUESTIONS_MAP.get(section_key, [])

    await context.bot.send_message(
        chat_id=ROMAN_ID,
        text=f"📥 Новая заявка!\n"
             f"Раздел: {section_name}\n"
             f"От: {user.first_name} @{user.username or 'нет'}\n"
             f"ID: {user.id}"
    )

    try:
        sheet = get_sheet()
        row = [
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            section_name,
            user.first_name,
            f"@{user.username}" if user.username else "нет",
            str(user.id)
        ]
        for answer in answers:
            row.append(answer)
        sheet.append_row(row)
    except Exception as e:
        import traceback
        print(f"Ошибка записи в таблицу: {e}")
        print(traceback.format_exc())
        await context.bot.send_message(
            chat_id=ROMAN_ID,
            text=f"Ошибка таблицы: {e}"
        )

async def finish_section(update, context, section_key):
    answers = context.user_data.get("answers", [])
    await send_collected_data(context, update.message.from_user, section_key, answers)
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Заявка принята!\n\n"
        "Роман свяжется с вами в течение часа.\n"
        "Если срочно — напишите напрямую: @Akhmedzyanov_Roman",
        reply_markup=MAIN_KEYBOARD
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Мой Telegram канал", url="https://t.me/Akhmedzyanov_ru")],
        [InlineKeyboardButton("📖 Подробнее обо мне", url="https://taplink.cc/akhmedzyanov")]
    ])
    await update.message.reply_text(
        "Я — Роман Ахмедзянов.\n"
        "Ваш человек в Китае 🇨🇳\n\n"
        "Живу и работаю в Иу.\n"
        "Более 10 лет в международной торговле и ВЭД.\n"
        "Помогаю российскому бизнесу находить поставщиков, "
        "проверять производство, организовывать доставку "
        "и сопровождать сделки под ключ.\n\n"
        "Выберите нужную услугу 👇",
        reply_markup=inline_kb
    )
    await update.message.reply_text("Меню услуг:", reply_markup=MAIN_KEYBOARD)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "consult":
        context.user_data.update({"section": "consultation", "step": 0, "answers": []})
        await query.message.reply_text(
            "💬 Консультация\n\n"
            "Первые 15 минут — бесплатно.\n"
            "Платная консультация (1 час) — 8 000 руб\n\n"
            "Ответьте на несколько вопросов 👇"
        )
        keyboard = get_keyboard_for_step("consultation", 0)
        await query.message.reply_text(CONSULTATION_QUESTIONS[0], reply_markup=keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    if text == "🏠 В меню":
        context.user_data.clear()
        await update.message.reply_text("Вы вернулись в главное меню 👇", reply_markup=MAIN_KEYBOARD)
        return

    section = context.user_data.get("section")
    if section:
        step = context.user_data.get("step", 0)
        answers = context.user_data.get("answers", [])
        answers.append("—" if text == "⏭ Пропустить" else text)
        context.user_data["answers"] = answers
        context.user_data["step"] = step + 1
        await ask_next_question(update, context, section)
        return

    if text == "🔎 Поиск поставщика":
        context.user_data.update({"section": "supplier", "step": 0, "answers": []})
        await update.message.reply_text("🔎 Поиск поставщика в Китае\n\nПодробнее: @Akhmedzyanov_ru\n\nФото и голосовые принимаются 👇")
        await ask_next_question(update, context, "supplier")

    elif text == "🏭 Инспекция фабрики":
        context.user_data.update({"section": "inspection", "step": 0, "answers": []})
        await update.message.reply_text("🏭 Инспекция фабрики\n\nПодробнее: @Akhmedzyanov_ru\n\nОтвечайте на вопросы по очереди 👇")
        await ask_next_question(update, context, "inspection")

    elif text == "🚚 Посчитать доставку":
        context.user_data.update({"section": "delivery", "step": 0, "answers": []})
        await update.message.reply_text("🚚 Посчитать доставку из Китая\n\nПодробнее: @Akhmedzyanov_ru\n\nОтвечайте на вопросы по очереди 👇")
        await ask_next_question(update, context, "delivery")

    elif text == "🎨 Брендирование":
        context.user_data.update({"section": "branding", "step": 0, "answers": []})
        await update.message.reply_text("🎨 Брендирование товара\n\nПроверка и брендирование выполняются вместе с другими услугами.\n\nРасскажите о вашей задаче 👇")
        await ask_next_question(update, context, "branding")

    elif text == "💬 Консультация":
        context.user_data.update({"section": "consultation", "step": 0, "answers": []})
        await update.message.reply_text("💬 Консультация\n\nПервые 15 минут — бесплатно.\nПлатная консультация (1 час) — 8 000 руб\n\nОтветьте на несколько вопросов 👇")
        await ask_next_question(update, context, "consultation")

    else:
        await update.message.reply_text("Выберите раздел в меню 👇", reply_markup=MAIN_KEYBOARD)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    section = context.user_data.get("section")
    if section:
        step = context.user_data.get("step", 0)
        answers = context.user_data.get("answers", [])
        answers.append("[фото]")
        await context.bot.forward_message(
            chat_id=ROMAN_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        context.user_data["answers"] = answers
        context.user_data["step"] = step + 1
        await ask_next_question(update, context, section)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    section = context.user_data.get("section")
    if section:
        step = context.user_data.get("step", 0)
        answers = context.user_data.get("answers", [])
        answers.append("[голосовое]")
        await context.bot.forward_message(
            chat_id=ROMAN_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        context.user_data["answers"] = answers
        context.user_data["step"] = step + 1
        await ask_next_question(update, context, section)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
