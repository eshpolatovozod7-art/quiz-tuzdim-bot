import asyncio
import html
import logging
import time
from typing import Any
from aiogram import Router, F, Bot
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Message,
    PollAnswer,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)

from database.db import get_quiz, save_attempt, record_group_answer, update_quiz_timer, get_last_quiz_attempt
from keyboards.inline_keyboards import get_quiz_finish_keyboard, get_change_timer_keyboard, get_quiz_card_keyboard
from services.tts_service import generate_audio_bytes

logger = logging.getLogger(__name__)
router = Router()

# Faol test sessiyalari: session_key (chat_id) -> session_dict
_active_sessions: dict[int, dict[str, Any]] = {}
# Oxirgi yakunlangan xato savollar kesh (Xatolar ustida ishlash tugmasi uchun): chat_id -> list[dict]
_last_completed_wrong_questions: dict[int, list[dict[str, Any]]] = {}
# poll_id -> session_key
_poll_map: dict[str, int] = {}
# Standalone / Guruh pollari: poll_id -> (chat_id, quiz_id, correct_id, start_time)
_group_poll_map: dict[str, tuple] = {}
# Faol guruh viktorinalari: chat_id -> dict
_group_active_quizzes: dict[int, dict[str, Any]] = {}


def prepare_poll_options(raw_options: list[Any], correct_id: int) -> tuple[list[str], int]:
    """Variantlarni tozalash, takrorlarini chetlatish va to'g'ri indeksni saqlash."""
    seen = set()
    cleaned_opts = []
    new_c_id = 0

    for idx, opt in enumerate(raw_options):
        opt_str = str(opt).strip()[:100]
        if not opt_str:
            opt_str = f"Variant {len(cleaned_opts) + 1}"
        if opt_str in seen:
            opt_str = f"{opt_str} ({len(cleaned_opts) + 1})"
        seen.add(opt_str)
        if idx == correct_id:
            new_c_id = len(cleaned_opts)
        cleaned_opts.append(opt_str)

    while len(cleaned_opts) < 2:
        extra = f"Variant {len(cleaned_opts) + 1}"
        cleaned_opts.append(extra)

    cleaned_opts = cleaned_opts[:10]
    if not (0 <= new_c_id < len(cleaned_opts)):
        new_c_id = 0

    return cleaned_opts, new_c_id


def format_quiz_ready_text(
    quiz: dict[str, Any],
    bot_username: str = "quiz_tuzdimbot",
    is_group: bool = False,
) -> str:
    """Telegram @QuizBot formatidagi test tayyorgarlik va kartochka xabari."""
    title = html.escape(quiz.get("title", "Test"), quote=False)
    questions = quiz.get("questions", [])
    count = quiz.get("question_count", len(questions))
    tm = quiz.get("timer_seconds", 15)
    tm_str = f"{tm} soniya" if (tm and tm > 0) else "15 soniya"
    quiz_id = quiz.get("quiz_id", "")
    share_link = f"https://t.me/{bot_username}?start=quiz_{quiz_id}" if quiz_id else ""

    diff = quiz.get("difficulty", "medium")
    diff_labels = {
        "easy": "🟢 Oson (Boshlang'ich)",
        "medium": "🟡 O'rta (Standart)",
        "hard": "🔴 Qiyin (Murakkab)",
        "olympiad": "🏆 Olimpiada (Ekspert)",
    }
    diff_str = diff_labels.get(diff, "🟡 O'rta (Standart)")
    opts_cnt = quiz.get("options_count")
    opts_str = f" · 🔘 {opts_cnt} variantli" if opts_cnt else ""

    if is_group:
        return (
            f"🎲 <b>“{title}” testiga tayyorlaning</b>\n\n"
            f"🗡 {count} ta savol{opts_str}\n"
            f"🎚 Qiyinlik darajasi: {diff_str}\n"
            f"⏱ Har bir savol uchun {tm_str}\n"
            f"🏛 Ovozlar test egasiga ko‘rinadigan bo‘ladi\n\n"
            f"🏁 Tayyor bo‘lganingizda quyidagi tugmani bosing.\n"
            f"Uni to‘xtatish uchun /stop buyrug‘ini yuboring."
        )

    link_section = f"\n\n🔗 <b>Test havolasi (boshqalarga ulashish uchun):</b>\n<code>{share_link}</code>" if share_link else ""
    return (
        f"🎲 <b>“{title}”</b>\n\n"
        f"🗡 {count} ta savol{opts_str}\n"
        f"🎚 Qiyinlik darajasi: {diff_str}\n"
        f"⏱ Guruhda: {tm_str} · Shaxsiyda: Cheklovsiz\n"
        f"🏛 Ovozlar test egasiga ko‘rinadigan bo‘ladi"
        f"{link_section}\n\n"
        f"<i>Testni boshlash, do‘stlarga ulashish yoki guruhga qo‘shish uchun quyidagi tugmalardan foydalaning:</i> 👇"
    )


