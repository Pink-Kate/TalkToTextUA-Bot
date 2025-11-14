"""Сумісність: проксі до кореневого модуля `storage`."""

import os
import sys
import importlib.util

# Отримуємо шлях до кореневого storage.py
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)
_ROOT_STORAGE_PATH = os.path.join(_PROJECT_ROOT, "storage.py")

# Видаляємо bot_app/storage з sys.modules, якщо він там є, щоб уникнути циклічного імпорту
if "storage" in sys.modules:
    storage_module = sys.modules["storage"]
    if hasattr(storage_module, "__file__") and storage_module.__file__:
        if "bot_app" in os.path.abspath(storage_module.__file__):
            del sys.modules["storage"]

# Завантажуємо кореневий storage.py напряму через importlib, щоб уникнути циклічного імпорту
if os.path.exists(_ROOT_STORAGE_PATH):
    # Використовуємо унікальне ім'я модуля, щоб уникнути конфліктів
    module_name = f"root_storage_{id(_ROOT_STORAGE_PATH)}"
    spec = importlib.util.spec_from_file_location(module_name, _ROOT_STORAGE_PATH)
    root_storage = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = root_storage
    spec.loader.exec_module(root_storage)
    
    # Експортуємо функції
    add_to_history = root_storage.add_to_history
    clear_chat_history = root_storage.clear_chat_history
    get_chat_history = root_storage.get_chat_history
    get_user_settings = root_storage.get_user_settings
else:
    # Якщо кореневий файл не знайдено, спробуємо звичайний імпорт
    # Додаємо корінь проекту до sys.path
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    
    # Імпортуємо з кореневого storage.py
    from storage import (  # noqa: F401
        add_to_history,
        clear_chat_history,
        get_chat_history,
        get_user_settings,
    )

# Експортуємо все для сумісності
__all__ = ["add_to_history", "clear_chat_history", "get_chat_history", "get_user_settings"]

