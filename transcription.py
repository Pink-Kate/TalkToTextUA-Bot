"""Завантаження аудіо з Telegram та транскрипція Whisper."""
from __future__ import annotations

import os
import asyncio
import logging
import tempfile
import threading

from utils import load_whisper_model
from storage import get_user_settings
from config import TRANSCRIPTION_TIMEOUT

logger = logging.getLogger(__name__)

# Семафор для обмеження кількості одночасних транскрипцій
# Whisper не є thread-safe і має проблеми з KV cache при паралельному використанні
# Тому використовуємо тільки 1 паралельну транскрипцію для уникнення помилок
_transcription_semaphore: asyncio.Semaphore | None = None
_semaphore_lock: asyncio.Lock | None = None
# Блокування для моделі - забезпечує, що тільки одна транскрипція виконується одночасно
# Використовуємо threading.Lock, оскільки транскрипція виконується в executor (thread pool)
_model_lock: threading.Lock | None = None


async def _get_transcription_semaphore() -> asyncio.Semaphore:
    """Отримує або створює семафор для обмеження паралельних транскрипцій."""
    global _transcription_semaphore, _semaphore_lock
    if _transcription_semaphore is None:
        if _semaphore_lock is None:
            _semaphore_lock = asyncio.Lock()
        async with _semaphore_lock:
            if _transcription_semaphore is None:
                # Використовуємо тільки 1 паралельну транскрипцію для уникнення проблем з KV cache
                _transcription_semaphore = asyncio.Semaphore(1)
                logger.info("🔒 Створено семафор для транскрипцій (макс. 1 одночасно)")
    return _transcription_semaphore


def _get_model_lock() -> threading.Lock:
    """Отримує або створює блокування для моделі (threading.Lock для executor)."""
    global _model_lock
    if _model_lock is None:
        _model_lock = threading.Lock()
    return _model_lock


