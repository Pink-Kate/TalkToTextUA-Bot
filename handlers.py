"""Основні обробники команд та повідомлень."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from config import MAX_AUDIO_DURATION
from storage import add_to_history, clear_chat_history, get_chat_history, get_user_settings
from transcription import download_audio_file, transcribe_audio
from utils import (
    create_language_keyboard,
    create_mode_keyboard,
    create_result_keyboard,
    create_start_keyboard,
    load_whisper_model,
)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_type = update.message.chat.type

    if chat_type == "private":
        message = (
            "Привіт! Я перетворюю голосові у текст 🎙️\n\n"
            "Надішли голосове або аудіофайл — я розшифрую його за секунди.\n\n"
            "Корисне:\n"
            "• /lang — обрати мову розпізнавання\n"
            "• /mode — вибрати режим (точність/швидкість)\n"
            "• /export — експортувати останній результат"
        )
        await update.message.reply_text(message, reply_markup=create_start_keyboard())
    else:
        message = (
            "Привіт! Я перетворюю голосові у текст 🎙️\n\n"
            "У цій групі автоматично розпізнаю голосові повідомлення та аудіофайли."
        )
        await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Як працює:\n\n"
        "1. Надішли голосове повідомлення або аудіофайл\n"
        "2. Отримай текст за секунду\n\n"
        "Підтримувані формати: голосові, .ogg, .mp3, .wav\n"
        "Команди:\n"
        "/lang — вибір мови\n"
        "/mode — режим роботи\n"
        "/export — останній транскрипт у .txt\n"
        "/clear — очистити історію\n"
        "/privacy — приватність"
    )
    await update.message.reply_text(text)


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id if update.message.from_user else None
    if user_id is None:
        await update.message.reply_text("Не вдалося визначити користувача.")
        return

    settings = get_user_settings(user_id)
    await update.message.reply_text(
        "🌐 Оберіть мову розпізнавання:",
        reply_markup=create_language_keyboard(settings.get("language")),
    )


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id if update.message.from_user else None
    if user_id is None:
        await update.message.reply_text("Не вдалося визначити користувача.")
        return

    settings = get_user_settings(user_id)
    current_mode = settings.get("mode", "balanced")

    if context.args:
        mode = context.args[0].lower()
        if mode in {"fast", "balanced", "accurate"}:
            settings["mode"] = mode
            descriptions = {
                "fast": "легка модель, швидко, але можливі неточності",
                "balanced": "збалансований режим (за замовчуванням)",
                "accurate": "велика модель, повільніше, але найкраща якість",
            }
            await update.message.reply_text(
                f"Режим встановлено: {mode}\n{descriptions[mode]}",
                reply_markup=create_mode_keyboard(mode),
            )
            return

    descriptions = {
        "fast": "легка модель, швидко, але можливі неточності",
        "balanced": "збалансований режим (за замовчуванням)",
        "accurate": "велика модель, повільніше, але найкраща якість",
    }
    await update.message.reply_text(
        f"Поточний режим: {current_mode}\n{descriptions.get(current_mode, '')}\n\n"
        "Оберіть новий режим:",
        reply_markup=create_mode_keyboard(current_mode),
    )


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat.id
    history = get_chat_history(chat_id)
    if not history:
        await update.message.reply_text("Історія порожня.")
        return

    last_entry = history[-1]
    text = last_entry.get("text", "")
    if not text:
        await update.message.reply_text("Останній транскрипт порожній.")
        return

    timestamp = last_entry.get("timestamp", "")
    language = last_entry.get("language", "невідома")
    user_id_entry = last_entry.get("user_id")

    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
    if update.message.chat.type != "private" and user_id_entry:
        tmp.write(f"[{timestamp}] [{language}] User ID: {user_id_entry}\n{text}\n")
    else:
        tmp.write(f"[{timestamp}] [{language}]\n{text}\n")
    tmp.close()

    try:
        with open(tmp.name, "rb") as fh:
            await update.message.reply_document(
                document=fh,
                filename="transcription.txt",
                caption="Останній транскрипт",
            )
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat.id
    clear_chat_history(chat_id)
    await update.message.reply_text("Історію очищено.")


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🔒 Приватність\n\n"
        "• Аудіо видаляються після транскрибування\n"
        "• Історія зберігається в пам'яті для поточного сеансу\n"
        "• Командою /clear можна стерти історію"
    )
    await update.message.reply_text(text)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_type = update.message.chat.type
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id if update.message.from_user else None

    processing = await update.message.reply_text("🎤 Обробляю...")

    try:
        if update.message.voice:
            file_id = update.message.voice.file_id
            duration = update.message.voice.duration
        elif update.message.audio:
            file_id = update.message.audio.file_id
            duration = update.message.audio.duration
        elif update.message.document and (update.message.document.mime_type or "").startswith("audio/"):
            file_id = update.message.document.file_id
            duration = None
        else:
            await processing.edit_text("Не вдалося знайти аудіо у повідомленні.")
            return

        if duration and duration > MAX_AUDIO_DURATION:
            minutes = MAX_AUDIO_DURATION // 60
            await processing.edit_text(f"⏳ Аудіо довше {minutes} хвилин. Поділіть на частини.")
            return

        path = await download_audio_file(context.bot, file_id)

        try:
            if await load_whisper_model() is None:
                await processing.edit_text("Завантаження моделі Whisper... зачекайте.")

            # Для довгих файлів оновлюємо повідомлення
            if duration and duration > 60:
                async def update_long_processing():
                    await asyncio.sleep(30)  # Через 30 секунд
                    try:
                        await processing.edit_text("🎤 Обробляю довгий файл... це може зайняти кілька хвилин ⏳")
                    except Exception:  # noqa: BLE001
                        pass
                
                asyncio.create_task(update_long_processing())

            text, language, quality = await transcribe_audio(path, user_id=user_id)
            if not text:
                await processing.edit_text(f"Не вдалося розпізнати аудіо.\n{language}")
                return

            add_to_history(chat_id, user_id, text, language)

            low_quality = False
            if quality:
                avg_logprob = quality.get("avg_logprob")
                no_speech = quality.get("no_speech_prob", 0.0)
                if (avg_logprob is not None and avg_logprob < -0.8) or no_speech > 0.5:
                    low_quality = True

            reply_text = "🗣️ Готово! Ось текст:\n" + text
            if low_quality:
                reply_text = (
                    "⚠️ Запис був шумним або тихим. Постарайся записати чистіше.\n\n" + reply_text
                )

            if chat_type != "private" and update.message.from_user:
                user_name = update.message.from_user.first_name or ""
                if update.message.from_user.last_name:
                    user_name += f" {update.message.from_user.last_name}"
                reply_text = f"{user_name}:\n\n{reply_text}"

            keyboard = None
            if chat_type == "private" and user_id:
                keyboard = create_result_keyboard(user_id)

            await processing.edit_text(reply_text, reply_markup=keyboard)
        finally:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as exc:
                    logger.warning("Не вдалося видалити тимчасовий файл %s: %s", path, exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Помилка під час обробки аудіо: %s", exc, exc_info=True)
        try:
            await processing.edit_text("❌ Виникла помилка. Спробуйте ще раз.")
        except Exception:  # noqa: BLE001
            pass


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_type = update.message.chat.type
    if chat_type != "private":
        if update.message.text:
            bot_username = context.bot.username
            if bot_username and f"@{bot_username}" not in update.message.text:
                return
    await update.message.reply_text(
        "Надішли голосове повідомлення або аудіо — я перетворю його в текст."
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    settings = get_user_settings(user_id)

    if data.startswith("lang_"):
        lang_code = data.split("_", 1)[1]
        lang_map = {
            "auto": ("🌐", "автоматичне визначення", None),
            "uk": ("🇺🇦", "українська", "uk"),
            "en": ("🇬🇧", "English", "en"),
            "pl": ("🇵🇱", "Polski", "pl"),
            "de": ("🇩🇪", "Deutsch", "de"),
            "ru": ("🇷🇺", "Русский", "ru"),
        }

        emoji, label, value = lang_map.get(lang_code, ("🌐", lang_code, lang_code))
        settings["language"] = value

        await query.edit_message_text(
            f"{emoji} Мову розпізнавання встановлено: {label}.\n\n"
            "🌐 Оберіть мову розпізнавання:",
            reply_markup=create_language_keyboard(settings.get("language")),
        )

    elif data.startswith("mode_"):
        mode_code = data.split("_", 1)[1]
        settings["mode"] = mode_code

        names = {
            "fast": "Швидкість",
            "balanced": "Збалансований",
            "accurate": "Точність",
        }
        descriptions = {
            "fast": "легка модель, швидко, але можливі неточності",
            "balanced": "збалансований режим (за замовчуванням)",
            "accurate": "велика модель, повільніше, але найкраща якість",
        }
        await query.edit_message_text(
            f"Режим встановлено: {names.get(mode_code, mode_code)}\n\n{descriptions.get(mode_code, '')}\n\n"
            "Оберіть новий режим:",
            reply_markup=create_mode_keyboard(mode_code),
        )

    elif data == "export_txt":
        chat_id = query.message.chat.id
        history = get_chat_history(chat_id)
        if not history:
            await query.answer("Історія порожня.", show_alert=True)
            return

        last_entry = history[-1]
        text = last_entry.get("text", "")
        if not text:
            await query.answer("Останній транскрипт порожній.", show_alert=True)
            return

        timestamp = last_entry.get("timestamp", "")
        language = last_entry.get("language", "невідома")
        user_id_entry = last_entry.get("user_id")

        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
        if query.message.chat.type != "private" and user_id_entry:
            tmp.write(f"[{timestamp}] [{language}] User ID: {user_id_entry}\n{text}\n")
        else:
            tmp.write(f"[{timestamp}] [{language}]\n{text}\n")
        tmp.close()

        try:
            with open(tmp.name, "rb") as fh:
                await query.message.reply_document(
                    document=fh,
                    filename="transcription.txt",
                    caption="Останній транскрипт.",
                )
            await query.answer("Файл відправлено!")
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)