def format_quiz_single_ready_text(quiz: dict[str, Any], bot_username: str = "quiz_tuzdimbot") -> str:
    """Yakka tartibda ishlayotganda (vaqt cheklovisiz) tayyorgarlik xabari."""
    title = html.escape(quiz.get("title", "Test"), quote=False)
    questions = quiz.get("questions", [])
    count = quiz.get("question_count", len(questions))
    quiz_id = quiz.get("quiz_id", "")
    share_link = f"https://t.me/{bot_username}?start=quiz_{quiz_id}" if quiz_id else ""
    link_section = f"\n\n🔗 <b>Test havolasi (ulashish uchun):</b>\n<code>{share_link}</code>" if share_link else ""

    diff = quiz.get("difficulty", "medium")
    diff_labels = {
        "easy": "🟢 Oson (Boshlang'ich)",
        "medium": "🟡 O'rta (Standart)",
        "hard": "🔴 Qiyin (Murakkab)",
        "olympiad": "🏆 Olimpiada (Ekspert)",
    }
    diff_str = diff_labels.get(diff, "🟡 O'rta (Standart)")
    opts_cnt = quiz.get("options_count")
    opts_str = f" · 🔘 {opts_cnt} variantli" if opts_cnt else ""

    return (
        f"🎲 <b>“{title}” testiga tayyorlaning</b>\n\n"
        f"🗡 {count} ta savol{opts_str}\n"
        f"🎚 Qiyinlik darajasi: {diff_str}\n"
        f"⏱ O‘z sur’atingizda (savol belgilanishi bilan keyingisiga o‘tadi)\n"
        f"🏛 Ovozlar test egasiga ko‘rinadigan bo‘ladi"
        f"{link_section}\n\n"
        f"🏁 Tayyor bo‘lganingizda quyidagi tugmani bosing.\n"
        f"Uni to‘xtatish uchun /stop buyrug‘ini yuboring."
    )


@router.message(Command("stop"))
async def handle_stop_command(message: Message, bot: Bot) -> None:
    """Testni to'xtatish (/stop)."""
    chat_id = message.chat.id

    # Guruhda bo'lsa
    if message.chat.type in ["group", "supergroup"]:
        active = _group_active_quizzes.get(chat_id)
        if active:
            active["cancelled"] = True
            active["is_running"] = False
            ev = active.get("advance_event")
            if ev and not ev.is_set():
                ev.set()
            task = active.get("task")
            if task and not task.done():
                task.cancel()
            _group_active_quizzes.pop(chat_id, None)
            await message.answer("🛑 <b>Test to'xtatildi.</b>", parse_mode="HTML")
            return
        await message.answer("ℹ️ Hozirda guruhda faol test mavjud emas.")
        return

    # Shaxsiy chatda bo'lsa
    session_key = chat_id
    if session_key in _active_sessions:
        session = _active_sessions.pop(session_key, None)
        if session:
            task = session.get("timeout_task")
            if task and not task.done():
                task.cancel()
            pid = session.get("current_poll_id")
            if pid and pid in _poll_map:
                _poll_map.pop(pid, None)
        await message.answer("🛑 <b>Test to'xtatildi.</b>", parse_mode="HTML")
    else:
        await message.answer("ℹ️ Hozirda faol test mavjud emas.")


