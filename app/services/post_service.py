"""Post business logic service."""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from app.models.post import Post
from app.models.channel import Channel
from app.models.interaction import Interaction, InteractionType
from app.models.user import User
from app.repositories.post_repository import PostRepository
from app.repositories.channel_repository import ChannelRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.user_channel_repository import UserChannelRepository
from app.schemas import PostCreate, PostBulkCreate, InteractionCreate, PostWithChannel
from app.exceptions import NotFoundError, ValidationError
from app.logging_config import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


def _normalize_datetime(dt: datetime) -> datetime:
    """Convert aware datetimes to naive UTC to satisfy TIMESTAMP WITHOUT TIME ZONE."""
    if dt is None:
        return dt
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _post_to_post_with_channel(post: Post, channel: Channel) -> PostWithChannel:
    """Convert Post and Channel to PostWithChannel schema.
    
    Note: text field is always None as it's stored in Redis, not DB.
    Clients should fetch text from Redis cache separately.
    """
    return PostWithChannel(
        id=post.id,
        telegram_message_id=post.telegram_message_id,
        text=None,  # Text stored in Redis, not DB - fetch separately via cache API
        media_type=post.media_type,
        media_file_id=post.media_file_id,
        posted_at=post.posted_at,
        channel_id=post.channel_id,
        relevance_score=post.relevance_score,
        created_at=post.created_at,
        channel_username=channel.username,
        channel_title=channel.title,
    )


async def get_post_by_id(session: AsyncSession, post_id: int) -> Optional[Post]:
    """Get post by ID."""
    return await PostRepository.get_by_id(session, post_id)


async def invalidate_post_message_gone(session: AsyncSession, post_id: int) -> bool:
    """
    Mark post as invalid because the Telegram message no longer exists (deleted in channel).
    Clears Redis cache and soft-deletes the post in DB.
    Returns True if post was invalidated, False if post not found or already deleted.
    """
    from app.services.post_cache_service import get_post_cache_service

    post = await PostRepository.get_by_id(session, post_id)
    if not post or post.is_deleted:
        return False
    cache_service = get_post_cache_service()
    await cache_service.invalidate_post_cache(post_id)
    await PostRepository.soft_delete(session, post_id)
    await session.commit()
    logger.info(f"post_message_gone_invalidated: post_id={post_id} (Redis cleared, soft-deleted)")
    return True


async def get_post_by_channel_and_message(
    session: AsyncSession,
    channel_telegram_id: int,
    telegram_message_id: int
) -> Optional[Post]:
    """Get post by channel and message ID."""
    return await PostRepository.get_by_channel_telegram_id_and_message(
        session, channel_telegram_id, telegram_message_id
    )


async def cleanup_expired_realtime_posts(session: AsyncSession) -> int:
    """
    Soft-delete realtime posts that have expired (expires_at < now).
    Also invalidate their Redis cache. Returns number of posts cleaned.
    """
    from app.services.post_cache_service import get_post_cache_service
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Post.id).where(
            Post.expires_at.isnot(None),
            Post.expires_at < now,
            Post.is_deleted == False,
        )
    )
    post_ids = [row[0] for row in result.all()]
    if not post_ids:
        return 0
    cache_service = get_post_cache_service()
    for post_id in post_ids:
        await cache_service.invalidate_post_cache(post_id)
        await PostRepository.soft_delete(session, post_id)
    await session.flush()
    logger.info(f"cleanup_expired_realtime_posts: cleaned {len(post_ids)} posts (expires_at < now)")
    return len(post_ids)


