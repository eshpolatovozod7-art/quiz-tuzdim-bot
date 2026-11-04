import asyncio
import html
import logging
import time
from typing import Any
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, PollAnswer, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

from database.db import get_quiz, save_attempt, record_group_answer, update_quiz_timer
from keyboards.inline_keyboards import get_quiz_finish_keyboard, get_change_timer_keyboard, get_quiz_card_keyboard
from services.tts_service import generate_audio_bytes

logger = logging.getLogger(__name__)
router = Router()

# Faol test sessiyalari: session_key (chat_id) -> session_dict
_active_sessions: dict[int, dict[str, Any]] = {}
# poll_id -> session_key
_poll_map: dict[str, int] = {}
# Standalone / Guruh pollari: poll_id -> (chat_id, quiz_id, correct_id)
_group_poll_map: dict[str, tuple[int, str, int]] = {}


@router.callback_query(F.data.startswith("qrun:start:"))
async def handle_start_quiz_run(callback: CallbackQuery, bot: Bot) -> None:
    """Interaktiv testni boshlash."""
    quiz_id = callback.data.split(":")[2]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else user_id
    session_key = chat_id

    await callback.answer("Test boshlanmoqda...")

    quiz = await get_quiz(quiz_id)
    if not quiz or not quiz.get("questions"):
        if callback.message:
            await callback.message.answer("⚠️ Kechirasiz, ushbu test topilmadi yoki o'chirilgan.")
        return

    # Eski sessiya bo'lsa tozalash
    old_session = _active_sessions.get(session_key)
    if old_session:
        task = old_session.get("timeout_task")
        if task and not task.done():
            task.cancel()
        old_pid = old_session.get("current_poll_id")
        if old_pid and old_pid in _poll_map:
            _poll_map.pop(old_pid, None)

    questions = quiz["questions"]
    timer_seconds = quiz.get("timer_seconds", 0)

    _active_sessions[session_key] = {
        "quiz_id": quiz_id,
        "title": quiz["title"],
        "questions": questions,
        "total": len(questions),
        "current_idx": 0,
        "correct_count": 0,
        "wrong_questions": [],
        "timer_seconds": timer_seconds,
        "start_time": time.time(),
        "current_poll_id": None,
        "timeout_task": None,
        "chat_id": chat_id,
        "lock": asyncio.Lock(),
    }

    timer_info = f"⏱ Har bir savolga {timer_seconds} soniya.\n" if timer_seconds > 0 else ""
    escaped_title = html.escape(quiz["title"], quote=False)

    await bot.send_message(
        chat_id=chat_id,
        text=f"🏁 <b>\"{escaped_title}\" testi boshlanmoqda!</b>\n{timer_info}<i>1-savol kelmoqda, diqqat bilan o'qing...</i> 👇",
        parse_mode="HTML",
    )
    await asyncio.sleep(0.5)
    await send_next_question(session_key, bot)


