import html
import io
import logging
import os
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import UPLOADS_DIR
from database.db import save_quiz, get_user_used_questions
import re
from keyboards.inline_keyboards import (
    get_main_menu_keyboard,
    get_create_source_keyboard,
    get_back_to_menu_keyboard,
    get_popular_topics_keyboard,
    get_subtopics_keyboard,
    FAN_TOPICS,
    get_quiz_count_keyboard,
    get_quiz_options_keyboard,
    get_quiz_difficulty_keyboard,
    get_quiz_timer_keyboard,
    get_quiz_card_keyboard,
)
from services.gemini_service import (
    GeminiService,
    is_english_grammar_or_formula_content,
    is_english_content,
)
from services.quiz_service import (
    extract_text_from_file,
    get_offline_quiz_questions,
    save_user_media,
    get_user_media,
)
from services.web_service import get_youtube_transcript_text, fetch_web_page_text
from utils.states import QuizCreateState

logger = logging.getLogger(__name__)
router = Router()
gemini_service = GeminiService()


@router.message(Command("newquiz"))
@router.callback_query(F.data == "menu:create")
async def handle_create_menu(event: Message | CallbackQuery, state: FSMContext) -> None:
    """Test tuzish: Mavzu bo'yicha yoki Manba orqali tanlash."""
    await state.clear()
    text = (
        "🎲 <b>Qanday usulda test tuzmoqchisiz?</b>\n\n"
        "• ✍️ <b>Mavzu bo‘yicha</b> — shunchaki mavzu yoki fan nomini yozasiz, AI mavzuga moslab o‘zi tuzadi.\n"
        "• 📁 <b>Manba orqali</b> — PDF, kitob, Word, rasm, konspekt yoki havola yuborasiz, AI o‘sha manba asosida tuzadi.\n\n"
        "<i>Kerakli usulni tanlang:</i> 👇"
    )
    kb = get_create_source_keyboard()
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


