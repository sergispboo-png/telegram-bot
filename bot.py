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
    get_all_user_ids,
    set_balance,
    add_generation,
    get_generations_count,
    get_top_users,
    get_payments_stats,
)

from generator import generate_image_openrouter


# ================= CONFIG ================= #

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}{WEBHOOK_PATH}"

CHANNEL_USERNAME = "@YourDesignerSpb"
CHANNEL_URL = "https://t.me/YourDesignerSpb"

ADMINS = [123456789]  # ВСТАВЬ СВОЙ TELEGRAM ID


bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================= HEALTH CHECK ================= #

async def health(request):
    return web.Response(text="Bot is running")


# ================= SUBSCRIPTION ================= #

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


def subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")]
    ])


async def require_subscription(user_id: int, message_obj):
    if not await check_subscription(user_id):
        await message_obj.answer(
            "❗ Для использования функций бота необходимо подписаться на канал.",
            reply_markup=subscribe_keyboard()
        )
        return False
    return True


# ================= ADMIN CHECK ================= #

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


# ================= FSM ================= #

class Generate(StatesGroup):
    waiting_image = State()
    waiting_prompt = State()
    editing = State()


# ================= UI ================= #

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="generate")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="📢 TG канал", url=CHANNEL_URL)],
    ])


# ================= START ================= #

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):

    await state.clear()

    user = get_user(message.from_user.id)

    if not user:
        add_user(message.from_user.id)
        users_count = get_users_count()

        banner = BufferedInputFile(
            open("banner.jpg", "rb").read(),
            filename="banner.jpg"
        )

        caption = (
            "✨ <b>LuxRender</b>\n\n"
            "Премиальная AI-генерация изображений.\n\n"
            f"👥 Уже <b>{users_count}</b> пользователей\n\n"
            "🚀 Нажмите «Сгенерировать изображение», чтобы начать."
        )

        await message.answer_photo(
            banner,
            caption=caption,
            parse_mode="HTML"
        )

    await message.answer("🏠 Главное меню", reply_markup=main_menu())


# ================= SUB CHECK ================= #

@dp.callback_query(F.data == "check_sub")
async def confirm_sub(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.answer("✅ Подписка подтверждена")
        await callback.message.delete()
    else:
        await callback.answer("❌ Вы ещё не подписались", show_alert=True)


# ================= GENERATE FLOW ================= #

@dp.callback_query(F.data == "generate")
async def generate_start(callback: CallbackQuery, state: FSMContext):

    if not await require_subscription(callback.from_user.id, callback.message):
        return

    await callback.message.edit_text("✍ Напишите промпт:")
    await state.set_state(Generate.waiting_prompt)
    await callback.answer()


@dp.message(Generate.waiting_prompt)
async def process_prompt(message: Message, state: FSMContext):

    if not await require_subscription(message.from_user.id, message):
        return

    user_id = message.from_user.id
    user = get_user(user_id)

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
            deduct_balance(user_id, COST)
            add_generation(user_id, model)

        new_balance = get_user(user_id)[0]

        await message.answer(
            f"✨ Готово!\n💎 Баланс: {new_balance}",
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


# ================= ADMIN ================= #

@dp.message(F.text == "/stats")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    users = get_users_count()
    generations = get_generations_count()
    payments_count, payments_sum = get_payments_stats()

    await message.answer(
        "📊 <b>LuxRender — Статистика</b>\n\n"
        f"👥 Пользователей: {users}\n"
        f"🎨 Генераций: {generations}\n"
        f"💳 Платежей: {payments_count}\n"
        f"💰 Доход: {payments_sum} ₽",
        parse_mode="HTML"
    )


@dp.message(F.text == "/top")
async def admin_top_users(message: Message):
    if not is_admin(message.from_user.id):
        return

    top_users = get_top_users()

    text = "🏆 <b>ТОП пользователей:</b>\n\n"

    for i, (user_id, count) in enumerate(top_users, start=1):
        text += f"{i}. ID {user_id} — {count} генераций\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text.startswith("/addbalance"))
async def admin_add_balance(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, user_id, amount = message.text.split()
        update_balance(int(user_id), int(amount))
        await message.answer("✅ Баланс начислен")
    except:
        await message.answer("❌ Формат: /addbalance user_id amount")


@dp.message(F.text.startswith("/setbalance"))
async def admin_set_balance(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, user_id, amount = message.text.split()
        set_balance(int(user_id), int(amount))
        await message.answer("✅ Баланс установлен")
    except:
        await message.answer("❌ Формат: /setbalance user_id amount")


@dp.message(F.text.startswith("/broadcast"))
async def admin_broadcast(message: Message):
    if not is_admin(message.from_user.id):
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

    await message.answer(f"📢 Отправлено {sent} пользователям")


# ================= WEBHOOK ================= #

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)


async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()


app = web.Application()
app.router.add_get("/", health)

SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
