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


# ---------------- LOGGING ---------------- #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ---------------- CONFIG ---------------- #

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ---------------- FSM ---------------- #

class Generate(StatesGroup):
    waiting_prompt = State()


# ---------------- MENUS ---------------- #

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="📢 TG канал с промптами", url="https://t.me/your_channel")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])


def model_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Gemini Flash Image", callback_data="model_gemini")],
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


def generate_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Выбрать модель", callback_data="choose_model")],
        [InlineKeyboardButton(text="📐 Выбрать формат", callback_data="choose_format")],
        [InlineKeyboardButton(text="✍️ Ввести промпт", callback_data="write_prompt")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


# ---------------- START ---------------- #

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    await message.answer("🏠 Главное меню", reply_markup=main_menu())


# ---------------- MAIN MENU ---------------- #

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.answer("🏠 Главное меню", reply_markup=main_menu())
    await callback.answer()


@dp.callback_query(F.data == "generate")
async def open_generate(callback: CallbackQuery):
    await callback.message.answer("🎨 Настройки генерации:", reply_markup=generate_menu())
    await callback.answer()


# ---------------- MODEL ---------------- #

@dp.callback_query(F.data == "choose_model")
async def choose_model(callback: CallbackQuery):
    await callback.message.answer("🧠 Выберите модель:", reply_markup=model_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("model_"))
async def select_model(callback: CallbackQuery):
    model_key = callback.data.split("_")[1]

    if model_key == "gemini":
        update_model(callback.from_user.id, "google/gemini-2.5-flash-image")
        await callback.message.answer("✅ Модель: Gemini Flash Image")

    await callback.answer()


# ---------------- FORMAT ---------------- #

@dp.callback_query(F.data == "choose_format")
async def choose_format(callback: CallbackQuery):
    await callback.message.answer("📐 Выберите формат:", reply_markup=format_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("format_"))
async def select_format(callback: CallbackQuery):
    format_value = callback.data.split("_")[1]
    update_format(callback.from_user.id, format_value)
    await callback.message.answer(f"✅ Формат: {format_value}")
    await callback.answer()


# ---------------- PROMPT ---------------- #

@dp.callback_query(F.data == "write_prompt")
async def write_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Generate.waiting_prompt)
    await callback.message.answer("✍️ Напишите промпт")
    await callback.answer()


# ---------------- GENERATION ---------------- #

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
            logging.error(result["error"])
            await status_msg.edit_text("❌ Ошибка генерации.")
            await state.clear()
            return

        image_bytes = result["image_bytes"]

        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        quality = 95
        while quality >= 30:
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=quality)
            size_mb = buffer.tell() / (1024 * 1024)

            if size_mb <= 9:
                image_bytes = buffer.getvalue()
                break

            quality -= 5

        file = BufferedInputFile(image_bytes, filename="image.jpg")

        if len(image_bytes) > 9 * 1024 * 1024:
            sent = await message.answer_document(file)
        else:
            sent = await message.answer_photo(file)

        if sent:
            deduct_balance(user_id, COST)
            new_balance = get_user(user_id)[0]
            await message.answer(f"💰 Остаток: {new_balance}₽")

        await status_msg.delete()

    except (TelegramBadRequest, TelegramNetworkError):
        logging.exception("Telegram send error")
        await status_msg.edit_text("❌ Ошибка отправки изображения.")

    except Exception:
        logging.exception("Generation error")
        await status_msg.edit_text("❌ Ошибка генерации.")

    await state.clear()


# ---------------- BALANCE ---------------- #

@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    balance_value = user[0] if user else 0
    await callback.message.answer(f"💰 Баланс: {balance_value}₽")
    await callback.answer()


# ---------------- OTHER BUTTONS ---------------- #

@dp.callback_query(F.data == "topup")
async def topup(callback: CallbackQuery):
    await callback.message.answer("💳 Пополнение скоро будет доступно.")
    await callback.answer()


@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.message.answer("🤖 AI генератор изображений на Gemini.")
    await callback.answer()


# ---------------- WEBHOOK ---------------- #

async def on_startup(app):
    logging.info("Setting webhook...")
    await bot.set_webhook(WEBHOOK_URL)


async def on_shutdown(app):
    logging.info("Deleting webhook...")
    await bot.delete_webhook()
    await bot.session.close()


app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
