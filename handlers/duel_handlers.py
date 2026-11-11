import asyncio
import html
import logging
import time
import uuid
from typing import Any
from urllib.parse import quote
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, CallbackQuery, PollAnswer, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    create_duel,
    get_duel,
    join_duel,
    submit_duel_result,
)
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)
router = Router()
gemini_service = GeminiService()


class DuelState(StatesGroup):
    waiting_topic = State()


# duel_session_key (chat_id, duel_id) -> session dict
_active_duel_sessions: dict[tuple[int, str], dict[str, Any]] = {}
_duel_poll_map: dict[str, tuple[int, str]] = {}


@router.message(Command("duel"))
@router.callback_query(F.data == "menu:duel")
async def handle_menu_duel(event: Message | CallbackQuery, state: FSMContext) -> None:
    """1 vs 1 Duel bo'limi boshlanishi."""
    await state.clear()
    text = (
        "⚔️ <b>1 vs 1 Do'stona Duel (Viktorina Jangi)</b>\n\n"
        "Do'stingiz bilan real vaqtda bir xil savollarda bellashing!\n"
        "Kim ko'proq to'g'ri topsa va tezroq ishlasa, o'sha g'olib bo'ladi! 🏆\n\n"
        "Mavzuni tanlang yoki o'zingiz xohlagan mavzuni chatga yozing: 👇"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇬🇧 Ingliz tili B2", callback_data="duel_top:Ingliz tili B2 grammatika"),
                InlineKeyboardButton(text="📐 Matematika", callback_data="duel_top:Matematika mantiq"),
            ],
            [
                InlineKeyboardButton(text="🏛 O'zbekiston tarixi", callback_data="duel_top:O'zbekiston tarixi"),
                InlineKeyboardButton(text="💻 Dasturlash (IT)", callback_data="duel_top:Dasturlash asoslari"),
            ],
            [
                InlineKeyboardButton(text="🧠 Mantiqiy topqirlik", callback_data="duel_top:Mantiqiy savollar"),
                InlineKeyboardButton(text="🌍 Geografiya", callback_data="duel_top:Dunyo geografiyasi"),
            ],
            [
                InlineKeyboardButton(text="✍️ Boshqa mavzu yozish", callback_data="duel_top:custom"),
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu:home"),
            ],
        ]
    )
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("duel_top:"))
async def handle_duel_topic_select(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    topic = callback.data.split(":", 1)[1]
    if topic == "custom":
        await state.set_state(DuelState.waiting_topic)
        await callback.message.answer(
            "✍️ <b>Duel mavzusini yozib yuboring:</b>\n"
            "<i>(Masalan: Fizika Optika, Ingliz tili Phrasal Verbs, Avtomobil qoidalari...)</i>",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await generate_and_prepare_duel(callback.message, callback.from_user, topic, bot)
    await callback.answer()


@router.message(DuelState.waiting_topic, F.text)
async def process_custom_duel_topic(message: Message, state: FSMContext, bot: Bot) -> None:
    topic = message.text.strip()
    await state.clear()
    await generate_and_prepare_duel(message, message.from_user, topic, bot)


async def generate_and_prepare_duel(message: Message, user: Any, topic: str, bot: Bot) -> None:
    status_msg = await message.answer(f"⏳ <b>«{html.escape(topic, quote=False)}» bo'yicha 5 ta savolli Duel tayyorlanmoqda...</b>", parse_mode="HTML")
    try:
        questions = await gemini_service.generate_quiz(
            topic=topic,
            count=5,
            options_count=4,
            difficulty="medium",
        )
    except Exception as e:
        logger.error("Duel generatsiya xatosi: %s", e)
        questions = []

    try:
        await status_msg.delete()
    except Exception:
        pass

    if not questions:
        await message.answer("⚠️ Duel savollarini tayyorlashda xatolik bo'ldi. Qaytadan urinib ko'ring.")
        return

    duel_id = str(uuid.uuid4())[:8]
    creator_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.username or "O'yinchi")

    await create_duel(
        duel_id=duel_id,
        creator_id=user.id,
        creator_name=creator_name,
        topic=topic,
        questions=questions,
    )

    bot_info = await bot.get_me()
    duel_link = f"https://t.me/{bot_info.username}?start=duel_{duel_id}"
    share_text = quote(f"⚔️ Men sizni «{topic}» bo'yicha 1 vs 1 duelga chorlayman! Kim ko'proq ball olishini sinab ko'ramiz:")
    share_url = f"https://t.me/share/url?url={duel_link}&text={share_text}"

    text = (
        "⚔️ <b>1 vs 1 DUEL TAYYOR!</b>\n\n"
        f"📌 <b>Mavzu:</b> <i>{html.escape(topic, quote=False)}</i> (5 ta savol)\n\n"
        "⚡️ Do'stingizga duel taklifini yuboring va o'zingiz ham testni yechishni boshlang!\n"
        "Ikkalangiz ham yakunlagach, bot g'olibni e'lon qiladi! 🏆"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Do'stga duel yuborish", url=share_url),
            ],
            [
                InlineKeyboardButton(text="▶️ O'zim jangga kirishish", callback_data=f"duel:play:{duel_id}"),
            ],
            [
                InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="menu:home"),
            ],
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("duel:play:"))
async def handle_duel_play_start(callback: CallbackQuery, bot: Bot) -> None:
    duel_id = callback.data.split(":")[2]
    user = callback.from_user
    chat_id = callback.message.chat.id if callback.message else user.id

    duel = await get_duel(duel_id)
    if not duel:
        await callback.answer("Duel topilmadi yoki eskirgan", show_alert=True)
        return

    # Raqib bo'lsa ro'yxatdan o'tkazamiz
    user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.username or "O'yinchi")
    await join_duel(duel_id, user.id, user_name)

    await callback.answer("Jang boshlandi! ⚔️")

    session_key = (chat_id, duel_id)
    questions = duel["questions"]

    _active_duel_sessions[session_key] = {
        "duel_id": duel_id,
        "user_id": user.id,
        "chat_id": chat_id,
        "user_name": user_name,
        "questions": questions,
        "current_idx": 0,
        "correct_count": 0,
        "start_time": time.time(),
        "current_poll_id": None,
        "lock": asyncio.Lock(),
    }

    await bot.send_message(
        chat_id=chat_id,
        text=f"🏁 <b>«{html.escape(duel['topic'], quote=False)}» dueli boshlandi!</b>\n<i>Savollarga iloji boricha tez va to'g'ri javob bering...</i> 👇",
        parse_mode="HTML",
    )
    await asyncio.sleep(0.5)
    await send_next_duel_question(session_key, bot)


