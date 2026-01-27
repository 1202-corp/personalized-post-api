"""Post business logic service."""
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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

logger = get_logger(__name__)


def _normalize_datetime(dt: datetime) -> datetime:
    """Convert aware datetimes to naive UTC to satisfy TIMESTAMP WITHOUT TIME ZONE."""
    if dt is None:
        return dt
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _post_to_post_with_channel(post: Post, channel: Channel) -> PostWithChannel:
    """Convert Post and Channel to PostWithChannel schema."""
    return PostWithChannel(
        id=post.id,
        telegram_message_id=post.telegram_message_id,
        text=post.text,
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
    """Create a new post."""
    try:
        channel = await ChannelRepository.get_by_telegram_id(session, post_data.channel_telegram_id)
        if not channel:
            raise NotFoundError(f"Channel with telegram_id {post_data.channel_telegram_id} not found")
        
        normalized_posted_at = _normalize_datetime(post_data.posted_at)
        
        post = Post(
            channel_id=channel.id,
            telegram_message_id=post_data.telegram_message_id,
            text=post_data.text,
            media_type=post_data.media_type,
            media_file_id=post_data.media_file_id,
            posted_at=normalized_posted_at,
        )
        session.add(post)
        await session.flush()
        await session.commit()
        await session.refresh(post)
        logger.info(f"post_created: post_id={post.id}, channel_id={channel.id}")
        return post
    except NotFoundError:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"post_creation_failed: {str(e)}", exc_info=True)
        raise ValidationError(f"Failed to create post: {str(e)}")


async def bulk_create_posts(session: AsyncSession, bulk_data: PostBulkCreate) -> List[Post]:
    """Bulk create posts for a channel."""
    try:
        channel = await ChannelRepository.get_by_telegram_id(session, bulk_data.channel_telegram_id)
        if not channel:
            raise NotFoundError(f"Channel with telegram_id {bulk_data.channel_telegram_id} not found")
        
        created_posts = []
        for post_data in bulk_data.posts:
            existing = await PostRepository.get_by_channel_telegram_id_and_message(
                session, bulk_data.channel_telegram_id, post_data.telegram_message_id
            )
            if existing:
                continue
            
            post = Post(
                channel_id=channel.id,
                telegram_message_id=post_data.telegram_message_id,
                text=post_data.text,
                media_type=post_data.media_type,
                media_file_id=post_data.media_file_id,
                posted_at=_normalize_datetime(post_data.posted_at),
            )
            session.add(post)
            created_posts.append(post)
        
        await session.flush()
        await session.commit()
        for post in created_posts:
            await session.refresh(post)
        logger.info(f"bulk_posts_created: count={len(created_posts)}, channel_id={channel.id}")
        return created_posts
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


async def get_posts_for_training(
    session: AsyncSession,
    user_telegram_id: int,
    channel_usernames: List[str],
    limit_per_channel: int = 7,
) -> List[PostWithChannel]:
    """Get recent posts from channels for training.

    Strategy:
    1) Try to get posts by the provided channel usernames.
    2) If nothing found, fallback to posts from the user's channels.
    3) If still nothing, fallback to latest posts from any channel.
    """
    # Primary: by explicit channel usernames
    posts = await _get_posts_by_channel_usernames(session, channel_usernames, limit_per_channel)
    if posts:
        return posts
    
    # Fallback: posts from user's channels
    limit = limit_per_channel * max(1, len(channel_usernames) or 1)
    posts = await _get_posts_from_user_channels(session, user_telegram_id, limit)
    if posts:
        return posts
    
    # Ultimate fallback: latest posts from any channels
    return await _get_latest_posts_from_any_channel(session, limit)


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
                'text': post.text or '',
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
