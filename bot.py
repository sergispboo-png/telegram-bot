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


# ---------------- MENU ---------------- #

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")]
    ])


# ---------------- HANDLERS ---------------- #

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    await message.answer("👋 Привет!", reply_markup=main_menu())


@dp.callback_query(F.data == "generate")
async def generate_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Generate.waiting_prompt)
    await callback.message.answer("✍️ Напиши промпт")
    await callback.answer()


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
        # ---------------- GENERATION ---------------- #
        result = await generate_image_openrouter(
            prompt=message.text,
            model="google/gemini-2.5-flash-image",
            format_value=format_value
        )

        if "error" in result:
            logging.error(f"OpenRouter error: {result['error']}")
            await status_msg.edit_text("❌ Ошибка генерации.")
            await state.clear()
            return

        image_bytes = result["image_bytes"]

        # ---------------- CONVERT PNG -> JPG ---------------- #
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

        file_size_mb = len(image_bytes) / (1024 * 1024)
        logging.info(f"Final image size: {file_size_mb:.2f} MB")

        file = BufferedInputFile(image_bytes, filename="image.jpg")

        # ---------------- SAFE SEND ---------------- #
        if file_size_mb > 9:
            sent = await message.answer_document(file)
        else:
            sent = await message.answer_photo(file)

        # ---------------- DEDUCT ONLY AFTER SUCCESS ---------------- #
        if sent:
            deduct_balance(user_id, COST)
            new_balance = get_user(user_id)[0]
            await message.answer(f"💰 Остаток: {new_balance}₽")

        await status_msg.delete()

    except (TelegramBadRequest, TelegramNetworkError) as e:
        logging.exception("Telegram send error")
        await status_msg.edit_text("❌ Ошибка отправки изображения.")

    except Exception as e:
        logging.exception("Generation error")
        await status_msg.edit_text("❌ Ошибка генерации.")

    await state.clear()


@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    balance_value = user[0] if user else 0
    await callback.message.answer(f"💰 Баланс: {balance_value}₽")
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
