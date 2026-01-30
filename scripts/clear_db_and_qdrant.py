#!/usr/bin/env python3
"""
Очистка всех таблиц БД и Qdrant (сброс к начальному состоянию).
Запуск из контейнера api: docker compose exec api python -m scripts.clear_db_and_qdrant
Или из корня api: PYTHONPATH=/app python scripts/clear_db_and_qdrant.py
"""
import asyncio
import sys
from pathlib import Path

# Ensure app is importable when run as script
if __name__ == "__main__" and str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import get_settings
from app.models.interaction import Interaction
from app.models.user_preference_vector import UserPreferenceVector
from app.models.taste_cluster import TasteCluster
from app.models.user import User
from app.models.channel import Channel
from app.models.post import Post
from app.models.user_channel import UserChannel
from app.models.channel_avatar import ChannelAvatar

settings = get_settings()
QDRANT_TIMEOUT = getattr(settings, "qdrant_timeout", 30)


async def clear_database():
    """Очистить ВСЕ таблицы в БД."""
    engine = create_async_engine(settings.database_url, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        print("Очистка БД (все таблицы)...")
        await session.execute(delete(Interaction))
        print("  ✓ Interactions удалены")
        await session.execute(delete(UserPreferenceVector))
        print("  ✓ User preference vectors удалены")
        await session.execute(delete(UserChannel))
        print("  ✓ User channels удалены")
        await session.execute(delete(Post))
        print("  ✓ Posts удалены")
        await session.execute(delete(ChannelAvatar))
        print("  ✓ Channel avatars удалены")
        await session.execute(delete(Channel))
        print("  ✓ Channels удалены")
        await session.execute(delete(TasteCluster))
        print("  ✓ Taste clusters удалены")
        await session.execute(delete(User))
        print("  ✓ Users удалены")
        await session.commit()
    await engine.dispose()
    print("БД полностью очищена\n")


def clear_qdrant():
    """Очистить Qdrant collection."""
    print("Очистка Qdrant...")
    client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout=QDRANT_TIMEOUT,
    )
    collections = client.get_collections().collections
    if settings.qdrant_collection_name in [c.name for c in collections]:
        client.delete_collection(settings.qdrant_collection_name)
        print(f"  ✓ Collection '{settings.qdrant_collection_name}' удалена")
    else:
        print(f"  - Collection '{settings.qdrant_collection_name}' не найдена")
    client.create_collection(
        collection_name=settings.qdrant_collection_name,
        vectors_config=models.VectorParams(
            size=settings.embedding_dimensions,
            distance=models.Distance.COSINE,
        ),
    )
    print(f"  ✓ Collection '{settings.qdrant_collection_name}' создана заново")
    print("Qdrant очищен\n")


async def main():
    print("=" * 60)
    print("Очистка БД и Qdrant")
    print("=" * 60)
    print()
    try:
        await clear_database()
        clear_qdrant()
        print("=" * 60)
        print("✓ Очистка завершена успешно")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
