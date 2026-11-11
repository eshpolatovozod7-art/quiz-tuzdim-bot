import html
import logging
import time
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, BufferedInputFile

from database.db import get_quiz, get_group_quiz_results_for_excel, get_last_quiz_attempt
from services.export_service import generate_quiz_pdf, generate_quiz_docx, generate_quizbot_text
from services.certificate_service import generate_certificate
from services.excel_service import generate_quiz_results_excel
from services.tutor_service import TutorService

logger = logging.getLogger(__name__)
router = Router()
tutor_service = TutorService()


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
        esc_title = html.escape(title, quote=False)
        caption = (
            f"📄 <b>\"{esc_title}\" — Chop etish uchun PDF test varaqasi</b>\n\n"
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
        esc_title = html.escape(title, quote=False)
        caption = (
            f"📝 <b>\"{esc_title}\" — Tahrirlanadigan Word (.docx) hujjati</b>\n\n"
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


@router.callback_query(F.data.startswith("qexp:cert:"))
async def handle_export_certificate(callback: CallbackQuery, bot: Bot) -> None:
    """O'quvchiga test natijasi bo'yicha chiroyli Sertifikat rasmini yuborish."""
    parts = callback.data.split(":")
    quiz_id = parts[2]
    # Agar parametrda foiz va to'g'ri soni bo'lsa: qexp:cert:{quiz_id}:{correct}:{total}:{percentage}
    correct = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    total = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
    percentage = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0

    await callback.answer("Sertifikat tayyorlanmoqda... 🎓")

    quiz = await get_quiz(quiz_id)
    title = quiz["title"] if quiz else "Viktorina testi"
    if total == 0 and quiz:
        total = quiz.get("question_count", 5)
        correct = total
        percentage = 100

    user = callback.from_user
    user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.username or "O'quvchi")
    bot_info = await bot.get_me()

    try:
        cert_bytes = generate_certificate(
            user_name=user_name,
            quiz_title=title,
            correct=correct,
            total=total,
            percentage=percentage,
            bot_username=bot_info.username or "quiz_tuzdimbot",
        )
        safe_name = "".join(c for c in user_name if c.isalnum() or c == "_")[:15]
        photo_file = BufferedInputFile(cert_bytes, filename=f"Certificate_{safe_name}.png")

        caption = (
            f"🎓 <b>Tabriklaymiz, {user.first_name}!</b>\n\n"
            f"Siz «<b>{title}</b>» bo'yicha testni <b>{percentage}%</b> natija bilan yakunladingiz va maxsus sertifikatga ega bo'ldingiz! 🏆\n\n"
            f"<i>Ushbu sertifikatni do'stlaringizga, profilingizga yoki kanalingizga faxr bilan ulashishingiz mumkin!</i>"
        )
        await callback.message.answer_photo(photo_file, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.exception("Sertifikat yaratishda xatolik: %s", e)
        await callback.message.answer("❌ Sertifikat yaratishda xatolik yuz berdi.")


@router.callback_query(F.data.startswith("qexp:tutor:"))
async def handle_ai_tutor_analysis(callback: CallbackQuery, bot: Bot) -> None:
    """O'quvchi xatolarini AI Repetitor orqali tahlil qilish."""
    quiz_id = callback.data.split(":")[2]
    await callback.answer("AI Repetitor xatolaringizni o'rganmoqda... 🧠")

    status_msg = await callback.message.answer("⏳ <b>Shaxsiy AI Repetitor xatolaringizni o'rganib chiqmoqda...</b>", parse_mode="HTML")

    quiz = await get_quiz(quiz_id)
    title = quiz["title"] if quiz else "Test"

    # Xato savollarni topish (kesh, sessiyalar yoki bazadagi oxirgi urinishdan)
    from handlers.quiz_play import _active_sessions, _last_completed_wrong_questions
    user_id = callback.from_user.id
    wrong_questions = []

    if user_id in _last_completed_wrong_questions and _last_completed_wrong_questions[user_id]:
        wrong_questions = _last_completed_wrong_questions[user_id]
    else:
        for s in _active_sessions.values():
            if s.get("quiz_id") == quiz_id and s.get("wrong_questions"):
                wrong_questions = s["wrong_questions"]
                break

    if not wrong_questions:
        attempt = await get_last_quiz_attempt(quiz_id, user_id)
        if attempt and attempt.get("wrong_questions"):
            wrong_questions = attempt["wrong_questions"]

    if not wrong_questions and quiz:
        # Xatolar umuman bo'lmasa yoki barchasi to'g'ri bo'lsa, quizning savollaridan namuna
        wrong_questions = quiz.get("questions", [])[:3]

    analysis = await tutor_service.analyze_wrong_questions(title, wrong_questions)

    try:
        await status_msg.delete()
    except Exception:
        pass

    text = (
        f"🧠 <b>SHAXSIY AI REPETITOR TAHLILI</b>\n"
        f"📌 <b>Mavzu:</b> <i>{html.escape(title, quote=False)}</i>\n\n"
        f"{analysis}\n\n"
        f"<i>Ushbu qoidalarni eslab qoling va bilimlaringizni mustahkamlang!</i> 🚀"
    )
    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("gexp:excel:"))
async def handle_export_excel(callback: CallbackQuery, bot: Bot) -> None:
    """Guruhdagi test natijalarini Excel (.xlsx) fayl qilib yuborish."""
    parts = callback.data.split(":")
    group_id = int(parts[2])
    quiz_id = parts[3] if len(parts) > 3 else None

    await callback.answer("Excel jadval shakllantirilmoqda... 📊")

    results = await get_group_quiz_results_for_excel(group_id, quiz_id)
    if not results:
        await callback.message.answer("⚠️ Guruhda hali natijalar mavjud emas.")
        return

    chat_title = callback.message.chat.title if callback.message and callback.message.chat else "Guruh"
    quiz = await get_quiz(quiz_id) if quiz_id else None
    quiz_title = quiz["title"] if quiz else "Guruh Viktorinasi"

    try:
        excel_bytes = generate_quiz_results_excel(quiz_title, results, chat_title)
        filename = f"Natijalar_{group_id}_{int(time.time()) % 10000}.xlsx"
        file = BufferedInputFile(excel_bytes, filename=filename)

        caption = (
            f"📊 <b>«{html.escape(quiz_title, quote=False)}» — Natijalar Jadvali (Excel)</b>\n\n"
            f"• Manba: <b>{html.escape(chat_title, quote=False)}</b>\n"
            f"• Jami qatnashchilar: <b>{len(results)} nafar</b>\n\n"
            f"<i>Barcha o'quvchilarning ballari, foizlari va darajalari jadvalda to'liq formatlangan!</i>"
        )
        await callback.message.answer_document(file, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.exception("Excel yaratishda xatolik: %s", e)
        await callback.message.answer("❌ Excel hisobot yaratishda xatolik yuz berdi.")


