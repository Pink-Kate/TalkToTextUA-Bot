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
BOT_TOKEN = os.getenv("BOT_TOKEN") or None

# Перевірка буде виконана в bot_runner.py при запуску, щоб не блокувати імпорт

# Whisper model preferences (порядок спроб завантаження)
# Оптимізовано для швидкості: спочатку менші моделі для швидкої обробки
# "base" - найшвидша, "small" - швидка з хорошою якістю, "medium" - найкраща якість
WHISPER_MODELS = ["base", "small", "medium"]

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Business limits
MAX_AUDIO_DURATION = 600  # seconds (10 minutes)
MAX_HISTORY_ENTRIES = 100
TRANSCRIPTION_TIMEOUT = 900  # seconds (15 minutes) - максимальний час на транскрипцію для довгих файлів



