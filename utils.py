"""Утиліти для бота: клавіатури, завантаження Whisper, тощо."""
from __future__ import annotations

import asyncio
import logging

import whisper
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import WHISPER_MODELS

logger = logging.getLogger(__name__)

whisper_model = None
_model_lock: asyncio.Lock | None = None


async def _ensure_lock() -> asyncio.Lock:
    global _model_lock
    if _model_lock is None:
        _model_lock = asyncio.Lock()
    return _model_lock


async def load_whisper_model():
    """Ледаче завантаження Whisper; повертає модель або None."""
    global whisper_model
    if whisper_model is not None:
        return whisper_model

    lock = await _ensure_lock()
    async with lock:
        if whisper_model is not None:
            return whisper_model

        logger.info("🔄 Початок завантаження моделі Whisper...")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        def load_sync():
            for name in WHISPER_MODELS:
                try:
                    logger.info("📥 Завантажую модель %s", name)
                    return whisper.load_model(name)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("⚠️ Не вдалося завантажити %s: %s", name, exc)
            return None

        whisper_model = await loop.run_in_executor(None, load_sync)

        if whisper_model is None:
            logger.error("❌ Жодну модель Whisper не завантажено.")
        else:
            logger.info("🎉 Whisper готова до використання.")
    return whisper_model


def create_language_keyboard(current_lang: str | None = None) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                "✓ Авто" if current_lang is None else "Авто",
                callback_data="lang_auto",
            ),
            InlineKeyboardButton(
                "✓ Українська" if current_lang == "uk" else "Українська",
                callback_data="lang_uk",
            ),
            InlineKeyboardButton(
                "✓ English" if current_lang == "en" else "English",
                callback_data="lang_en",
            ),
        ],
        [
            InlineKeyboardButton(
                "✓ Polski" if current_lang == "pl" else "Polski",
                callback_data="lang_pl",
            ),
            InlineKeyboardButton(
                "✓ Deutsch" if current_lang == "de" else "Deutsch",
                callback_data="lang_de",
            ),
            InlineKeyboardButton(
                "✓ Русский" if current_lang == "ru" else "Русский",
                callback_data="lang_ru",
            ),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def create_start_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("Авто", callback_data="lang_auto"),
            InlineKeyboardButton("Українська", callback_data="lang_uk"),
            InlineKeyboardButton("English", callback_data="lang_en"),
        ],
        [InlineKeyboardButton("Експорт .txt", callback_data="export_txt")],
    ]
    return InlineKeyboardMarkup(buttons)


def create_result_keyboard(_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Експорт .txt", callback_data="export_txt")]])




