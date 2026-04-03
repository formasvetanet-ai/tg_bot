"""
Тесты логики бота — запуск: python test_bot.py
Не требует Telegram, Railway или Claude API.
"""

import sys

# ──────────────────────────────────────────────
# Импортируем только то что не требует внешних сервисов
# ──────────────────────────────────────────────
from prompts import format_answers

SKIP_STEPS = {
    "supplier": [1, 3, 4, 5, 6, 8],
    "inspection": [2, 3, 6],
    "delivery": [3, 4, 7, 9],
    "branding": [4],
    "consultation": [2, 6]
}

SUPPLIER_QUESTIONS = [
    "1️⃣ Опишите товар подробно (название, характеристики):",
    "2️⃣ Пришлите фото товара (можно несколько):",
    "3️⃣ Какое количество нужно? (например: 500 штук, 1000 кг, 2 паллета)",
    "4️⃣ Какой бюджет на закупку? (если не знаете — пропустите)",
    "5️⃣ Доп. требования к товару?",
    "6️⃣ Ссылка на похожий товар (Alibaba, 1688)?",
    "7️⃣ Нужны доп. услуги? (доставка, проверка, брендирование)",
    "8️⃣ Ваше имя:",
    "9️⃣ Ваш email (на случай если Telegram будет недоступен):"
]

INSPECTION_QUESTIONS = [
    "1️⃣ Город где находится производство:",
    "2️⃣ ТЗ на проверку — цель, нюансы, вопросы поставщику:",
    "3️⃣ Вид отчёта — фото / видео / комментарии?",
    "4️⃣ Дата — Когда нужна проверка?",
    "5️⃣ Нужны доп. услуги?",
    "6️⃣ Ваше имя:",
    "7️⃣ Ваш email (на случай если Telegram будет недоступен):"
]

DELIVERY_QUESTIONS = [
    "1️⃣ Откуда везём? (страна/город):",
    "2️⃣ Куда везём? (страна/город):",
    "3️⃣ Какой товар?",
    "4️⃣ Количество мест (например: 10 коробок, 2 паллета):",
    "5️⃣ Нужна доп. упаковка или страховка? (да/нет)",
    "6️⃣ Объём груза в м³ (например: 1 или 2.5):",
    "7️⃣ Вес груза в кг (например: 200 или 500):",
    "8️⃣ Стоимость товара в USD (нужна для расчёта таможни).\nБез неё будет считаться только логистика. Если не знаете — пропустите:",
    "9️⃣ Ваше имя:",
    "🔟 Ваш email (на случай если Telegram будет недоступен):"
]

BRANDING_QUESTIONS = [
    "1️⃣ Опишите задачу (логотип, упаковка, этикетка, мерч):",
    "2️⃣ Референсы — фото или ссылки:",
    "3️⃣ Количество товара для брендирования (например: 1000 штук):",
    "4️⃣ Ваше имя:",
    "5️⃣ Ваш email (на случай если Telegram будет недоступен):"
]

CONSULTATION_QUESTIONS = [
    "1️⃣ Каков ваш статус?\n(Стартап / ИП или ООО / Корпоративный клиент / Самозанятый / Физлицо)",
    "2️⃣ С чем нужна помощь?\n(Поиск поставщика / Инспекция / Доставка / Брендирование / Таможня / Контроль качества / Проблема с поставкой / Другое)",
    "3️⃣ Что у вас уже есть?\n(ТЗ / Контакты поставщиков / КП / Данные по весу и габаритам / Бюджет / Пока ничего нет)",
    "4️⃣ Опишите ваш запрос подробно:",
    "5️⃣ Какой результат будет для вас идеальным?",
    "6️⃣ Ваше имя:",
    "7️⃣ Ваш email (на случай если Telegram будет недоступен):"
]

QUESTIONS_MAP = {
    "supplier": SUPPLIER_QUESTIONS,
    "inspection": INSPECTION_QUESTIONS,
    "delivery": DELIVERY_QUESTIONS,
    "branding": BRANDING_QUESTIONS,
    "consultation": CONSULTATION_QUESTIONS,
}

# ──────────────────────────────────────────────
PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  ✓  {name}")
        PASS += 1
    else:
        print(f"  ✗  {name}" + (f"\n       {detail}" if detail else ""))
        FAIL += 1

