import asyncio
import logging
from aiogram import Bot

from database.db import (
    get_due_channel_schedules,
    update_channel_schedule_last_posted,
    save_quiz,
    get_user_used_questions,
)
from services.gemini_service import GeminiService
from handlers.quiz_play import send_quiz_polls_to_chat

logger = logging.getLogger(__name__)
gemini_service = GeminiService()


async def channel_scheduler_worker(bot: Bot) -> None:
    """Kanallarga avtomatik testlarni o'z vaqtida jo'natuvchi fon xizmati."""
    logger.info("Kanal avtoposting xizmati ishga tushdi.")
    await asyncio.sleep(15)  # Bot to'liq start bo'lishini kutish

    while True:
        try:
            due_schedules = await get_due_channel_schedules()
            for sch in due_schedules:
                sch_id = sch["id"]
                channel_id = sch["channel_id"]
                topic = sch["topic"]
                user_id = sch["user_id"]
                count = sch.get("question_count", 3)

                logger.info("Kanalga avtoposting bajarilmoqda: %s (Mavzu: %s)", channel_id, topic)

                try:
                    used = await get_user_used_questions(user_id, topic)
                    questions = await gemini_service.generate_quiz(
                        topic=topic,
                        count=count,
                        options_count=4,
                        difficulty="medium",
                        used_questions=used,
                    )

                    if questions:
                        import uuid
                        quiz_id = str(uuid.uuid4())[:8]
                        await save_quiz(
                            quiz_id=quiz_id,
                            user_id=user_id,
                            title=f"{topic} (Kanal testi)",
                            source_type="channel",
                            topic=topic,
                            questions=questions,
                        )
                        quiz_dict = {
                            "quiz_id": quiz_id,
                            "title": f"🎯 {topic}",
                            "questions": questions,
                            "timer_seconds": 30,
                        }
                        await send_quiz_polls_to_chat(bot, int(channel_id) if channel_id.lstrip("-").isdigit() else channel_id, quiz_dict)
                        await update_channel_schedule_last_posted(sch_id)
                        logger.info("Kanalga test muvaffaqiyatli tashlandi: %s", channel_id)
                except Exception as post_err:
                    logger.error("Kanalga post qilishda xatolik (%s): %s", channel_id, post_err)

        except Exception as loop_err:
            logger.error("Kanal scheduler xatosi: %s", loop_err)

        await asyncio.sleep(60)  # Har 1 daqiqada tekshirish
