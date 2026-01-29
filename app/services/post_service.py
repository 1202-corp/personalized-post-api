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


async def get_post_by_channel_and_message(
    session: AsyncSession,
    channel_telegram_id: int,
    telegram_message_id: int
) -> Optional[Post]:
    """Get post by channel and message ID."""
    return await PostRepository.get_by_channel_telegram_id_and_message(
        session, channel_telegram_id, telegram_message_id
    )


async def create_post(session: AsyncSession, post_data: PostCreate) -> Optional[Post]:
    """Create a new post. Text and media are stored in Redis, not in DB."""
    from app.services.post_cache_service import get_post_cache_service
    
    try:
        channel = await ChannelRepository.get_by_telegram_id(session, post_data.channel_telegram_id)
        if not channel:
            raise NotFoundError(f"Channel with telegram_id {post_data.channel_telegram_id} not found")
        
        normalized_posted_at = _normalize_datetime(post_data.posted_at)
        
        # Create post (text is stored in Redis, not DB - field removed from model)
        post = Post(
            channel_id=channel.id,
            telegram_message_id=post_data.telegram_message_id,
            media_type=post_data.media_type,
            media_file_id=post_data.media_file_id,
            posted_at=normalized_posted_at,
        )
        session.add(post)
        await session.flush()
        await session.commit()
        await session.refresh(post)
        
        # Store text and media in Redis cache if provided
        # This ensures all users get content from Redis, not by requesting user-bot each time
        if post_data.text or post_data.media_file_id:
            cache_service = get_post_cache_service()
            await cache_service.set_post_content(
                post_id=post.id,
                text=post_data.text,
                media_type=post_data.media_type,
                media_data=None  # Media data (bytes) should be fetched and cached separately via user-bot if needed
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
    """Bulk create posts for a channel. Text and media are stored in Redis, not in DB."""
    from app.services.post_cache_service import get_post_cache_service
    
    try:
        channel = await ChannelRepository.get_by_telegram_id(session, bulk_data.channel_telegram_id)
        if not channel:
            raise NotFoundError(f"Channel with telegram_id {bulk_data.channel_telegram_id} not found")
        
        created_posts = []
        cache_service = get_post_cache_service()
        
        for post_data in bulk_data.posts:
            existing = await PostRepository.get_by_channel_telegram_id_and_message(
                session, bulk_data.channel_telegram_id, post_data.telegram_message_id
            )
            if existing:
                continue
            
            # Create post (text is stored in Redis, not DB - field removed from model)
            post = Post(
                channel_id=channel.id,
                telegram_message_id=post_data.telegram_message_id,
                media_type=post_data.media_type,
                media_file_id=post_data.media_file_id,
                posted_at=_normalize_datetime(post_data.posted_at),
            )
            session.add(post)
            created_posts.append((post, post_data))  # Store post_data for Redis caching
        
        await session.flush()
        await session.commit()
        
        # Store text and media in Redis cache for each created post
        # This ensures all users get content from Redis, not by requesting user-bot each time
        for post, post_data in created_posts:
            await session.refresh(post)
            if post_data.text or post_data.media_file_id:
                await cache_service.set_post_content(
                    post_id=post.id,
                    text=post_data.text,
                    media_type=post_data.media_type,
                    media_data=None  # Media data (bytes) should be fetched and cached separately via user-bot if needed
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
            .join(Channel)
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
        .join(Channel)
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
        .join(Channel)
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
    limit_per_channel: int = 7,
) -> List[PostWithChannel]:
    """Get recent posts from channels for training.

    Strategy:
    1) For each channel, check if metadata is fresh (less than TTL hours old)
    2) If metadata is stale or missing, update it via user-bot
    3) Return posts with text from Redis cache
    4) Fallback to user's channels or any channels if needed
    """
    from app.services.post_cache_service import get_post_cache_service
    
    posts = []
    metadata_limit = settings.training_posts_per_channel_limit
    
    # Process each channel username
    for username in channel_usernames:
        username_clean = username.lstrip("@").lower().strip()
        if not username_clean:
            continue
        
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
        
        # Get fresh metadata posts
        result = await session.execute(
            select(Post, Channel)
            .join(Channel)
            .where(
                Post.channel_id == channel.id,
                Post.is_deleted == False,
                Channel.is_deleted == False
            )
            .order_by(Post.posted_at.desc())
            .limit(limit_per_channel)
        )
        
        for post, ch in result.all():
            post_with_channel = _post_to_post_with_channel(post, ch)
            posts.append(post_with_channel)
    
    if not posts:
        # Fallback: posts from user's channels
        limit = limit_per_channel * max(1, len(channel_usernames) or 1)
        posts = await _get_posts_from_user_channels(session, user_telegram_id, limit)
        
        if not posts:
            # Ultimate fallback: latest posts from any channels
            posts = await _get_latest_posts_from_any_channel(session, limit)
    
    # Enrich posts with text from Redis cache
    if posts:
        cache_service = get_post_cache_service()
        post_ids = [p.id for p in posts]
        cached_contents = await cache_service.get_multiple_posts_content(post_ids)
        
        for post in posts:
            if post.id in cached_contents:
                content = cached_contents[post.id]
                post.text = content.get("text")
    
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
        return interaction
    except NotFoundError:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"interaction_creation_failed: {str(e)}", exc_info=True)
        raise ValidationError(f"Failed to create interaction: {str(e)}")


