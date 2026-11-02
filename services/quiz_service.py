import io
import logging
import os
import random
import time
from typing import Any

logger = logging.getLogger(__name__)

# Mahalliy zaxira savollar banki (Offline fallback)
LOCAL_QUIZ_BANK = {
    "matematika": [
        {
            "question": "A kvadrat matritsaning determinanti det(A) = 0 bo'lsa, bu matritsa qanday matritsa deyiladi?",
            "options": ["Xosmas", "Maxsus (singular)", "Simmetrik", "Birlik (ortogonal)"],
            "correct_id": 1,
            "explanation": "Determinanti nol bo'lgan matritsalar maxsus (singular) matritsalar deb ataladi.",
        },
        {
            "question": "f(x) = x³ funksiyaning x = 2 nuqtadagi hosilasi (f'(2)) nimaga teng?",
            "options": ["6", "8", "12", "16"],
            "correct_id": 2,
            "explanation": "f'(x) = 3x² bo'ladi. x = 2 da: 3 * (2²) = 3 * 4 = 12.",
        },
        {
            "question": "Ikki perpendikulyar vektorning skalyar ko'paytmasi nechiga teng?",
            "options": ["1", "0", "-1", "Cheksiz"],
            "correct_id": 1,
            "explanation": "cos(90°) = 0 bo'lgani sababli, perpendikulyar vektorlarning skalyar ko'paytmasi 0 bo'ladi.",
        },
        {
            "question": "Pifagor teoremasiga ko'ra to'g'ri burchakli uchburchak gipotenuzasining kvadrati nimaga teng?",
            "options": ["Katetlar ayirmasiga", "Katetlar kvadratlari yig'indisiga", "Katetlar ko'paytmasiga", "Perimetrga"],
            "correct_id": 1,
            "explanation": "Pifagor teoremasi: a² + b² = c² (katetlar kvadratlari yig'indisi gipotenuza kvadratiga teng).",
        },
        {
            "question": "Logarifm asosida log₂(16) qiymati nechiga teng?",
            "options": ["2", "4", "8", "16"],
            "correct_id": 1,
            "explanation": "2 ning 4-darajasi 16 ga teng (2⁴ = 16), shuning uchun log₂(16) = 4.",
        },
    ],
    "dasturlash": [
        {
            "question": "Python tilida qaysi ma'lumot turi o'zgarmas (immutable) hisoblanadi?",
            "options": ["list (ro'yxat)", "dict (lug'at)", "tuple (kortej)", "set (to'plam)"],
            "correct_id": 2,
            "explanation": "Tuple elementlari yaratilgach o'zgartirib bo'lmaydi, shuning uchun u immutable.",
        },
        {
            "question": "SQL tilida faqat takrorlanmagan noyob qatorlarni tanlash uchun qaysi kalit so'z ishlatiladi?",
            "options": ["UNIQUE", "DISTINCT", "DIFFERENT", "PRIMARY"],
            "correct_id": 1,
            "explanation": "SELECT DISTINCT so'rovi faqat takrorlanmaydigan noyob qatorlarni tanlaydi.",
        },
        {
            "question": "Git versiya nazorati tizimida yangi branch (tarmoq) yaratish va unga o'tish qaysi buyruq orqali qilinadi?",
            "options": ["git branch", "git checkout -b <name>", "git merge", "git push"],
            "correct_id": 1,
            "explanation": "git checkout -b yangi branch ochadi va darhol unga o'tadi.",
        },
        {
            "question": "Veb dasturlashda HTTP 404 status kodi nimani bildiradi?",
            "options": ["Server xatosi", "Sahifa topilmadi", "Ruxsat berilmagan", "Muvaffaqiyatli"],
            "correct_id": 1,
            "explanation": "404 Not Found — so'ralgan manba serverda topilmaganligini anglatadi.",
        },
        {
            "question": "Algoritmlarning vaqt bo'yicha murakkabligida eng tezkor bajarilish qaysi?",
            "options": ["O(N²)", "O(N log N)", "O(1)", "O(N)"],
            "correct_id": 2,
            "explanation": "O(1) — o'zgarmas (konstant) vaqt, kiruvchi ma'lumot hajmiga bog'liq bo'lmagan eng tezkor murakkablik.",
        },
    ],
    "ingliz_tili": [
        {
            "question": "Choose the correct sentence in IELTS academic writing:",
            "options": [
                "The data shows a dramatically increase.",
                "The data shows a dramatic increase.",
                "The data show dramatically increasing.",
                "The data is show dramatic increase."
            ],
            "correct_id": 1,
            "explanation": "'Increase' bu yerda ot bo'lgani uchun uning oldidan sifat ('dramatic') ishlatiladi.",
        },
        {
            "question": "Which word is the best formal synonym for 'give' in an academic essay?",
            "options": ["hand out", "provide", "dish out", "drop"],
            "correct_id": 1,
            "explanation": "'Provide' rasmiy akademik so'z bo'lib, insholarda keng qo'llaniladi.",
        },
        {
            "question": "What is the past participle (3-forma) of the verb 'choose'?",
            "options": ["chose", "chosen", "choosed", "choicing"],
            "correct_id": 1,
            "explanation": "Choose fe'lining 3-formasi 'chosen' bo'ladi (choose - chose - chosen).",
        },
    ],
    "umumiy": [
        {
            "question": "Kompyuter arxitekturasida protsessor (CPU) eng tezkor ma'lumot almashadigan xotira qaysi?",
            "options": ["Operativ xotira (RAM)", "L1/L2 Kesh (Cache) xotira", "SSD disk", "HDD disk"],
            "correct_id": 1,
            "explanation": "CPU ichidagi Kesh va Registrlar barcha tashqi xotiralardan ancha tez ishlaydi.",
        },
        {
            "question": "Quyosh sistemasidagi eng katta sayyora qaysi?",
            "options": ["Mars", "Yupiter", "Saturn", "Neptun"],
            "correct_id": 1,
            "explanation": "Yupiter Quyosh sistemasidagi eng ulkan gaz giganti hisoblanadi.",
        },
        {
            "question": "O'zbekiston Respublikasi BMT (Birlashgan Millatlar Tashkiloti)ga qaysi yili qabul qilingan?",
            "options": ["1991-yil", "1992-yil", "1993-yil", "1994-yil"],
            "correct_id": 1,
            "explanation": "O'zbekiston 1992-yil 2-martda BMT a'zoligiga qabul qilingan.",
        },
    ],
}