def _clear_model_cache(model):
    """Очищує KV cache моделі Whisper для уникнення конфліктів."""
    try:
        # Спробуємо очистити cache в декодері
        if hasattr(model, "decoder") and hasattr(model.decoder, "kv_cache"):
            model.decoder.kv_cache = None
            logger.debug("🧹 Очищено KV cache в decoder")
        # Спробуємо очистити cache в encoder (якщо є)
        if hasattr(model, "encoder") and hasattr(model.encoder, "kv_cache"):
            model.encoder.kv_cache = None
            logger.debug("🧹 Очищено KV cache в encoder")
        # Спробуємо очистити загальний cache моделі
        if hasattr(model, "kv_cache"):
            model.kv_cache = None
            logger.debug("🧹 Очищено загальний KV cache")
    except Exception as exc:  # noqa: BLE001
        logger.debug("⚠️ Не вдалося очистити cache: %s", exc)


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
    settings = get_user_settings(user_id) if user_id else {"language": None}
    target_lang = settings.get("language")

    logger.info("⚙️ Параметри: language=%s", target_lang or "auto")
    
    # Оптимізовані таймаути на основі тривалості аудіо
    # Збільшені таймаути для надійної обробки всіх файлів (включаючи повторні спроби)
    if audio_duration:
        if audio_duration <= 5:  # дуже короткі (до 5 сек)
            timeout = 180  # 3 хвилини (з урахуванням можливої повторної спроби)
        elif audio_duration <= 10:  # до 10 секунд
            timeout = 240  # 4 хвилини (з урахуванням можливої повторної спроби)
        elif audio_duration <= 30:  # до 30 секунд
            timeout = 300  # 5 хвилин
        elif audio_duration <= 60:  # до 1 хвилини
            timeout = 360  # 6 хвилин
        elif audio_duration <= 120:  # до 2 хвилин
            timeout = 420  # 7 хвилин
        elif audio_duration <= 300:  # до 5 хвилин
            timeout = 600  # 10 хвилин
        else:
            timeout = TRANSCRIPTION_TIMEOUT  # 15 хвилин
        logger.info("⏱️ Динамічний таймаут: %s сек (тривалість аудіо: %s сек)", timeout, audio_duration)
    else:
        timeout = 360  # За замовчуванням 6 хвилин для файлів невідомої тривалості
        logger.info("⏱️ Використовую стандартний таймаут: %s сек", timeout)

    loop = asyncio.get_event_loop()

    # Оптимальні параметри для швидкої та точної транскрипції
    # Для коротких файлів використовуємо швидкі параметри, щоб уникнути таймаутів
    if audio_duration and audio_duration <= 5:  # дуже короткі (до 5 сек)
        best_of, beam_size, temperature = 1, 2, 0.0  # Швидкі параметри для дуже коротких
    elif audio_duration and audio_duration <= 10:  # дуже короткі (до 10 сек)
        best_of, beam_size, temperature = 1, 2, 0.0  # Швидкі параметри
    elif audio_duration and audio_duration <= 30:  # короткі (до 30 сек)
        best_of, beam_size, temperature = 1, 3, 0.0  # Швидкі параметри
    elif audio_duration and audio_duration <= 60:  # короткі (до 1 хв)
        best_of, beam_size, temperature = 1, 3, 0.0
    elif audio_duration and audio_duration <= 180:  # середні (до 3 хв)
        best_of, beam_size, temperature = 1, 3, 0.0
    elif audio_duration and audio_duration <= 300:  # довгі (до 5 хв)
        best_of, beam_size, temperature = 2, 3, 0.0
    else:  # дуже довгі (більше 5 хв)
        best_of, beam_size, temperature = 2, 4, 0.0

    logger.info("🔧 Whisper параметри: best_of=%s, beam_size=%s, temperature=%s", best_of, beam_size, temperature)

    def run():
        logger.info("▶️ Запуск Whisper.transcribe()...")
        transcribe_start = time.time()
        
        # Використовуємо блокування моделі для забезпечення послідовного доступу
        # Це критично важливо для уникнення конфліктів з KV cache
        model_lock = _get_model_lock()
        
        with model_lock:
            # Очищуємо cache моделі перед транскрипцією, щоб уникнути конфліктів з KV cache
            # Це допомагає вирішити проблему з різними розмірами тензорів
            _clear_model_cache(model)
            
            prompts = {
                "uk": "Це український текст. Використовуй українську мову.",
                "en": "This is English text.",
                "pl": "To jest język polski.",
                "de": "Das ist deutscher Text.",
                "ru": "Это русский текст.",
            }

            # Базові параметри транскрипції - оптимізовані для швидкості та якості
            # Для коротких голосових використовуємо більш чутливі параметри
            base_params = {
                "fp16": False,  # False для CPU стабільності
                "temperature": temperature,
                "best_of": best_of,
                "beam_size": beam_size,
                "compression_ratio_threshold": 2.4,  # Поріг для виявлення повторень
                "condition_on_previous_text": False,  # Вимикаємо для швидкості
                "word_timestamps": False,  # Вимикаємо timestamps для швидкості
            }
            
            # Оптимізації для коротких голосових повідомлень
            # Для коротких файлів зменшуємо no_speech_threshold, щоб приймати навіть тихі звуки
            if audio_duration and audio_duration <= 5:  # дуже короткі (до 5 сек)
                # Для дуже коротких голосових - максимально чутливі параметри
                base_params.update({
                    "no_speech_threshold": 0.2,  # Дуже низький поріг - приймаємо майже все
                })
            elif audio_duration and audio_duration <= 10:  # дуже короткі (до 10 сек)
                # Для дуже коротких голосових - дуже чутливі параметри
                base_params.update({
                    "no_speech_threshold": 0.25,  # Дуже низький поріг - приймаємо навіть тихі звуки
                })
            elif audio_duration and audio_duration <= 30:  # короткі (до 30 сек)
                # Для коротких голосових - чутливі параметри
                base_params.update({
                    "no_speech_threshold": 0.35,  # Низький поріг для коротких файлів
                })
            elif audio_duration and audio_duration <= 60:  # середні (до 1 хв)
                base_params.update({
                    "no_speech_threshold": 0.45,  # Середній поріг
                })
            else:
                # Для довгих файлів - стандартні параметри
                base_params.update({
                    "no_speech_threshold": 0.6,  # Стандартний поріг
                })

            if target_lang:
                prompt = prompts.get(target_lang, "")
                try:
                    logger.info("🌐 Використовую мову: %s", target_lang)
                    # Формуємо параметри для транскрипції
                    transcribe_params = base_params.copy()
                    if prompt:
                        transcribe_params["initial_prompt"] = prompt
                    result = model.transcribe(
                        audio_path,
                        language=target_lang,
                        **transcribe_params,
                    )
                    elapsed = time.time() - transcribe_start
                    logger.info("✅ Whisper завершив транскрипцію за %.2f секунд", elapsed)
                    # Очищуємо cache після успішної транскрипції для наступної транскрипції
                    _clear_model_cache(model)
                    return result
                except RuntimeError as exc:
                    # Якщо помилка пов'язана з KV cache, спробуємо знову з очищеним cache
                    error_msg = str(exc)
                    if "Sizes of tensors" in error_msg or "kv_cache" in error_msg.lower() or "Expected size" in error_msg:
                        logger.warning("⚠️ Помилка KV cache: %s, очищаю cache і повторюю", error_msg[:150])
                        try:
                            _clear_model_cache(model)
                            # Повторна спроба з очищеним cache
                            retry_params = base_params.copy()
                            if prompt:
                                retry_params["initial_prompt"] = prompt
                            result = model.transcribe(
                                audio_path,
                                language=target_lang,
                                **retry_params,
                            )
                            elapsed = time.time() - transcribe_start
                            logger.info("✅ Whisper завершив транскрипцію після повторної спроби за %.2f секунд", elapsed)
                            # Очищуємо cache після успішної транскрипції
                            _clear_model_cache(model)
                            return result
                        except Exception as retry_exc:  # noqa: BLE001
                            logger.warning("⚠️ Повторна спроба не вдалася: %s, спробую auto", str(retry_exc)[:100])
                            # Очищуємо cache перед переходом до auto
                            _clear_model_cache(model)
                            pass
                    else:
                        logger.warning("⚠️ Помилка з мовою %s: %s, спробую auto", target_lang, error_msg[:100])
                        # Очищуємо cache перед переходом до auto
                        _clear_model_cache(model)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("⚠️ Помилка з мовою %s: %s, спробую auto", target_lang, str(exc)[:100])
                    # Очищуємо cache перед переходом до auto
                    _clear_model_cache(model)
                    pass

            logger.info("🌐 Використовую автоматичне визначення мови")
            try:
                # Для auto режиму використовуємо базовий prompt
                transcribe_params = base_params.copy()
                transcribe_params["initial_prompt"] = "Це може бути українська, англійська, польська, німецька або інша мова."
                result = model.transcribe(
                    audio_path,
                    language=None,
                    **transcribe_params,
                )
                elapsed = time.time() - transcribe_start
                logger.info("✅ Whisper завершив транскрипцію за %.2f секунд", elapsed)
                # Очищуємо cache після успішної транскрипції для наступної транскрипції
                _clear_model_cache(model)
                return result
            except RuntimeError as exc:
                # Якщо помилка пов'язана з KV cache, спробуємо знову з очищеним cache
                error_msg = str(exc)
                if "Sizes of tensors" in error_msg or "kv_cache" in error_msg.lower() or "Expected size" in error_msg:
                    logger.warning("⚠️ Помилка KV cache при auto: %s, очищаю cache і повторюю", error_msg[:150])
                    try:
                        _clear_model_cache(model)
                        # Повторна спроба з очищеним cache
                        retry_params = base_params.copy()
                        retry_params["initial_prompt"] = "Це може бути українська, англійська, польська, німецька або інша мова."
                        result = model.transcribe(
                            audio_path,
                            language=None,
                            **retry_params,
                        )
                        elapsed = time.time() - transcribe_start
                        logger.info("✅ Whisper завершив транскрипцію після повторної спроби за %.2f секунд", elapsed)
                        # Очищуємо cache після успішної транскрипції
                        _clear_model_cache(model)
                        return result
                    except Exception as retry_exc:  # noqa: BLE001
                        logger.error("❌ Повторна спроба не вдалася: %s", retry_exc)
                        # Очищуємо cache навіть при помилці
                        _clear_model_cache(model)
                        raise
                else:
                    # Очищуємо cache при інших помилках
                    _clear_model_cache(model)
                    raise

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
        minutes = timeout // 60
        if minutes == 0:
            minutes = 1
        return None, f"Транскрипція зайняла більше {minutes} хвилин. Спробуйте коротший аудіофайл або перевірте якість запису.", None
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error("❌ Помилка під час транскрипції (через %.2f сек): %s", elapsed, exc, exc_info=True)
        return None, f"Помилка обробки: {str(exc)[:100]}", None
    
    if result is None:
        logger.error("❌ Whisper повернув None")
        return None, "Не вдалося розпізнати аудіо", None

    text = result.get("text", "").strip() if result.get("text") else ""
    language = result.get("language", "невідома")
    no_speech_prob = result.get("no_speech_prob", 0.0)

    # Перевіряємо, чи Whisper визначив, що в аудіо немає мови
    # Для коротких файлів це може бути помилковим визначенням
    # Спробуємо повторити транскрипцію з більш чутливими параметрами
    # Але тільки якщо перша спроба була швидкою (щоб не перевищити таймаут)
    elapsed_so_far = time.time() - start_time
    time_left = timeout - elapsed_so_far
    
    if not text or (no_speech_prob > 0.7 and audio_duration and audio_duration <= 30):
        logger.warning("⚠️ Whisper визначив, що в аудіо немає мови або текст порожній (no_speech_prob=%.2f, text='%s', duration=%s, elapsed=%.1f сек)", 
                      no_speech_prob, text[:50] if text else "", audio_duration, elapsed_so_far)
        # Для коротких файлів спробуємо повторити з ще більш чутливими параметрами
        # Але тільки якщо залишилося достатньо часу (мінімум 30 секунд)
        if audio_duration and audio_duration <= 30 and time_left > 30:
            logger.info("🔄 Повторюю транскрипцію для короткого файлу (%s сек) з чутливими параметрами (залишилось часу: %.1f сек)", 
                       audio_duration, time_left)
            try:
                # Використовуємо блокування моделі для повторної спроби
                model_lock = _get_model_lock()
                with model_lock:
                    _clear_model_cache(model)
                    # Повторна спроба з дуже чутливими параметрами, але швидшими
                    # Використовуємо мінімальні параметри для максимальної швидкості
                    retry_params = {
                        "fp16": False,
                        "temperature": 0.0,
                        "best_of": 1,  # Мінімальні параметри для швидкості
                        "beam_size": 2,  # Мінімальні параметри для швидкості
                        "no_speech_threshold": 0.1,  # Дуже низький поріг - приймаємо майже все
                        "compression_ratio_threshold": 3.0,
                        "condition_on_previous_text": False,  # Вимикаємо для швидкості
                        "word_timestamps": False,
                    }
                    # Повторна спроба з максимально чутливими параметрами
                    retry_prompts = {
                        "uk": "Це український текст. Використовуй українську мову.",
                        "en": "This is English text.",
                        "pl": "To jest język polski.",
                        "de": "Das ist deutscher Text.",
                        "ru": "Это русский текст.",
                    }
                    if target_lang and target_lang in retry_prompts:
                        retry_params["initial_prompt"] = retry_prompts[target_lang]
                        logger.info("🔄 Повторна транскрипція з мовою: %s", target_lang)
                        retry_result = model.transcribe(audio_path, language=target_lang, **retry_params)
                    else:
                        retry_params["initial_prompt"] = "Це може бути українська, англійська, польська, німецька або інша мова."
                        logger.info("🔄 Повторна транскрипція з автоматичним визначенням мови")
                        retry_result = model.transcribe(audio_path, language=None, **retry_params)
                    
                    retry_text = retry_result.get("text", "").strip() if retry_result.get("text") else ""
                    retry_no_speech = retry_result.get("no_speech_prob", 0.0)
                    if retry_text:
                        logger.info("✅ Повторна транскрипція успішна: '%s' (no_speech_prob=%.2f)", retry_text[:50], retry_no_speech)
                        text = retry_text
                        language = retry_result.get("language", language)
                        no_speech_prob = retry_no_speech
                        result = retry_result  # Оновлюємо result для segments
                    else:
                        logger.warning("⚠️ Повторна транскрипція також не дала результату (no_speech_prob=%.2f)", retry_no_speech)
            except Exception as retry_exc:  # noqa: BLE001
                logger.error("❌ Помилка при повторній транскрипції: %s", retry_exc, exc_info=True)
        elif time_left <= 30:
            logger.warning("⚠️ Пропускаю повторну спробу - залишилось мало часу (%.1f сек)", time_left)

    if not text:
        logger.error("❌ Не вдалося отримати текст з транскрипції")
        return None, "Не вдалося розпізнати аудіо. Спробуйте записати голосове повідомлення чіткіше.", None

    segments = result.get("segments", [])
    avg_logprob = None
    if segments:
        logs = [seg.get("avg_logprob", -1.0) for seg in segments if "avg_logprob" in seg]
        if logs:
            avg_logprob = sum(logs) / len(logs)

    quality_info = {"avg_logprob": avg_logprob, "no_speech_prob": no_speech_prob}
    logger.info("✅ Розпізнавання завершено. language=%s, len(text)=%s, segments=%s, no_speech_prob=%.2f", 
                language, len(text), len(segments), no_speech_prob)
    return text, language, quality_info



