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

from database import add_user, get_user, update_model, update_format, deduct_balance
from generator import generate_image_openrouter


logging.basicConfig(level=logging.WARNING)

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= FSM ================= #

class Generate(StatesGroup):
    waiting_image = State()
    waiting_prompt = State()


# ================= MENUS ================= #

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(
            text="📢 TG канал с промптами",
            url="https://t.me/YourDesignerSpb"
        )],
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
            InlineKeyboardButton(text="💳 Другая сумма", callback_data="topup_custom")
        ],
        [
            InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")
        ]
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
        [InlineKeyboardButton(text="📝 Только промпт", callback_data="mode_text")],
        [InlineKeyboardButton(text="🖼 Фото + промпт", callback_data="mode_image")],
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


# ================= START ================= #

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    await message.answer("🏠 Главное меню", reply_markup=main_menu())


# ================= NAVIGATION ================= #

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 Главное меню", reply_markup=main_menu())
    await callback.answer()


# ================= TOPUP ================= #

@dp.callback_query(F.data == "topup")
async def show_topup(callback: CallbackQuery):
    await callback.message.edit_text("💰 Выберите сумму пополнения:", reply_markup=topup_menu())
    await callback.answer()


# ================= GENERATION FLOW ================= #

@dp.callback_query(F.data == "generate")
async def choose_model(callback: CallbackQuery):
    await callback.message.edit_text("🧠 Выберите модель:", reply_markup=model_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("model_"))
async def choose_mode(callback: CallbackQuery, state: FSMContext):
    model_key = callback.data.split("_")[1]

    model_map = {
        "nano": "google/gemini-2.5-flash-image",
        "pro": "google/gemini-2.5-flash-image",
        "seedream": "google/gemini-2.5-flash-image"
    }

    update_model(callback.from_user.id, model_map.get(model_key))
    await state.update_data(selected_model=model_key)

    await callback.message.edit_text("⚙ Выберите режим генерации:", reply_markup=mode_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("mode_"))
async def choose_format(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split("_")[1]
    await state.update_data(mode=mode)

    await callback.message.edit_text("📐 Выберите формат:", reply_markup=format_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("format_"))
async def after_format(callback: CallbackQuery, state: FSMContext):
    format_value = callback.data.split("_")[1]
    update_format(callback.from_user.id, format_value)

    data = await state.get_data()
    mode = data.get("mode")

    if mode == "text":
        await callback.message.edit_text(
            f"✅ Формат: {format_value}\n\n✍️ Напишите промпт:"
        )
        await state.set_state(Generate.waiting_prompt)

    elif mode == "image":
        await callback.message.edit_text(
            f"✅ Формат: {format_value}\n\n🖼 Отправьте изображение:"
        )
        await state.set_state(Generate.waiting_image)

    await callback.answer()


# ================= IMAGE MODE ================= #

@dp.message(Generate.waiting_image)
async def receive_image(message: Message, state: FSMContext):

    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image"):
        file_id = message.document.file_id
    else:
        await message.answer("❌ Пожалуйста, отправьте изображение.")
        return

    file = await bot.get_file(file_id)
    downloaded = await bot.download_file(file.file_path)

    image_bytes = downloaded.read()
    image_base64 = base64.b64encode(image_bytes).decode()

    await state.update_data(user_image=image_base64)
    await message.answer("✍️ Теперь напишите промпт:")
    await state.set_state(Generate.waiting_prompt)


# ================= GENERATION ================= #

@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):

    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await state.clear()
        return

    balance, model, format_value = user
    COST = 10

    if balance < COST:
        await message.answer("❌ Недостаточно средств.")
        await state.clear()
        return

    status = await message.answer("🎨 Генерирую...")

    try:
        data = await state.get_data()
        user_image = data.get("user_image")

        result = await generate_image_openrouter(
            prompt=message.text,
            model=model,
            format_value=format_value,
            user_image=user_image
        )

        if "error" in result:
            await status.edit_text("❌ Ошибка генерации.")
            await state.clear()
            return

        image = Image.open(BytesIO(result["image_bytes"])).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)

        file = BufferedInputFile(buffer.getvalue(), filename="image.jpg")
        sent = await message.answer_photo(file)

        if sent:
            deduct_balance(user_id, COST)

        try:
            await status.delete()
        except:
            pass

    except Exception:
        logging.exception("FINAL GENERATION ERROR")
        try:
            await status.edit_text("❌ Ошибка отправки изображения.")
        except:
            pass

    await state.clear()


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
