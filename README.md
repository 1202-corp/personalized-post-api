# Personalized Post Bot API

> [Русская версия](docs/README-RU.md)

FastAPI backend with ML service for personalized post recommendations in Telegram channels.

## Overview

The API provides REST endpoints for user management, channel management, post scraping, ML-based recommendations, analytics, and A/B testing. It integrates with PostgreSQL for data persistence, Qdrant for vector embeddings, and Redis for caching.

## Key Features

- User and channel management
- Post scraping and storage
- ML-based recommendation system using vector embeddings
- Analytics and metrics dashboard
- A/B testing framework
- Admin operations and data management
- Health checks and monitoring

## Technology Stack

- **FastAPI** - REST API framework
- **SQLAlchemy 2.0** - Async ORM
- **PostgreSQL** - Primary database
- **Qdrant** - Vector database for embeddings
- **Redis** - Caching layer
- **Alembic** - Database migrations
- **OpenAI-compatible API** - Embedding generation

## Documentation

- [Russian documentation](docs/README-RU.md)
