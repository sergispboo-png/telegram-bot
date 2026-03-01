import os
import logging
import base64
from aiohttp import web
from PIL import Image
from io import BytesIO

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BufferedInputFile,
)
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from database import (
    add_user,
    get_user,
    update_model,
    update_format,
    deduct_balance,
    update_balance,
    get_users_count,
    get_generations_count,
    get_payments_stats,
    get_all_user_ids,
    add_generation,
)

from generator import generate_image_openrouter

# ================== НАСТРОЙКИ ==================

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = "YourDesignerSpb"
ADMIN_ID = 373830941

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

# ================== ЛОГИ ==================

logging.basicConfig(level=logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)

# ================== INIT ==================

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ERROR_LOG = []

# ================== FSM ==================

class Generate(StatesGroup):
    waiting_image = State()
    waiting_prompt = State()
    editing = State()

# ================== ВСПОМОГАТЕЛЬНОЕ ==================

def is_admin(user_id: int):
    return user_id == ADMIN_ID

async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def require_subscription(user_id, message):
    if not await check_subscription(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME}")]
        ])
        await message.answer(
            "❗ Для использования бота необходимо подписаться на канал.",
            reply_markup=keyboard
        )
        return False
    return True

# ================== UI ==================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="profile")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="📢 TG канал", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])

def model_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nano Banana", callback_data="model_nano")],
        [InlineKeyboardButton(text="Nano Banana Pro", callback_data="model_pro")],
        [InlineKeyboardButton(text="SeeDream", callback_data="model_seedream")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])

def mode_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Только текст", callback_data="mode_text")],
        [InlineKeyboardButton(text="🖼 Фото + текст", callback_data="mode_image")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="generate")]
    ])

def format_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1:1", callback_data="format_1:1"),
            InlineKeyboardButton(text="16:9", callback_data="format_16:9"),
        ],
        [
            InlineKeyboardButton(text="9:16", callback_data="format_9:16"),
        ],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="generate")]
    ])

def after_generation_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить", callback_data="edit_start")],
        [InlineKeyboardButton(text="✏ Изменить промпт", callback_data="edit_prompt")],
        [InlineKeyboardButton(text="🖼 Добавить фото", callback_data="edit_add_photo")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
    ])

# ================== START ==================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)

    await message.answer(
        "✨ <b>LuxRender</b>\n\n"
        "Премиальная AI-генерация изображений нового уровня.\n\n"
        "🎨 Создавайте визуал для соцсетей\n"
        "🚀 Делайте рекламные креативы\n"
        "💼 Развивайте бизнес-проекты\n\n"
        "👇 Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

# ================== ЛИЧНЫЙ КАБИНЕТ ==================

@dp.callback_query(F.data == "profile")
async def user_profile(callback: CallbackQuery):
    user_id = callback.from_user.id

    user = get_user(user_id)
    balance = user[0] if user else 0

    from database import conn
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM generations WHERE user_id = ?",
        (user_id,)
    )
    user_generations = cursor.fetchone()[0]

    text = (
        "👤 <b>Личный кабинет</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"💰 Баланс: <b>{balance}</b>\n"
        f"🎨 Всего генераций: <b>{user_generations}</b>\n\n"
        "👇 Выберите действие:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
    ])

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "profile_stats")
async def profile_stats(callback: CallbackQuery):
    user_id = callback.from_user.id

    from database import conn
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM generations WHERE user_id = ?",
        (user_id,)
    )
    total = cursor.fetchone()[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="profile")]
    ])

    await callback.message.edit_text(
        f"📊 <b>Ваша статистика</b>\n\n🎨 Всего генераций: <b>{total}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()

# ================== НАВИГАЦИЯ ==================

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 Главное меню", reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(F.data == "generate")
async def choose_model(callback: CallbackQuery):
    if not await require_subscription(callback.from_user.id, callback.message):
        return
    await callback.message.edit_text("🧠 Выберите модель:", reply_markup=model_menu())
    await callback.answer()

@dp.callback_query(F.data.startswith("model_"))
async def choose_mode(callback: CallbackQuery, state: FSMContext):
    update_model(callback.from_user.id, "google/gemini-2.5-flash-image")
    await callback.message.edit_text("⚙ Выберите режим:", reply_markup=mode_menu())
    await callback.answer()

@dp.callback_query(F.data.startswith("mode_"))
async def choose_format(callback: CallbackQuery):
    await callback.message.edit_text("📐 Выберите формат:", reply_markup=format_menu())
    await callback.answer()
    @dp.callback_query(F.data.startswith("format_"))
async def after_format(callback: CallbackQuery, state: FSMContext):
    format_value = callback.data.split("_")[1]
    update_format(callback.from_user.id, format_value)

    data = await state.get_data()
    mode = data.get("mode")

    if mode == "text":
        await callback.message.edit_text("✍ Напишите промпт:")
        await state.set_state(Generate.waiting_prompt)
    else:
        await callback.message.edit_text("🖼 Отправьте изображение:")
        await state.set_state(Generate.waiting_image)

    await callback.answer()

# ================== WEBHOOK ==================

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