async def create_post(session: AsyncSession, post_data: PostCreate) -> Optional[Post]:
    """Create a new post (realtime: DB + Redis 10 min TTL). Text and media are stored in Redis, not in DB."""
    from app.services.post_cache_service import get_post_cache_service
    
    try:
        await cleanup_expired_realtime_posts(session)
        await session.commit()
        # Re-open transaction for create
        channel = await ChannelRepository.get_by_telegram_id(session, post_data.channel_telegram_id)
        if not channel:
            raise NotFoundError(f"Channel with telegram_id {post_data.channel_telegram_id} not found")
        
        normalized_posted_at = _normalize_datetime(post_data.posted_at)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.realtime_post_ttl_minutes)
        
        # Create post (realtime: expires_at = 10 min; Redis content 10 min set below)
        post = Post(
            channel_id=channel.id,
            telegram_message_id=post_data.telegram_message_id,
            media_type=post_data.media_type,
            media_file_id=post_data.media_file_id,
            posted_at=normalized_posted_at,
            expires_at=expires_at,
        )
        session.add(post)
        await session.flush()
        await session.commit()
        await session.refresh(post)
        
        # Store text and media in Redis cache if provided (10 min TTL for new realtime posts)
        if post_data.text or post_data.media_file_id:
            cache_service = get_post_cache_service()
            await cache_service.set_post_content(
                post_id=post.id,
                text=post_data.text,
                media_type=post_data.media_type,
                media_data=None,
                ttl_seconds=settings.realtime_post_ttl_minutes * 60,  # realtime: 10 min
            )
            logger.debug(f"Cached post content in Redis (post_id={post.id}, has_text={post_data.text is not None})")
        
        logger.info(f"post_created: post_id={post.id}, channel_id={channel.id}, text_in_redis={post_data.text is not None}")
        return post
    except NotFoundError:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"post_creation_failed: {str(e)}", exc_info=True)
        raise ValidationError(f"Failed to create post: {str(e)}")


async def bulk_create_posts(session: AsyncSession, bulk_data: PostBulkCreate) -> List[Post]:
    """Bulk create/update posts. If for_training=True: training metadata (no TTL, update-or-create). Else: realtime (10 min TTL)."""
    from app.services.post_cache_service import get_post_cache_service

    channel = await ChannelRepository.get_by_telegram_id(session, bulk_data.channel_telegram_id)
    if not channel:
        raise NotFoundError(f"Channel with telegram_id {bulk_data.channel_telegram_id} not found")

    if getattr(bulk_data, "for_training", False):
        return await _bulk_upsert_training_posts(session, channel, bulk_data)

    try:
        await cleanup_expired_realtime_posts(session)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    try:
        created_posts = []
        cache_service = get_post_cache_service()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.realtime_post_ttl_minutes)

        for post_data in bulk_data.posts:
            existing = await PostRepository.get_by_channel_telegram_id_and_message(
                session, bulk_data.channel_telegram_id, post_data.telegram_message_id
            )
            if existing:
                continue

            post = Post(
                channel_id=channel.id,
                telegram_message_id=post_data.telegram_message_id,
                media_type=post_data.media_type,
                media_file_id=post_data.media_file_id,
                posted_at=_normalize_datetime(post_data.posted_at),
                expires_at=expires_at,
            )
            session.add(post)
            created_posts.append((post, post_data))

        await session.flush()
        await session.commit()

        for post, post_data in created_posts:
            await session.refresh(post)
            if post_data.text or post_data.media_file_id:
                await cache_service.set_post_content(
                    post_id=post.id,
                    text=post_data.text,
                    media_type=post_data.media_type,
                    media_data=None,
                    ttl_seconds=settings.realtime_post_ttl_minutes * 60,
                )
                logger.debug(f"Cached post content in Redis (post_id={post.id}, has_text={post_data.text is not None})")

        logger.info(f"bulk_posts_created: count={len(created_posts)}, channel_id={channel.id}")
        return [post for post, _ in created_posts]
    except NotFoundError:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"bulk_posts_creation_failed: {str(e)}", exc_info=True)
        raise ValidationError(f"Failed to bulk create posts: {str(e)}")


