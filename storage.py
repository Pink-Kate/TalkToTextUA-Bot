"""Зберігання даних бота (в пам'яті)."""
from __future__ import annotations

import threading
from typing import Any, Dict, List

from config import MAX_HISTORY_ENTRIES

user_settings: Dict[int, Dict[str, Any]] = {}
chat_history: Dict[int, List[Dict[str, Any]]] = {}
_storage_lock = threading.Lock()


def get_user_settings(user_id: int) -> Dict[str, Any]:
    """Отримує налаштування користувача (thread-safe)."""
    with _storage_lock:
        if user_id not in user_settings:
            user_settings[user_id] = {"language": None}
        # Повертаємо посилання (налаштування змінюються через це посилання)
        return user_settings[user_id]


def add_to_history(chat_id: int, user_id: int | None, text: str, language: str) -> None:
    """Додає запис до історії чату (thread-safe)."""
    import datetime
    
    with _storage_lock:
        if chat_id not in chat_history:
            chat_history[chat_id] = []
        chat_history[chat_id].append(
            {
                "text": text,
                "language": language,
                "user_id": user_id,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )
        if len(chat_history[chat_id]) > MAX_HISTORY_ENTRIES:
            chat_history[chat_id] = chat_history[chat_id][-MAX_HISTORY_ENTRIES:]


def get_chat_history(chat_id: int) -> List[Dict[str, Any]]:
    """Отримує історію чату (thread-safe read)."""
    with _storage_lock:
        return chat_history.get(chat_id, []).copy()


def clear_chat_history(chat_id: int) -> None:
    """Очищає історію чату (thread-safe)."""
    with _storage_lock:
        if chat_id in chat_history:
            chat_history[chat_id] = []




