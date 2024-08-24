import time
from aiogram.types import ContentType
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import sqlite3
from sqlite3 import Error
import os

API_TOKEN = '7129169272:AAFdC8hln0Vl2Lz3wShSL4lf59PtZYkVJac'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


# Добавляем новое состояние для фотоотчета
class PhotoReport(StatesGroup):
    waiting_for_photo = State()


# State management classes for various user flows
class UserState(StatesGroup):
    role = State()  # Initial state for role selection
    brigade_selection = State()  # For selecting brigade
    day_selection = State()  # For selecting day
    task_entry = State()  # For entering tasks



class AdminAuth(StatesGroup):
    awaiting_login = State()
    awaiting_password = State()


class TaskManagement(StatesGroup):
    choosing_brigade = State()
    choosing_day = State()
    entering_tasks = State()
    confirming_tasks = State()
    adding_more_tasks = State()


class EmployeeActions(StatesGroup):
    choosing_action = State()
    choosing_brigade = State()
    choosing_day = State()
    viewing_tasks = State()
    marking_tasks = State()
    entering_uncompleted_tasks = State()


class DatabaseManager:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self.initialize_db()

    def create_connection(self):
        """Создает соединение с базой данных."""
        try:
            self.conn = sqlite3.connect(self.db_file)
        except Error as e:
            print(f"Ошибка подключения к базе данных: {e}")

    def initialize_db(self):
        """Инициализирует базу данных и создает необходимые таблицы."""
        self.create_connection()
        if self.conn is not None:
            # SQL для создания таблиц
            self.create_tasks_table()
            self.create_uncompleted_tasks_table()
        else:
            print("Не удалось создать соединение с базой данных.")

    def create_tasks_table(self):
        """Создает таблицу задач, если она еще не существует."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            brigade INTEGER NOT NULL,
            day TEXT NOT NULL,
            task_name TEXT NOT NULL,
            status TEXT NOT NULL
        );
        """
        try:
            c = self.conn.cursor()
            c.execute(create_table_sql)
        except Error as e:
            print(f"Ошибка при создании таблицы задач: {e}")

    def create_uncompleted_tasks_table(self):
        """Создает таблицу невыполненных задач, если она еще не существует."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS uncompleted_tasks (
            id INTEGER PRIMARY KEY,
            brigade INTEGER NOT NULL,
            day TEXT NOT NULL,
            description TEXT NOT NULL
        );
        """
        try:
            c = self.conn.cursor()
            c.execute(create_table_sql)
        except Error as e:
            print(f"Ошибка при создании таблицы невыполненных задач: {e}")

    def add_task(self, brigade, day, task_name, status="pending"):
        """Добавляет задачу в базу данных."""
        with self.conn:
            self.conn.execute("INSERT INTO tasks (brigade, day, task_name, status) VALUES (?, ?, ?, ?)",
                              (brigade, day, task_name, status))
            print(f"Задача добавлена: {task_name}")

    def delete_tasks_for_brigade_on_day(self, brigade, day):
        """Удаляет все задачи для заданной бригады на заданный день."""
        delete_query = "DELETE FROM tasks WHERE brigade = ? AND day = ?"
        try:
            self.conn.execute(delete_query, (brigade, day))
            self.conn.commit()
            print(f"Все предыдущие задачи для бригады {brigade} на день {day} были удалены.")
        except Error as e:
            print(f"Ошибка при удалении задач: {e}")

    def get_tasks_for_brigade(self, brigade, day=None):
        """Извлекает задачи для заданной бригады и, опционально, для определенного дня."""
        tasks = []
        try:
            cursor = self.conn.cursor()
            query = "SELECT id, brigade, day, task_name, status FROM tasks WHERE brigade = ?"
            params = (brigade,)
            if day:
                # Преобразуем day в нижний регистр, чтобы соответствовать формату в базе данных
                query += " AND day = ?"
                params += (day.lower(),)  # Убедитесь, что day передаётся в нижнем регистре
            cursor.execute(query, params)
            tasks = cursor.fetchall()
        except Error as e:
            print(f"Ошибка при получении задач: {e}")
        return tasks

    def close_connection(self):
        """Закрывает соединение с базой данных."""
        if self.conn:
            self.conn.close()