async def _bulk_upsert_training_posts(
    session: AsyncSession, channel: Channel, bulk_data: PostBulkCreate
) -> List[Post]:
    """Create/update training metadata posts (no expires_at). Refreshes channel TTL in admin."""
    from app.services.post_cache_service import get_post_cache_service

    cache_service = get_post_cache_service()
    limit = settings.training_posts_per_channel_limit
    updated_or_created_ids = set()

    try:
        for post_data in bulk_data.posts:
            existing = await PostRepository.get_by_channel_and_message(
                session, channel.id, post_data.telegram_message_id
            )
            posted_at = _normalize_datetime(post_data.posted_at)
            if existing:
                existing.media_type = post_data.media_type
                existing.media_file_id = post_data.media_file_id
                existing.posted_at = posted_at
                existing.updated_at = datetime.now(timezone.utc)
                updated_or_created_ids.add(post_data.telegram_message_id)
            else:
                new_post = Post(
                    channel_id=channel.id,
                    telegram_message_id=post_data.telegram_message_id,
                    media_type=post_data.media_type,
                    media_file_id=post_data.media_file_id,
                    posted_at=posted_at,
                    # no expires_at = training metadata
                )
                session.add(new_post)
                updated_or_created_ids.add(post_data.telegram_message_id)

        await session.flush()

        all_posts_result = await session.execute(
            select(Post)
            .where(Post.channel_id == channel.id, Post.is_deleted == False)
            .order_by(Post.posted_at.desc())
        )
        all_posts = list(all_posts_result.scalars().all())
        if len(all_posts) > limit:
            posts_to_keep = all_posts[:limit]
            keep_ids = {p.id for p in posts_to_keep}
            for post in all_posts:
                if post.id not in keep_ids:
                    post.is_deleted = True
                    post.deleted_at = datetime.now(timezone.utc)

        await session.commit()

        for post_data in bulk_data.posts:
            post = await PostRepository.get_by_channel_and_message(
                session, channel.id, post_data.telegram_message_id
            )
            if post and (post_data.text or post_data.media_file_id):
                await cache_service.set_post_content(
                    post_id=post.id,
                    text=post_data.text,
                    media_type=post_data.media_type,
                    media_data=None,
                    ttl_seconds=settings.training_metadata_ttl_hours * 3600,
                )
        logger.info(f"bulk_training_posts_upserted: channel_id={channel.id}, count={len(updated_or_created_ids)}")
        all_posts_result2 = await session.execute(
            select(Post).where(Post.channel_id == channel.id, Post.is_deleted == False).order_by(Post.posted_at.desc())
        )
        return list(all_posts_result2.scalars().all())
    except Exception as e:
        await session.rollback()
        logger.error(f"bulk_training_posts_upsert_failed: {str(e)}", exc_info=True)
        raise ValidationError(f"Failed to bulk upsert training posts: {str(e)}")


async def _get_posts_by_channel_usernames(
    session: AsyncSession,
    channel_usernames: List[str],
    limit_per_channel: int
) -> List[PostWithChannel]:
    """Get posts from channels by usernames."""
    posts = []
    for username in channel_usernames:
        username_clean = username.lstrip("@").lower().strip()
        if not username_clean:
            continue

        channel = await ChannelRepository.get_by_username(session, username_clean)
        if not channel:
            continue

        result = await session.execute(
            select(Post, Channel)
            .join(Channel, Post.channel_id == Channel.id)
            .where(
                Post.channel_id == channel.id,
                Post.is_deleted == False,
                Channel.is_deleted == False
            )
            .order_by(Post.posted_at.desc())
            .limit(limit_per_channel)
        )
        for post, ch in result.all():
            posts.append(_post_to_post_with_channel(post, ch))
    return posts


async def _get_posts_from_user_channels(
    session: AsyncSession,
    user_telegram_id: int,
    limit: int
) -> List[PostWithChannel]:
    """Get posts from user's subscribed channels."""
    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    if not user:
        return []
    
    user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
    channel_ids = [uc.channel_id for uc in user_channels]
    
    if not channel_ids:
        return []
    
    result = await session.execute(
        select(Post, Channel)
        .join(Channel, Post.channel_id == Channel.id)
        .where(
            Post.channel_id.in_(channel_ids),
            Post.is_deleted == False,
            Channel.is_deleted == False
        )
        .order_by(Post.posted_at.desc())
        .limit(limit)
    )
    return [_post_to_post_with_channel(post, ch) for post, ch in result.all()]


