# 🎯 Quiz Tuzdim Bot (@quiz_tuzdimbot)

Sun'iy intellekt (Google Gemini 3.5 Flash) yordamida turli xil manbalardan professional test (viktorina)lar tuzuvchi, ularni interaktiv yechish va chop etish uchun eksport qiluvchi Telegram bot.

---

## ✨ Imkoniyatlar va Funksiyalar

### 1. Ko'p qirrali manbalar (Multimodal input)
- 🎲 **Mavzu bo'yicha:** Istalgan fan, soha yoki dars mavzusini matn ko'rinishida yuborish.
- 📁 **Hujjatlar (PDF, Word DOCX/DOC, TXT):** Katta darsliklar, qo'llanmalar yoki ma'ruzalardan avtomatik matn ajratib test tuzish.
- 🎥 **Video darsliklar:** Telegram orqali yuborilgan videoni ko'rib, eshitib, undagi formulalar va qoidalardan test olish.
- 🎙 **Ovozli xabarlar va Audiolar (MP3, OGG, WAV):** Audio ma'ruzalarni to'liq tinglab viktorina tuzish.
- 📸 **Rasmlar (Doska, Kitob sahifasi, Konspekt):** Rasmdagi matn va grafiklarni tahlil qilib savollar tuzish.
- 📋 **Tayyor matn (Konspekt):** Chatga tashlangan ixtiyoriy matndan darhol test tuzish.

### 2. Moslashuvchan sozlamalar (Wizard)
- 📊 **Savollar soni:** 3, 5, 10, 15, 20, 30 ta.
- 🔘 **Variantlar soni:** 2 ta (A, B), 3 ta (A, B, C) yoki 4 ta (A, B, C, D).
- 🎚 **Qiyinlik darajalari:** Oson 🟢, O'rta 🟡, Qiyin 🔴, Olimpiada 🏆.
- ⏱ **Taymer:** Cheklovsiz yoki 10s, 15s, 30s, 45s, 60s.

### 3. Testni yechish va Interaktivlik
- 🏁 **Qadamma-qadam (Savolma-savol) sessiya:** Telegram Quiz Poll formatida har bir savol ketma-ket chiqadi.
- 💡 **Xatolar ustida ishlash:** Test yakunlanganda agar noto'g'ri javoblar bo'lsa, maxsus tugma orqali faqat xato savollardan qayta test topshirish imkoniyati!
- 📩 **Barcha testlarni bittalab yuborish:** Guruhlar va kanallarga bir zumda barcha testlarni poll sifatida tashlash.
- 🛑 **To'xtatish va davom ettirish nazorati.**
- 🏆 **Baho va Natijalar tahlili:** To'g'ri/noto'g'ri soni, foiz, sarflangan vaqt va daraja.

### 4. O'qituvchilar va Repetitorlar uchun eksport
- 📄 **Chop etishga tayyor A4 PDF:** Titul, o'quvchi ma'lumotlari kiritish qismi, tartiblangan savollar va oxirgi sahifada Javoblar kaliti hamda tushuntirishlar.
- 📝 **Word (.docx):** Tahrirlash va o'zgartirish uchun formatlangan hujjat.
- 🤖 **@QuizBot import matni:** Rasmiy @QuizBot ga osonlik bilan kiritish uchun qulay ro'yxat va yo'riqnoma.

### 5. Zaxira va Xavfsizlik (Offline Fallback)
- Gemini API tarmoqda uzilish yoki 503 xatosi berganda ham to'xtab qolmasdan boy mahalliy zaxira savollar bazasidan foydalanadi.
- Har bir testda to'g'ri javoblar o'rni tasodifiy aralashtiriladi.

---

## 🚀 O'rnatish va Ishga tushirish

```bash
cd /home/ozodbek/Projects/quiz-tuzdim-bot

# Virtual muhitni faollashtirish
source venv/bin/activate

# Botni ishga tushirish
python main.py
```

## ⚙️ Sozlamalar (`.env`)
```env
BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
DEFAULT_MODEL=gemini-3.5-flash-lite
```