@router.callback_query(F.data.startswith("qrun:next_batch:"))
async def handle_next_batch_quiz(callback: CallbackQuery, bot: Bot) -> None:
    """Shu fayl yoki mavzudan avvalgi savollarni takrorlamasdan keyingi to'plamni tuzish."""
    quiz_id = callback.data.split(":")[2]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else user_id

    quiz = await get_quiz(quiz_id)
    if not quiz:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    await callback.answer("Keyingi yangi to'plam shakllantirilmoqda...")

    source_title = quiz["title"]
    options_count = quiz.get("options_count", 4)
    timer_seconds = quiz.get("timer_seconds", 0)
    difficulty = quiz.get("difficulty", "medium")
    count = quiz.get("question_count", 5)

    status_msg = await bot.send_message(
        chat_id=chat_id,
        text=f"⏳ <b>'{html.escape(source_title, quote=False)}' manbasi bo'yicha yangi, takrorlanmagan testlar tuzilmoqda...</b>\n\n"
             f"<i>Avvalgi savollar chetlatilmoqda...</i>",
        parse_mode="HTML",
    )

    from services.quiz_service import get_user_media, get_offline_quiz_questions
    from database.db import get_user_used_questions, save_quiz
    from keyboards.inline_keyboards import get_quiz_card_keyboard
    from services.gemini_service import GeminiService
    import uuid

    gemini_service = GeminiService()
    cached_media = get_user_media(user_id)
    file_bytes = cached_media.get("bytes") if cached_media else None
    file_mime = cached_media.get("mime") if cached_media else None
    file_name = cached_media.get("name") if cached_media else None
    text_content = cached_media.get("text") if cached_media else None

    used_q = await get_user_used_questions(user_id, source_title)

    questions = await gemini_service.generate_quiz(
        topic=quiz.get("topic") or source_title,
        text_content=text_content,
        file_bytes=file_bytes,
        file_mime=file_mime,
        file_name=file_name,
        count=count,
        options_count=options_count,
        difficulty=difficulty,
        used_questions=used_q,
    )

    if not questions:
        questions = get_offline_quiz_questions(
            quiz.get("topic") or source_title,
            count=count,
            options_count=options_count,
            used_questions=used_q,
        )

    try:
        await status_msg.delete()
    except Exception:
        pass

    if not questions:
        await bot.send_message(chat_id=chat_id, text="❌ Yangi savollar tuzishda xatolik yuz berdi.")
        return

    new_quiz_id = uuid.uuid4().hex[:10]
    await save_quiz(
        quiz_id=new_quiz_id,
        user_id=user_id,
        title=source_title,
        source_type=quiz.get("source_type", "topic"),
        topic=quiz.get("topic", source_title),
        questions=questions,
        options_count=options_count,
        timer_seconds=timer_seconds,
        difficulty=difficulty,
    )

    bot_info = await bot.get_me()
    timer_str = f"{timer_seconds}s" if timer_seconds > 0 else "Cheklovsiz"
    escaped_title = html.escape(source_title, quote=False)
    card_text = (
        f"🎯 <b>\"{escaped_title}\" (Yangi to'plam) testi tayyor!</b>\n"
        f"✦ • ──────────────────── • ✦\n\n"
        f"📊 <b>Savollar soni:</b> {len(questions)} ta (Barchasi yangi)\n"
        f"🔘 <b>Variantlar:</b> {options_count} ta\n"
        f"⏱ <b>Taymer:</b> {timer_str}\n\n"
        f"<i>Boshlash uchun quyidagi tugmani bosing:</i>"
    )
    await bot.send_message(
        chat_id=chat_id,
        text=card_text,
        reply_markup=get_quiz_card_keyboard(new_quiz_id, bot_info.username or "quiz_tuzdimbot", has_media=True),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("qrun:retry_wrong:"))
async def handle_retry_wrong_questions(callback: CallbackQuery, bot: Bot) -> None:
    """Xatolar ustida ishlash: faqat xato belgilangan savollarni qayta topshirish."""
    quiz_id = callback.data.split(":")[2]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else user_id
    session_key = chat_id

    # Avvalgi urinishdagi xato savollarni qidirish
    quiz = await get_quiz(quiz_id)
    if not quiz:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    # Foydalanuvchining oxirgi sessiyasidagi wrong_questions ni tekshiramiz
    wrong_questions = []
    old_session = _active_sessions.get(session_key)
    if old_session and old_session.get("wrong_questions"):
        wrong_questions = old_session["wrong_questions"]

    if not wrong_questions:
        await callback.answer("Xatolar topilmadi yoki barchasi to'g'ri yechilgan!", show_alert=True)
        return

    await callback.answer("Xatolar ustida ishlash boshlandi!")

    timer_seconds = quiz.get("timer_seconds", 0)
    _active_sessions[session_key] = {
        "quiz_id": quiz_id,
        "title": f"{quiz['title']} (Xatolar ustida ishlash)",
        "questions": wrong_questions,
        "total": len(wrong_questions),
        "current_idx": 0,
        "correct_count": 0,
        "wrong_questions": [],
        "timer_seconds": timer_seconds,
        "start_time": time.time(),
        "current_poll_id": None,
        "timeout_task": None,
        "chat_id": chat_id,
        "lock": asyncio.Lock(),
    }

    await bot.send_message(
        chat_id=chat_id,
        text=f"💡 <b>Xatolar ustida ishlash rejimi boshlandi!</b>\n"
             f"Siz adashgan {len(wrong_questions)} ta savol qayta beriladi. Omad! 👇",
        parse_mode="HTML",
    )
    await asyncio.sleep(0.5)
    await send_next_question(session_key, bot)


