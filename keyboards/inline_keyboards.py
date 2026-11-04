from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Asosiy menyu klaviaturasi (QuizBot kabi sodda, toza va tushunarli)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎲 Test tuzish", callback_data="menu:create"),
            ],
            [
                InlineKeyboardButton(text="📜 Mening testlarim", callback_data="menu:history"),
            ],
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="menu:stats"),
                InlineKeyboardButton(text="ℹ️ Qo'llanma", callback_data="menu:help"),
            ],
        ]
    )


def get_create_source_keyboard() -> InlineKeyboardMarkup:
    """Test tuzish usulini tanlash (Mavzu yoki Manba)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ Mavzu bo'yicha (AI o'zi tuzadi)", callback_data="menu:topic"),
            ],
            [
                InlineKeyboardButton(text="📁 Manba orqali (Fayl / Kitob / Rasm)", callback_data="menu:source"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu:home"),
            ],
        ]
    )


def get_files_menu_keyboard() -> InlineKeyboardMarkup:
    """Fayl va hujjat turlari sub-menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 PDF yoki Word (.docx)", callback_data="menu:doc"),
                InlineKeyboardButton(text="📸 Rasm / Fotosurat", callback_data="menu:image"),
            ],
            [
                InlineKeyboardButton(text="🎙 Ovoz / Audio (MP3)", callback_data="menu:audio"),
                InlineKeyboardButton(text="🎥 Video darslik", callback_data="menu:video"),
            ],
            [
                InlineKeyboardButton(text="📋 Matn (Konspekt)", callback_data="menu:text"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bosh menyuga qaytish", callback_data="menu:home"),
            ],
        ]
    )


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Kutish va yo'riqnoma bosqichlari uchun qisqa orqaga qaytish klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bosh menyuga qaytish", callback_data="menu:home")]
        ]
    )


def get_exam_presets_keyboard() -> InlineKeyboardMarkup:
    """DTM, IELTS va Milliy Sertifikat maxsus shablonlari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏛 DTM: Majburiy fanlar bloki", callback_data="qtop:DTM Majburiy fanlar (Ona tili, Matematika, Tarix)"),
            ],
            [
                InlineKeyboardButton(text="📐 DTM: Matematika va Fizika", callback_data="qtop:DTM Matematika va Fizika bloki"),
                InlineKeyboardButton(text="🧪 DTM: Biologiya va Kimyo", callback_data="qtop:DTM Biologiya va Kimyo bloki"),
            ],
            [
                InlineKeyboardButton(text="📚 DTM: Tarix va Huquq", callback_data="qtop:DTM Tarix va Huquqshunoslik"),
                InlineKeyboardButton(text="🇺🇿 Ona tili va Adabiyot", callback_data="qtop:Ona tili va Adabiyot Milliy Sertifikat"),
            ],
            [
                InlineKeyboardButton(text="🇬🇧 IELTS / CEFR Vocabulary", callback_data="qtop:IELTS and CEFR Advanced Vocabulary"),
                InlineKeyboardButton(text="🎧 IELTS Listening Audio Test", callback_data="qtop:IELTS Listening Comprehension Audio Test"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu:home"),
            ],
        ]
    )


def get_popular_topics_keyboard() -> InlineKeyboardMarkup:
    """Mashhur fanlar klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📐 Matematika", callback_data="qtop:Matematika"),
                InlineKeyboardButton(text="💻 Dasturlash (IT)", callback_data="qtop:Dasturlash"),
            ],
            [
                InlineKeyboardButton(text="🇬🇧 Ingliz tili", callback_data="qtop:Ingliz tili"),
                InlineKeyboardButton(text="🏛 O'zbekiston tarixi", callback_data="qtop:Tarix"),
            ],
            [
                InlineKeyboardButton(text="🧬 Biologiya", callback_data="qtop:Biologiya"),
                InlineKeyboardButton(text="⚡️ Fizika", callback_data="qtop:Fizika"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="menu:create"),
            ],
        ]
    )


