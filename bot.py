import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import init_db, save_user_token, get_user_token, delete_user_token
from railway_api import validate_railway_token, deploy_pablo

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("توکن ربات BOT_TOKEN یافت نشد!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class BotStates(StatesGroup):
    waiting_for_token = State()

def get_main_keyboard(has_token: bool):
    if has_token:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 ساخت خودکار پابلو پنل", callback_data="deploy_pablo")],
            [InlineKeyboardButton(text="🔄 تغییر / حذف توکن ریلوی", callback_data="change_token")],
            [InlineKeyboardButton(text=" راهنما", callback_data="help")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 ثبت توکن ریلوی (Railway Token)", callback_data="set_token")],
            [InlineKeyboardButton(text=" راهنما", callback_data="help")]
        ])

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_token = get_user_token(message.from_user.id)
    has_token = bool(user_token)
    
    text = (
        f"سلام {message.from_user.first_name} عزیز! 🌹\n\n"
        "به ربات **نصاب خودکار Pablo Panel روی Railway** خوش آمدید.\n\n"
    )
    if has_token:
        text += "✅ توکن ریلوی شما فعال و آماده به کار است.\nبرای ساخت پنل روی دکمه زیر کلیک کنید:"
    else:
        text += "⚠️ برای شروع، لطفاً ابتدا توکن اکانت Railway خود را ثبت کنید."
        
    await message.answer(text, reply_markup=get_main_keyboard(has_token), parse_mode="Markdown")

@dp.callback_query(F.data == "set_token")
@dp.callback_query(F.data == "change_token")
async def ask_token(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BotStates.waiting_for_token)
    
    text = (
        "🔑 **لطفاً توکن اکانت Railway خود را ارسال کنید:**\n\n"
        "📌 *چگونه توکن بگیرم؟*\n"
        "1. وارد سایت `railway.app` شوید.\n"
        "2. به بخش **Account Settings > Tokens** بروید.\n"
        "3. یک توکن بسازید و مقدار آن را کپی کرده و به همینجا بفرستید."
    )
    await callback.message.edit_text(text, parse_mode="Markdown")

@dp.message(BotStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    status_msg = await message.answer("⏳ در حال بررسی اعتبار توکن ریلوی...")
    
    is_valid, result = await validate_railway_token(token)
    if is_valid:
        save_user_token(message.from_user.id, token)
        await state.clear()
        await status_msg.edit_text(
            f"✅ **توکن با موفقیت تایید و ذخیره شد!**\n👤 ایمیل اکانت: `{result}`\n\nاکنون می‌توانید پنل خود را بسازید.",
            reply_markup=get_main_keyboard(True),
            parse_mode="Markdown"
        )
    else:
        await status_msg.edit_text(
            f"❌ **خطا:** {result}\nلطفاً توکن را بررسی کرده و مجدداً ارسال کنید."
        )

@dp.callback_query(F.data == "deploy_pablo")
async def handle_deploy(callback: types.CallbackQuery):
    user_token = get_user_token(callback.from_user.id)
    if not user_token:
        await callback.answer("ابتدا باید توکن خود را ثبت کنید!", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.edit_text(
        "⏳ **در حال ایجاد پروژه و دیپلوی Pablo Panel روی ریلوی...**\n"
        "لطفاً صبور باشید، این عملیات حدود ۳۰ الی ۶۰ ثانیه طول می‌کشد...",
        parse_mode="Markdown"
    )

    result, err = await deploy_pablo(user_token)
    if err:
        await status_msg.edit_text(
            f"❌ **متأسفانه در ساخت پنل خطایی رخ داد:**\n`{err}`",
            reply_markup=get_main_keyboard(True),
            parse_mode="Markdown"
        )
        return

    success_text = (
        "🎉 **تبریک! پابلو پنل با موفقیت روی ریلوی شما ساخته شد.**\n\n"
        f"🌐 **آدرس پنل:** {result['domain']}\n"
        f"👤 **نام کاربری:** `{result['user']}`\n"
        f"🔑 **رمز عبور:** `{result['pass']}`\n\n"
        "⚠️ *نکته:* حدود ۱ تا ۲ دقیقه طول می‌کشد تا سرور ریلوی کدهای پنل را کامپایل و روشن کند. پس از ۲ دقیقه وارد لینک شوید."
    )
    await status_msg.edit_text(success_text, reply_markup=get_main_keyboard(True), parse_mode="Markdown")

@dp.callback_query(F.data == "help")
async def handle_help(callback: types.CallbackQuery):
    await callback.answer()
    help_text = (
        "📖 **راهنمای ربات:**\n\n"
        "این ربات به صورت مستقیم و امن با استفاده از API رسمی ریلوی، سورس کد پابلو پنل را روی حساب کاربری شما دیپلوی می‌کند.\n\n"
        "تمامی ترافیک و مدیریت روی اکانت خود شما خواهد بود."
    )
    user_token = bool(get_user_token(callback.from_user.id))
    await callback.message.edit_text(help_text, reply_markup=get_main_keyboard(user_token), parse_mode="Markdown")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())