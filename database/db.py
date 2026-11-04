import json
import logging
import time
from typing import Any
import aiosqlite
from config import DB_PATH

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Ma'lumotlar bazasi jadvallarini ishga tushirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registered_at REAL,
                tests_created INTEGER DEFAULT 0,
                tests_taken INTEGER DEFAULT 0,
                total_correct INTEGER DEFAULT 0,
                total_questions INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id TEXT PRIMARY KEY,
                user_id INTEGER,
                title TEXT,
                source_type TEXT,
                topic TEXT,
                created_at REAL,
                question_count INTEGER,
                options_count INTEGER,
                timer_seconds INTEGER,
                difficulty TEXT,
                questions_json TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id TEXT,
                user_id INTEGER,
                correct_count INTEGER,
                total_count INTEGER,
                percentage INTEGER,
                time_spent_seconds INTEGER,
                completed_at REAL,
                wrong_questions_json TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                source_label TEXT,
                question_text TEXT,
                created_at REAL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                quiz_id TEXT,
                user_id INTEGER,
                user_name TEXT,
                score INTEGER DEFAULT 0,
                total_answered INTEGER DEFAULT 0,
                last_active REAL,
                UNIQUE(group_id, quiz_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_id TEXT,
                channel_title TEXT,
                topic TEXT,
                question_count INTEGER DEFAULT 3,
                interval_hours INTEGER DEFAULT 24,
                last_posted REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_streaks (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_active_date TEXT DEFAULT '',
                last_quiz_time REAL DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS duels (
                duel_id TEXT PRIMARY KEY,
                creator_id INTEGER,
                creator_name TEXT,
                opponent_id INTEGER DEFAULT 0,
                opponent_name TEXT DEFAULT '',
                topic TEXT,
                questions_json TEXT,
                creator_score INTEGER DEFAULT 0,
                creator_time INTEGER DEFAULT 0,
                opponent_score INTEGER DEFAULT 0,
                opponent_time INTEGER DEFAULT 0,
                creator_finished INTEGER DEFAULT 0,
                opponent_finished INTEGER DEFAULT 0,
                status TEXT DEFAULT 'waiting',
                created_at REAL
            )
        """)

        await db.commit()
    logger.info("Ma'lumotlar bazasi tayyor: %s", DB_PATH)


async def register_or_update_user(user_id: int, username: str | None, first_name: str | None) -> None:
    """Foydalanuvchini ro'yxatdan o'tkazish yoki ma'lumotlarini yangilash."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = time.time()
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, registered_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username or "", first_name or "", now))
        await db.commit()