def clean_topic_input(text: str) -> str:
    """Foydalanuvchi yozgan test buyrug'i yoki matnidan asosiy mavzu nomini tozalab ajratib olish."""
    cleaned = text.strip()
    # "Mavzu:", "Mavzusi:" kabilarni boshidan tozalash
    cleaned = re.sub(r"^(mavzu|mavzusi|fan|mavzusi bo['‘`]?yicha)\s*[:\-–—]?\s*", "", cleaned, flags=re.IGNORECASE)
    # "haqida test tuzib ber", "mavzusida test", "ga test", "test tuz" kabilarni oxiridan tozalash
    cleaned = re.sub(r"\s+(haqida|bo['‘`]?yicha|ga|dan)?\s*(test|savollar|viktorina)\s*(tuzib ber|tuzish|tuz|qilib ber|kerak)?\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+mavzusida\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+haqida\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    return cleaned if cleaned else text.strip()


@router.callback_query(F.data.in_(["menu:topic", "menu:presets"]))
async def handle_menu_topic(callback: CallbackQuery, state: FSMContext) -> None:
    """Mavzu bo'yicha test tuzish."""
    await state.set_state(QuizCreateState.waiting_topic)
    await callback.answer()
    text = (
        "✍️ <b>Mavzu bo‘yicha test tuzish:</b>\n\n"
        "O‘zingiz istagan <b>har qanday mavzuni chatga yozib yuboring</b>:\n"
        "<i>(Masalan: Nyuton qonunlari, Kvadrat tenglamalar, Present Continuous, Alisher Navoiy, Hujayra tuzilishi...)</i>\n\n"
        "Yoki fanni tanlab, uning ichidagi <b>aniq mavzulardan birini tanlang</b>: 👇"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_popular_topics_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("qfan:"))
async def handle_fan_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Tanlangan fanning ichidagi aniq mavzular ro'yxatini ko'rsatish."""
    fan_key = callback.data.split(":")[1]
    fan_info = FAN_TOPICS.get(fan_key)
    if not fan_info:
        await callback.answer()
        return

    title = fan_info["title"]
    kb = get_subtopics_keyboard(fan_key)
    text = (
        f"📚 <b>{title} fanidan aniq mavzuni tanlang:</b>\n\n"
        f"<i>Quyidagi mashhur mavzulardan birini tanlang yoki chatga o‘zingiz xohlagan boshqa aniq mavzuni yozing:</i> 👇"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("qtop:"))
async def handle_topic_preset(callback: CallbackQuery, state: FSMContext) -> None:
    topic_name = callback.data.split(":", 1)[1]
    await callback.answer(f"{topic_name[:30]} tanlandi")
    await start_quiz_wizard(callback.message, state, topic=topic_name, source_type="topic", user_id=callback.from_user.id)


# ---------------- Xabarlarni qabul qilish ---------------- #

@router.message(QuizCreateState.waiting_topic, F.text)
async def process_topic_text(message: Message, state: FSMContext) -> None:
    raw_topic = message.text.strip()
    clean_topic = clean_topic_input(raw_topic)
    await start_quiz_wizard(message, state, topic=clean_topic, label=clean_topic, source_type="topic", user_id=message.from_user.id)


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

        is_grammar = is_english_grammar_or_formula_content(topic=clean_title, text=text_content, filename=file_name)
        is_en = is_english_content(topic=clean_title, text=text_content, filename=file_name)
        grammar_notice = ""
        if is_grammar:
            grammar_notice = (
                "\n\n🇬🇧 <b>Ingliz tili grammatika/formula hujjati aniqlandi!</b>\n"
                "<i>AI formulalar asosida amaliy gaplar tuzib, tushib qolgan so‘zni topish (fill-in-the-blank) shaklida chuqur testlar tuzadi.</i>"
            )
        elif is_en:
            grammar_notice = (
                "\n\n🇬🇧 <b>Ingliz tili (Cambridge / CEFR standarti) aniqlandi!</b>\n"
                "<i>AI sayoz savollar tuzmaydi — boy amaliy kontekst, kollokatsiyalar va qoidalar asosida sifatli testlar tuziladi.</i>"
            )

        caption = (message.caption or "").lower()
        is_batch_requested = any(k in caption for k in [
            "har bir", "alohida", "mavzular", "darslar", "20 ta", "bo'lib", "bolib",
            "mavzuga", "darsga", "unit", "har biriga", "ajrat", "mavzusi"
        ])

        if is_batch_requested:
            await state.update_data(
                doc_text=text_content,
                doc_title=clean_title,
                batch_text=text_content,
                batch_title=clean_title,
                file_bytes=file_bytes,
                file_name=file_name,
                mime_type=doc.mime_type or "application/pdf",
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="3 tadan", callback_data="qbatch:cnt:3"),
                        InlineKeyboardButton(text="5 tadan", callback_data="qbatch:cnt:5"),
                    ],
                    [
                        InlineKeyboardButton(text="10 tadan", callback_data="qbatch:cnt:10"),
                        InlineKeyboardButton(text="15 tadan", callback_data="qbatch:cnt:15"),
                    ],
                    [
                        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu:home"),
                    ],
                ]
            )
            await message.answer(
                f"📚 <b>«{html.escape(clean_title, quote=False)}» qabul qilindi!</b>"
                f"{grammar_notice}\n\n"
                f"Fayldagi <b>har bir mavzu/dars uchun</b> alohida testlar to‘plami tuziladi.\n"
                f"Har bir mavzuda nechtadan savol bo‘lsin? Tanlang: 👇",
                reply_markup=kb,
                parse_mode="HTML",
            )
            return

        has_multiple_topics = len(text_content) > 1200 or any(w in text_content.lower() for w in ["unit ", "lesson ", "mavzu", "dars ", "chapter "])
        if has_multiple_topics:
            await state.update_data(
                doc_text=text_content,
                doc_title=clean_title,
                batch_text=text_content,
                batch_title=clean_title,
                file_bytes=file_bytes,
                file_name=file_name,
                mime_type=doc.mime_type or "application/pdf",
            )
            mode_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🎯 Bitta umumiy test", callback_data="qdoc_mode:single"),
                    ],
                    [
                        InlineKeyboardButton(text="📚 Har bir mavzuga alohida testlar", callback_data="qdoc_mode:batch"),
                    ],
                    [
                        InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu:home"),
                    ],
                ]
            )
            await message.answer(
                f"📄 <b>«{html.escape(clean_title, quote=False)}» qabul qilindi!</b>"
                f"{grammar_notice}\n\n"
                f"Ushbu fayldan qanday test tuzmoqchisiz?\n\n"
                f"• 🎯 <b>Bitta umumiy test</b> — butun hujjat bo‘yicha bitta umumiy test\n"
                f"• 📚 <b>Har bir mavzuga alohida testlar</b> — fayldagi har bir mavzu (Unit/Lesson) uchun alohida-alohida testlar to‘plamini tuzish\n\n"
                f"<i>Kerakli usulni tanlang:</i> 👇",
                reply_markup=mode_kb,
                parse_mode="HTML",
            )
            return

        await start_quiz_wizard(
            message, state,
            text_content=text_content,
            file_bytes=file_bytes,
            file_mime=doc.mime_type or "application/pdf",
            file_name=file_name,
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


# ---------------- Har bir mavzuga alohida testlar (Batch Mode) ---------------- #

@router.callback_query(F.data == "qdoc_mode:single")
async def handle_doc_single_mode(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text_content = data.get("doc_text", "")
    clean_title = data.get("doc_title", "Hujjat")
    await callback.answer()
    if callback.message:
        await start_quiz_wizard(
            callback.message,
            state,
            text_content=text_content,
            file_bytes=data.get("file_bytes"),
            file_mime=data.get("mime_type"),
            file_name=data.get("file_name"),
            label=clean_title,
            source_type="doc",
            user_id=callback.from_user.id,
        )


@router.callback_query(F.data == "qdoc_mode:batch")
async def handle_doc_batch_mode(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    clean_title = data.get("doc_title") or "Hujjat"
    await callback.answer()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="3 tadan", callback_data="qbatch:cnt:3"),
                InlineKeyboardButton(text="5 tadan", callback_data="qbatch:cnt:5"),
            ],
            [
                InlineKeyboardButton(text="10 tadan", callback_data="qbatch:cnt:10"),
                InlineKeyboardButton(text="15 tadan", callback_data="qbatch:cnt:15"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu:home"),
            ],
        ]
    )
    if callback.message:
        await callback.message.edit_text(
            f"📚 <b>«{html.escape(clean_title, quote=False)}» — Har bir mavzuga alohida test:</b>\n\n"
            f"Fayldagi har bir mavzu/dars uchun nechtadan savol tuzilsin? Tanlang: 👇",
            reply_markup=kb,
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("qbatch:cnt:"))
async def handle_batch_count(callback: CallbackQuery, state: FSMContext) -> None:
    cnt = int(callback.data.split(":")[2])
    await state.update_data(batch_count=cnt)
    await callback.answer(f"{cnt} tadan savol tanlandi")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡️ 10 soniya", callback_data="qbatch:tm:10"),
                InlineKeyboardButton(text="⏱ 15 soniya", callback_data="qbatch:tm:15"),
            ],
            [
                InlineKeyboardButton(text="⏱ 30 soniya", callback_data="qbatch:tm:30"),
                InlineKeyboardButton(text="⏳ Cheklovsiz", callback_data="qbatch:tm:0"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu:home"),
            ],
        ]
    )
    if callback.message:
        await callback.message.edit_text(
            f"⏱ <b>Har bir savol uchun vaqt chegarasini (taymer) tanlang:</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("qbatch:tm:"))
async def handle_batch_timer(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    tm = int(callback.data.split(":")[2])
    data = await state.get_data()
    cnt = data.get("batch_count", 5)
    text_content = data.get("doc_text") or data.get("batch_text") or ""
    clean_title = data.get("doc_title") or data.get("batch_title") or "Hujjat"
    user_id = callback.from_user.id

    if not text_content:
        cached = get_user_media(user_id)
        if cached:
            text_content = cached.get("text") or ""
            if not text_content and cached.get("bytes") and cached.get("name"):
                text_content = extract_text_from_file(cached["bytes"], cached["name"])
            clean_title = clean_title or cached.get("name") or "Hujjat"

    if not text_content:
        await callback.answer("Hujjat matni topilmadi", show_alert=True)
        return

    await callback.answer("Mavzular bo'yicha testlar tuzilmoqda...")

    status_msg = None
    if callback.message:
        status_msg = await callback.message.edit_text(
            f"⏳ <b>«{html.escape(clean_title, quote=False)}» tahlil qilinmoqda...</b>\n\n"
            f"Sun'iy intellekt barcha dars/mavzularni aniqlab, har biri uchun alohida {cnt} tadan sifatli test tuzmoqda...\n\n"
            f"<i>Biroz kuting...</i>",
            parse_mode="HTML",
        )

    topics_data = await gemini_service.generate_batch_topic_quizzes(
        text_content=text_content,
        questions_per_topic=cnt,
        options_count=4,
        difficulty="medium",
    )

    if not topics_data:
        if status_msg:
            await status_msg.edit_text(
                "❌ Hujjatdagi mavzularni ajratishda xatolik yuz berdi. Iltimos, bitta umumiy test tuzishni tanlang yoki faylni qaytadan yuboring.",
                reply_markup=get_back_to_menu_keyboard(),
                parse_mode="HTML",
            )
        return

    # Har bir mavzu bo'yicha alohida quiz yaratish va bazaga saqlash
    from database.db import get_user_max_batch_id
    max_b = await get_user_max_batch_id(user_id)
    new_batch_id = max_b + 1
    new_batch_title = f"{new_batch_id}-to'plam: {clean_title[:22]} ({len(topics_data)} ta test)"

    created_quizzes = []
    for t_item in topics_data:
        t_title = t_item.get("topic_title") or "Dars"
        t_questions = t_item.get("questions") or []
        if not t_questions:
            continue

        q_id = uuid.uuid4().hex[:10]
        full_title = f"{t_title}"[:40]
        await save_quiz(
            quiz_id=q_id,
            user_id=user_id,
            title=full_title,
            source_type="doc_topic",
            topic=full_title,
            questions=t_questions,
            options_count=4,
            timer_seconds=tm,
            difficulty="medium",
            batch_id=new_batch_id,
            batch_title=new_batch_title,
        )
        created_quizzes.append({
            "quiz_id": q_id,
            "title": full_title,
            "count": len(t_questions),
        })

    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

    target_chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    if not created_quizzes:
        await bot.send_message(
            chat_id=target_chat_id,
            text="⚠️ Mavzular bo'yicha savollar shakllantirilmadi.",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # Natijalarni klaviatura bilan chiqarish (har bir mavzuga to'g'ridan-to'g'ri ochiladigan tugma)
    rows = []
    for idx, q in enumerate(created_quizzes[:25], 1):
        rows.append([
            InlineKeyboardButton(
                text=f"{idx}. 🎯 {q['title']} ({q['count']} ta)",
                callback_data=f"qopen:{q['quiz_id']}",
            )
        ])

    rows.append([
        InlineKeyboardButton(text="📜 Barcha testlarim", callback_data="menu:history"),
        InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:home"),
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    finish_text = (
        f"🎉 <b>«{html.escape(clean_title, quote=False)}» faylidan {len(created_quizzes)} ta mavzu bo'yicha testlar muvaffaqiyatli tayyorlandi!</b>\n\n"
        f"<i>Istalgan testni boshlash yoki do'stlarga ulashish uchun quyidagi ro'yxatdan tanlang:</i> 👇"
    )
    await bot.send_message(
        chat_id=target_chat_id,
        text=finish_text,
        reply_markup=kb,
        parse_mode="HTML",
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


@router.message(F.text.regexp(r"^https?://[^\s]+"))
async def process_url_message(message: Message, state: FSMContext) -> None:
    """YouTube yoki veb-havoladan test tuzish."""
    url = message.text.strip()
    is_youtube = "youtube.com" in url or "youtu.be" in url

    if is_youtube:
        status_msg = await message.answer("⏳ <b>YouTube video tahlil qilinmoqda va subtitrlar o'qilmoqda...</b>", parse_mode="HTML")
        transcript, title = await get_youtube_transcript_text(url)
        try:
            await status_msg.delete()
        except Exception:
            pass

        if transcript and len(transcript) > 80:
            save_user_media(message.from_user.id, text_content=transcript)
            await start_quiz_wizard(
                message, state,
                text_content=transcript,
                label=title,
                source_type="video",
                user_id=message.from_user.id,
            )
        else:
            await message.answer(
                "⚠️ Ushbu YouTube videoda ochiq subtitrlar topilmadi.\n\n"
                "Iltimos, video mavzusini chatga matn sifatida yozib yuboring (masalan: <i>Python darsi</i>) yoki boshqa videoni sinab ko'ring.",
                parse_mode="HTML",
            )
    else:
        status_msg = await message.answer("⏳ <b>Veb sahifa yuklanmoqda va tahlil qilinmoqda...</b>", parse_mode="HTML")
        page_text, title = await fetch_web_page_text(url)
        try:
            await status_msg.delete()
        except Exception:
            pass

        if page_text and len(page_text) > 100:
            save_user_media(message.from_user.id, text_content=page_text)
            await start_quiz_wizard(
                message, state,
                text_content=page_text,
                label=title,
                source_type="doc",
                user_id=message.from_user.id,
            )
        else:
            await message.answer(
                "⚠️ Sahifadan matn ajratib olish imkoni bo'lmadi yoki matn hajmi juda qisqa.\n"
                "Iltimos, matnni nusxalab to'g'ridan-to'g'ri chatga yuboring.",
                parse_mode="HTML",
            )


# Oddiy xabar kelsa va boshqa FSM bo'lmasa -> Mavzu deb qabul qilish
@router.message(F.text & ~F.text.startswith("/"))
async def process_plain_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    lower_text = text.lower().strip()
    if lower_text in ("mening testlarim", "testlarim", "statistika", "mening statistikam", "kun testi", "duel", "yordam", "bosh menyu"):
        return

    # Foydalanuvchi "har bir mavzuga test qilib ber" deb yozsa va hujjat nazarda tutilgan bo'lsa
    batch_keywords = [
        "har bir mavzu", "har bir dars", "alohida mavzu", "alohida dars",
        "har biriga", "mavzularga bo'l", "mavzularga bol", "har bir mavzudan",
        "har bir darsdan", "mavzular bo'yicha", "mavzular boyicha", "darslar bo'yicha",
        "mavzularga ajrat", "har bir unit", "alohida test", "har bir mavzuga", "har bir darsga",
        "har bir mavzusiga", "mavzularga bo'lib", "mavzularga bolib"
    ]
    is_batch_phrase = any(bk in lower_text for bk in batch_keywords) or (
        any(k in lower_text for k in ["har bir", "alohida", "bo'lib", "bolib", "ajratib"])
        and any(w in lower_text for w in ["mavzu", "dars", "test", "savol", "unit"])
    )

    if is_batch_phrase:
        cached = get_user_media(message.from_user.id)
        if cached and (cached.get("text") or cached.get("bytes")):
            clean_title = cached.get("name") or "Yuklangan hujjat"
            text_content = cached.get("text") or ""
            if not text_content and cached.get("bytes") and cached.get("name"):
                text_content = extract_text_from_file(cached["bytes"], cached["name"])

            if text_content:
                await state.update_data(
                    batch_text=text_content,
                    batch_title=clean_title,
                    doc_text=text_content,
                    doc_title=clean_title,
                    file_bytes=cached.get("bytes"),
                    file_name=cached.get("name"),
                    mime_type=cached.get("mime"),
                )
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="3 tadan", callback_data="qbatch:cnt:3"),
                            InlineKeyboardButton(text="5 tadan", callback_data="qbatch:cnt:5"),
                        ],
                        [
                            InlineKeyboardButton(text="10 tadan", callback_data="qbatch:cnt:10"),
                            InlineKeyboardButton(text="15 tadan", callback_data="qbatch:cnt:15"),
                        ],
                        [
                            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu:home"),
                        ],
                    ]
                )
                await message.answer(
                    f"📚 <b>Oxirgi yuklangan «{html.escape(clean_title, quote=False)}» fayli bo'yicha:</b>\n\n"
                    f"Har bir mavzu/dars uchun nechtadan savol tuzilsin? Tanlang: 👇",
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                return

        await message.answer(
            "📁 <b>Marhamat, o'sha PDF yoki Word faylni hozir chatga tashlang!</b>\n\n"
            "Bot fayldagi barcha dars va mavzularni (masalan, 20 ta mavzuni) avtomatik aniqlab, har biriga alohida testlar to'plamini tuzib beradi.",
            parse_mode="HTML",
        )
        return

    is_grammar = is_english_grammar_or_formula_content(topic=text, text=text)
    is_en = is_english_content(topic=text, text=text)
    if is_grammar or is_en:
        clean_topic = clean_topic_input(text)
        title = clean_topic[:35]
        save_user_media(message.from_user.id, text_content=text)
        await start_quiz_wizard(
            message,
            state,
            topic=clean_topic,
            text_content=text,
            label=title,
            source_type="text",
            user_id=message.from_user.id,
        )
    elif len(text) > 200:
        # Uzun matn bo'lsa, konspekt deb hisoblaymiz
        title = text[:35].replace("\n", " ").strip() + "..."
        save_user_media(message.from_user.id, text_content=text)
        await start_quiz_wizard(message, state, text_content=text, label=title, source_type="text", user_id=message.from_user.id)
    else:
        # Qisqa matn bo'lsa, aniq mavzu deb hisoblaymiz (masalan: "Nyuton qonunlari", "Kvadrat tenglamalar", "Present Continuous")
        clean_topic = clean_topic_input(text)
        await start_quiz_wizard(message, state, topic=clean_topic, label=clean_topic, source_type="topic", user_id=message.from_user.id)


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

    is_grammar = is_english_grammar_or_formula_content(
        topic=topic or source_label,
        text=text_content,
        filename=file_name,
    )
    is_en = is_english_content(
        topic=topic or source_label,
        text=text_content,
        filename=file_name,
    )
    grammar_note = ""
    if is_grammar:
        grammar_note = "\n💡 <i>Ingliz tili formulalari asosida amaliy gap to‘ldirish savollari tuziladi.</i>\n"
    elif is_en:
        grammar_note = "\n🇬🇧 <i>Ingliz tili: Cambridge/CEFR darajasidagi chuqur amaliy kontekstli testlar tuziladi.</i>\n"

    text = (
        "✦ • ──────────────────── • ✦\n"
        "🎯 <b>TEST SOZLAMALARI (1/4-QADAM)</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Manba:</b> <i>«{html.escape(source_label, quote=False)}»</i>\n"
        f"{grammar_note}\n"
        "1️⃣ <b>Nechta test savoli tuzilsin?</b>\n"
        "👇 <i>Quyidagi sonlardan birini tanlang:</i>"
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
        "🎯 <b>TEST SOZLAMALARI (2/4-QADAM)</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Manba:</b> <i>«{html.escape(source_label, quote=False)}»</i>\n"
        f"📊 <b>Savollar soni:</b> {cnt} ta ✅\n\n"
        "2️⃣ <b>Har bir savolda nechta variant bo'lsin?</b>\n"
        "👇 <i>Variantlar sonini tanlang:</i>"
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
        "🎯 <b>TEST SOZLAMALARI (3/4-QADAM)</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Manba:</b> <i>«{html.escape(source_label, quote=False)}»</i>\n"
        f"📊 <b>Savollar:</b> {cnt} ta · 🔘 <b>Variantlar:</b> {opts} ta ✅\n\n"
        "3️⃣ <b>Testning qiyinlik darajasi qanday bo'lsin?</b>\n"
        "👇 <i>Qiyinlik darajasini tanlang:</i>"
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
        "🎯 <b>TEST SOZLAMALARI (4/4-QADAM)</b>\n"
        "✦ • ──────────────────── • ✦\n\n"
        f"📌 <b>Manba:</b> <i>«{html.escape(source_label, quote=False)}»</i>\n"
        f"📊 <b>Savollar:</b> {cnt} ta · 🔘 <b>Variantlar:</b> {opts} ta · 🎚 <b>Daraja:</b> {diff_title} ✅\n\n"
        "4️⃣ <b>Har bir savolga necha soniya vaqt berilsin (Taymer)?</b>\n"
        "👇 <i>Vaqt chegarasini tanlang:</i>"
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

    # Agar manba "topic" bo'lsa, keshdagi eski fayl/matn aralashmasligi kerak
    if source_type == "topic":
        file_bytes = None
        file_mime = None
        file_name = None
        text_content = None
        topic = topic or source_label
    else:
        cached_media = get_user_media(user_id)
        if cached_media:
            file_bytes = file_bytes or cached_media.get("bytes")
            file_mime = file_mime or cached_media.get("mime")
            file_name = file_name or cached_media.get("name")
            text_content = text_content or cached_media.get("text")

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
    elif len(questions) < cnt:
        # Savollar soni so'ralgandan kam bo'lsa, to'liq cnt taga yetkazish
        needed = cnt - len(questions)
        logger.info("Savollar soni kam (%d/%d), yana %d ta to'ldirilmoqda...", len(questions), cnt, needed)
        import re
        used_now = (used_q or set()) | {re.sub(r"^\[\d+/\d+\]\s*", "", q["question"]).strip().lower() for q in questions}
        extra = get_offline_quiz_questions(
            topic or source_label,
            count=needed,
            options_count=opts,
            used_questions=used_now,
        )
        questions.extend(extra[:needed])

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
    bot_username = bot_info.username or "quiz_tuzdimbot"
    from handlers.quiz_play import format_quiz_ready_text
    quiz_obj = {
        "quiz_id": quiz_id,
        "title": clean_title,
        "questions": questions,
        "question_count": len(questions),
        "timer_seconds": tm,
    }
    card_text = format_quiz_ready_text(quiz_obj, bot_username=bot_username, is_group=False)

    target_chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    await bot.send_message(
        chat_id=target_chat_id,
        text=card_text,
        reply_markup=get_quiz_card_keyboard(
            quiz_id,
            bot_username=bot_username,
            is_group=False,
            title=clean_title,
        ),
        parse_mode="HTML",
    )
