import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# === Настройки бота ===
BOT_TOKEN = '8157675439:AAEc3KeNuEo_rPdMe1hmIhwi4Kd6eXi2J9Y'  # Токен твоего бота
SHEET_ID = '1idTZnstCFEXQXsiMn5ADl-SvK8z8t1Tojc9lz2wVYFA'     # ID таблицы из ссылки
WORKSHEET_NAME = 'MERKEZI МИР'                                # Лист в таблице

# === Списки ===
EMPLOYEES = ["Дима", "Лена", "Дарья", "Вероника", "Алина", "Нико", "Эмиль", "Павел"]
CATEGORIES = ["Одноразка", "POD-Устройство", "Жидкость", "Картридж", "Испаритель", "Табак", "Напитки", "Угли", "АКБ"]
PAYMENT_TYPES = ["Терминал", "Наличка", "Перевод", "СБП"]

# === Переменные для работы с таблицей ===
PLAN_CELL = 'K2'
CASH_REGISTER_CELL = 'J2'
DATE_COLUMN = "Дата"
CASH_COLUMN = "Сумма"
PAYMENT_COLUMN = "Оплата"

# === Подключение к Google Sheets ===
def connect_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(WORKSHEET_NAME)
    return worksheet, sheet

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)

user_data = {}        # Хранение данных пользователя
user_states = {}      # Хранение шагов ввода

# === Функция главного меню (закреплённая клавиатура) ===
def get_main_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("🔚 Закрыть смену")
    btn2 = telebot.types.KeyboardButton("🔁 Открыть новую смену")
    btn3 = telebot.types.KeyboardButton("💰 Инкассация")
    keyboard.row(btn1, btn2)
    keyboard.row(btn3)
    return keyboard

# === Команда /start ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 Добро пожаловать в бота для учёта продаж!\n\n"
        "📌 Этот бот поможет вам быстро фиксировать продажи товаров.\n\n"
        "Как им пользоваться:\n"
        "1️⃣ Выберите своё имя при первом запуске.\n"
        "2️⃣ Нажмите «Новая продажа», чтобы добавить запись.\n"
        "3️⃣ В любое время вы можете закрыть смену или начать новую.\n\n"
        "Выберите ваше имя:"
    )
    bot.send_message(message.chat.id, welcome_text)

    # Показываем список имён
    keyboard = telebot.types.InlineKeyboardMarkup()
    for name in EMPLOYEES:
        keyboard.add(telebot.types.InlineKeyboardButton(text=name, callback_data=f"name_{name}"))
    bot.send_message(message.chat.id, "👤 Выберите ваше имя:", reply_markup=keyboard)

# === Обработка выбора имени ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("name_"))
def handle_employee_choice(call):
    chat_id = call.message.chat.id
    employee = call.data.replace("name_", "")
    user_data[chat_id] = {"employee": employee}

    # Получаем сумму в кассе
    worksheet, _ = connect_sheet()
    cash_value = worksheet.acell(CASH_REGISTER_CELL).value or "0"
    try:
        cash = int(cash_value.replace(" ", "").replace(",", "."))
    except:
        cash = 0
    user_data[chat_id]["cash"] = cash

    bot.answer_callback_query(call.id, f"Вы выбрали: {employee}")
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"✅ Вы выбрали: {employee}."
    )

    # Сообщение о кассе
    bot.send_message(chat_id, f"💼 В кассе сейчас: {cash} руб.")

    # Инлайн-кнопка "Новая продажа"
    keyboard = telebot.types.InlineKeyboardMarkup()
    new_sale_btn = telebot.types.InlineKeyboardButton("🆕 Новая продажа", callback_data="new_sale")
    keyboard.add(new_sale_btn)

    bot.send_message(chat_id, "Можно приступать к работе!", reply_markup=get_main_keyboard())
    bot.send_message(chat_id, "👇 Начните с добавления продажи", reply_markup=keyboard)

# === Обработчик инлайн-кнопки "Новая продажа" ===
@bot.callback_query_handler(func=lambda call: call.data == "new_sale")
def handle_new_sale_button(call):
    chat_id = call.message.chat.id

    if chat_id not in user_data:
        bot.send_message(chat_id, "❌ Сначала выберите имя командой /start")
        return

    user_states[chat_id] = {
        "step": "category",
        "data": {}
    }

    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    buttons = [telebot.types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in CATEGORIES]
    keyboard.add(*buttons)

    bot.send_message(chat_id, "📦 Выберите категорию:", reply_markup=keyboard)

