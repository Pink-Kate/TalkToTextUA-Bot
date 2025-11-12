"""Завантаження аудіо з Telegram та транскрипція Whisper."""
from __future__ import annotations

import os
import asyncio
import logging
import tempfile

from utils import load_whisper_model
from storage import get_user_settings
from config import TRANSCRIPTION_TIMEOUT

logger = logging.getLogger(__name__)


async def download_audio_file(bot, file_id: str) -> str:
    file = await bot.get_file(file_id)
    logger.info("Отримано файл: %s (%s байт)", file.file_path, file.file_size)

    extension = file.file_path.split(".")[-1] if "." in file.file_path else "ogg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}")
    tmp_path = tmp.name
    tmp.close()

    await file.download_to_drive(tmp_path)

    if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
        raise FileNotFoundError(f"Файл не завантажено або порожній: {tmp_path}")
    return tmp_path


async def transcribe_audio(audio_path: str, user_id: int | None = None):
    model = await load_whisper_model()
    if model is None:
        return None, "Не вдалося завантажити модель Whisper", None

    if not os.path.exists(audio_path):
        return None, f"Файл не знайдено: {audio_path}", None

    settings = get_user_settings(user_id) if user_id else {"language": None, "mode": "balanced"}
    target_lang = settings.get("language")
    mode = settings.get("mode", "balanced")

    logger.info("Починаємо розпізнавання %s (mode=%s)", audio_path, mode)

    loop = asyncio.get_event_loop()

    if mode == "fast":
        best_of, beam_size, temperature = 1, 3, 0.2
    elif mode == "accurate":
        best_of, beam_size, temperature = 5, 10, 0.0
    else:
        best_of, beam_size, temperature = 2, 5, 0.0

    def run():
        prompts = {
            "uk": "Це український текст. Використовуй українську мову.",
            "en": "This is English text.",
            "pl": "To jest język polski.",
            "de": "Das ist deutscher Text.",
            "ru": "Это русский текст.",
        }

        if target_lang:
            prompt = prompts.get(target_lang, "")
            try:
                return model.transcribe(
                    audio_path,
                    language=target_lang,
                    fp16=False,
                    initial_prompt=prompt or None,
                    temperature=temperature,
                    best_of=best_of,
                    beam_size=beam_size,
                )
            except Exception:  # noqa: BLE001
                pass

        return model.transcribe(
            audio_path,
            language=None,
            fp16=False,
            initial_prompt="Це може бути українська, англійська, польська, німецька або інша мова.",
            temperature=temperature,
            best_of=best_of,
            beam_size=beam_size,
        )

    try:
        result = await asyncio.wait_for(loop.run_in_executor(None, run), timeout=TRANSCRIPTION_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error("Транскрипція перевищила таймаут %s секунд", TRANSCRIPTION_TIMEOUT)
        return None, f"Транскрипція зайняла більше {TRANSCRIPTION_TIMEOUT // 60} хвилин. Спробуйте коротший аудіофайл.", None
    except Exception as exc:
        logger.error("Помилка під час транскрипції: %s", exc, exc_info=True)
        return None, f"Помилка обробки: {str(exc)[:100]}", None
    
    if result is None:
        return None, "Не вдалося розпізнати аудіо", None

    text = result["text"].strip()
    language = result.get("language", "невідома")

    segments = result.get("segments", [])
    avg_logprob = None
    if segments:
        logs = [seg.get("avg_logprob", -1.0) for seg in segments if "avg_logprob" in seg]
        if logs:
            avg_logprob = sum(logs) / len(logs)

    quality_info = {"avg_logprob": avg_logprob, "no_speech_prob": result.get("no_speech_prob", 0.0)}
    logger.info("Розпізнавання завершено. language=%s, len(text)=%s", language, len(text))
    return text, language, quality_info



