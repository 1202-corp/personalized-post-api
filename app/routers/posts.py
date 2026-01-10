from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.schemas import (
    PostCreate, PostResponse, PostBulkCreate, PostWithChannel,
    InteractionCreate, InteractionResponse,
    TrainingPostsRequest, BestPostRequest, BestPostResponse
)
from app.services import post_service

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new post."""
    post = await post_service.create_post(session, post_data)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create post (channel not found)"
        )
    return post


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_create_posts(
    bulk_data: PostBulkCreate,
    session: AsyncSession = Depends(get_session)
):
    """Bulk create posts for a channel."""
    posts = await post_service.bulk_create_posts(session, bulk_data)
    return {"created_count": len(posts), "post_ids": [p.id for p in posts]}


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


@router.post("/training", response_model=List[PostWithChannel])
async def get_training_posts(
    request: TrainingPostsRequest,
    session: AsyncSession = Depends(get_session)
):
    """Get posts for training from specified channels."""
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
    interaction = await post_service.create_interaction(session, interaction_data)
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create interaction (user/post not found or already exists)"
        )
    return interaction


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
    """Get best (highest relevance) posts for a user."""
    posts = await post_service.get_best_posts_for_user(
        session,
        request.user_telegram_id,
        request.limit
    )
    return BestPostResponse(posts=posts)
