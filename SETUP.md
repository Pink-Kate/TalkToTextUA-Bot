# Інструкція з налаштування

## Крок 1: Встановлення залежностей

```bash
pip install -r requirements.txt
```

## Крок 2: Налаштування змінних середовища

1. Скопіюйте файл `env.example` в `.env`:
```bash
copy env.example .env
```

2. Відкрийте `.env` файл та додайте ваш токен бота:
```env
BOT_TOKEN=ваш_токен_тут
LOG_LEVEL=INFO
```

**Як отримати токен:**
1. Відкрийте [@BotFather](https://t.me/BotFather) в Telegram
2. Введіть `/newbot`
3. Дотримуйтесь інструкцій для створення бота
4. Скопіюйте отриманий токен в `.env` файл

## Крок 3: Встановлення FFmpeg

FFmpeg необхідний для обробки аудіофайлів.

### Windows:
```bash
choco install ffmpeg
```
Або завантажте з [ffmpeg.org](https://ffmpeg.org/download.html)

### Linux:
```bash
sudo apt-get install ffmpeg
```

### macOS:
```bash
brew install ffmpeg
```

## Крок 4: Запуск бота

```bash
python bot.py
```

## Налаштування для роботи в групах

Для того, щоб бот працював у групах:

1. Відкрийте [@BotFather](https://t.me/BotFather)
2. Виберіть вашого бота
3. Виберіть "Bot Settings"
4. Виберіть "Group Privacy"
5. Встановіть "Disable" (вимкніть приватність групи)

## Структура проекту

```
BOT-2/
├── bot.py              # Головний файл (новий модульний)
├── bot_old.py          # Резервна копія старого файлу
├── config.py           # Конфігурація
├── handlers.py         # Обробники команд та повідомлень
├── storage.py          # Зберігання даних
├── transcription.py    # Модуль транскрипції
├── utils.py            # Утиліти
├── .env                # Ваші налаштування (не комітиться)
├── env.example         # Приклад налаштувань
├── requirements.txt    # Залежності
└── README.md           # Документація
```

## Важливо!

⚠️ **НЕ додавайте файл `.env` до Git!** Він містить ваш токен бота і не повинен бути публічним.

Файл `.env` вже додано до `.gitignore`.

