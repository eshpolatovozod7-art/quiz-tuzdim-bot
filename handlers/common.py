import html
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext

from database.db import register_or_update_user, get_user_stats, get_user_quizzes, get_quiz, get_group_leaderboard
from keyboards.inline_keyboards import get_main_menu_keyboard, get_quiz_card_keyboard
from handlers.quiz_play import send_quiz_polls_to_chat

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, command: CommandObject, bot: Bot, state: FSMContext) -> None:
    """Botga start bosilganda yoki deep link orqali test ochilganda."""
    await state.clear()
    user = message.from_user
    if user:
        await register_or_update_user(user.id, user.username, user.first_name)

    # Deep link orqali test ochilgan bo'lsa: /start quiz_abc123 yoki /start poll_abc123
    if command.args and (command.args.startswith("quiz_") or command.args.startswith("q_") or command.args.startswith("poll_")):
        is_direct_poll = command.args.startswith("poll_")
        quiz_id = command.args.replace("quiz_", "").replace("q_", "").replace("poll_", "").strip()
        quiz = await get_quiz(quiz_id)
        if quiz:
            # Agar startgroup=poll_... orqali yoki guruh ichida chaqirilgan bo'lsa, to'g'ridan-to'g'ri so'rovnomalarni tashlash:
            if is_direct_poll or message.chat.type in ["group", "supergroup"]:
                await send_quiz_polls_to_chat(bot, message.chat.id, quiz)
                return

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


@router.message(Command("poll", "quiz"))
async def handle_poll_command(message: Message, command: CommandObject, bot: Bot) -> None:
    """Guruhda yoki shaxsiy chatda testlarni so'rovnoma (Quiz Poll) ko'rinishida chiqarish."""
    if command.args:
        quiz_id = command.args.replace("quiz_", "").replace("poll_", "").replace("q_", "").strip()
        quiz = await get_quiz(quiz_id)
        if quiz:
            await send_quiz_polls_to_chat(bot, message.chat.id, quiz)
            return
        else:
            await message.answer("⚠️ Ushbu ID bo'yicha test topilmadi.")
            return

    user = message.from_user
    if not user:
        return

    quizzes = await get_user_quizzes(user.id, limit=5)
    bot_info = await bot.get_me()

    if not quizzes:
        await message.answer(
            f"⚠️ Siz hali test tuzmagansiz!\n\n"
            f"Avval shaxsiy chatda @{bot_info.username} ga kirib test tuzing, so'ngra bu yerda <code>/poll</code> orqali guruhga tashlashingiz mumkin.",
            parse_mode="HTML",
        )
        return

    keyboard_rows = []
    for q in quizzes:
        q_title = q["title"][:25]
        q_count = q["question_count"]
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"🎯 {q_title} ({q_count} ta)",
                callback_data=f"gpoll:dump:{q['quiz_id']}",
            )
        ])
    keyboard_rows.append([
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="gpoll:cancel")
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(
        f"📋 <b>{html.escape(user.first_name, quote=False)}</b>, qaysi testingizni guruhga tashlamoqchisiz? Tanlang: 👇",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("gpoll:dump:"))
async def handle_gpoll_dump_callback(callback: CallbackQuery, bot: Bot) -> None:
    """Guruhdagi /poll menyusidan tanlangan testni so'rovnoma qilib tashlash."""
    quiz_id = callback.data.split(":")[2]
    quiz = await get_quiz(quiz_id)
    if not quiz:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    await callback.answer("Savollar yuborilmoqda...")
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_quiz_polls_to_chat(bot, callback.message.chat.id, quiz)


@router.callback_query(F.data == "gpoll:cancel")
async def handle_gpoll_cancel_callback(callback: CallbackQuery) -> None:
    """Guruhdagi /poll menyusini bekor qilish."""
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
    await callback.answer("Bekor qilindi")


@router.message(F.new_chat_members)
async def handle_new_chat_members(message: Message, bot: Bot) -> None:
    """Bot guruhga qo'shilganda yo'riqnoma berish."""
    if not message.new_chat_members:
        return
    bot_info = await bot.get_me()
    for new_member in message.new_chat_members:
        if new_member.id == bot_info.id:
            text = (
                "👋 <b>Assalomu alaykum!</b>\n\n"
                "🎯 Men <b>Quiz Tuzdim Bot</b>man. Bu guruhda o'quvchilar va a'zolar uchun qiziqarli viktorinalar (so'rovnomalar) tashlab bera olaman.\n\n"
                "📌 <b>Guruhda qanday ishlatiladi?</b>\n"
                f"1. Shaxsiy chatda @{bot_info.username} ga kirib xohlagan mavzuingizda test tuzing.\n"
                "2. Guruhda <code>/poll</code> buyrug'ini yuboring va testingizni tanlang.\n"
                "3. Bot barcha savollarni to'g'ridan-to'g'ri guruhga <b>Quiz Poll (Viktorina)</b> qilib tashlab beradi!\n\n"
                "<i>Guruh a'zolari hech qanday havolasiz o'z javoblarini tanlab bellashishlari mumkin!</i> 🚀"
            )
            await message.answer(text, parse_mode="HTML")
            break


@router.message(Command("top", "leaderboard"))
async def handle_group_leaderboard(message: Message, bot: Bot) -> None:
    """Guruhdagi testlar bo'yicha eng yuqori natijali ishtirokchilar reytingi."""
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer(
            "ℹ️ <b>Guruh reytingi:</b>\n"
            "Bu buyruq faqat guruhlarda ishlaydi. Botni guruhingizga qo'shib, <code>/poll</code> orqali test tashlang va <code>/top</code> orqali kim eng ko'p ball to'plaganini ko'ring!",
            parse_mode="HTML"
        )
        return

    leaders = await get_group_leaderboard(message.chat.id, limit=10)
    if not leaders:
        await message.answer(
            "📊 <b>Guruhda hali hech kim test yechmagan.</b>\n\n"
            "Guruhga test tashlash uchun: <code>/poll</code> buyrug'ini bering!",
            parse_mode="HTML"
        )
        return

    text = (
        "✦ • ──────────────────── • ✦\n"
        "🏆 <b>GURUH REYTINGI (TOP-10 ISHTIROKCHI)</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
    )
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for idx, l in enumerate(leaders):
        medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
        u_name = html.escape(l["user_name"], quote=False)
        score = l["score"]
        tot = l["total_answered"]
        pct = round((score / tot) * 100) if tot > 0 else 0
        text += f"{medal} <b>{u_name}</b> — <b>{score} ta</b> to'g'ri ({pct}%)\n"

    text += "\n🔥 <i>Viktorinalarda qatnashib, o'z o'rningizni ko'taring!</i>"
    await message.answer(text, parse_mode="HTML")