def extract_text_from_file(file_bytes: bytes, filename: str, max_chars: int = 250000) -> str:
    """PDF, Word, TXT yoki boshqa hujjatlardan toza matnni ajratib olish."""
    ext = os.path.splitext(filename)[1].lower() if filename else ""
    text = ""
    try:
        if ext == ".pdf":
            import pymupdf as fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            parts = []
            cur_len = 0
            for page in doc:
                t = page.get_text()
                if t and t.strip():
                    parts.append(t.strip())
                    cur_len += len(t)
                    if cur_len >= max_chars:
                        break
            text = "\n\n".join(parts)[:max_chars]
        elif ext in (".docx", ".doc"):
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        parts.append(" | ".join(cells))
            text = "\n\n".join(parts)[:max_chars]
        else:
            text = file_bytes.decode("utf-8", errors="ignore")[:max_chars]
    except Exception as e:
        logger.warning("Fayldan matn ajratishda xatolik (%s): %s", filename, e)
    return text.strip()


def get_offline_quiz_questions(
    topic: str,
    count: int = 5,
    options_count: int = 4,
) -> list[dict[str, Any]]:
    """Mavzuga mos oflayn zaxira savollarni olish va variantlarni aralashtirish."""
    lower = (topic or "").lower()
    cat = "umumiy"
    if any(k in lower for k in ["matem", "algebra", "hisob", "geometr", "integral"]):
        cat = "matematika"
    elif any(k in lower for k in ["dastur", "python", "sql", "kod", "algoritm", "it", "web"]):
        cat = "dasturlash"
    elif any(k in lower for k in ["ingliz", "english", "ielts", "grammar"]):
        cat = "ingliz_tili"
    else:
        cat = random.choice(list(LOCAL_QUIZ_BANK.keys()))

    pool = list(LOCAL_QUIZ_BANK.get(cat, LOCAL_QUIZ_BANK["umumiy"]))
    selected = pool if count >= len(pool) else random.sample(pool, min(count, len(pool)))

    formatted = []
    for q in selected:
        opts = list(q.get("options", []))
        c_id = q.get("correct_id", 0)
        target_opts = opts[:options_count]
        if c_id >= len(target_opts) and c_id < len(opts):
            target_opts[0] = opts[c_id]
            c_id = 0
        if not (0 <= c_id < len(target_opts)):
            c_id = 0

        # Variantlarni aralashtirish
        indexed = list(enumerate(target_opts))
        random.shuffle(indexed)
        shuffled = [t for _, t in indexed]
        new_c_id = next(n_i for n_i, (o_i, _) in enumerate(indexed) if o_i == c_id)

        formatted.append({
            "question": q["question"],
            "options": shuffled,
            "correct_id": new_c_id,
            "explanation": q.get("explanation", ""),
        })
    return formatted


# Foydalanuvchilarning oxirgi yuklagan fayllari (kesh)
_user_media_cache: dict[int, dict[str, Any]] = {}


def save_user_media(
    user_id: int,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
) -> None:
    _user_media_cache[user_id] = {
        "bytes": file_bytes,
        "name": file_name,
        "mime": mime_type,
        "time": time.time(),
    }


def get_user_media(user_id: int) -> dict[str, Any] | None:
    data = _user_media_cache.get(user_id)
    if data and (time.time() - data.get("time", 0) < 7200):
        return data
    return None
