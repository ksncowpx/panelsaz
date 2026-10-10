import os
import re
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from database import (
    init_db, save_user_token, get_user_token, 
    get_all_panels, get_panel_by_id, add_new_panel, 
    delete_panel_by_id, get_total_users, DB_NAME
)
from railway_api import validate_railway_token, deploy_custom_panel

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # آیدی عددی شما به عنوان ادمین

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ماشین وضعیت
class BotStates(StatesGroup):
    waiting_for_token = State()
    waiting_panel_name = State()
    waiting_panel_repo = State()
    waiting_backup_file = State()

def get_main_keyboard(user_id: int, has_token: bool):
    buttons = []
    if has_token:
        buttons.append([InlineKeyboardButton(text="🚀 ساخت پنل روی ریلوی", callback_data="select_panel")])
        buttons.append([InlineKeyboardButton(text="🔄 تغییر / ثبت مجدد توکن", callback_data="set_token")])
    else:
        buttons.append([InlineKeyboardButton(text="🔑 ثبت توکن ریلوی", callback_data="set_token")])
        
    buttons.append([InlineKeyboardButton(text=" راهنما", callback_data="help")])
    
    # دکمه اختصاصی ادمین
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton(text="⚙️ پنل مدیریت (ادمین)", callback_data="admin_panel")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_token = get_user_token(message.from_user.id)
    text = f"سلام {message.from_user.first_name} عزیز! 🌹\nبه ربات هوشمند نصاب پنل‌های Railway خوش آمدید.\nلوکیشن تمامی سرورها: 🇳🇱 هلند (Amsterdam)"
    await message.answer(text, reply_markup=get_main_keyboard(message.from_user.id, bool(user_token)))

# منوی انتخاب پنل برای کاربر
@dp.callback_query(F.data == "select_panel")
async def choose_panel(callback: types.CallbackQuery):
    panels = get_all_panels()
    if not panels:
        await callback.answer("هیچ پنلی در حال حاضر موجود نیست!", show_alert=True)
        return
        
    buttons = []
    for p_id, p_name, _ in panels:
        buttons.append([InlineKeyboardButton(text=p_name, callback_data=f"deploy_{p_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_home")])
    
    await callback.message.edit_text("لطفاً پنل مورد نظر خود را برای نصب انتخاب کنید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# اجرای عملیات دیپلوی پنل انتخابی
@dp.callback_query(F.data.startswith("deploy_"))
async def handle_deploy(callback: types.CallbackQuery):
    panel_id = int(callback.data.split("_")[1])
    panel = get_panel_by_id(panel_id)
    if not panel:
        await callback.answer("پنل یافت نشد!", show_alert=True)
        return
        
    user_token = get_user_token(callback.from_user.id)
    if not user_token:
        await callback.answer("توکن ریلوی ثبت نشده است!", show_alert=True)
        return

    name, repo, def_user, def_pass = panel
    await callback.answer()
    status_msg = await callback.message.edit_text(f"⏳ در حال ساخت و دیپلوی **{name}** روی سرور هلند...\nلطفاً ۳۰ تا ۶۰ ثانیه صبر کنید.", parse_mode="Markdown")

    result, err = await deploy_custom_panel(user_token, repo, def_user, def_pass)
    if err:
        await status_msg.edit_text(f"❌ **خطا:**\n`{err}`", reply_markup=get_main_keyboard(callback.from_user.id, True), parse_mode="Markdown")
        return

    success_text = (
        f"🎉 **پنل {name} با موفقیت ساخته شد!**\n\n"
        f"🌐 **آدرس پنل:** {result['domain']}\n"
        f"👤 **نام کاربری:** `{result['user']}`\n"
        f"🔑 **رمز عبور:** `{result['pass']}`\n"
        f"🇳🇱 **لوکیشن:** هلند (آمستردام)\n\n"
        "⚠️ حدود ۱ تا ۲ دقیقه دیگر وارد لینک پنل شوید تا بیلد کامل شود."
    )
    await status_msg.edit_text(success_text, reply_markup=get_main_keyboard(callback.from_user.id, True), parse_mode="Markdown")

# ----------------- بخش پنل مدیریت ادمین -----------------

@dp.callback_query(F.data == "admin_panel")
async def admin_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("شما دسترسی ادمین ندارید!", show_alert=True)
        return

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن پنل جدید", callback_data="adm_add_panel"),
         InlineKeyboardButton(text="🗑 حذف پنل‌ها", callback_data="adm_delete_panel")],
        [InlineKeyboardButton(text="📥 دانلود فایل بک‌آپ", callback_data="adm_get_backup"),
         InlineKeyboardButton(text="📤 بازیابی بک‌آپ", callback_data="adm_restore_backup")],
        [InlineKeyboardButton(text="📊 آمار کاربران", callback_data="adm_stats"),
         InlineKeyboardButton(text="📖 راهنمای پنل", callback_data="adm_guide")],
        [InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="back_home")]
    ])
    await callback.message.edit_text("👑 **پنل مدیریت پیشرفته سازنده:**", reply_markup=admin_kb, parse_mode="Markdown")

