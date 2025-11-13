"""Railway entrypoint."""

import os
import sys

# Додаємо корінь проекту до sys.path ПЕРЕД будь-якими імпортами
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Імпортуємо bot_runner - він знайде config
from bot_runner import main  # noqa: E402


if __name__ == "__main__":
    main()

