from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Asosiy menyu klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎲 Mavzu bo'yicha", callback_data="menu:topic"),
                InlineKeyboardButton(text="🏛 DTM & Imtihonlar", callback_data="menu:presets"),
            ],
            [
                InlineKeyboardButton(text="📁 PDF / Word hujjatdan", callback_data="menu:doc"),
                InlineKeyboardButton(text="🔗 YouTube / Havoladan", callback_data="menu:url"),
            ],
            [
                InlineKeyboardButton(text="🎥 Video darslikdan", callback_data="menu:video"),
                InlineKeyboardButton(text="🎙 Ovoz / Audiodan", callback_data="menu:audio"),
            ],
            [
                InlineKeyboardButton(text="📸 Rasmdan (Doska/Kitob)", callback_data="menu:image"),
                InlineKeyboardButton(text="📋 Matndan test tuzish", callback_data="menu:text"),
            ],
            [
                InlineKeyboardButton(text="📢 Kanalga avtoposting", callback_data="menu:channels"),
                InlineKeyboardButton(text="📊 Mening statistikam", callback_data="menu:stats"),
            ],
            [
                InlineKeyboardButton(text="📜 Mening testlarim", callback_data="menu:history"),
                InlineKeyboardButton(text="ℹ️ Qo'llanma", callback_data="menu:help"),
            ],
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
    """Mashhur mavzular klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📐 Matematika", callback_data="qtop:Matematika"),
                InlineKeyboardButton(text="💻 Dasturlash (IT)", callback_data="qtop:Dasturlash"),
            ],
            [
                InlineKeyboardButton(text="🇬🇧 Ingliz tili (IELTS)", callback_data="qtop:Ingliz tili"),
                InlineKeyboardButton(text="🏛 O'zbekiston tarixi", callback_data="qtop:Tarix"),
            ],
            [
                InlineKeyboardButton(text="🧬 Biologiya", callback_data="qtop:Biologiya"),
                InlineKeyboardButton(text="⚡️ Fizika", callback_data="qtop:Fizika"),
            ],
            [
                InlineKeyboardButton(text="🌍 Geografiya", callback_data="qtop:Geografiya"),
                InlineKeyboardButton(text="🧠 Mantiqiy savollar", callback_data="qtop:Mantiq"),
            ],
            [
                InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="menu:home"),
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


def get_quiz_card_keyboard(quiz_id: str, bot_username: str = "quiz_tuzdimbot", has_media: bool = True) -> InlineKeyboardMarkup:
    """Yangi tuzilgan quiz kartochkasi klaviaturasi."""
    rows = [
        [
            InlineKeyboardButton(text="▶️ O'zim yechish (Interaktiv)", callback_data=f"qrun:start:{quiz_id}"),
        ],
        [
            InlineKeyboardButton(text="👥 Guruhga tashlash (Quiz Poll)", url=f"https://t.me/{bot_username}?startgroup=poll_{quiz_id}"),
            InlineKeyboardButton(text="📩 Barcha testlarni tashlash", callback_data=f"qrun:dump:{quiz_id}"),
        ],
    ]
    if has_media:
        rows.append([
            InlineKeyboardButton(text="🔄 Shu manbadan keyingi yangi testlar 🎯", callback_data=f"qrun:next_batch:{quiz_id}")
        ])
    rows.extend([
        [
            InlineKeyboardButton(text="📄 PDF test varaqasi", callback_data=f"qexp:pdf:{quiz_id}"),
            InlineKeyboardButton(text="📝 Word (.docx)", callback_data=f"qexp:docx:{quiz_id}"),
        ],
        [
            InlineKeyboardButton(text="🤖 @QuizBot matni", callback_data=f"qexp:quizbot:{quiz_id}"),
            InlineKeyboardButton(text="📤 Ulashish", switch_inline_query=f"quiz_{quiz_id}"),
        ],
        [
            InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="menu:home"),
        ],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_quiz_finish_keyboard(
    quiz_id: str,
    has_wrong: bool = False,
    has_media: bool = True,
    bot_username: str = "quiz_tuzdimbot",
    correct: int = 0,
    total: int = 0,
    percentage: int = 0,
) -> InlineKeyboardMarkup:
    """Test yakunlanganda natijalar klaviaturasi."""
    rows = []
    if percentage >= 70 or (total > 0 and correct >= total * 0.7):
        rows.append([
            InlineKeyboardButton(
                text="🎓 Rasmiy Sertifikatni yuklab olish 🏆",
                callback_data=f"qexp:cert:{quiz_id}:{correct}:{total}:{percentage}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="🔄 Qaytadan boshlash", callback_data=f"qrun:start:{quiz_id}")
    ])
    if has_wrong:
        rows.append([
            InlineKeyboardButton(text="💡 Xatolar ustida ishlash 🎯", callback_data=f"qrun:retry_wrong:{quiz_id}")
        ])
    if has_media:
        rows.append([
            InlineKeyboardButton(text="🔄 Shu manbadan keyingi yangi testlar 🎯", callback_data=f"qrun:next_batch:{quiz_id}")
        ])
    rows.append([
        InlineKeyboardButton(text="👥 Guruhga tashlash (Quiz Poll)", url=f"https://t.me/{bot_username}?startgroup=poll_{quiz_id}"),
        InlineKeyboardButton(text="📩 Barcha testlarni tashlash", callback_data=f"qrun:dump:{quiz_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="📄 PDF test varaqasi", callback_data=f"qexp:pdf:{quiz_id}"),
        InlineKeyboardButton(text="📝 Word (.docx)", callback_data=f"qexp:docx:{quiz_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="🎲 Yangi test tuzish", callback_data="menu:topic"),
        InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