def read_tasks(db_file):
    """Читает и выводит содержимое таблицы задач."""
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Выполняем запрос на выборку всех задач
        cursor.execute("SELECT * FROM tasks")
        tasks = cursor.fetchall()

        # Выводим содержимое таблицы
        for task in tasks:
            print(task)

        # Закрываем соединение с базой данных
        conn.close()
    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")


# Utility functions for creating inline keyboards
def get_role_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Сотрудник", callback_data="employee"),
                 InlineKeyboardButton("Администратор", callback_data="admin"))
    return keyboard


def get_brigade_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    for i in range(1, 5):
        keyboard.insert(InlineKeyboardButton(f"Бригада {i}", callback_data=f"brigade_{i}"))
    return keyboard


def get_day_keyboard():
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
    keyboard = InlineKeyboardMarkup(row_width=3)
    for day in days:
        keyboard.add(InlineKeyboardButton(day, callback_data=f"day_{day.lower()}"))
    return keyboard


def yes_no_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Да", callback_data="yes"),
                 InlineKeyboardButton("Нет", callback_data="no"))
    return keyboard


# Manager notification functions
manager_chat_id = "7129169272"  # Example manager chat ID


async def notify_manager_about_uncompleted_tasks(brigade, day, tasks):
    message = f"Бригада {brigade}, {day}, не выполнила следующие задания:\n{tasks}"
    await bot.send_message(manager_chat_id, message)



async def notify_manager_about_completion(brigade, day):
    message = f"Бригада {brigade} выполнила все задания за {day}."
    await bot.send_message(manager_chat_id, message)


# Bot command and message handlers
@dp.message_handler(commands=['start'], state='*')
async def send_welcome(message: types.Message):
    await message.reply("Привет! Кто вы?", reply_markup=get_role_keyboard())
    await UserState.role.set()

@dp.callback_query_handler(text="return_to_main", state="*")
async def return_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await send_welcome(call.message)


# Handlers for role selection
# Объединяем обработку выбора роли в один обработчик с проверкой callback_data
@dp.callback_query_handler(lambda call: call.data in ["employee", "admin"], state=UserState.role)
async def choose_role(call: types.CallbackQuery, state: FSMContext):
    role = call.data
    await state.update_data(role=role)
    if role == "admin":
        await AdminAuth.awaiting_login.set()
        await call.message.answer("Введите ваш логин:")
    elif role == "employee":
        # Переход к выбору действия сразу после выбора роли "сотрудник"
        await EmployeeActions.choosing_action.set()
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Просмотреть задания", callback_data="mark_tasks"))
        await call.message.answer("Выберите действие:", reply_markup=keyboard)



# Continue adding handlers for admin and employee workflows...

