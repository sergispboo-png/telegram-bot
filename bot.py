import os
import asyncio
import tempfile
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from database import add_user, get_user, update_model, update_format, deduct_balance
from generator import generate_image_openrouter


# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= FSM =================

class Generate(StatesGroup):
    waiting_prompt = State()


# ================= MENUS =================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
    ])


def generate_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Модель", callback_data="model")],
        [InlineKeyboardButton(text="📐 Формат", callback_data="format")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main")]
    ])


def model_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nano-Banana", callback_data="m1")],
        [InlineKeyboardButton(text="Nano-Banana Pro", callback_data="m2")],
        [InlineKeyboardButton(text="SeeDream 4.0", callback_data="m3")],
        [InlineKeyboardButton(text="SeeDream 4.5", callback_data="m4")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
    ])


def format_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1:1", callback_data="f1")],
        [InlineKeyboardButton(text="2:3", callback_data="f2")],
        [InlineKeyboardButton(text="16:9", callback_data="f3")],
        [InlineKeyboardButton(text="Original", callback_data="f4")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="generate")]
    ])


# ================= START =================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    await message.answer("👋 Привет! Выбери действие:", reply_markup=main_menu())


# ================= SAFE EDIT =================

async def safe_edit(callback: CallbackQuery, text, markup):
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=text,
        reply_markup=markup
    )


# ================= MAIN =================

@dp.callback_query(F.data == "main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🏠 Главное меню:", reply_markup=main_menu())
    await callback.answer()


@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback, "LuxRender — AI генерация изображений.", main_menu()))


# ================= GENERATION FLOW =================

@dp.callback_query(F.data == "generate")
async def generate(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Generate.waiting_prompt)
    await callback.answer()
    asyncio.create_task(safe_edit(callback, "🖼 Напишите промпт для генерации:", generate_menu()))


# ================= MODEL =================

MODELS = {
    "m1": "Nano-Banana",
    "m2": "Nano-Banana Pro",
    "m3": "SeeDream 4.0",
    "m4": "SeeDream 4.5",
}

@dp.callback_query(F.data == "model")
async def open_model(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback, "🤖 Выберите модель:", model_menu()))


@dp.callback_query(F.data.in_(MODELS.keys()))
async def set_model(callback: CallbackQuery):
    model_name = MODELS[callback.data]
    update_model(callback.from_user.id, model_name)
    await callback.answer("✅ Модель сохранена")
    asyncio.create_task(
        safe_edit(callback, f"🤖 Вы выбрали модель:\n\n{model_name}\n\nТеперь отправьте промпт:", generate_menu())
    )


# ================= FORMAT =================

FORMATS = {
    "f1": "1:1",
    "f2": "2:3",
    "f3": "16:9",
    "f4": "Original",
}

@dp.callback_query(F.data == "format")
async def open_format(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(safe_edit(callback, "📐 Выберите формат:", format_menu()))


@dp.callback_query(F.data.in_(FORMATS.keys()))
async def set_format(callback: CallbackQuery):
    format_value = FORMATS[callback.data]
    update_format(callback.from_user.id, format_value)
    await callback.answer("✅ Формат сохранён")
    asyncio.create_task(
        safe_edit(callback, f"📐 Вы выбрали формат:\n\n{format_value}\n\nТеперь отправьте промпт:", generate_menu())
    )


# ================= PROMPT =================

@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):

    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        await message.answer("Ошибка пользователя.")
        return

    balance, model, format_value = user
    COST = 10

    # Проверка баланса
    if balance < COST:
        await message.answer(
            f"❌ Недостаточно средств.\nБаланс: {balance}₽\nСтоимость: {COST}₽",
            reply_markup=main_menu()
        )
        await state.clear()
        return

    await message.answer("🎨 Генерирую изображение (10–20 секунд)...")

    # Запрос к OpenRouter
    result = await generate_image_openrouter(
        prompt=message.text,
        model="google/gemini-2.5-flash-image",
        format_value=format_value
    )

    # Если ошибка API — НЕ отправляем огромный JSON в Telegram
    if "error" in result:
        print("OPENROUTER ERROR:", result["error"])  # лог в Railway
        await message.answer("❌ Ошибка генерации. Попробуйте позже.")
        await state.clear()
        return

    try:
        # Сохраняем картинку во временный файл
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(result["image_bytes"])
            tmp_path = tmp.name

        # Отправляем файл
        await message.answer_photo(photo=open(tmp_path, "rb"))

    except Exception as e:
        print("SEND IMAGE ERROR:", e)
        await message.answer("❌ Ошибка отправки изображения.")
        await state.clear()
        return

    # Списываем деньги ТОЛЬКО после успешной отправки
    deduct_balance(user_id, COST)

    new_balance = get_user(user_id)[0]
    await message.answer(f"💰 Остаток: {new_balance}₽")

    await state.clear()


# ================= BALANCE =================

@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    balance_value = user[0] if user else 0
    await callback.answer()
    asyncio.create_task(safe_edit(callback, f"💰 Ваш баланс: {balance_value}₽", main_menu()))


# ================= WEBHOOK =================

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

