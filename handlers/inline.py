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

from database.db import get_quiz, get_user_quizzes

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
            title = quiz["title"]
            count = quiz["question_count"]
            tm = quiz.get("timer_seconds", 15)
            timer = f"{tm} soniya" if (tm and tm > 0) else "15 soniya"
            escaped_title = html.escape(title, quote=False)

            text = (
                f"🎲 <b>“{escaped_title}” testi</b>\n\n"
                f"🗡 {count} ta savol\n"
                f"⏱ Har bir savol uchun {timer}\n"
                f"🏛 Ovozlar test egasiga ko‘rinadigan bo‘ladi\n\n"
                f"👇 <i>Testni boshlash uchun quyidagi tugmani bosing:</i>"
            )

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="▶️ Testni boshlash",
                            url=f"https://t.me/{bot_username}?start=quiz_{quiz_id}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="👥 Guruhda testni boshlash",
                            url=f"https://t.me/{bot_username}?startgroup=poll_{quiz_id}",
                        ),
                    ],
                ]
            )

            result = InlineQueryResultArticle(
                id=_make_id(f"quiz_{quiz_id}"),
                title=f"🎲 “{title}” ({count} ta savol)",
                description=f"⏱ {timer} | Testni boshlash yoki guruhga qo'shish",
                input_message_content=InputTextMessageContent(
                    message_text=text,
                    parse_mode="HTML",
                ),
                reply_markup=kb,
            )
            await inline_query.answer(results=[result], cache_time=5, is_personal=True)
            return

    # Foydalanuvchining o'z testlarini inline orqali chiqarish
    user_quizzes = await get_user_quizzes(inline_query.from_user.id, limit=10)
    results = []

    for q in user_quizzes:
        q_id = q["quiz_id"]
        q_title = q["title"]
        q_count = q["question_count"]
        q_tm = q.get("timer_seconds", 15)
        q_timer = f"{q_tm} soniya" if (q_tm and q_tm > 0) else "15 soniya"

        if raw_query and raw_query.lower() not in q_title.lower():
            continue

        escaped_title = html.escape(q_title, quote=False)
        q_text = (
            f"🎲 <b>“{escaped_title}” testi</b>\n\n"
            f"🗡 {q_count} ta savol\n"
            f"⏱ Har bir savol uchun {q_timer}\n"
            f"🏛 Ovozlar test egasiga ko‘rinadigan bo‘ladi\n\n"
            f"👇 <i>Testni boshlash uchun quyidagi tugmani bosing:</i>"
        )
        q_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="▶️ Testni boshlash",
                        url=f"https://t.me/{bot_username}?start=quiz_{q_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="👥 Guruhda testni boshlash",
                        url=f"https://t.me/{bot_username}?startgroup=poll_{q_id}",
                    ),
                ],
            ]
        )
        results.append(
            InlineQueryResultArticle(
                id=_make_id(f"user_q_{q_id}"),
                title=f"🎯 {q_title} ({q_count} ta savol)",
                description=f"⏱ {q_timer} | Guruhda yoki shaxsiyda boshlash",
                input_message_content=InputTextMessageContent(
                    message_text=q_text,
                    parse_mode="HTML",
                ),
                reply_markup=q_kb,
            )
        )

    if results:
        await inline_query.answer(results=results[:10], cache_time=5, is_personal=True)
        return

    # Standart inline yordam
    text = (
        "🎯 <b>Quiz Tuzdim Bot</b> — Har qanday mavzu, hujjat yoki videodan test tuzuvchi intellektual yordamchi!\n\n"
        f"O'zingiz test tuzish uchun botga kiring: @{bot_username}"
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
