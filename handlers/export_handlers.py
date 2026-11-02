import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, BufferedInputFile

from database.db import get_quiz
from services.export_service import generate_quiz_pdf, generate_quiz_docx, generate_quizbot_text

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("qexp:pdf:"))
async def handle_export_pdf(callback: CallbackQuery, bot: Bot) -> None:
    """PDF test varaqasini generatsiya qilish va foydalanuvchiga yuborish."""
    quiz_id = callback.data.split(":")[2]
    await callback.answer("PDF test varaqasi tayyorlanmoqda...")

    quiz = await get_quiz(quiz_id)
    if not quiz or not quiz.get("questions"):
        await callback.message.answer("⚠️ Test topilmadi.")
        return

    title = quiz["title"]
    questions = quiz["questions"]

    try:
        pdf_bytes = generate_quiz_pdf(title, questions)
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
        filename = f"Test_{safe_title[:25]}.pdf"

        file = BufferedInputFile(pdf_bytes, filename=filename)
        caption = (
            f"📄 <b>\"{title}\" — Chop etish uchun PDF test varaqasi</b>\n\n"
            f"• Jami savollar: {len(questions)} ta\n"
            f"• Oxirgi qismida to'g'ri javoblar kaliti va izohlar mavjud.\n\n"
            f"<i>Ushbu PDF faylni printerdan chiqarib, dars yoki imtihonlarda to'g'ridan-to'g'ri qo'llashingiz mumkin!</i>"
        )
        await callback.message.answer_document(file, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.exception("PDF yaratishda xatolik: %s", e)
        await callback.message.answer("❌ PDF fayl yaratishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("qexp:docx:"))
async def handle_export_docx(callback: CallbackQuery, bot: Bot) -> None:
    """Word (.docx) test hujjatini yuborish."""
    quiz_id = callback.data.split(":")[2]
    await callback.answer("Word hujjati tayyorlanmoqda...")

    quiz = await get_quiz(quiz_id)
    if not quiz or not quiz.get("questions"):
        await callback.message.answer("⚠️ Test topilmadi.")
        return

    title = quiz["title"]
    questions = quiz["questions"]

    try:
        docx_bytes = generate_quiz_docx(title, questions)
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
        filename = f"Test_{safe_title[:25]}.docx"

        file = BufferedInputFile(docx_bytes, filename=filename)
        caption = (
            f"📝 <b>\"{title}\" — Tahrirlanadigan Word (.docx) hujjati</b>\n\n"
            f"• Savollar va javoblar kaliti bilan.\n"
            f"<i>Microsoft Word yoki WPS da xohlagancha tahrirlashingiz mumkin.</i>"
        )
        await callback.message.answer_document(file, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.exception("Word yaratishda xatolik: %s", e)
        await callback.message.answer("❌ Word fayl yaratishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("qexp:quizbot:"))
async def handle_export_quizbot(callback: CallbackQuery, bot: Bot) -> None:
    """@QuizBot ga kiritish uchun qulay formatdagi matnni yuborish."""
    quiz_id = callback.data.split(":")[2]
    await callback.answer()

    quiz = await get_quiz(quiz_id)
    if not quiz or not quiz.get("questions"):
        await callback.message.answer("⚠️ Test topilmadi.")
        return

    title = quiz["title"]
    questions = quiz["questions"]

    quizbot_text = generate_quizbot_text(title, questions)
    guide = (
        "🤖 <b>Telegram @QuizBot ga o'tkazish bo'yicha yo'riqnoma:</b>\n\n"
        "1. <b>@QuizBot</b> ga kiring va <code>/newquiz</code> buyrug'ini bering.\n"
        "2. Test nomini yozing.\n"
        "3. Quyidagi savollarni nusxalab @QuizBot ga ketma-ket poll ko'rinishida yuboring yoki botimizdagi testlarni to'g'ridan-to'g'ri Forward (Uzatish) qiling!\n\n"
        "👇 <b>Savollar va to'g'ri javoblar ro'yxati:</b>\n\n"
    )

    full_message = guide + quizbot_text
    if len(full_message) <= 4000:
        await callback.message.answer(full_message, parse_mode="HTML")
    else:
        # Uzun bo'lsa qismlarga bo'lib yuborish
        await callback.message.answer(guide, parse_mode="HTML")
        parts = [quizbot_text[i:i+3800] for i in range(0, len(quizbot_text), 3800)]
        for p in parts:
            await callback.message.answer(p)