@router.callback_query(F.data.startswith("play_quiz:"))
async def handle_play_quiz_alias(callback: CallbackQuery, bot: Bot) -> None:
    """play_quiz callback aliasini qayta ishlash."""
    quiz_id = callback.data.split(":")[1]
    quiz = await get_quiz(quiz_id)
    if not quiz:
        await callback.answer("⚠️ Kechirasiz, ushbu test topilmadi.", show_alert=True)
        return

    text = format_quiz_single_ready_text(quiz)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Men tayyorman!", callback_data=f"qrun:start:{quiz_id}")]
        ]
    )
    if callback.message:
        await callback.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("qrun:ready:"))
async def handle_quiz_run_ready(callback: CallbackQuery, bot: Bot) -> None:
    """Test boshlashdan oldin @QuizBot kabi yagona 'Men tayyorman!' ekranini ko'rsatish."""
    quiz_id = callback.data.split(":")[2]
    quiz = await get_quiz(quiz_id)
    if not quiz:
        await callback.answer("⚠️ Kechirasiz, ushbu test topilmadi.", show_alert=True)
        return

    text = format_quiz_single_ready_text(quiz)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Men tayyorman!", callback_data=f"qrun:start:{quiz_id}")]
        ]
    )
    if callback.message:
        await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("qrun:start:"))
