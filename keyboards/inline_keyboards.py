from __future__ import annotations
from typing import Any
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


FAN_TOPICS: dict[str, dict[str, Any]] = {
    "matematika": {
        "title": "📐 Matematika",
        "topics": [
            ("Kvadrat tenglamalar", "Kvadrat tenglamalar"),
            ("Kasrlar va foizlar", "Kasrlar va foizlar"),
            ("Trigonometriya", "Trigonometriya"),
            ("Hosilalar va integrallar", "Hosilalar va integrallar"),
            ("Arifmetik progressiya", "Arifmetik va geometrik progressiya"),
            ("Geometriya asoslari", "Geometriya va planimetriya"),
            ("🎲 Barcha mavzular aralash", "Matematika (umumiy aralash)"),
        ],
    },
    "fizika": {
        "title": "⚡️ Fizika",
        "topics": [
            ("Nyuton qonunlari", "Nyuton qonunlari va dinamika"),
            ("Kinematika (harakat)", "Kinematika va to'g'ri chiziqli harakat"),
            ("Ish, quvvat va energiya", "Mexanik ish, quvvat va energiya"),
            ("Elektr toki va zanjirlar", "Elektr toki, Om qonuni va zanjirlar"),
            ("Optika va yorug'lik", "Optika va yorug'lik hodisalari"),
            ("Molekulyar fizika", "Molekulyar fizika va termodinamika"),
            ("🎲 Barcha mavzular aralash", "Fizika (umumiy aralash)"),
        ],
    },
    "ingliz_tili": {
        "title": "🇬🇧 Ingliz tili",
        "topics": [
            ("📝 Zamonlar formulalari (Amaliy)", "English Tenses Grammar Formulas (Fill in the blanks)"),
            ("Present Simple & Continuous", "Present Simple and Present Continuous"),
            ("Past Simple & Continuous", "Past Simple and Past Continuous"),
            ("Present Perfect", "Present Perfect tense"),
            ("Conditionals (If clauses)", "Conditionals (Zero, First, Second, Third)"),
            ("Passive Voice", "Passive Voice in English"),
            ("Vocabulary (Lug'at)", "English Essential Vocabulary"),
            ("Prepositions (Predloglar)", "English Prepositions (in, on, at, by)"),
            ("🎲 Barcha mavzular aralash", "Ingliz tili (General English)"),
        ],
    },
    "tarix": {
        "title": "🏛 O'zbekiston tarixi",
        "topics": [
            ("Amir Temur va Temuriylar", "Amir Temur va Temuriylar davlati"),
            ("Qadimgi Movarounnahr", "Qadimgi Movarounnahr va ilk davlatlar"),
            ("Jadidchilik harakati", "Jadidchilik harakati va ma'rifatparvarlar"),
            ("Uch xonlik davri", "Buxoro amirligi, Xiva va Qo'qon xonliklari"),
            ("Mustaqillik yillari", "O'zbekistonning mustaqillikka erishishi"),
            ("Buyuk Ipak yo'li", "Buyuk Ipak yo'li va savdo aloqalari"),
            ("🎲 Barcha mavzular aralash", "O'zbekiston tarixi (umumiy aralash)"),
        ],
    },
    "biologiya": {
        "title": "🧬 Biologiya",
        "topics": [
            ("Hujayra tuzilishi", "Hujayra tuzilishi va organoidlari"),
            ("Genetika va irsiyat", "Genetika va Mendel qonunlari"),
            ("Fotosintez va nafas", "Fotosintez va hujayraviy nafas olish"),
            ("Odam anatomiyasi", "Odam anatomiyasi va fiziologiyasi"),
            ("Botanika (O'simliklar)", "O'simliklar anatomiyasi va morfologiyasi"),
            ("Zoologiya (Hayvonlar)", "Hayvonot olami va xordalilar"),
            ("🎲 Barcha mavzular aralash", "Biologiya (umumiy aralash)"),
        ],
    },
    "dasturlash": {
        "title": "💻 Dasturlash (IT)",
        "topics": [
            ("Python asoslari", "Python asoslari va sintaksisi"),
            ("Python OOP (Klasslar)", "Python OOP va obyektga yo'naltirilgan dasturlash"),
            ("SQL va Ma'lumotlar bazasi", "SQL so'rovlari va ma'lumotlar bazasi"),
            ("Algoritmlar", "Algoritmlar va ma'lumotlar tuzilmasi"),
            ("Web: HTML, CSS, JS", "Web dasturlash: HTML, CSS va JavaScript"),
            ("Git va GitHub", "Git versiya boshqaruvi va GitHub"),
            ("🎲 Barcha mavzular aralash", "Dasturlash (umumiy IT)"),
        ],
    },
    "kimyo": {
        "title": "🧪 Kimyo",
        "topics": [
            ("Davriy jadval va qonun", "Mendeleyev davriy jadvali va qonuni"),
            ("Kimyoviy bog'lanishlar", "Kovalent, ion va metall bog'lanishlar"),
            ("Oksidlanish-qaytarilish", "Oksidlanish-qaytarilish reaksiyalari"),
            ("Organik kimyo", "Organik kimyo va uglevodorodlar"),
            ("Kislotalar, asoslar, tuzlar", "Kislotalar, asoslar va tuzlarning xossalari"),
            ("Eritmalar va konsentratsiya", "Eritmalar va foiz konsentratsiyasi"),
            ("🎲 Barcha mavzular aralash", "Kimyo (umumiy aralash)"),
        ],
    },
    "ona_tili": {
        "title": "🇺🇿 Ona tili va adabiyot",
        "topics": [
            ("Fonetika va imlo", "O'zbek tili fonetikasi va imlo qoidalari"),
            ("Morfologiya (So'z turkumlari)", "Morfologiya va so'z turkumlari"),
            ("Sintaksis (Gap bo'laklari)", "Sintaksis va gap bo'laklari"),
            ("Alisher Navoiy ijodi", "Alisher Navoiy hayoti va Xamsa dostonlari"),
            ("Zahiriddin Muhammad Bobur", "Bobur hayoti, lirikasi va Boburnoma"),
            ("Jadid adabiyoti", "Jadid adabiyoti (Fitrat, Cho'lpon, Qodiriy)"),
            ("🎲 Barcha mavzular aralash", "Ona tili va adabiyot (umumiy)"),
        ],
    },
}


