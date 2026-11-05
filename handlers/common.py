import html
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext

from database.db import register_or_update_user, get_user_stats, get_user_quizzes, get_quiz, get_group_leaderboard
from keyboards.inline_keyboards import get_main_menu_keyboard, get_quiz_card_keyboard, get_back_to_menu_keyboard
from handlers.quiz_play import send_quiz_polls_to_chat, send_group_quiz_lobby, format_quiz_ready_text

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
            # Agar startgroup=poll_... orqali yoki guruh ichida chaqirilgan bo'lsa:
            if message.chat.type in ["group", "supergroup"]:
                await send_group_quiz_lobby(bot, message.chat.id, quiz)
                return
            elif is_direct_poll:
                await send_quiz_polls_to_chat(bot, message.chat.id, quiz)
                return

            bot_info = await bot.get_me()
            bot_username = bot_info.username or "quiz_tuzdimbot"
            text = format_quiz_ready_text(quiz, bot_username=bot_username, is_group=False)
            await message.answer(
                text=text,
                reply_markup=get_quiz_card_keyboard(quiz_id, bot_username=bot_username, is_group=False),
                parse_mode="HTML",
            )
            return

    # Deep link orqali 1 vs 1 duelga kirilgan bo'lsa: /start duel_abc123
    if command.args and command.args.startswith("duel_"):
        duel_id = command.args.replace("duel_", "").strip()
        from database.db import get_duel
        duel = await get_duel(duel_id)
        if duel:
            creator_name = html.escape(duel["creator_name"], quote=False)
            topic = html.escape(duel["topic"], quote=False)
            duel_text = (
                "⚔️ <b>1 vs 1 DUEL CHORLOVI!</b>\n\n"
                f"👤 <b>{creator_name}</b> sizni «<b>{topic}</b>» bo'yicha 5 ta savolli jangga chorladi!\n\n"
                "⚡️ Har bir savolga 20 soniya beriladi. Kim ko'proq to'g'ri topsa va tezroq ishlasa, o'sha g'olib bo'ladi!\n\n"
                "Jangga tayyormisiz? 👇"
            )
            duel_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="▶️ Jangga kirishish ⚔️", callback_data=f"duel:play:{duel_id}")],
                    [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="menu:home")],
                ]
            )
            await message.answer(duel_text, reply_markup=duel_kb, parse_mode="HTML")
            return

    first_name = html.escape(user.first_name if user else "Foydalanuvchi")
    text = (
        f"Assalomu alaykum, <b>{first_name}</b>! 👋\n\n"
        f"🎯 <b>Quiz Tuzdim Bot</b> — Telegramda tezkor va sifatli test tuzish yordamchingiz.\n\n"
        f"👇 <b>Kerakli bo'limni tanlang:</b>"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.message(Command("help"))
@router.callback_query(F.data == "menu:help")
async def handle_help(event: Message | CallbackQuery) -> None:
    """Yordam va yo'riqnoma."""
    text = (
        "📖 <b>Quiz Tuzdim Bot — Foydalanish Qo'llanmasi:</b>\n\n"
        "1️⃣ <b>Test tuzish:</b>\n"
        "• <b>🎲 Test tuzish</b> tugmasini bosing yoki <code>/newquiz</code> buyrug'ini yuboring.\n"
        "• <b>Mavzu bo‘yicha:</b> Shunchaki mavzu/fanni yozing, AI testni o‘zi tuzadi.\n"
        "• <b>Manba orqali:</b> PDF, Word, rasm, audio yoki havola yuboring, AI manba asosida tuzadi.\n\n"
        "2️⃣ <b>Testni boshlash va ishlash:</b>\n"
        "• Test kartochkasi chiqqach <b>«Men tayyorman!»</b> tugmasini bosing.\n"
        "• Testni to‘xtatish uchun <code>/stop</code> buyrug‘ini yuboring.\n\n"
        "3️⃣ <b>Do'stlarga va guruhga ulashish:</b>\n"
        "• Test tugagach <b>«Do'stlarga ulashish»</b> tugmasi orqali testni istalgan do'st yoki guruhga yuborishingiz mumkin!"
    )
    kb = get_back_to_menu_keyboard()
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
        "👇 <b>Kerakli bo'limni tanlang:</b>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.message(Command("stats"))
@router.message(F.text.lower().in_(["statistika", "mening statistikam", "statistika 📊", "📊 mening statistikam"]))
@router.callback_query(F.data == "menu:stats")
async def handle_stats(event: Message | CallbackQuery) -> None:
    """Foydalanuvchi statistikasi."""
    user = event.from_user
    if not user:
        return
    if isinstance(event, CallbackQuery):
        await event.answer()

    stats = await get_user_stats(user.id)
    mins, secs = divmod(stats["total_time"], 60)
    time_str = f"{mins} daqiqa {secs} soniya" if mins > 0 else f"{secs} soniya"

    text = (
        "📊 <b>Sizning shaxsiy statistikangiz:</b>\n\n"
        f"🎯 Tuzilgan testlar soni: <b>{stats['tests_created']} ta</b>\n"
        f"📝 Ishlangan testlar: <b>{stats['tests_taken']} marta</b>\n"
        f"📈 O'rtacha o'zlashtirish: <b>{stats['avg_score']}%</b>\n"
        f"⏱ Jami sarflangan vaqt: <b>{time_str}</b>\n\n"
        f"<i>O'z ustingizda ishlashda davom eting!</i> 💪"
    )
    kb = get_back_to_menu_keyboard()
    if isinstance(event, CallbackQuery) and event.message:
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("tests", "myquizzes", "quizzes", "history"))
@router.message(F.text.lower().in_(["mening testlarim", "testlarim", "mening testlarim 📜", "📜 mening testlarim"]))
@router.callback_query(F.data == "menu:history")
async def handle_history(event: Message | CallbackQuery, bot: Bot) -> None:
    """Foydalanuvchi tuzgan oxirgi testlar ro'yxati (Tugmalar bilan)."""
    user = event.from_user
    if not user:
        return
    if isinstance(event, CallbackQuery):
        await event.answer()

    quizzes = await get_user_quizzes(user.id, limit=8)
    if not quizzes:
        text = (
            "📜 <b>Siz hali birorta ham test tuzmadingiz.</b>\n\n"
            "«Test tuzish» tugmasi orqali birinchi testingizni yarating!"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎲 Test tuzish", callback_data="menu:create")],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="menu:home")],
            ]
        )
        if isinstance(event, CallbackQuery) and event.message:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    text = (
        "📜 <b>Siz tuzgan testlar ro'yxati:</b>\n\n"
        "<i>Testni boshlash uchun quyidagilardan birini tanlang:</i> 👇"
    )

    rows = []
    for idx, q in enumerate(quizzes, 1):
        title = q["title"][:26]
        count = q["question_count"]
        tm = q.get("timer_seconds", 0)
        tm_str = "Cheksiz" if tm == 0 else f"{tm}s"
        rows.append([
            InlineKeyboardButton(
                text=f"{idx}. 🎯 {title} ({count} ta, ⏱ {tm_str})",
                callback_data=f"qopen:{q['quiz_id']}",
            )
        ])

    rows.append([
        InlineKeyboardButton(text="🎲 Test tuzish", callback_data="menu:create"),
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="menu:home"),
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if isinstance(event, CallbackQuery) and event.message:
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("qopen:"))
async def handle_open_saved_quiz(callback: CallbackQuery, bot: Bot) -> None:
    """Tarixdan tanlangan test kartochkasini to'liq ochish."""
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    if not quiz:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    await callback.answer()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or "quiz_tuzdimbot"
    card_text = format_quiz_ready_text(quiz, bot_username=bot_username, is_group=False)
    if callback.message:
        await callback.message.edit_text(
            text=card_text,
            reply_markup=get_quiz_card_keyboard(quiz_id, bot_username=bot_username, is_group=False),
            parse_mode="HTML",
        )