# === Обработка выбора категории ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def handle_category(call):
    chat_id = call.message.chat.id
    category = call.data.replace("cat_", "")
    user_states[chat_id]["data"]["category"] = category
    user_states[chat_id]["step"] = "name"

    bot.answer_callback_query(call.id, f"Выбрано: {category}")
    bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                          text="📝 Введите название товара:")

# === Ввод названия товара ===
@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get("step") == "name")
def handle_name(message):
    chat_id = message.chat.id
    name = message.text.strip()
    user_states[chat_id]["data"]["name"] = name
    user_states[chat_id]["step"] = "quantity"

    keyboard = telebot.types.InlineKeyboardMarkup(row_width=4)
    buttons = [telebot.types.InlineKeyboardButton(str(q), callback_data=f"qty_{q}") for q in [1, 2, 5, 10]]
    keyboard.add(*buttons)

    bot.send_message(chat_id, "🔢 Выберите количество:", reply_markup=keyboard)

# === Обработка количества ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("qty_"))
def handle_quantity(call):
    chat_id = call.message.chat.id
    qty = int(call.data.replace("qty_", ""))
    user_states[chat_id]["data"]["quantity"] = qty
    user_states[chat_id]["step"] = "amount"

    bot.answer_callback_query(call.id, f"Выбрано: {qty}")
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text="💰 Введите сумму:")

# === Ввод суммы ===
@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get("step") == "amount")
def handle_amount(message):
    chat_id = message.chat.id
    try:
        amount = int(message.text.strip())
        user_states[chat_id]["data"]["amount"] = amount
        user_states[chat_id]["step"] = "payment"

        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        buttons = [telebot.types.InlineKeyboardButton(pay, callback_data=f"pay_{pay}") for pay in PAYMENT_TYPES]
        keyboard.add(*buttons)

        bot.send_message(chat_id, "💳 Выберите способ оплаты:", reply_markup=keyboard)
    except ValueError:
        bot.reply_to(message, "❌ Введите корректное число")

# === Обработка способа оплаты ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def handle_payment(call):
    chat_id = call.message.chat.id
    payment = call.data.replace("pay_", "")
    user_states[chat_id]["data"]["payment"] = payment
    user_states[chat_id]["step"] = "discount"

    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        telebot.types.InlineKeyboardButton("Да", callback_data="disc_да"),
        telebot.types.InlineKeyboardButton("Нет", callback_data="disc_нет")
    ]
    keyboard.add(*buttons)

    bot.answer_callback_query(call.id, f"Выбрано: {payment}")
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text="🎁 Есть ли скидка?", reply_markup=keyboard)

# === Обработка скидки и сохранение ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("disc_"))
def handle_discount(call):
    chat_id = call.message.chat.id
    discount = call.data.replace("disc_", "").capitalize()
    user_states[chat_id]["data"]["discount"] = discount

    data = user_states[chat_id]["data"]
    employee = user_data[chat_id]["employee"]
    time = datetime.now().strftime("%H:%M")
    date = datetime.now().strftime("%Y-%m-%d")

    row = [
        date,
        time,
        employee,
        data["category"],
        data["name"],
        data["quantity"],
        data["amount"],
        data["payment"],
        data["discount"]
    ]

    try:
        worksheet, _ = connect_sheet()
        worksheet.append_row(row)

        # Если оплата наличкой — увеличиваем кассу
        if data["payment"] == "Наличка":
            user_data[chat_id]["cash"] += int(data["amount"])
            worksheet.update(CASH_REGISTER_CELL, [[str(user_data[chat_id]["cash"])]])  # ✅ Исправлено

        # Кнопка "Новая продажа" под сообщением
        keyboard = telebot.types.InlineKeyboardMarkup()
        new_sale_btn = telebot.types.InlineKeyboardButton("🆕 Новая продажа", callback_data="new_sale")
        keyboard.add(new_sale_btn)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Продажа добавлена:\n"
                 f"{data['name']} x{data['quantity']} = {data['amount']} руб.\n"
                 f"Оплата: {data['payment']}, Скидка: {discount}",
            reply_markup=keyboard
        )
        del user_states[chat_id]  # Очистка состояния
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка при записи в таблицу: {str(e)}")

# === Команда /close_shift или кнопка "Закрыть смену" ===
@bot.message_handler(func=lambda m: m.text == "🔚 Закрыть смену")
def handle_close_shift_button(message):
    close_shift(message)

