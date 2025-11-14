"""Сумісність: проксі до кореневого модуля `storage`."""

import os
import sys

# Додаємо корінь проекту до sys.path для правильного імпорту
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)
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