async def send_quiz_polls_to_chat(bot: Bot, chat_id: int, quiz: dict[str, Any]) -> None:
    """Berilgan chatga (guruh yoki shaxsiy) barcha savollarni Telegram Quiz Poll sifatida yuborish."""
    questions = quiz.get("questions", [])
    if not questions:
        await bot.send_message(chat_id=chat_id, text="⚠️ Test savollari topilmadi.")
        return

    timer_seconds = quiz.get("timer_seconds", 0)
    title = html.escape(quiz.get("title", "Viktorina"), quote=False)

    header_text = (
        "✦ • ──────────────────── • ✦\n"
        f"🎯 <b>VIKTORINA TEST ({len(questions)} TA SAVOL)</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Mavzu:</b> <i>{title}</i>\n\n"
        "⚡️ <i>To'g'ri javoblarni tanlab o'z bilimingizni sinab ko'ring:</i> 👇"
    )
    await bot.send_message(chat_id=chat_id, text=header_text, parse_mode="HTML")

    for idx, q in enumerate(questions, 1):
        q_text = f"[{idx}/{len(questions)}] {q['question']}"
        opts = [str(o)[:100] for o in q.get("options", [])][:10]
        c_id = q.get("correct_id", 0)
        expl = str(q.get("explanation", "")).strip()[:200]

        poll_kwargs = {
            "chat_id": chat_id,
            "question": q_text[:300],
            "options": opts,
            "type": "quiz",
            "correct_option_id": c_id,
            "is_anonymous": False,
        }
        if expl:
            poll_kwargs["explanation"] = expl
        if timer_seconds and 5 <= timer_seconds <= 600:
            poll_kwargs["open_period"] = timer_seconds

        try:
            # Agar Listening audio matni bo'lsa, avval audio/ovozli xabar yuboramiz
            if q.get("audio_text"):
                try:
                    audio_bytes = await generate_audio_bytes(q["audio_text"])
                    if audio_bytes:
                        audio_file = BufferedInputFile(audio_bytes, filename=f"listening_{idx}.mp3")
                        await bot.send_voice(
                            chat_id=chat_id,
                            voice=audio_file,
                            caption=f"🎧 <b>[{idx}/{len(questions)}] Audioni tinglang va javobni tanlang:</b>",
                            parse_mode="HTML",
                        )
                        await asyncio.sleep(0.4)
                except Exception as a_err:
                    logger.warning("Audio jo'natishda xatolik: %s", a_err)

            msg = await bot.send_poll(**poll_kwargs)
            if msg and msg.poll:
                _group_poll_map[msg.poll.id] = (chat_id, quiz.get("quiz_id", ""), c_id)
            await asyncio.sleep(0.35)
        except Exception as e:
            logger.error("Poll yuborishda xatolik: %s", e)

    await bot.send_message(
        chat_id=chat_id,
        text="✨ <b>Barcha test savollari yuborildi! Omad!</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("qrun:dump:"))
async def handle_dump_all_polls(callback: CallbackQuery, bot: Bot) -> None:
    """Barcha testlarni birdaniga ketma-ket yuborish (Guruh yoki shaxsiy uchun)."""
    quiz_id = callback.data.split(":")[2]
    await callback.answer("Barcha savollar yuborilmoqda...")

    quiz = await get_quiz(quiz_id)
    if not quiz or not quiz.get("questions"):
        return

    chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    await send_quiz_polls_to_chat(bot, chat_id, quiz)


async def send_next_question(session_key: int, bot: Bot) -> None:
    """Faol sessiyadagi navbatdagi savolni yuborish."""
    session = _active_sessions.get(session_key)
    if not session:
        return

    idx = session["current_idx"]
    total = session["total"]
    chat_id = session["chat_id"]
    questions = session["questions"]
    timer_seconds = session.get("timer_seconds", 0)

    if idx >= total:
        await finish_quiz(session_key, bot)
        return

    q = questions[idx]
    q_title = f"[{idx + 1}/{total}] {q['question']}"
    opts = [str(o)[:100] for o in q.get("options", [])][:10]
    c_id = q.get("correct_id", 0)
    expl = str(q.get("explanation", "")).strip()[:200]

    stop_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛑 Testni to'xtatish", callback_data="qrun:stop")]]
    )

    poll_kwargs = {
        "chat_id": chat_id,
        "question": q_title[:300],
        "options": opts,
        "type": "quiz",
        "correct_option_id": c_id,
        "is_anonymous": False,
        "reply_markup": stop_kb,
    }
    if expl:
        poll_kwargs["explanation"] = expl
    if timer_seconds and 5 <= timer_seconds <= 600:
        poll_kwargs["open_period"] = timer_seconds

    try:
        if q.get("audio_text"):
            try:
                audio_bytes = await generate_audio_bytes(q["audio_text"])
                if audio_bytes:
                    audio_file = BufferedInputFile(audio_bytes, filename=f"listening_{idx + 1}.mp3")
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=audio_file,
                        caption=f"🎧 <b>[{idx + 1}/{total}] Audioni tinglang va savolga javob bering:</b>",
                        parse_mode="HTML",
                    )
                    await asyncio.sleep(0.4)
            except Exception as a_err:
                logger.warning("Audio jo'natishda xatolik: %s", a_err)

        msg = await bot.send_poll(**poll_kwargs)
        pid = msg.poll.id
        session["current_poll_id"] = pid
        _poll_map[pid] = session_key

        if timer_seconds and 5 <= timer_seconds <= 600:
            session["timeout_task"] = asyncio.create_task(
                _timeout_watcher(session_key, pid, idx, timer_seconds, bot)
            )
    except Exception as e:
        logger.error("Savol yuborishda xatolik: %s", e)
        session["current_idx"] += 1
        if session["current_idx"] < total:
            await send_next_question(session_key, bot)
        else:
            await finish_quiz(session_key, bot)


