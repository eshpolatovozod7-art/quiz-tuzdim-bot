import asyncio
import json
import logging
import os
import random
import re
import tempfile
from typing import Any
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, DEFAULT_MODEL

logger = logging.getLogger(__name__)


def sanitize_question_text(q_text: str) -> str:
    """Robotik 'Matnga ko'ra', 'Manbaga asosan' kabi prefikslarni tozalash va matnni tekislash."""
    if not q_text:
        return ""
    cleaned = q_text.strip()
    pattern = (
        r"^(Matnga ko['‘`]?ra|Manbaga ko['‘`]?ra|Manbaga asosan|Hujjatga ko['‘`]?ra|"
        r"Berilgan matnga asosan|Matnda aytilishicha|Ushbu matnda|Manba matniga ko['‘`]?ra|"
        r"According to the text|According to the passage|Based on the text),?\s*"
    )
    cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def try_repair_and_parse_json(text: str) -> Any:
    """Tugallanmagan yoki kesilib qolgan JSON matnidan xavfsiz holda ma'lumotlarni ajratib olish."""
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    # 1. To'g'ridan-to'g'ri json.loads
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2. Agar oxiri kesilgan bo'lsa, oxirgi tugallangan '}' dan orqaga tekshirib yopish
    last_brace = raw.rfind("}")
    while last_brace > 0:
        candidate = raw[:last_brace + 1].strip()
        for closer in ("]", "}]", "}]}", "]}", "}", "}}"):
            try:
                res = json.loads(candidate + closer)
                if res:
                    return res
            except Exception:
                pass
        try:
            res = json.loads(candidate)
            if res:
                return res
        except Exception:
            pass
        last_brace = raw.rfind("}", 0, last_brace)

    return None


def is_english_grammar_or_formula_content(
    topic: str | None = None,
    text: str | None = None,
    filename: str | None = None,
) -> bool:
    """Mavzu, matn yoki fayl nomi ingliz tili grammatikasi, zamonlar va formulalarga oidligini aniqlash."""
    combined = f"{topic or ''} {filename or ''} {(text or '')[:15000]}".lower()

    # 1. Zamonlar va asosiy grammatik mavzular
    tense_keywords = [
        "present simple", "present continuous", "present progressive",
        "past simple", "past continuous", "past progressive",
        "present perfect", "past perfect", "future simple",
        "future continuous", "future perfect", "conditionals",
        "passive voice", "active voice", "modal verbs", "modal verb",
        "gerund", "infinitive", "reported speech", "relative clauses",
        "irregular verbs", "question tags", "english grammar",
        "english tenses", "tenses formula", "formula of tenses",
        "grammar formula", "grammatika formulalari", "zamon formulalari",
        "ingliz tili zamonlari", "ingliz tili grammatika",
    ]
    if any(k in combined for k in tense_keywords):
        return True

    # 2. Formula sintaksisi va tuzilishi
    formula_patterns = [
        r"\b(s|subject)\s*\+\s*(am|is|are|was|were|have|has|had|do|does|did|will|verb|v1|v2|v3|v-ing|ving|ved)\b",
        r"\b(am|is|are)\s*\+\s*(v-ing|ving|not|\+)\b",
        r"\b(have|has|had)\s*\+\s*(v3|ved|been|not|\+)\b",
        r"\b(do|does|did)\s*\+\s*(s|subject|not|\+)\b",
        r"\b(was|were)\s*\+\s*(v-ing|ving|not|\+)\b",
        r"\bwill\s*\+\s*(v1|be|have)\b",
        r"\b(s\s*\+\s*v(1|2|s|es)?)\b",
        r"\b(s\s*\+\s*to\s*be)\b",
        r"\bam\s*/\s*is\s*/\s*are\b",
        r"\bwas\s*/\s*were\b",
        r"\bdo\s*/\s*does\b",
        r"\bhave\s*/\s*has\b",
        r"\bverb\s*\+\s*(ing|ed|s|es)\b",
        r"\bv-ing\b",
        r"\bv1\s*/\s*v2\b",
    ]
    for pat in formula_patterns:
        if re.search(pat, combined, re.IGNORECASE):
            return True

    # 3. Ingliz tili va qoida/formula birikmasi
    has_english = any(w in combined for w in ["ingliz", "english", "ielts", "cefr"])
    has_formula = any(w in combined for w in ["formula", "qoida", "tuzilish", "struktur", "tense", "zamon", "verb", "gap", "tushib qolgan"])
    if has_english and has_formula:
        return True

    return False


def is_beginner_difficulty(difficulty: str | None) -> bool:
    """Qiyinlik darajasi boshlang'ich / oson ekanligini tekshirish."""
    diff = (difficulty or "medium").lower()
    return diff in ("easy", "beginner", "oson", "elementary", "a1", "a2", "boshlang'ich", "boshlangich")


def is_vocabulary_content(
    topic: str | None = None,
    text: str | None = None,
    filename: str | None = None,
) -> bool:
    """Foydalanuvchi ingliz tili lug'at ro'yxati (vocabulary list / word - translation) yuborganini aniqlash."""
    combined = f"{topic or ''} {filename or ''}".lower()
    vocab_keywords = [
        "vocabulary", "vocablry", "vocab", "lug'at", "lugat", "lug‘at", "lug`at",
        "words list", "word list", "wordlist", "words", "word",
        "so'zlar ro'yxati", "sozlar royxati", "so'zlar", "sozlar", "so'z", "soz",
        "so'z boyligi", "soz boyligi", "phrasal verbs", "idioms",
        "essential words", "inglizcha so'z", "english words",
        "tarjima", "tarjimalar", "dictionary", "glossary", "lexis"
    ]
    if any(k in combined for k in vocab_keywords):
        return True

    if not text:
        return False

    raw_text = text.strip()
    if any(k in raw_text[:500].lower() for k in vocab_keywords):
        return True

    from services.quiz_service import parse_vocabulary_pairs
    pairs = parse_vocabulary_pairs(raw_text)
    if len(pairs) >= 2:
        return True

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    vocab_line_pattern = re.compile(
        r"^([\d+•\-\*]+[\.\)]?\s*)?"
        r"[a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲʻʼ']"
        r"[a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲʻʼ'\s\(\)/]{0,40}\s*"
        r"(?:->|=>|[-–—:=/•|]|\t|\s{2,})\s*"
        r".+$"
    )
    matching_lines = sum(1 for line in lines if vocab_line_pattern.match(line))
    if len(lines) >= 2 and matching_lines >= max(2, int(len(lines) * 0.30)):
        return True

    return False


def is_english_content(
    topic: str | None = None,
    text: str | None = None,
    filename: str | None = None,
) -> bool:
    """Mavzu, matn yoki fayl ingliz tili (grammatika, lug'at, IELTS, CEFR va h.k.)ga oidligini aniqlash."""
    combined = f"{topic or ''} {filename or ''} {(text or '')[:15000]}".lower()

    # 1. Lug'at (vocabulary) tekshiruvi
    if is_vocabulary_content(topic, text, filename):
        return True

    # 2. Ingliz tili kalit so'zlari
    english_keywords = [
        "ingliz", "english", "ielts", "cefr", "toefl", "duolingo",
        "vocabulary", "phrasal verb", "collocation", "grammar",
        "preposition", "tense", "modal verb", "irregular verb",
        "conditional", "passive voice", "reported speech", "gerund",
        "infinitive", "milliy sertifikat", "reading comprehension",
        "listening", "inversion", "relative clause", "conjunction",
        "idiom", "idioms", "antonym", "synonym", "cambridge",
        "dtm ingliz", "b1 english", "b2 english", "c1 english", "a1 english", "a2 english",
    ]
    if any(k in combined for k in english_keywords):
        return True

    # 3. Grammatika va formulalar tekshiruvi
    if is_english_grammar_or_formula_content(topic, text, filename):
        return True

    # 4. Matndagi inglizcha to'xtash so'zlari ulushi (Inglizcha matn/kitob/maqolani aniqlash)
    words = [w.strip(".,!?:;\"'()[]{}") for w in combined.split() if w.strip()]
    if len(words) >= 15:
        common_en_stop_words = {
            "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
            "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
            "this", "but", "his", "by", "from", "they", "we", "say", "her",
            "she", "or", "an", "will", "my", "one", "all", "would", "there",
            "their", "what", "so", "up", "out", "if", "about", "who", "get",
            "which", "go", "me", "when", "make", "can", "like", "time", "no",
            "just", "him", "know", "take", "people", "into", "year", "your",
            "good", "some", "could", "them", "see", "other", "than", "then",
            "now", "look", "only", "come", "its", "over", "think", "also"
        }
        en_stop_count = sum(1 for w in words[:100] if w in common_en_stop_words)
        if en_stop_count >= 10 and (en_stop_count / len(words[:100])) > 0.15:
            return True

    return False


