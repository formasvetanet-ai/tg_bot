import os
import base64
import json
import gspread
import anthropic
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from prompts import get_system_prompt, format_answers

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ROMAN_ID = 148945798
PROMO_MERCH_ID = 5084361079

MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["🔎 Поиск поставщика", "🏭 Инспекция фабрики"],
    ["🚚 Посчитать доставку", "🎨 Брендирование"],
    ["💬 Консультация", "🏠 В меню"]
], resize_keyboard=True, is_persistent=True)

SKIP_STEPS = {
    "supplier": [1, 3, 4, 5, 6],
    "inspection": [2, 3],
    "delivery": [3, 4],
    "branding": [],
    "consultation": [2]
}

NUMERIC_STEPS = {}

SUPPLIER_QUESTIONS = [
    "1️⃣ Опишите товар подробно (название, характеристики):",
    "2️⃣ Пришлите фото товара (можно несколько):",
    "3️⃣ Какое количество нужно? (например: 500 штук, 1000 кг, 2 паллета)",
    "4️⃣ Какой бюджет на закупку? (если не знаете — пропустите)",
    "5️⃣ Доп. требования к товару?",
    "6️⃣ Ссылка на похожий товар (Alibaba, 1688)?",
    "7️⃣ Нужны доп. услуги? (доставка, проверка, брендирование)",
    "8️⃣ Ваши контакты (имя + телефон или Telegram):"
]

INSPECTION_QUESTIONS = [
    "1️⃣ Город где находится производство:",
    "2️⃣ ТЗ на проверку — цель, нюансы, вопросы поставщику:",
    "3️⃣ Вид отчёта — фото / видео / комментарии?",
    "4️⃣ Дата — Когда нужна проверка?",
    "5️⃣ Нужны доп. услуги?",
    "6️⃣ Ваши контакты (имя + телефон или Telegram):"
]

DELIVERY_QUESTIONS = [
    "1️⃣ Откуда везём? (город в Китае)",
    "2️⃣ Куда везём? (город в России)",
    "3️⃣ Какой товар?",
    "4️⃣ Количество мест (например: 10 коробок, 2 паллета):",
    "5️⃣ Нужна доп. упаковка или страховка? (да/нет)",
    "6️⃣ Объём груза в м³ (например: 1 или 2.5):",
    "7️⃣ Вес груза в кг (например: 200 или 500):",
    "8️⃣ Ваши контакты (имя + телефон или Telegram):"
]

BRANDING_QUESTIONS = [
    "1️⃣ Опишите задачу (логотип, упаковка, этикетка, мерч):",
    "2️⃣ Референсы — фото или ссылки:",
    "3️⃣ Количество товара для брендирования (например: 1000 штук):",
    "4️⃣ Ваши контакты (имя + телефон или Telegram):"
]

