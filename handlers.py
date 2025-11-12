"""Сумісність: проксі до кореневого модуля `handlers`."""

from __future__ import annotations

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from handlers import *  # noqa: F401,F403
except ModuleNotFoundError as exc:  # pragma: no cover
    raise ModuleNotFoundError(
        "Не вдалося імпортувати модуль `handlers`. Запускайте код із кореня проєкту, "
        "де розміщено файл `handlers.py`."
    ) from exc