async def send_next_duel_question(session_key: tuple[int, str], bot: Bot) -> None:
    session = _active_duel_sessions.get(session_key)
    if not session:
        return

    idx = session["current_idx"]
    questions = session["questions"]
    chat_id = session["chat_id"]

    if idx >= len(questions):
        await finish_player_duel(session_key, bot)
        return

    q = questions[idx]
    q_title = f"[{idx + 1}/{len(questions)}] {q['question']}"
    opts = [str(o)[:100] for o in q.get("options", [])][:4]
    c_id = q.get("correct_id", 0)

    try:
        msg = await bot.send_poll(
            chat_id=chat_id,
            question=q_title[:300],
            options=opts,
            type="quiz",
            correct_option_id=c_id,
            is_anonymous=False,
            open_period=20,  # 20 soniya limit
        )
        pid = msg.poll.id
        session["current_poll_id"] = pid
        _duel_poll_map[pid] = session_key
    except Exception as e:
        logger.error("Duel savol yuborishda xatolik: %s", e)
        session["current_idx"] += 1
        await send_next_duel_question(session_key, bot)


@router.poll_answer(lambda pa: pa.poll_id in _duel_poll_map)
async def handle_duel_poll_answer(poll_answer: PollAnswer, bot: Bot) -> None:
    pid = poll_answer.poll_id
    session_key = _duel_poll_map.get(pid)
    if not session_key or session_key not in _active_duel_sessions:
        raise SkipHandler()

    session = _active_duel_sessions[session_key]
    if session.get("current_poll_id") != pid:
        return

    async with session["lock"]:
        idx = session["current_idx"]
        if idx >= len(session["questions"]):
            return

        q = session["questions"][idx]
        chosen = poll_answer.option_ids[0] if poll_answer.option_ids else -1
        correct_id = q.get("correct_id", 0)
        if chosen == correct_id:
            session["correct_count"] += 1

        session["current_idx"] += 1

    await asyncio.sleep(0.8)
    await send_next_duel_question(session_key, bot)


