# Pribilka Backend

Backend для поиска выгодных вложений капитала. MVP ориентирован на рынок Польши.

> Платформа не является инвестиционным советником — только агрегация и сравнение рыночных данных.

## Стек

- Python 3.12 + FastAPI
- PostgreSQL 16 + SQLAlchemy 2.0 + Alembic
- Redis 7 + Celery
- Docker Compose

## Быстрый старт

```bash
# 1. Скопировать переменные окружения
cp .env.example .env

# 2. Запустить инфраструктуру
docker compose up -d db redis

# 3. Установить зависимости (нужен Python 3.12+)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 4. Заполнить БД начальными данными
PYTHONPATH=src python scripts/run_collectors.py

# 5. Запустить API
PYTHONPATH=src uvicorn pribilka.main:app --reload --port 8000
```

API: http://localhost:8000/docs

## Docker (полный стек)

```bash
docker compose up --build
```

Сервисы:
- `api` — FastAPI на порту 8000
- `worker` — Celery worker + beat (расписание коллекторов)
- `db` — PostgreSQL
- `redis` — Redis

## API Endpoints (v1)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/v1/deposits` | Список депозитов |
| GET | `/api/v1/deposits/{id}` | Детали депозита |
| GET | `/api/v1/bonds` | Список облигаций |
| GET | `/api/v1/gold` | Текущая цена золота |
| GET | `/api/v1/fx` | Курсы валют |
| GET | `/api/v1/market-summary` | Сводка рынка |
| GET | `/api/v1/best-deposits` | Лучшие депозиты |
| GET | `/api/v1/best-bonds` | Лучшие облигации |
| GET | `/api/v1/market-opportunities` | Топ возможностей |
| POST | `/api/v1/alerts` | Создать алерт |
| GET | `/api/v1/alerts?user_id=` | Список алертов |

## Коллекторы

| Коллектор | Источник | Интервал |
|-----------|----------|----------|
| `PolandDepositCollector` | Seed (→ скрейпинг банков) | 4 часа |
| `PolandBondCollector` | Seed (→ MF/GPW) | 1 час |
| `NbpFxCollector` | NBP API (живые данные) | 15 мин |
| `PolandGoldCollector` | Placeholder | 15 мин |

Добавление нового источника: создать класс в `src/pribilka/collectors/`, зарегистрировать в `workers/tasks.py`.

## Структура проекта

```
src/pribilka/
├── api/           # REST endpoints
├── collectors/    # Сборщики данных по классам активов
├── models/        # SQLAlchemy модели
├── schemas/       # Pydantic схемы
├── services/      # Бизнес-логика (ingestion, scoring, events)
├── workers/       # Celery tasks
└── main.py        # FastAPI app
```

## Следующие шаги

1. Реальный скрейпинг польских банков (PKO, ING, mBank, Santander)
2. Источник облигаций (GPW / Ministerstwo Finansów)
3. Живой источник цены золота
4. Alert engine — проверка правил после каждого сбора
5. JWT аутентификация
