"""Railway entrypoint."""

import os
import sys

# Додаємо корінь проекту до sys.path ПЕРШИМ, щоб всі модулі могли знайти config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = BASE_DIR

# Додаємо корінь проекту до sys.path, якщо його там немає
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Перевіряємо, що config.py існує
config_path = os.path.join(PROJECT_ROOT, "config.py")
if not os.path.exists(config_path):
    raise FileNotFoundError(
        f"config.py не знайдено в {PROJECT_ROOT}. "
        f"Переконайтеся, що файл існує в корені проекту."
    )

try:
    from bot_runner import main  # noqa: E402
except ModuleNotFoundError:
    try:
        from bot_app.main import main  # noqa: E402
    except ModuleNotFoundError:
        import importlib.util

        module_path = os.path.join(PROJECT_ROOT, "bot_app", "main.py")
        if not os.path.exists(module_path):
            raise

        spec = importlib.util.spec_from_file_location("bot_app.main", module_path)
        if not spec or not spec.loader:
            raise

        bot_app_main = importlib.util.module_from_spec(spec)
        sys.modules["bot_app.main"] = bot_app_main
        spec.loader.exec_module(bot_app_main)
        main = bot_app_main.main  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()

