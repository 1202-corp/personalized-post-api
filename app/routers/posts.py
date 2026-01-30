from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.schemas import (
    PostCreate, PostResponse, PostUpdate, PostBulkCreate, PostWithChannel,
    InteractionCreate, InteractionResponse,
    TrainingPostsRequest, BestPostRequest, BestPostResponse
)
from app.services import post_service
from app.repositories.post_repository import PostRepository

router = APIRouter(prefix="/posts", tags=["posts"])


# ============== List/Create ==============

@router.get("/", response_model=List[PostResponse])
async def list_posts(
    skip: int = 0,
    limit: int = 50,
    channel_id: Optional[int] = Query(None, description="Filter by channel ID"),
    session: AsyncSession = Depends(get_session)
):
    """
    List all posts with pagination.
    
    Returns a paginated list of posts. Optionally filter by channel ID.
    
    **Parameters:**
    - `skip`: Number of posts to skip (default: 0)
    - `limit`: Maximum number of posts to return (default: 50)
    - `channel_id`: Optional channel ID to filter posts (query parameter)
    
    **Example Request (All Posts):**
    ```
    GET /api/v1/posts/?skip=0&limit=10
    ```
    
    **Example Request (Filtered by Channel):**
    ```
    GET /api/v1/posts/?channel_id=1&skip=0&limit=10
    ```
    
    **Example Response:**
    ```json
    [
        {
            "id": 1,
            "channel_id": 1,
            "telegram_message_id": 12345,
            "text": "Post content here",
            "media_type": "photo",
            "media_file_id": "123,456",
            "posted_at": "2024-01-01T12:00:00",
            "relevance_score": 0.85,
            "created_at": "2024-01-01T12:00:00"
        }
    ]
    ```
    """
    if channel_id:
        posts = await PostRepository.get_all_by_channel(session, channel_id)
    else:
        posts = await PostRepository.get_all(session)
    paginated_posts = posts[skip:skip + limit]
    return paginated_posts


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new post."""
    from app.exceptions import NotFoundError, ValidationError
    try:
        post = await post_service.create_post(session, post_data)
        return post
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============== Specific endpoints (before parameterized routes) ==============

@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_create_posts(
    bulk_data: PostBulkCreate,
    session: AsyncSession = Depends(get_session)
):
    """Bulk create posts for a channel."""
    from app.exceptions import NotFoundError, ValidationError
    try:
        posts = await post_service.bulk_create_posts(session, bulk_data)
        return {"created_count": len(posts), "post_ids": [p.id for p in posts]}
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/training", response_model=List[PostWithChannel])
async def get_training_posts(
    request: TrainingPostsRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Get posts metadata for training from specified channels.
    
    **Allowed only when user status is TRAINING** (MiniApp/chat training in progress).
    Returns 403 if user is not in training — ensures posts are from the current session only.
    
    Retrieves recent posts metadata (without text content) from specified channels for user training.
    Falls back to user's subscribed channels if specified channels have no posts.
    
    **Important:** This endpoint returns only metadata (IDs, media_type, media_file_id, posted_at).
    Text and media content are stored in Redis cache and should be fetched separately.
    The `text` field in the response is always `null` for training posts.
    
    **Request Body:**
    ```json
    {
        "user_telegram_id": 123456789,
        "channel_usernames": ["@durov", "@telegram"],
        "posts_per_channel": 7
    }
    ```
    """
    from app.repositories.user_repository import UserRepository
    from app.models import UserStatus

    user = await UserRepository.get_by_telegram_id(session, request.user_telegram_id)
    if not user or user.status != UserStatus.TRAINING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Training posts are only available when training is in progress. Start training from the bot first.",
        )
    posts = await post_service.get_posts_for_training(
        session,
        request.user_telegram_id,
        request.channel_usernames,
        request.posts_per_channel,
    )
    return posts


