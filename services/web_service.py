import logging
import re
import aiohttp
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)


def extract_youtube_video_id(url: str) -> str | None:
    """YouTube video ID sini havoladan ajratib olish."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"youtube\.com\/shorts\/([0-9A-Za-z_-]{11})",
        r"youtube\.com\/embed\/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def get_youtube_transcript_text(url: str) -> tuple[str | None, str]:
    """
    YouTube video subtitrlarini matn ko'rinishida olish.
    Qaytaradi: (transcript_text, title_or_source)
    """
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return None, "YouTube video"

    try:
        # Transcriptlarni qidirish (o'zbek, rus, ingliz yoki avtomatik)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        for lang in ["uz", "ru", "en"]:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except Exception:
                continue

        if not transcript:
            try:
                # Topilmasa, avtomatik yaratilganini olish
                transcript = transcript_list.find_generated_transcript(["uz", "ru", "en"])
            except Exception:
                # Ixtiyoriy birinchi subtitrni olish
                for t in transcript_list:
                    transcript = t
                    break

        if transcript:
            data = transcript.fetch()
            full_text = " ".join(item.get("text", "") for item in data)
            full_text = re.sub(r"\s+", " ", full_text).strip()
            return full_text, f"YouTube Video ({video_id})"
    except Exception as e:
        logger.warning("YouTube subtitr olishda xatolik (%s): %s", video_id, e)

    return None, f"YouTube Video ({video_id})"


async def fetch_web_page_text(url: str) -> tuple[str | None, str]:
    """
    Ixtiyoriy veb-sahifa yoki maqoladan asosiy matnni ajratib olish.
    Qaytaradi: (clean_text, title)
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    return None, "Veb sahifa"

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                # Keraksiz teglarni olib tashlash
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
                    tag.decompose()

                title = soup.title.string.strip() if soup.title and soup.title.string else "Veb sahifa"
                title = re.sub(r"\s+", " ", title)[:40]

                # Asosiy matnni olish: avval <article>, topilmasa <p> teglari
                article = soup.find("article") or soup.find("main")
                if article:
                    paragraphs = article.find_all("p")
                else:
                    paragraphs = soup.find_all("p")

                text_parts = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 25]
                clean_text = "\n\n".join(text_parts)

                if len(clean_text) < 100:
                    # Agar <p> larda kam bo'lsa, butun body matnini olish
                    body_text = soup.get_text()
                    clean_text = re.sub(r"\n\s*\n+", "\n\n", body_text).strip()

                return clean_text[:40000], title
    except Exception as e:
        logger.warning("Veb sahifani yuklashda xatolik (%s): %s", url, e)
        return None, "Veb sahifa"
