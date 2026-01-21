"""Post business logic service."""
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.post import Post
from app.models.channel import Channel
from app.models.interaction import Interaction, InteractionType
from app.models.user import User
from app.models.user_channel import UserChannel
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
    """Convert aware datetimes to naive UTC to satisfy TIMESTAMP WITHOUT TIME ZONE.

    asyncpg raises `TypeError: can't subtract offset-naive and offset-aware datetimes`
    if we pass tz-aware datetimes into a naive timestamp column.
    """
    if dt is None:
        return dt
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt
    # convert to UTC and drop tzinfo
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


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
        
        # Normalize datetime
        normalized_posted_at = _normalize_datetime(post_data.posted_at)
        
        # Create Post object manually since repository expects channel_id
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
        logger.info("post_created", post_id=post.id, channel_id=channel.id)
        return post
    except NotFoundError:
        raise
    except Exception as e:
        await session.rollback()
        logger.error("post_creation_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to create post: {str(e)}")


async def bulk_create_posts(session: AsyncSession, bulk_data: PostBulkCreate) -> List[Post]:
    """Bulk create posts for a channel."""
    try:
        channel = await ChannelRepository.get_by_telegram_id(session, bulk_data.channel_telegram_id)
        if not channel:
            raise NotFoundError(f"Channel with telegram_id {bulk_data.channel_telegram_id} not found")
        
        created_posts = []
        for post_data in bulk_data.posts:
            # Check if post exists
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
        logger.info("bulk_posts_created", count=len(created_posts), channel_id=channel.id)
        return created_posts
    except NotFoundError:
        raise
    except Exception as e:
        await session.rollback()
        logger.error("bulk_posts_creation_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to bulk create posts: {str(e)}")


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
    all_posts: List[PostWithChannel] = []

    # --- 1) Primary: by explicit channel usernames ---
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
            all_posts.append(
                PostWithChannel(
                    id=post.id,
                    telegram_message_id=post.telegram_message_id,
                    text=post.text,
                    media_type=post.media_type,
                    media_file_id=post.media_file_id,
                    posted_at=post.posted_at,
                    channel_id=post.channel_id,
                    relevance_score=post.relevance_score,
                    created_at=post.created_at,
                    channel_username=ch.username,
                    channel_title=ch.title,
                )
            )

    if all_posts:
        return all_posts

    # --- 2) Fallback: posts from user's channels ---
    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    if user:
        user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
        channel_ids = [uc.channel_id for uc in user_channels]

        if channel_ids:
            result = await session.execute(
                select(Post, Channel)
                .join(Channel)
                .where(
                    Post.channel_id.in_(channel_ids),
                    Post.is_deleted == False,
                    Channel.is_deleted == False
                )
                .order_by(Post.posted_at.desc())
                .limit(limit_per_channel * max(1, len(channel_usernames) or 1))
            )

            for post, ch in result.all():
                all_posts.append(
                    PostWithChannel(
                        id=post.id,
                        telegram_message_id=post.telegram_message_id,
                        text=post.text,
                        media_type=post.media_type,
                        media_file_id=post.media_file_id,
                        posted_at=post.posted_at,
                        channel_id=post.channel_id,
                        relevance_score=post.relevance_score,
                        created_at=post.created_at,
                        channel_username=ch.username,
                        channel_title=ch.title,
                    )
                )

    if all_posts:
        return all_posts

    # --- 3) Ultimate fallback: latest posts from any channels ---
    result = await session.execute(
        select(Post, Channel)
        .join(Channel)
        .where(
            Post.is_deleted == False,
            Channel.is_deleted == False
        )
        .order_by(Post.posted_at.desc())
        .limit(limit_per_channel * max(1, len(channel_usernames) or 1))
    )

    for post, ch in result.all():
        all_posts.append(
            PostWithChannel(
                id=post.id,
                telegram_message_id=post.telegram_message_id,
                text=post.text,
                media_type=post.media_type,
                media_file_id=post.media_file_id,
                posted_at=post.posted_at,
                channel_id=post.channel_id,
                relevance_score=post.relevance_score,
                created_at=post.created_at,
                channel_username=ch.username,
                channel_title=ch.title,
            )
        )

    return all_posts


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
            "interaction_type": i.interaction_type.value if hasattr(i.interaction_type, 'value') else i.interaction_type,
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
            "interaction_created",
            interaction_id=interaction.id,
            user_id=user.id,
            post_id=post.id
        )
        return interaction
    except NotFoundError:
        raise
    except Exception as e:
        await session.rollback()
        logger.error("interaction_creation_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to create interaction: {str(e)}")


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
    
    # Get user's interacted post IDs
    interactions = await InteractionRepository.get_by_user_id(session, user.id)
    interacted_post_ids = {i.post_id for i in interactions}
    
    # Get user's channels
    user_channels = await UserChannelRepository.get_by_user_id(session, user.id)
    channel_ids = [uc.channel_id for uc in user_channels]
    
    if not channel_ids:
        return []
    
    # Check if user is in LLM reranker treatment group
    algorithm = ab_testing_service.get_algorithm_for_user(user_telegram_id)
    use_llm_reranker = algorithm == RecommendationAlgorithm.LLM_RERANKER
    
    # Get more candidates for LLM reranking
    fetch_limit = limit * 5 if use_llm_reranker else limit * 3
    
    # Get best uninteracted posts
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
    
    # Apply LLM reranking if enabled for this user
    if use_llm_reranker and len(candidates) > 0:
        from app.services import llm_reranker_service
        reranked = await llm_reranker_service.get_reranked_recommendations(
            session, user_telegram_id, candidates, limit=limit
        )
        # Use reranked order
        candidates = reranked
    
    # Build response
    posts = []
    for item in candidates[:limit]:
        post = item.get('post') or await PostRepository.get_by_id(session, item['post_id'])
        channel = item.get('channel')
        if not channel and post:
            channel = await ChannelRepository.get_by_id(session, post.channel_id)
        
        if post and channel:
            posts.append(PostWithChannel(
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
            ))
    
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
        logger.error("post_relevance_update_failed", error=str(e), post_id=post_id, exc_info=True)
        raise ValidationError(f"Failed to update post relevance: {str(e)}")


async def get_user_interaction_count(session: AsyncSession, user_telegram_id: int) -> int:
    """Get total number of interactions for a user."""
    user = await UserRepository.get_by_telegram_id(session, user_telegram_id)
    if not user:
        return 0
    
    interactions = await InteractionRepository.get_by_user_id(session, user.id)
    return len(interactions)
