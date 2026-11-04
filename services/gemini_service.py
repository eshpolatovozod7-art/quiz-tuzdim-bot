import asyncio
import json
import logging
import os
import random
import tempfile
from typing import Any
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, DEFAULT_MODEL

logger = logging.getLogger(__name__)


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

            if file_bytes and is_media:
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
            elif text_content:
                prompt += f"MANBA MATNI:\n\"\"\"\n{text_content[:200000]}\n\"\"\""
            else:
                prompt += f"MANBA MAVZUSI: '{topic or 'Umumiy bilimlar'}'"

            contents.append(prompt)

            models_to_try = [
                self.model,
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-flash-lite-latest",
                "gemini-3.8-flash",
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

                    parsed = json.loads(raw_text.strip())
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
