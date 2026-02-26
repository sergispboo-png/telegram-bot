from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher()

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="pay")],
            [InlineKeyboardButton(text="📢 TG канал с промтами", url="https://t.me/LuxRenderBot")],
            [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
        ]
    )

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привет!\n\nВыбери действие:", reply_markup=main_menu())

@dp.callback_query(F.data == "generate")
async def generate(callback: CallbackQuery):
    await callback.message.answer("Опиши изображение ✍️")
    await callback.answer()

@dp.callback_query(F.data == "pay")
async def pay(callback: CallbackQuery):
    await callback.message.answer("Выбери сумму пополнения 💳")
    await callback.answer()

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()



app = web.Application()
SimpleRequestHandler(
    dispatcher=dp,
    bot=bot
).register(app, path=WEBHOOK_PATH)

setup_application(app, dp, bot=bot)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

