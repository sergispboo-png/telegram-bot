import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="balance")],
        [InlineKeyboardButton(text="📢 TG канал с промтами", url="https://t.me/LuxRenderBot")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])

def generate_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Модель", callback_data="model")],
        [InlineKeyboardButton(text="📐 Формат", callback_data="format")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="balance")],
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
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
    ])

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привет!\n\nВыбери действие:", reply_markup=main_menu())

async def safe_edit(callback: CallbackQuery, text, markup):
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=text,
        reply_markup=markup
    )

@dp.callback_query(F.data == "generate")
async def generate(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback,
        "🖼 Работа с изображениями\n\nЧто вы хотите сделать?",
        generate_menu()))

@dp.callback_query(F.data == "model")
async def model(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback,
        "🤖 Выберите модель:",
        model_menu()))

@dp.callback_query(F.data == "format")
async def format_select(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback,
        "📐 Выберите формат:",
        format_menu()))

@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback,
        "💰 Пополнение баланса:",
        balance_menu()))

@dp.callback_query(F.data == "main")
async def main(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback,
        "👋 Главное меню:",
        main_menu()))

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback,
        "ℹ️ LuxRender — сервис генерации изображений.",
        main_menu()))

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
