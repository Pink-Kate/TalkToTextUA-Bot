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

# Семафор для обмеження кількості одночасних транскрипцій
# Дозволяє 2 паралельні транскрипції (Whisper не є thread-safe, але через executor це працює)
_transcription_semaphore: asyncio.Semaphore | None = None
_semaphore_lock: asyncio.Lock | None = None


async def _get_transcription_semaphore() -> asyncio.Semaphore:
    """Отримує або створює семафор для обмеження паралельних транскрипцій."""
    global _transcription_semaphore, _semaphore_lock
    if _transcription_semaphore is None:
        if _semaphore_lock is None:
            _semaphore_lock = asyncio.Lock()
        async with _semaphore_lock:
            if _transcription_semaphore is None:
                # Дозволяємо 2 одночасні транскрипції для кращої продуктивності
                # Можна збільшити до 3-4, якщо сервер має достатньо ресурсів
                _transcription_semaphore = asyncio.Semaphore(2)
                logger.info("🔒 Створено семафор для транскрипцій (макс. 2 одночасно)")
    return _transcription_semaphore


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


async def transcribe_audio(audio_path: str, user_id: int | None = None, audio_duration: int | None = None):
    import time
    start_time = time.time()
    
    logger.info("🔍 Початок транскрипції: %s", audio_path)
    
    model = await load_whisper_model()
    if model is None:
        logger.error("❌ Модель Whisper не завантажена")
        return None, "Не вдалося завантажити модель Whisper", None

    if not os.path.exists(audio_path):
        logger.error("❌ Файл не знайдено: %s", audio_path)
        return None, f"Файл не знайдено: {audio_path}", None

    file_size = os.path.getsize(audio_path)
    logger.info("📊 Розмір файлу: %s байт (%.2f МБ)", file_size, file_size / (1024 * 1024))

    # Використовуємо синхронну версію, оскільки це викликається з async контексту
    # але get_user_settings тепер thread-safe
    settings = get_user_settings(user_id) if user_id else {"language": None, "mode": "balanced"}
    target_lang = settings.get("language")
    mode = settings.get("mode", "balanced")

    logger.info("⚙️ Параметри: mode=%s, language=%s", mode, target_lang or "auto")
    
    # Динамічний таймаут на основі тривалості аудіо
    # Для коротких файлів (до 2 хв) - 5 хв, для середніх (2-5 хв) - 10 хв, для довгих - 15 хв
    if audio_duration:
        if audio_duration <= 120:  # до 2 хвилин
            timeout = 300  # 5 хвилин
        elif audio_duration <= 300:  # до 5 хвилин
            timeout = 600  # 10 хвилин
        else:
            timeout = TRANSCRIPTION_TIMEOUT  # 15 хвилин
        logger.info("⏱️ Динамічний таймаут: %s сек (тривалість аудіо: %s сек)", timeout, audio_duration)
    else:
        timeout = TRANSCRIPTION_TIMEOUT
        logger.info("⏱️ Використовую стандартний таймаут: %s сек", timeout)

    loop = asyncio.get_event_loop()

    # Оптимізація параметрів для коротших файлів
    if audio_duration and audio_duration <= 120:  # до 2 хвилин
        # Для коротких файлів використовуємо більш швидкі параметри
        if mode == "fast":
            best_of, beam_size, temperature = 1, 2, 0.2
        elif mode == "accurate":
            best_of, beam_size, temperature = 3, 5, 0.0
        else:
            best_of, beam_size, temperature = 1, 3, 0.0
    else:
        # Для довгих файлів використовуємо стандартні параметри
        if mode == "fast":
            best_of, beam_size, temperature = 1, 3, 0.2
        elif mode == "accurate":
            best_of, beam_size, temperature = 5, 10, 0.0
        else:
            best_of, beam_size, temperature = 2, 5, 0.0

    logger.info("🔧 Whisper параметри: best_of=%s, beam_size=%s, temperature=%s", best_of, beam_size, temperature)

    def run():
        logger.info("▶️ Запуск Whisper.transcribe()...")
        transcribe_start = time.time()
        
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
                logger.info("🌐 Використовую мову: %s", target_lang)
                result = model.transcribe(
                    audio_path,
                    language=target_lang,
                    fp16=False,
                    initial_prompt=prompt or None,
                    temperature=temperature,
                    best_of=best_of,
                    beam_size=beam_size,
                )
                elapsed = time.time() - transcribe_start
                logger.info("✅ Whisper завершив транскрипцію за %.2f секунд", elapsed)
                return result
            except Exception as exc:  # noqa: BLE001
                logger.warning("⚠️ Помилка з мовою %s: %s, спробую auto", target_lang, exc)
                pass

        logger.info("🌐 Використовую автоматичне визначення мови")
        result = model.transcribe(
            audio_path,
            language=None,
            fp16=False,
            initial_prompt="Це може бути українська, англійська, польська, німецька або інша мова.",
            temperature=temperature,
            best_of=best_of,
            beam_size=beam_size,
        )
        elapsed = time.time() - transcribe_start
        logger.info("✅ Whisper завершив транскрипцію за %.2f секунд", elapsed)
        return result

    try:
        # Отримуємо доступ до семафора для паралельної обробки
        semaphore = await _get_transcription_semaphore()
        logger.info("🔒 Очікую дозвіл на транскрипцію...")
        
        async with semaphore:
            logger.info("✅ Отримано дозвіл, починаю транскрипцію")
            logger.info("⏱️ Початок очікування транскрипції (таймаут: %s сек)", timeout)
            result = await asyncio.wait_for(loop.run_in_executor(None, run), timeout=timeout)
            total_elapsed = time.time() - start_time
            logger.info("⏱️ Загальний час транскрипції: %.2f секунд (%.2f хвилин)", total_elapsed, total_elapsed / 60)
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        logger.error("⏰ Транскрипція перевищила таймаут %s секунд (працювала %.2f сек)", timeout, elapsed)
        return None, f"Транскрипція зайняла більше {timeout // 60} хвилин. Спробуйте коротший аудіофайл або режим 'Швидкість'.", None
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error("❌ Помилка під час транскрипції (через %.2f сек): %s", elapsed, exc, exc_info=True)
        return None, f"Помилка обробки: {str(exc)[:100]}", None
    
    if result is None:
        logger.error("❌ Whisper повернув None")
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
    logger.info("✅ Розпізнавання завершено. language=%s, len(text)=%s, segments=%s", language, len(text), len(segments))
    return text, language, quality_info



