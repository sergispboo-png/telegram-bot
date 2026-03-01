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


# ================= НАСТРОЙКИ =================

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = "YourDesignerSpb"
ADMIN_ID = 373830941

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.WARNING)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ERROR_LOG = []


# ================= FSM =================

class Generate(StatesGroup):
    waiting_image = State()
    waiting_prompt = State()
    editing = State()


# ================= ВСПОМОГАТЕЛЬНОЕ =================

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
        await message.answer("❗ Подпишитесь на канал для использования бота.", reply_markup=keyboard)
        return False
    return True


# ================= UI =================

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
            InlineKeyboardButton(text="1:1", callback_data="format_1_1"),
            InlineKeyboardButton(text="16:9", callback_data="format_16_9"),
        ],
        [
            InlineKeyboardButton(text="9:16", callback_data="format_9_16"),
        ],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="generate")]
    ])


def after_generation_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить", callback_data="generate")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
    ])


# ================= START =================

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


# ================= ЛИЧНЫЙ КАБИНЕТ =================

@dp.callback_query(F.data == "profile")
async def user_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    balance = user[0] if user else 0

    from database import conn
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM generations WHERE user_id=?", (user_id,))
    total_generations = cursor.fetchone()[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
    ])

    await callback.message.edit_text(
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: <b>{balance}</b>\n"
        f"🎨 Всего генераций: <b>{total_generations}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


# ================= АДМИН КОМАНДЫ =================

@dp.message(F.text == "/stats")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    users = get_users_count()
    generations = get_generations_count()
    payments_count, payments_sum = get_payments_stats()

    await message.answer(
        f"📊 Статистика\n\n"
        f"👥 Пользователей: {users}\n"
        f"🎨 Генераций: {generations}\n"
        f"💳 Платежей: {payments_count}\n"
        f"💰 Доход: {payments_sum} ₽"
    )


@dp.message(F.text.startswith("/broadcast "))
async def admin_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return

    text = message.text.replace("/broadcast ", "")
    users = get_all_user_ids()

    sent, failed = 0, 0

    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except:
            failed += 1

    await message.answer(f"Рассылка завершена\nОтправлено: {sent}\nОшибок: {failed}")


@dp.message(F.text.startswith("/addbalance "))
async def admin_add_balance(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, user_id, amount = message.text.split()
        update_balance(int(user_id), int(amount))
        await message.answer("Баланс обновлён.")
    except:
        await message.answer("Формат: /addbalance USER_ID СУММА")


@dp.message(F.text == "/logs")
async def admin_logs(message: Message):
    if not is_admin(message.from_user.id):
        return

    if not ERROR_LOG:
        await message.answer("Ошибок нет.")
        return

    await message.answer("\n".join(ERROR_LOG[-10:]))


# ================= ГЕНЕРАЦИЯ =================

@dp.callback_query(F.data == "generate")
async def choose_model(callback: CallbackQuery):
    if not await require_subscription(callback.from_user.id, callback.message):
        return
    await callback.message.edit_text("🧠 Выберите модель:", reply_markup=model_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("model_"))
async def choose_mode(callback: CallbackQuery):
    update_model(callback.from_user.id, "google/gemini-2.5-flash-image")
    await callback.message.edit_text("⚙ Выберите режим:", reply_markup=mode_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("mode_"))
async def choose_format(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split("_")[1]
    await state.update_data(mode=mode)
    await callback.message.edit_text("📐 Выберите формат:", reply_markup=format_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("format_"))
async def after_format(callback: CallbackQuery, state: FSMContext):
    format_value = callback.data.replace("format_", "").replace("_", ":")
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