async def handle_start_quiz_run(callback: CallbackQuery, bot: Bot) -> None:
    """Interaktiv testni boshlash."""
    quiz_id = callback.data.split(":")[2]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else user_id
    session_key = chat_id

    quiz = await get_quiz(quiz_id)
    if not quiz or not quiz.get("questions"):
        if callback.message:
            await callback.message.answer("⚠️ Kechirasiz, ushbu test topilmadi yoki o'chirilgan.")
        return

    await callback.answer("Boshlanmoqda...")

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

    title_clean = html.escape(quiz.get("title", "Test"), quote=False)
    for count in [3, 2, 1]:
        try:
            await callback.message.edit_text(
                f"⏳ <b>“{title_clean}”</b>\n\n"
                f"Tayyorlaning: <b>{count}...</b> 🔔",
                parse_mode="HTML"
            )
            await asyncio.sleep(1.0)
        except Exception:
            pass

    try:
        await callback.message.edit_text(
            "🚀 <b>Ketdik! 1-savol kelmoqda...</b>",
            parse_mode="HTML"
        )
        await asyncio.sleep(0.5)
    except Exception:
        pass

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
            text_content=text_content,
        )
    elif len(questions) < count:
        needed = count - len(questions)
        import re
        used_now = (used_q or set()) | {re.sub(r"^\[\d+/\d+\]\s*", "", q["question"]).strip().lower() for q in questions}
        extra = get_offline_quiz_questions(
            quiz.get("topic") or source_title,
            count=needed,
            options_count=options_count,
            used_questions=used_now,
            text_content=text_content,
        )
        questions.extend(extra[:needed])

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
    bot_username = bot_info.username or "quiz_tuzdimbot"
    new_quiz_obj = {
        "quiz_id": new_quiz_id,
        "title": f"{source_title} (Yangi to'plam)",
        "questions": questions,
        "question_count": len(questions),
        "timer_seconds": timer_seconds,
    }
    card_text = format_quiz_ready_text(new_quiz_obj, bot_username=bot_username, is_group=False)
    await bot.send_message(
        chat_id=chat_id,
        text=card_text,
        reply_markup=get_quiz_card_keyboard(new_quiz_id, bot_username=bot_username, is_group=False),
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

    if not wrong_questions and session_key in _last_completed_wrong_questions:
        wrong_questions = _last_completed_wrong_questions[session_key]

    if not wrong_questions:
        attempt = await get_last_quiz_attempt(quiz_id, user_id)
        if attempt and attempt.get("wrong_questions"):
            wrong_questions = attempt["wrong_questions"]

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
        q_text = f"[{idx}/{len(questions)}] {q['question']}"[:300]
        opts, c_id = prepare_poll_options(q.get("options", []), q.get("correct_id", 0))
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

            msg = None
            try:
                msg = await bot.send_poll(**poll_kwargs)
            except Exception as pe:
                if "anonymous" in str(pe).lower() or "channel" in str(pe).lower():
                    poll_kwargs["is_anonymous"] = True
                    msg = await bot.send_poll(**poll_kwargs)
                else:
                    raise pe
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


async def send_group_quiz_lobby(bot: Bot, chat_id: int, quiz: dict[str, Any]) -> None:
    """Guruhga @QuizBot kabi yagona 'Men tayyorman!' kartasini yuborish."""
    quiz_id = quiz["quiz_id"]
    bot_info = await bot.get_me()
    bot_username = bot_info.username or "quiz_tuzdimbot"
    text = format_quiz_ready_text(quiz, bot_username=bot_username, is_group=True)
    kb = get_quiz_card_keyboard(quiz_id, bot_username=bot_username, is_group=True)
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("qgrp:start:"))
async def handle_group_quiz_start(callback: CallbackQuery, bot: Bot) -> None:
    """Guruhda QuizBot kabi testni boshlash va teskari hisobni (countdown) yoqish."""
    chat_id = callback.message.chat.id
    quiz_id = callback.data.split(":")[2]
    user = callback.from_user

    active = _group_active_quizzes.get(chat_id)
    if active and active.get("is_running"):
        task = active.get("task")
        if task and not task.done():
            # Test allaqachon ketayotgan bo'lsa, bosgan foydalanuvchini ishtirokchilar safiga qo'shamiz
            active.setdefault("participants", set()).add(user.id)
            await callback.answer("Siz ham viktorinaga qo'shildingiz! 🎮")
            return
        else:
            _group_active_quizzes.pop(chat_id, None)

    quiz = await get_quiz(quiz_id)
    if not quiz or not quiz.get("questions"):
        await callback.answer("⚠️ Kechirasiz, ushbu test topilmadi.", show_alert=True)
        return

    await callback.answer("Viktorina boshlanmoqda! 🏁")

    title_clean = html.escape(quiz.get("title", "Viktorina"), quote=False)
    # 3... 2... 1... Countdown
    for count in [3, 2, 1]:
        try:
            await callback.message.edit_text(
                f"⏳ <b>“{title_clean}”</b>\n\n"
                f"Tayyorlaning: <b>{count}...</b> 🔔",
                parse_mode="HTML"
            )
            await asyncio.sleep(1.0)
        except Exception:
            pass

    try:
        await callback.message.edit_text(
            f"🚀 <b>Ketdik! 1-savol kelmoqda...</b>",
            parse_mode="HTML"
        )
        await asyncio.sleep(0.5)
    except Exception:
        pass

    session = {
        "quiz_id": quiz_id,
        "title": quiz.get("title", "Viktorina"),
        "is_running": True,
        "cancelled": False,
        "current_poll_id": None,
        "current_msg_id": None,
        "initiator_id": user.id,
        "participants": {user.id},
        "answered_users": set(),
        "advance_event": asyncio.Event(),
        "scores": {},
    }
    _group_active_quizzes[chat_id] = session

    task = asyncio.create_task(run_group_quiz_loop(chat_id, quiz, bot, session))
    session["task"] = task