async def _get_latest_posts_from_any_channel(
    session: AsyncSession,
    limit: int
) -> List[PostWithChannel]:
    """Get latest posts from any channel as fallback."""
    result = await session.execute(
        select(Post, Channel)
        .join(Channel, Post.channel_id == Channel.id)
        .where(
            Post.is_deleted == False,
            Channel.is_deleted == False
        )
        .order_by(Post.posted_at.desc())
        .limit(limit)
    )
    
    return [_post_to_post_with_channel(post, ch) for post, ch in result.all()]


async def _check_channel_metadata_freshness(
    session: AsyncSession,
    channel_id: int
) -> bool:
    """
    Check if channel has fresh training metadata (less than TTL hours old).
    
    Args:
        session: Database session
        channel_id: Channel ID
        
    Returns:
        True if metadata is fresh, False otherwise
    """
    ttl_hours = settings.training_metadata_ttl_hours
    threshold_time = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
    
    # Check if there are any posts created/updated after threshold
    result = await session.execute(
        select(func.count(Post.id))
        .where(
            Post.channel_id == channel_id,
            Post.is_deleted == False,
            Post.created_at >= threshold_time
        )
    )
    count = result.scalar() or 0
    
    # If there are fresh posts, metadata is fresh
    return count > 0


async def get_channel_usernames_needing_refresh(
    session: AsyncSession,
    channel_usernames: List[str],
) -> List[str]:
    """
    Return channel usernames that need scraping (not in DB or metadata older than TTL).
    Used by main-bot to skip scrape when posts are already fresh.
    """
    need_refresh: List[str] = []
    for raw in channel_usernames:
        username_clean = raw.lstrip("@").lower().strip()
        if not username_clean:
            continue
        channel = await ChannelRepository.get_by_username(session, username_clean)
        if not channel:
            need_refresh.append(f"@{username_clean}")
            continue
        is_fresh = await _check_channel_metadata_freshness(session, channel.id)
        if not is_fresh:
            need_refresh.append(f"@{username_clean}")
    return need_refresh


