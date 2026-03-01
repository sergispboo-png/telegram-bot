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

# ================== ЛОГИ (ЧИСТЫЕ) ==================

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

MODEL_NAMES = {
    "nano": "Nano Banana",
    "pro": "Nano Banana Pro",
    "seedream": "SeeDream"
}

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
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
    model_key = callback.data.split("_")[1]
    update_model(callback.from_user.id, "google/gemini-2.5-flash-image")
    await state.update_data(selected_model=model_key)
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

# ================== ПОЛУЧЕНИЕ ФОТО ==================

@dp.message(Generate.waiting_image)
async def receive_image(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    downloaded = await bot.download_file(file.file_path)

    image_bytes = downloaded.read()
    image_base64 = base64.b64encode(image_bytes).decode()

    await state.update_data(user_image=image_base64)
    await message.answer("✍ Теперь напишите промпт:")
    await state.set_state(Generate.waiting_prompt)

# ================== ГЕНЕРАЦИЯ ==================

@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):
    if not await require_subscription(message.from_user.id, message):
        return

    user_id = message.from_user.id
    user = get_user(user_id)
    balance, model, format_value = user
    COST = 10

    if balance < COST:
        await message.answer("❌ Недостаточно средств.")
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

        if "image_bytes" not in result:
            await status.edit_text("❌ Ошибка генерации.")
            return

        image = Image.open(BytesIO(result["image_bytes"])).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)

        file = BufferedInputFile(buffer.getvalue(), filename="image.jpg")
        await message.answer_photo(file)

        deduct_balance(user_id, COST)
        add_generation(user_id, model)

        new_balance = get_user(user_id)[0]

        await message.answer(
            f"✅ Готово!\n💎 Баланс: {new_balance}",
            reply_markup=after_generation_menu()
        )

        await state.set_state(Generate.editing)

    except Exception as e:
        ERROR_LOG.append(str(e))
        await status.edit_text("❌ Ошибка генерации.")

# ================== АДМИН ==================

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

# ================== ERROR HANDLER ==================

@dp.errors()
async def global_error_handler(event, exception):
    ERROR_LOG.append(str(exception))
    return True

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