def get_quiz_count_keyboard() -> InlineKeyboardMarkup:
    """Savollar soni tanlash."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="3 ta", callback_data="qcfg:cnt:3"),
                InlineKeyboardButton(text="5 ta", callback_data="qcfg:cnt:5"),
                InlineKeyboardButton(text="10 ta", callback_data="qcfg:cnt:10"),
            ],
            [
                InlineKeyboardButton(text="15 ta", callback_data="qcfg:cnt:15"),
                InlineKeyboardButton(text="20 ta", callback_data="qcfg:cnt:20"),
                InlineKeyboardButton(text="30 ta", callback_data="qcfg:cnt:30"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu:home"),
            ],
        ]
    )


def get_quiz_options_keyboard() -> InlineKeyboardMarkup:
    """Variantlar soni tanlash."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="2 ta (A, B)", callback_data="qcfg:opt:2"),
                InlineKeyboardButton(text="3 ta (A, B, C)", callback_data="qcfg:opt:3"),
                InlineKeyboardButton(text="4 ta (A, B, C, D)", callback_data="qcfg:opt:4"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu:home"),
            ],
        ]
    )


def get_quiz_difficulty_keyboard() -> InlineKeyboardMarkup:
    """Qiyinlik darajasini tanlash."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Oson (Boshlang'ich)", callback_data="qcfg:diff:easy"),
                InlineKeyboardButton(text="🟡 O'rta (Standart)", callback_data="qcfg:diff:medium"),
            ],
            [
                InlineKeyboardButton(text="🔴 Qiyin (Murakkab)", callback_data="qcfg:diff:hard"),
                InlineKeyboardButton(text="🏆 Olimpiada (Ekspert)", callback_data="qcfg:diff:olympiad"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu:home"),
            ],
        ]
    )


def get_quiz_timer_keyboard() -> InlineKeyboardMarkup:
    """Taymer tanlash."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ Cheklovsiz", callback_data="qcfg:tm:0"),
                InlineKeyboardButton(text="⚡️ 10 sekund", callback_data="qcfg:tm:10"),
            ],
            [
                InlineKeyboardButton(text="⏱ 15 sekund", callback_data="qcfg:tm:15"),
                InlineKeyboardButton(text="⏱ 30 sekund", callback_data="qcfg:tm:30"),
            ],
            [
                InlineKeyboardButton(text="⏱ 45 sekund", callback_data="qcfg:tm:45"),
                InlineKeyboardButton(text="⏱ 60 sekund", callback_data="qcfg:tm:60"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu:home"),
            ],
        ]
    )


def get_change_timer_keyboard(quiz_id: str) -> InlineKeyboardMarkup:
    """Mavjud testning taymerini o'zgartirish klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ Cheklovsiz (Vaqt yo'q)", callback_data=f"qsettm:{quiz_id}:0"),
                InlineKeyboardButton(text="⚡️ 10 sekund", callback_data=f"qsettm:{quiz_id}:10"),
            ],
            [
                InlineKeyboardButton(text="⏱ 15 sekund", callback_data=f"qsettm:{quiz_id}:15"),
                InlineKeyboardButton(text="⏱ 30 sekund", callback_data=f"qsettm:{quiz_id}:30"),
            ],
            [
                InlineKeyboardButton(text="⏱ 45 sekund", callback_data=f"qsettm:{quiz_id}:45"),
                InlineKeyboardButton(text="⏱ 60 sekund (1 daqiqa)", callback_data=f"qsettm:{quiz_id}:60"),
            ],
            [
                InlineKeyboardButton(text="⏱ 90 sekund", callback_data=f"qsettm:{quiz_id}:90"),
                InlineKeyboardButton(text="⏱ 120 sekund (2 daqiqa)", callback_data=f"qsettm:{quiz_id}:120"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data=f"qsettm_back:{quiz_id}"),
            ],
        ]
    )


def get_quiz_card_keyboard(
    quiz_id: str,
    bot_username: str = "quiz_tuzdimbot",
    has_media: bool = False,
    full_menu: bool = False,
    is_group: bool = False,
) -> InlineKeyboardMarkup:
    """QuizBot kabi yagona 'Men tayyorman!' tugmasi."""
    callback_data = f"qgrp:start:{quiz_id}" if is_group else f"qrun:start:{quiz_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Men tayyorman!", callback_data=callback_data)
            ]
        ]
    )


def get_quiz_finish_keyboard(
    quiz_id: str,
    bot_username: str = "quiz_tuzdimbot",
    **kwargs: Any,
) -> InlineKeyboardMarkup:
    """QuizBot kabi test yakunlanganda yagona 'Do'stlarga ulashish' tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Do'stlarga ulashish",
                    switch_inline_query=f"quiz_{quiz_id}",
                )
            ]
        ]
    )