async def _update_channel_training_metadata(
    session: AsyncSession,
    channel: Channel,
    limit: int = 50
) -> bool:
    """
    Update training metadata for a channel by fetching from user-bot.
    
    Strategy:
    - Fetch up to limit posts from user-bot
    - Update existing posts by telegram_message_id
    - Add new posts
    - Remove oldest posts if total exceeds limit (keep only limit most recent)
    
    Args:
        session: Database session
        channel: Channel object
        limit: Maximum number of posts to keep
        
    Returns:
        True if successful, False otherwise
    """
    try:
        username = channel.username
        if not username:
            logger.warning(f"Cannot update metadata for channel {channel.id}: no username")
            return False
        
        # Request metadata from user-bot
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.user_bot_url}/cmd/scrape",
                json={
                    "channel_username": username,
                    "limit": limit,
                    "for_training": True,  # Don't store text, only metadata
                }
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get("success"):
                logger.error(f"User-bot scrape failed for {username}: {result.get('message')}")
                return False
            
            posts_data = result.get("posts", [])
            if not posts_data:
                logger.warning(f"No posts returned from user-bot for {username}")
                return False
        
        # Process posts: update existing or create new
        existing_message_ids = set()
        for post_data in posts_data:
            telegram_message_id = post_data.get("telegram_message_id")
            if not telegram_message_id:
                continue
            
            # Check if post already exists
            existing_post = await PostRepository.get_by_channel_and_message(
                session,
                channel.id,
                telegram_message_id
            )
            
            if existing_post:
                # Update existing post metadata (but keep text=null for training)
                existing_post.media_type = post_data.get("media_type")
                existing_post.media_file_id = post_data.get("media_file_id")
                existing_post.posted_at = datetime.fromisoformat(
                    post_data["posted_at"].replace("Z", "+00:00")
                ) if post_data.get("posted_at") else datetime.now(timezone.utc)
                # Note: text field removed from model - stored in Redis only
                existing_post.updated_at = datetime.now(timezone.utc)
                existing_message_ids.add(telegram_message_id)
            else:
                # Create new post with metadata only (text stored in Redis, not DB)
                posted_at = datetime.fromisoformat(
                    post_data["posted_at"].replace("Z", "+00:00")
                ) if post_data.get("posted_at") else datetime.now(timezone.utc)
                
                new_post = Post(
                    channel_id=channel.id,
                    telegram_message_id=telegram_message_id,
                    # Note: text field removed from model - stored in Redis only
                    media_type=post_data.get("media_type"),
                    media_file_id=post_data.get("media_file_id"),
                    posted_at=posted_at,
                )
                session.add(new_post)
                existing_message_ids.add(telegram_message_id)
        
        await session.flush()
        
        # Remove oldest posts if total exceeds limit
        # Get all posts for this channel (including ones we just added)
        all_posts_result = await session.execute(
            select(Post)
            .where(
                Post.channel_id == channel.id,
                Post.is_deleted == False
            )
            .order_by(Post.posted_at.desc())
        )
        all_posts = list(all_posts_result.scalars().all())
        
        if len(all_posts) > limit:
            # Keep only the limit most recent posts
            posts_to_keep = all_posts[:limit]
            posts_to_keep_ids = {p.id for p in posts_to_keep}
            
            # Soft delete the oldest posts
            for post in all_posts:
                if post.id not in posts_to_keep_ids:
                    post.is_deleted = True
                    post.deleted_at = datetime.now(timezone.utc)
        
        await session.commit()
        logger.info(f"Updated training metadata for channel {username} (channel_id={channel.id}): {len(existing_message_ids)} posts")
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating training metadata for channel {channel.username}: {e}", exc_info=True)
        return False


async def get_posts_for_training(
    session: AsyncSession,
    user_telegram_id: int,
    channel_usernames: List[str],
    limit_per_channel: int = 50,
) -> List[PostWithChannel]:
    """Get recent posts from channels for training.

    Strategy:
    1) For each channel, check if metadata is fresh (less than TTL hours old)
    2) If metadata is stale or missing, update it via user-bot
    3) Return posts with text from Redis cache
    4) Fallback to user's channels or any channels if needed
    """
    from app.services.post_cache_service import get_post_cache_service
    
    logger.info(f"get_posts_for_training: channels={channel_usernames}, limit_per_channel={limit_per_channel}")

    # Deterministic channel order: N1 queue then N2 queue (no interleaving)
    seen = set()
    channel_order: List[str] = []
    for u in channel_usernames:
        c = (u or "").strip().lstrip("@").lower()
        if c and c not in seen:
            seen.add(c)
            channel_order.append(c)
    channel_order.sort()

    posts = []
    metadata_limit = settings.training_posts_per_channel_limit

    for username_clean in channel_order:
        channel = await ChannelRepository.get_by_username(session, username_clean)
        if not channel:
            # Channel doesn't exist in DB, skip for now (could trigger creation, but that's handled elsewhere)
            continue
        
        # Check if metadata is fresh
        is_fresh = await _check_channel_metadata_freshness(session, channel.id)
        
        if not is_fresh:
            # Metadata is stale or missing, update it
            logger.info(f"Metadata stale for channel {username_clean}, updating...")
            await _update_channel_training_metadata(session, channel, metadata_limit)
        
        # Get fresh metadata posts — join on Post.channel_id so Channel is always the post's channel
        result = await session.execute(
            select(Post, Channel)
            .join(Channel, Post.channel_id == Channel.id)
            .where(
                Post.channel_id == channel.id,
                Post.is_deleted == False,
                Channel.is_deleted == False
            )
            .order_by(Post.posted_at.desc())
            .limit(limit_per_channel)
        )
        channel_post_ids = []
        for post, ch in result.all():
            post_with_channel = _post_to_post_with_channel(post, ch)
            posts.append(post_with_channel)
            channel_post_ids.append(post.id)
        logger.info(
            "[TRAINING_POSTS] channel=%s: limit_per_channel=%s, post_ids(count=%s)=%s",
            username_clean,
            limit_per_channel,
            len(channel_post_ids),
            channel_post_ids,
        )
    
    if not posts:
        limit = limit_per_channel * max(1, len(channel_order) or 1)
        posts = await _get_posts_from_user_channels(session, user_telegram_id, limit)
        if not posts:
            posts = await _get_latest_posts_from_any_channel(session, limit)

    all_post_ids = [p.id for p in posts]
    if posts:
        cache_service = get_post_cache_service()
        cached_contents = await cache_service.get_multiple_posts_content(all_post_ids)
        for post in posts:
            if post.id in cached_contents:
                content = cached_contents[post.id]
                post.text = content.get("text")

    logger.info(
        "[TRAINING_POSTS] returned pool: total=%s, post_ids=%s",
        len(posts),
        all_post_ids,
    )
    # No interleaving: order is already N1 then N2 (posts appended per channel above)
    return posts