# === Команда /open_shift или кнопка "Открыть новую смену" ===
@bot.message_handler(func=lambda m: m.text == "🔁 Открыть новую смену")
def handle_open_shift_button(message):
    chat_id = message.chat.id

    # Удаляем старое имя
    if chat_id in user_data:
        del user_data[chat_id]

    # Предлагаем выбрать имя заново
    bot.send_message(chat_id, "🔄 Новая смена. Выберите ваше имя снова.")

    keyboard = telebot.types.InlineKeyboardMarkup()
    for name in EMPLOYEES:
        keyboard.add(telebot.types.InlineKeyboardButton(text=name, callback_data=f"name_{name}"))
    bot.send_message(chat_id, "👤 Выберите ваше имя:", reply_markup=keyboard)

# === Команда /close_shift ===
def close_shift(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.reply_to(message, "❌ Сначала выберите имя командой /start")
        return

    employee = user_data[chat_id]["employee"]
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        worksheet, _ = connect_sheet()
        records = worksheet.get_all_records()

        # Получаем план на день
        plan_cell = worksheet.acell(PLAN_CELL).value
        plan = float(plan_cell.replace(" ", "").replace(",", ".")) if plan_cell and plan_cell.isdigit() else 0

        # Фильтруем записи за сегодня по имени
        today_sales = [r for r in records if r[DATE_COLUMN] == today and r["Имя"] == employee]

        if not today_sales:
            bot.reply_to(message, "⚠️ За сегодня нет записей.")
            return

        total_sales = sum(int(r[CASH_COLUMN]) for r in today_sales)
        percent_complete = (total_sales / plan * 100) if plan > 0 else 0

        payment_types = {}
        categories = {}

        for r in today_sales:
            payment_types[r[PAYMENT_COLUMN]] = payment_types.get(r[PAYMENT_COLUMN], 0) + int(r[CASH_COLUMN])
            categories[r["Категория"]] = categories.get(r["Категория"], 0) + int(r["Кол-во"])

        report = (
            f"✅ Закрытие смены: {employee}\n"
            f"📅 Дата: {today}\n"
            f"📦 Всего позиций: {len(today_sales)} шт.\n"
            f"💰 Общая выручка: {total_sales} руб.\n\n"
            f"🎯 План на день: {plan} руб.\n"
            f"📈 Выполнение: {percent_complete:.1f}%\n\n"
            f"💳 По форме оплаты:\n"
        )

        for pay_type, amount in payment_types.items():
            report += f"- {pay_type}: {amount} руб.\n"

        report += "\n🧾 Категории товаров:\n"
        for category, count in categories.items():
            report += f"- {category}: {count} шт.\n"

        bot.reply_to(message, report)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при получении данных: {str(e)}")

# === Обработчик кнопки "Инкассация" ===
@bot.message_handler(func=lambda m: m.text == "💰 Инкассация")
def handle_cash_out_button(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.reply_to(message, "❌ Сначала выберите имя командой /start")
        return

    user_states[chat_id] = {
        "step": "inc_reason",
        "data": {"type": "incassation"}
    }
    bot.send_message(chat_id, "📝 Укажите причину инкассации:")

# === Шаг 1: Причина инкассации ===
@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get("step") == "inc_reason")
def handle_inc_reason(message):
    chat_id = message.chat.id
    reason = message.text.strip()
    user_states[chat_id]["data"]["reason"] = reason
    user_states[chat_id]["step"] = "inc_amount"
    bot.send_message(chat_id, "🔢 Укажите сумму инкассации:")

# === Шаг 2: Сумма инкассации ===
@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get("step") == "inc_amount")
def handle_inc_amount(message):
    chat_id = message.chat.id
    try:
        amount = int(message.text.strip())
        data = user_states[chat_id]["data"]
        employee = user_data[chat_id]["employee"]
        time = datetime.now().strftime("%H:%M")
        date = datetime.now().strftime("%Y-%m-%d")

        if amount <= 0:
            bot.reply_to(message, "❌ Сумма должна быть положительной!")
            return

        if user_data[chat_id]["cash"] < amount:
            bot.reply_to(message, "❌ В кассе недостаточно средств!")
            return

        # Обновляем кассу
        user_data[chat_id]["cash"] -= amount

        worksheet, _ = connect_sheet()
        worksheet.append_row([
            date, time, employee, "Инкассация", data["reason"], 0, -amount, "Наличка", "-"
        ])
        worksheet.update(CASH_REGISTER_CELL, [[str(user_data[chat_id]["cash"])]])  # ✅ Исправлено

        bot.send_message(chat_id, f"✅ Инкассация проведена: {amount} руб.\n"
                                  f"Осталось в кассе: {user_data[chat_id]['cash']} руб.")
        del user_states[chat_id]

    except ValueError:
        bot.reply_to(message, "❌ Введите корректное число")

# === Запуск бота ===
print("Бот запущен...")
bot.polling(none_stop=True)
