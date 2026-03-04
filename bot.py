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
from aiogram.filters import CommandStart, Command
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
from payment import create_payment


# ================= НАСТРОЙКИ =================

TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
CHANNEL_USERNAME = "YourDesignerSpb"
ADMIN_ID = 373830941

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{PUBLIC_DOMAIN}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.WARNING)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ERROR_LOG = []
GENERATION_PRICE = 10


# ================= FSM =================

class Generate(StatesGroup):
    waiting_image = State()
    waiting_prompt = State()


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
        "🚀 Премиальная AI-генерация изображений\n\n"
        "🎨 Создавайте креативы\n"
        "🔥 Улучшайте фотографии\n"
        "💼 Делайте рекламные макеты\n\n"
        "💎 Стоимость — 10₽ за генерацию\n\n"
        "👇 Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# ================= НАВИГАЦИЯ =================
@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    await callback.message.edit_text(
        "✨ <b>LuxRender</b>\n\n"
        "🚀 Премиальная AI-генерация изображений\n\n"
        "🎨 Создавайте креативы\n"
        "🔥 Улучшайте фотографии\n"
        "💼 Делайте рекламные макеты\n\n"
        "💎 Стоимость — 10₽ за генерацию\n\n"
        "👇 Выберите действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

    await callback.answer()



@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ <b>О сервисе LuxRender</b>\n\n"
        "AI-генерация изображений.\n"
        "Стоимость — 10₽.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
        ])
    )
    await callback.answer()


# ================= ЛИЧНЫЙ КАБИНЕТ =================
@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    balance = get_user(user_id)[0]

    from database import conn
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM generations WHERE user_id=?", (user_id,))
    total_generations = cursor.fetchone()[0]

    await callback.message.edit_text(
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: <b>{balance}₽</b>\n"
        f"🎨 Генераций: <b>{total_generations}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
        ])
    )

    await callback.answer()


# ================= ГЕНЕРАЦИЯ =================

@dp.callback_query(F.data == "generate")
async def choose_model(callback: CallbackQuery, state: FSMContext):
    await state.clear()
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


@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):

    user_id = message.from_user.id
    balance, model, format_value = get_user(user_id)

    if balance < GENERATION_PRICE:
        await message.answer("❌ Недостаточно средств.", reply_markup=main_menu())
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
            ERROR_LOG.append(str(result))
            await status.edit_text("❌ Ошибка генерации.", reply_markup=after_generation_menu())
            return

        image = Image.open(BytesIO(result["image_bytes"])).convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="JPEG")

        file = BufferedInputFile(buffer.getvalue(), filename="image.jpg")
        await message.answer_photo(file)

        deduct_balance(user_id, GENERATION_PRICE)
        add_generation(user_id, model)

        new_balance = get_user(user_id)[0]

        await message.answer(
            f"✅ Готово!\n💎 Остаток: {new_balance}₽",
            reply_markup=after_generation_menu()
        )

        await state.clear()

    except Exception as e:
        ERROR_LOG.append(str(e))
        await status.edit_text("❌ Ошибка сервера.", reply_markup=after_generation_menu())


# ================= АДМИН =================

@dp.message(Command("stats"))
async def admin_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = get_users_count()
    generations = get_generations_count()
    payments_count, payments_sum = get_payments_stats()

    await message.answer(
        f"📊 Статистика\n\n"
        f"👥 Пользователей: {users}\n"
        f"🎨 Генераций: {generations}\n"
        f"💳 Платежей: {payments_count}\n"
        f"💰 Доход: {payments_sum}₽"
    )


@dp.message(Command("addbalance"))
async def admin_add_balance(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, user_id, amount = message.text.split()
        update_balance(int(user_id), int(amount))
        await message.answer("Баланс обновлён.")
    except:
        await message.answer("Формат: /addbalance USER_ID СУММА")


@dp.message(Command("broadcast"))
async def admin_broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.replace("/broadcast ", "")
    users = get_all_user_ids()

    sent = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except:
            pass

    await message.answer(f"Рассылка завершена. Отправлено: {sent}")


@dp.message(Command("logs"))
async def admin_logs(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not ERROR_LOG:
        await message.answer("Ошибок нет.")
    else:
        await message.answer("\n".join(ERROR_LOG[-10:]))


# ================= WEBHOOK =================

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