async def get_user_interactions(
    session: AsyncSession,
    user_telegram_id: int
) -> List[dict]:
    """Get all interactions for a user."""
    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    if not user:
        return []
    
    interactions = await InteractionRepository.get_by_user_id(session, user.id)
    return [
        {
            "id": i.id,
            "post_id": i.post_id,
            "interaction_type": i.interaction_type.value,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in interactions
    ]


async def create_interaction(
    session: AsyncSession,
    interaction_data: InteractionCreate
) -> Optional[Interaction]:
    """Create a user interaction with a post."""
    try:
        user = await UserRepository.get_by_telegram_id(session, interaction_data.user_telegram_id)
        if not user:
            raise NotFoundError(f"User with telegram_id {interaction_data.user_telegram_id} not found")
        
        post = await PostRepository.get_by_id(session, interaction_data.post_id)
        if not post:
            raise NotFoundError(f"Post with id {interaction_data.post_id} not found")
        
        interaction = await InteractionRepository.create(
            session,
            user.id,
            post.id,
            interaction_data.interaction_type
        )
        await session.commit()
        await session.refresh(interaction)
        logger.info(
            f"interaction_created: interaction_id={interaction.id}, user_id={user.id}, post_id={post.id}"
        )
        from app.services.ml_client import on_user_interaction as ml_on_user_interaction
        await ml_on_user_interaction(interaction_data.user_telegram_id)
        return interaction
    except NotFoundError:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"interaction_creation_failed: {str(e)}", exc_info=True)
        raise ValidationError(f"Failed to create interaction: {str(e)}")


# Max candidates to fetch for scoring (ML predict is per-user, no DB relevance_score)
_MAX_FEED_CANDIDATES = 200


async def _get_candidate_posts_for_user(
    session: AsyncSession,
    user: User,
    fetch_limit: int,
    exclude_post_ids: Optional[List[int]] = None,
) -> List[dict]:
    """Get candidate posts from user's channels (no relevance_score). Scores come from ML predict on the fly."""
    user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
    channel_ids = [uc.channel_id for uc in user_channels]
    if not channel_ids:
        return []

    interactions = await InteractionRepository.get_by_user_id(session, user.id)
    interacted_post_ids = {i.post_id for i in interactions}
    excluded = set(exclude_post_ids or [])

    query = (
        select(Post, Channel)
        .join(Channel, Post.channel_id == Channel.id)
        .where(
            Post.channel_id.in_(channel_ids),
            Post.is_deleted == False,
            Channel.is_deleted == False,
        )
        .order_by(Post.posted_at.desc())
        .limit(_MAX_FEED_CANDIDATES)
    )
    result = await session.execute(query)
    candidates = []
    for post, channel in result.all():
        if post.id not in interacted_post_ids and post.id not in excluded:
            candidates.append({
                "post_id": post.id,
                "text": "",
                "score": 0.0,
                "post": post,
                "channel": channel,
            })
    return candidates


