import os
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# FSM
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


# =======================
# CONFIG
# =======================

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# =======================
# FSM STATES
# =======================

class Generate(StatesGroup):
    choosing_model = State()
    choosing_format = State()
    waiting_prompt = State()


# =======================
# MENUS
# =======================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="balance")],
        [InlineKeyboardButton(text="📢 TG канал с промтами", url="https://t.me/YourDesignerSpb")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])


def generate_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Модель", callback_data="model")],
        [InlineKeyboardButton(text="📐 Формат", callback_data="format")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main")]
    ])


def model_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nano-Banana", callback_data="m1")],
        [InlineKeyboardButton(text="Nano-Banana Pro", callback_data="m2")],
        [InlineKeyboardButton(text="SeeDream 4.0", callback_data="m3")],
        [InlineKeyboardButton(text="SeeDream 4.5", callback_data="m4")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
    ])


def format_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1:1 Квадрат", callback_data="f1")],
        [InlineKeyboardButton(text="2:3 Портрет", callback_data="f2")],
        [InlineKeyboardButton(text="16:9 Широкое", callback_data="f3")],
        [InlineKeyboardButton(text="Оригинал", callback_data="f4")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
    ])


def balance_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100₽", callback_data="pay1")],
        [InlineKeyboardButton(text="500₽ +50₽", callback_data="pay2")],
        [InlineKeyboardButton(text="1000₽ +150₽", callback_data="pay3")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main")]
    ])


# =======================
# START
# =======================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет!\n\nВыбери действие:",
        reply_markup=main_menu()
    )


# =======================
# SAFE EDIT (Webhook safe)
# =======================

async def safe_edit(callback: CallbackQuery, text, markup):
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=text,
        reply_markup=markup
    )


# =======================
# MAIN MENU
# =======================

@dp.callback_query(F.data == "main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(
        callback,
        "ℹ️ LuxRender — сервис генерации изображений.",
        main_menu()
    ))


# =======================
# GENERATE FLOW
# =======================

@dp.callback_query(F.data == "generate")
async def generate(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Generate.waiting_prompt)

    await callback.answer()
    asyncio.create_task(safe_edit(
        callback,
        "🖼 Отправьте текстовый промпт для генерации изображения:",
        generate_menu()
    ))


@dp.callback_query(F.data == "model")
async def choose_model(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Generate.choosing_model)

    await callback.answer()
    asyncio.create_task(safe_edit(
        callback,
        "🤖 Выберите модель:",
        model_menu()
    ))


@dp.callback_query(F.data == "format")
async def choose_format(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Generate.choosing_format)

    await callback.answer()
    asyncio.create_task(safe_edit(
        callback,
        "📐 Выберите формат:",
        format_menu()
    ))


# =======================
# MODEL SELECTION
# =======================

MODELS = {
    "m1": "Nano-Banana",
    "m2": "Nano-Banana Pro",
    "m3": "SeeDream 4.0",
    "m4": "SeeDream 4.5",
}


@dp.callback_query(F.data.in_(MODELS.keys()))
async def set_model(callback: CallbackQuery, state: FSMContext):
    model_name = MODELS[callback.data]
    await state.update_data(model=model_name)

    await callback.answer("✅ Модель выбрана")
    asyncio.create_task(safe_edit(
        callback,
        f"🤖 Вы выбрали модель:\n\n{model_name}\n\nТеперь отправьте промпт:",
        generate_menu()
    ))

    await state.set_state(Generate.waiting_prompt)


# =======================
# FORMAT SELECTION
# =======================

FORMATS = {
    "f1": "1:1",
    "f2": "2:3",
    "f3": "16:9",
    "f4": "Original",
}


@dp.callback_query(F.data.in_(FORMATS.keys()))
async def set_format(callback: CallbackQuery, state: FSMContext):
    format_value = FORMATS[callback.data]
    await state.update_data(format=format_value)

    await callback.answer("✅ Формат выбран")
    asyncio.create_task(safe_edit(
        callback,
        f"📐 Вы выбрали формат:\n\n{format_value}\n\nТеперь отправьте промпт:",
        generate_menu()
    ))

    await state.set_state(Generate.waiting_prompt)


# =======================
# PROMPT HANDLER
# =======================

@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    model = data.get("model", "Nano-Banana")
    format_value = data.get("format", "1:1")

    prompt = message.text

    await message.answer(
        f"🎨 Генерирую изображение...\n\n"
        f"📝 Промпт: {prompt}\n"
        f"🤖 Модель: {model}\n"
        f"📐 Формат: {format_value}\n\n"
        f"(Здесь будет вызов API генерации)"
    )

    await state.clear()


# =======================
# BALANCE
# =======================

@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(
        callback,
        "💰 Пополнение баланса:",
        balance_menu()
    ))


# =======================
# WEBHOOK
# =======================

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)


async def on_shutdown(app):
    await bot.delete_webhook()


app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