async def finish_player_duel(session_key: tuple[int, str], bot: Bot) -> None:
    session = _active_duel_sessions.pop(session_key, None)
    if not session:
        return

    duel_id = session["duel_id"]
    user_id = session["user_id"]
    chat_id = session["chat_id"]
    score = session["correct_count"]
    time_spent = int(time.time() - session["start_time"])

    updated_duel = await submit_duel_result(duel_id, user_id, score, time_spent)
    if not updated_duel:
        return

    if updated_duel.get("status") == "finished":
        # Ikkala o'yinchi ham tugatdi, umumiy g'olibni e'lon qilamiz!
        c_id = updated_duel["creator_id"]
        c_name = updated_duel["creator_name"]
        c_score = updated_duel["creator_score"]
        c_time = updated_duel["creator_time"]

        o_id = updated_duel["opponent_id"]
        o_name = updated_duel["opponent_name"]
        o_score = updated_duel["opponent_score"]
        o_time = updated_duel["opponent_time"]

        if c_score > o_score:
            winner_text = f"🏆 <b>G'OLIB: {html.escape(c_name, quote=False)}!</b> 🎉"
        elif o_score > c_score:
            winner_text = f"🏆 <b>G'OLIB: {html.escape(o_name, quote=False)}!</b> 🎉"
        else:
            if c_time < o_time:
                winner_text = f"🏆 <b>G'OLIB: {html.escape(c_name, quote=False)}!</b> (Tezroq ishlagan) ⚡️"
            elif o_time < c_time:
                winner_text = f"🏆 <b>G'OLIB: {html.escape(o_name, quote=False)}!</b> (Tezroq ishlagan) ⚡️"
            else:
                winner_text = "🤝 <b>DO'STLIK G'ALABA QOZONDI! (Durang)</b>"

        result_message = (
            "✦ • ──────────────────── • ✦\n"
            "🏁 <b>1 vs 1 DUEL YAKUNLANDI!</b>\n"
            "✦ • ──────────────────── • ✦\n\n"
            f"👤 <b>{html.escape(c_name, quote=False)}:</b> {c_score} / 5 ball (⏱ {c_time}s)\n"
            f"👤 <b>{html.escape(o_name, quote=False)}:</b> {o_score} / 5 ball (⏱ {o_time}s)\n\n"
            f"{winner_text}\n"
            "✦ • ──────────────────── • ✦"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚔️ Yangi duel boshlash", callback_data="menu:duel")]])

        for target_id in (c_id, o_id):
            if target_id:
                try:
                    await bot.send_message(chat_id=target_id, text=result_message, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass
    else:
        # Hali ikkinchi o'yinchi tugatmagan
        wait_text = (
            "🏁 <b>Siz duelni yakunladingiz!</b>\n\n"
            f"📊 Natijangiz: <b>{score} / 5 ball</b> (⏱ {time_spent} soniya)\n\n"
            "⏳ <i>Raqibingiz testni yakunlashi kutilmoqda. U tugatishi bilan ikkalangizga ham yakuniy g'olib xabari boradi!</i>"
        )
        await bot.send_message(chat_id=chat_id, text=wait_text, parse_mode="HTML")
