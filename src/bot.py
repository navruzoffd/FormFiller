from src.config import TOKEN
from logger import logger
import re
import json
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup, StateFilter
from playwright.async_api import async_playwright
from fake_useragent import UserAgent
from src.yandex import YandexForm
import os

class FormFillingState(StatesGroup):
    waiting_for_question_number = State()
    waiting_for_weights = State()
    waiting_for_repetitions = State()

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    try:
        logger.info(f"Начата обработка команды /start от пользователя {message.from_user.id}")
        await message.answer("Привет 👋. Отправь мне ссылку на Yandex форму.")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")

@dp.message(lambda message: bool(re.search(r'https?://(?:www\.)?forms\.yandex\.[a-z]{2,}', message.text)))
async def handle_yandex_form_link(message: Message) -> None:
    try:
        link = message.text
        user_id = message.from_user.id
        logger.info(f"Получена ссылка на форму от пользователя {user_id}: {link}")

        await message.answer("Спасибо за ссылку! Получаю данные...")

        async with async_playwright() as playwright:
            ua = UserAgent(browsers=['edge', 'chrome'], os=["windows", "android", "ios"])
            form = YandexForm(playwright, ua.random)
            await form.start(link)
            await form.get_form_json(f"forms/{user_id}.json")
            await message.answer("Данные формы получены:")
            
            parse_json_message = await parse_json(f"forms/{user_id}.json")
            await message.answer(parse_json_message)
            await message.answer("Указать весомость ответов- /weight.\nЗапустить - /run")
    except Exception as e:
        logger.error(f"Ошибка при обработке ссылки на форму: {e}")
        await message.answer("Произошла ошибка при обработке формы.")

@dp.message(F.text == "/run")
async def run_filling(message: Message, state: FSMContext):
    try:
        logger.info(f"Команда /run от пользователя {message.from_user.id}")
        await message.answer("Сколько раз вы хотите заполнить форму?")
        await state.set_state(FormFillingState.waiting_for_repetitions)
    except Exception as e:
        logger.error(f"Ошибка при запуске заполнения формы: {e}")
        await message.answer("Произошла ошибка при запуске заполнения формы.")

@dp.message(StateFilter(FormFillingState.waiting_for_repetitions))
async def process_repetitions(message: Message, state: FSMContext):
    try:
        repetitions = int(message.text)
        user_id = message.from_user.id
        path = f"forms/{user_id}.json"

        logger.info(f"Пользователь {user_id} запросил {repetitions} повторений заполнения формы")
        await message.answer("Начинаю процесс заполнения...\nНе изменяйте форму до завершения процесса!")

        with open(path, 'r', encoding='utf-8') as file: 
            form = json.load(file)

        link = form["formLink"]

        async with async_playwright() as playwright:
            for i in range(repetitions):
                ua = UserAgent(browsers=['edge', 'chrome'], os=["windows", "android", "ios"])
                storage = os.getenv("storage.json")
                form_filler = YandexForm(playwright, ua.random, storage)
                await form_filler.start(link)
                await form_filler.fill_form(f"forms/{user_id}.json")
                if (i+1) % 10 == 0:
                    os.remove("storage.json")

        await message.answer(f"Форма была успешно заполнена {repetitions} раз(а).")
        logger.info(f"Форма успешно заполнена {repetitions} раз(а) для пользователя {user_id}")
    except ValueError:
        logger.warning(f"Некорректное число повторений от пользователя {message.from_user.id}")
        await message.answer("Пожалуйста, введите корректное число.")
    except Exception as e:
        logger.error(f"Ошибка при заполнении формы: {e}")
        await message.answer("Произошла ошибка при заполнении формы.")
    finally:
        await state.clear()

@dp.message(F.text == "/weight")
async def weight_setting(message: Message, state: FSMContext):
    user_id = message.from_user.id
    path = f"forms/{user_id}.json"

    try:
        with open(path, 'r', encoding='utf-8') as file:
            form = json.load(file)
        
        questions = form.get('questions', [])
        
        if not questions:
            await message.answer("В этой форме нет вопросов.")
            return
        
        question_list = "\n".join([f"{i+1}) {q['questionText']}" for i, q in enumerate(questions)])
        await message.answer(f"Выберите номер вопроса для наложения весов:\n\n{question_list}")
        await state.set_state(FormFillingState.waiting_for_question_number)
    except Exception as e:
        logger.error(f"Ошибка при загрузке формы для пользователя {user_id}: {e}")
        await message.answer("Произошла ошибка при загрузке формы.")

@dp.message(StateFilter(FormFillingState.waiting_for_question_number))
async def process_question_number(message: Message, state: FSMContext):
    try:
        question_number = int(message.text) - 1
        user_id = message.from_user.id
        path = f"forms/{user_id}.json"

        with open(path, 'r', encoding='utf-8') as file:
            form = json.load(file)

        if question_number < 0 or question_number >= len(form['questions']):
            await message.answer("Неверный номер вопроса. Попробуйте снова.")
            return

        await state.update_data(question_number=question_number)
        await message.answer("Введите веса для вариантов через запятую (например: 9,1,1,1). Веса должны быть в диапазоне от 0 до 10.")
        await state.set_state(FormFillingState.waiting_for_weights)
    except ValueError:
        await message.answer("Пожалуйста, введите корректный номер вопроса.")
    except Exception as e:
        logger.error(f"Ошибка при выборе номера вопроса: {e}")
        await message.answer("Произошла ошибка при выборе вопроса.")

@dp.message(StateFilter(FormFillingState.waiting_for_weights))
async def process_weights(message: Message, state: FSMContext):
    try:
        weights = list(map(int, message.text.split(',')))

        if any(weight < 0 or weight > 10 for weight in weights):
            await message.answer("Веса должны быть в диапазоне от 0 до 10. Попробуйте снова.")
            return

        user_data = await state.get_data()
        question_number = user_data.get('question_number')

        user_id = message.from_user.id
        path = f"forms/{user_id}.json"

        with open(path, 'r', encoding='utf-8') as file:
            form = json.load(file)

        options = form['questions'][question_number].get('options', [])
        if len(weights) != len(options):
            await message.answer(f"Количество весов ({len(weights)}) не совпадает с количеством ответов ({len(options)}). Попробуйте снова.")
            return

        form['questions'][question_number]['selectionWeight'] = {
            str(i + 1): weight for i, weight in enumerate(weights)
        }

        with open(path, 'w', encoding='utf-8') as file:
            json.dump(form, file, ensure_ascii=False, indent=4)

        await message.answer(f"Веса успешно установлены для вопроса №{question_number + 1}.\nУказать весомость - /weight.\nЗапустить - /run")
        logger.info(f"Пользователь {user_id} установил веса для вопроса №{question_number + 1}: {weights}")
    except ValueError:
        await message.answer("Пожалуйста, введите корректные веса (целые числа через запятую).")
    except Exception as e:
        logger.error(f"Ошибка при установке весов для пользователя {user_id}: {e}")
        await message.answer("Произошла ошибка при установке весов.")
    finally:
        await state.clear()

async def parse_json(path: str):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            form = json.load(file)

        message_text = f"{form['formTitle']}\n\n"
        question_num = 1
        for question in form["questions"]:
            message_text += f"{question_num}) {question['questionText']}:\n"
            for option in question["options"]:
                message_text += f"- {option}\n"
            message_text += "\n"
            question_num += 1

        return message_text
    except Exception as e:
        logger.error(f"Ошибка при парсинге JSON файла {path}: {e}")
        return "Ошибка при загрузке данных формы."

async def main():
    try:
        logger.info("Запуск бота")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