@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer, bot: Bot) -> None:
    """Foydalanuvchi javob berganda qabul qilish."""
    pid = poll_answer.poll_id

    # 1. Guruhdagi umumiy poll bo'lsa, ballni hisoblab borish
    if pid in _group_poll_map:
        grp_chat_id, grp_quiz_id, correct_id = _group_poll_map[pid]
        user = poll_answer.user
        chosen = poll_answer.option_ids[0] if poll_answer.option_ids else -1
        is_correct = (chosen == correct_id)
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.username or "O'quvchi")
        try:
            await record_group_answer(grp_chat_id, grp_quiz_id, user.id, name, is_correct)
        except Exception as e:
            logger.warning("Guruh ballini yozishda xatolik: %s", e)

    # 2. Interaktiv individual sessiya
    session_key = _poll_map.get(pid)
    if not session_key or session_key not in _active_sessions:
        return

    session = _active_sessions[session_key]
    if session.get("current_poll_id") != pid:
        return

    async with session["lock"]:
        idx = session["current_idx"]
        if idx >= session["total"]:
            return

        task = session.get("timeout_task")
        if task and not task.done():
            task.cancel()

        q = session["questions"][idx]
        chosen = poll_answer.option_ids[0] if poll_answer.option_ids else -1
        correct_id = q.get("correct_id", 0)

        if chosen == correct_id:
            session["correct_count"] += 1
        else:
            session["wrong_questions"].append(q)

        session["current_idx"] += 1

    # Animatsiya va tushuntirishni ko'rish uchun 1.1s pauza
    await asyncio.sleep(1.1)

    if session["current_idx"] < session["total"]:
        await send_next_question(session_key, bot)
    else:
        await finish_quiz(session_key, bot)


async def _timeout_watcher(
    session_key: int,
    poll_id: str,
    expected_idx: int,
    timer_seconds: int,
    bot: Bot,
) -> None:
    """Taymer vaqti tugaganda keyingi savolga o'tkazish."""
    try:
        await asyncio.sleep(timer_seconds + 1.2)
        session = _active_sessions.get(session_key)
        if not session or session.get("current_poll_id") != poll_id:
            return

        async with session["lock"]:
            if session["current_idx"] != expected_idx:
                return
            # Vaqt tugagani uchun xato deb hisoblanadi
            q = session["questions"][expected_idx]
            session["wrong_questions"].append(q)
            session["current_idx"] += 1

        if session["current_idx"] < session["total"]:
            await send_next_question(session_key, bot)
        else:
            await finish_quiz(session_key, bot)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Timeout watcher xatolik: %s", e)


