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

        prompt = (
            f"Siz professional testolog, pedagog va metodistsiz.\n"
            f"Quyida berilgan manba asosida ROPPA-ROSA {count} TA sifatli, mantiqan to'g'ri va qiziqarli test (viktorina) savollarini tuzing.\n\n"
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
            f"4. explanation (Izoh): To'g'ri javob nima uchun to'g'riligini va asosiy qoidani qisqa tushuntirib bering (maksimal 180 belgi).\n"
            f"5. BUTUN HUJJATNI QAMRAB OLING: Savollarni faqat hujjat boshidan emas, butun matn bo'ylab (boshi, o'rtasi, oxiri, turli darslar) aralash holda tanlang.\n"
            f"6. Til qoidasi: Agar mavzu xorijiy til (ingliz tili, rus tili va h.k.) o'rganishga oid bo'lsa, test savollari va variantlari o'sha o'rganilayotgan tilda (yoki grammatika/lug'at topshirig'i shaklida), izohi (explanation) esa o'zbek tilida tushuntirilsin. Boshqa fanlar uchun savollar to'liq o'zbek tilida bo'lsin.\n"
            f"{grammar_formula_clause}"
            f"{listening_clause}"
            f"7. Javobingiz FAQAT aynan {count} ta elementdan iborat JSON array formatida bo'lsin:\n"
            "[\n"
            "  {\n"
            f"{listening_sample_json}"
            '    "question": "Savol matni?",\n'
            f'    "options": {sample_opts_json},\n'
            '    "correct_id": 0,\n'
            '    "explanation": "Qisqa tushuntirish"\n'
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
                "gemini-flash-lite-latest",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-3.5-flash",
                "gemini-3.8-flash",
                "gemini-flash-latest",
            ]
            seen = set()
            unique_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

            for model_name in unique_models:
                try:
                    config = types.GenerateContentConfig(
                        system_instruction=(
                            f"Siz bilimli, xolis va tajribali pedagog-testologsiz. "
                            f"Sizdan so'ralgan roppa-rosa {count} ta savolni to'liq shakllantiring. "
                            f"JSON arrayida aynan {count} ta obyekt bo'lsin."
                        ),
                        response_mime_type="application/json",
                        temperature=0.7,
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
                        q_text = str(item.get("question", "")).strip()
                        opts = [str(o).strip()[:98] for o in item.get("options", []) if str(o).strip()]
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
        if not self.client or not text_content:
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
            self.model,
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
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
        }.get(difficulty, "O'rta (standart daraja)")

        is_grammar_formula = is_english_grammar_or_formula_content(text=text_content)
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
                    q_text = str(q.get("question", "")).strip()
                    opts = [str(o).strip()[:98] for o in q.get("options", []) if str(o).strip()]
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

        models_to_try = [
            self.model,
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-flash-latest",
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

            sem = asyncio.Semaphore(3)

            async def process_chunk(chunk_topics: list[str]) -> list[dict[str, Any]]:
                chunk_prompt = (
                    "Siz professional pedagog-testologsiz.\n"
                    f"Quyida ko'rsatilgan darslar/mavzularning HAR BIRI uchun alohida roppa-rosa {questions_per_topic} tadan sifatli test savollarini tuzing.\n\n"
                    f"KO'RSATILGAN MAVZULAR RO'YXATI:\n{json.dumps(chunk_topics, ensure_ascii=False, indent=2)}\n\n"
                    f"PARAMETRLAR:\n"
                    f"- Har bir mavzudagi savollar soni: {questions_per_topic} ta\n"
                    f"- Variantlar soni: {options_count} ta\n"
                    f"- Qiyinlik darajasi: {diff_uz}\n\n"
                    "TALABLAR:\n"
                    "1. Ro'yxatdagi har bir mavzuni o'z ichiga olgan alohida obyekt tuzing.\n"
                    "2. 'topic_title' aynan o'sha mavzu nomi bo'lsin.\n"
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
                    '        "explanation": "Qisqa izoh"\n'
                    "      }\n"
                    "    ]\n"
                    "  }\n"
                    "]\n\n"
                    f"MANBA HUJJAT MATNI:\n\"\"\"\n{text_content[:60000]}\n\"\"\""
                )

                async with sem:
                    for m_name in unique_models:
                        try:
                            cfg = types.GenerateContentConfig(
                                system_instruction="Ko'rsatilgan har bir mavzu uchun alohida sifatli test savollarini JSON ro'yxatida tuzib bering.",
                                response_mime_type="application/json",
                                temperature=0.7,
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
            "Siz professional pedagog-testolog va metodistsiz.\n"
            "Quyida berilgan hujjat (darslik, konspekt yoki lug'at)da bir nechta darslar, unitlar yoki mavzular mavjud.\n"
            f"Vazifangiz: Hujjatdagi HAR BIR dars/mavzu/unitni aniqlab, har biri uchun alohida roppa-rosa {questions_per_topic} tadan sifatli test savollarini tuzing.\n\n"
            f"PARAMETRLAR:\n"
            f"- Har bir mavzudagi savollar soni: {questions_per_topic} ta\n"
            f"- Variantlar soni: {options_count} ta\n"
            f"- Qiyinlik darajasi: {diff_uz}\n\n"
            "QAT'IY TALABLAR:\n"
            "1. Hujjatdagi barcha dars/mavzularni to'liq qamrab oling.\n"
            "2. 'topic_title' maydonida mavzuning aniq nomi bo'lsin.\n"
            "3. Savollar va variantlar o'sha mavzuning lug'ati va faktlariga mos bo'lsin.\n"
            "4. Har bir savolda 'question', 'options', 'correct_id' (0 dan boshlanadi), va 'explanation' bo'lsin.\n"
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
            '        "explanation": "Qisqa izoh"\n'
            "      }\n"
            "    ]\n"
            "  }\n"
            "]\n\n"
            f"HUJJAT MATNI:\n\"\"\"\n{text_content[:100000]}\n\"\"\""
        )

        for model_name in unique_models:
            try:
                config = types.GenerateContentConfig(
                    system_instruction="Siz tajribali pedagog-testologsiz. Hujjatdagi barcha dars/mavzularni aniqlab, har biriga alohida testlar to'plamini JSON ro'yxatida to'liq tuzib bering.",
                    response_mime_type="application/json",
                    temperature=0.7,
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