async def increment_user_tests_created(user_id: int) -> None:
    """Foydalanuvchi tuzgan testlar sonini 1 ga oshirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET tests_created = tests_created + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def save_quiz(
    quiz_id: str,
    user_id: int,
    title: str,
    source_type: str,
    topic: str,
    questions: list[dict],
    options_count: int = 4,
    timer_seconds: int = 0,
    difficulty: str = "medium",
) -> None:
    """Yangi tuzilgan quizni saqlash."""
    async with aiosqlite.connect(DB_PATH) as db:
        now = time.time()
        q_json = json.dumps(questions, ensure_ascii=False)
        await db.execute("""
            INSERT OR REPLACE INTO quizzes (
                quiz_id, user_id, title, source_type, topic, created_at,
                question_count, options_count, timer_seconds, difficulty, questions_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quiz_id, user_id, title, source_type, topic, now,
            len(questions), options_count, timer_seconds, difficulty, q_json
        ))

        # Savollar takrorlanmasligi uchun used_questions jadvaliga yozib boramiz
        for q in questions:
            q_text = q.get("question", "").strip()
            if q_text:
                await db.execute("""
                    INSERT INTO used_questions (user_id, source_label, question_text, created_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, title, q_text, now))

        await db.commit()
    await increment_user_tests_created(user_id)


async def get_quiz(quiz_id: str) -> dict[str, Any] | None:
    """Quizni ID bo'yicha bazadan olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["questions"] = json.loads(data["questions_json"])
            return data


async def get_user_quizzes(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """Foydalanuvchi tuzgan oxirgi testlarni olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM quizzes WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["questions"] = json.loads(item["questions_json"])
                result.append(item)
            return result


async def save_attempt(
    quiz_id: str,
    user_id: int,
    correct_count: int,
    total_count: int,
    time_spent_seconds: int,
    wrong_questions: list[dict],
) -> int:
    """Test yechish urinishini saqlash va foydalanuvchi statistikasini yangilash."""
    percentage = round((correct_count / total_count) * 100) if total_count > 0 else 0
    now = time.time()
    wrong_json = json.dumps(wrong_questions, ensure_ascii=False)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO quiz_attempts (
                quiz_id, user_id, correct_count, total_count,
                percentage, time_spent_seconds, completed_at, wrong_questions_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quiz_id, user_id, correct_count, total_count,
            percentage, time_spent_seconds, now, wrong_json
        ))
        attempt_id = cursor.lastrowid

        await db.execute("""
            UPDATE users SET
                tests_taken = tests_taken + 1,
                total_correct = total_correct + ?,
                total_questions = total_questions + ?
            WHERE user_id = ?
        """, (correct_count, total_count, user_id))

        await db.commit()
        return attempt_id


async def get_user_stats(user_id: int) -> dict[str, Any]:
    """Foydalanuvchining umumiy statistikasini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            u_row = await cursor.fetchone()

        async with db.execute(
            "SELECT COUNT(*) as count FROM quizzes WHERE user_id = ?", (user_id,)
        ) as cursor:
            created_count = (await cursor.fetchone())["count"]

        async with db.execute("""
            SELECT
                COUNT(*) as attempts_count,
                AVG(percentage) as avg_score,
                SUM(time_spent_seconds) as total_time
            FROM quiz_attempts WHERE user_id = ?
        """, (user_id,)) as cursor:
            att_row = await cursor.fetchone()

        tests_taken = (att_row["attempts_count"] if att_row else 0) or 0
        avg_score = round(att_row["avg_score"] or 0) if att_row and att_row["avg_score"] else 0
        total_time = (att_row["total_time"] if att_row else 0) or 0

        return {
            "tests_created": created_count,
            "tests_taken": tests_taken,
            "avg_score": avg_score,
            "total_time": total_time,
            "registered_at": u_row["registered_at"] if u_row else time.time(),
        }


async def get_user_used_questions(user_id: int, source_label: str) -> set[str]:
    """Foydalanuvchining avvalgi testlarida shu fayl yoki mavzudan ishlatilgan barcha savollarini olish."""
    import re
    clean_label = re.sub(r"\.(pdf|docx|doc|txt|mp4|mkv|mov|avi|jpg|png|ogg|mp3)", "", source_label, flags=re.IGNORECASE).strip()
    prefix_match = clean_label[:15] if len(clean_label) >= 4 else clean_label

    used: set[str] = set()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 1. used_questions jadvalidan qidirish
        async with db.execute(
            "SELECT question_text FROM used_questions WHERE user_id = ? AND (source_label = ? OR source_label LIKE ?)",
            (user_id, source_label, f"%{prefix_match}%"),
        ) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                txt = str(r[0] or "").strip()
                clean = re.sub(r"^\[\d+/\d+\]\s*", "", txt).strip().lower()
                if clean:
                    used.add(clean)

        # 2. quizzes jadvalidan ham kafolatlangan holda to'plash
        async with db.execute(
            "SELECT questions_json FROM quizzes WHERE user_id = ? AND (title = ? OR title LIKE ? OR topic LIKE ?) ORDER BY created_at DESC LIMIT 50",
            (user_id, source_label, f"%{prefix_match}%", f"%{prefix_match}%"),
        ) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                try:
                    q_list = json.loads(r["questions_json"])
                    for item in q_list:
                        q_txt = str(item.get("question", "")).strip()
                        clean = re.sub(r"^\[\d+/\d+\]\s*", "", q_txt).strip().lower()
                        if clean:
                            used.add(clean)
                except Exception:
                    pass

    return used


# ---------------- Guruh Reytingi (Leaderboard) ---------------- #

async def record_group_answer(
    group_id: int,
    quiz_id: str,
    user_id: int,
    user_name: str,
    is_correct: bool,
) -> None:
    """Guruh a'zosining bergan javobini hisoblab borish."""
    now = time.time()
    inc_score = 1 if is_correct else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO group_scores (group_id, quiz_id, user_id, user_name, score, total_answered, last_active)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(group_id, quiz_id, user_id) DO UPDATE SET
                user_name = excluded.user_name,
                score = score + ?,
                total_answered = total_answered + 1,
                last_active = excluded.last_active
        """, (group_id, quiz_id, user_id, user_name, inc_score, now, inc_score))
        await db.commit()


async def get_group_leaderboard(group_id: int, quiz_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Guruhdagi eng yuqori natijali ishtirokchilar ro'yxatini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if quiz_id:
            query = """
                SELECT user_name, score, total_answered, last_active
                FROM group_scores
                WHERE group_id = ? AND quiz_id = ?
                ORDER BY score DESC, total_answered ASC, last_active ASC
                LIMIT ?
            """
            params = (group_id, quiz_id, limit)
        else:
            query = """
                SELECT user_name, SUM(score) as score, SUM(total_answered) as total_answered, MAX(last_active) as last_active
                FROM group_scores
                WHERE group_id = ?
                GROUP BY user_id
                ORDER BY score DESC, total_answered ASC
                LIMIT ?
            """
            params = (group_id, limit)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ---------------- Kanallarga Avtoposting (Schedules) ---------------- #

async def add_channel_schedule(
    user_id: int,
    channel_id: str,
    channel_title: str,
    topic: str,
    question_count: int = 3,
    interval_hours: int = 24,
) -> int:
    """Kanalga avtomatik test rejalashtirish."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO channel_schedules (user_id, channel_id, channel_title, topic, question_count, interval_hours, last_posted, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (user_id, channel_id, channel_title, topic, question_count, interval_hours, now))
        await db.commit()
        return cursor.lastrowid


async def get_due_channel_schedules() -> list[dict[str, Any]]:
    """Vaqti kelgan kanal posting vazifalarini olish."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM channel_schedules
            WHERE is_active = 1 AND (? - last_posted) >= (interval_hours * 3600)
        """, (now,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def update_channel_schedule_last_posted(schedule_id: int) -> None:
    """Oxirgi yuborilgan vaqtni yangilash."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE channel_schedules SET last_posted = ? WHERE id = ?",
            (now, schedule_id),
        )
        await db.commit()


async def get_user_channel_schedules(user_id: int) -> list[dict[str, Any]]:
    """Foydalanuvchining kanallarga rejalashtirilgan barcha vazifalari."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM channel_schedules WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def delete_channel_schedule(schedule_id: int, user_id: int) -> None:
    """Kanal avtoposting vazifasini o'chirish."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM channel_schedules WHERE id = ? AND user_id = ?",
            (schedule_id, user_id),
        )
        await db.commit()


# ---------------- Kundalik Streak (Olov) Tizimi ---------------- #

async def record_or_update_user_streak(user_id: int) -> tuple[int, int, bool]:
    """
    Foydalanuvchi kunlik test ishlaganda streak (ketma-ketlik)ni yangilash.
    Qaytaradi: (current_streak, longest_streak, is_new_today)
    """
    import datetime
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    now = time.time()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_streaks WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            # Yangi streak boshlanmoqda
            await db.execute("""
                INSERT INTO user_streaks (user_id, current_streak, longest_streak, last_active_date, last_quiz_time)
                VALUES (?, 1, 1, ?, ?)
            """, (user_id, today, now))
            await db.commit()
            return 1, 1, True

        last_date = row["last_active_date"]
        current = row["current_streak"]
        longest = row["longest_streak"]

        if last_date == today:
            # Bugun allaqachon bajargan
            return current, longest, False

        if last_date == yesterday:
            # Kecha ishlagan, ketma-ketlik davom etadi!
            new_current = current + 1
            new_longest = max(longest, new_current)
        else:
            # Zanjir uzilgan, qaytadan 1 dan boshlanadi
            new_current = 1
            new_longest = max(longest, 1)

        await db.execute("""
            UPDATE user_streaks
            SET current_streak = ?, longest_streak = ?, last_active_date = ?, last_quiz_time = ?
            WHERE user_id = ?
        """, (new_current, new_longest, today, now, user_id))
        await db.commit()
        return new_current, new_longest, True


async def get_user_streak(user_id: int) -> dict[str, Any]:
    """Foydalanuvchi streak ko'rsatkichlarini olish."""
    import datetime
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_streaks WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {"current": 0, "longest": 0, "active_today": False}

            last_date = row["last_active_date"]
            if last_date != today and last_date != yesterday:
                # Agar kecha ham kirmagan bo'lsa, current streak 0
                return {"current": 0, "longest": row["longest_streak"], "active_today": False}

            return {
                "current": row["current_streak"],
                "longest": row["longest_streak"],
                "active_today": (last_date == today),
            }


# ---------------- 1 vs 1 Do'stona Duel (Jang) ---------------- #

async def create_duel(
    duel_id: str,
    creator_id: int,
    creator_name: str,
    topic: str,
    questions: list[dict],
) -> None:
    """Yangi 1 vs 1 duel yaratish."""
    now = time.time()
    q_json = json.dumps(questions, ensure_ascii=False)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO duels (
                duel_id, creator_id, creator_name, topic, questions_json,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'waiting', ?)
        """, (duel_id, creator_id, creator_name, topic, q_json, now))
        await db.commit()


async def get_duel(duel_id: str) -> dict[str, Any] | None:
    """Duel ma'lumotlarini olish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM duels WHERE duel_id = ?", (duel_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["questions"] = json.loads(data["questions_json"])
            return data


async def join_duel(duel_id: str, opponent_id: int, opponent_name: str) -> bool:
    """Raqib sifatida duelga qo'shilish."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM duels WHERE duel_id = ?", (duel_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            if row["creator_id"] == opponent_id:
                return True  # O'zi boshlagan
            if row["opponent_id"] != 0 and row["opponent_id"] != opponent_id:
                return False  # Boshqa raqib allaqachon qo'shilgan

        await db.execute("""
            UPDATE duels
            SET opponent_id = ?, opponent_name = ?, status = 'in_progress'
            WHERE duel_id = ?
        """, (opponent_id, opponent_name, duel_id))
        await db.commit()
        return True


async def submit_duel_result(
    duel_id: str,
    user_id: int,
    score: int,
    time_spent: int,
) -> dict[str, Any] | None:
    """
    O'yinchi duelni yakunlaganda natijani yozish.
    Ikkala o'yinchi ham tugatgan bo'lsa, status = 'finished' qiladi va yakuniy natijani qaytaradi.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM duels WHERE duel_id = ?", (duel_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            duel = dict(row)

        is_creator = (user_id == duel["creator_id"])
        if is_creator:
            await db.execute("""
                UPDATE duels
                SET creator_score = ?, creator_time = ?, creator_finished = 1
                WHERE duel_id = ?
            """, (score, time_spent, duel_id))
        else:
            await db.execute("""
                UPDATE duels
                SET opponent_score = ?, opponent_time = ?, opponent_finished = 1
                WHERE duel_id = ?
            """, (score, time_spent, duel_id))

        await db.commit()

        # Yangilangan holatni olish
        async with db.execute("SELECT * FROM duels WHERE duel_id = ?", (duel_id,)) as cursor:
            updated_row = await cursor.fetchone()
            updated_duel = dict(updated_row)

        c_fin = updated_duel["creator_finished"]
        o_fin = updated_duel["opponent_finished"]

        if c_fin and o_fin:
            await db.execute("UPDATE duels SET status = 'finished' WHERE duel_id = ?", (duel_id,))
            await db.commit()
            updated_duel["status"] = "finished"

        return updated_duel


async def get_group_quiz_results_for_excel(group_id: int, quiz_id: str | None = None) -> list[dict[str, Any]]:
    """Guruhdagi test natijalarini Excel eksporti uchun olish."""
    return await get_group_leaderboard(group_id, quiz_id=quiz_id, limit=50)


async def update_quiz_timer(quiz_id: str, new_timer: int) -> bool:
    """Mavjud testning taymerini (soniyasini) yangilash."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE quizzes SET timer_seconds = ? WHERE quiz_id = ?", (new_timer, quiz_id))
        await db.commit()
        return True



