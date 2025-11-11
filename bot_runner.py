"""Побудова Telegram Application та запуск бота (основний runtime)."""
from __future__ import annotations

import asyncio
import logging

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

from config import BOT_TOKEN, LOG_LEVEL
from handlers import (
    button_callback,
    clear_command,
    echo,
    export_command,
    handle_audio,
    help_command,
    lang_command,
    mode_command,
    privacy_command,
    start,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL),
)
logger = logging.getLogger(__name__)


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(CommandHandler("mode", mode_command))
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
        if update.message and not update.message.text.startswith("/"):
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


