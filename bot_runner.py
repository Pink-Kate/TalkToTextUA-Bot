"""Побудова Telegram Application та запуск бота (основний runtime)."""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# Додаємо корінь проекту до sys.path ПЕРЕД будь-якими імпортами
# Це гарантує, що Python знайде модуль config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from telegram import Update
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Імпортуємо config - просто і прямо
import config

# Перевіряємо, що config виконався правильно
if not hasattr(config, "BOT_TOKEN"):
    # Якщо BOT_TOKEN не існує, це означає, що config.py не виконався
    # Спробуємо виконати його вручну
    import importlib
    importlib.reload(config)

# Тепер імпортуємо потрібні змінні
try:
    BOT_TOKEN = config.BOT_TOKEN
    LOG_LEVEL = config.LOG_LEVEL
except AttributeError as e:
    # Якщо атрибут не існує, виводимо детальну інформацію
    import traceback
    print(f"Помилка при завантаженні config: {e}")
    print(f"Шлях до config: {getattr(config, '__file__', 'невідомо')}")
    print(f"Доступні атрибути config: {[a for a in dir(config) if not a.startswith('_')]}")
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"sys.path: {sys.path[:5]}")
    traceback.print_exc()
    raise

from handlers import (
    button_callback,
    clear_command,
    echo,
    export_command,
    handle_audio,
    help_command,
    lang_command,
    privacy_command,
    start,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, "INFO"),
)
logger = logging.getLogger(__name__)


def main() -> None:
    # Перевірка BOT_TOKEN перед запуском
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не встановлено. Додайте його у .env або в змінні середовища.")
    
    # Налаштування для паралельної обробки оновлень з різних чатів
    # concurrent_updates=None означає необмежену паралельність (за замовчуванням)
    # Це дозволяє обробляти повідомлення з різних чатів одночасно
    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("privacy", privacy_command))

    application.add_handler(CallbackQueryHandler(button_callback))

    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio), group=1)
    application.add_handler(
        MessageHandler(filters.Document.ALL & ~filters.VOICE & ~filters.AUDIO, handle_audio),
        group=1,
    )

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        err = context.error
        if not err:
            return

        if isinstance(err, Conflict) or "Conflict" in type(err).__name__:
            logger.warning(
                "⚠️ Conflict: бот запущений в іншому місці. Якщо це Railway + локальний запуск — це нормально."
            )
            return

        logger.error("=" * 50)
        logger.error("❌ НЕОБРОБЛЕНА ПОМИЛКА", exc_info=err)
        logger.error("=" * 50)

        if isinstance(update, Update) and update.message:
            try:
                await update.message.reply_text(
                    "❌ Виникла помилка при обробці вашого запиту. Спробуйте ще раз."
                )
            except Exception:  # noqa: BLE001
                pass

    application.add_error_handler(error_handler)

    async def log_updates(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        text = getattr(update.message, "text", None)
        if text and not text.startswith("/"):
            logger.info(
                "📨 Оновлення: chat=%s user=%s voice=%s audio=%s document=%s",
                update.message.chat.id,
                update.message.from_user.id if update.message.from_user else None,
                bool(update.message.voice),
                bool(update.message.audio),
                bool(update.message.document),
            )

    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, log_updates), group=99)

    logger.info("=" * 50)
    logger.info("🚀 БОТ ЗАПУСКАЄТЬСЯ...")
    logger.info("✅ Токен завантажено: %s", "Так" if BOT_TOKEN else "НІ")
    logger.info("=" * 50)

    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(application.bot.delete_webhook(drop_pending_updates=True))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не вдалося видалити webhook: %s", exc)

    logger.info("Очікую оновлення від Telegram...")

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, close_loop=False)
    except KeyboardInterrupt:
        logger.info("Зупинено користувачем.")
    except Conflict as exc:
        logger.warning("⚠️ Conflict при запуску polling: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Критична помилка: %s", exc, exc_info=True)
        raise