def get_popular_topics_keyboard() -> InlineKeyboardMarkup:
    """Mashhur fanlar klaviaturasi (har bir fanning ichida aniq mavzulari bilan)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📐 Matematika", callback_data="qfan:matematika"),
                InlineKeyboardButton(text="💻 Dasturlash (IT)", callback_data="qfan:dasturlash"),
            ],
            [
                InlineKeyboardButton(text="🇬🇧 Ingliz tili", callback_data="qfan:ingliz_tili"),
                InlineKeyboardButton(text="🏛 O'zbekiston tarixi", callback_data="qfan:tarix"),
            ],
            [
                InlineKeyboardButton(text="🧬 Biologiya", callback_data="qfan:biologiya"),
                InlineKeyboardButton(text="⚡️ Fizika", callback_data="qfan:fizika"),
            ],
            [
                InlineKeyboardButton(text="🧪 Kimyo", callback_data="qfan:kimyo"),
                InlineKeyboardButton(text="🇺🇿 Ona tili va adabiyot", callback_data="qfan:ona_tili"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="menu:create"),
            ],
        ]
    )


def get_subtopics_keyboard(fan_key: str) -> InlineKeyboardMarkup:
    """Tanlangan fanning ichidagi aniq mavzular klaviaturasi."""
    fan_info = FAN_TOPICS.get(fan_key, {})
    topics = fan_info.get("topics", [])
    rows = []
    # 2 tadan qilib qatorlarga taxlash
    for i in range(0, len(topics) - 1, 2):
        row = [InlineKeyboardButton(text=topics[i][0], callback_data=f"qtop:{topics[i][1]}")]
        if i + 1 < len(topics) - 1:
            row.append(InlineKeyboardButton(text=topics[i + 1][0], callback_data=f"qtop:{topics[i + 1][1]}"))
        rows.append(row)

    # Oxirgi umumiy aralash tugmasi
    if topics:
        last_label, last_val = topics[-1]
        rows.append([InlineKeyboardButton(text=last_label, callback_data=f"qtop:{last_val}")])

    rows.append([InlineKeyboardButton(text="🔙 Boshqa fanlar", callback_data="menu:topic")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    """Quiz kartochkasi klaviaturasi.
    - Guruhda bo'lsa (is_group=True): QuizBot kabi yagona 'Men tayyorman!' tugmasi.
    - Shaxsiy chatda bo'lsa (is_group=False): Testni boshlash, Guruhda boshlash, Do'stlarga ulashish va menyu.
    """
    if is_group:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Men tayyorman!", callback_data=f"qgrp:start:{quiz_id}")]
            ]
        )

    if not full_menu:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="▶️ Testni boshlash",
                        callback_data=f"qrun:ready:{quiz_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="👥 Guruhda testni boshlash",
                        url=f"https://t.me/{bot_username}?startgroup=poll_{quiz_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📤 Do'stlarga ulashish",
                        switch_inline_query=f"quiz_{quiz_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="⚙️ Boshqa amallar (PDF, Taymer...)",
                        callback_data=f"qcard:more:{quiz_id}",
                    ),
                ],
            ]
        )

    # To'liq menyu (full_menu=True)
    rows = [
        [
            InlineKeyboardButton(
                text="▶️ Testni boshlash",
                callback_data=f"qrun:ready:{quiz_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="👥 Guruhda testni boshlash",
                url=f"https://t.me/{bot_username}?startgroup=poll_{quiz_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📤 Do'stlarga ulashish",
                switch_inline_query=f"quiz_{quiz_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⏱ Taymerni o'zgartirish",
                callback_data=f"qedit:tm:{quiz_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📄 PDF test varaqasi",
                callback_data=f"qexp:pdf:{quiz_id}",
            ),
            InlineKeyboardButton(
                text="📝 Word (.docx)",
                callback_data=f"qexp:docx:{quiz_id}",
            ),
        ],
    ]
    if has_media:
        rows.append([
            InlineKeyboardButton(
                text="🔄 Shu manbadan yangi to'plam 🎯",
                callback_data=f"qrun:next_batch:{quiz_id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="🔙 Qisqa menyuga qaytish",
            callback_data=f"qcard:less:{quiz_id}",
        ),
        InlineKeyboardButton(
            text="🏠 Bosh menyu",
            callback_data="menu:home",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_quiz_finish_keyboard(
    quiz_id: str,
    bot_username: str = "quiz_tuzdimbot",
    has_wrong: bool = False,
    has_media: bool = False,
    correct: int = 0,
    total: int = 0,
    percentage: int = 0,
    **kwargs: Any,
) -> InlineKeyboardMarkup:
    """Test yakunlanganda natijalar klaviaturasi (ulashish, qayta ishlash, sertifikat)."""
    rows = []
    if percentage >= 70 or (total > 0 and correct >= total * 0.7):
        rows.append([
            InlineKeyboardButton(
                text="🎓 Rasmiy Sertifikatni yuklab olish 🏆",
                callback_data=f"qexp:cert:{quiz_id}:{correct}:{total}:{percentage}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="📤 Do'stlarga ulashish",
            switch_inline_query=f"quiz_{quiz_id}",
        ),
        InlineKeyboardButton(
            text="👥 Guruhda o'ynash",
            url=f"https://t.me/{bot_username}?startgroup=poll_{quiz_id}",
        ),
    ])
    rows.append([
        InlineKeyboardButton(
            text="🔄 Qaytadan boshlash",
            callback_data=f"qrun:start:{quiz_id}",
        ),
    ])
    if has_wrong:
        rows.append([
            InlineKeyboardButton(
                text="💡 Xatolar ustida ishlash 🎯",
                callback_data=f"qrun:retry_wrong:{quiz_id}",
            ),
        ])
    rows.append([
        InlineKeyboardButton(
            text="🎲 Yangi test tuzish",
            callback_data="menu:topic",
        ),
        InlineKeyboardButton(
            text="🏠 Asosiy menyu",
            callback_data="menu:home",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
