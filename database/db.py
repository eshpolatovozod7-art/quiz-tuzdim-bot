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
