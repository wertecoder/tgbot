import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Словарь для хранения данных пользователей (баланс, состояние игры, мины, нажатия).
# Данные сбрасываются при перезапуске. Для реального проекта используйте базу данных (например, SQLite).
users = {}

# Команда /start - приветствие и инструкции для пользователя
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Это бот-игра 'Минное поле'. "
        "Команды:\n/start - начать\n/free - проверить баланс\n/bet <сумма> - сделать ставку и начать игру"
    )

# Команда /free - показывает текущий баланс пользователя
async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем ID пользователя
    user_id = update.message.from_user.id
    # Получаем баланс или задаём начальный (100 монет), если пользователь новый
    balance = users.get(user_id, {}).get('balance', 100.0)
    # Отправляем сообщение с балансом, отформатированным до 2 знаков после запятой
    await update.message.reply_text(f"Ваш баланс: {balance:.2f} монет")

# Команда /bet - начало игры с указанной ставкой
async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем ID пользователя
    user_id = update.message.from_user.id
    # Получаем аргументы команды (сумма ставки)
    args = context.args

    # Проверяем, что введена сумма ставки
    if not args:
        await update.message.reply_text("Укажите сумму ставки! Пример: /bet 10")
        return

    # Проверяем, что сумма введена корректно
    try:
        bet_amount = float(args[0])  # Сумма ставки
        if bet_amount <= 0:
            raise ValueError("Сумма ставки должна быть больше 0!")
    except ValueError:
        await update.message.reply_text("Сумма должна быть числом больше 0! Пример: /bet 10")
        return

    # Инициализируем пользователя, если его нет в словаре
    if user_id not in users:
        users[user_id] = {'balance': 100.0, 'game_active': False, 'mines': [], 'safe_clicks': 0, 'chosen_cells': []}

    # Проверяем, достаточно ли средств для ставки
    if bet_amount > users[user_id]['balance']:
        await update.message.reply_text("Недостаточно средств для ставки!")
        return
    if users[user_id]['balance'] <= 0:
        await update.message.reply_text("Ваш баланс 0! Пополните его или начните заново.")
        return

    # Проверяем, не активна ли уже игра
    if users[user_id]['game_active']:
        await update.message.reply_text("Игра уже начата! Введите число (0-24) или 'стоп'.")
        return

    # Запускаем игру: вычитаем ставку, сбрасываем состояние, генерируем мины
    users[user_id]['balance'] -= bet_amount
    users[user_id]['game_active'] = True
    users[user_id]['mines'] = random.sample(range(25), 5)  # Генерируем 5 случайных мин на поле 5x5
    users[user_id]['safe_clicks'] = 0  # Сбрасываем счётчик безопасных ходов
    users[user_id]['bet_amount'] = bet_amount  # Сохраняем ставку
    users[user_id]['chosen_cells'] = []  # Сбрасываем выбранные клетки

    # Уведомляем пользователя о начале игры
    await update.message.reply_text(
        f"Ставка {bet_amount:.2f} принята! Поле 5x5, 5 мин. Введите число от 0 до 24 или 'стоп'."
    )

# Обработка ходов игрока (числа или команды 'стоп')
async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем ID пользователя
    user_id = update.message.from_user.id
    # Получаем текст сообщения и приводим к нижнему регистру
    text = update.message.text.lower()

    # Проверяем, активна ли игра для пользователя
    if user_id not in users or not users[user_id]['game_active']:
        await update.message.reply_text("Игра не начата! Используйте /bet <сумма> для начала.")
        return

    # Обработка команды 'стоп' для завершения игры
    if text == 'стоп':
        clicks = users[user_id]['safe_clicks']  # Количество безопасных ходов
        multiplier = clicks * 0.2  # Множитель: 0.2 за каждый безопасный ход
        users[user_id]['balance'] *= (1 + multiplier)  # Умножаем баланс на (1 + множитель)
        users[user_id]['game_active'] = False  # Завершаем игру
        users[user_id]['chosen_cells'] = []  # Сбрасываем выбранные клетки
        await update.message.reply_text(
            f"Игра окончена! Вы сделали {clicks} безопасных ходов. "
            f"Баланс умножен на {1 + multiplier:.2f}. Новый баланс: {users[user_id]['balance']:.2f}"
        )
        return

    # Проверяем, что введено корректное число
    try:
        cell = int(text)  # Пытаемся преобразовать ввод в число
        if cell < 0 or cell > 24:  # Проверяем диапазон (0-24 для поля 5x5)
            await update.message.reply_text("Введите число от 0 до 24!")
            return
    except ValueError:
        await update.message.reply_text("Введите число от 0 до 24 или 'стоп' для завершения!")
        return

    # Проверяем, не выбиралась ли уже эта клетка
    if cell in users[user_id]['chosen_cells']:
        await update.message.reply_text("Эта клетка уже выбрана! Выберите другую.")
        return
    users[user_id]['chosen_cells'].append(cell)  # Добавляем клетку в список выбранных

    # Проверяем, попал ли игрок на мину
    if cell in users[user_id]['mines']:
        users[user_id]['game_active'] = False  # Завершаем игру
        users[user_id]['chosen_cells'] = []  # Сбрасываем выбранные клетки
        await update.message.reply_text(
            f"Бум! Вы попали на мину. Игра окончена. Баланс: {users[user_id]['balance']:.2f}"
        )
    else:
        users[user_id]['safe_clicks'] += 1  # Увеличиваем счётчик безопасных ходов
        await update.message.reply_text(
            f"Безопасно! Ходов: {users[user_id]['safe_clicks']}. Введите следующее число или 'стоп'."
        )

# Основная функция для запуска бота
def main():
    # Токен бота от @BotFather. Замените на ваш собственный токен!
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    try:
        # Создаём приложение для бота
        app = Application.builder().token(TOKEN).build()
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}. Проверьте правильность токена!")
        return

    # Регистрируем команды и обработчик текстовых сообщений
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("free", free))
    app.add_handler(CommandHandler("bet", bet))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_move))

    # Запускаем бота в режиме опроса сообщений
    print("Бот запущен. Нажмите Ctrl+C для остановки.")
    app.run_polling()

# Запускаем бота, если скрипт запущен напрямую
if __name__ == '__main__':
    main()