async def finish_quiz(session_key: int, bot: Bot) -> None:
    """Test yakunlanganda umumiy natijalarni hisoblash va chiqarish."""
    session = _active_sessions.pop(session_key, None)
    if not session:
        return

    pid = session.get("current_poll_id")
    if pid and pid in _poll_map:
        _poll_map.pop(pid, None)

    task = session.get("timeout_task")
    if task and not task.done():
        task.cancel()

    quiz_id = session["quiz_id"]
    title = session["title"]
    escaped_title = html.escape(title, quote=False)
    total = session["total"]
    correct = session["correct_count"]
    wrong = max(0, total - correct)
    pct = round((correct / total) * 100) if total > 0 else 0
    elapsed = max(1, round(time.time() - session.get("start_time", time.time())))
    mins, secs = divmod(elapsed, 60)
    time_str = f"{mins} daqiqa {secs} soniya" if mins > 0 else f"{secs} soniya"

    if pct >= 90:
        grade = "🏆 A'lo daraja! (Mukammal bilim)"
    elif pct >= 70:
        grade = "🥇 Yaxshi natija! (Katta muvaffaqiyat)"
    elif pct >= 50:
        grade = "🥈 Qoniqarli! (Yana ozroq mashq qiling)"
    else:
        grade = "🥉 Qoniqarsiz (Yana o'rganib qayta topshiring)"

    # Urinishni bazaga saqlash
    chat_id = session["chat_id"]
    try:
        await save_attempt(
            quiz_id=quiz_id,
            user_id=chat_id,
            correct_count=correct,
            total_count=total,
            time_spent_seconds=elapsed,
            wrong_questions=session["wrong_questions"],
        )
    except Exception as e:
        logger.error("Attempt saqlashda xatolik: %s", e)

    has_wrong = len(session["wrong_questions"]) > 0

    result_text = (
        f"🏁 <b>\"{escaped_title}\" testi yakunlandi!</b>\n\n"
        f"📊 <b>Natijangiz:</b>\n"
        f"✅ To'g'ri javoblar: <b>{correct} ta</b> ({pct}%)\n"
        f"❌ Noto'g'ri javoblar: <b>{wrong} ta</b>\n"
        f"⏱ Sarflangan vaqt: <b>{time_str}</b>\n"
        f"🎖 Baho: <b>{grade}</b>\n\n"
        f"<i>Quyidagi tugmalar orqali xatolar ustida ishlashingiz yoki test varaqasini yuklab olishingiz mumkin:</i>"
    )

    bot_info = await bot.get_me()
    await bot.send_message(
        chat_id=chat_id,
        text=result_text,
        reply_markup=get_quiz_finish_keyboard(
            quiz_id,
            has_wrong=has_wrong,
            bot_username=bot_info.username or "quiz_tuzdimbot",
            correct=correct,
            total=total,
            percentage=pct,
        ),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "qrun:stop")
async def handle_stop_quiz(callback: CallbackQuery, bot: Bot) -> None:
    """Testni to'xtatish."""
    session_key = callback.message.chat.id if callback.message else callback.from_user.id
    session = _active_sessions.pop(session_key, None)
    await callback.answer("Test to'xtatildi")

    if not session:
        return

    pid = session.get("current_poll_id")
    if pid and pid in _poll_map:
        _poll_map.pop(pid, None)

    task = session.get("timeout_task")
    if task and not task.done():
        task.cancel()

    escaped_title = html.escape(session["title"], quote=False)
    correct = session["correct_count"]
    total = session["total"]
    current = session["current_idx"]
    quiz_id = session["quiz_id"]

    text = (
        f"🛑 <b>\"{escaped_title}\" testi to'xtatildi!</b>\n\n"
        f"📊 Ishlangan savollar: <b>{current} / {total} ta</b>\n"
        f"✅ To'g'ri javoblar: <b>{correct} ta</b>\n\n"
        f"<i>Xohlasangiz testni boshidan qayta boshlashingiz mumkin:</i>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Boshidan boshlash", callback_data=f"qrun:start:{quiz_id}")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:home")],
        ]
    )
    if callback.message:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


# ---------------- Taymerni O'zgartirish (Edit Timer) ---------------- #

