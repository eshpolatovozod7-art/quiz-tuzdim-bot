import asyncio
import base64
import logging
import os
from pathlib import Path
from typing import Any
import aiohttp

from config import DB_PATH, GITHUB_TOKEN, GITHUB_DATA_REPO

logger = logging.getLogger(__name__)

_is_dirty = False
_sync_lock = asyncio.Lock()


def mark_db_dirty() -> None:
    """Ma'lumotlar bazasida o'zgarish bo'lganini belgilash."""
    global _is_dirty
    _is_dirty = True


def _get_headers() -> dict[str, str]:
    headers = {
        "User-Agent": "Quiz-Tuzdim-Bot-CloudSync",
        "Accept": "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


async def download_cloud_db() -> bool:
    """
    Render yoki yangi server ishga tushganda GitHub private omboridan
    oxirgi quiz_bot.db ma'lumotlar bazasini yuklab olish (restore).
    """
    if not GITHUB_TOKEN or not GITHUB_DATA_REPO:
        logger.info("Cloud Sync: GITHUB_TOKEN yoki GITHUB_DATA_REPO berilmagan, lokal SQLite ishlatiladi.")
        return False

    url = f"https://api.github.com/repos/{GITHUB_DATA_REPO}/contents/quiz_bot.db"
    headers = _get_headers()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content_b64 = data.get("content", "")
                    if not content_b64:
                        logger.warning("Cloud Sync: Ombor faylida ma'lumot yo'q.")
                        return False

                    # Base64 qatorlarida yangi qator (\n) belgilari bo'lishi mumkin
                    db_bytes = base64.b64decode(content_b64.replace("\n", ""))
                    
                    # Agar lokal baza mavjud bo'lsa va uning hajmi kattaroq bo'lsa, ehtiyotkorlik tekshiruvi
                    if DB_PATH.exists() and DB_PATH.stat().st_size > len(db_bytes) and DB_PATH.stat().st_size > 50000:
                        logger.info("Cloud Sync: Lokal baza hajmi kattaroq (%d > %d), lokal saqlanadi.",
                                    DB_PATH.stat().st_size, len(db_bytes))
                        return True

                    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                    # Atomik saqlash (temp fayl orqali)
                    tmp_path = DB_PATH.with_suffix(".tmp")
                    tmp_path.write_bytes(db_bytes)
                    tmp_path.replace(DB_PATH)

                    logger.info("✅ Cloud bazadan %d bayt ma'lumot muvaffaqiyatli tiklandi: %s", len(db_bytes), DB_PATH)
                    return True
                elif resp.status == 404:
                    logger.info("Cloud Sync: Omborida hali quiz_bot.db mavjud emas, noldan boshlanadi.")
                    return False
                else:
                    err_txt = await resp.text()
                    logger.warning("Cloud Sync yuklab olishda kutilmagan javob (%d): %s", resp.status, err_txt[:150])
                    return False
    except Exception as e:
        logger.error("Cloud Sync yuklab olishda xatolik: %s", e)
        return False


async def upload_cloud_db(commit_message: str = "Auto-sync database update [skip ci]") -> bool:
    """
    Lokal quiz_bot.db faylini GitHub private omboriga xavfsiz yuklash (backup).
    """
    if not GITHUB_TOKEN or not GITHUB_DATA_REPO:
        return False

    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return False

    async with _sync_lock:
        global _is_dirty
        url = f"https://api.github.com/repos/{GITHUB_DATA_REPO}/contents/quiz_bot.db"
        headers = _get_headers()

        try:
            content_bytes = DB_PATH.read_bytes()
            content_b64 = base64.b64encode(content_bytes).decode("utf-8")

            async with aiohttp.ClientSession() as session:
                # 1. Mavjud faylning SHA qiymatini olish
                sha = None
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as get_resp:
                    if get_resp.status == 200:
                        existing = await get_resp.json()
                        sha = existing.get("sha")

                # 2. Yangi kontentni PUT orqali yuklash
                payload: dict[str, Any] = {
                    "message": commit_message,
                    "content": content_b64,
                }
                if sha:
                    payload["sha"] = sha

                async with session.put(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as put_resp:
                    if put_resp.status in (200, 201):
                        res = await put_resp.json()
                        new_sha = res.get("commit", {}).get("sha", "unknown")[:7]
                        logger.info("✅ Cloud bazaga yangilanish saqlandi! (Hajm: %d bayt, SHA: %s)", len(content_bytes), new_sha)
                        _is_dirty = False
                        return True
                    else:
                        err_txt = await put_resp.text()
                        logger.warning("Cloud Sync saqlashda xatolik (%d): %s", put_resp.status, err_txt[:150])
                        return False
        except Exception as e:
            logger.error("Cloud Sync saqlashda istisno: %s", e)
            return False


def trigger_cloud_sync_background() -> None:
    """Yangi test tuzilganda fonda darhol sinxronlashni ishga tushirish."""
    mark_db_dirty()
    try:
        asyncio.create_task(upload_cloud_db("Auto-sync: yangi test yaratildi [skip ci]"))
    except RuntimeError:
        pass


async def cloud_sync_worker(interval_seconds: int = 180) -> None:
    """
    Orqa fonda har 3 daqiqada yangi natijalar yoki o'zgarishlar bo'lsa,
    avtomatik ravishda cloud omborga yuklab boruvchi xizmatchi.
    """
    logger.info("Cloud Sync xizmatchisi ishga tushdi (interval: %d soniya).", interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            global _is_dirty
            if _is_dirty:
                logger.debug("Cloud Sync: o'zgarishlar aniqlandi, omborga sinxronlanmoqda...")
                await upload_cloud_db("Auto-sync: natijalar va yangilanishlar [skip ci]")
        except asyncio.CancelledError:
            logger.info("Cloud Sync to'xtatildi, oxirgi holat saqlanmoqda...")
            if _is_dirty:
                try:
                    await upload_cloud_db("Final sync before shutdown [skip ci]")
                except Exception:
                    pass
            break
        except Exception as e:
            logger.warning("Cloud Sync siklida ogohlantirish: %s", e)
