import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env", override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.5-flash").strip()

# Cloud zaxiralash sozlamalari (Render restartlarida bazani saqlash uchun)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_DATA_REPO = os.getenv("GITHUB_DATA_REPO", "eshpolatovozod7-art/quiz-bot-data").strip()

# Ma'lumotlar saqlanadigan kataloglar
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "quiz_bot.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