@router.callback_query(F.data.startswith("qedit:tm:"))
async def handle_edit_timer_start(callback: CallbackQuery) -> None:
    """Mavjud testning taymerini o'zgartirish oynasini ochish."""
    quiz_id = callback.data.split(":")[2]
    quiz = await get_quiz(quiz_id)
    if not quiz:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    cur_timer = quiz.get("timer_seconds", 0)
    cur_str = "Cheklovsiz (Vaqt belgilanmagan)" if cur_timer == 0 else f"{cur_timer} soniya"
    title = html.escape(quiz.get("title", "Test"), quote=False)

    text = (
        f"⏱ <b>«{title}» testi taymerini o'zgartirish:</b>\n\n"
        f"Joriy vaqt chegarasi: <b>{cur_str}</b>\n\n"
        "<i>Har bir savol uchun yangi vaqt chegarasini tanlang:</i> 👇"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_change_timer_keyboard(quiz_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("qsettm:"))
async def handle_save_new_timer(callback: CallbackQuery, bot: Bot) -> None:
    """Yangi tanlangan taymerni bazada saqlash va kartochkani yangilash."""
    parts = callback.data.split(":")
    quiz_id = parts[1]
    new_tm = int(parts[2])

    await update_quiz_timer(quiz_id, new_tm)

    tm_str = "Cheklovsiz" if new_tm == 0 else f"{new_tm} soniya"
    await callback.answer(f"Taymer muvaffaqiyatli {tm_str}ga almashtirildi! ✅", show_alert=True)

    quiz = await get_quiz(quiz_id)
    if not quiz:
        return

    bot_info = await bot.get_me()
    clean_title = html.escape(quiz.get("title", "Test"), quote=False)
    diff = {"easy": "Oson", "medium": "O'rta", "hard": "Qiyin", "olympiad": "Olimpiada"}.get(quiz.get("difficulty", "medium"), "O'rta")
    count = quiz.get("question_count", len(quiz.get("questions", [])))

    card_text = (
        f"🎯 <b>\"{clean_title}\" testi (Taymer yangilandi ✅)</b>\n"
        f"✦ • ──────────────────── • ✦\n\n"
        f"📊 <b>Savollar soni:</b> {count} ta\n"
        f"🔘 <b>Variantlar:</b> {quiz.get('options_count', 4)} ta\n"
        f"⏱ <b>Taymer:</b> <b>{tm_str}</b> ⚡️\n"
        f"🎚 <b>Qiyinlik:</b> {diff}\n\n"
        f"💡 <i>Ushbu testni yangilangan taymer bilan yechishingiz, chop etish uchun PDF qilib yuklab olishingiz yoki guruhlarga ulashishingiz mumkin:</i>"
    )
    if callback.message:
        await callback.message.edit_text(
            card_text,
            reply_markup=get_quiz_card_keyboard(quiz_id, bot_info.username or "quiz_tuzdimbot"),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("qsettm_back:"))
async def handle_cancel_timer_change(callback: CallbackQuery, bot: Bot) -> None:
    """Taymerni o'zgartirishni bekor qilib kartochkaga qaytish."""
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    if not quiz:
        return

    bot_info = await bot.get_me()
    clean_title = html.escape(quiz.get("title", "Test"), quote=False)
    tm = quiz.get("timer_seconds", 0)
    tm_str = "Cheklovsiz" if tm == 0 else f"{tm} soniya"
    diff = {"easy": "Oson", "medium": "O'rta", "hard": "Qiyin", "olympiad": "Olimpiada"}.get(quiz.get("difficulty", "medium"), "O'rta")
    count = quiz.get("question_count", len(quiz.get("questions", [])))

    card_text = (
        f"🎯 <b>\"{clean_title}\" testi</b>\n"
        f"✦ • ──────────────────── • ✦\n\n"
        f"📊 <b>Savollar soni:</b> {count} ta\n"
        f"🔘 <b>Variantlar:</b> {quiz.get('options_count', 4)} ta\n"
        f"⏱ <b>Taymer:</b> {tm_str}\n"
        f"🎚 <b>Qiyinlik:</b> {diff}\n\n"
        f"💡 <i>Ushbu testni boshlashingiz yoki guruhlarga ulashishingiz mumkin:</i>"
    )
    if callback.message:
        await callback.message.edit_text(
            card_text,
            reply_markup=get_quiz_card_keyboard(quiz_id, bot_info.username or "quiz_tuzdimbot"),
            parse_mode="HTML",
        )
    await callback.answer()