@router.callback_query(F.data.startswith("qgrp:cancel:"))
async def handle_group_quiz_cancel(callback: CallbackQuery, bot: Bot) -> None:
    """Guruhdagi viktorinani bekor qilish yoki to'xtatish."""
    chat_id = callback.message.chat.id
    user = callback.from_user

    active = _group_active_quizzes.get(chat_id)
    if active:
        is_initiator = (user.id == active.get("initiator_id"))
        is_admin = False
        try:
            member = await bot.get_chat_member(chat_id, user.id)
            if member.status in ["administrator", "creator"]:
                is_admin = True
        except Exception:
            pass

        if not (is_initiator or is_admin):
            await callback.answer("❌ Viktorinani faqat admin yoki uni boshlagan shaxs to'xtata oladi!", show_alert=True)
            return

        active["cancelled"] = True
        active["is_running"] = False
        ev = active.get("advance_event")
        if ev and not ev.is_set():
            ev.set()
        task = active.get("task")
        if task and not task.done():
            task.cancel()

        current_msg_id = active.get("current_msg_id")
        if current_msg_id:
            try:
                await bot.stop_poll(chat_id=chat_id, message_id=current_msg_id)
            except Exception:
                pass

        _group_active_quizzes.pop(chat_id, None)
        await callback.message.answer("🛑 <b>Guruhdagi viktorina to'xtatildi.</b>", parse_mode="HTML")
        await callback.answer("Viktorina to'xtatildi.")
    else:
        try:
            await callback.message.edit_text("❌ <b>Viktorina bekor qilindi.</b>", parse_mode="HTML")
        except Exception:
            pass
        await callback.answer("Bekor qilindi.")


async def _trigger_group_advance(session: dict[str, Any], delay: float = 0.8) -> None:
    """Ishtirokchilar javob bergach, Telegram animatsiyasi ko'rinishi uchun ozgina kutib keyingi savolga o'tkazish."""
    try:
        await asyncio.sleep(delay)
        event = session.get("advance_event")
        if event and not event.is_set():
            event.set()
    except Exception:
        pass


async def run_group_quiz_loop(chat_id: int, quiz: dict[str, Any], bot: Bot, session: dict[str, Any]) -> None:
    """Guruhda savollarni sinxron ketma-ket yuboruvchi worker."""
    questions = quiz.get("questions", [])
    if not questions:
        await bot.send_message(chat_id=chat_id, text="⚠️ Test savollari topilmadi.")
        return

    quiz_id = quiz.get("quiz_id", "")
    timer_seconds = quiz.get("timer_seconds", 30)
    if not (5 <= timer_seconds <= 600):
        timer_seconds = 30

    total = len(questions)

    try:
        for idx, q in enumerate(questions, 1):
            if session.get("cancelled") or not session.get("is_running"):
                break

            session["answered_users"] = set()
            session["advance_event"] = asyncio.Event()

            # Listening audio bo'lsa
            if q.get("audio_text"):
                try:
                    audio_bytes = await generate_audio_bytes(q["audio_text"])
                    if audio_bytes:
                        audio_file = BufferedInputFile(audio_bytes, filename=f"listening_{idx}.mp3")
                        await bot.send_voice(
                            chat_id=chat_id,
                            voice=audio_file,
                            caption=f"🎧 <b>[{idx}/{total}] Audioni tinglang va javobni tanlang:</b>",
                            parse_mode="HTML",
                        )
                        await asyncio.sleep(0.5)
                except Exception as a_err:
                    logger.warning("Guruh audiosida xatolik: %s", a_err)

            q_text = f"[{idx}/{total}] {q['question']}"[:300]
            opts, c_id = prepare_poll_options(q.get("options", []), q.get("correct_id", 0))
            expl = str(q.get("explanation", "")).strip()[:200]

            poll_kwargs = {
                "chat_id": chat_id,
                "question": q_text[:300],
                "options": opts,
                "type": "quiz",
                "correct_option_id": c_id,
                "is_anonymous": False,
                "open_period": timer_seconds,
            }
            if expl:
                poll_kwargs["explanation"] = expl

            msg = None
            for attempt in range(2):
                try:
                    msg = await bot.send_poll(**poll_kwargs)
                    break
                except Exception as pe:
                    if "anonymous" in str(pe).lower() or "channel" in str(pe).lower():
                        poll_kwargs["is_anonymous"] = True
                    logger.warning("Guruhda poll jo'natishda xatolik (%d-urinish): %s", attempt + 1, pe)
                    await asyncio.sleep(1.0)

            if not msg or not msg.poll:
                logger.error("Guruhda savol jo'natib bo'lmadi [%d/%d], keyingisiga o'tilmoqda", idx, total)
                continue

            session["current_poll_id"] = msg.poll.id
            session["current_msg_id"] = msg.message_id
            _group_poll_map[msg.poll.id] = (chat_id, quiz_id, c_id, time.time())

            # Barcha ishtirokchilar javob berishini yoki taymer tugashini kutish
            try:
                await asyncio.wait_for(session["advance_event"].wait(), timeout=timer_seconds)
            except asyncio.TimeoutError:
                pass

            if session.get("cancelled") or not session.get("is_running"):
                break

            try:
                await bot.stop_poll(chat_id=chat_id, message_id=msg.message_id)
            except Exception:
                pass

            if idx < total:
                await asyncio.sleep(0.8)

        if not session.get("cancelled") and session.get("is_running"):
            await finish_group_quiz(chat_id, quiz, bot, session)

    except asyncio.CancelledError:
        logger.info("Guruh viktorinasi bekor qilindi: %d", chat_id)
    except Exception as e:
        logger.exception("Guruh viktorinasi siklida xatolik: %s", e)
    finally:
        _group_active_quizzes.pop(chat_id, None)