CONSULTATION_QUESTIONS = [
    "1️⃣ Каков ваш статус?\n(Стартап / ИП или ООО / Корпоративный клиент / Самозанятый / Физлицо)",
    "2️⃣ С чем нужна помощь?\n(Поиск поставщика / Инспекция / Доставка / Брендирование / Таможня / Контроль качества / Проблема с поставкой / Другое)",
    "3️⃣ Что у вас уже есть?\n(ТЗ / Контакты поставщиков / КП / Данные по весу и габаритам / Бюджет / Пока ничего нет)",
    "4️⃣ Опишите ваш запрос подробно:",
    "5️⃣ Какой результат будет для вас идеальным?",
    "6️⃣ Ваши контакты (имя + телефон или Telegram):"
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
STATUS_ROW = [["🚀 Стартап", "💼 ИП/ООО"], ["🏢 Корпоративный", "👤 Самозанятый"], ["🙋 Физлицо"]]


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

    if section == "consultation" and step == 0:
        return ReplyKeyboardMarkup(
            STATUS_ROW + [MENU_ROW],
            resize_keyboard=True, is_persistent=True
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


async def get_ai_response(section_key, answers):
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        system_prompt = get_system_prompt(section_key)
        formatted = format_answers(section_key, answers, QUESTIONS_MAP)
        system_prompt = system_prompt.replace("{answers}", formatted)

        print(f"DEBUG SECTION: {section_key}")
        print(f"DEBUG ANSWERS: {formatted}")
        print(f"DEBUG PROMPT LENGTH: {len(system_prompt)}")
        print(f"DEBUG ANSWERS IN PROMPT: {formatted in system_prompt}")

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=system_prompt,
            messages=[
                {"role": "user", "content": "Проанализируй данные клиента и дай предварительный ответ."}
            ]
        )
        return message.content[0].text
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        import traceback
        print(traceback.format_exc())
        return None


async def send_collected_data(context, user, section_key, answers, ai_response=None):
    section_name = SECTION_NAMES.get(section_key, section_key)
    questions = QUESTIONS_MAP.get(section_key, [])

    await context.bot.send_message(
        chat_id=ROMAN_ID,
        text=f"📥 Новая заявка!\n"
             f"Раздел: {section_name}\n"
             f"От: {user.first_name} @{user.username or 'нет'}\n"
             f"ID: {user.id}"
    )

    if section_key == "branding":
        branding_text = f"🎨 Новый запрос на брендирование!\n\n"
        branding_text += f"От: {user.first_name} @{user.username or 'нет'}\n\n"
        for i, answer in enumerate(answers):
            if i < len(questions):
                q = questions[i].split(":")[0].strip()
                branding_text += f"{q}: {answer}\n"
        try:
            await context.bot.send_message(
                chat_id=PROMO_MERCH_ID,
                text=branding_text
            )
        except Exception as e:
            print(f"Ошибка отправки в promo_merch: {e}")
            await context.bot.send_message(
                chat_id=ROMAN_ID,
                text=f"⚠️ Не удалось отправить Кате. Перешли вручную:\n\n{branding_text}"
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
        if ai_response:
            row.append(ai_response)
        sheet.append_row(row)
    except Exception as e:
        import traceback
        print(f"Ошибка записи в таблицу: {e}")
        print(traceback.format_exc())
        await context.bot.send_message(
            chat_id=ROMAN_ID,
            text=f"⚠️ Ошибка таблицы: {e}"
        )


async def finish_section(update, context, section_key):
    answers = context.user_data.get("answers", [])

    await update.message.reply_text(
        "⏳ Анализирую ваш запрос...",
        reply_markup=ReplyKeyboardMarkup([MENU_ROW], resize_keyboard=True)
    )

    ai_response = await get_ai_response(section_key, answers)

    await send_collected_data(
        context,
        update.message.from_user,
        section_key,
        answers,
        ai_response
    )

    if ai_response:
        await update.message.reply_text(
            ai_response,
            reply_markup=MAIN_KEYBOARD
        )
    else:
        await update.message.reply_text(
            "✅ Заявка принята!\n\n"
            "Роман свяжется с вами в течение часа.\n"
            "Если срочно — напишите напрямую: @Akhmedzyanov_Roman",
            reply_markup=MAIN_KEYBOARD
        )

    context.user_data.clear()


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
        "⚠️ Работаю с оптовыми закупками и крупными проектами.\n\n"
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
        await update.message.reply_text(
            "Вы вернулись в главное меню 👇",
            reply_markup=MAIN_KEYBOARD
        )
        return

    section = context.user_data.get("section")
    if section:
        step = context.user_data.get("step", 0)
        answers = context.user_data.get("answers", [])

        if text == "⏭ Пропустить":
            answers.append("—")
            context.user_data["answers"] = answers
            context.user_data["step"] = step + 1
            await ask_next_question(update, context, section)
            return

        answers.append(text)
        context.user_data["answers"] = answers
        context.user_data["step"] = step + 1
        await ask_next_question(update, context, section)
        return

    if text == "🔎 Поиск поставщика":
        context.user_data.update({"section": "supplier", "step": 0, "answers": []})
        await update.message.reply_text(
            "🔎 Поиск поставщика в Китае\n\n"
            "Подробнее: @Akhmedzyanov_ru\n\n"
            "Фото принимаются 👇"
        )
        await ask_next_question(update, context, "supplier")

    elif text == "🏭 Инспекция фабрики":
        context.user_data.update({"section": "inspection", "step": 0, "answers": []})
        await update.message.reply_text(
            "🏭 Инспекция фабрики\n\n"
            "Подробнее: @Akhmedzyanov_ru\n\n"
            "Отвечайте на вопросы по очереди 👇"
        )
        await ask_next_question(update, context, "inspection")

    elif text == "🚚 Посчитать доставку":
        context.user_data.update({"section": "delivery", "step": 0, "answers": []})
        await update.message.reply_text(
            "🚚 Посчитать доставку из Китая\n\n"
            "Подробнее: @Akhmedzyanov_ru\n\n"
            "Отвечайте на вопросы по очереди 👇"
        )
        await ask_next_question(update, context, "delivery")

    elif text == "🎨 Брендирование":
        context.user_data.update({"section": "branding", "step": 0, "answers": []})
        await update.message.reply_text(
            "🎨 Брендирование товара\n\n"
            "Расскажите о вашей задаче 👇"
        )
        await ask_next_question(update, context, "branding")

    elif text == "💬 Консультация":
        context.user_data.update({"section": "consultation", "step": 0, "answers": []})
        await update.message.reply_text(
            "💬 Консультация\n\n"
            "Первые 15 минут — бесплатно.\n"
            "Платная консультация (1 час) — 8 000 руб\n\n"
            "Ответьте на несколько вопросов 👇"
        )
        await ask_next_question(update, context, "consultation")

    else:
        await update.message.reply_text(
            "Выберите раздел в меню 👇",
            reply_markup=MAIN_KEYBOARD
        )


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
    else:
        await update.message.reply_text(
            "Чтобы отправить фото — выберите нужную услугу в меню 👇",
            reply_markup=MAIN_KEYBOARD
        )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
