import os
import logging
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
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from database import add_user, get_user, update_model, update_format, deduct_balance
from generator import generate_image_openrouter


logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= FSM ================= #

class Generate(StatesGroup):
    waiting_prompt = State()


# ================= MENUS ================= #

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="📢 TG канал с промптами", url="https://t.me/your_channel")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])


def topup_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100 ₽", callback_data="topup_100"),
            InlineKeyboardButton(text="500 ₽", callback_data="topup_500"),
        ],
        [
            InlineKeyboardButton(text="1000 ₽", callback_data="topup_1000"),
        ],
        [
            InlineKeyboardButton(text="💳 Другая сумма", callback_data="topup_custom"),
        ],
        [
            InlineKeyboardButton(text="⬅ Назад", callback_data="back_main"),
        ]
    ])


def model_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nano Banana", callback_data="model_nano")],
        [InlineKeyboardButton(text="Nano Banana Pro", callback_data="model_pro")],
        [InlineKeyboardButton(text="SeeDream", callback_data="model_seedream")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


def format_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1:1", callback_data="format_1:1"),
            InlineKeyboardButton(text="16:9", callback_data="format_16:9"),
        ],
        [
            InlineKeyboardButton(text="9:16", callback_data="format_9:16"),
        ]
    ])


# ================= START ================= #

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    await message.answer("🏠 Главное меню", reply_markup=main_menu())


# ================= TOPUP ================= #

@dp.callback_query(F.data == "topup")
async def topup(callback: CallbackQuery):
    await callback.message.answer("💳 Выберите сумму пополнения:", reply_markup=topup_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("topup_"))
async def topup_selected(callback: CallbackQuery):
    amount = callback.data.split("_")[1]
    await callback.message.answer(f"🚧 Пополнение на {amount} ₽ скоро будет подключено.")
    await callback.answer()


# ================= GENERATE ================= #

@dp.callback_query(F.data == "generate")
async def generate_start(callback: CallbackQuery):
    await callback.message.answer("🧠 Выберите модель:", reply_markup=model_menu())
    await callback.answer()


# ================= MODEL ================= #

@dp.callback_query(F.data.startswith("model_"))
async def select_model(callback: CallbackQuery):
    model_key = callback.data.split("_")[1]

    model_map = {
        "nano": "google/gemini-2.5-flash-image",
        "pro": "google/gemini-2.5-flash-image",
        "seedream": "google/gemini-2.5-flash-image"
    }

    update_model(callback.from_user.id, model_map[model_key])

    await callback.message.answer("📐 Теперь выберите формат:", reply_markup=format_menu())
    await callback.answer()


# ================= FORMAT ================= #

@dp.callback_query(F.data.startswith("format_"))
async def select_format(callback: CallbackQuery, state: FSMContext):
    format_value = callback.data.split("_")[1]

    update_format(callback.from_user.id, format_value)

    user = get_user(callback.from_user.id)
    _, model, format_value = user

    model_name = {
        "google/gemini-2.5-flash-image": "Nano Banana"
    }.get(model, "Неизвестно")

    await callback.message.answer(
        f"✅ Модель: {model_name}\n"
        f"✅ Формат: {format_value}\n\n"
        f"✍️ Напишите промпт:"
    )

    await state.set_state(Generate.waiting_prompt)
    await callback.answer()


# ================= PROMPT ================= #

@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):

    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await message.answer("Ошибка пользователя.")
        await state.clear()
        return

    balance, model, format_value = user
    COST = 10

    if balance < COST:
        await message.answer("❌ Недостаточно средств.")
        await state.clear()
        return

    status_msg = await message.answer("🎨 Генерирую...")

    try:
        result = await generate_image_openrouter(
            prompt=message.text,
            model=model,
            format_value=format_value
        )

        if "error" in result:
            await status_msg.edit_text("❌ Ошибка генерации.")
            await state.clear()
            return

        image_bytes = result["image_bytes"]

        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_bytes = buffer.getvalue()

        file = BufferedInputFile(image_bytes, filename="image.jpg")

        sent = await message.answer_photo(file)

        if sent:
            deduct_balance(user_id, COST)
            new_balance = get_user(user_id)[0]
            await message.answer(f"💰 Остаток: {new_balance}₽")

        await status_msg.delete()

    except Exception:
        await status_msg.edit_text("❌ Ошибка отправки изображения.")

    await state.clear()


# ================= OTHER ================= #

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.message.answer("🤖 AI генератор изображений.")
    await callback.answer()


@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.answer("🏠 Главное меню", reply_markup=main_menu())
    await callback.answer()


# ================= WEBHOOK ================= #

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