# ۱. دریافت بک‌آپ دیتابیس
@dp.callback_query(F.data == "adm_get_backup")
async def send_backup(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    
    if os.path.exists(DB_NAME):
        backup_file = FSInputFile(DB_NAME, filename="backup_database.db")
        await callback.message.answer_document(
            backup_file, 
            caption="📦 **فایل بک‌آپ دیتابیس ربات شما**\n\nاین فایل را ذخیره کنید تا در صورت جابجایی سرور، به سادگی ربات را بازیابی کنید."
        )
    else:
        await callback.message.answer("❌ دیتابیس فعلاً خالی است یا یافت نشد.")

# ۲. شروع بازیابی بک‌آپ
@dp.callback_query(F.data == "adm_restore_backup")
async def start_restore(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    await state.set_state(BotStates.waiting_backup_file)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="admin_panel")]])
    await callback.message.edit_text(
        "📤 **ارسال فایل دیتابیس:**\n\nلطفاً فایل بک‌آپ قبلی (`backup_database.db`) را به صورت **File / Document** به همینجا بفرستید:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# ۳. پردازش و جایگزینی فایل ارسالی
@dp.message(BotStates.waiting_backup_file, F.document)
async def process_restore_file(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    doc = message.document
    if not (doc.file_name.endswith(".db") or doc.file_name.endswith(".sqlite")):
        await message.answer("❌ فرمت فایل نامعتبر است! لطفاً حتماً فایل با پسوند `.db` بفرستید.")
        return

    # دانلود و جایگزینی دیتابیس
    status_msg = await message.answer("⏳ در حال جایگزینی و بازگردانی اطلاعات دیتابیس...")
    file_info = await bot.get_file(doc.file_id)
    await bot.download_file(file_info.file_path, DB_NAME)
    
    # اعمال تغییرات دیتابیس
    init_db()
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 ورود به پنل ادمین", callback_data="admin_panel")]])
    await status_msg.edit_text("✅ **تبریک! کل اطلاعات و کاربران با موفقیت بازیابی شدند.** 🎉", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_stats")
async def show_stats(callback: types.CallbackQuery):
    total = get_total_users()
    panels = len(get_all_panels())
    await callback.answer(f"📊 آمار ربات:\n👥 کل کاربران: {total}\n📦 تعداد پنل‌ها: {panels}", show_alert=True)

@dp.callback_query(F.data == "adm_guide")
async def show_guide(callback: types.CallbackQuery):
    guide_text = (
        "📖 **راهنمای ساخت پنل‌های سازگار با ریلوی:**\n\n"
        "1. **پابلیک بودن:** ریپازیتوری گیت‌هاب حتماً باید Public باشد.\n"
        "2. **فایل Dockerfile:** پروژه باید داکرفایل داشته باشد که وب‌سرور و هسته Xray را روی پورت `$PORT` مدیریت کند.\n"
        "3. **فرمت آدرس:** موقع وارد کردن ریپازیتوری فقط فرمت `owner/repo` (مثلاً `x4gpanell/SuperJinX`) را بفرستید."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت به منوی ادمین", callback_data="admin_panel")]])
    await callback.message.edit_text(guide_text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_add_panel")
async def add_panel_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    await state.set_state(BotStates.waiting_panel_name)
    await callback.message.edit_text("لطفاً **نام نمایشی پنل** را بفرستید (مثلاً: `🔵 سوپرجینکس`):", parse_mode="Markdown")

@dp.message(BotStates.waiting_panel_name)
async def process_panel_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(panel_name=message.text.strip())
    await state.set_state(BotStates.waiting_panel_repo)
    await message.answer("اکنون **آدرس ریپازیتوری گیت‌هاب** را بفرستید (مثلاً: `x4gpanell/SuperJinX`):")

@dp.message(BotStates.waiting_panel_repo)
async def process_panel_repo(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    repo_input = message.text.strip()
    match = re.search(r"github\.com/([^/]+/[^/]+)", repo_input)
    repo = match.group(1).replace(".git", "") if match else repo_input

    data = await state.get_data()
    add_new_panel(data['panel_name'], repo)
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت به ادمین", callback_data="admin_panel")]])
    await message.answer(f"✅ **پنل جدید با موفقیت اضافه شد!**\n🏷 نام: {data['panel_name']}\n📦 مخزن: `{repo}`", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "adm_delete_panel")
async def list_panels_to_delete(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    panels = get_all_panels()
    buttons = []
    for p_id, p_name, _ in panels:
        buttons.append([InlineKeyboardButton(text=f"❌ حذف {p_name}", callback_data=f"delp_{p_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_panel")])
    await callback.message.edit_text("برای حذف هر پنل، روی آن کلیک کنید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("delp_"))
async def del_panel_confirm(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    p_id = int(callback.data.split("_")[1])
    delete_panel_by_id(p_id)
    await callback.answer("پنل با موفقیت حذف شد!", show_alert=True)
    await admin_menu(callback, None)

# ----------------- بخش توکن و راهنما -----------------

@dp.callback_query(F.data == "set_token")
async def ask_token(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BotStates.waiting_for_token)
    await callback.message.edit_text("🔑 **توکن ریلوی خود را بفرستید:**\n(از بخش Account Settings > Tokens در سایت ریلوی)", parse_mode="Markdown")

@dp.message(BotStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    status_msg = await message.answer("⏳ در حال بررسی توکن...")
    is_valid, result = await validate_railway_token(token)
    if is_valid:
        save_user_token(message.from_user.id, token)
        await state.clear()
        await status_msg.edit_text(f"✅ **توکن تایید شد!**\nایمیل: `{result}`", reply_markup=get_main_keyboard(message.from_user.id, True), parse_mode="Markdown")
    else:
        await status_msg.edit_text(f"❌ **خطا:** {result}\nمجدداً تلاش کنید.")

@dp.callback_query(F.data == "back_home")
async def back_to_main(callback: types.CallbackQuery):
    user_token = bool(get_user_token(callback.from_user.id))
    await callback.message.edit_text("منوی اصلی:", reply_markup=get_main_keyboard(callback.from_user.id, user_token))

@dp.callback_query(F.data == "help")
async def handle_help(callback: types.CallbackQuery):
    await callback.answer()
    text = "📖 **راهنما:**\nاین ربات پنل‌های فیلترشکن را با لوکیشن دیتاسنتر هلند روی اکانت شخصی ریلوی شما می‌سازد."
    user_token = bool(get_user_token(callback.from_user.id))
    await callback.message.edit_text(text, reply_markup=get_main_keyboard(callback.from_user.id, user_token), parse_mode="Markdown")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
