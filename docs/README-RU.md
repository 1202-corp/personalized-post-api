# API для Personalized Post Bot

> [English version](../README.md)

FastAPI бэкенд с ML-сервисом для персонализированных рекомендаций постов из Telegram каналов.

## Описание

API предоставляет REST эндпоинты для управления пользователями, каналами, скрейпинга постов, ML-рекомендаций на основе векторных эмбеддингов, аналитики и A/B тестирования. Интегрируется с PostgreSQL для хранения данных, Qdrant для векторных эмбеддингов и Redis для кеширования.

## Основные функции

- Управление пользователями и каналами
- Скрейпинг и хранение постов
- ML-система рекомендаций на основе векторных эмбеддингов
- Аналитика и метрики
- A/B тестирование алгоритмов
- Административные операции
- Health checks и мониторинг

## Технологии

- **FastAPI** — REST API фреймворк
- **SQLAlchemy 2.0** — Асинхронный ORM
- **PostgreSQL** — Основная база данных
- **Qdrant** — Векторная БД для эмбеддингов
- **Redis** — Кеширование
- **Alembic** — Миграции базы данных
- **OpenAI-совместимый API** — Генерация эмбеддингов

## ML Pipeline

1. **Генерация эмбеддингов** — Используется OpenAI-совместимый API для создания векторных представлений постов
2. **Хранение векторов** — Эмбеддинги сохраняются в Qdrant для быстрого поиска
3. **Обучение модели** — Preference vector вычисляется на основе лайков/дизлайков пользователя
4. **Рекомендации** — Поиск релевантных постов через cosine similarity

## API Endpoints

### Users
- `POST /api/v1/users/` - Create or get user
- `GET /api/v1/users/{id}` - Get user by telegram_id
- `PATCH /api/v1/users/{id}` - Update user

### Channels
- `POST /api/v1/channels/` - Create channel
- `GET /api/v1/channels/defaults` - Get default channels
- `POST /api/v1/channels/user-channel` - Link channel to user

### Posts
- `POST /api/v1/posts/bulk` - Bulk create posts
- `POST /api/v1/posts/training` - Get training posts
- `POST /api/v1/posts/interactions` - Record like/dislike
- `POST /api/v1/posts/best` - Get best posts for user

### ML
- `POST /api/v1/ml/train` - Train model for user
- `GET /api/v1/ml/eligibility/{id}` - Check training eligibility

### Analytics
- `GET /api/v1/analytics/dashboard` - Full dashboard
- `GET /api/v1/analytics/overview` - Overview statistics
- `GET /api/v1/analytics/daily` - Daily statistics
- `GET /api/v1/analytics/channels` - Top channels
- `GET /api/v1/analytics/retention` - Retention metrics

### A/B Testing
- `GET /api/v1/ab-testing/config` - Get test configuration
- `POST /api/v1/ab-testing/config` - Update configuration
- `GET /api/v1/ab-testing/results` - Get test results

### Admin
- `GET /api/v1/admin/users` - List users
- `GET /api/v1/admin/users/{id}` - User details
- `PATCH /api/v1/admin/users/{id}` - Update user
- `DELETE /api/v1/admin/users/{id}` - Delete user

### Health
- `GET /health` - Liveness check
- `GET /health/ready` - Readiness check (postgres, qdrant)