PEDAGOGICAL_DEPTH_DIRECTIVE = (
    "\n"
    "════════════════════════════════════════════════════════════════════\n"
    "🧠 TEST SIFATI VA CHUQURLIGI BO'YICHA QAT'IY TALABLAR (SAYOZLIKNI TAQIQLASH):\n"
    "════════════════════════════════════════════════════════════════════\n"
    "1. SAYOZ, IBTIDOIY VA BIRLAMCHI YODLASH SAVOLLARI QAT'IYAN TAQIQLANADI:\n"
    "   - 'X nima deb ataladi?', 'Qachon sodir bo'lgan?', 'Kim kashf qilgan?', 'Atamaning nomi nima?', 'Formulasi nima?' kabi 1 soniyada yoddan aytiladigan, hech qanday fikrlash talab qilmaydigan quruq ensiklopedik savollar ASLO TUZILMASIN!\n"
    "   - Savollar Blum taksonomiyasining yuqori pog'onalari (Qo'llash, Tahlil, Mantiqiy xulosa chiqarish, Taqqoslash)ga asoslansin.\n\n"
    "2. AMALIY VAZIYATLAR (KEYSLAR), TAHLIL VA SABAB-OQIBAT ZANJIRI:\n"
    "   - Savol real hayotiy misol, ilmiy tajriba/eksperiment natijasi, masalali keys yoki amaliy vaziyat shaklida bo'lsin.\n"
    "   - O'quvchi shunchaki eslash orqali emas, qoidani o'sha vaziyatga tadbiq etib, sabab-oqibatni tahlil qilib javob topsin.\n"
    "   - 'Agar parametr o'zgarsa jarayon qanday kechadi?', 'Nima sababdan bunday hodisa yuz beradi?', 'Qaysi holatda ushbu qoida istisno bo'ladi?' kabi sababiy mexanizmlarni so'rang.\n\n"
    "3. CHALG'ITUVCHI VARIANTLAR SIFATI (HIGH-QUALITY DISTRACTORS):\n"
    "   - Noto'g'ri variantlar mutlaqo bema'ni, kulgili yoki bir qarashdayoq ko'rinib turgan oson variantlar bo'lmasin!\n"
    "   - Noto'g'ri variantlar — o'quvchilar eng ko'p yo'l qo'yadigan tipik xatoliklar (common misconceptions), qoidadagi nozik shartni hisobga olmaslik oqibati yoki o'xshash tushunchalarning chalkashliklari bo'lsin.\n"
    "   - O'quvchi diqqat bilan o'ylamasdan, shunchaki tavakkal qilib to'g'ri javobni topa olmasin.\n\n"
    "4. VARIANTLAR SIMMETRIYASI VA BALANSI:\n"
    "   - Barcha variantlar taxminan bir xil hajmda (uzunlikda), bir xil grammatik tuzilishda va teng darajada ishonarli bo'lsin.\n"
    "   - To'g'ri javob eng uzun, eng chiroyli yoki eng batafsil bo'lib qolmasin (to'g'ri javob tashqi ko'rinishidan fosh bo'lmasin).\n\n"
    "5. 'MATNGA KO'RA...', 'MANBAGA ASOSAN...' KABI ROBOTIK PREFIKSLAR TAQIQLANADI:\n"
    "   - Savol matnini 'Matnga ko'ra...', 'Manbaga ko'ra...', 'Hujjatda aytilishicha...', 'Ushbu darslikka asosan...' kabi robotik so'zlar bilan boshlamang!\n"
    "   - Savol to'g'ridan-to'g'ri tabiiy, ravon va mustaqil imtihon savoli shaklida yozilsin.\n\n"
    "6. EXPLANATION (IZOH) PEDAGOGIK AHAMIYATGA EGA BO'LSIN:\n"
    "   - Shunchaki 'A javob to'g'ri' deb quruq yozilmasin.\n"
    "   - Qisqa, lo'nda va ilmiy-ommabop qilib (maksimal 180 belgi) nima uchun aynan shu javob to'g'riligi va qaysi mexanizm ishlashi o'quvchiga o'rgatilsin.\n\n"
    "NAMUNAVIY TAQQOSLASH (QANDAY TUZISH KERAK VA QANDAY TUZMASLIK KERAK):\n"
    "❌ TAQIQLANGAN SAYOZ SAVOLLAR:\n"
    "- 'Alisher Navoiy qachon tug'ilgan?' (Quruq sana)\n"
    "- 'Nyutonning ikkinchi qonuni formulasi qaysi?' (Quruq formula)\n"
    "- 'Manbaga ko'ra, fotosintez nima?' (Robotik prefiks va sayozlik)\n\n"
    "✅ TALAB QILINGAN YUQORI SIFATLI PEDAGOGIK SAVOLLAR:\n"
    "- 'Massasi 60 kg bo\\'lgan odam lift ichidagi tarozida turibdi. Lift pastga qarab 2 m/s² tezlanish bilan harakatlansa, tarozi ko\\'rsatgichi necha Nyuton bo\\'ladi? (g = 10 m/s²)'\n"
    "  Variantlar: ['480 N', '600 N', '720 N', '120 N']\n"
    "- 'Gorizontal tekislikda harakatlanayotgan jismga ta\\'sir etuvchi natijaviy kuch 3 barobar oshirilib, jism massasi 1.5 barobar kamaytirilsa, uning tezlanishi qanday o\\'zgaradi?'\n"
    "  Variantlar: ['4.5 barobar ortadi', '2 barobar ortadi', '3 barobar kamayadi', 'O\\'zgarmaydi']\n"
    "════════════════════════════════════════════════════════════════════\n\n"
)


ENGLISH_PEDAGOGICAL_MASTER_DIRECTIVE = (
    "\n"
    "════════════════════════════════════════════════════════════════════\n"
    "🇬🇧 INGLIZ TILI BO'YICHA XALQARO DARAJA (CAMBRIDGE / CEFR B1-C1 / IELTS) STANDARTI:\n"
    "════════════════════════════════════════════════════════════════════\n"
    "Ingliz tili bo'yicha savollarda SAYOZLIK (boshlang'ich yodlash) QAT'IYAN TAQIQLANADI:\n\n"
    "1. QURUQ TARJIMA VA QURUQ NAZARIYAT ASLO TUZILMASIN:\n"
    "   - 'X so'zining o'zbekcha tarjimasi nima?', 'Y so'zining sinonimi qaysi?' kabi 1 soniyalik quruq tarjima savollari MUTLAQO TAQIQLANADI!\n"
    "   - 'Present Perfect formulasini toping', 'Ushbu gap qaysi zamonda?' kabi quruq nomlash savollari TAQIQLANADI!\n\n"
    "2. SO'Z BOYLIGI VA IBORALAR FAQAT JONLI KONTEKSTDA (CONTEXTUAL CLOZE & COLLOCATIONS):\n"
    "   - So'zlar, frazeologik birikmalar (phrasal verbs) va iboralar to'liq, mazmunli gap ichida '______' qoldirilib tekshirilsin.\n"
    "   - Kollokatsiyalar (masalan: 'reach a compromise', 'pay attention to', 'take into account', 'heavy traffic') va bog'lanuvchi predloglar (e.g. 'interested in', 'prevent from', 'accused of') tabiiy kontekstda berilsin.\n"
    "   - Gap ichida to'g'ri so'zni tanlashga undovchi mantiqiy kalit (context clue, collocation, preposition) bo'lishi shart.\n\n"
    "3. GRAMMATIKA — AMALIY VA CHUQUR VAZIYATLI GAP TO'LDIRISH (FILL-IN-THE-BLANKS / CLOZE):\n"
    "   - Zamonlar (Tenses), Shart mayli (Conditionals), Majhul nisbat (Passive), O'zlashtirma gap (Reported Speech), Inversiya (Inversion), Modal fe'llar jonli gaplar ichida tekshirilsin.\n"
    "   - Gapda tekshiriladigan qism o'rniga '______' qoldiring (masalan: 'Look at how spotless the kitchen is! Sarah ______ it all morning, though she ______ the exact same clean three days ago.').\n"
    "   - Gaplarda vaqt signallari (time markers), kontekstli qarama-qarshiliklar va nozik qoidalar aks etsin.\n\n"
    "4. YUQORI SIFATLI CHALG'ITUVCHILAR (HIGH-QUALITY DISTRACTORS):\n"
    "   - Noto'g'ri variantlar — o'quvchilar eng ko'p adashadigan tipik xatoliklar (common learner pitfalls, confusing word pairs: affect/effect, raise/rise, borrow/lend, o'xshash zamon shakllari) bo'lsin.\n"
    "   - Bir qarashdayoq ko'rinib turadigan, kulgili yoki qoidaga umuman aloqasiz variantlar bo'lmasin.\n\n"
    "5. O'ZBEK TILIDAGI PEDAGOGIK IZOH (EXPLANATION):\n"
    "   - To'g'ri javob nega to'g'riligi va qaysi qoida yoki kollokatsiya ishlagani hamda boshqa variantlar nima sababdan mos kelmasligi o'zbek tilida lo'nda (maksimal 180 belgi) tushuntirilsin.\n\n"
    "NAMUNAVIY TAQQOSLASH (INGLIZ TILI UCHUN):\n"
    "❌ TAQIQLANGAN SAYOZ SAVOLLAR:\n"
    "- ''Dentist' so\\'zining o\\'zbekcha tarjimasi nima?' (Quruq tarjima TAQIQLANGAN)\n"
    "- 'I ______ a student. (am/is/are)' (Ibtidoiy 1-sinf darajasi TAQIQLANGAN)\n"
    "- 'Present Continuous formulasi qaysi?' (Quruq nazariya TAQIQLANGAN)\n\n"
    "✅ TALAB QILINGAN YUQORI SIFATLI SAVOLLAR:\n"
    "- 'After suffering from an excruciating toothache all night, Michael immediately visited the ______ to extract the severely infected molar.'\n"
    "  Variantlar: ['optometrist', 'dentist', 'dermatologist', 'cardiologist']\n"
    "  Izoh: 'Toothache' (tish og\\'rig\\'i) va 'molar' (oziq tish) konteksti bemor aynan 'dentist' (tish shifokori)ga borganini bildiradi.\n"
    "- 'By the time the rescue team arrived at the isolated village, the volunteers ______ essential medical supplies to all residents.'\n"
    "  Variantlar: ['had already distributed', 'have already distributed', 'already distributed', 'were distributing']\n"
    "  Izoh: 'By the time + Past Simple' tugallangan ish-harakat uchun oldingi o\\'tgan zamon (Past Perfect)ni talab qiladi.\n"
    "- 'Despite hours of heated debate, neither of the political parties was willing to ______ a compromise on the new reform.'\n"
    "  Variantlar: ['reach', 'make', 'settle', 'strike']\n"
    "  Izoh: 'Reach a compromise' (kelishuvga erishish) turg\\'un kollokatsiya hisoblanadi.\n"
    "════════════════════════════════════════════════════════════════════\n\n"
)


