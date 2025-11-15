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
# Оптимізовано для балансу швидкості та якості
# "turbo" - швидка і точна модель (оптимальний вибір)
# "medium" - хороший баланс швидкості/якості (резервна)
# "small" та "base" - швидкі резервні
# "large-v3" - найточніша, але повільна (остання резервна)
WHISPER_MODELS = ["turbo", "medium", "small", "base", "large-v3"]

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Admin user ID або username (для команди /stats)
# Можна використовувати або ADMIN_USER_ID, або ADMIN_USERNAME
# ADMIN_USER_ID - надійніше (отримати через @userinfobot або @getidsbot)
# ADMIN_USERNAME - зручніше (без @, наприклад: Professional012)
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
if ADMIN_USER_ID:
    try:
        ADMIN_USER_ID = int(ADMIN_USER_ID)
    except ValueError:
        ADMIN_USER_ID = None

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
if ADMIN_USERNAME:
    # Видаляємо @ з початку, якщо є
    ADMIN_USERNAME = ADMIN_USERNAME.lstrip("@").lower()

# Business limits
MAX_AUDIO_DURATION = 600  # seconds (10 minutes)
MAX_HISTORY_ENTRIES = 100
TRANSCRIPTION_TIMEOUT = 900  # seconds (15 minutes)