def _post_to_post_with_channel_with_score(post: Post, channel: Channel, score: Optional[float] = None) -> PostWithChannel:
    """Build PostWithChannel with optional score override (e.g. from ML predict)."""
    out = _post_to_post_with_channel(post, channel)
    if score is not None:
        out = out.model_copy(update={"relevance_score": score})
    return out


async def _build_post_with_channel_response(
    session: AsyncSession,
    candidate: dict,
    score_override: Optional[float] = None,
) -> Optional[PostWithChannel]:
    """Build PostWithChannel from candidate dict. Use score_override for feed (from ML predict)."""
    post = candidate.get("post") or await PostRepository.get_by_id(session, candidate["post_id"])
    channel = candidate.get("channel")
    if not post:
        return None
    if not channel:
        channel = await ChannelRepository.get_by_id(session, post.channel_id)
    if not channel:
        return None
    return _post_to_post_with_channel_with_score(post, channel, score_override)


async def get_best_posts_for_user(
    session: AsyncSession,
    user_telegram_id: int,
    limit: int = 1,
    exclude_post_ids: Optional[List[int]] = None,
) -> List[PostWithChannel]:
    """Get best posts for a user: candidates from user's channels, scored on the fly via ML predict (cosine similarity)."""
    from app.services.ml_client import predict as ml_predict

    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    if not user:
        return []

    user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
    channel_ids = [uc.channel_id for uc in user_channels]
    fetch_limit = limit * 3

    candidates = await _get_candidate_posts_for_user(
        session, user, fetch_limit, exclude_post_ids=exclude_post_ids
    )
    if not candidates:
        logger.info(
            f"get_best_posts: no candidates user_telegram_id={user_telegram_id} channel_ids={channel_ids} channel_count={len(channel_ids)}"
        )
        return []

    post_ids = [c["post_id"] for c in candidates]
    scores = await ml_predict(user_telegram_id, post_ids)
    for c in candidates:
        c["score"] = scores.get(c["post_id"], 0.0)
    score_list = [c["score"] for c in candidates]
    threshold = 0.3
    count_above = sum(1 for s in score_list if s >= threshold)
    score_min = min(score_list) if score_list else None
    score_max = max(score_list) if score_list else None
    score_mean = round(sum(score_list) / len(score_list), 4) if score_list else None
    logger.info(
        f"get_best_posts: user_telegram_id={user_telegram_id} candidates={len(candidates)} "
        f"score_min={score_min} score_max={score_max} score_mean={score_mean} count_above_{threshold}={count_above}"
    )
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:fetch_limit]

    posts = []
    for candidate in candidates[:limit]:
        post_with_channel = await _build_post_with_channel_response(
            session, candidate, score_override=candidate.get("score")
        )
        if post_with_channel:
            posts.append(post_with_channel)
    return posts


async def update_post_relevance(
    session: AsyncSession,
    post_id: int,
    relevance_score: float
) -> bool:
    """Update post's relevance score."""
    try:
        post = await PostRepository.update(session, post_id, relevance_score=relevance_score)
        if post:
            await session.commit()
            logger.info("post_relevance_updated", post_id=post_id, score=relevance_score)
            return True
        return False
    except Exception as e:
        await session.rollback()
        logger.error(f"post_relevance_update_failed: post_id={post_id}, error={str(e)}", exc_info=True)
        raise ValidationError(f"Failed to update post relevance: {str(e)}")


async def get_user_interaction_count(session: AsyncSession, user_telegram_id: int) -> int:
    """Get total number of interactions for a user."""
    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    if not user:
        return 0
    
    interactions = await InteractionRepository.get_by_user_id(session, user.id)
    return len(interactions)