MASTER_TEACHER_METHODOLOGY_DIRECTIVE = (
    "\n"
    "════════════════════════════════════════════════════════════════════\n"
    "👨‍🏫 TAJRIBALI USTOZ-METODIST NIGOHI BILAN TEST TUZISH STANDARTI:\n"
    "════════════════════════════════════════════════════════════════════\n"
    "Siz shunchaki sun'iy intellekt emassiz — siz 20 yillik pedagogik tajribaga ega,\n"
    "o'quvchilarning psixologiyasi, darsdagi odatiy xatolari va nozik 'ilmoqlari'ni\n"
    "besh qo'lday biladigan OLIY TOIFALI USTOZ-METODIST VA REPETITORSIZ!\n\n"
    "Haqiqiy ustoz har bir savolni tuzishda quyidagi 4 ta ustozona tamoyil asosida o'ylaydi:\n\n"
    "1. 🎯 DIAGNOSTIK VA ILMOQLI SAVOL (O'quvchi bu mavzuda qayerda adashadi?):\n"
    "   - Ustoz har bir savolni boshlashdan oldin o'ziga savol beradi:\n"
    "     'O'quvchilarim ushbu qoidani o'rganganda eng ko'p qaysi nozik joyda adashadi? Qaysi istisno yoki shart ularni chalg'itadi?'\n"
    "   - Savol o'quvchining shunchaki quruq yodlaganini emas, mavzuning mohiyatini va 'ilmoqli' joylarini tushunganini tekshirsin.\n\n"
    "2. 🧩 CHALG'ITUVCHILAR — TALABANING REAL XATOLARI (Har bir variant ma'noga ega):\n"
    "   - Noto'g'ri variantlar tasodifiy o'ylab topilmaydi! Har bir variant talabaning muayyan xato fikrlashini aks ettirsin:\n"
    "     * To'g'ri javob: Qoidani chuqur tushungan o'quvchi tanlaydi.\n"
    "     * 1-tuzoq: Qoidaning birinchi yarmini bilib, ikkinchi nozik shartini unutgan o'quvchi varianti.\n"
    "     * 2-tuzoq: O'xshash qoida, shakl yoki zamon bilan chalkashtirgan o'quvchi varianti.\n"
    "     * 3-tuzoq: Shoshilib, kontekstni to'liq o'qimay yuzaki qaragan o'quvchi varianti.\n\n"
    "3. 💡 USTOZONA VA O'RGATUVCHI IZOH (Explanation):\n"
    "   - Haqiqiy ustoz hech qachon 'A javob to'g'ri' deb quruq yozmaydi!\n"
    "   - Izohni xuddi o'quvchining yonida turib, uning xatosini mehr bilan tuzatayotgan ustozdek yozing:\n"
    "     '💡 Ustoz maslahati: Ko\\'pchilik bu yerda [X] deb adashadi, lekin [nozik shart] tufayli [Y] to\\'g\\'ri bo\\'ladi. Qoida: ...'\n"
    "   - Izoh maksimal 180 belgi (Telegram poll chegarasi) ichida ixcham, lekin o'quvchiga 'Aha!' dedirtiradigan bilim bersin.\n\n"
    "4. ⚖️ DIDAKTIK XILMA-XILLIK (Hamma savol bir xil qolipda bo'lmasin):\n"
    "   - Savollarning biri vaziyatli keys, biri sabab-oqibat, biri qoidadagi istisno/ilmoq, biri ikki tushunchani taqqoslash bo'lsin.\n"
    "════════════════════════════════════════════════════════════════════\n\n"
)


VOCABULARY_BEGINNER_DIRECTIVE = (
    "\n"
    "════════════════════════════════════════════════════════════════════\n"
    "🟢 QAT'IY TALAB: BOSHLANG'ICH DARAJA (BEGINNER / ELEMENTARY) LUG'AT TESTI:\n"
    "════════════════════════════════════════════════════════════════════\n"
    "Foydalanuvchi ingliz tili lug'atini (so'zlar ro'yxatini) taqdim etdi va BOSHLANG'ICH (Beginner / Oson) darajani tanladi.\n"
    "🚨 ENG MUHIM TALAB (ODDIY SO'Z-TARJIMA VA MA'NO SAVOLLARI):\n"
    "- Beginner darajadagi o'quvchi ingliz tilidagi uzun va murakkab gaplarni, qiyin grammatikani bilmaydi!\n"
    "- Shuning uchun bu darajada uzun murakkab gaplar, chigal gap to'ldirish (cloze) testlari ASLO TUZILMASIN!\n"
    "- Savollar xuddi maktab darsligidagi kabi O'TA ODDIY, TO'G'RIDAN-TO'G'RI SO'Z-TARJIMA va MA'NO shaklida bo'lsin:\n\n"
    "1. SAVOL SHAKLLARI (savollarni aralash qilib tuzing):\n"
    "   a) O'zbekcha so'zning inglizcha tarjimasi:\n"
    "      Masalan: '«suv» so\\'zining inglizcha tarjimasi qaysi?' -> Variantlar: ['water', 'milk', 'bread', 'tea']\n"
    "      Masalan: '«kitob» so\\'zi ingliz tilida nima deyiladi?' -> Variantlar: ['book', 'pen', 'desk', 'bag']\n"
    "      Masalan: '«olma» — to\\'g\\'ri inglizcha tarjimani tanlang:' -> Variantlar: ['apple', 'orange', 'banana', 'lemon']\n"
    "   b) Inglizcha so'zning o'zbekcha ma'nosi:\n"
    "      Masalan: '«water» so\\'zining ma\\'nosi nima?' -> Variantlar: ['suv', 'non', 'choy', 'sut']\n"
    "      Masalan: '«cat» so\\'zining o\\'zbekcha tarjimasini toping:' -> Variantlar: ['mushuk', 'kuchuk', 'qush', 'baliq']\n"
    "   c) Oddiy so'z juftligi / moslik:\n"
    "      Masalan: 'Qaysi juftlik to\\'g\\'ri?' -> Variantlar: ['suv - water', 'non - pen', 'kitob - milk', 'maktab - dog']\n"
    "      yoki: '«suv» — ...' -> Variantlar: ['water', 'fire', 'air', 'earth']\n\n"
    "2. VARIANTLAR (OPTIONS):\n"
    "   - Har bir variant lo'nda va qisqa (1 ta so'z yoki qisqa ibora) bo'lsin.\n"
    "   - To'g'ri javob berilgan lug'atdagi so'z yoki uning tarjimasi bo'lsin.\n"
    "   - Noto'g'ri variantlar (distractors) ham taqdim etilgan lug'atdagi boshqa so'zlardan yoki boshlang'ich darajaga mos boshqa oddiy so'zlardan tuzilsin.\n\n"
    "3. IZOH (EXPLANATION):\n"
    "   - O'zbek tilida, samimiy va o'rgatuvchi bo'lsin (maksimal 180 belgi).\n"
    "   - Masalan: '💡 water — suv degani. Boshqa variantlar: milk — sut, bread — non, tea — choy.'\n"
    "════════════════════════════════════════════════════════════════════\n\n"
)

VOCABULARY_INTERMEDIATE_DIRECTIVE = (
    "\n"
    "════════════════════════════════════════════════════════════════════\n"
    "🟡 DARAJA: O'RTA (INTERMEDIATE / B1-B2) LUG'AT TESTI:\n"
    "════════════════════════════════════════════════════════════════════\n"
    "- Lug'atdagi so'zlar tabiiy kundalik kontekstdagi sodda gaplar (fill-in-the-blanks) orqali tekshirilsin.\n"
    "- Gapdagi tekshirilayotgan so'z o'rniga '______' qoldiring.\n"
    "- Gaplar tushunarli, o'rtacha murakkablikda (A2-B1 leksikasi) bo'lsin. Murakkab arxaik so'zlar kiritilmasin.\n"
    "- Masalan: 'Please give me a glass of ______ because I am thirsty.' -> ['water', 'bread', 'table', 'paper']\n"
    "- Izoh o'zbek tilida so'zning kontekstdagi ma'nosini lo'nda tushuntirsin (maksimal 180 belgi).\n"
    "════════════════════════════════════════════════════════════════════\n\n"
)

VOCABULARY_ADVANCED_DIRECTIVE = (
    "\n"
    "════════════════════════════════════════════════════════════════════\n"
    "🔴 DARAJA: QIYIN / YUQORI (ADVANCED / CEFR B2-C1 / IELTS) LUG'AT TESTI:\n"
    "════════════════════════════════════════════════════════════════════\n"
    "- Lug'atdagi so'zlar boy akademik va professional kontekstda, turg'un kollokatsiyalar va nozik semantik farqlar orqali tekshirilsin.\n"
    "- Barcha savollar jonli kontekstli gap to'ldirish (contextual cloze) shaklida bo'lsin ('______').\n"
    "- Chalg'ituvchilar nozik semantik farqli yoki talabalar tez-tez adashadigan so'zlar bo'lsin.\n"
    "- Izoh o'zbek tilida ushbu so'z va kollokatsiyaning nozik qoidasini ko'rsatsin (maksimal 180 belgi).\n"
    "════════════════════════════════════════════════════════════════════\n\n"
)

# Qadimgi nomlar bilan moslik uchun
VOCABULARY_LIST_DIRECTIVE = VOCABULARY_INTERMEDIATE_DIRECTIVE


