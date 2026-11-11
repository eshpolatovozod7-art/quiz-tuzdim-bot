import logging
from google import genai
from config import GEMINI_API_KEY, DEFAULT_MODEL

logger = logging.getLogger(__name__)


class TutorService:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or DEFAULT_MODEL
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    async def analyze_wrong_questions(
        self,
        quiz_title: str,
        wrong_questions: list[dict],
    ) -> str:
        """
        O'quvchi xato qilgan savollarni sun'iy intellekt orqali chuqur pedagogik tahlil qilish va maslahatlar berish.
        """
        if not self.client or not wrong_questions:
            return "Xatolar tahlilini olish uchun AI xizmati ulanmagan yoki xatolar yo'q."

        # Savollar ma'lumotlarini matnga aylantirish
        questions_text = ""
        for idx, q in enumerate(wrong_questions[:5], 1):  # Maksimal 5 ta xato bir martada
            q_text = q.get("question", "")
            opts = q.get("options", [])
            c_id = q.get("correct_id", 0)
            correct_ans = opts[c_id] if 0 <= c_id < len(opts) else "Noma'lum"
            expl = q.get("explanation", "")
            questions_text += (
                f"{idx}-savol: {q_text}\n"
                f"To'g'ri javob: {correct_ans}\n"
                f"Asosiy qoida: {expl}\n\n"
            )

        prompt = (
            f"Siz mehribon, kuchli va rag'batlantiruvchi Shaxsiy AI Repetitorsiz.\n"
            f"O'quvchi «{quiz_title}» testida quyidagi savollarda adashdi:\n\n"
            f"{questions_text}\n"
            "VAZIFANGIZ:\n"
            "O'quvchiga quyidagi tuzilmada tushunarli, dalda beruvchi va professional tahlil yozing:\n"
            "1. Qaysi mavzu yoki qoidada adashilganini aniq ko'rsating.\n"
            "2. Qoidani eslab qolishning oson 'Lifehack' yoki formulasini bering.\n"
            "3. O'quvchining kelajakda bu xatoni takrorlamasligi uchun qisqa amaliy tavsiya bering.\n\n"
            "TALABLAR:\n"
            "- Telegram uchun mos HTML formatda (<b>, <i>, <code> teglaridan foydalaning, hech qanday markdown ** ishlatmang).\n"
            "- Matn ixcham, jozibali va o'zbek tilida bo'lsin.\n"
            "- Emojilardan o'rinli foydalaning."
        )

        models_to_try = [
            self.model,
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
        ]
        seen = set()
        unique_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        for model_name in unique_models:
            try:
                response = await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning("AI repetitor tahlilida model %s xatoligi: %s", model_name, e)
                continue

        logger.error("Barcha modellar AI repetitor tahlilida muvaffaqiyatsiz bo'ldi.")
        return (
            "⚠️ <b>AI Repetitor tahlilida vaqtinchalik uzilish yuz berdi.</b>\n\n"
            "Iltimos, pastdagi «Xatolar ustida ishlash» tugmasi orqali savollarni qayta topshirib ko'ring!"
        )
