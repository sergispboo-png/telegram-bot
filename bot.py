import hmac
import hashlib
import os
import json
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
WebAppInfo
)
from aiogram.filters import CommandStart, Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

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
redis = Redis.from_url(os.getenv("REDIS_PUBLIC_URL"))

storage = RedisStorage(redis)

dp = Dispatcher(storage=storage)

ERROR_LOG = []
GENERATION_PRICE = 10

GENERATION_QUEUE_KEY = "generation_queue"

# ================= GENERATION QUEUE =================
import asyncio



GENERATION_DELAY = 15
user_generation_times = {}

import time


async def check_generation_queue(user_id):

now = time.time()

last_time = user_generation_times.get(user_id, 0)

if now - last_time < GENERATION_DELAY:
    wait = int(GENERATION_DELAY - (now - last_time))
    return False, wait

user_generation_times[user_id] = now
return True, 0
# бонусы за пополнение
BONUS_TABLE = {
100: 0,
500: 50,
1000: 150,
3000: 500
}

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

text = (
    "ℹ️ <b>О сервисе LuxRender</b>\n\n"
    "LuxRender — это Telegram-бот для генерации изображений "
    "с помощью искусственного интеллекта.\n\n"

    "🖼 <b>Модели для изображений:</b>\n"
    "• Nano Banana — быстрая генерация\n"
    "• Nano Banana Pro — профессиональное качество\n"
    "• SeeDream 4.0 / 4.5 — фотореализм\n\n"

    "✨ <b>Возможности:</b>\n"
    "• Создание изображений по тексту\n"
    "• Редактирование фото\n"
    "• Оживление изображений\n"
    "• Готовые шаблоны промптов\n\n"

    "🔒 <b>Конфиденциальность:</b>\n"
    "Данные хранятся до 24 часов и используются "
    "только для работы сервиса.\n\n"

    "💙 Проект развивается благодаря вашей обратной связи!"
)

keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔒 Политика конфиденциальности",
                web_app=WebAppInfo(
                    url=f"https://{PUBLIC_DOMAIN}/privacy"
                )
            )
        ],
        [
            InlineKeyboardButton(
                text="📄 Пользовательское соглашение",
                web_app=WebAppInfo(
                    url=f"https://{PUBLIC_DOMAIN}/terms"
                )
            )
        ],
        [
            InlineKeyboardButton(
                text="💬 Техническая поддержка",
                url="https://t.me/SantaSpb1"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅ Назад",
                callback_data="back_main"
            )
        ]
    ]
)

await callback.message.edit_text(
    text,
    parse_mode="HTML",
    reply_markup=keyboard
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
# ================= ПОПОЛНЕНИЕ =================

@dp.callback_query(F.data == "topup")
async def topup(callback: CallbackQuery):

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="100₽", callback_data="pay_100")],
    [InlineKeyboardButton(text="500₽ + 50₽ бонус", callback_data="pay_500")],
    [InlineKeyboardButton(text="1000₽ + 150₽ бонус", callback_data="pay_1000")],
    [InlineKeyboardButton(text="3000₽ + 500₽ бонус", callback_data="pay_3000")],
    [InlineKeyboardButton(text="📜 История платежей", callback_data="payments_history")],
    [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
])

await callback.message.edit_text(
    "💰 <b>Пополнение баланса</b>\n\n"
    "Выберите сумму:",
    parse_mode="HTML",
    reply_markup=keyboard
)

await callback.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def create_payment_handler(callback: CallbackQuery):

amount = int(callback.data.split("_")[1])
user_id = callback.from_user.id

payment = create_payment(user_id, amount)

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💳 Оплатить", url=payment["payment_url"])],
    [InlineKeyboardButton(text="⬅ Назад", callback_data="topup")]
])

await callback.message.edit_text(
    f"💳 Пополнение баланса\n\n"
    f"Сумма: {amount}₽\n\n"
    f"Нажмите кнопку ниже для оплаты.",
    reply_markup=keyboard
)

await callback.answer()
@dp.callback_query(F.data == "payments_history")
async def payments_history(callback: CallbackQuery):

from database import conn
cursor = conn.cursor()

cursor.execute(
    "SELECT amount, created_at FROM payments WHERE user_id=? ORDER BY created_at DESC",
    (callback.from_user.id,)
)

payments = cursor.fetchall()

if not payments:
    text = "📜 История платежей пуста."
else:
    text = "📜 <b>История платежей</b>\n\n"

    for amount, date in payments[:10]:
        text += f"💳 {amount}₽ — {date}\n"

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅ Назад", callback_data="topup")]
])

