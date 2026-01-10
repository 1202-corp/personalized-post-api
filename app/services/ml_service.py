"""
ML Service - Real implementation using embeddings and Qdrant vector search.
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import post_service, user_service
from app.services import embedding_service, qdrant_service
from app.models import UserStatus, Post, Channel, Interaction, User, InteractionType
from app.schemas import UserUpdate

logger = logging.getLogger(__name__)
settings = get_settings()

# Minimum interactions required for training
MIN_INTERACTIONS_FOR_TRAINING = 5


async def train_model(session: AsyncSession, user_telegram_id: int) -> tuple[bool, str, float]:
    """
    Train ML model for a user using embeddings and Qdrant.
    
    Process:
    1. Get user's liked and disliked posts
    2. Generate embeddings for posts that don't have them
    3. Store embeddings in Qdrant
    4. Compute user preference vector
    5. Calculate relevance scores for all posts in user's channels
    
    Returns (success, message, training_time).
    """
    start_time = time.time()
    
    # Check if user has enough interactions
    interaction_count = await post_service.get_user_interaction_count(session, user_telegram_id)
    
    if interaction_count < MIN_INTERACTIONS_FOR_TRAINING:
        training_time = time.time() - start_time
        return False, f"Need at least {MIN_INTERACTIONS_FOR_TRAINING} interactions, got {interaction_count}", training_time
    
    try:
        # Get user
        user = await user_service.get_user_by_telegram_id(session, user_telegram_id)
        if not user:
            return False, "User not found", time.time() - start_time
        
        # Get user's interactions with posts
        liked_posts, disliked_posts = await _get_user_interaction_posts(session, user.id)
        
        # Generate and store embeddings for all interacted posts
        all_posts = liked_posts + disliked_posts
        await _ensure_post_embeddings(session, all_posts)
        
        # Get embeddings for liked and disliked posts
        liked_embeddings = await _get_embeddings_for_posts([p.id for p in liked_posts])
        disliked_embeddings = await _get_embeddings_for_posts([p.id for p in disliked_posts])
        
        # Compute user preference vector
        preference_vector = await qdrant_service.get_user_preference_vector(
            liked_embeddings,
            disliked_embeddings if disliked_embeddings else None
        )
        
        if not preference_vector:
            return False, "Could not compute preference vector", time.time() - start_time
        
        # Get all posts from user's channels and score them
        await _score_user_channel_posts(session, user_telegram_id, preference_vector)
        
        # Update user status
        await user_service.update_user(
            session,
            user_telegram_id,
            UserUpdate(status=UserStatus.TRAINED, is_trained=True)
        )
        
        training_time = time.time() - start_time
        logger.info(f"Training completed for user {user_telegram_id} in {training_time:.2f}s")
        
        return True, "Model trained successfully", training_time
        
    except Exception as e:
        logger.error(f"Training failed for user {user_telegram_id}: {e}")
        return False, f"Training failed: {str(e)}", time.time() - start_time


async def predict(
    session: AsyncSession,
    user_telegram_id: int,
    post_ids: List[int]
) -> Dict[int, float]:
    """
    Get relevance predictions for specific posts.
    Uses user's preference vector and post embeddings.
    """
    try:
        user = await user_service.get_user_by_telegram_id(session, user_telegram_id)
        if not user:
            return {}
        
        # Get user's liked posts for preference vector
        liked_posts, disliked_posts = await _get_user_interaction_posts(session, user.id)
        
        liked_embeddings = await _get_embeddings_for_posts([p.id for p in liked_posts])
        disliked_embeddings = await _get_embeddings_for_posts([p.id for p in disliked_posts])
        
        preference_vector = await qdrant_service.get_user_preference_vector(
            liked_embeddings,
            disliked_embeddings if disliked_embeddings else None
        )
        
        if not preference_vector:
            # Fallback to neutral scores
            return {pid: 0.5 for pid in post_ids}
        
        # Get posts and ensure they have embeddings
        posts = []
        for post_id in post_ids:
            post = await post_service.get_post_by_id(session, post_id)
            if post:
                posts.append(post)
        
        await _ensure_post_embeddings(session, posts)
        
        # Calculate similarity scores
        predictions = {}
        post_embeddings = await qdrant_service.get_post_embeddings_batch(post_ids)
        
        for post_id in post_ids:
            if post_id in post_embeddings:
                score = _cosine_similarity(preference_vector, post_embeddings[post_id])
                # Normalize to 0-1 range (cosine similarity is -1 to 1)
                score = (score + 1) / 2
                predictions[post_id] = round(score, 4)
                
                # Update post relevance in DB
                await post_service.update_post_relevance(session, post_id, score)
            else:
                predictions[post_id] = 0.5
        
        return predictions
        
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        return {pid: 0.5 for pid in post_ids}


async def get_recommended_posts(
    session: AsyncSession,
    user_telegram_id: int,
    limit: int = 10,
    exclude_interacted: bool = True
) -> List[Dict]:
    """
    Get recommended posts for user using vector similarity search.
    """
    try:
        user = await user_service.get_user_by_telegram_id(session, user_telegram_id)
        if not user:
            return []
        
        # Get user's liked posts for preference vector
        liked_posts, disliked_posts = await _get_user_interaction_posts(session, user.id)
        
        if not liked_posts:
            # No liked posts yet - return recent posts
            return []
        
        liked_embeddings = await _get_embeddings_for_posts([p.id for p in liked_posts])
        disliked_embeddings = await _get_embeddings_for_posts([p.id for p in disliked_posts])
        
        preference_vector = await qdrant_service.get_user_preference_vector(
            liked_embeddings,
            disliked_embeddings if disliked_embeddings else None
        )
        
        if not preference_vector:
            return []
        
        # Get IDs of posts to exclude
        exclude_ids = set()
        if exclude_interacted:
            result = await session.execute(
                select(Interaction.post_id).where(Interaction.user_id == user.id)
            )
            exclude_ids = {row[0] for row in result.all()}
        
        # Search for similar posts
        results = await qdrant_service.search_similar_posts(
            query_vector=preference_vector,
            limit=limit + len(exclude_ids),  # Get extra to filter
            score_threshold=0.3,
        )
        
        # Filter and return
        recommended = []
        for r in results:
            if r['id'] not in exclude_ids and len(recommended) < limit:
                recommended.append({
                    'post_id': r['id'],
                    'score': r['score'],
                    'payload': r['payload'],
                })
        
        return recommended
        
    except Exception as e:
        logger.error(f"Get recommendations failed: {e}")
        return []


async def check_training_eligibility(session: AsyncSession, user_telegram_id: int) -> tuple[bool, str]:
    """Check if user is eligible to start training."""
    user = await user_service.get_user_by_telegram_id(session, user_telegram_id)
    
    if not user:
        return False, "User not found"
    
    interaction_count = await post_service.get_user_interaction_count(session, user_telegram_id)
    
    if interaction_count < MIN_INTERACTIONS_FOR_TRAINING:
        return False, f"Need {MIN_INTERACTIONS_FOR_TRAINING - interaction_count} more interactions"
    
    return True, "Ready for training"


# ==================== Helper Functions ====================

async def _get_user_interaction_posts(
    session: AsyncSession,
    user_id: int
) -> tuple[List[Post], List[Post]]:
    """Get user's liked and disliked posts."""
    # Liked posts
    liked_result = await session.execute(
        select(Post)
        .join(Interaction)
        .where(
            Interaction.user_id == user_id,
            Interaction.interaction_type == InteractionType.LIKE
        )
    )
    liked_posts = list(liked_result.scalars().all())
    
    # Disliked posts
    disliked_result = await session.execute(
        select(Post)
        .join(Interaction)
        .where(
            Interaction.user_id == user_id,
            Interaction.interaction_type == InteractionType.DISLIKE
        )
    )
    disliked_posts = list(disliked_result.scalars().all())
    
    return liked_posts, disliked_posts


