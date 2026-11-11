import io
import logging
import edge_tts

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en-US-JennyNeural"
UK_VOICE = "en-GB-SoniaNeural"
US_MALE_VOICE = "en-US-ChristopherNeural"


async def generate_audio_bytes(text: str, voice: str = DEFAULT_VOICE) -> bytes | None:
    """
    Edge-TTS orqali berilgan matnni yuqori sifatli MP3 audio baytlariga aylantirish.
    """
    clean_text = text.strip()
    if not clean_text:
        return None

    try:
        communicate = edge_tts.Communicate(clean_text, voice=voice)
        audio_stream = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])
        return audio_stream.getvalue()
    except Exception as e:
        logger.warning("TTS audio generatsiyasida xatolik: %s", e)
        return None