async def _get_candidate_posts_for_user(
    session: AsyncSession,
    user: User,
    fetch_limit: int
) -> List[dict]:
    """Get candidate posts for recommendation scoring."""
    user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
    channel_ids = [uc.channel_id for uc in user_channels]
    
    if not channel_ids:
        return []
    
    interactions = await InteractionRepository.get_by_user_id(session, user.id)
    interacted_post_ids = {i.post_id for i in interactions}
    
    query = (
        select(Post, Channel)
        .join(Channel)
        .where(
            Post.channel_id.in_(channel_ids),
            Post.relevance_score.isnot(None),
            Post.is_deleted == False,
            Channel.is_deleted == False
        )
        .order_by(Post.relevance_score.desc())
        .limit(fetch_limit)
    )
    
    result = await session.execute(query)
    candidates = []
    
    for post, channel in result.all():
        if post.id not in interacted_post_ids:
            candidates.append({
                'post_id': post.id,
                'text': '',  # Text stored in Redis, not DB - fetch separately if needed
                'score': post.relevance_score or 0,
                'post': post,
                'channel': channel,
            })
    
    return candidates


async def _build_post_with_channel_response(
    session: AsyncSession,
    candidate: dict
) -> Optional[PostWithChannel]:
    """Build PostWithChannel from candidate dict."""
    post = candidate.get('post') or await PostRepository.get_by_id(session, candidate['post_id'])
    channel = candidate.get('channel')
    
    if not post:
        return None
    
    if not channel:
        channel = await ChannelRepository.get_by_id(session, post.channel_id)
    
    if not channel:
        return None
    
    return _post_to_post_with_channel(post, channel)


async def get_best_posts_for_user(
    session: AsyncSession,
    user_telegram_id: int,
    limit: int = 1
) -> List[PostWithChannel]:
    """Get best (highest relevance) posts for a user that they haven't interacted with."""
    from app.services import ab_testing_service
    from app.services.ab_testing_service import RecommendationAlgorithm
    
    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    if not user:
        return []
    
    algorithm = ab_testing_service.get_algorithm_for_user(user_telegram_id)
    use_llm_reranker = algorithm == RecommendationAlgorithm.LLM_RERANKER
    
    fetch_limit = limit * 5 if use_llm_reranker else limit * 3
    candidates = await _get_candidate_posts_for_user(session, user, fetch_limit)
    
    if not candidates:
        return []
    
    # Apply LLM reranking if enabled
    if use_llm_reranker:
        from app.services import llm_reranker_service
        candidates = await llm_reranker_service.get_reranked_recommendations(
            session, user_telegram_id, candidates, limit=limit
        )
    
    # Build response
    posts = []
    for candidate in candidates[:limit]:
        post_with_channel = await _build_post_with_channel_response(session, candidate)
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