await callback.message.edit_text(
    text,
    parse_mode="HTML",
    reply_markup=keyboard
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

allowed, wait = await check_generation_queue(message.from_user.id)

if not allowed:
    await message.answer(
        f"⏳ Сервер сейчас занят.\n"
        f"Попробуйте снова через {wait} сек."
    )
    return

user_id = message.from_user.id
balance, model, format_value = get_user(user_id)

if balance < GENERATION_PRICE:
    await message.answer(
        "❌ Недостаточно средств.",
        reply_markup=main_menu()
    )
    return
    data = await state.get_data()
user_image = data.get("user_image")

import json

task = {
"chat_id": message.chat.id,
"prompt": message.text,
"model": model,
"format": format_value,
"image": user_image,
"user_id": user_id
}

await redis.rpush(GENERATION_QUEUE_KEY, json.dumps(task))

queue_size = await redis.llen(GENERATION_QUEUE_KEY)

await message.answer(
f"⏳ Запрос добавлен в очередь генерации\n"
f"Ваша позиция: {queue_size}"
)

# ================= АДМИН =================
async def generation_worker():

while True:

    data = await redis.blpop(GENERATION_QUEUE_KEY)

    task = json.loads(data[1])
    chat_id = task["chat_id"]
    prompt = task["prompt"]
    model = task["model"]
    format_value = task["format"]
    user_image = task["image"]
    user_id = task["user_id"]

    try:

        result = None

        # повтор генерации если API временно упал
        for attempt in range(2):

            result = await generate_image_openrouter(
                prompt=prompt,
                model=model,
                format_value=format_value,
                user_image=user_image
            )

            if result and "image_bytes" in result:
                break

        # если генерация не удалась
        if not result or "image_bytes" not in result:

            await message.answer(
                "❌ Ошибка генерации.\nПопробуйте снова.",
                reply_markup=after_generation_menu()
            )

        
            continue

        image = Image.open(BytesIO(result["image_bytes"])).convert("RGB")

        buffer = BytesIO()
        image.save(buffer, format="JPEG")

        file = BufferedInputFile(buffer.getvalue(), filename="image.jpg")

        await bot.send_photo(chat_id, file)

        deduct_balance(user_id, GENERATION_PRICE)
        add_generation(user_id, model)

        new_balance = get_user(user_id)[0]

        await message.answer(
            f"✅ Готово!\n💎 Остаток: {new_balance}₽",
            reply_markup=after_generation_menu()
        )

       
   except Exception as e:

ERROR_LOG.append(str(e))

await bot.send_message(
    chat_id,
    "⚠️ Произошла ошибка генерации.\nПопробуйте снова.",
    reply_markup=after_generation_menu()
)

   
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

asyncio.create_task(generation_worker())


async def on_shutdown(app):
await bot.delete_webhook()
await bot.session.close()

# ================= YOOKASSA WEBHOOK =================

async def yookassa_webhook(request):

body = await request.read()

signature = request.headers.get("Yookassa-Signature")

secret_key = os.getenv("YOOKASSA_SECRET_KEY")

generated_signature = hmac.new(
    secret_key.encode(),
    body,
    hashlib.sha256
).hexdigest()

if signature != generated_signature:
    return web.Response(text="invalid signature", status=403)

data = await request.json()

event = data.get("event")
obj = data.get("object", {})

if event != "payment.succeeded":
    return web.Response(text="ignored")

payment_id = obj["id"]
amount = int(float(obj["amount"]["value"]))
user_id = int(obj["metadata"]["user_id"])

from database import conn, cursor

cursor.execute(
    "SELECT payment_id FROM payments WHERE payment_id=?",
    (payment_id,)
)

exists = cursor.fetchone()

if exists:
    return web.Response(text="already processed")

bonus = BONUS_TABLE.get(amount, 0)
total_amount = amount + bonus

cursor.execute(
    "INSERT INTO payments (payment_id, user_id, amount, status) VALUES (?, ?, ?, ?)",
    (payment_id, user_id, amount, "success")
)

conn.commit()

update_balance(user_id, total_amount)

try:
    await bot.send_message(
        user_id,
        f"💳 <b>Платёж получен!</b>\n\n"
        f"Баланс пополнен на <b>{total_amount}₽</b>\n"
        f"Бонус: <b>{bonus}₽</b>",
        parse_mode="HTML"
    )
except:
    pass

logging.warning(f"Payment success: {user_id} +{total_amount}")

return web.Response(text="OK")

# ================= MINI APP PAGES =================

async def privacy_page(request):
return web.FileResponse("privacy.html")

async def terms_page(request):
return web.FileResponse("terms.html")
# ================= SERVER =================

app = web.Application()

# страницы Mini App
app.router.add_get("/privacy", privacy_page)
app.router.add_get("/terms", terms_page)

# webhook оплаты
app.router.add_post("/yookassa", yookassa_webhook)

# webhook telegram
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