# Выбор бригады и дня недели администратором
@dp.callback_query_handler(state=TaskManagement.choosing_brigade)
async def choose_brigade(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(chosen_brigade=call.data)
    await TaskManagement.choosing_day.set()
    await call.message.answer("Выберите день недели:", reply_markup=get_day_keyboard())



@dp.callback_query_handler(state=TaskManagement.choosing_day)
async def choose_day(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(chosen_day=call.data)
    await TaskManagement.entering_tasks.set()
    await call.message.answer("Введите задания для выбранной бригады и дня через запятую:")


# Ввод и подтверждение заданий администратором
@dp.message_handler(state=TaskManagement.entering_tasks)
async def enter_tasks(message: types.Message, state: FSMContext):
    tasks_text = message.text
    await state.update_data(tasks=tasks_text.split(', '))
    await TaskManagement.confirming_tasks.set()
    await message.answer(f"Вы ввели следующие задания:\n{tasks_text}\nВсё верно?", reply_markup=yes_no_keyboard())


# Изменения в обработчике tasks_confirmed
@dp.callback_query_handler(lambda call: call.data == "yes", state=TaskManagement.confirming_tasks)
async def tasks_confirmed(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brigade = data['chosen_brigade'].split("_")[1]  # Извлекаем номер бригады из callback_data
    day = data['chosen_day'].split("_")[1]  # Извлекаем день из callback_data
    tasks = data['tasks']

    db_manager = DatabaseManager(db_file)
    # Сначала удаляем все предыдущие задачи для данной бригады и дня
    db_manager.delete_tasks_for_brigade_on_day(int(brigade), day)

    for task_name in tasks:  # Предполагается, что tasks - это список имен задач
        db_manager.add_task(int(brigade), day, task_name)

    await state.finish()
    await call.message.answer("Задания сохранены и опубликованы для сотрудников.", reply_markup=get_main_menu_keyboard())


# Повторный ввод заданий администратором
@dp.callback_query_handler(text_contains="no", state=TaskManagement.confirming_tasks)
async def reenter_tasks(call: types.CallbackQuery):
    await TaskManagement.entering_tasks.set()
    await call.message.answer("Введите задания заново:")


# Выбор действия сотрудником
@dp.callback_query_handler(text="employee", state=UserState.role)
async def employee_choose_action(call: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Просмотреть задания", callback_data="mark_tasks"))
    await call.message.answer("Выберите действие:", reply_markup=keyboard)
    await EmployeeActions.choosing_action.set()


# Просмотр заданий сотрудником
@dp.callback_query_handler(text="view_tasks", state=EmployeeActions.choosing_action)
async def view_tasks(call: types.CallbackQuery):
    await EmployeeActions.choosing_brigade.set()
    await call.message.answer("Выберите бригаду:", reply_markup=get_brigade_keyboard())


@dp.callback_query_handler(lambda c: c.data.startswith('brigade_'), state=EmployeeActions.choosing_brigade)
async def employee_select_brigade(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(chosen_brigade=call.data)
    await EmployeeActions.choosing_day.set()
    await call.message.answer("Выберите день недели:", reply_markup=get_day_keyboard())



day_photos = {
    "суббота": "images/saturday.jpeg",
    "понедельник": "images/monday.jpeg",
    "вторник": "images/tuesday.jpeg",
    "среда": "images/wednesday.jpeg",
    "четверг": "images/thirthday.jpeg",
    "пятница": "images/friday.jpeg",
}



@dp.callback_query_handler(lambda c: c.data.startswith('day_'), state=EmployeeActions.choosing_day)
async def employee_select_day(call: types.CallbackQuery, state: FSMContext):
    chosen_day = call.data.split("_")[1]
    photo_path = os.path.expanduser(day_photos[chosen_day])

    detailed_tasks = """1. Корректировка полива
2. Прополка и протравка сорняка
3. Собрать ВЕСЬ мусор и опавшие листья
4. Стрижка и аэрация газона (по необходимости)
5. Внос удобрений и лечение болезней (только после консультации и одобрения бригадира)
6. Проверить все растения на наличие болезней и вредителей
7. Удаление с отцветших частей
8. В случае обнаружения мертвого растения, уведомить об этом бригадира, зафиксировать (фото) и ТОЛЬКО ПОСЛЕ одобрения бригадира удалить растение"""

    # Отправляем фотографию для выбранного дня
    with open(photo_path, 'rb') as photo:
        await bot.send_photo(call.from_user.id, photo, caption=f"Задания на {chosen_day}")

    # Отправляем детализированные задания
    await call.message.answer(detailed_tasks)

    data = await state.get_data()
    brigade = int(data['chosen_brigade'].split("_")[1])

    # Получаем и отправляем задания после отправки фотографии
    tasks = db_manager.get_tasks_for_brigade(brigade, chosen_day)

    if tasks:
        tasks_message = "\n".join([f"{task[3]}" for task in tasks])
        await call.message.answer(f"Задания для бригады {brigade} на {chosen_day}:\n{tasks_message}")
    else:
        await call.message.answer(f"Задания для бригады {brigade} на {chosen_day}:\nЗадания на этот день не найдены.")

    # Добавляем кнопки для возможных действий после просмотра заданий
    task_actions_keyboard = InlineKeyboardMarkup()
    task_actions_keyboard.add(
        InlineKeyboardButton("Выполнено", callback_data="all_done"),
        InlineKeyboardButton("Не выполнено", callback_data="not_all_done"),
    InlineKeyboardButton("Главное меню", callback_data="return_to_main")
    )
    await call.message.answer("Выберите действие:", reply_markup=task_actions_keyboard)
    await state.update_data(chosen_day=chosen_day)
    await EmployeeActions.marking_tasks.set()


@dp.callback_query_handler(lambda c: c.data == "employee", state=UserState.role)
async def employee_selected(call: types.CallbackQuery, state: FSMContext):
    await EmployeeActions.choosing_action.set()
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Просмотреть задания", callback_data="view_tasks"),
                 InlineKeyboardButton("Отметить выполнение", callback_data="mark_tasks"),
                 )

    await call.message.answer("Выберите действие:", reply_markup=keyboard)
    await call.answer()


# Примерная проверка логина и пароля для администратора (в реальных условиях используйте защищенное хранилище)
VALID_ADMIN_LOGIN = "admin"
VALID_ADMIN_PASSWORD = "password"


@dp.message_handler(state=AdminAuth.awaiting_login)
async def process_login(message: types.Message, state: FSMContext):
    # Сохраняем логин во временном хранилище
    await state.update_data(admin_login=message.text)
    await AdminAuth.awaiting_password.set()
    await message.answer("Введите ваш пароль:")


@dp.message_handler(state=AdminAuth.awaiting_password)
async def process_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_login = data.get("admin_login")
    admin_password = message.text
    if admin_login == VALID_ADMIN_LOGIN and admin_password == VALID_ADMIN_PASSWORD:
        await TaskManagement.choosing_brigade.set()
        await message.answer("Аутентификация прошла успешно. Выберите бригаду:", reply_markup=get_brigade_keyboard())
    else:
        await message.answer("Неверный логин или пароль. Попробуйте ещё раз.")
        await AdminAuth.awaiting_login.set()


# Выбор действия "Отметить выполнение заданий"
@dp.callback_query_handler(text="mark_tasks", state=EmployeeActions.choosing_action)
async def mark_tasks_choose_brigade(call: types.CallbackQuery):
    await EmployeeActions.choosing_brigade.set()
    await call.message.answer("Выберите бригаду:", reply_markup=get_brigade_keyboard())


# После выбора бригады, выбор дня недели
@dp.callback_query_handler(lambda c: c.data.startswith('brigade_'), state=EmployeeActions.choosing_brigade)
async def mark_tasks_choose_day(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(chosen_brigade=call.data)
    await EmployeeActions.choosing_day.set()
    await call.message.answer("Выберите день недели:", reply_markup=get_day_keyboard())


@dp.callback_query_handler(lambda c: c.data.startswith('day_'), state=EmployeeActions.choosing_day)
async def show_tasks_for_day(call: types.CallbackQuery, state: FSMContext):
    chosen_day_code = call.data  # 'day_понедельник', например
    chosen_day = chosen_day_code.split("_")[1]  # Получаем выбранный день, например 'понедельник'

    data = await state.get_data()
    brigade_code = data['chosen_brigade']  # 'brigade_1', например
    brigade = brigade_code.split("_")[1]  # Получаем номер бригады, например '1'

    # Получение заданий для бригады и дня из базы данных
    tasks = db_manager.get_tasks_for_brigade(brigade, chosen_day)

    # Формирование сообщения со списком заданий
    if tasks:
        tasks_message = "\n".join([f"{task[3]}: {('✅' if task[4] == 'completed' else '❌')}" for task in tasks])
    else:
        tasks_message = "На данный день задания отсутствуют."

    # Создание кнопок для отметки выполнения заданий
    markup = InlineKeyboardMarkup().row(
        InlineKeyboardButton("Все задания выполнены", callback_data="all_done"),
        InlineKeyboardButton("Не все задания выполнены", callback_data="not_all_done")
    )

    # Отправка сообщения с заданиями и кнопками
    await call.message.answer(f"Задания для бригады {brigade} на {chosen_day}:\n{tasks_message}", reply_markup=markup)

    # Переход в состояние ожидания выбора выполнения заданий
    await EmployeeActions.marking_tasks.set()

def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Вернуться на главное меню", callback_data="return_to_main"))
    return keyboard



# Если сотрудник отметил, что все задания выполнены
@dp.callback_query_handler(text="all_done", state=EmployeeActions.marking_tasks)
async def all_tasks_done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brigade = data['chosen_brigade'].split("_")[1]
    day = data['chosen_day']

    # Запрашиваем у пользователя отправку фотоотчета
    await PhotoReport.waiting_for_photo.set()
    await call.message.answer("Отправьте фотоотчет о выполненных заданиях.")

    # Сохраняем в состоянии информацию о бригаде и дне
    await state.update_data(report_message=f"Бригада {brigade}, {day}, выполнила все задания.")


# Если сотрудник отметил, что не все задания выполнены
@dp.callback_query_handler(text="not_all_done", state=EmployeeActions.marking_tasks)
async def not_all_tasks_done(call: types.CallbackQuery, state: FSMContext):
    await EmployeeActions.entering_uncompleted_tasks.set()
    await call.message.answer("Какие задания не были выполнены? Введите ниже одним сообщением.")


# После отправки текстового отчета о невыполненных заданиях
@dp.message_handler(state=EmployeeActions.entering_uncompleted_tasks)
async def enter_uncompleted_tasks(message: types.Message, state: FSMContext):
    uncompleted_tasks = message.text
    data = await state.get_data()

    if 'chosen_day' not in data:
        await message.answer("Произошла ошибка: день не был выбран. Пожалуйста, начните процесс заново.")
        await state.finish()
        return

    brigade = data['chosen_brigade'].split("_")[1]
    day = data['chosen_day']

    # Запрашиваем у пользователя отправку фотоотчета
    await PhotoReport.waiting_for_photo.set()
    await message.answer("Отправьте фотоотчет о выполнении заданий.")

    # Сохраняем в состоянии информацию о бригаде, дне и невыполненных задачах
    await state.update_data(report_message=f"Бригада {brigade}, {day}, выполнила все задания кроме: {uncompleted_tasks}")

# Обработка получения фотоотчета
@dp.message_handler(content_types=[ContentType.PHOTO], state=PhotoReport.waiting_for_photo)
async def handle_photo_report(message: types.Message, state: FSMContext):
    data = await state.get_data()
    report_message = data.get('report_message')
    photo = message.photo[-1]  # Выбираем фото с наибольшим разрешением

    # Отправляем текстовый отчет и фото администратору
    await bot.send_message(manager_chat_id, report_message)
    await bot.send_photo(manager_chat_id, photo.file_id)

    # Завершаем процесс и возвращаем пользователя в главное меню
    await message.answer("Фотоотчет отправлен менеджеру.", reply_markup=get_main_menu_keyboard())
    await state.finish()

# Если пользователь не отправил фото, но отправил другое сообщение
@dp.message_handler(state=PhotoReport.waiting_for_photo)
async def handle_invalid_photo_report(message: types.Message):
    await message.answer("Пожалуйста, отправьте фотографию в качестве фотоотчета.")


def main():
    while True:
        try:
            # Запуск бота с aiogram
            executor.start_polling(dp, skip_updates=True)
        except Exception as e:
            print(f"Произошла ошибка: {e}. Перезапуск через 5 секунд.")
            time.sleep(5)


# Ensure database is initialized before the bot starts polling
if __name__ == '__main__':
    db_file = 'tasks.db'  # Указываем путь к файлу базы данных здесь
    db_manager = DatabaseManager(db_file)
    read_tasks(db_file)
    # Предполагаем, что brigade и day были правильно извлечены из callback_data
    brigade_number = 1  # Пример извлечения номера бригады
    day_of_week = "понедельник"  # Убедитесь, что день передаётся в нижнем регистре

    # Вызов метода с правильными параметрами
    tasks = db_manager.get_tasks_for_brigade(brigade_number, day_of_week)

    executor.start_polling(dp, skip_updates=True)
