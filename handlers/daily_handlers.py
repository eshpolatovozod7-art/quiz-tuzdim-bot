import asyncio
import datetime
import html
import logging
from aiogram import Router, F, Bot
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, CallbackQuery, PollAnswer, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from database.db import get_user_streak, record_or_update_user_streak, save_quiz
from keyboards.inline_keyboards import get_main_menu_keyboard
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)
router = Router()
gemini_service = GeminiService()

# poll_id -> (user_id, correct_id)
_daily_poll_map: dict[str, tuple[int, int]] = {}


@router.message(Command("daily"))
@router.callback_query(F.data == "menu:daily")
async def handle_daily_quiz(event: Message | CallbackQuery, bot: Bot) -> None:
    """Har kungi Kun Testi va Streak tekshiruvi."""
    user = event.from_user
    if not user:
        return

    streak_info = await get_user_streak(user.id)
    current_streak = streak_info["current"]
    longest_streak = streak_info["longest"]
    active_today = streak_info["active_today"]

    if active_today:
        text = (
            f"🔥 <b>Bugungi Kun Testi allaqachon topshirilgan!</b>\n\n"
            f"⚡️ Joriy ketma-ketlik (Streak): <b>{current_streak} kun</b> 🔥\n"
            f"🏆 Shaxsiy rekordingiz: <b>{longest_streak} kun</b>\n\n"
            f"<i>Ertaga yangi savol bilan olovli streakni davom ettiring!</i> 🚀"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎲 Test tuzish", callback_data="menu:create")],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="menu:home")],
            ]
        )
        if isinstance(event, CallbackQuery) and event.message:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    # Yangi kunlik savol generatsiya qilish
    if isinstance(event, CallbackQuery):
        await event.answer("Bugungi Kun Testi tayyorlanmoqda... 🔥")
        status_msg = await event.message.answer("⏳ <b>Bugungi eksklyuziv Kun Testi shakllantirilmoqda...</b>", parse_mode="HTML")
    else:
        status_msg = await event.answer("⏳ <b>Bugungi eksklyuziv Kun Testi shakllantirilmoqda...</b>", parse_mode="HTML")

    topics_pool = [
        "Mantiq va intellektual topqirlik",
        "Qiziqarli dunyo bilimlari va faktlar",
        "Tarixiy kashfiyotlar va buyuk allomalar",
        "Ingliz tili qiziqarli iboralari va idiomalar",
        "Zamonaviy texnologiyalar va koinot",
    ]
    import random
    selected_topic = random.choice(topics_pool)

    try:
        questions = await gemini_service.generate_quiz(
            topic=selected_topic,
            count=1,
            options_count=4,
            difficulty="medium",
        )
    except Exception as e:
        logger.error("Daily quiz xatosi: %s", e)
        questions = []

    if not questions:
        from services.quiz_service import get_offline_quiz_questions
        questions = get_offline_quiz_questions(selected_topic, 1, 4)

    try:
        await status_msg.delete()
    except Exception:
        pass

    if not questions:
        await (event.message if isinstance(event, CallbackQuery) else event).answer(
            "⚠️ Hozircha kun testi savolini tayyorlab bo'lmadi. Birozdan so'ng qayta urinib ko'ring."
        )
        return

    q = questions[0]
    opts = [str(o)[:100] for o in q.get("options", [])][:4]
    c_id = q.get("correct_id", 0)
    expl = str(q.get("explanation", "")).strip()[:200]

    header_text = (
        "✦ • ──────────────────── • ✦\n"
        f"🔥 <b>BUGUNGI KUN TESTI ({datetime.date.today().strftime('%d.%m.%Y')})</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"⚡️ Joriy streak: <b>{current_streak} kun</b> 🔥\n"
        "<i>To'g'ri javobni tanlang va olovli ketma-ketlikni oshiring!</i> 👇"
    )
    target_chat_id = event.message.chat.id if isinstance(event, CallbackQuery) and event.message else event.chat.id
    await bot.send_message(chat_id=target_chat_id, text=header_text, parse_mode="HTML")

    poll_msg = await bot.send_poll(
        chat_id=target_chat_id,
        question=f"[Kun Testi] {q['question']}"[:300],
        options=opts,
        type="quiz",
        correct_option_id=c_id,
        is_anonymous=False,
        explanation=expl or None,
    )
    _daily_poll_map[poll_msg.poll.id] = (user.id, c_id)


@router.poll_answer(lambda pa: pa.poll_id in _daily_poll_map)
async def handle_daily_poll_answer(poll_answer: PollAnswer, bot: Bot) -> None:
    """Kun testiga javob berilganda streakni yangilash."""
    pid = poll_answer.poll_id
    if pid not in _daily_poll_map:
        raise SkipHandler()

    target_user_id, correct_id = _daily_poll_map.pop(pid)
    user = poll_answer.user
    if user.id != target_user_id:
        return

    chosen = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    is_correct = (chosen == correct_id)

    curr, longest, is_new = await record_or_update_user_streak(user.id)
    if is_new:
        bonus = "🎉 To'g'ri javob!" if is_correct else "💡 Harakat uchun tashakkur!"
        text = (
            f"🔥 <b>KUN TESTI TOPSHIRILDI!</b>\n\n"
            f"{bonus}\n"
            f"⚡️ Sizning ketma-ketlik (Streak) ko'rsatkichingiz: <b>{curr} kun</b>! 🔥\n"
            f"🏆 Shaxsiy rekordingiz: <b>{longest} kun</b>\n\n"
            f"<i>Ertaga ham kiring va rekordni yangilang!</i> 🚀"
        )
        try:
            await bot.send_message(chat_id=user.id, text=text, parse_mode="HTML")
        except Exception:
            pass
