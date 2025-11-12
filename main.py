"""Сумісність: проксі до кореневого модуля `bot_runner`."""

from __future__ import annotations

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from bot_runner import main
except ModuleNotFoundError as exc:  # pragma: no cover
    raise ModuleNotFoundError(
        "Не вдалося імпортувати `bot_runner`. Переконайтеся, що запускаєте скрипт "
        "з кореня проєкту або що файли розміщені в одній директорії."
    ) from exc

__all__ = ["main"]