def get_vocabulary_directive(difficulty: str) -> str:
    """Lug'at (vocabulary) uchun tanlangan darajaga mos direktivani qaytarish."""
    if is_beginner_difficulty(difficulty):
        return VOCABULARY_BEGINNER_DIRECTIVE
    elif (difficulty or "").lower() in ("medium", "intermediate", "o'rta", "orta", "b1", "b2"):
        return VOCABULARY_INTERMEDIATE_DIRECTIVE
    else:
        return VOCABULARY_ADVANCED_DIRECTIVE


def get_difficulty_calibration_directive(
    difficulty: str,
    is_english: bool = True,
    is_vocab: bool = False,
) -> str:
    """Foydalanuvchi tanlagan qiyinlik darajasiga mos ravishda gap va so'z murakkabligini qat'iy cheklovchi direktiva."""
    diff = (difficulty or "medium").lower()
    if is_beginner_difficulty(diff):
        if is_vocab:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🟢 DARAJA: OSON / BOSHLANG'ICH (BEGINNER / ELEMENTARY / CEFR A1-A2)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🚨 LUG'AT UCHUN QAT'IY CHEKLOV (ODDIY SO'Z-TARJIMA VA MA'NO):\n"
                "- Siz 'OSON / BOSHLANG'ICH' (Beginner) darajasidagi lug'at uchun test tuzmoqdasiz!\n"
                "- Uzun, chigal yoki murakkab gaplar ASLO TUZILMASIN!\n"
                "- Savollar to'g'ridan-to'g'ri so'z-tarjima va ma'no shaklida bo'lsin (masalan: «suv» so'zining inglizcha tarjimasi nima? -> 'water', yoki «water» so'zining ma'nosi nima? -> 'suv').\n"
                "- Variantlar o'ta lo'nda — faqat 1 ta so'zdan iborat bo'lsin.\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )
        elif is_english:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🟢 DARAJA: OSON / BOSHLANG'ICH (BEGINNER / ELEMENTARY / CEFR A1-A2)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🚨 GAP TUZILISHI VA SO'ZLAR MURAKKABLIGI BO'YICHA QAT'IY CHEKLOV:\n"
                "- Siz tanlangan 'OSON / BOSHLANG'ICH' daraja uchun test tuzmoqdasiz!\n"
                "- Savol gapidagi barcha so'zlar va grammatika O'TA SODDA, KUNDALIK (A1-A2) bo'lishi SHART!\n"
                "- Boshlang'ich o'quvchi tushunmaydigan murakkab so'zlar (masalan: 'excruciating', 'deteriorate', 'subsequently', 'furthermore', 'molar', 'depletion', 'ubiquitous') ASLO ISHLATILMASIN!\n"
                "- Gaplar qisqa (6-12 so'z), sodda grammatika (Present Simple, Past Simple, can, must, am/is/are) va hamma biladigan so'zlardan (school, friend, car, food, time, go, see, help, home, weather) iborat bo'lsin.\n"
                "  ✅ To'g'ri misol: 'Yesterday, Tom went to the ______ because his tooth was hurting.' -> ['dentist', 'driver', 'cook', 'farmer']\n"
                "  ❌ Xato misol: 'After suffering from an excruciating toothache, Michael visited the ______ to extract the molar.' (Beginner o'quvchi bu gapni umuman tushunmaydi!)\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )
        else:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🟢 DARAJA: OSON / BOSHLANG'ICH (MAKTAB ASOSLARI / SODDA SAVOLLAR)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "- Savollar mavzuning eng asosiy, boshlang'ich va sodda qoidalarini tekshirsin.\n"
                "- Murakkab 3-4 bosqichli hisob-kitoblar yoki chigal parametrlar berilmasin. Savol tushunarli va 1-2 bosqichda yechiladigan bo'lsin.\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )
    elif diff == "medium":
        if is_english:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🟡 DARAJA: O'RTA (INTERMEDIATE / CEFR B1-B2 / DTM STANDART)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "- Gaplar standart o'rta darajadagi tabiiy ingliz tilida bo'lsin.\n"
                "- Keng tarqalgan bog'lovchilar (although, because, while, unless) va kundalik mavzular qatnashsin.\n"
                "- Haddan tashqari ibtidoiy bo'lib qolmasin, o'ta arxaik yoki ilmiy ham bo'lmasin.\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )
        else:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🟡 DARAJA: O'RTA (STANDART / DTM IMTIHON DARAJASI)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "- Standart maktab va litsey dasturi darajasidagi amaliy masalalar va tahliliy savollar.\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )
    elif diff == "hard":
        if is_english:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🔴 DARAJA: QIYIN / YUQORI (UPPER-INTERMEDIATE - ADVANCED / CEFR B2-C1 / IELTS 6.5-7.5)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "- Boy akademik kontekst, rasmiy yoki ilmiy uslubdagi gaplar.\n"
                "- Akademik lug'at (AWL), turg'un kollokatsiyalar va nozik semantik chalg'ituvchilar bo'lsin.\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )
        else:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🔴 DARAJA: QIYIN / CHUQUR (MURAKKAB MASALALAR VA PARAMETRLAR)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "- Bir nechta qoidani birlashtiruvchi, mantiqiy ilmoqli va chuqur bilim talab qiluvchi savollar.\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )
    else:  # olympiad
        if is_english:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🏆 DARAJA: OLIMPIADA / EKSPERT (CEFR C1-C2 / PROFICIENT / IELTS 8.0+)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "- Eng yuqori darajadagi nozik leksik farqlar, idiomatik birikmalar va murakkab sintaksis.\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )
        else:
            return (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🏆 DARAJA: OLIMPIADA / EKSPERT (MAKTAB VA RESPUBLIKA OLIMPIADASI)\n"
                "════════════════════════════════════════════════════════════════════\n"
                "- Eng yuqori qiyinchilikdagi, nostandart yondashuv va chuqur ilmiy tahlil talab qiluvchi savollar.\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )


class GeminiService:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or DEFAULT_MODEL
        if not self.api_key:
            logger.warning("GEMINI_API_KEY topilmadi! Oflayn rejim ishlaydi.")
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)

    async def generate_quiz(
        self,
        topic: str | None = None,
        text_content: str | None = None,
        file_bytes: bytes | None = None,
        file_mime: str | None = None,
        file_name: str | None = None,
        count: int = 5,
        options_count: int = 4,
        difficulty: str = "medium",
        used_questions: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Gemini AI orqali test savollarini generatsiya qilish.
        Mavzu, matn, fayl (audio, video, rasm, pdf/doc matni) qabul qiladi.
        """
        if not self.client:
            return []

        if options_count not in (2, 3, 4):
            options_count = 4

        diff_uz = {
            "easy": "Oson (boshlang'ich, asosiy faktlar va sodda tushunchalar)",
            "medium": "O'rta (standart daraja, tahlil va tushunishni talab qiladigan)",
            "hard": "Qiyin (murakkab, chuqur bilim va mantiqiy fikrlash talab qiluvchi)",
            "olympiad": "Olimpiada / Ekspert (eng yuqori darajadagi mantiqiy va chuqur savollar)",
        }.get(difficulty, "O'rta (standart daraja)")

        avoid_clause = ""
        if used_questions:
            sample_avoid = "\n".join(f"- {q}" for q in list(used_questions)[-50:])
            avoid_clause = (
                f"\n\n🚨 QAT'IY TALAB (SAVOLLAR TAKRORLANMASLIGI SHART):\n"
                f"Foydalanuvchi ushbu manbadan avval quyidagi test savollarini ishlagan.\n"
                f"Quyidagi savollar, ularning tushunchalari yoki aynan shu faktlarni QAYTA ISHLATISH QAT'IYAN TAQIQLANADI:\n"
                f"{sample_avoid}\n\n"
                f"Hujjatning boshqa darslari, keyingi sahifalari yoki matnning boshqa qismlaridan MUTLAQO YANGI, o'xshash bo'lmagan {count} ta savol tuzing!\n"
            )

        sample_opts = ["Variant A", "Variant B", "Variant C", "Variant D"][:options_count]
        sample_opts_json = json.dumps(sample_opts, ensure_ascii=False)

        is_listening = bool(topic and any(w in topic.lower() for w in ("listening", "tinglab", "eshitib", "audio test")))
        listening_clause = ""
        listening_sample_json = ""
        if is_listening:
            listening_clause = (
                "8. 🎧 LISTENING (TINGLAB TUSHUNISH) TALABI:\n"
                "- Har bir savolda 'audio_text' maydoni bo'lishi SHART!\n"
                "- 'audio_text' bu diktor tomonidan o'qib beriladigan tabiiy, ravon inglizcha matn yoki qisqa dialog (20-40 ta so'z).\n"
                "- 'question' esa tinglovchi shu audioni eshitib topishi kerak bo'lgan savol bo'lsin.\n"
            )
            listening_sample_json = '    "audio_text": "Spoken text or dialogue...",\n'

        is_grammar_formula = is_english_grammar_or_formula_content(
            topic=topic,
            text=text_content,
            filename=file_name,
        )
        is_english = is_english_content(
            topic=topic,
            text=text_content,
            filename=file_name,
        )
        is_vocab = is_vocabulary_content(
            topic=topic,
            text=text_content,
            filename=file_name,
        )
        if is_vocab:
            is_english = True

        is_beginner = is_beginner_difficulty(difficulty)

        level_calibration_clause = get_difficulty_calibration_directive(
            difficulty=difficulty,
            is_english=is_english,
            is_vocab=is_vocab,
        )

        english_directive_clause = ""
        vocabulary_clause = ""
        pedagogical_depth_clause = PEDAGOGICAL_DEPTH_DIRECTIVE
        master_teacher_clause = MASTER_TEACHER_METHODOLOGY_DIRECTIVE

        if is_vocab and is_beginner:
            pedagogical_depth_clause = ""
            master_teacher_clause = ""
            english_directive_clause = ""
            vocabulary_clause = VOCABULARY_BEGINNER_DIRECTIVE
        elif is_vocab:
            vocabulary_clause = get_vocabulary_directive(difficulty)
            english_directive_clause = ENGLISH_PEDAGOGICAL_MASTER_DIRECTIVE
        elif is_english and is_beginner:
            pedagogical_depth_clause = ""
            master_teacher_clause = ""
            english_directive_clause = ""
        elif is_english:
            english_directive_clause = ENGLISH_PEDAGOGICAL_MASTER_DIRECTIVE

        grammar_formula_clause = ""
        if is_grammar_formula:
            grammar_formula_clause = (
                "\n"
                "════════════════════════════════════════════════════════════════════\n"
                "🚨 QAT'IY VA MAJBURIY TALAB (INGLIZ TILI FORMULALARI ASOSIDA GAP TO'LDIRISH TESTLARI):\n"
                "════════════════════════════════════════════════════════════════════\n"
                "Manbada ingliz tili grammatika formulalari, zamonlar (tenses), fe'l qoidalari yoki tuzilmalar berilgan.\n"
                "Ushbu formulalar asosida savollar tuzishda QUYIDAGI TALABLARGA 100% AMAL QILISHINGIZ SHART:\n\n"
                "1. QURUQ NAZARIY SAVOLLAR MUTLAQO TAQIQLANADI:\n"
                "   - 'Present Continuous zamonining formulasi qanday?'\n"
                "   - 'Qaysi formula to'g'ri?'\n"
                "   - 'Ushbu gap qaysi zamonda?'\n"
                "   - 'Qaysi yordamchi fe'l ishlatiladi?'\n"
                "   KABI QURUQ NAZARIY VA YODLASH SAVOLLARI ASLO TUZILMASIN!\n\n"
                "2. BARCHA SAVOLLAR AMALIY GAP TUZISH VA TUSHIB QOLGAN SO'ZNI TOPISH (FILL-IN-THE-BLANKS) SHAKLIDA BO'LISHI SHART:\n"
                "   - Manbadagi formulaga mos ravishda to'g'ri, jonli va tabiiy inglizcha gap tuzing.\n"
                "   - Gap ichida formulada ko'rsatilgan tekshirilishi kerak bo'lgan asosiy grammatik qism (yordamchi fe'l: am/is/are, was/were, have/has, do/does; yoki fe'l shakli: V-ing, V1, V2, V3, Vs) o'rniga '______' (pastki chiziq) qoldiring.\n"
                "   - Masalan: 'He ______ watching TV right now.' yoki fe'l negizi bilan: 'He ______ (watch) TV right now.'\n\n"
                "3. EGALARNI (SUBJECTS) VA SHAXSLARNI XILMA-XIL QILING:\n"
                "   - Har bir savolda turli egalarni ishlating:\n"
                "     * 3-shaxs birlik: 'He', 'She', 'It', 'My father'\n"
                "     * 1-shaxs: 'I'\n"
                "     * Ko'plik va 2-shaxs: 'They', 'We', 'You', 'The children'\n"
                "   - Egaga qarab to'g'ri yordamchi fe'l yoki shakl tanlashni tekshiring:\n"
                "     * Present Continuous-da: He/She/It uchun 'is'; I uchun 'am'; They/We/You uchun 'are'.\n"
                "     * Present Simple-da: He/She/It uchun 'does/plays'; They/We/I uchun 'do/play'.\n"
                "     * Past Simple-da: o'tgan zamon shakli (did/visited/went).\n\n"
                "4. GAP TURLARI ARALASH BO'LSIN:\n"
                "   - Darak gap (+): 'He ______ (read) a book right now.' -> ['is reading', 'are reading', 'am reading', 'reads']\n"
                "   - Yordamchi fe'l: 'Look! The baby ______ sleeping.' -> ['is', 'are', 'am', 'be']\n"
                "   - Inkor gap (-): 'They ______ not playing football at the moment.' -> ['are', 'is', 'am', 'do']\n"
                "   - So'roq gap (?): '______ you doing your homework right now?' -> ['Are', 'Is', 'Am', 'Do']\n\n"
                "5. VARIANTLAR (OPTIONS):\n"
                "   - Variantlar aynan gapdagi '______' o'rniga tushadigan grammatik so'zlar bo'lsin.\n"
                "   - 1 ta to'g'ri javob va qolgan variantlar grammatik chalg'ituvchilar bo'lsin.\n\n"
                "6. IZOH (EXPLANATION) O'ZBEK TILIDA BO'LSIN:\n"
                "   - Qaysi formula qo'llangani va nima sababdan aynan shu variant to'g'riligini o'zbek tilida aniq ko'rsating.\n"
                "   - Masalan: 'Present Continuous formulasiga ko\\'ra (Subject + am/is/are + V-ing): \"He\" birlik olmoshi uchun \"is\" yordamchi fe\\'li ishlatiladi (He is watching).'\n"
                "════════════════════════════════════════════════════════════════════\n\n"
            )

        if is_vocab and is_beginner:
            prompt_intro = (
                f"Siz ingliz tili bo'yicha boshlang'ich (Beginner / A1 / Oson) daraja o'qituvchisisiz.\n"
                f"Taqdim etilgan lug'at ro'yxatidan boshlang'ich o'quvchilar uchun ROPPA-ROSA {count} TA "
                f"o'ta sodda, tushunarli so'z-tarjima va ma'no test savollarini tuzing.\n\n"
            )
            rule4_clause = (
                f"4. explanation (Izoh): O'zbek tilida, qisqa va o'rgatuvchi bo'lsin "
                f"(Masalan: '💡 water — suv degani. Boshqa variantlar: bread — non, milk — sut.').\n"
            )
            rule6_clause = (
                f"6. Savollar shakli: O'zbekcha so'zning inglizcha tarjimasi (masalan: «suv» so'zi ingliz tilida nima deyiladi? -> water) "
                f"yoki inglizcha so'zning o'zbekcha ma'nosi (masalan: «water» so'zining ma'nosi nima? -> suv). "
                f"Variantlar lo'nda va faqat 1 ta so'zdan iborat bo'lsin.\n"
            )
            sample_expl = "💡 water — suv degani."
        else:
            prompt_intro = (
                f"Siz 20 yillik tajribaga ega oliy toifali ustoz-metodist, akademik repetitor va pedagog-testologsiz.\n"
                f"Xuddi tajribali ustoz o'quvchilarining bilimini sinovdan o'tkazayotgandek, "
                f"quyida berilgan manba asosida ROPPA-ROSA {count} TA sifatli, mantiqan to'g'ri, ilmoqli va o'rgatuvchi test savollarini tuzing.\n\n"
            )
            rule4_clause = (
                f"4. explanation (Izoh): Xuddi tajribali ustoz o'quvchining xatosini mehr bilan tuzatayotgandek yozilsin! "
                f"Nega aynan shu javob to'g'riligi, qaysi nozik qoida ishlagani va o'quvchilar ko'p tushadigan tuzoq lo'nda (maksimal 180 belgi) tushuntirilsin "
                f"(Masalan: '💡 Ustoz maslahati: ...' yoki '💡 Eslab qoling: ...').\n"
            )
            rule6_clause = (
                f"6. Til qoidasi: Agar mavzu xorijiy til (ingliz tili, rus tili va h.k.) o'rganishga oid bo'lsa, test savollari va variantlari o'sha o'rganilayotgan tilda (yoki grammatika/lug'at topshirig'i shaklida), izohi (explanation) esa o'zbek tilida tushuntirilsin. Boshqa fanlar uchun savollar to'liq o'zbek tilida bo'lsin.\n"
            )
            sample_expl = "💡 Ustoz maslahati: ..."

        prompt = (
            f"{prompt_intro}"
            f"DIQQAT (SAVOLLAR SONI BO'YICHA QAT'IY TALAB):\n"
            f"Siz ROPPA-ROSA {count} TA savol tuzishingiz SHART! Kam ham bo'lmasin, ko'p ham bo'lmasin, aynan {count} ta bo'lsin.\n"
            f"JSON massivida aynan {count} ta savol obyekti bo'lishi shart (len(array) == {count}).\n\n"
            f"PARAMETRLAR:\n"
            f"- Qiyinlik darajasi: {diff_uz}\n"
            f"- Har bir savoldagi variantlar soni: {options_count} ta\n\n"
            f"QAT'IY TALABLAR (TELEGRAM QUIZ STANDARTI):\n"
            f"1. Savol matni: Aniq, lo'nda va tushunarli bo'lsin (maksimal 280 belgi).\n"
            f"2. Variantlar: Aynan {options_count} ta variant bo'lsin. Har bir variant maksimal 95 belgi.\n"
            f"3. To'g'ri javob: Faqat bitta variant to'g'ri bo'lsin va 'correct_id' 0 dan {options_count - 1} gacha bo'lgan to'g'ri indeksni ko'rsatsin.\n"
            f"{rule4_clause}"
            f"5. BUTUN HUJJATNI QAMRAB OLING: Savollarni faqat hujjat boshidan emas, butun matn bo'ylab (boshi, o'rtasi, oxiri, turli darslar) aralash holda tanlang.\n"
            f"{rule6_clause}"
            f"{master_teacher_clause}"
            f"{pedagogical_depth_clause}"
            f"{level_calibration_clause}"
            f"{english_directive_clause}"
            f"{vocabulary_clause}"
            f"{grammar_formula_clause}"
            f"{listening_clause}"
            f"7. Javobingiz FAQAT aynan {count} ta elementdan iborat JSON array formatida bo'lsin:\n"
            "[\n"
            "  {\n"
            f"{listening_sample_json}"
            '    "question": "Savol matni?",\n'
            f'    "options": {sample_opts_json},\n'
            '    "correct_id": 0,\n'
            f'    "explanation": "{sample_expl}"\n'
            "  }\n"
            "]"
            f"{avoid_clause}\n\n"
        )

        uploaded_file = None
        temp_file_path = None
        contents: list[Any] = []

        try:
            # Agar multimodal fayl (audio, video, rasm) bo'lsa
            is_media = file_mime and (
                file_mime.startswith("audio/")
                or file_mime.startswith("video/")
                or file_mime.startswith("image/")
                or file_mime == "application/pdf"
            )

            # Agar matn mavjud bo'lsa (masalan PDF/Word dan ajratib olingan matn), bevosita matndan foydalanish (tezkor va ishonchli)
            if text_content and len(text_content.strip()) > 50:
                prompt += f"MANBA MATNI:\n\"\"\"\n{text_content[:200000]}\n\"\"\"\n"
                if topic:
                    prompt += f"\nANIQ MAVZU / QOIDALAR YO'NALISHI: «{topic}»\n"
            elif file_bytes and is_media:
                suffix = os.path.splitext(file_name)[1] if file_name else ".tmp"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                    tf.write(file_bytes)
                    temp_file_path = tf.name

                logger.info("Fayl Gemini File API ga yuklanmoqda: %s (%s)", file_name, file_mime)
                uploaded_file = await self.client.aio.files.upload(
                    file=temp_file_path,
                    config=types.UploadFileConfig(mime_type=file_mime) if file_mime else None,
                )

                # Agar video yoki audio bo'lsa, ACTIVE holatga o'tishini kutish
                if file_mime.startswith("video/") or file_mime.startswith("audio/"):
                    for _ in range(40):
                        if uploaded_file.state.name == "ACTIVE":
                            break
                        await asyncio.sleep(1)
                        uploaded_file = await self.client.aio.files.get(name=uploaded_file.name)

                contents.append(uploaded_file)
                prompt += f"MANBA: Yuqorida yuklangan media fayl ('{file_name or 'fayl'}') ning to'liq mazmunidan foydalaning."
                if topic:
                    prompt += f"\nANIQ MAVZU / QOIDALAR YO'NALISHI: «{topic}»\n"
            else:
                prompt += (
                    f"MANBA MAVZUSI (ANIQ MAVZU): «{topic or 'Umumiy bilimlar'}»\n\n"
                    f"QAT'IY TALAB:\n"
                    f"- Barcha {count} ta test savollari FAQAT va FAQAT ko'rsatilgan «{topic}» mavzusiga oid bo'lishi SHART!\n"
                    f"- Savollar aynan shu mavzuning asosiy qoidalari, formulalari, ta'riflari, faktlari va mantiqiy jihatlarini to'liq qamrab olsin.\n"
                    f"- Mavzudan mutlaqo chetga chiqmang, umumiy yoki boshqa begona mavzulardan savol qo'shmang."
                )

            contents.append(prompt)

            models_to_try = [
                self.model,
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-flash-latest",
                "gemini-flash-lite-latest",
                "gemini-3.8-flash",
            ]
            seen = set()
            unique_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

            if is_vocab and is_beginner:
                sys_instruction = (
                    "Siz tajribali ingliz tili o'qituvchisisiz. "
                    "Boshlang'ich (Beginner / A1 / Oson) darajadagi o'quvchilar uchun taqdim etilgan lug'at ro'yxatidan "
                    "o'ta sodda, ravon va tushunarli so'z-tarjima testlarini (masalan: '«water» so\\'zining ma\\'nosi nima?' -> 'suv' yoki '«suv» so\\'zining inglizcha tarjimasi qaysi?' -> 'water') JSON array formatida tuzib bering. "
                    "Uzun murakkab gaplar yoki qiyin grammatikadan mutlaqo saqlaning. Savollar sodda, variantlar lo'nda bitta so'zdan iborat bo'lsin. "
                    f"Sizdan so'ralgan roppa-rosa {count} ta savolni to'liq shakllantiring. "
                    f"JSON arrayida aynan {count} ta obyekt bo'lsin."
                )
            else:
                sys_instruction = (
                    "Siz 20 yillik tajribaga ega oliy toifali ustoz-metodist, akademik repetitor va pedagog-testologsiz. "
                    "Siz test tuzishda xuddi tajribali ustozlarday o'ylaysiz: o'quvchilar eng ko'p qayerda adashishini, qaysi ilmoq va nozik qoidalarda "
                    "qoqilishini oldindan bilgan holda, chuqur fikrlashga, sabab-oqibatni tahlil qilishga va qoidalarni amalda qo'llashga undaydigan "
                    "Cambridge / CEFR va xalqaro olimpiada standartidagi professional test savollarini tuzasiz. "
                    "Sayoz yodlash, 1 soniyalik quruq faktlar, robotik iboralar ('Matnga ko'ra...') va quruq tarjimalardan saqlaning. "
                    f"Sizdan so'ralgan roppa-rosa {count} ta savolni to'liq shakllantiring. "
                    f"JSON arrayida aynan {count} ta obyekt bo'lsin."
                )

            for model_name in unique_models:
                try:
                    config = types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        response_mime_type="application/json",
                        temperature=0.35,
                        max_output_tokens=max(4096, count * 450),
                    )
                    res = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    raw_text = res.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    if raw_text.startswith("```"):
                        raw_text = raw_text[3:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]

                    parsed = try_repair_and_parse_json(raw_text)
                    if parsed is None:
                        continue
                    if isinstance(parsed, dict):
                        for k in ("questions", "quiz", "items", "data"):
                            if k in parsed and isinstance(parsed[k], list):
                                parsed = parsed[k]
                                break
                        else:
                            parsed = [parsed]

                    import re
                    from difflib import SequenceMatcher

                    valid_questions = []
                    seen_clean: set[str] = set()

                    for idx, item in enumerate(parsed):
                        if not isinstance(item, dict):
                            continue
                        raw_q = str(item.get("question", "")).strip()
                        q_text = sanitize_question_text(raw_q)
                        raw_opts = item.get("options", [])
                        if not isinstance(raw_opts, list):
                            continue
                        opts = []
                        seen_o = set()
                        for o in raw_opts:
                            o_str = str(o).strip()[:98]
                            if o_str and o_str.lower() not in seen_o:
                                seen_o.add(o_str.lower())
                                opts.append(o_str)
                        c_id = item.get("correct_id", 0)
                        expl = str(item.get("explanation", "")).strip()

                        if not q_text or len(opts) < 2:
                            continue

                        clean_check = re.sub(r"^\[\d+/\d+\]\s*", "", q_text).strip().lower()

                        # Takrorlanishni aniq va xolis tekshirish
                        is_dup = False
                        if clean_check in seen_clean:
                            is_dup = True
                        else:
                            for prev in seen_clean:
                                if clean_check == prev or (len(clean_check) > 25 and len(prev) > 25 and SequenceMatcher(None, clean_check, prev).ratio() > 0.90):
                                    is_dup = True
                                    break

                        if not is_dup and used_questions:
                            if clean_check in used_questions:
                                is_dup = True
                            else:
                                for uq in used_questions:
                                    if clean_check == uq or (len(clean_check) > 25 and len(uq) > 25 and SequenceMatcher(None, clean_check, uq).ratio() > 0.90):
                                        is_dup = True
                                        logger.info("Avvalgi ishlatilgan savol bilan o'xshashlik topildi: %s", q_text)
                                        break

                        if is_dup:
                            continue

                        seen_clean.add(clean_check)

                        # Variantlarni moslashtirish
                        target_opts = opts[:options_count]
                        if not isinstance(c_id, int) or not (0 <= c_id < len(target_opts)):
                            c_id = 0

                        # Variantlarni tasodifiy aralashtirish
                        indexed = list(enumerate(target_opts))
                        random.shuffle(indexed)
                        shuffled_opts = [t for _, t in indexed]
                        new_c_id = next(n_i for n_i, (o_i, _) in enumerate(indexed) if o_i == c_id)

                        valid_questions.append({
                            "question": q_text[:295],
                            "options": shuffled_opts,
                            "correct_id": new_c_id,
                            "explanation": expl[:195],
                        })

                    if len(valid_questions) >= count:
                        return valid_questions[:count]
                    elif valid_questions:
                        # Agar AI barcha savollarni to'liq bermagan bo'lsa (masalan 15 ta o'rniga 8 ta),
                        # yetishmayotgan qismini zaxira bankidan to'ldirib aynan 'count' ta qilib qaytaramiz
                        from services.quiz_service import get_offline_quiz_questions
                        missing = count - len(valid_questions)
                        logger.info("Gemini %d ta savol berdi, kerak: %d ta. Qolgan %d ta savol to'ldirilmoqda...", len(valid_questions), count, missing)
                        extra_questions = get_offline_quiz_questions(
                            topic=topic or "Umumiy",
                            count=missing,
                            options_count=options_count,
                            used_questions=(used_questions or set()) | seen_clean,
                        )
                        valid_questions.extend(extra_questions[:missing])
                        return valid_questions[:count]

                except Exception as err:
                    logger.warning("Gemini model %s da test tuzishda xatolik: %s", model_name, err)
                    await asyncio.sleep(0.5)

        finally:
            if uploaded_file:
                try:
                    await self.client.aio.files.delete(name=uploaded_file.name)
                except Exception:
                    pass
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass

        return []

    async def extract_topics_from_text(self, text_content: str) -> list[str]:
        """Hujjatdagi barcha darslar, unitlar yoki mustaqil mavzular ro'yxatini aniqlash."""
        if not text_content:
            return []

        # 1. Regex orqali aniq sarlavhalarni topish (tez va bexato)
        try:
            from services.quiz_service import extract_lesson_sections
            regex_sections = extract_lesson_sections(text_content)
            if len(regex_sections) >= 2:
                logger.info("Mavzular regex orqali aniqlandi: %d ta mavzu.", len(regex_sections))
                return [s["title"] for s in regex_sections][:40]
        except Exception as re_err:
            logger.debug("Regex mavzular ajratishda ogohlantirish: %s", re_err)

        if not self.client:
            return []

        prompt = (
            "Quyidagi hujjat (darslik, konspekt, qo'llanma yoki lug'at)dagi BARCHA darslar, unitlar, boblar yoki alohida mustaqil mavzular ro'yxatini aniqlang.\n"
            "QAT'IY TALAB: Javobingiz FAQAT JSON ro'yxati (stringlar massivi) bo'lsin. Har bir element dars yoki mavzuning aniq nomi bo'lsin.\n"
            "Format namunasi:\n"
            "[\n"
            "  \"1-dars: Mavzu nomi\",\n"
            "  \"2-dars: Mavzu nomi\"\n"
            "]\n\n"
            f"HUJJAT MATNI:\n\"\"\"\n{text_content[:60000]}\n\"\"\""
        )
        models_to_try = [
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            self.model,
            "gemini-3.5-flash",
        ]
        seen = set()
        unique_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        for model_name in unique_models:
            try:
                config = types.GenerateContentConfig(
                    system_instruction="Hujjatdan barcha dars/mavzular nomlari ro'yxatini JSON massivi sifatida aniq ajratib bering.",
                    response_mime_type="application/json",
                    temperature=0.3,
                    max_output_tokens=4096,
                )
                res = await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                parsed = try_repair_and_parse_json(res.text)
                if isinstance(parsed, dict):
                    for k in ("topics", "lessons", "units", "items", "data", "chapters"):
                        if k in parsed and isinstance(parsed[k], list):
                            parsed = parsed[k]
                            break
                    else:
                        parsed = list(parsed.values())

                if isinstance(parsed, list):
                    clean_topics = []
                    for item in parsed:
                        if isinstance(item, str) and item.strip():
                            clean_topics.append(item.strip())
                        elif isinstance(item, dict):
                            t_name = item.get("topic_title") or item.get("title") or item.get("topic") or item.get("name")
                            if t_name and str(t_name).strip():
                                clean_topics.append(str(t_name).strip())
                    if clean_topics:
                        return clean_topics[:35]
            except Exception as e:
                logger.warning("Mavzularni ajratishda model %s da xatolik: %s", model_name, e)
                await asyncio.sleep(0.3)

        return []

    async def generate_batch_topic_quizzes(
        self,
        text_content: str,
        questions_per_topic: int = 5,
        options_count: int = 4,
        difficulty: str = "medium",
    ) -> list[dict[str, Any]]:
        """
        Hujjatdagi har bir alohida dars/mavzu/unit uchun alohida testlar to'plamini tuzish.
        Qaytaradi: [
            {
                "topic_title": "Lesson 1: Greetings",
                "questions": [ ... ]
            }, ...
        ]
        """
        if not self.client or not text_content:
            return []

        if options_count not in (2, 3, 4):
            options_count = 4

        diff_uz = {
            "easy": "Oson (boshlang'ich)",
            "medium": "O'rta (standart daraja)",
            "hard": "Qiyin (chuqur bilim talab qiluvchi)",
            "olympiad": "Olimpiada (ekspert daraja)",
        }.get(difficulty, "O'rta (standart daraja)")

        is_grammar_formula = is_english_grammar_or_formula_content(text=text_content)
        is_english = is_english_content(text=text_content)
        is_vocab = is_vocabulary_content(text=text_content)
        if is_vocab:
            is_english = True

        level_batch_clause = get_difficulty_calibration_directive(
            difficulty=difficulty,
            is_english=is_english,
            is_vocab=is_vocab,
        )

        english_batch_clause = ""
        vocabulary_batch_clause = ""
        pedagogical_batch_clause = PEDAGOGICAL_DEPTH_DIRECTIVE
        master_teacher_batch_clause = MASTER_TEACHER_METHODOLOGY_DIRECTIVE

        is_beginner = is_beginner_difficulty(difficulty)

        if is_vocab and is_beginner:
            pedagogical_batch_clause = ""
            master_teacher_batch_clause = ""
            english_batch_clause = ""
            vocabulary_batch_clause = VOCABULARY_BEGINNER_DIRECTIVE
        elif is_vocab:
            vocabulary_batch_clause = get_vocabulary_directive(difficulty)
            english_batch_clause = ENGLISH_PEDAGOGICAL_MASTER_DIRECTIVE
        elif is_english and is_beginner:
            pedagogical_batch_clause = ""
            master_teacher_batch_clause = ""
            english_batch_clause = ""
        elif is_english:
            english_batch_clause = ENGLISH_PEDAGOGICAL_MASTER_DIRECTIVE

        grammar_batch_clause = ""
        if is_grammar_formula:
            grammar_batch_clause = (
                "\n🚨 QAT'IY VA MAJBURIY TALAB (INGLIZ TILI FORMULALARI ASOSIDA GAP TO'LDIRISH TESTLARI):\n"
                "- Har bir dars/mavzu/zamon bo'yicha quruq nazariy savollar (masalan 'Present continuous formulasi qanaqa?') MUTLAQO TUZILMASIN!\n"
                "- Barcha savollar amaliy gap tuzish va bo'sh o'rinni to'ldirish (fill-in-the-blank) shaklida bo'lsin.\n"
                "- Gapda formulaga mos tekshiriladigan so'z (am/is/are, was/were, have/has, do/does, V-ing va h.k.) o'rniga '______' pastki chiziq qo'yilsin (Masalan: 'He ______ watching TV right now.').\n"
                "- Turli egalar ('He', 'She', 'It', 'I', 'They', 'We') va turli gap shakllari (+, -, ?) aralash qatnashsin.\n"
                "- Variantlar o'sha bo'sh joyga qo'yiladigan shakllar bo'lsin (masalan: ['is', 'are', 'am', 'be']).\n"
                "- 'explanation' o'zbek tilida qoidani ko'rsatib tushuntirilsin.\n\n"
            )

        def sanitize_parsed_topics(parsed: Any) -> list[dict[str, Any]]:
            if isinstance(parsed, dict):
                for k in ("topics", "lessons", "units", "quizzes", "items", "data", "chapters"):
                    if k in parsed and isinstance(parsed[k], list):
                        parsed = parsed[k]
                        break
                else:
                    parsed = [parsed]
            if not isinstance(parsed, list):
                return []

            result_topics = []
            for t_item in parsed:
                if not isinstance(t_item, dict):
                    continue
                t_title = str(t_item.get("topic_title") or t_item.get("title") or t_item.get("topic") or "Dars").strip()
                raw_questions = t_item.get("questions", [])
                if not isinstance(raw_questions, list) or not raw_questions:
                    continue

                valid_q = []
                for q in raw_questions:
                    if not isinstance(q, dict):
                        continue
                    raw_q = str(q.get("question", "")).strip()
                    q_text = sanitize_question_text(raw_q)
                    raw_opts = q.get("options", [])
                    if not isinstance(raw_opts, list):
                        continue
                    opts = []
                    seen_o = set()
                    for o in raw_opts:
                        o_str = str(o).strip()[:98]
                        if o_str and o_str.lower() not in seen_o:
                            seen_o.add(o_str.lower())
                            opts.append(o_str)
                    c_id = q.get("correct_id", 0)
                    expl = str(q.get("explanation", "")).strip()

                    if not q_text or len(opts) < 2:
                        continue

                    target_opts = opts[:options_count]
                    if not isinstance(c_id, int) or not (0 <= c_id < len(target_opts)):
                        c_id = 0

                    indexed = list(enumerate(target_opts))
                    random.shuffle(indexed)
                    shuffled_opts = [t for _, t in indexed]
                    new_c_id = next(n_i for n_i, (o_i, _) in enumerate(indexed) if o_i == c_id)

                    valid_q.append({
                        "question": q_text[:295],
                        "options": shuffled_opts,
                        "correct_id": new_c_id,
                        "explanation": expl[:195],
                    })

                if valid_q:
                    result_topics.append({
                        "topic_title": t_title[:50],
                        "questions": valid_q,
                    })
            return result_topics

        # 0-BOSQICH (Eng tez va 100% ishonchli): Hujjatdan dars bo'limlarini regex orqali ajratib olish
        try:
            from services.quiz_service import extract_lesson_sections, parse_vocabulary_pairs, generate_vocabulary_quiz_from_pairs
            sections = extract_lesson_sections(text_content)
            if len(sections) >= 2:
                logger.info("Aniq sarlavhalar orqali %d ta dars/mavzu bo'limi aniqlandi.", len(sections))
                direct_topics = []
                for sec in sections:
                    sec_title = sec["title"]
                    sec_content = sec["content"]
                    sec_pairs = parse_vocabulary_pairs(sec_content)
                    if (is_vocab or is_beginner or len(sec_pairs) >= 3) and len(sec_pairs) >= 2:
                        q_list = generate_vocabulary_quiz_from_pairs(
                            sec_pairs,
                            count=questions_per_topic,
                            options_count=options_count,
                        )
                        if q_list:
                            direct_topics.append({
                                "topic_title": sec_title,
                                "questions": q_list,
                            })
                if len(direct_topics) >= 2:
                    logger.info("Lug'at juftliklaridan %d ta dars uchun testlar to'liq va tez tuzildi!", len(direct_topics))
                    return direct_topics
        except Exception as fast_err:
            logger.warning("Tezkor dars bo'limlarini tahlil qilishda ogohlantirish: %s", fast_err)

        models_to_try = [
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            self.model,
            "gemini-3.5-flash",
        ]
        seen = set()
        unique_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        # 1-BOSQICH: Hujjatdagi mavzularni avval aniqlash
        discovered_topics = await self.extract_topics_from_text(text_content)
        logger.info("Batch test uchun %d ta mavzu aniqlandi.", len(discovered_topics))

        # Agar kamida 2 ta mavzu aniqlangan bo'lsa, ularni bo'laklab parallel generatsiya qilamiz
        if len(discovered_topics) >= 2:
            chunk_size = 3 if questions_per_topic >= 10 else 4
            chunks = [discovered_topics[i:i + chunk_size] for i in range(0, len(discovered_topics), chunk_size)]
            logger.info("Mavzular %d ta bo'lakka bo'lindi (har birida ~%d ta mavzu).", len(chunks), chunk_size)

            sem = asyncio.Semaphore(2)

            async def process_chunk(chunk_topics: list[str]) -> list[dict[str, Any]]:
                chunk_prompt = (
                    "Siz 20 yillik tajribaga ega oliy toifali ustoz-metodist va akademik repetitorsiz.\n"
                    "Xuddi tajribali ustoz darsda o'quvchilarining bilimini sinayotgandek, "
                    f"quyida ko'rsatilgan darslar/mavzularning HAR BIRI uchun alohida roppa-rosa {questions_per_topic} tadan sifatli, ilmoqli va o'rgatuvchi test savollarini tuzing.\n\n"
                    f"KO'RSATILGAN MAVZULAR RO'YXATI:\n{json.dumps(chunk_topics, ensure_ascii=False, indent=2)}\n\n"
                    f"PARAMETRLAR:\n"
                    f"- Har bir mavzudagi savollar soni: {questions_per_topic} ta\n"
                    f"- Variantlar soni: {options_count} ta\n"
                    f"- Qiyinlik darajasi: {diff_uz}\n\n"
                    "TALABLAR:\n"
                    "1. Ro'yxatdagi har bir mavzuni o'z ichiga olgan alohida obyekt tuzing.\n"
                    "2. 'topic_title' aynan o'sha mavzu nomi bo'lsin.\n"
                    f"{master_teacher_batch_clause}"
                    f"{pedagogical_batch_clause}"
                    f"{level_batch_clause}"
                    f"{english_batch_clause}"
                    f"{vocabulary_batch_clause}"
                    f"{grammar_batch_clause}"
                    "3. Javobingiz FAQAT JSON ro'yxati formatida bo'lsin:\n"
                    "[\n"
                    "  {\n"
                    '    "topic_title": "Mavzu nomi",\n'
                    '    "questions": [\n'
                    "      {\n"
                    '        "question": "Savol matni?",\n'
                    '        "options": ["Variant 1", "Variant 2", "Variant 3", "Variant 4"],\n'
                    '        "correct_id": 0,\n'
                    '        "explanation": "💡 Ustoz maslahati: ..."\n'
                    "      }\n"
                    "    ]\n"
                    "  }\n"
                    "]\n\n"
                    f"MANBA HUJJAT MATNI:\n\"\"\"\n{text_content[:60000]}\n\"\"\""
                )

                if is_vocab and is_beginner:
                    batch_sys_instruction = (
                        "Siz tajribali ingliz tili o'qituvchisisiz. Boshlang'ich (Beginner / Oson) darajadagi o'quvchilar uchun "
                        "taqdim etilgan lug'at ro'yxatidagi har bir dars/mavzu bo'yicha sodda so'z-tarjima va ma'no testlarini (masalan: '«water» so\\'zining ma\\'nosi nima?' -> 'suv') JSON ro'yxatida tuzib bering. "
                        "Uzun murakkab gaplar yoki qiyin grammatikadan mutlaqo saqlaning. Savollar sodda, variantlar lo'nda bitta so'zdan iborat bo'lsin."
                    )
                else:
                    batch_sys_instruction = (
                        "Siz 20 yillik tajribaga ega oliy toifali ustoz-metodist va pedagog-repetitorsiz. "
                        "Xuddi tajribali ustozlarday o'ylab, o'quvchini chuqur fikrlashga, sabab-oqibatni tahlil qilishga va qoidalarni amalda qo'llashga undaydigan "
                        "professional va xalqaro standartdagi test savollarini JSON ro'yxatida tuzib bering. "
                        "Sayoz, 1 soniyalik yodlash savollari, robotik iboralar ('Matnga ko'ra...') va quruq tarjimalardan saqlaning."
                    )

                async with sem:
                    for m_name in unique_models:
                        try:
                            cfg = types.GenerateContentConfig(
                                system_instruction=batch_sys_instruction,
                                response_mime_type="application/json",
                                temperature=0.35,
                                max_output_tokens=8192,
                            )
                            r = await self.client.aio.models.generate_content(
                                model=m_name,
                                contents=chunk_prompt,
                                config=cfg,
                            )
                            p = try_repair_and_parse_json(r.text)
                            res = sanitize_parsed_topics(p)
                            if res:
                                return res
                        except Exception as c_err:
                            logger.warning("Chunk %s uchun model %s xatosi: %s", chunk_topics, m_name, c_err)
                            await asyncio.sleep(0.3)
                return []

            chunk_results = await asyncio.gather(*(process_chunk(c) for c in chunks), return_exceptions=True)
            combined_topics = []
            for cr in chunk_results:
                if isinstance(cr, list):
                    combined_topics.extend(cr)
                elif isinstance(cr, Exception):
                    logger.warning("Chunk bajarilishida xatolik: %s", cr)

            if combined_topics:
                logger.info("Jami %d ta mavzu bo'yicha testlar muvaffaqiyatli tuzildi!", len(combined_topics))
                return combined_topics

        # 2-BOSQICH (Zaxira): Agar bo'laklash imkoni bo'lmasa, to'g'ridan-to'g'ri bitta so'rov bilan tuzish
        single_prompt = (
            "Siz 20 yillik tajribaga ega oliy toifali ustoz-metodist va akademik repetitorsiz.\n"
            "Xuddi tajribali ustozlarday o'ylab, hujjatdagi HAR BIR dars/mavzu/unit uchun alohida "
            f"roppa-rosa {questions_per_topic} tadan sifatli, ilmoqli va o'rgatuvchi test savollarini tuzing.\n\n"
            f"PARAMETRLAR:\n"
            f"- Har bir mavzudagi savollar soni: {questions_per_topic} ta\n"
            f"- Variantlar soni: {options_count} ta\n"
            f"- Qiyinlik darajasi: {diff_uz}\n\n"
            "QAT'IY TALABLAR:\n"
            "1. Hujjatdagi barcha dars/mavzularni to'liq qamrab oling.\n"
            "2. 'topic_title' maydonida mavzuning aniq nomi bo'lsin.\n"
            "3. Savollar va variantlar o'sha mavzuning lug'ati va faktlariga mos bo'lsin.\n"
            "4. Har bir savolda 'question', 'options', 'correct_id' (0 dan boshlanadi), va 'explanation' bo'lsin.\n"
            f"{master_teacher_batch_clause}"
            f"{pedagogical_batch_clause}"
            f"{level_batch_clause}"
            f"{english_batch_clause}"
            f"{vocabulary_batch_clause}"
            f"{grammar_batch_clause}"
            "5. Javobingiz FAQAT quyidagi JSON ro'yxati formatida bo'lsin:\n"
            "[\n"
            "  {\n"
            '    "topic_title": "Dars yoki Mavzu nomi",\n'
            '    "questions": [\n'
            "      {\n"
            '        "question": "Savol matni?",\n'
            '        "options": ["Variant 1", "Variant 2", "Variant 3", "Variant 4"],\n'
            '        "correct_id": 0,\n'
            '        "explanation": "💡 Ustoz maslahati: ..."\n'
            "      }\n"
            "    ]\n"
            "  }\n"
            "]\n\n"
            f"HUJJAT MATNI:\n\"\"\"\n{text_content[:100000]}\n\"\"\""
        )

        if is_vocab and is_beginner:
            single_sys_instruction = (
                "Siz tajribali ingliz tili o'qituvchisisiz. Boshlang'ich (Beginner / Oson) darajadagi o'quvchilar uchun "
                "taqdim etilgan lug'at ro'yxatidagi barcha dars/mavzular bo'yicha sodda so'z-tarjima va ma'no testlarini (masalan: '«water» so\\'zining ma\\'nosi nima?' -> 'suv') JSON ro'yxatida to'liq tuzib bering. "
                "Uzun murakkab gaplar yoki qiyin grammatikadan mutlaqo saqlaning. Savollar sodda, variantlar lo'nda bitta so'zdan iborat bo'lsin."
            )
        else:
            single_sys_instruction = (
                "Siz 20 yillik tajribaga ega oliy toifali ustoz-metodist va akademik repetitorsiz. "
                "Hujjatdagi barcha dars/mavzularni aniqlab, xuddi tajribali ustozlarday o'ylab, o'quvchini chuqur fikrlashga, tahlilga va qoidalarni amalda qo'llashga undaydigan "
                "professional testlar to'plamini JSON ro'yxatida to'liq tuzib bering. "
                "Sayoz savollar, robotik iboralar ('Matnga ko'ra...') va quruq tarjimalardan saqlaning."
            )

        for model_name in unique_models:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=single_sys_instruction,
                    response_mime_type="application/json",
                    temperature=0.35,
                    max_output_tokens=16384,
                )
                res = await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=single_prompt,
                    config=config,
                )
                parsed = try_repair_and_parse_json(res.text)
                res_topics = sanitize_parsed_topics(parsed)
                if res_topics:
                    return res_topics
            except Exception as e:
                logger.warning("To'g'ridan-to'g'ri batch test tuzishda model %s da xatolik: %s", model_name, e)
                await asyncio.sleep(0.5)

        return []