@router.post("/interactions", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    interaction_data: InteractionCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a user interaction with a post."""
    from app.exceptions import NotFoundError, ValidationError
    try:
        interaction = await post_service.create_interaction(session, interaction_data)
        return interaction
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/interactions/{telegram_id}")
async def get_user_interactions(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get all interactions for a user."""
    interactions = await post_service.get_user_interactions(session, telegram_id)
    return interactions


@router.post("/best", response_model=BestPostResponse)
async def get_best_posts(
    request: BestPostRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Get best (highest relevance) posts for a user.
    
    Returns personalized posts with highest relevance scores for the user.
    Uses A/B testing algorithm selection (cosine similarity or LLM reranker).
    Excludes posts the user has already interacted with.
    
    **Request Body:**
    ```json
    {
        "user_telegram_id": 123456789,
        "limit": 10
    }
    ```
    
    **Example Response:**
    ```json
    {
        "posts": [
            {
                "id": 42,
                "channel_id": 1,
                "telegram_message_id": 12345,
                "text": "Recommended post",
                "media_type": "photo",
                "posted_at": "2024-01-01T12:00:00",
                "relevance_score": 0.95,
                "created_at": "2024-01-01T12:00:00",
                "channel_username": "example",
                "channel_title": "Example Channel"
            }
        ]
    }
    ```
    """
    posts = await post_service.get_best_posts_for_user(
        session,
        request.user_telegram_id,
        request.limit,
        exclude_post_ids=request.exclude_post_ids,
    )
    return BestPostResponse(posts=posts)


# ============== Parameterized routes ==============

@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get post by ID."""
    post = await post_service.get_post_by_id(session, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return post


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int,
    post_update: PostUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update post fields. Text is stored in Redis, not in DB."""
    from app.services.post_cache_service import get_post_cache_service
    
    update_data = post_update.model_dump(exclude_unset=True)
    
    # Extract text from update_data - it should go to Redis, not DB
    text_to_cache = update_data.pop('text', None)
    
    # Update post fields (excluding text)
    post = await PostRepository.update(session, post_id, **update_data)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Store text in Redis if provided
    if text_to_cache is not None:
        cache_service = get_post_cache_service()
        await cache_service.set_post_content(
            post_id=post_id,
            text=text_to_cache,
            media_type=update_data.get('media_type'),
            media_data=None  # Media data should be handled separately if needed
        )
    
    await session.commit()
    await session.refresh(post)
    return post


@router.get("/{post_id}/content")
async def get_post_content(
    post_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Get post content (text and media) from Redis cache.
    If not in cache, fetch from user-bot, store in Redis, then return.
    """
    from app.services.post_cache_service import get_post_cache_service
    from app.repositories.post_repository import PostRepository
    from app.repositories.channel_repository import ChannelRepository
    from app.config import get_settings
    import httpx

    post = await PostRepository.get_by_id(session, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )

    cache_service = get_post_cache_service()
    content = await cache_service.get_post_content(post_id)

    if not content:
        # Fetch from user-bot, then cache and return
        channel = await ChannelRepository.get_by_id(session, post.channel_id)
        if not channel or not (channel.username or getattr(channel, "telegram_id", None)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post content not found (channel missing)"
            )
        channel_username = (channel.username or "").strip() or f"id{channel.telegram_id}"
        if not channel_username.startswith("@"):
            channel_username = f"@{channel_username}"
        from app.config import get_settings
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{settings.user_bot_url.rstrip('/')}/media/full",
                    params={
                        "channel_username": channel_username,
                        "message_id": post.telegram_message_id,
                    },
                )
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Post content not found (fetch failed)"
                    )
                data = resp.json()
                text = data.get("text")
                media_type = data.get("media_type")
                await cache_service.set_post_content(
                    post_id=post_id,
                    text=text,
                    media_type=media_type,
                    media_data=None,
                )
                content = await cache_service.get_post_content(post_id)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post content not found (fetch failed)"
            )

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post content not found in cache"
        )

    return content


@router.get("/{post_id}/recipients")
async def get_post_recipients(
    post_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Post-centric delivery: return telegram_ids of users who should receive this post.
    Uses taste clusters and mailing_enabled for the post's channel.
    """
    from app.repositories.post_repository import PostRepository
    from app.services.post_cache_service import get_post_cache_service
    from app.services.ml_client import get_post_recipients as ml_get_post_recipients

    from app.logging_config import get_logger
    logger = get_logger(__name__)
    
    logger.info(f"[API_POST_RECIPIENTS] Запрос получателей для post_id={post_id}")
    post = await PostRepository.get_by_id(session, post_id)
    if not post:
        logger.warning(f"[API_POST_RECIPIENTS] post_id={post_id}: пост не найден")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    cache_service = get_post_cache_service()
    content = await cache_service.get_post_content(post_id)
    text = content.get("text") if isinstance(content, dict) else None
    logger.info(f"[API_POST_RECIPIENTS] post_id={post_id}: текст из кеша: {text[:100] if text else None!r}")
    telegram_ids = await ml_get_post_recipients(post_id, text=text)
    logger.info(f"[API_POST_RECIPIENTS] post_id={post_id}: ML service вернул {len(telegram_ids)} получателей")
    return {"telegram_ids": telegram_ids}


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    hard: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """Delete a post (soft delete by default, hard delete if hard=true)."""
    post = await PostRepository.delete(session, post_id, hard=hard)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    await session.commit()
