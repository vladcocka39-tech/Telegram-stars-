
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import config

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class OrderState(StatesGroup):
    waiting_for_receipt = State()


def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Каталог товаров"), KeyboardButton(text="ℹ️ О нас / Помощь")],
            [KeyboardButton(text="👨‍💻 Поддержка")],
        ],
        resize_keyboard=True,
    )


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Добро пожаловать в наш магазин **Telegram Stars & NFT**!\n"
        f"Здесь вы можете быстро приобрести звёзды и цифровые товары с оплатой по СБП / Сбербанк.",
        parse_mode="Markdown",
        reply_markup=main_kb(),
    )


@dp.message(F.text == "ℹ️ О нас / Помощь")
async def process_about(message: types.Message):
    await message.answer(
        "⚡️ **Наш магазин работает в полуавтоматическом режиме.**\n\n"
        "1. Вы выбираете нужный товар из каталога.\n"
        "2. Переводите оплату по СБП на Сбербанк.\n"
        "3. Отправляете скриншот/чек в бота.\n"
        "4. Администратор подтверждает перевод, и товар выдается вам!",
        parse_mode="Markdown",
    )


@dp.message(F.text == "👨‍💻 Поддержка")
async def process_support(message: types.Message):
    await message.answer("По всем вопросам обращайтесь к администратору: @Mr_Farvix_TL")


@dp.message(F.text == "🛒 Каталог товаров")
async def process_catalog(message: types.Message):
    builder = []
    for key, item in config.PRODUCTS.items():
        builder.append(
            [InlineKeyboardButton(text=f"{item['name']} — {item['price']} ₽", callback_data=f"buy_{key}")]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=builder)
    await message.answer("🛒 **Выберите товар для покупки:**", parse_mode="Markdown", reply_markup=kb)


@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    prod_key = callback.data.split("_")[1] + ("_" + callback.data.split("_")[2] if len(callback.data.split("_")) > 2 else "")
    product = config.PRODUCTS.get(prod_key)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await state.update_data(product_name=product["name"], price=product["price"])
    await state.set_state(OrderState.waiting_for_receipt)

    text = (
        f"💳 **Оформление заказа:** {product['name']}\n"
        f"💰 **Сумма к оплате:** `{product['price']} ₽`\n\n"
        f"📌 **Реквизиты для оплаты (Сбербанк / СБП):**\n"
        f"📱 Номер: `{config.SBER_NUMBER}`\n"
        f"👤 Получатель: **{config.SBER_NAME}**\n\n"
        f"⚠️ **ИНСТРУКЦИЯ:**\n"
        f"1. Переведите `{product['price']} ₽` по номеру выше.\n"
        f"2. Пришлите **скриншот чека** или фотографию оплаты прямо в этот чат!"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_order")]]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)


@dp.callback_query(F.data == "cancel_order")
async def cancel_order(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Заказ отменен.")


@dp.message(OrderState.waiting_for_receipt, F.photo | F.document)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prod_name = data.get("product_name")
    price = data.get("price")

    await state.clear()

    await message.answer(
        "✅ **Чек успешно получен и отправлен на проверку!**\n"
        "Ожидайте, администратор проверит перевод и вышлет ваш товар в течение 5-15 минут.",
        parse_mode="Markdown",
    )

    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить и Выдать",
                    callback_data=f"approve_{message.from_user.id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"reject_{message.from_user.id}"
                ),
            ]
        ]
    )

    admin_text = (
        f"🔔 **НОВЫЙ ЗАКАЗ!**\n\n"
        f"👤 Покупатель: @{message.from_user.username or 'без_юзернейма'} (ID: `{message.from_user.id}`)\n"
        f"📦 Товар: **{prod_name}**\n"
        f"💵 Сумма: `{price} ₽`\n\n"
        f"Проверьте приход на карте Сбербанка и нажмите кнопку ниже:"
    )

    if message.photo:
        await bot.send_photo(
            config.ADMIN_ID,
            message.photo[-1].file_id,
            caption=admin_text,
            parse_mode="Markdown",
            reply_markup=admin_kb,
        )
    elif message.document:
        await bot.send_document(
            config.ADMIN_ID,
            message.document.file_id,
            caption=admin_text,
            parse_mode="Markdown",
            reply_markup=admin_kb,
        )


@dp.callback_query(F.data.startswith("approve_"))
async def approve_order(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    try:
        await bot.send_message(
            user_id,
            "🎉 **Ваш платеж успешно подтвержден!**\n\n"
            "Ваш заказ передан в доставку/выдачу. Ожидайте начисления звёзд на ваш аккаунт!",
            parse_mode="Markdown",
        )
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n✅ **ЗАКАЗ ПОДТВЕРЖДЕН И ВЫДАН!**"
        )
    except Exception as e:
        await callback.answer(f"Ошибка при отправке: {e}", show_alert=True)


@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    try:
        await bot.send_message(
            user_id,
            "❌ **Ваш платеж не найден или отклонен.**\n"
            "Пожалуйста, свяжитесь с поддержкой для уточнения: @Mr_Farvix_TL",
            parse_mode="Markdown",
        )
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n❌ **ЗАКАЗ ОТКЛОНЕН!**"
        )
    except Exception as e:
        await callback.answer(f"Ошибка при отправке: {e}", show_alert=True)


async def main():
    print("🚀 Бот успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