async def finish_group_quiz(chat_id: int, quiz: dict[str, Any], bot: Bot, session: dict[str, Any]) -> None:
    """Guruhdagi viktorina yakunlanganda jonli reyting (Leaderboard) chiqarish."""
    quiz_id = quiz.get("quiz_id", "")
    title = html.escape(quiz.get("title", "Viktorina"), quote=False)
    total = len(quiz.get("questions", []))
    scores_dict = session.get("scores", {})

    if not scores_dict:
        finish_text = (
            f"🏁 <b>“{title}” viktorinasi yakunlandi!</b>\n\n"
            f"📊 Jami savollar: {total} ta\n"
            f"<i>Hech kim savollarga javob bermadi.</i>"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Do'stlarga ulashish", switch_inline_query=f"quiz_{quiz_id}")]
            ]
        )
        await bot.send_message(chat_id=chat_id, text=finish_text, reply_markup=kb, parse_mode="HTML")
        return

    sorted_players = sorted(
        scores_dict.values(),
        key=lambda p: (-p["score"], p["total_time"])
    )

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []
    for i, p in enumerate(sorted_players[:10]):
        rank_icon = medals[i] if i < len(medals) else f"{i+1}."
        p_name = html.escape(p["name"], quote=False)
        p_score = p["score"]
        p_time = round(p["total_time"], 1)
        lines.append(f"{rank_icon} <b>{p_name}</b> — <b>{p_score}/{total}</b> ball ({p_time}s)")

    leaderboard_str = "\n".join(lines)
    winner_name = sorted_players[0]["name"]

    finish_text = (
        f"🏆 <b>“{title}” viktorinasi yakunlandi!</b>\n\n"
        f"📊 Savollar: {total} ta | 👥 Ishtirokchilar: {len(sorted_players)} nafar\n\n"
        f"<b>Ishtirokchilar natijalari:</b>\n"
        f"{leaderboard_str}\n\n"
        f"<i>Barcha ishtirokchilarga rahmat!</i> 🎉"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Do'stlarga ulashish", switch_inline_query=f"quiz_{quiz_id}")
            ]
        ]
    )
    await bot.send_message(chat_id=chat_id, text=finish_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("qcard:more:"))
