"""Конфігурація бота."""
import os

# Завантажуємо змінні середовища з `.env`, якщо файл існує
try:
    from dotenv import load_dotenv
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _DOTENV_PATH = os.path.join(_BASE_DIR, ".env")
    if os.path.exists(_DOTENV_PATH):
        load_dotenv(dotenv_path=_DOTENV_PATH)
except (ImportError, Exception):
    # Якщо python-dotenv не встановлений або виникла помилка, продовжуємо без нього
    pass

# Telegram Bot token
# На Railway BOT_TOKEN має бути встановлено як змінна середовища
BOT_TOKEN = os.getenv("BOT_TOKEN") or None

# Whisper model preferences (порядок спроб завантаження)
# Оптимізовано для швидкості: спочатку менші моделі для швидкої обробки
# "base" - найшвидша, "small" - швидка з хорошою якістю, "medium" - найкраща якість
WHISPER_MODELS = ["base", "small", "medium"]

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Business limits
MAX_AUDIO_DURATION = 600  # seconds (10 minutes)
MAX_HISTORY_ENTRIES = 100
TRANSCRIPTION_TIMEOUT = 900  # seconds (15 minutes)



