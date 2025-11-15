"""Зберігання даних бота (в пам'яті)."""
from __future__ import annotations

import threading
from typing import Any, Dict, List

from config import MAX_HISTORY_ENTRIES

user_settings: Dict[int, Dict[str, Any]] = {}
chat_history: Dict[int, List[Dict[str, Any]]] = {}
# Окреме відстеження всіх унікальних користувачів бота
_all_users: set[int] = set()
_storage_lock = threading.Lock()


def register_user(user_id: int) -> None:
    """Реєструє користувача (thread-safe)."""
    with _storage_lock:
        _all_users.add(user_id)


def get_user_settings(user_id: int) -> Dict[str, Any]:
    """Отримує налаштування користувача (thread-safe)."""
    with _storage_lock:
        # Реєструємо користувача при отриманні налаштувань
        _all_users.add(user_id)
        if user_id not in user_settings:
            user_settings[user_id] = {"language": None}
        # Повертаємо посилання (налаштування змінюються через це посилання)
        return user_settings[user_id]


def add_to_history(chat_id: int, user_id: int | None, text: str, language: str) -> None:
    """Додає запис до історії чату (thread-safe)."""
    import datetime
    
    with _storage_lock:
        # Реєструємо користувача, якщо він є
        if user_id is not None:
            _all_users.add(user_id)
        
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


def get_user_count() -> int:
    """Отримує кількість унікальних користувачів бота (thread-safe)."""
    with _storage_lock:
        # Використовуємо окреме відстеження _all_users
        # Також синхронізуємо з існуючими даними для надійності
        users_from_settings = set(user_settings.keys())
        users_from_history = set()
        for history_list in chat_history.values():
            for entry in history_list:
                user_id = entry.get("user_id")
                if user_id is not None:
                    users_from_history.add(user_id)
        
        # Об'єднуємо всі джерела для точного підрахунку
        all_known_users = users_from_settings | users_from_history | _all_users
        
        # Оновлюємо _all_users для подальшого використання
        _all_users.update(all_known_users)
        
        return len(_all_users)


def get_detailed_stats() -> Dict[str, Any]:
    """Отримує детальну статистику бота (thread-safe)."""
    import datetime
    from collections import Counter
    
    with _storage_lock:
        # Синхронізуємо _all_users
        users_from_settings = set(user_settings.keys())
        users_from_history = set()
        all_transcriptions = []
        total_text_length = 0
        language_counter = Counter()
        user_language_settings = Counter()
        last_activity = None
        
        # Збираємо дані з історії
        for history_list in chat_history.values():
            for entry in history_list:
                all_transcriptions.append(entry)
                user_id = entry.get("user_id")
                if user_id is not None:
                    users_from_history.add(user_id)
                
                # Статистика по мовам транскрипцій
                lang = entry.get("language", "невідома")
                if lang and lang != "невідома":
                    language_counter[lang] += 1
                
                # Довжина тексту
                text = entry.get("text", "")
                if text:
                    total_text_length += len(text)
                
                # Остання активність
                timestamp_str = entry.get("timestamp")
                if timestamp_str:
                    try:
                        timestamp = datetime.datetime.fromisoformat(timestamp_str)
                        if last_activity is None or timestamp > last_activity:
                            last_activity = timestamp
                    except (ValueError, TypeError):
                        pass
        
        # Налаштування мов користувачів
        for user_id, settings in user_settings.items():
            lang = settings.get("language")
            if lang:
                user_language_settings[lang] += 1
            else:
                user_language_settings["auto"] += 1
        
        # Об'єднуємо всі джерела користувачів
        all_known_users = users_from_settings | users_from_history | _all_users
        _all_users.update(all_known_users)
        
        # Середня довжина тексту
        avg_text_length = total_text_length / len(all_transcriptions) if all_transcriptions else 0
        
        # Найпопулярніші мови транскрипцій
        top_languages = language_counter.most_common(5)
        
        # Налаштування мов користувачів
        top_user_languages = user_language_settings.most_common(5)
        
        return {
            "total_users": len(_all_users),
            "total_transcriptions": len(all_transcriptions),
            "unique_chats": len(chat_history),
            "total_text_length": total_text_length,
            "avg_text_length": round(avg_text_length, 1),
            "top_languages": top_languages,
            "top_user_languages": top_user_languages,
            "last_activity": last_activity,
            "users_with_settings": len(user_settings),
        }