async def handle_quiz_card_more(callback: CallbackQuery, bot: Bot) -> None:
    """Test kartochkasidagi qo'shimcha menyuni ochish."""
    quiz_id = callback.data.split(":")[2]
    quiz = await get_quiz(quiz_id)
    title = quiz.get("title", "") if quiz else ""
    b_id = quiz.get("batch_id") if quiz else None
    back_cb = f"history:batch:{b_id}:1" if b_id else "menu:history"
    bot_info = await bot.get_me()
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_quiz_card_keyboard(
                quiz_id,
                bot_info.username or "quiz_tuzdimbot",
                full_menu=True,
                title=title,
                back_callback=back_cb,
            )
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("qcard:less:"))
async def handle_quiz_card_less(callback: CallbackQuery, bot: Bot) -> None:
    """Test kartochkasidagi qisqa (chalg'itmaydigan) menyuga qaytish."""
    quiz_id = callback.data.split(":")[2]
    quiz = await get_quiz(quiz_id)
    title = quiz.get("title", "") if quiz else ""
    b_id = quiz.get("batch_id") if quiz else None
    back_cb = f"history:batch:{b_id}:1" if b_id else "menu:history"
    bot_info = await bot.get_me()
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_quiz_card_keyboard(
                quiz_id,
                bot_info.username or "quiz_tuzdimbot",
                full_menu=False,
                title=title,
                back_callback=back_cb,
            )
        )
    except Exception:
        pass
    await callback.answer()


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
    q_title = f"[{idx + 1}/{total}] {q['question']}"[:300]
    opts, c_id = prepare_poll_options(q.get("options", []), q.get("correct_id", 0))
    expl = str(q.get("explanation", "")).strip()[:200]

    poll_kwargs = {
        "chat_id": chat_id,
        "question": q_title[:300],
        "options": opts,
        "type": "quiz",
        "correct_option_id": c_id,
        "is_anonymous": False,
    }
    if expl:
        poll_kwargs["explanation"] = expl

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

        old_pid = session.get("current_poll_id")
        if old_pid and old_pid in _poll_map:
            _poll_map.pop(old_pid, None)

        msg = await bot.send_poll(**poll_kwargs)
        pid = msg.poll.id
        session["current_poll_id"] = pid
        _poll_map[pid] = session_key
        logger.info("Savol [%d/%d] muvaffaqiyatli yuborildi: poll_id=%s (chat_id=%s)", idx + 1, total, pid, chat_id)
    except Exception as e:
        logger.exception("Savol yuborishda xatolik: %s", e)
        session["current_idx"] += 1
        if session["current_idx"] < total:
            await send_next_question(session_key, bot)
        else:
            await finish_quiz(session_key, bot)


