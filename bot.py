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
PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
CHANNEL_USERNAME = "YourDesignerSpb"
ADMIN_ID = 373830941

if not TOKEN:
    raise ValueError("BOT_TOKEN not set!")

if not PUBLIC_DOMAIN:
    raise ValueError("RAILWAY_PUBLIC_DOMAIN not set!")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{PUBLIC_DOMAIN}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.WARNING)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ERROR_LOG = []

# ================= ЦЕНА =================

GENERATION_PRICE = 10

# ================= ЦЕНЫ МОДЕЛЕЙ =================

MODEL_PRICES = {
    "google/gemini-2.5-flash-image": GENERATION_PRICE,
    "pro_model": GENERATION_PRICE,
    "seedream_model": GENERATION_PRICE,
}

# ================= FSM =================

class Generate(StatesGroup):
    waiting_image = State()
    waiting_prompt = State()

# ================= MIDDLEWARE БАЛАНСА =================

from aiogram import BaseMiddleware
from typing import Callable, Dict, Any


class BalanceMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable,
        event,
        data: Dict[str, Any]
    ):

        if not isinstance(event, Message):
            return await handler(event, data)

        state = data.get("state")
        if state:
            current_state = await state.get_state()
            if current_state != Generate.waiting_prompt.state:
                return await handler(event, data)

        user_id = event.from_user.id
        user = get_user(user_id)

        if not user:
            add_user(user_id)
            user = get_user(user_id)

        balance, model, format_value = user
        price = MODEL_PRICES.get(model, GENERATION_PRICE)

        if balance < price:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
            ])

            await event.answer(
                f"❌ Недостаточно средств.\n\n"
                f"Стоимость генерации: {price}₽\n"
                f"Ваш баланс: {balance}₽",
                reply_markup=keyboard
            )
            return

        return await handler(event, data)


dp.message.middleware(BalanceMiddleware())
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
        [InlineKeyboardButton(text=f"Nano Banana — {GENERATION_PRICE}₽", callback_data="model_nano")],
        [InlineKeyboardButton(text=f"Nano Banana Pro — {GENERATION_PRICE}₽", callback_data="model_pro")],
        [InlineKeyboardButton(text=f"SeeDream — {GENERATION_PRICE}₽", callback_data="model_seedream")],
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
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
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


# ================= ГЕНЕРАЦИЯ (ИСПРАВЛЕННЫЕ ОТСТУПЫ) =================

@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):
    if not await require_subscription(message.from_user.id, message):
        return

    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        add_user(user_id)
        user = get_user(user_id)

    balance, model, format_value = user

    status = await message.answer(
        f"🎨 Генерирую...\n💰 Стоимость: {GENERATION_PRICE}₽"
    )

    try:
        data = await state.get_data()
        user_image = data.get("user_image")

        result = await generate_image_openrouter(
            prompt=message.text,
            model=model,
            format_value=format_value,
            user_image=user_image
        )

        if "image_bytes" not in result:
            ERROR_LOG.append(str(result))

            await status.edit_text(
                "❌ Ошибка генерации.",
                reply_markup=after_generation_menu()
            )
            return

        image = Image.open(BytesIO(result["image_bytes"])).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=90)

        file = BufferedInputFile(buffer.getvalue(), filename="image.jpg")
        await message.answer_photo(file)

        price = MODEL_PRICES.get(model, GENERATION_PRICE)
        deduct_balance(user_id, price)
        add_generation(user_id, model)

        new_balance = get_user(user_id)[0]

        await message.answer(
            f"✅ Готово!\n💎 Баланс: {new_balance}",
            reply_markup=after_generation_menu()
        )

        await state.clear()

    except Exception as e:
        ERROR_LOG.append(str(e))

        await status.edit_text(
            "❌ Ошибка генерации.",
            reply_markup=after_generation_menu()
        )
