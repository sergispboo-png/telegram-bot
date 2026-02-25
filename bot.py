from fastapi import FastAPI, Request
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.webhook.aiohttp_server import setup_application
import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()

selected_model = "SeeDream 4.5"
selected_format = "Оригинал"
balance = 0


def main_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="pay")],
            [InlineKeyboardButton(text="📢 TG канал с промтами", url="https://t.me/YourDesignerSpb")],
            [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
        ]
    )
    return keyboard


def generate_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🤖 Модель: {selected_model}", callback_data="model")],
            [InlineKeyboardButton(text=f"📐 Формат: {selected_format}", callback_data="format")],
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="pay")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back")]
        ]
    )
    return keyboard


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет!\n\nВыбери действие:",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "generate")
async def generate(callback: CallbackQuery):

    await callback.message.edit_text(
        f"""🖼 Работа с изображениями

🤖 Модель: {selected_model}
📐 Формат: {selected_format}
💰 Стоимость: 10₽

Что вы хотите сделать?""",
        reply_markup=generate_menu()
    )

    await callback.answer()


@dp.callback_query(F.data == "model")
async def model_menu(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Nano-Banana", callback_data="nano")],
            [InlineKeyboardButton(text="Nano-Banana Pro", callback_data="pro")],
            [InlineKeyboardButton(text="SeeDream 4.0", callback_data="sd4")],
            [InlineKeyboardButton(text="SeeDream 4.5", callback_data="sd45")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
        ]
    )

    await callback.message.edit_text(
        "🤖 Выберите модель:",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data.in_(["nano", "pro", "sd4", "sd45"]))
async def set_model(callback: CallbackQuery):

    global selected_model

    if callback.data == "nano":
        selected_model = "Nano-Banana"
    elif callback.data == "pro":
        selected_model = "Nano-Banana Pro"
    elif callback.data == "sd4":
        selected_model = "SeeDream 4.0"
    elif callback.data == "sd45":
        selected_model = "SeeDream 4.5"

    await generate(callback)


@dp.callback_query(F.data == "format")
async def format_menu(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1:1 Квадрат", callback_data="f1")],
            [InlineKeyboardButton(text="2:3 Портрет", callback_data="f2")],
            [InlineKeyboardButton(text="16:9 Широкое", callback_data="f3")],
            [InlineKeyboardButton(text="Оригинал", callback_data="f4")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
        ]
    )

    await callback.message.edit_text(
        "📐 Выберите формат:",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data.in_(["f1", "f2", "f3", "f4"]))
async def set_format(callback: CallbackQuery):

    global selected_format

    if callback.data == "f1":
        selected_format = "1:1"
    elif callback.data == "f2":
        selected_format = "2:3"
    elif callback.data == "f3":
        selected_format = "16:9"
    elif callback.data == "f4":
        selected_format = "Оригинал"

    await generate(callback)


@dp.callback_query(F.data == "pay")
async def pay(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
        ]
    )

    await callback.message.edit_text(
        f"""💰 Пополнение баланса

Ваш текущий баланс: {balance}₽

Выберите сумму пополнения:""",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ]
    )

    await callback.message.edit_text(
        "ℹ️ Информация о сервисе",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    await callback.message.edit_text(
        "👋 Привет!\n\nВыбери действие:",
        reply_markup=main_menu()
    )

    await callback.answer()


WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
app = FastAPI()


@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)


@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()


@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    data = await request.json()
    await dp.feed_update(bot, data)
    return {"ok": True}
