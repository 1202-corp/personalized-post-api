from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Post, Channel, Interaction, User, UserChannel
from app.schemas import PostCreate, PostBulkCreate, InteractionCreate, PostWithChannel


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
    result = await session.execute(
        select(Post).where(Post.id == post_id)
    )
    return result.scalar_one_or_none()


async def get_post_by_channel_and_message(
    session: AsyncSession,
    channel_telegram_id: int,
    telegram_message_id: int
) -> Optional[Post]:
    """Get post by channel and message ID."""
    result = await session.execute(
        select(Post)
        .join(Channel)
        .where(
            Channel.telegram_id == channel_telegram_id,
            Post.telegram_message_id == telegram_message_id
        )
    )
    return result.scalar_one_or_none()


async def create_post(session: AsyncSession, post_data: PostCreate) -> Optional[Post]:
    """Create a new post."""
    # Get channel
    channel_result = await session.execute(
        select(Channel).where(Channel.telegram_id == post_data.channel_telegram_id)
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        return None
    
    post = Post(
        channel_id=channel.id,
        telegram_message_id=post_data.telegram_message_id,
        text=post_data.text,
        media_type=post_data.media_type,
        media_file_id=post_data.media_file_id,
        posted_at=_normalize_datetime(post_data.posted_at),
    )
    session.add(post)
    await session.flush()
    return post


async def bulk_create_posts(session: AsyncSession, bulk_data: PostBulkCreate) -> List[Post]:
    """Bulk create posts for a channel."""
    # Get channel
    channel_result = await session.execute(
        select(Channel).where(Channel.telegram_id == bulk_data.channel_telegram_id)
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        return []
    
    created_posts = []
    for post_data in bulk_data.posts:
        # Check if post exists
        existing = await get_post_by_channel_and_message(
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
    return created_posts


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

        result = await session.execute(
            select(Post, Channel)
            .join(Channel)
            .where(func.lower(Channel.username) == username_clean)
            .order_by(Post.posted_at.desc())
            .limit(limit_per_channel)
        )

        for post, channel in result.all():
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
                    channel_username=channel.username,
                    channel_title=channel.title,
                )
            )

    if all_posts:
        return all_posts

    # --- 2) Fallback: posts from user's channels ---
    user_result = await session.execute(
        select(User).where(User.telegram_id == user_telegram_id)
    )
    user = user_result.scalar_one_or_none()

    if user:
        uc_result = await session.execute(
            select(UserChannel.channel_id).where(UserChannel.user_id == user.id)
        )
        channel_ids = [row[0] for row in uc_result.all()]

        if channel_ids:
            result = await session.execute(
                select(Post, Channel)
                .join(Channel)
                .where(Post.channel_id.in_(channel_ids))
                .order_by(Post.posted_at.desc())
                .limit(limit_per_channel * max(1, len(channel_usernames) or 1))
            )

            for post, channel in result.all():
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
                        channel_username=channel.username,
                        channel_title=channel.title,
                    )
                )

    if all_posts:
        return all_posts

    # --- 3) Ultimate fallback: latest posts from any channels ---
    result = await session.execute(
        select(Post, Channel)
        .join(Channel)
        .order_by(Post.posted_at.desc())
        .limit(limit_per_channel * max(1, len(channel_usernames) or 1))
    )

    for post, channel in result.all():
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
                channel_username=channel.username,
                channel_title=channel.title,
            )
        )

    return all_posts


async def get_user_interactions(
    session: AsyncSession,
    user_telegram_id: int
) -> List[dict]:
    """Get all interactions for a user."""
    user_result = await session.execute(
        select(User).where(User.telegram_id == user_telegram_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return []
    
    result = await session.execute(
        select(Interaction).where(Interaction.user_id == user.id)
    )
    interactions = result.scalars().all()
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
    # Get user
    user_result = await session.execute(
        select(User).where(User.telegram_id == interaction_data.user_telegram_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return None
    
    # Check if post exists
    post = await get_post_by_id(session, interaction_data.post_id)
    if not post:
        return None
    
    # Check for existing interaction
    existing = await session.execute(
        select(Interaction).where(
            Interaction.user_id == user.id,
            Interaction.post_id == post.id
        )
    )
    if existing.scalar_one_or_none():
        return None
    
    interaction = Interaction(
        user_id=user.id,
        post_id=post.id,
        interaction_type=interaction_data.interaction_type,
    )
    session.add(interaction)
    await session.flush()
    return interaction


async def get_best_posts_for_user(
    session: AsyncSession,
    user_telegram_id: int,
    limit: int = 1
) -> List[PostWithChannel]:
    """Get best (highest relevance) posts for a user that they haven't interacted with."""
    from app.services import ab_testing_service
    from app.services.ab_testing_service import RecommendationAlgorithm
    
    # Get user's interacted post IDs
    user_result = await session.execute(
        select(User).where(User.telegram_id == user_telegram_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return []
    
    interacted_ids = await session.execute(
        select(Interaction.post_id).where(Interaction.user_id == user.id)
    )
    interacted_post_ids = {row[0] for row in interacted_ids.all()}
    
    # Get user's channels
    user_channels = await session.execute(
        select(UserChannel.channel_id).where(UserChannel.user_id == user.id)
    )
    channel_ids = [row[0] for row in user_channels.all()]
    
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
            Post.relevance_score.isnot(None)
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
        post = item.get('post') or await get_post_by_id(session, item['post_id'])
        channel = item.get('channel')
        if not channel:
            channel_result = await session.execute(
                select(Channel).where(Channel.id == post.channel_id)
            )
            channel = channel_result.scalar_one_or_none()
        
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
    post = await get_post_by_id(session, post_id)
    if not post:
        return False
    post.relevance_score = relevance_score
    await session.flush()
    return True


async def get_user_interaction_count(session: AsyncSession, user_telegram_id: int) -> int:
    """Get total number of interactions for a user."""
    user_result = await session.execute(
        select(User).where(User.telegram_id == user_telegram_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return 0
    
    result = await session.execute(
        select(Interaction).where(Interaction.user_id == user.id)
    )
    return len(result.all())
