import os
import asyncio
from aiohttp import web
from PIL import Image
from io import BytesIO
import tempfile

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from database import add_user, get_user, update_model, update_format, deduct_balance
from generator import generate_image_openrouter


TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class Generate(StatesGroup):
    waiting_prompt = State()


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")]
    ])


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    await message.answer("👋 Привет!", reply_markup=main_menu())


@dp.callback_query(F.data == "generate")
async def generate(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Generate.waiting_prompt)
    await callback.message.answer("✍️ Напиши промпт")


@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):

    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await message.answer("Ошибка пользователя.")
        return

    balance, model, format_value = user
    COST = 10

    if balance < COST:
        await message.answer("❌ Недостаточно средств.")
        await state.clear()
        return

    await message.answer("🎨 Генерирую...")

    result = await generate_image_openrouter(
        prompt=message.text,
        model="google/gemini-2.5-flash-image",
        format_value=format_value
    )

    if "error" in result:
        print("OPENROUTER ERROR:", result["error"])
        await message.answer("❌ Ошибка генерации.")
        await state.clear()
        return

    try:
        image = Image.open(BytesIO(result["image_bytes"]))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            image.convert("RGB").save(tmp, format="JPEG", quality=80)
            tmp_path = tmp.name

        sent = await message.answer_photo(photo=open(tmp_path, "rb"))

        if sent:
            deduct_balance(user_id, COST)
            new_balance = get_user(user_id)[0]
            await message.answer(f"💰 Остаток: {new_balance}₽")

    except Exception as e:
        print("SEND IMAGE ERROR:", e)
        await message.answer("❌ Ошибка отправки изображения.")

    await state.clear()


@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    balance_value = user[0] if user else 0
    await callback.message.answer(f"💰 Баланс: {balance_value}₽")


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