@router.poll_answer(lambda pa: pa.poll_id in _poll_map or pa.poll_id in _group_poll_map)
async def handle_poll_answer(poll_answer: PollAnswer, bot: Bot) -> None:
    """Foydalanuvchi javob berganda qabul qilish."""
    try:
        pid = poll_answer.poll_id
        if pid not in _poll_map and pid not in _group_poll_map:
            raise SkipHandler()

        user = poll_answer.user
        user_id = user.id if user else 0
        name = "Ishtirokchi"
        if user:
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.username or "Ishtirokchi")
        chosen = poll_answer.option_ids[0] if poll_answer.option_ids else -1
        logger.info("handle_poll_answer qabul qilindi: pid=%s, user_id=%s (%s), chosen=%s", pid, user_id, name, chosen)

        # 1. Guruhdagi umumiy poll bo'lsa, ballni hisoblab borish
        if pid in _group_poll_map:
            grp_data = _group_poll_map[pid]
            grp_chat_id = grp_data[0]
            grp_quiz_id = grp_data[1]
            correct_id = grp_data[2]
            q_start = grp_data[3] if len(grp_data) > 3 else time.time()

            is_correct = (chosen == correct_id)
            time_spent = max(0.1, time.time() - q_start)

            # Jonli guruh sessiyasida ball va vaqtni hisoblash
            if grp_chat_id in _group_active_quizzes:
                sess = _group_active_quizzes[grp_chat_id]
                scores = sess.setdefault("scores", {})
                if user_id not in scores:
                    scores[user_id] = {
                        "name": name,
                        "score": 0,
                        "total_time": 0.0,
                        "answered_count": 0,
                    }
                player = scores[user_id]
                player["answered_count"] += 1
                player["total_time"] += time_spent
                if is_correct:
                    player["score"] += 1

                participants = sess.setdefault("participants", set())
                if user_id:
                    participants.add(user_id)

                answered_users = sess.setdefault("answered_users", set())
                if user_id:
                    answered_users.add(user_id)

                # Agar barcha ma'lum ishtirokchilar javob bergan bo'lsa:
                if participants and participants.issubset(answered_users):
                    # Birinchi savolda va faqat 1 kishi bo'lsa boshqalarga imkon berish uchun 1.5s, keyinroq yoki to'liq bo'lsa 0.8s
                    delay = 1.5 if (len(scores) <= 1 and player["answered_count"] == 1) else 0.8
                    asyncio.create_task(_trigger_group_advance(sess, delay=delay))

            try:
                if user_id:
                    await record_group_answer(grp_chat_id, grp_quiz_id, user_id, name, is_correct)
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
            correct_id = q.get("correct_id", 0)

            if chosen == correct_id:
                session["correct_count"] += 1
            else:
                session["wrong_questions"].append(q)

            session["current_idx"] += 1

        # Animatsiya ko'rinishi uchun juda tezkor pauza (0.3 soniya)
        await asyncio.sleep(0.3)

        if session["current_idx"] < session["total"]:
            await send_next_question(session_key, bot)
        else:
            await finish_quiz(session_key, bot)
    except Exception as ex:
        logger.exception("handle_poll_answer da xatolik: %s", ex)


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

    _last_completed_wrong_questions[session_key] = list(session.get("wrong_questions", []))

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

    bot_info = await bot.get_me()
    bot_username = bot_info.username or "quiz_tuzdimbot"
    share_link = f"https://t.me/{bot_username}?start=quiz_{quiz_id}"

    clean_title = html.escape(title, quote=False)
    result_text = (
        f"🏁 <b>“{clean_title}” testi yakunlandi!</b>\n\n"
        f"📊 Natijangiz: {total} ta savoldan <b>{correct}</b> tasiga to‘g‘ri javob berdingiz (<b>{pct}%</b>)\n"
        f"⏱ Sarflangan vaqt: <b>{time_str}</b>\n\n"
        f"{grade}\n\n"
        f"🔗 <b>Ushbu testni boshqalarga ulashish havolasi:</b>\n"
        f"<code>{share_link}</code>"
    )

    await bot.send_message(
        chat_id=chat_id,
        text=result_text,
        reply_markup=get_quiz_finish_keyboard(
            quiz_id,
            bot_username=bot_username,
            has_wrong=has_wrong,
            correct=correct,
            total=total,
            percentage=pct,
            title=title,
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
    bot_username = bot_info.username or "quiz_tuzdimbot"
    card_text = format_quiz_ready_text(quiz, bot_username=bot_username, is_group=False)
    if callback.message:
        await callback.message.edit_text(
            card_text,
            reply_markup=get_quiz_card_keyboard(
                quiz_id,
                bot_username=bot_username,
                is_group=False,
                title=quiz.get("title", ""),
            ),
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
    bot_username = bot_info.username or "quiz_tuzdimbot"
    card_text = format_quiz_ready_text(quiz, bot_username=bot_username, is_group=False)
    if callback.message:
        await callback.message.edit_text(
            card_text,
            reply_markup=get_quiz_card_keyboard(
                quiz_id,
                bot_username=bot_username,
                is_group=False,
                title=quiz.get("title", ""),
            ),
            parse_mode="HTML",
        )
    await callback.answer()

