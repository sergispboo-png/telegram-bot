import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart

import os

TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()

def main_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🖼 Изображение", callback_data="image")],
            [InlineKeyboardButton(text="✨ Генератор промптов", callback_data="prompt")],
            [InlineKeyboardButton(text="👤 Аватар", callback_data="avatar")],
            [
                InlineKeyboardButton(text="👤 Личный кабинет", callback_data="profile"),
                InlineKeyboardButton(text="💰 Пополнить", callback_data="pay")
            ],
            [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")]
        ]
    )
    return keyboard

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет!\n\nВыбери действие:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "image")
async def image(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ]
    )

    await callback.message.edit_text(
        "✍️ Опиши изображение которое хочешь создать:",
        reply_markup=keyboard
    )

    await callback.answer()
@dp.callback_query(F.data == "avatar")
async def avatar(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ]
    )

    await callback.message.edit_text(
        "🧑 Опиши какой аватар ты хочешь:",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data == "pay")
async def pay(callback: CallbackQuery):
    await callback.message.answer("Выбери способ оплаты 💳")
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    await callback.message.answer("Это твой профиль 👤")
    await callback.answer()

async def main():
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())
    @dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    await callback.message.edit_text(
        "👋 Привет!\n\nВыбери действие:",
        reply_markup=main_menu()
    )

    await callback.answer()

