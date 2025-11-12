"""Побудова Telegram Application та запуск бота (основний runtime)."""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# КРИТИЧНО: Додаємо корінь проекту до sys.path ПЕРЕД будь-якими імпортами
# Це гарантує, що Python знайде модуль config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = BASE_DIR

# Додаємо корінь проекту на початок sys.path (найвищий пріоритет)
# Це гарантує, що кореневий config.py матиме пріоритет над bot_app/config.py
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
elif sys.path.index(PROJECT_ROOT) != 0:
    # Якщо PROJECT_ROOT вже в sys.path, але не на початку, переміщуємо його на початок
    sys.path.remove(PROJECT_ROOT)
    sys.path.insert(0, PROJECT_ROOT)

# Перевіряємо, що config.py існує в корені проекту
config_file_path = os.path.join(PROJECT_ROOT, "config.py")
if not os.path.exists(config_file_path):
    raise FileNotFoundError(
        f"config.py не знайдено в {PROJECT_ROOT}. "
        f"Поточний робочий каталог: {os.getcwd()}. "
        f"Файли в директорії: {os.listdir(PROJECT_ROOT) if os.path.exists(PROJECT_ROOT) else 'N/A'}"
    )

# Тепер імпортуємо config - він має бути доступним
# Спочатку видаляємо можливий конфлікт з bot_app.config (якщо він був завантажений)
if "config" in sys.modules:
    # Перевіряємо, чи це кореневий config чи bot_app.config
    loaded_config = sys.modules["config"]
    loaded_path = getattr(loaded_config, "__file__", "")
    if "bot_app" in loaded_path:
        # Якщо завантажений bot_app.config, видаляємо його
        del sys.modules["config"]
        # Також видаляємо bot_app.config, якщо він існує
        if "bot_app.config" in sys.modules:
            del sys.modules["bot_app.config"]

# Тепер імпортуємо config - він має знайти кореневий config.py
try:
    import config
    # Перевіряємо, що це правильний config (кореневий)
    config_path_loaded = getattr(config, "__file__", "")
    if "bot_app" in config_path_loaded:
        raise ImportError(f"Імпортовано bot_app.config замість кореневого config. Шлях: {config_path_loaded}")
    
    # Перевіряємо, що модуль містить необхідні атрибути
    if not hasattr(config, "BOT_TOKEN"):
        raise AttributeError(f"config.py не містить BOT_TOKEN. Доступні атрибути: {dir(config)}")
    if not hasattr(config, "LOG_LEVEL"):
        raise AttributeError(f"config.py не містить LOG_LEVEL. Доступні атрибути: {dir(config)}")
except ImportError as e:
    raise ImportError(
        f"Не вдалося імпортувати config з {config_file_path}. "
        f"PROJECT_ROOT: {PROJECT_ROOT}. "
        f"Поточний робочий каталог: {os.getcwd()}. "
        f"sys.path (перші 5): {sys.path[:5]}. "
        f"Помилка: {e}"
    ) from e
except AttributeError as e:
    raise AttributeError(
        f"config.py не містить необхідних атрибутів. "
        f"Шлях до config: {getattr(config, '__file__', 'невідомо')}. "
        f"Помилка: {e}"
    ) from e

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

# Тепер імпортуємо з config - він точно доступний
BOT_TOKEN = config.BOT_TOKEN
LOG_LEVEL = config.LOG_LEVEL
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
    level=getattr(logging, LOG_LEVEL),
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



