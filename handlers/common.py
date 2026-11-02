import html
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext

from database.db import register_or_update_user, get_user_stats, get_user_quizzes, get_quiz
from keyboards.inline_keyboards import get_main_menu_keyboard, get_quiz_card_keyboard

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, bot: Bot, state: FSMContext) -> None:
    """Botga start bosilganda yoki deep link orqali test ochilganda."""
    await state.clear()
    user = message.from_user
    if user:
        await register_or_update_user(user.id, user.username, user.first_name)

    # Deep link orqali test ochilgan bo'lsa: /start quiz_abc123
    if command.args and (command.args.startswith("quiz_") or command.args.startswith("q_")):
        quiz_id = command.args.replace("quiz_", "").replace("q_", "").strip()
        quiz = await get_quiz(quiz_id)
        if quiz:
            bot_info = await bot.get_me()
            title = html.escape(quiz["title"], quote=False)
            count = quiz["question_count"]
            timer = f"{quiz['timer_seconds']}s" if quiz.get("timer_seconds", 0) > 0 else "Cheklovsiz"
            diff = {"easy": "Oson", "medium": "O'rta", "hard": "Qiyin", "olympiad": "Olimpiada"}.get(quiz.get("difficulty", "medium"), "O'rta")

            text = (
                f"🎲 <b>\"{title}\" testi</b>\n\n"
                f"📊 <b>Savollar soni:</b> {count} ta\n"
                f"🔘 <b>Variantlar:</b> {quiz.get('options_count', 4)} ta\n"
                f"⏱ <b>Taymer:</b> {timer}\n"
                f"🎚 <b>Daraja:</b> {diff}\n\n"
                f"<i>Quyidagi tugmalar orqali testni boshlashingiz yoki yuklab olishingiz mumkin:</i>"
            )
            await message.answer(
                text=text,
                reply_markup=get_quiz_card_keyboard(quiz_id, bot_info.username or "quiz_tuzdimbot"),
                parse_mode="HTML",
            )
            return

    first_name = html.escape(user.first_name if user else "Foydalanuvchi")
    text = (
        f"Assalomu alaykum, <b>{first_name}</b>! 👋\n\n"
        f"🎯 <b>Quiz Tuzdim Bot</b> ga xush kelibsiz!\n"
        f"Bu bot orqali siz sun'iy intellekt (Gemini AI) yordamida har qanday manbadan professional test (viktorina)lar tuza olasiz.\n\n"
        f"✨ <b>Imkoniyatlar:</b>\n"
        f"• 🎲 Har qanday mavzu yoki fandan test tuzish\n"
        f"• 📁 <b>PDF, Word (DOCX), TXT</b> darsliklardan test olish\n"
        f"• 🎥 <b>Video darsliklar</b> (ko'rib/eshitib test tuzadi)\n"
        f"• 🎙 <b>Ovozli xabar va audio ma'ruzalar</b>\n"
        f"• 📸 <b>Doska, konspekt va kitob sahifalari fotosi</b>\n"
        f"• 📄 <b>Chop etishga tayyor A4 PDF va Word</b> varaqasi\n"
        f"• 🔄 Xatolar ustida qayta ishlash va natijalar tahlili\n\n"
        f"Quyidagi menyudan kerakli bo'limni tanlang: 👇"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.message(Command("help"))
@router.callback_query(F.data == "menu:help")
async def handle_help(event: Message | CallbackQuery) -> None:
    """Yordam va yo'riqnoma."""
    text = (
        "📖 <b>Quiz Tuzdim Bot — Qo'llanma:</b>\n\n"
        "1️⃣ <b>Test tuzishning 5 xil yo'li:</b>\n"
        "• <b>Mavzu bo'yicha:</b> Shunchaki fanni yoki mavzuni yozing (masalan: <i>Kvadrat tenglamalar</i> yoki <i>Python OOP</i>).\n"
        "• <b>Hujjat tashlash:</b> Botga PDF yoki Word fayl yuboring — bot hujjat mazmunidan test tuzib beradi.\n"
        "• <b>Video tashlash:</b> Video darslik yuboring — bot videoni ko'rib va tushunib savollar tuzadi.\n"
        "• <b>Audio / Ovoz:</b> Ovozli xabar yoki mp3 audio yuboring — bot eshitib test tayyorlaydi.\n"
        "• <b>Rasm tashlash:</b> Kitob yoki konspekt rasmini tashlang.\n\n"
        "2️⃣ <b>Chop etish uchun PDF / Word:</b>\n"
        "Test tayyor bo'lgach, 'PDF test varaqasi' tugmasini bosing. Bot maktab va oliygohlarga mos A4 formatdagi chiroyli test varaqasi va oxirida javoblar kalitini taqdim etadi!\n\n"
        "3️⃣ <b>Xatolar ustida ishlash:</b>\n"
        "Test yechish yakunida agar xato javoblar bo'lsa, bot sizga faqat adashgan savollaringizdan qayta imtihon olish imkonini beradi."
    )
    kb = get_main_menu_keyboard()
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "menu:home")
async def handle_home(callback: CallbackQuery, state: FSMContext) -> None:
    """Bosh menyuga qaytish."""
    await state.clear()
    await callback.answer()
    text = (
        "🏠 <b>Asosiy menyu</b>\n\n"
        "Qanday manbadan test tuzmoqchisiz yoki qaysi bo'limga o'tmoqchisiz? Tanlang: 👇"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:stats")
async def handle_stats(callback: CallbackQuery) -> None:
    """Foydalanuvchi statistikasi."""
    await callback.answer()
    stats = await get_user_stats(callback.from_user.id)
    mins, secs = divmod(stats["total_time"], 60)
    time_str = f"{mins} daqiqa {secs} soniya" if mins > 0 else f"{secs} soniya"

    text = (
        "📊 <b>Sizning shaxsiy statistikangiz:</b>\n\n"
        f"🎯 Tuzilgan testlar soni: <b>{stats['tests_created']} ta</b>\n"
        f"📝 Ishlangan testlar: <b>{stats['tests_taken']} marta</b>\n"
        f"📈 O'rtacha o'zlashtirish foizi: <b>{stats['avg_score']}%</b>\n"
        f"⏱ Jami sarflangan vaqt: <b>{time_str}</b>\n\n"
        f"<i>O'z ustingizda ishlashda davom eting!</i> 💪"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:history")
async def handle_history(callback: CallbackQuery, bot: Bot) -> None:
    """Foydalanuvchi tuzgan oxirgi testlar ro'yxati."""
    await callback.answer()
    quizzes = await get_user_quizzes(callback.from_user.id, limit=5)
    if not quizzes:
        text = (
            "📜 <b>Siz hali birorta ham test tuzmadingiz.</b>\n\n"
            "Bosh menyuga qaytib, o'zingiz xohlagan mavzuda birinchi testingizni tuzing!"
        )
        if callback.message:
            await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
        return

    text = "📜 <b>Sizning oxirgi tuzgan testlaringiz:</b>\n\n"
    for idx, q in enumerate(quizzes, 1):
        title = html.escape(q["title"], quote=False)
        count = q["question_count"]
        timer = f"{q.get('timer_seconds', 0)}s" if q.get("timer_seconds", 0) > 0 else "Cheklovsiz"
        text += f"{idx}. <b>{title}</b> ({count} ta savol, ⏱ {timer})\n"
        text += f"   👉 Qayta boshlash: /start quiz_{q['quiz_id']}\n\n"

    text += "<i>Istalgan test linkini bosib qayta yechishingiz yoki ulashishingiz mumkin!</i>"
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
