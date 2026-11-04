import hashlib
import html
from aiogram import Router, F, Bot
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database.db import get_quiz

router = Router()


def _make_id(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery, bot: Bot) -> None:
    raw_query = inline_query.query.strip()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or "quiz_tuzdimbot"

    if raw_query.startswith("quiz_") or raw_query.startswith("q_"):
        quiz_id = raw_query.replace("quiz_", "").replace("q_", "").strip()
        quiz = await get_quiz(quiz_id)
        if quiz:
            from handlers.quiz_play import format_quiz_ready_text
            title = quiz["title"]
            count = quiz["question_count"]
            timer = f"{quiz.get('timer_seconds', 0)}s" if quiz.get("timer_seconds", 0) > 0 else "15s"
            text = format_quiz_ready_text(quiz)

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Bu testni boshlash", url=f"https://t.me/{bot_username}?start=quiz_{quiz_id}")],
                ]
            )

            result = InlineQueryResultArticle(
                id=_make_id(f"quiz_{quiz_id}"),
                title=f"🎲 “{title}” ({count} ta savol)",
                description=f"⏱ {timer} | Testga tayyorlaning",
                input_message_content=InputTextMessageContent(
                    message_text=text,
                    parse_mode="HTML",
                ),
                reply_markup=kb,
            )
            await inline_query.answer(results=[result], cache_time=5, is_personal=True)
            return

    # Standart inline yordam
    text = (
        "🎯 <b>Quiz Tuzdim Bot</b> — Har qanday mavzu, hujjat yoki videodan test tuzuvchi intellektual yordamchi!\n\n"
        "O'zingiz test tuzish uchun botga kiring: @quiz_tuzdimbot"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Botga o'tish", url=f"https://t.me/{bot_username}")],
        ]
    )
    result = InlineQueryResultArticle(
        id=_make_id("help_default"),
        title="🎯 Quiz Tuzdim Bot",
        description="Mavzu, PDF, Video, Audio yoki Rasmdan test tuzish",
        input_message_content=InputTextMessageContent(
            message_text=text,
            parse_mode="HTML",
        ),
        reply_markup=kb,
    )
    await inline_query.answer(results=[result], cache_time=10, is_personal=True)
