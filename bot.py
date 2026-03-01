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
    get_users_count
)

from generator import generate_image_openrouter


logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

CHANNEL_USERNAME = "@YourDesignerSpb"
CHANNEL_URL = "https://t.me/YourDesignerSpb"

ADMINS = [373830941]  # ← ВСТАВЬ СВОЙ TELEGRAM ID

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= SUBSCRIPTION CHECK ================= #

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


# ================= FSM ================= #

class Generate(StatesGroup):
    waiting_image = State()
    waiting_prompt = State()
    editing = State()


# ================= UI ================= #

MODEL_NAMES = {
    "nano": "Nano Banana",
    "pro": "Nano Banana Pro",
    "seedream": "SeeDream"
}


def breadcrumb_text(model=None, format_value=None):
    lines = []
    if model:
        lines.append(f"🧠 Модель: {MODEL_NAMES.get(model, model)}")
    if format_value:
        lines.append(f"📐 Формат: {format_value}")
    return "\n".join(lines)


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="📢 TG канал с промптами", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])


def subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
    ])


# ================= START ================= #

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    if not await check_subscription(message.from_user.id):
        await message.answer(
            "❗ Для использования бота необходимо подписаться на канал.",
            reply_markup=subscribe_keyboard()
        )
        return

    add_user(message.from_user.id)
    await message.answer("🏠 Главное меню", reply_markup=main_menu())


# ================= SUB CHECK BUTTON ================= #

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery, state: FSMContext):
    if await check_subscription(callback.from_user.id):
        add_user(callback.from_user.id)
        await callback.message.edit_text("✅ Подписка подтверждена!")
        await callback.message.answer("🏠 Главное меню", reply_markup=main_menu())
    else:
        await callback.answer("❌ Вы ещё не подписались", show_alert=True)


# ================= GLOBAL CALLBACK GUARD ================= #

@dp.callback_query()
async def subscription_guard(callback: CallbackQuery):
    if callback.data == "check_sub":
        return

    if not await check_subscription(callback.from_user.id):
        await callback.message.answer(
            "❗ Для работы с ботом нужно подписаться на канал.",
            reply_markup=subscribe_keyboard()
        )
        await callback.answer()
        return


# ================= STATS ================= #

@dp.message(F.text == "/stats")
async def stats_handler(message: Message):
    if message.from_user.id not in ADMINS:
        return

    count = get_users_count()
    await message.answer(f"👥 Всего пользователей: {count}")


# ================= GENERATION ================= #

@dp.callback_query(F.data == "generate")
async def choose_model(callback: CallbackQuery):
    await callback.message.edit_text(
        "🧠 Выберите модель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Nano Banana", callback_data="model_nano")],
            [InlineKeyboardButton(text="Nano Banana Pro", callback_data="model_pro")],
            [InlineKeyboardButton(text="SeeDream", callback_data="model_seedream")],
        ])
    )
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

    await callback.message.edit_text("✍ Напишите промпт:")
    await state.set_state(Generate.waiting_prompt)
    await callback.answer()


@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):

    if not await check_subscription(message.from_user.id):
        await message.answer("❗ Подпишитесь на канал для использования бота.")
        return

    user = get_user(message.from_user.id)
    if not user:
        return

    balance, model, format_value = user
    COST = 10

    if balance < COST:
        await message.answer("❌ Недостаточно средств.")
        await state.clear()
        return

    status = await message.answer("🎨 Генерирую...")

    try:
        result = await generate_image_openrouter(
            prompt=message.text,
            model=model,
            format_value=format_value,
            user_image=None
        )

        if "image_bytes" not in result:
            await status.edit_text("❌ Ошибка генерации.")
            return

        image = Image.open(BytesIO(result["image_bytes"])).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)

        file = BufferedInputFile(buffer.getvalue(), filename="image.jpg")
        sent = await message.answer_photo(file)

        if sent:
            deduct_balance(message.from_user.id, COST)

        new_balance = get_user(message.from_user.id)[0]

        await message.answer(
            f"✨ Готово!\n\n💎 Баланс: {new_balance} кредитов",
            reply_markup=main_menu()
        )

        await state.clear()

        try:
            await status.delete()
        except:
            pass

    except Exception:
        logging.exception("GENERATION ERROR")
        try:
            await status.edit_text("❌ Ошибка генерации.")
        except:
            pass


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
