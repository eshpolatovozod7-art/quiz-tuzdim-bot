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
        {
            "question": "Uchburchakning ichki burchaklari yig'indisi necha gradusga teng?",
            "options": ["90°", "180°", "270°", "360°"],
            "correct_id": 1,
            "explanation": "Evklid geometriyasida har qanday tekis uchburchakning ichki burchaklari yig'indisi 180° ga teng.",
        },
        {
            "question": "Kvadrat tenglama ax² + bx + c = 0 da diskriminant D = b² - 4ac > 0 bo'lsa, tenglama nechta haqiqiy ildizga ega?",
            "options": ["0 ta", "1 ta", "2 ta turli", "Cheksiz ko'p"],
            "correct_id": 2,
            "explanation": "D > 0 bo'lganda kvadrat tenglama 2 ta haqiqiy turli ildizga ega bo'ladi.",
        },
        {
            "question": "Doiraning yuzi qaysi formula orqali hisoblanadi?",
            "options": ["S = 2πR", "S = πR²", "S = 4πR²", "S = πD"],
            "correct_id": 1,
            "explanation": "Doira yuzi radiusi orqali S = πR² formulasi bilan topiladi.",
        },
        {
            "question": "sin²(α) + cos²(α) ifodaning qiymati nimaga teng?",
            "options": ["0", "1", "2", "tg(α)"],
            "correct_id": 1,
            "explanation": "Bu asosiy trigonometrik ayniyat bo'lib, uning qiymati har doim 1 ga teng.",
        },
        {
            "question": "Arifmetik progressiyada a₁ = 3, d = 4 bo'lsa, a₅ hadi nechiga teng?",
            "options": ["15", "19", "23", "27"],
            "correct_id": 1,
            "explanation": "a₅ = a₁ + 4d = 3 + 4 * 4 = 3 + 16 = 19.",
        },
        {
            "question": "Qaysi son na tub, na murakkab son hisoblanadi?",
            "options": ["0", "1", "2", "3"],
            "correct_id": 1,
            "explanation": "1 soni qoidaga ko'ra na tub, na murakkab son deb qabul qilingan.",
        },
        {
            "question": "lim(x→0) sin(x)/x ajoyib limitining qiymati nechiga teng?",
            "options": ["0", "1", "∞", "Aniqlanmagan"],
            "correct_id": 1,
            "explanation": "Birinchi ajoyib limit qoidasiga ko'ra lim(x→0) sin(x)/x = 1 bo'ladi.",
        },
        {
            "question": "∫ x dx aniqmas integrali nimaga teng?",
            "options": ["x² + C", "(x²/2) + C", "1 + C", "x³ + C"],
            "correct_id": 1,
            "explanation": "x ning boshlang'ich funksiyasi (x²/2) + C ga teng.",
        },
        {
            "question": "Muntazam oltiburchakning bitta ichki burchagi necha gradus?",
            "options": ["108°", "120°", "135°", "150°"],
            "correct_id": 1,
            "explanation": "Ichki burchak = (6 - 2) * 180° / 6 = 720° / 6 = 120°.",
        },
        {
            "question": "5! (5 faktorial) qiymati nechiga teng?",
            "options": ["24", "60", "120", "720"],
            "correct_id": 2,
            "explanation": "5! = 5 * 4 * 3 * 2 * 1 = 120.",
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
        {
            "question": "Python-da ro'yxatning oxiriga element qo'shish qaysi metod orqali amalga oshiriladi?",
            "options": ["insert()", "add()", "append()", "push()"],
            "correct_id": 2,
            "explanation": "Python list ob'ektida append(element) oxiriga qo'shadi.",
        },
        {
            "question": "Relatsion ma'lumotlar bazalarida birlamchi kalit (Primary Key) ning asosiy xususiyati nima?",
            "options": ["Faqat matn bo'lishi", "Takrorlanmas (unique) va NULL bo'lmasligi", "Ixtiyoriy bo'lishi", "Manfiy bo'lishi"],
            "correct_id": 1,
            "explanation": "Primary Key har bir qatorni bir qiymatli identifikatsiya qiladi va NULL bo'la olmaydi.",
        },
        {
            "question": "REST API-da yangi ma'lumot yaratish uchun odatda qaysi HTTP metodi ishlatiladi?",
            "options": ["GET", "POST", "PUT", "DELETE"],
            "correct_id": 1,
            "explanation": "POST metodi yangi resurs yaratish uchun xizmat qiladi.",
        },
        {
            "question": "Dasturlashda FIFO (First In, First Out) tamoyili asosida ishlaydigan ma'lumotlar tuzilmasi qaysi?",
            "options": ["Stack (Stek)", "Queue (Navbat)", "Tree (Daraxt)", "Graph (Graf)"],
            "correct_id": 1,
            "explanation": "Navbat (Queue) da birinchi kirgan element birinchi bo'lib chiqadi (FIFO).",
        },
        {
            "question": "JSON formatida qaysi ma'lumot turi qo'llab-quvvatlanmaydi?",
            "options": ["Array", "Object", "Function / Metod", "Boolean"],
            "correct_id": 2,
            "explanation": "JSON faqat sof ma'lumotlarni saqlaydi, unda funksiyalar mavjud emas.",
        },
        {
            "question": "Obyektga yo'naltirilgan dasturlash (OOP)ning asosiy 4 ustunidan biri bo'lmaganini toping:",
            "options": ["Inkapsulyatsiya", "Polimorfizm", "Kompilyatsiya", "Merosxo'rlik"],
            "correct_id": 2,
            "explanation": "OOP ustunlari: Inkapsulyatsiya, Merosxo'rlik, Polimorfizm va Abstraksiya.",
        },
        {
            "question": "Docker texnologiyasining asosiy vazifasi nima?",
            "options": ["Dasturlarni konteynerlashtirish va izolyatsiya qilish", "Operatsion tizim o'rnatish", "Kodni kompilyatsiya qilish", "Grafik dizayn chizish"],
            "correct_id": 0,
            "explanation": "Docker ilovalarni o'z muhiti bilan birga konteynerlarga joylashtirish imkonini beradi.",
        },
        {
            "question": "Binary Search (ikkilik qidiruv) algoritmining ishlashi uchun ro'yxat qanday bo'lishi shart?",
            "options": ["Faqat musbat sonlardan iborat", "Tartiblangan (saralangan)", "Faqat juft sonlar", "Kamida 100 ta element"],
            "correct_id": 1,
            "explanation": "Binary search faqat tartiblangan ro'yxatda ikkiga bo'lish orqali ishlaydi.",
        },
        {
            "question": "Asinxron dasturlashda 'async/await' nima uchun ishlatiladi?",
            "options": ["Kodni sekinlashtirish", "Bloklamaydigan (non-blocking) I/O operatsiyalarini bajarish", "Xotirani tozalash", "Fayllarni shifrlash"],
            "correct_id": 1,
            "explanation": "Asinxron kod dastur oqimini to'xtatib qo'ymasdan parallel operatsiyalarni bajarish imkonini beradi.",
        },
        {
            "question": "CSS da flexbox yoki grid texnologiyasi nima uchun xizmat qiladi?",
            "options": ["Ma'lumotlar bazasini boshqarish", "Sahifadagi elementlarni qulay joylashtirish (layout)", "Serverga so'rov yuborish", "Shifrlash"],
            "correct_id": 1,
            "explanation": "Flexbox va CSS Grid veb sahifadagi bloklarni moslashuvchan joylashtirish vositalaridir.",
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
        {
            "question": "Select the correct preposition: 'She is capable ___ handling this difficult project.'",
            "options": ["to", "at", "of", "with"],
            "correct_id": 2,
            "explanation": "'Capable' sifati har doim 'of' predlogi bilan ishlatiladi (capable of doing sth).",
        },
        {
            "question": "Which word means 'existing in large quantities; plentiful'?",
            "options": ["scarce", "abundant", "fragile", "trivial"],
            "correct_id": 1,
            "explanation": "'Abundant' ko'p miqdorda, serob degan ma'noni anglatadi.",
        },
        {
            "question": "Identify the correct conditional: 'If I ___ you, I would accept the job offer immediately.'",
            "options": ["am", "was", "were", "had been"],
            "correct_id": 2,
            "explanation": "Second Conditional-da maslahat yoki xayoliy holat uchun 'were' qo'llaniladi (If I were you).",
        },
        {
            "question": "Choose the correct antonym of the word 'diligent':",
            "options": ["lazy", "hardworking", "accurate", "clever"],
            "correct_id": 0,
            "explanation": "'Diligent' (mehnatsevar, tirishqoq) so'zining ziddi 'lazy' (dangasa) hisoblanadi.",
        },
        {
            "question": "Which sentence uses the Present Perfect tense correctly?",
            "options": [
                "I have seen him yesterday.",
                "I have lived in Tashkent for five years.",
                "He has went to the market.",
                "They have finish their homework just now."
            ],
            "correct_id": 1,
            "explanation": "Muayyan davr mobaynida davom etayotgan holat uchun Present Perfect + for to'g'ri ishlatilgan.",
        },
        {
            "question": "What is the meaning of the idiom 'a piece of cake'?",
            "options": ["Something very delicious", "Something very easy", "A difficult task", "A birthday gift"],
            "correct_id": 1,
            "explanation": "'A piece of cake' iborasi judayam oson, hech qanday qiyinchiliksiz degan ma'noda keladi.",
        },
        {
            "question": "Select the word that is spelled correctly:",
            "options": ["Accomodation", "Accommodation", "Acommodation", "Acomodation"],
            "correct_id": 1,
            "explanation": "To'g'ri yozilishi: ikkita 'c' va ikkita 'm' bilan — 'Accommodation'.",
        },
        {
            "question": "Choose the correct modal verb: 'You ___ drive on the right in the UK; it is illegal.'",
            "options": ["shouldn't", "mustn't", "don't have to", "might not"],
            "correct_id": 1,
            "explanation": "Qonuniy taqiq uchun 'mustn't' ishlatiladi.",
        },
        {
            "question": "What is the noun form of the adjective 'accurate'?",
            "options": ["accurately", "accuracy", "accurateness", "accuration"],
            "correct_id": 1,
            "explanation": "'Accurate' (aniq) so'zining ot shakli 'accuracy' (aniqlik).",
        },
        {
            "question": "Which word is a synonym for 'meticulous'?",
            "options": ["careless", "careful and precise", "quick", "noisy"],
            "correct_id": 1,
            "explanation": "'Meticulous' har bir mayda detalga e'tibor beruvchi, o'ta puxta degan ma'noni bildiradi.",
        },
        {
            "question": "Fill in the blank: 'Neither John nor his friends ___ arrived yet.'",
            "options": ["has", "have", "is", "was"],
            "correct_id": 1,
            "explanation": "'Neither ... nor' da fe'l o'ziga eng yaqin turgan ot ('friends' - ko'plik) bilan moslashadi.",
        },
        {
            "question": "Which transition word expresses contrast?",
            "options": ["Furthermore", "However", "Consequently", "Moreover"],
            "correct_id": 1,
            "explanation": "'However' (biroq, ammo) zidlovchi bog'lovchi hisoblanadi.",
        },
        {
            "question": "He ______ (read) a book right now. (Present Continuous)",
            "options": ["is reading", "are reading", "am reading", "reads"],
            "correct_id": 0,
            "explanation": "Present Continuous formulasiga ko'ra (Subject + am/is/are + V-ing): 'He' uchun 'is reading' to'g'ri bo'ladi.",
        },
        {
            "question": "Look! The children ______ playing in the playground.",
            "options": ["are", "is", "am", "be"],
            "correct_id": 0,
            "explanation": "'The children' ko'plik ot bo'lgani sababli Present Continuous-da 'are' yordamchi fe'li ishlatiladi.",
        },
        {
            "question": "I ______ (write) an email to my teacher at the moment.",
            "options": ["am writing", "is writing", "are writing", "writes"],
            "correct_id": 0,
            "explanation": "Present Continuous formulasiga ko'ra 'I' shaxs olmoshi uchun 'am writing' ishlatiladi.",
        },
        {
            "question": "She ______ not like spicy food. (Present Simple)",
            "options": ["does", "do", "is", "has"],
            "correct_id": 0,
            "explanation": "Present Simple inkor formulasiga ko'ra (S + do/does + not + V1): 'She' uchun 'does' yordamchi fe'li qo'yiladi.",
        },
        {
            "question": "My father ______ to work by car every morning.",
            "options": ["goes", "go", "is going", "went"],
            "correct_id": 0,
            "explanation": "Present Simple formulasiga ko'ra (S + V1/Vs): 3-shaxs birlik (He) uchun fe'lga '-es' qo'shiladi: 'goes'.",
        },
        {
            "question": "______ you watch the football match last night? (Past Simple)",
            "options": ["Did", "Do", "Were", "Have"],
            "correct_id": 0,
            "explanation": "Past Simple so'roq formulasiga ko'ra (Did + Subject + V1): o'tgan zamon savolida 'Did' ishlatiladi.",
        },
        {
            "question": "We ______ (visit) the museum yesterday.",
            "options": ["visited", "visit", "visiting", "are visiting"],
            "correct_id": 0,
            "explanation": "Past Simple formulasiga ko'ra (Subject + V2/Ved): o'tgan zamonda fe'lning 2-shakli 'visited' ishlatiladi.",
        },
        {
            "question": "At 8 PM yesterday, they ______ (watch) a movie. (Past Continuous)",
            "options": ["were watching", "was watching", "watched", "are watching"],
            "correct_id": 0,
            "explanation": "Past Continuous formulasiga ko'ra (Subject + was/were + V-ing): 'They' uchun 'were watching' qo'yiladi.",
        },
        {
            "question": "She ______ already finished her project. (Present Perfect)",
            "options": ["has", "have", "is", "had"],
            "correct_id": 0,
            "explanation": "Present Perfect formulasiga ko'ra (Subject + have/has + V3): 'She' uchun 'has' ishlatiladi.",
        },
        {
            "question": "I think it ______ rain tomorrow. (Future Simple)",
            "options": ["will", "is", "shall", "does"],
            "correct_id": 0,
            "explanation": "Future Simple formulasiga ko'ra (Subject + will + V1): kelasi zamon taxmini uchun 'will' ishlatiladi.",
        },
        {
            "question": "______ they playing football right now? (Present Continuous)",
            "options": ["Are", "Is", "Do", "Did"],
            "correct_id": 0,
            "explanation": "Present Continuous so'roq formulasiga ko'ra (Am/Is/Are + S + V-ing): 'they' uchun gap boshida 'Are' keladi.",
        },
        {
            "question": "We ______ not go to school on Sundays.",
            "options": ["do", "does", "are", "have"],
            "correct_id": 0,
            "explanation": "Present Simple inkor formulasiga ko'ra (S + do/does + not + V1): 'We' uchun 'do' ishlatiladi.",
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
        {
            "question": "Inson tanasidagi eng katta ichki a'zo qaysi?",
            "options": ["Yurak", "Jigar", "O'pka", "Oshqozon"],
            "correct_id": 1,
            "explanation": "Jigar inson organizmidagi eng og'ir va eng katta ichki a'zo hisoblanadi.",
        },
        {
            "question": "Dunyodagi eng uzun daryo qaysi?",
            "options": ["Amazonka", "Nil", "Yangtze", "Missisipi"],
            "correct_id": 1,
            "explanation": "Afrikadagi Nil daryosi (taxminan 6650 km) dunyodagi eng uzun daryo hisoblanadi.",
        },
        {
            "question": "Amir Temur qaysi yilda tavallud topgan?",
            "options": ["1336-yil", "1340-yil", "1370-yil", "1405-yil"],
            "correct_id": 0,
            "explanation": "Sohibqiron Amir Temur 1336-yil 9-aprelda Kesh (Shahrisabz) yaqinidagi Xoja Ilg'or qishlog'ida tug'ilgan.",
        },
        {
            "question": "Atomning yadrosida qanday zarralar joylashgan?",
            "options": ["Faqat elektronlar", "Proton va neytronlar", "Elektron va protonlar", "Faqat fotonlar"],
            "correct_id": 1,
            "explanation": "Atom yadrosi musbat zaryadli protonlar va neytral neytronlardan tashkil topgan.",
        },
        {
            "question": "Kimyoviy elementlar davriy jadvalida 'Fe' belgisi qaysi elementni bildiradi?",
            "options": ["Ftor", "Temir (Ferrum)", "Fosfor", "Fransiy"],
            "correct_id": 1,
            "explanation": "Fe lotincha 'Ferrum' so'zidan olingan bo'lib, temir elementini anglatadi.",
        },
        {
            "question": "O'zbekiston Respublikasining Konstitutsiyasi qachon qabul qilingan?",
            "options": ["1991-yil 1-sentyabr", "1992-yil 8-dekabr", "1993-yil 1-oktyabr", "1994-yil 1-iyul"],
            "correct_id": 1,
            "explanation": "O'zbekiston Konstitutsiyasi 1992-yil 8-dekabrda qabul qilingan.",
        },
        {
            "question": "Yer atmosferasining eng katta qismini qaysi gaz tashkil qiladi?",
            "options": ["Kislorod", "Azot", "Karbonat angidrid", "Vodorod"],
            "correct_id": 1,
            "explanation": "Havo tarkibining taxminan 78% qismini Azot (N₂) gazi tashkil qiladi.",
        },
        {
            "question": "Al-Xorazmiy qaysi fanning asoschilaridan biri hisoblanadi?",
            "options": ["Tibbiyot", "Algebra", "Kimyo", "Falsafa"],
            "correct_id": 1,
            "explanation": "Muhammad ibn Muso al-Xorazmiy 'Al-Jabr' asari bilan algebra faniga asos solgan.",
        },
        {
            "question": "Suvning qaynash harorati normal atmosfera bosimida necha gradus Selsiy?",
            "options": ["80°C", "90°C", "100°C", "120°C"],
            "correct_id": 2,
            "explanation": "Normal bosimda (1 atm) toza suv 100°C haroratda qaynaydi.",
        },
        {
            "question": "Eng chuqur chuchuk suvli ko'l qaysi?",
            "options": ["Baykal", "Kaspiy", "Viktoriya", "Yuqori ko'l"],
            "correct_id": 0,
            "explanation": "Rossiyadagi Baykal ko'li (chuqurligi 1642 m) dunyodagi eng chuqur ko'ldir.",
        },
        {
            "question": "Yorug'lik tezligi vakuumda taxminan sekundiga qancha?",
            "options": ["300 km/s", "30 000 km/s", "300 000 km/s", "3 000 000 km/s"],
            "correct_id": 2,
            "explanation": "Yorug'likning bo'shliqdagi tezligi sekundiga taxminan 300 000 km ni tashkil etadi.",
        },
        {
            "question": "DNK molekulasining qo'sh spiral strukturasini kimlar kashf etgan?",
            "options": ["Mendel va Morqan", "Uotson va Krik", "Paster va Kox", "Darvin va Lamark"],
            "correct_id": 1,
            "explanation": "Jeyms Uotson va Frensis Krik 1953-yilda DNK qo'sh spiral tuzilishini kashf etgan.",
        },
    ],
    "fizika": [
        {
            "question": "Nyutonning ikkinchi qonuni formulasini ko'rsating:",
            "options": ["F = m * a", "E = m * c²", "P = U * I", "v = s / t"],
            "correct_id": 0,
            "explanation": "Nyutonning II qonuni: jismga ta'sir etuvchi kuch uning massasi va olgan tezlanishi ko'paytmasiga teng (F = ma).",
        },
        {
            "question": "Zanjir qismi uchun Om qonuni qaysi formula bilan ifodalanadi?",
            "options": ["I = U / R", "U = I / R", "R = U * I", "P = I² * t"],
            "correct_id": 0,
            "explanation": "Om qonuniga ko'ra tok kuchi kuchlanishga to'g'ri, qarshilikka teskari mutanosibdir (I = U / R).",
        },
        {
            "question": "Nyutonning birinchi qonuni yana qanday nom bilan mashhur?",
            "options": ["Inersiya qonuni", "Ta'sir va aks ta'sir qonuni", "Butun olam tortishish qonuni", "Paskal qonuni"],
            "correct_id": 0,
            "explanation": "Nyutonning 1-qonuni inersiya qonuni deb ataladi (tashqi kuch ta'sir etmaguncha jism o'z tinch yoki to'g'ri chiziqli tekis harakat holatini saqlaydi).",
        },
        {
            "question": "Xalqaro birliklar sistemasida (SI) bosim birligi nima?",
            "options": ["Nyuton (N)", "Paskal (Pa)", "Joul (J)", "Vatt (W)"],
            "correct_id": 1,
            "explanation": "SI sistemasida bosim birligi Paskal (Pa) bo'lib, 1 Pa = 1 N/m² ga teng.",
        },
        {
            "question": "Kinetik energiyaning hisoblash formulasi qaysi?",
            "options": ["E = (m * v²) / 2", "E = m * g * h", "E = F * s", "E = k * x² / 2"],
            "correct_id": 0,
            "explanation": "Harakatdagi jismning kinetik energiyasi E = (m * v²) / 2 formulasi orqali topiladi.",
        },
        {
            "question": "Yorug'likning vakuumdagi tezligi sekundiga taxminan qancha?",
            "options": ["150 000 km/s", "300 000 km/s", "500 000 km/s", "1 000 000 km/s"],
            "correct_id": 1,
            "explanation": "Yorug'lik tezligi vakuumda taxminan c = 300 000 km/s (3 * 10⁸ m/s) ga teng.",
        },
    ],
    "tarix": [
        {
            "question": "Sohibqiron Amir Temur qaysi yilda tavallud topgan?",
            "options": ["1336-yil 9-aprel", "1340-yil 1-may", "1370-yil 10-aprel", "1405-yil 18-fevral"],
            "correct_id": 0,
            "explanation": "Amir Temur 1336-yil 9-aprelda Kesh (Shahrisabz) yaqinidagi Xo'ja Ilg'or qishlog'ida tug'ilgan.",
        },
        {
            "question": "Amir Temurning Movarounnahr oliy hukmdori deb e'lon qilingan mashhur Balx qurultoyi qaysi yili bo'lgan?",
            "options": ["1365-yil", "1370-yil", "1380-yil", "1395-yil"],
            "correct_id": 1,
            "explanation": "1370-yil aprel oyida bo'lib o'tgan Balx qurultoyida Amir Temur Movarounnahrning yagona hukmdori deb e'lon qilingan.",
        },
        {
            "question": "Turkistonda Jadidchilik harakatining asoschilaridan biri, birinchi o'zbek dramasini yozgan ma'rifatparvar kim?",
            "options": ["Mahmudxo'ja Behbudiy", "Abdulla Avloniy", "Munavvarqori Abdurashidxonov", "Abdurauf Fitrat"],
            "correct_id": 0,
            "explanation": "Mahmudxo'ja Behbudiy jadidlik harakati yetakchisi hamda 'Padarkush' nomli birinchi o'zbek dramasining muallifidir.",
        },
        {
            "question": "Mirzo Ulug'bek tomonidan Samarqandda qurilgan mashhur rasadxona qaysi asrga tegishli?",
            "options": ["XII asr", "XIV asr", "XV asr (1424-1428)", "XVI asr"],
            "correct_id": 2,
            "explanation": "Ulug'bek rasadxonasi XV asrda (1424-1428 yillarda) Samarqandning Ko'hak tepaligida qurilgan.",
        },
        {
            "question": "O'zbekiston Respublikasining davlat mustaqilligi qachon e'lon qilingan?",
            "options": ["1991-yil 31-avgust (1-sentabr)", "1992-yil 8-dekabr", "1990-yil 20-iyun", "1991-yil 18-noyabr"],
            "correct_id": 0,
            "explanation": "1991-yil 31-avgustda O'zbekiston mustaqilligi e'lon qilingan va 1-sentabr Mustaqillik kuni deb belgilangan.",
        },
    ],
    "biologiya": [
        {
            "question": "O'simliklar hujayrasida fotosintez jarayoni qaysi organoidda amalga oshadi?",
            "options": ["Xloroplastlarda", "Mitoxondriyada", "Ribosomada", "Yadroda"],
            "correct_id": 0,
            "explanation": "Fotosintez jarayoni o'simlik hujayrasining xlorofill pigmentiga ega bo'lgan xloroplastlarida kechadi.",
        },
        {
            "question": "Hujayraning 'energiya stansiyasi' deb ataluvchi organoid qaysi?",
            "options": ["Mitoxondriya", "Golji majmuasi", "Lizosoma", "Ribosoma"],
            "correct_id": 0,
            "explanation": "Mitoxondriyalarda ATF (adenozintrifosfat) sintezlanadi va ular hujayrani energiya bilan ta'minlaydi.",
        },
        {
            "question": "Genetika fanining asoschisi kim hisoblanadi?",
            "options": ["Gregor Mendel", "Charlz Darvin", "Lui Paster", "Ivan Pavlov"],
            "correct_id": 0,
            "explanation": "Noxat ustida tajribalar o'tkazib irsiyat qonuniyatlarini kashf etgan Gregor Mendel genetika asoschisidir.",
        },
        {
            "question": "Inson yuragi necha kameradan iborat?",
            "options": ["2 ta", "3 ta", "4 ta (2 bo'lmacha, 2 qorincha)", "5 ta"],
            "correct_id": 2,
            "explanation": "Sutemizuvchilar va inson yuragi to'rt kameradan (o'ng va chap bo'lmacha, o'ng va chap qorincha) iborat.",
        },
    ],
    "kimyo": [
        {
            "question": "Oddiy toza suvning kimyoviy formulasi qaysi?",
            "options": ["H₂O", "H₂O₂", "CO₂", "NaCl"],
            "correct_id": 0,
            "explanation": "Suv molekulasi ikkita vodorod va bitta kislorod atomidan iborat bo'lib, H₂O deb yoziladi.",
        },
        {
            "question": "Kimyoviy elementlarning davriy qonunini kim kashf etgan?",
            "options": ["D.I. Mendeleyev", "Antuan Lavuazye", "Jon Dalton", "Ernest Rezerford"],
            "correct_id": 0,
            "explanation": "1869-yilda rus olimi D.I. Mendeleyev kimyoviy elementlarning davriy qonuni va jadvalini kashf etgan.",
        },
        {
            "question": "Neytral muhitning pH ko'rsatkichi nechiga teng?",
            "options": ["0", "7", "14", "10"],
            "correct_id": 1,
            "explanation": "pH = 7 neytral muhit (masalan, toza distillangan suv), pH < 7 kislotali, pH > 7 ishqoriy muhit hisoblanadi.",
        },
        {
            "question": "Mendeleyev davriy jadvalidagi birinchi va eng yengil kimyoviy element qaysi?",
            "options": ["Vodorod (H)", "Geliy (He)", "Litiy (Li)", "Kislorod (O)"],
            "correct_id": 0,
            "explanation": "Vodorod (H) atom massasi 1 ga teng bo'lgan eng yengil va davriy jadvaldagi 1-elementdir.",
        },
    ],
    "ona_tili": [
        {
            "question": "O'zbek adabiy tilida nechta unli tovush mavjud?",
            "options": ["6 ta (a, o, i, u, e, o')", "8 ta", "10 ta", "12 ta"],
            "correct_id": 0,
            "explanation": "Hozirgi o'zbek adabiy tilida 6 ta unli tovush (fonema) mavjud: a, o, i, u, e, o'.",
        },
        {
            "question": "Alisher Navoiyning turkiy tilda yozilgan mashhur beshlik dostoni qanday ataladi?",
            "options": ["Xamsa", "Xazoyinul-maoniy", "Muhokamatul-lug'atayn", "Lisonut-tayr"],
            "correct_id": 0,
            "explanation": "Alisher Navoiy 1483-1485 yillarda besh dostondan iborat 'Xamsa' asarini yaratgan.",
        },
        {
            "question": "O'zbek adabiyotidagi ilk realistik roman qaysi va uning muallifi kim?",
            "options": ["'O'tkan kunlar' - Abdulla Qodiriy", "'Navoiy' - Oybek", "'Mehrobdan chayon' - Cho'lpon", "'Kecha va kunduz' - Fitrat"],
            "correct_id": 0,
            "explanation": "Abdulla Qodiriyning 1922-1925 yillarda yozilgan 'O'tkan kunlar' asari ilk o'zbek romanidir.",
        },
        {
            "question": "Shaxs, narsa va hodisalarning belgisini (rangi, shakli, xususiyatini) bildiruvchi so'z turkumi qaysi?",
            "options": ["Sifat", "Ot", "Son", "Olmosh"],
            "correct_id": 0,
            "explanation": "Sifat so'z turkumi narsa-buyumlarning belgisini bildiradi va 'qanday?', 'qanaqa?' so'roqlariga javob bo'ladi.",
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
    used_questions: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Mavzuga mos oflayn zaxira savollarni olish va variantlarni aralashtirish."""
    lower = (topic or "").lower()
    cat = "umumiy"
    if any(k in lower for k in ["matem", "algebra", "hisob", "geometr", "integral", "kvadrat tenglama", "kasr", "progressiya"]):
        cat = "matematika"
    elif any(k in lower for k in ["dastur", "python", "sql", "kod", "algoritm", "it", "web", "html", "css", "git"]):
        cat = "dasturlash"
    elif any(k in lower for k in ["ingliz", "english", "ielts", "grammar", "present", "past", "passive", "vocabulary", "tense"]):
        cat = "ingliz_tili"
    elif any(k in lower for k in ["fizik", "nyuton", "kinematik", "dinamik", "tok", "om qonuni", "optika", "quvvat", "energiya"]):
        cat = "fizika"
    elif any(k in lower for k in ["tarix", "temur", "jadid", "movarounnahr", "xonlik", "ipak yo'li", "mustaqillik"]):
        cat = "tarix"
    elif any(k in lower for k in ["biolog", "hujayra", "genetik", "mendel", "fotosintez", "anatomiya", "botanika", "zoologiya"]):
        cat = "biologiya"
    elif any(k in lower for k in ["kimyo", "mendeleyev", "reaksiya", "oksidlanish", "organik", "kislota", "eritma"]):
        cat = "kimyo"
    elif any(k in lower for k in ["ona tili", "adabiyot", "navoiy", "bobur", "fonetika", "morfologiya", "sintaksis", "imlo"]):
        cat = "ona_tili"
    else:
        cat = random.choice(list(LOCAL_QUIZ_BANK.keys()))

    pool = list(LOCAL_QUIZ_BANK.get(cat, LOCAL_QUIZ_BANK["umumiy"]))

    # Agar ingliz tili formulalari yoki zamonlari so'ralgan bo'lsa, gap to'ldirish savollarini oldinga qo'yish
    if cat == "ingliz_tili" and any(k in lower for k in ["continuous", "present", "past", "formula", "zamon", "tense", "verb", "gap"]):
        fill_blanks = [q for q in pool if "______" in q.get("question", "") or "___" in q.get("question", "")]
        if len(fill_blanks) >= count:
            pool = fill_blanks
        else:
            others = [q for q in pool if q not in fill_blanks]
            pool = fill_blanks + others

    # Avval ishlatilgan savollarni chetlatish
    if used_questions:
        filtered_pool = []
        for q in pool:
            q_clean = q.get("question", "").strip().lower()
            if not any(uq in q_clean or q_clean in uq for uq in used_questions):
                filtered_pool.append(q)
        if filtered_pool:
            pool = filtered_pool

    if count <= len(pool):
        selected = random.sample(pool, count)
    else:
        selected = list(pool)
        while len(selected) < count:
            selected.append(random.choice(pool))

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
    file_bytes: bytes | None = None,
    file_name: str | None = None,
    mime_type: str | None = None,
    text_content: str | None = None,
) -> None:
    _user_media_cache[user_id] = {
        "bytes": file_bytes,
        "name": file_name,
        "mime": mime_type,
        "text": text_content,
        "time": time.time(),
    }


def get_user_media(user_id: int) -> dict[str, Any] | None:
    data = _user_media_cache.get(user_id)
    if data and (time.time() - data.get("time", 0) < 7200):
        return data
    return None
