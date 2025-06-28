import os
import json
import random
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Константы
NUM_TASKS = 12
VARIANTS_PER_TASK = 15
TASKS_DIR = 'tasks'
URLS_DIR = 'URLs'
DATA_FILE = 'bot_data.json'

# Приветствия
GREETING_INPUTS = [
    "привет", "здравствуй", "хай", "добрый день", "доброе утро",
    "добрый вечер", "приветствую", "салют", "здорово", "приветик",
    "хелло", "доброго времени суток", "йоу", "ку", "хэллоу"
]

GREETING_OUTPUTS = [
    "Привет! Чем могу помочь?",
    "Здравствуй! Готов к изучению математики?",
    "Доброго времени суток! Выбирай раздел:",
    "Приветствую! Задачки ждут тебя!",
    "Хай! Начнём подготовку к ЕГЭ?",
    "Рад тебя видеть! Запускаем тест?",
    "Салют! Загляни в справочные материалы!",
    "Здорово! Посмотрим результаты прошлых тестов?",
    "Привет-привет! Выбирай действие в меню ниже 👇",
    "Йоу! Готов к математическим подвигам?",
    "Добрый день! Задания уже ждут тебя!",
    "Хэллоу! Начнём с теории или практики?"
]

# Инициализация данных
if os.path.isfile(DATA_FILE):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {'sessions': {}}

async def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Загрузка заданий и ссылок
TASKS = []
for t in range(1, NUM_TASKS + 1):
    variants = []
    folder = os.path.join(TASKS_DIR, str(t))
    for v in range(1, VARIANTS_PER_TASK + 1):
        txt = os.path.join(folder, f"{v}.txt")
        png = os.path.join(folder, f"{v}.png")
        text, ans = None, None
        if os.path.isfile(txt):
            lines = open(txt, encoding='utf-8').read().splitlines()
            text = lines[0] if len(lines) >= 1 else None
            ans = lines[1] if len(lines) >= 2 else None
        photo = png if os.path.isfile(png) else None
        variants.append({'text': text, 'answer': ans, 'photo': photo})
    TASKS.append(variants)

# Главное меню
def main_menu():
    return ReplyKeyboardMarkup([
        ["Справочные материалы", "Тестовые материалы"],
        ["Результаты"]
    ], resize_keyboard=True)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для подготовки к ЕГЭ по профильной математике."
        "\nВыберите раздел:",
        reply_markup=main_menu()
    )

# Справочные материалы
async def ref_materials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите номер задания для справки (1-12) или 'Отмена':",
        reply_markup=ReplyKeyboardMarkup([[str(i) for i in range(1, NUM_TASKS+1)], ["Отмена"]], resize_keyboard=True)
    )
    context.user_data['awaiting_ref'] = True

async def handle_ref_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == 'отмена':
        context.user_data.pop('awaiting_ref', None)
        await update.message.reply_text("Отмена.", reply_markup=main_menu())
        return
    if text.isdigit() and 1 <= int(text) <= NUM_TASKS:
        path = os.path.join(URLS_DIR, f"{text}.txt")
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                await update.message.reply_text(f.read())
        else:
            await update.message.reply_text("Справочный файл не найден.")
    else:
        await update.message.reply_text("Неверный ввод. Введите номер задания или 'Отмена'.")
        return
    context.user_data.pop('awaiting_ref', None)
    await update.message.reply_text("Главное меню:", reply_markup=main_menu())

# Тестовые материалы
async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Тест начат. Введите 'Отмена' для выхода.")
    uid = str(update.effective_user.id)
    session = {'start': datetime.utcnow().isoformat(), 'answers': []}
    data['sessions'].setdefault(uid, []).append(session)
    context.user_data.update({'session': session, 'task_idx': 0, 'in_test': True})
    await send_question(update, context)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = context.user_data['task_idx']
    var = random.randint(1, VARIANTS_PER_TASK)
    q = TASKS[idx][var-1]
    context.user_data['current'] = {'task': idx+1, 'variant': var, 'correct': q['answer']}
    text = q['text'] or 'Условие отсутствует.'
    await update.message.reply_text(f"Задание {idx+1}, вариант {var}:\n{text}")
    if q['photo']:
        await update.message.reply_photo(open(q['photo'], 'rb'))

