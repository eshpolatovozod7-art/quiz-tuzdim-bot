import html
import io
import logging
import os
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import UPLOADS_DIR
from database.db import save_quiz, get_user_used_questions
from keyboards.inline_keyboards import (
    get_main_menu_keyboard,
    get_popular_topics_keyboard,
    get_quiz_count_keyboard,
    get_quiz_options_keyboard,
    get_quiz_difficulty_keyboard,
    get_quiz_timer_keyboard,
    get_quiz_card_keyboard,
)
from services.gemini_service import GeminiService
from services.quiz_service import (
    extract_text_from_file,
    get_offline_quiz_questions,
    save_user_media,
    get_user_media,
)
from utils.states import QuizCreateState

logger = logging.getLogger(__name__)
router = Router()
gemini_service = GeminiService()


# ---------------- Menyu bo'limlari ---------------- #

@router.callback_query(F.data == "menu:topic")
async def handle_menu_topic(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuizCreateState.waiting_topic)
    await callback.answer()
    text = (
        "🎲 <b>Mavzu bo'yicha test tuzish:</b>\n\n"
        "Quyidagi mashhur mavzulardan birini tanlang yoki o'zingiz istagan mavzu/fan nomini chatga yozing:\n"
        "<i>(Masalan: Oliy matematika, Python OOP, Jahon tarixi, IELTS Vocabulary...)</i>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_popular_topics_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("qtop:"))
async def handle_topic_preset(callback: CallbackQuery, state: FSMContext) -> None:
    topic_name = callback.data.split(":", 1)[1]
    await callback.answer(f"{topic_name} tanlandi")
    await start_quiz_wizard(callback.message, state, topic=topic_name, user_id=callback.from_user.id)


@router.callback_query(F.data == "menu:doc")
async def handle_menu_doc(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuizCreateState.waiting_document)
    await callback.answer()
    text = (
        "📁 <b>Hujjat (PDF yoki Word) orqali test tuzish:</b>\n\n"
        "Iltimos, darslik, qo'llanma, ma'ruza matni yoki konspektni <b>PDF</b> yoki <b>Word (.docx, .doc)</b> formatida yuboring (20 MB gacha).\n\n"
        "AI hujjatdagi ma'lumotlarni to'liq tahlil qilib, dars bo'yicha mukammal test savollarini tuzadi!"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:video")
async def handle_menu_video(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuizCreateState.waiting_video)
    await callback.answer()
    text = (
        "🎥 <b>Video darslik orqali test tuzish:</b>\n\n"
        "Telegramga video darslik yoki video xabar (20 MB gacha) yuboring.\n\n"
        "Sun'iy intellekt videoni ko'rib, unda tushuntirilgan qoidalar, formulalar va faktlar asosida viktorina tuzadi!"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:audio")
async def handle_menu_audio(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuizCreateState.waiting_audio)
    await callback.answer()
    text = (
        "🎙 <b>Ovoz / Audio orqali test tuzish:</b>\n\n"
        "Ovozli xabar (voice note) yoki audio fayl (mp3, ogg, wav) yuboring.\n\n"
        "AI ma'ruza yoki audio darslikni to'liq tinglab, tushunilganlik darajasini tekshiruvchi test tuzadi!"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:image")
async def handle_menu_image(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuizCreateState.waiting_image)
    await callback.answer()
    text = (
        "📸 <b>Rasm / Fotosurat orqali test tuzish:</b>\n\n"
        "Doska surati, daftar konspekti yoki kitob sahifasining fotosini yuboring.\n\n"
        "AI rasmdagi matn va formulalarni o'qib, ulardan test tuzib beradi!"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:text")
async def handle_menu_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuizCreateState.waiting_text)
    await callback.answer()
    text = (
        "📋 <b>Matndan test tuzish:</b>\n\n"
        "O'zingiz nusxalagan konspekt, maqola yoki mavzu matnini chatga yuboring.\n\n"
        "AI matndagi har bir muhim nuqtadan test savollarini shakllantiradi."
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


# ---------------- Xabarlarni qabul qilish ---------------- #

@router.message(QuizCreateState.waiting_topic, F.text)
async def process_topic_text(message: Message, state: FSMContext) -> None:
    topic = message.text.strip()
    await start_quiz_wizard(message, state, topic=topic, user_id=message.from_user.id)


@router.message(QuizCreateState.waiting_text, F.text)
async def process_custom_text(message: Message, state: FSMContext) -> None:
    text_content = message.text.strip()
    title = text_content[:30].replace("\n", " ").strip() + "..."
    save_user_media(message.from_user.id, text_content=text_content)
    await start_quiz_wizard(message, state, text_content=text_content, label=title, user_id=message.from_user.id)


@router.message(F.document)
async def process_document_message(message: Message, bot: Bot, state: FSMContext) -> None:
    doc = message.document
    if not doc:
        return

    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.answer("⚠️ Kechirasiz, fayl hajmi 20 MB dan oshmasligi kerak.")
        return

    file_name = doc.file_name or "document.pdf"
    status_msg = await message.answer(f"⏳ `{file_name}` yuklab olinmoqda va tahlil qilinmoqda...")

    stream = io.BytesIO()
    try:
        await bot.download(doc, destination=stream)
        file_bytes = stream.getvalue()
    except Exception as e:
        logger.error("Hujjat yuklab olishda xatolik: %s", e)
        await status_msg.edit_text("❌ Faylni yuklab olishda xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    try:
        await status_msg.delete()
    except Exception:
        pass

    ext = os.path.splitext(file_name)[1].lower()
    if ext in (".pdf", ".docx", ".doc", ".txt"):
        text_content = extract_text_from_file(file_bytes, file_name)
        save_user_media(message.from_user.id, file_bytes, file_name, doc.mime_type or "application/pdf", text_content=text_content)
        clean_title = os.path.splitext(file_name)[0][:35]
        await start_quiz_wizard(
            message, state,
            text_content=text_content,
            label=clean_title,
            source_type="doc",
            user_id=message.from_user.id,
        )
    elif ext in (".mp4", ".mov", ".avi", ".mkv"):
        save_user_media(message.from_user.id, file_bytes, file_name, doc.mime_type or "video/mp4")
        clean_title = os.path.splitext(file_name)[0][:35]
        await start_quiz_wizard(
            message, state,
            file_bytes=file_bytes,
            file_mime=doc.mime_type or "video/mp4",
            file_name=file_name,
            label=clean_title,
            source_type="video",
            user_id=message.from_user.id,
        )
    else:
        text_content = extract_text_from_file(file_bytes, file_name)
        await start_quiz_wizard(
            message, state,
            text_content=text_content,
            label=file_name[:35],
            source_type="doc",
            user_id=message.from_user.id,
        )


@router.message(F.video | F.video_note)
async def process_video_message(message: Message, bot: Bot, state: FSMContext) -> None:
    video_obj = message.video or message.video_note
    if not video_obj:
        return

    if video_obj.file_size and video_obj.file_size > 20 * 1024 * 1024:
        await message.answer("⚠️ Kechirasiz, Telegram faqat 20 MB gacha videolarni qabul qila oladi.")
        return

    file_name = getattr(video_obj, "file_name", None) or f"video_{video_obj.file_unique_id[:8]}.mp4"
    status_msg = await message.answer(f"⏳ `{file_name}` yuklab olinmoqda...")

    stream = io.BytesIO()
    try:
        await bot.download(video_obj, destination=stream)
        video_bytes = stream.getvalue()
    except Exception as e:
        logger.error("Video yuklab olishda xatolik: %s", e)
        await status_msg.edit_text("❌ Videoni yuklab olishda xatolik yuz berdi.")
        return

    try:
        await status_msg.delete()
    except Exception:
        pass

    mime_type = getattr(video_obj, "mime_type", None) or "video/mp4"
    save_user_media(message.from_user.id, video_bytes, file_name, mime_type)
    clean_title = os.path.splitext(file_name)[0][:35]

    await start_quiz_wizard(
        message, state,
        file_bytes=video_bytes,
        file_mime=mime_type,
        file_name=file_name,
        label=clean_title,
        source_type="video",
        user_id=message.from_user.id,
    )


@router.message(F.voice | F.audio)
async def process_audio_message(message: Message, bot: Bot, state: FSMContext) -> None:
    audio_obj = message.voice or message.audio
    if not audio_obj:
        return

    file_name = getattr(audio_obj, "file_name", None) or f"audio_{audio_obj.file_unique_id[:8]}.ogg"
    status_msg = await message.answer("⏳ Audio yuklab olinmoqda va tahlil qilinmoqda...")

    stream = io.BytesIO()
    try:
        await bot.download(audio_obj, destination=stream)
        audio_bytes = stream.getvalue()
    except Exception as e:
        logger.error("Audio yuklab olishda xatolik: %s", e)
        await status_msg.edit_text("❌ Audio yuklab olishda xatolik yuz berdi.")
        return

    try:
        await status_msg.delete()
    except Exception:
        pass

    mime_type = getattr(audio_obj, "mime_type", None) or "audio/ogg"
    save_user_media(message.from_user.id, audio_bytes, file_name, mime_type)
    label = "Audio ma'ruza" if message.audio else "Ovozli xabar"

    await start_quiz_wizard(
        message, state,
        file_bytes=audio_bytes,
        file_mime=mime_type,
        file_name=file_name,
        label=label,
        source_type="audio",
        user_id=message.from_user.id,
    )


@router.message(F.photo)
async def process_photo_message(message: Message, bot: Bot, state: FSMContext) -> None:
    photo = message.photo[-1]  # Eng yuqori sifatlisi
    status_msg = await message.answer("⏳ Rasm yuklab olinmoqda...")

    stream = io.BytesIO()
    try:
        await bot.download(photo, destination=stream)
        photo_bytes = stream.getvalue()
    except Exception as e:
        logger.error("Rasm yuklab olishda xatolik: %s", e)
        await status_msg.edit_text("❌ Rasmni yuklab olishda xatolik yuz berdi.")
        return

    try:
        await status_msg.delete()
    except Exception:
        pass

    file_name = f"photo_{photo.file_unique_id[:8]}.jpg"
    mime_type = "image/jpeg"
    save_user_media(message.from_user.id, photo_bytes, file_name, mime_type)

    await start_quiz_wizard(
        message, state,
        file_bytes=photo_bytes,
        file_mime=mime_type,
        file_name=file_name,
        label="Rasm / Konspekt",
        source_type="image",
        user_id=message.from_user.id,
    )


# Oddiy xabar kelsa va boshqa FSM bo'lmasa -> Mavzu deb qabul qilish
@router.message(F.text & ~F.text.startswith("/"))
async def process_plain_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) > 120:
        # Uzun matn bo'lsa, konspekt deb hisoblaymiz
        title = text[:30].replace("\n", " ").strip() + "..."
        save_user_media(message.from_user.id, text_content=text)
        await start_quiz_wizard(message, state, text_content=text, label=title, source_type="text", user_id=message.from_user.id)
    else:
        # Qisqa matn bo'lsa, mavzu deb hisoblaymiz
        await start_quiz_wizard(message, state, topic=text, label=text, source_type="topic", user_id=message.from_user.id)


# ---------------- Wizard bosqichlari ---------------- #

async def start_quiz_wizard(
    message: Message,
    state: FSMContext,
    topic: str | None = None,
    text_content: str | None = None,
    file_bytes: bytes | None = None,
    file_mime: str | None = None,
    file_name: str | None = None,
    label: str | None = None,
    source_type: str = "topic",
    user_id: int | None = None,
) -> None:
    """Sozlamalar wizardini boshlash."""
    source_label = label or topic or file_name or "Mavzu"
    await state.update_data(
        quiz_topic=topic,
        quiz_text=text_content,
        quiz_file_mime=file_mime,
        quiz_file_name=file_name,
        quiz_source_label=source_label,
        quiz_source_type=source_type,
        quiz_user_id=user_id or (message.from_user.id if message.from_user else 0),
        quiz_count=5,
        quiz_options=4,
        quiz_diff="medium",
        quiz_timer=0,
    )

    text = (
        "✦ • ──────────────────── • ✦\n"
        "🎯 <b>QUIZ TEST SOZLAMALARI</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Manba:</b> <i>{html.escape(source_label, quote=False)}</i>\n\n"
        "1️⃣ <b>Nechta test savoli bo'lsin?</b>\n"
        "👇 Savollar sonini tanlang:"
    )
    kb = get_quiz_count_keyboard()
    if getattr(message, "edit_text", None):
        try:
            await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("qcfg:cnt:"))
async def handle_qcfg_count(callback: CallbackQuery, state: FSMContext) -> None:
    cnt = int(callback.data.split(":")[2])
    data = await state.get_data()
    source_label = data.get("quiz_source_label", "Mavzu")
    await state.update_data(quiz_count=cnt)
    await callback.answer(f"{cnt} ta savol tanlandi")

    text = (
        "✦ • ──────────────────── • ✦\n"
        "🎯 <b>QUIZ TEST SOZLAMALARI</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Manba:</b> <i>{html.escape(source_label, quote=False)}</i>\n"
        f"📊 <b>Savollar soni:</b> {cnt} ta\n\n"
        "2️⃣ <b>Har bir savolda nechta variant bo'lsin?</b>\n"
        "👇 Variantlar sonini tanlang:"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_quiz_options_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("qcfg:opt:"))
async def handle_qcfg_options(callback: CallbackQuery, state: FSMContext) -> None:
    opts = int(callback.data.split(":")[2])
    data = await state.get_data()
    source_label = data.get("quiz_source_label", "Mavzu")
    cnt = data.get("quiz_count", 5)
    await state.update_data(quiz_options=opts)
    await callback.answer(f"{opts} ta variant tanlandi")

    text = (
        "✦ • ──────────────────── • ✦\n"
        "🎯 <b>QUIZ TEST SOZLAMALARI</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Manba:</b> <i>{html.escape(source_label, quote=False)}</i>\n"
        f"📊 <b>Savollar soni:</b> {cnt} ta\n"
        f"🔘 <b>Variantlar soni:</b> {opts} ta\n\n"
        "3️⃣ <b>Testning qiyinlik darajasi qanday bo'lsin?</b>\n"
        "👇 Darajani tanlang:"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_quiz_difficulty_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("qcfg:diff:"))
async def handle_qcfg_diff(callback: CallbackQuery, state: FSMContext) -> None:
    diff = callback.data.split(":")[2]
    data = await state.get_data()
    source_label = data.get("quiz_source_label", "Mavzu")
    cnt = data.get("quiz_count", 5)
    opts = data.get("quiz_options", 4)
    await state.update_data(quiz_diff=diff)
    diff_title = {"easy": "Oson", "medium": "O'rta", "hard": "Qiyin", "olympiad": "Olimpiada"}.get(diff, "O'rta")
    await callback.answer(f"{diff_title} tanlandi")

    text = (
        "✦ • ──────────────────── • ✦\n"
        "🎯 <b>QUIZ TEST SOZLAMALARI</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Manba:</b> <i>{html.escape(source_label, quote=False)}</i>\n"
        f"📊 <b>Savollar:</b> {cnt} ta · 🔘 <b>Variantlar:</b> {opts} ta\n"
        f"🎚 <b>Daraja:</b> {diff_title}\n\n"
        "4️⃣ <b>Har bir savolga necha sekund vaqt berilsin (Taymer)?</b>\n"
        "👇 Vaqt chegarasini tanlang:"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_quiz_timer_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("qcfg:tm:"))
async def handle_qcfg_timer(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    tm = int(callback.data.split(":")[2])
    data = await state.get_data()
    await state.clear()

    source_label = data.get("quiz_source_label", "Test")
    cnt = data.get("quiz_count", 5)
    opts = data.get("quiz_options", 4)
    diff = data.get("quiz_diff", "medium")
    topic = data.get("quiz_topic")
    text_content = data.get("quiz_text")
    file_mime = data.get("quiz_file_mime")
    file_name = data.get("quiz_file_name")
    source_type = data.get("quiz_source_type", "topic")
    user_id = callback.from_user.id

    timer_str = "Cheklovsiz" if tm == 0 else f"{tm} soniya"
    await callback.answer(f"Taymer: {timer_str}")

    status_msg = None
    if callback.message:
        status_msg = await callback.message.edit_text(
            f"⏳ <b>'{html.escape(source_label, quote=False)}' asosida {cnt} ta sifatli test savollari shakllantirilmoqda...</b>\n\n"
            f"<i>Sun'iy intellekt savollarni imlo va mantiqiy jihatdan tekshirmoqda...</i>",
            parse_mode="HTML",
        )

    # Agar keshda fayl bo'lsa
    cached_media = get_user_media(user_id)
    file_bytes = cached_media.get("bytes") if cached_media else None

    # Avval berilgan savollarni olish (takrorlanmaslik uchun)
    used_q = await get_user_used_questions(user_id, source_label)

    # Gemini orqali test tuzish
    questions = await gemini_service.generate_quiz(
        topic=topic,
        text_content=text_content,
        file_bytes=file_bytes,
        file_mime=file_mime,
        file_name=file_name,
        count=cnt,
        options_count=opts,
        difficulty=diff,
        used_questions=used_q,
    )

    # Agar AI dan savol kelmasa -> Oflayn zaxira bazadan olish
    if not questions:
        logger.info("Gemini savol bermadi, oflayn zaxira savollardan foydalanilmoqda")
        questions = get_offline_quiz_questions(topic or source_label, count=cnt, options_count=opts)

    if not questions:
        if status_msg:
            await status_msg.edit_text("❌ Test tuzishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        return

    # Bazaga saqlash
    quiz_id = uuid.uuid4().hex[:10]
    clean_title = source_label.strip()[:40] or "Viktorina Test"

    await save_quiz(
        quiz_id=quiz_id,
        user_id=user_id,
        title=clean_title,
        source_type=source_type,
        topic=topic or source_label,
        questions=questions,
        options_count=opts,
        timer_seconds=tm,
        difficulty=diff,
    )

    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

    bot_info = await bot.get_me()
    escaped_title = html.escape(clean_title, quote=False)
    card_text = (
        f"🎯 <b>\"{escaped_title}\" testi tayyor!</b>\n"
        f"✦ • ──────────────────── • ✦\n\n"
        f"📊 <b>Savollar soni:</b> {len(questions)} ta\n"
        f"🔘 <b>Variantlar:</b> {opts} ta\n"
        f"⏱ <b>Taymer:</b> {timer_str}\n"
        f"🎚 <b>Qiyinlik:</b> {diff.capitalize()}\n\n"
        f"💡 <i>Ushbu testni hoziroq interaktiv yechishingiz, chop etish uchun PDF qilib yuklab olishingiz yoki guruhlarga ulashishingiz mumkin:</i>"
    )

    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=card_text,
        reply_markup=get_quiz_card_keyboard(quiz_id, bot_info.username or "quiz_tuzdimbot"),
        parse_mode="HTML",
    )
