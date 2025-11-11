"""Railway entrypoint."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = BASE_DIR
PARENT_DIR = os.path.dirname(PROJECT_ROOT)

for path in {PROJECT_ROOT, PARENT_DIR}:
    if path and path not in sys.path:
        sys.path.insert(0, path)

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