async def handle_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == 'отмена' and context.user_data.get('in_test'):
        context.user_data.clear()
        await update.message.reply_text("Тест отменён.", reply_markup=main_menu())
        return
    session = context.user_data.get('session')
    current = context.user_data.get('current')
    if not session or not current:
        return
    ans = text
    session['answers'].append({
        'task': current['task'], 'variant': current['variant'],
        'answer': ans, 'correct': current['correct']
    })
    context.user_data['task_idx'] = current['task']
    context.user_data.pop('current', None)
    if context.user_data['task_idx'] < NUM_TASKS:
        await send_question(update, context)
    else:
        context.user_data.pop('in_test', None)
        session['end'] = datetime.utcnow().isoformat()
        correct_count = sum(1 for a in session['answers'] if a['answer'] == a['correct'])
        session['score'] = f"{correct_count}/{NUM_TASKS}"
        await save_data()
        lines = [
            f"З{a['task']} в{a['variant']}: ваш {a['answer']} - факт {a['correct']} - {'OK' if a['answer']==a['correct'] else 'NO'}"
            for a in session['answers']
        ]
        await update.message.reply_text("Детальные результаты:\n" + "\n".join(lines))
        await update.message.reply_text(f"Общий результат: {session['score']}", reply_markup=main_menu())

# Просмотр результатов
async def show_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    sessions = data['sessions'].get(uid, [])
    if not sessions:
        await update.message.reply_text("Нет попыток.", reply_markup=main_menu())
        return
    buttons = [[str(i+1) for i in range(len(sessions))], ["Отмена"]]
    await update.message.reply_text("Выберите номер попытки для деталей или 'Отмена':",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    context.user_data['awaiting_session'] = True

async def handle_session_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == 'отмена':
        context.user_data.pop('awaiting_session', None)
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return
    if text.isdigit():
        idx = int(text)-1
        uid = str(update.effective_user.id)
        sessions = data['sessions'].get(uid, [])
        if 0 <= idx < len(sessions):
            sess = sessions[idx]
            lines = [
                f"З{a['task']} в{a['variant']}: ваш {a['answer']} - факт {a['correct']} - {'OK' if a['answer']==a['correct'] else 'NO'}"
                for a in sess['answers']
            ]
            await update.message.reply_text(f"Детали попытки #{text}:\n" + "\n".join(lines))
        else:
            await update.message.reply_text("Некорректный номер.")
            return
    else:
        await update.message.reply_text("Введите номер или 'Отмена'.")
        return
    context.user_data.pop('awaiting_session', None)
    await update.message.reply_text("Главное меню:", reply_markup=main_menu())

# Общий обработчик
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text in GREETING_INPUTS:
        response = random.choice(GREETING_OUTPUTS)
        await update.message.reply_text(response, reply_markup=main_menu())
        return

    if context.user_data.get('awaiting_ref'):
        await handle_ref_choice(update, context)
    elif context.user_data.get('awaiting_session'):
        await handle_session_choice(update, context)
    elif context.user_data.get('in_test'):
        await handle_test_answer(update, context)
    elif text == 'Справочные материалы':
        await ref_materials(update, context)
    elif text == 'Тестовые материалы':
        await start_test(update, context)
    elif text == 'Результаты':
        await show_sessions(update, context)
    else:
        await update.message.reply_text("Неизвестная команда. Выберите из меню.", reply_markup=main_menu())

# Запуск
if __name__ == '__main__':
    app = ApplicationBuilder().token('7708870604:AAHpJ8uZXw_-OzZS3wJTpyK-h4dEM_4IOOA').build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
