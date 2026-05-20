# ContentOps

Многоканальный Telegram-бот с AI-генерацией постов, модерацией, планировщиком и Mini App для администрирования.

## Стек
- Python 3.11, aiogram 3.x, FastAPI
- PostgreSQL + SQLAlchemy (async) + Alembic
- APScheduler (`AsyncIOScheduler`, SQLAlchemy job-store)
- AI: OpenAI / Anthropic Claude / Google Gemini (переключается через `.env`)
- Telegram Mini App на чистом HTML/CSS/JS
- Docker + docker-compose

## Структура
```
project/
├── bot/                    aiogram-роутеры, middlewares, клавиатуры, runtime-контейнер
├── services/
│   ├── ai/                 интерфейс AIProvider + реализации OpenAI / Claude / Gemini
│   ├── moderation/         ModerationService (стоп-слова + AI)
│   ├── scheduler/          PostScheduler (обёртка APScheduler)
│   └── channel/            ChannelManager (публикация/правка/удаление через Bot API)
├── models/                 SQLAlchemy-модели + async engine/session
├── webapp/                 FastAPI-приложение + static/ (UI Mini App)
├── migrations/             Alembic-миграции
├── tests/                  unit-тесты на pytest
├── config.py               pydantic-settings
├── run.py                  единый entrypoint (бот + webapp)
└── docker-compose.yml
```

## Конфигурация

Скопируйте и заполните:
```bash
cp .env.example .env
```

Ключевые переменные:
- `BOT_TOKEN` — токен от @BotFather
- `SUPERADMIN_IDS` — Telegram user_id администраторов (через запятую)
- `WEBAPP_URL` — публичный HTTPS-адрес Mini App (Telegram требует HTTPS)
- `AI_PROVIDER` — `openai` | `claude` | `gemini`
- `AI_MODEL` — например, `gpt-4o`, `claude-3-5-sonnet-latest`, `gemini-1.5-flash`
- Один из `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`
- `DATABASE_URL` — по умолчанию указывает на Postgres из compose
- `WEBAPP_HOST` / `WEBAPP_PORT` — по умолчанию `0.0.0.0:8080`

## Запуск

```bash
docker compose up --build
```

Compose поднимает Postgres, Redis, разовый сервис `migrate` (`alembic upgrade head`) и сервис `bot`, который слушает порт 8080.

## Добавление канала
1. Создайте канал в Telegram, добавьте бота **администратором** с правом публикации.
2. В личке бота отправьте `/addchannel <chat_id>` (число вида `-1001234567890`). Получить ID можно, переслав любое сообщение из канала боту вроде @userinfobot.
3. Откройте Mini App по inline-кнопке из `/start`, перейдите во вкладку «Настройки», задайте системный промт, стоп-слова, слоты расписания и тогглы.

## Команды бота
- `/start` — главное меню (с кнопкой Mini App)
- `/addchannel <chat_id>` — зарегистрировать канал
- `/channels` — список зарегистрированных каналов
- `/removechannel <id>` — снять регистрацию
- Запросы на одобрение приходят в личку администраторам с кнопками «Опубликовать» / «Отклонить»

## Вкладки Mini App
- **Обзор** — статистика по каналам, постам за 24 часа, очереди, ожиданию модерации, последние публикации
- **Создать** — ручной/AI-пост, медиа, расписание
- **Модерация** — очередь на одобрение и журнал автоудалений
- **Настройки** — системный промт, тогглы (одобрение / автопостинг / автоудаление), стоп-слова, слоты расписания, переопределение модели AI

## Логика модерации

```
новый пост → ModerationService
  ├─ есть совпадение со стоп-словом? → auto_delete? да → AUTO_DELETE / нет → NEEDS_APPROVAL
  ├─ AI check_content == BLOCK? → auto_delete? да → AUTO_DELETE / нет → NEEDS_APPROVAL
  ├─ AI check_content == FLAG? → NEEDS_APPROVAL
  ├─ channel.approval_required? → NEEDS_APPROVAL
  └─ иначе → PUBLISH
```

Автоудалённые посты записываются в `moderation_logs` с источником (`webapp`, `scheduler`, `autopost`, `admin`) и причиной.

## Авторизация в Mini App
Mini App отправляет `initData` в заголовке `X-Telegram-Init-Data`. Бэкенд проверяет HMAC-SHA256 подпись по `BOT_TOKEN` ([webapp/auth.py](webapp/auth.py)) и сверяет пользователя со списком `SUPERADMIN_IDS`. Чтобы пускать ролей `editor`, расширьте `require_admin` обращением к таблице `admins`.

## Тесты

```bash
pip install -r requirements.txt
pytest
```

Unit-тесты покрывают `ModerationService` (стоп-слова, regex, AI-вердикты, режим одобрения) и `PostScheduler` (разовые джобы, синхронизация cron, гейтинг по `auto_post`).

## Примечания
- Бот использует long polling (`dp.start_polling`). Для вебхуков поставьте nginx перед FastAPI и добавьте webhook-роут.
- Mini App — статический HTML/JS, отдаётся тем же процессом FastAPI. Для своего домена терминируйте TLS на nginx.
- `redis` и `celery` присутствуют в `requirements.txt` под будущие тяжёлые задачи; текущий пайплайн полностью in-process.
