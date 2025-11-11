"""Конфігурація бота.

Розміщена в корені, щоб код коректно працював як зі старою структурою `bot_app`,
так і з плоским набором файлів (Railway, локальний запуск, тощо).
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

# Завантажуємо змінні середовища з `.env`, що лежить поруч із цим файлом
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=DOTENV_PATH)

# Telegram Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не встановлено. Додайте його у .env або в змінні середовища.")

# Whisper model preferences (порядок спроб завантаження)
WHISPER_MODELS = ["medium", "small", "base"]

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Business limits
MAX_AUDIO_DURATION = 600  # seconds (10 minutes)
MAX_HISTORY_ENTRIES = 100


