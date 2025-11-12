"""Railway entrypoint."""

import os
import sys

# КРИТИЧНО: Додаємо корінь проекту до sys.path ПЕРШИМ
# Це гарантує, що всі модулі (config, bot_runner, handlers, тощо) будуть доступні
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = BASE_DIR

# Додаємо корінь проекту на початок sys.path (найвищий пріоритет)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Додаткова перевірка: переконаємося, що config.py існує
config_path = os.path.join(PROJECT_ROOT, "config.py")
if not os.path.exists(config_path):
    # Логуємо помилку з деталями для діагностики
    error_msg = (
        f"❌ config.py не знайдено в {PROJECT_ROOT}\n"
        f"   Поточний робочий каталог: {os.getcwd()}\n"
        f"   Абсолютний шлях до main.py: {os.path.abspath(__file__)}\n"
    )
    if os.path.exists(PROJECT_ROOT):
        try:
            files = os.listdir(PROJECT_ROOT)
            error_msg += f"   Файли в директорії: {', '.join(files[:20])}\n"
        except Exception:
            pass
    raise FileNotFoundError(error_msg)

# Тепер імпортуємо bot_runner - він має знайти config
try:
    from bot_runner import main  # noqa: E402
except ImportError as e:
    # Детальна помилка для діагностики
    error_msg = (
        f"❌ Не вдалося імпортувати bot_runner\n"
        f"   Помилка: {e}\n"
        f"   PROJECT_ROOT: {PROJECT_ROOT}\n"
        f"   sys.path: {sys.path[:5]}\n"
    )
    # Спробуємо альтернативний шлях
    try:
        from bot_app.main import main  # noqa: E402
    except ImportError:
        raise ImportError(error_msg) from e


if __name__ == "__main__":
    main()

