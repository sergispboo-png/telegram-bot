from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------- ГЛАВНОЕ МЕНЮ ----------
def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="balance")],
            [InlineKeyboardButton(text="📢 TG канал с промтами", url="https://t.me/YourDesignerSpb")],
            [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
        ]
    )

# ---------- МЕНЮ ГЕНЕРАЦИИ ----------
def generate_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Модель", callback_data="model")],
            [InlineKeyboardButton(text="📐 Формат", callback_data="format")],
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="balance")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main")]
        ]
    )

# ---------- МОДЕЛИ ----------
def model_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Nano-Banana", callback_data="m1")],
            [InlineKeyboardButton(text="Nano-Banana Pro", callback_data="m2")],
            [InlineKeyboardButton(text="SeeDream 4.0", callback_data="m3")],
            [InlineKeyboardButton(text="SeeDream 4.5", callback_data="m4")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
        ]
    )

# ---------- ФОРМАТ ----------
def format_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1:1 Квадрат", callback_data="f1")],
            [InlineKeyboardButton(text="2:3 Портрет", callback_data="f2")],
            [InlineKeyboardButton(text="16:9 Широкое", callback_data="f3")],
            [InlineKeyboardButton(text="Оригинал", callback_data="f4")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
        ]
    )

# ---------- БАЛАНС ----------
def balance_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="100₽", callback_data="pay1")],
            [InlineKeyboardButton(text="500₽ +50₽", callback_data="pay2")],
            [InlineKeyboardButton(text="1000₽ +150₽", callback_data="pay3")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
        ]
    )

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привет!\n\nВыбери действие:", reply_markup=main_menu())

# ---------- CALLBACKS ----------
@dp.callback_query(F.data == "generate")
async def generate(callback: CallbackQuery):
    await callback.message.edit_text(
        "🖼 Работа с изображениями\n\nЧто вы хотите сделать?",
        reply_markup=generate_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "model")
async def model(callback: CallbackQuery):
    await callback.message.edit_text(
        "🤖 Выберите модель:",
        reply_markup=model_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "format")
async def format(callback: CallbackQuery):
    await callback.message.edit_text(
        "📐 Выберите формат:",
        reply_markup=format_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 Пополнение баланса:",
        reply_markup=balance_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "main")
async def main(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 Главное меню:",
        reply_markup=main_menu()
    )
    await callback.answer()

# ---------- WEBHOOK ----------
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