async def _ensure_post_embeddings(session: AsyncSession, posts: List[Post]) -> None:
    """Ensure all posts have embeddings in Qdrant."""
    # Check which posts need embeddings
    post_ids = [p.id for p in posts]
    existing = await qdrant_service.get_post_embeddings_batch(post_ids)
    
    posts_needing_embeddings = [p for p in posts if p.id not in existing]
    
    if not posts_needing_embeddings:
        return
    
    # Get channel info for context
    channel_cache = {}
    for post in posts_needing_embeddings:
        if post.channel_id not in channel_cache:
            result = await session.execute(
                select(Channel).where(Channel.id == post.channel_id)
            )
            channel = result.scalar_one_or_none()
            channel_cache[post.channel_id] = channel.title if channel else None
    
    # Prepare texts for embedding
    texts = [
        embedding_service.prepare_post_text(p.text or "", channel_cache.get(p.channel_id))
        for p in posts_needing_embeddings
    ]
    
    # Get embeddings
    embeddings = await embedding_service.get_embeddings_batch(texts)
    
    # Store in Qdrant
    points = []
    for post, emb in zip(posts_needing_embeddings, embeddings):
        if emb:
            points.append({
                'id': post.id,
                'vector': emb,
                'payload': {
                    'channel_id': post.channel_id,
                    'text_preview': (post.text or "")[:200],
                }
            })
    
    if points:
        await qdrant_service.upsert_post_embeddings_batch(points)
        logger.info(f"Stored {len(points)} post embeddings in Qdrant")


async def _get_embeddings_for_posts(post_ids: List[int]) -> List[List[float]]:
    """Get embeddings for posts from Qdrant."""
    if not post_ids:
        return []
    
    embeddings_dict = await qdrant_service.get_post_embeddings_batch(post_ids)
    return [embeddings_dict[pid] for pid in post_ids if pid in embeddings_dict]


async def _score_user_channel_posts(
    session: AsyncSession,
    user_telegram_id: int,
    preference_vector: List[float]
) -> None:
    """Score all posts in user's channels based on preference vector."""
    from app.services.channel_service import get_user_channels
    
    channels = await get_user_channels(session, user_telegram_id)
    
    for channel in channels:
        result = await session.execute(
            select(Post).where(Post.channel_id == channel.id)
        )
        posts = list(result.scalars().all())
        
        # Ensure embeddings exist
        await _ensure_post_embeddings(session, posts)
        
        # Get embeddings and calculate scores
        post_embeddings = await qdrant_service.get_post_embeddings_batch([p.id for p in posts])
        
        for post in posts:
            if post.id in post_embeddings:
                score = _cosine_similarity(preference_vector, post_embeddings[post.id])
                # Normalize to 0-1 range
                score = (score + 1) / 2
                post.relevance_score = round(score, 4)
    
    await session.flush()


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


# Legacy function names for backward compatibility
async def mock_train_model(session: AsyncSession, user_telegram_id: int) -> tuple[bool, str, float]:
    """Backward compatible wrapper for train_model."""
    return await train_model(session, user_telegram_id)


async def mock_predict(
    session: AsyncSession,
    user_telegram_id: int,
    post_ids: List[int]
) -> Dict[int, float]:
    """Backward compatible wrapper for predict."""
    return await predict(session, user_telegram_id, post_ids)