# ──────────────────────────────────────────────
# 1. Количество вопросов в каждом разделе
# ──────────────────────────────────────────────
print("\n[1] Количество вопросов в анкетах")

check("supplier — 9 вопросов",  len(SUPPLIER_QUESTIONS) == 9,  f"Найдено: {len(SUPPLIER_QUESTIONS)}")
check("inspection — 7 вопросов", len(INSPECTION_QUESTIONS) == 7, f"Найдено: {len(INSPECTION_QUESTIONS)}")
check("delivery — 10 вопросов",  len(DELIVERY_QUESTIONS) == 10,  f"Найдено: {len(DELIVERY_QUESTIONS)}")
check("branding — 5 вопросов",   len(BRANDING_QUESTIONS) == 5,   f"Найдено: {len(BRANDING_QUESTIONS)}")
check("consultation — 7 вопросов", len(CONSULTATION_QUESTIONS) == 7, f"Найдено: {len(CONSULTATION_QUESTIONS)}")

# ──────────────────────────────────────────────
# 2. SKIP_STEPS не выходят за пределы вопросов
# ──────────────────────────────────────────────
print("\n[2] SKIP_STEPS не выходят за границы вопросов")

for section, skips in SKIP_STEPS.items():
    q_count = len(QUESTIONS_MAP[section])
    bad = [s for s in skips if s >= q_count]
    check(
        f"{section}: шаги {skips} в пределах {q_count} вопросов",
        len(bad) == 0,
        f"Шаги за пределами: {bad}"
    )

# ──────────────────────────────────────────────
# 3. Текст вопросов не содержит ограничений "город в Китае" / "в России"
# ──────────────────────────────────────────────
print("\n[3] Вопросы доставки не содержат устаревших ограничений")

forbidden = ["город в Китае", "город в России", "в Китае", "в России"]
for q in DELIVERY_QUESTIONS:
    for f in forbidden:
        check(
            f"Нет '{f}' в: {q[:50]}",
            f not in q,
            f"Найдено запрещённое: '{f}'"
        )

# ──────────────────────────────────────────────
# 4. format_answers корректно собирает ответы
# ──────────────────────────────────────────────
print("\n[4] format_answers — корректная сборка ответов")

answers_delivery = ["Китай, Иу", "Россия, Москва", "Бандана", "10 коробок", "нет", "2.5", "150", "—", "Катя", "—"]
result = format_answers("delivery", answers_delivery, QUESTIONS_MAP)

check("Содержит откуда",    "Китай, Иу" in result,       f"Результат:\n{result}")
check("Содержит куда",      "Россия, Москва" in result,  f"Результат:\n{result}")
check("Содержит товар",     "Бандана" in result,         f"Результат:\n{result}")
check("Нет пустых строк",   "\n\n" not in result,        f"Результат:\n{result}")

answers_supplier = ["Искусственные цветы", "[фото]", "10000 кг", "—", "—", "—", "—", "Роман", "—"]
result2 = format_answers("supplier", answers_supplier, QUESTIONS_MAP)
check("supplier: содержит товар", "Искусственные цветы" in result2, f"Результат:\n{result2}")
check("supplier: содержит имя",   "Роман" in result2,               f"Результат:\n{result2}")

# ──────────────────────────────────────────────
# 5. Промпт содержит {answers} placeholder
# ──────────────────────────────────────────────
print("\n[5] Промпты содержат плейсхолдер {answers}")

from prompts import get_system_prompt

for section in ["supplier", "delivery", "inspection", "branding", "consultation"]:
    prompt = get_system_prompt(section)
    check(f"{section}: есть {{answers}}", "{answers}" in prompt)

# ──────────────────────────────────────────────
# 6. Промпты не содержат Markdown символов в инструкциях
# ──────────────────────────────────────────────
print("\n[6] Промпты запрещают Markdown (правило есть в тексте)")

for section in ["supplier", "delivery", "inspection", "branding", "consultation"]:
    prompt = get_system_prompt(section)
    check(
        f"{section}: упоминает запрет Markdown",
        "Markdown" in prompt or "markdown" in prompt
    )

# ──────────────────────────────────────────────
# Итог
# ──────────────────────────────────────────────
total = PASS + FAIL
print(f"\n{'='*40}")
print(f"Итого: {PASS}/{total} тестов прошло", end="")
if FAIL == 0:
    print(" ✓ Всё OK")
else:
    print(f"\n  Провалено: {FAIL}")
    sys.exit(1)