@router.message(Command("poll", "quiz"))
async def handle_poll_command(message: Message, command: CommandObject, bot: Bot) -> None:
    """Guruhda yoki shaxsiy chatda testlarni so'rovnoma (Quiz Poll) ko'rinishida chiqarish."""
    if command.args:
        quiz_id = command.args.replace("quiz_", "").replace("poll_", "").replace("q_", "").strip()
        quiz = await get_quiz(quiz_id)
        if quiz:
            if message.chat.type in ["group", "supergroup"]:
                await send_group_quiz_lobby(bot, message.chat.id, quiz)
            else:
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

    await callback.answer("Tanlandi...")
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
        if callback.message.chat.type in ["group", "supergroup"]:
            await send_group_quiz_lobby(bot, callback.message.chat.id, quiz)
        else:
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
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Natijalarni Excelda yuklab olish", callback_data=f"gexp:excel:{message.chat.id}")],
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("excel"))
async def handle_excel_command(message: Message, bot: Bot) -> None:
    """Guruhdagi natijalarni Excel qilish buyrug'i."""
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("ℹ️ Ushbu buyruq faqat Telegram guruhlarida ishlaydi.")
        return

    from database.db import get_group_quiz_results_for_excel
    from services.excel_service import generate_quiz_results_excel
    from aiogram.types import BufferedInputFile

    results = await get_group_quiz_results_for_excel(message.chat.id)
    if not results:
        await message.answer("⚠️ Guruhda hali natijalar mavjud emas.")
        return

    chat_title = message.chat.title or "Guruh"
    try:
        excel_bytes = generate_quiz_results_excel("Guruh Testi", results, chat_title)
        filename = f"Natijalar_{message.chat.id}_{int(time.time()) % 10000}.xlsx"
        file = BufferedInputFile(excel_bytes, filename=filename)
        caption = f"📊 <b>{html.escape(chat_title, quote=False)}</b> guruhining test natijalari hisoboti (Excel)"
        await message.answer_document(file, caption=caption, parse_mode="HTML")
    except Exception as e:
        await message.answer("❌ Excel hisobot yaratishda xatolik yuz berdi.")
