"""
A/B Testing service for recommendation algorithms.

Allows testing different recommendation strategies and tracking their performance.
"""

import hashlib
from enum import Enum
from typing import Optional
from datetime import datetime
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Interaction


class RecommendationAlgorithm(str, Enum):
    """Available recommendation algorithms."""
    COSINE_SIMILARITY = "cosine_similarity"  # Default: cosine similarity with preference vector
    POPULARITY = "popularity"  # Rank by global like count
    RECENCY = "recency"  # Most recent posts first
    HYBRID = "hybrid"  # Combination of cosine + recency
    LLM_RERANKER = "llm_reranker"  # GPT-4o-mini reranking on top of cosine similarity


# A/B Test configuration
AB_TEST_CONFIG = {
    "enabled": True,
    "test_name": "recommendation_algo_v2",
    "variants": {
        "control": {
            "algorithm": RecommendationAlgorithm.COSINE_SIMILARITY,
            "weight": 34,  # ~34% of users
        },
        "treatment_a": {
            "algorithm": RecommendationAlgorithm.HYBRID,
            "weight": 33,  # ~33% of users
        },
        "treatment_b": {
            "algorithm": RecommendationAlgorithm.LLM_RERANKER,
            "weight": 33,  # ~33% of users - GPT-4o-mini reranking
        },
    },
}


def get_user_variant(user_id: int, test_name: str = "default") -> str:
    """
    Deterministically assign user to a test variant.
    Uses hash to ensure consistent assignment.
    """
    hash_input = f"{user_id}:{test_name}"
    hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    
    # Calculate bucket (0-99)
    bucket = hash_value % 100
    
    # Assign to variant based on weights
    cumulative = 0
    for variant_name, config in AB_TEST_CONFIG["variants"].items():
        cumulative += config["weight"]
        if bucket < cumulative:
            return variant_name
    
    return "control"  # Fallback


def get_algorithm_for_user(user_id: int) -> RecommendationAlgorithm:
    """Get the recommendation algorithm assigned to a user."""
    if not AB_TEST_CONFIG["enabled"]:
        return RecommendationAlgorithm.COSINE_SIMILARITY
    
    variant = get_user_variant(user_id, AB_TEST_CONFIG["test_name"])
    return AB_TEST_CONFIG["variants"][variant]["algorithm"]


async def get_ab_test_results(db: AsyncSession) -> dict:
    """
    Calculate A/B test results comparing variants.
    
    IMPORTANT: Only counts POST-TRAINING interactions (after user completed training).
    Training interactions are for calibration and should not affect A/B metrics.
    """
    from app.models import Post
    
    results = {
        "test_name": AB_TEST_CONFIG["test_name"],
        "enabled": AB_TEST_CONFIG["enabled"],
        "description": "Только post-training интеракции (после обучения)",
        "variants": {},
    }
    
    # Default training count (7 posts from default channels)
    DEFAULT_TRAINING_COUNT = 7
    
    # Get all users
    users_result = await db.execute(
        select(User.id, User.telegram_id, User.is_trained)
    )
    users = users_result.all()
    
    # Assign users to variants and calculate metrics
    variant_users = {v: [] for v in AB_TEST_CONFIG["variants"].keys()}
    
    for user_id, telegram_id, is_trained in users:
        variant = get_user_variant(telegram_id, AB_TEST_CONFIG["test_name"])
        variant_users[variant].append((user_id, is_trained, DEFAULT_TRAINING_COUNT))
    
    for variant_name, user_list in variant_users.items():
        trained_users = [(u[0], u[2]) for u in user_list if u[1]]  # Only trained users
        trained_count = len(trained_users)
        
        if not trained_users:
            results["variants"][variant_name] = {
                "algorithm": AB_TEST_CONFIG["variants"][variant_name]["algorithm"],
                "users": len(user_list),
                "trained": 0,
                "post_training_interactions": 0,
                "post_training_likes": 0,
                "like_rate": 0,
                "note": "Нет обученных юзеров для сравнения"
            }
            continue
        
        # For each trained user, count interactions AFTER their training interactions
        # We use row_number to skip the first N (training_count) interactions
        total_post_training = 0
        total_post_training_likes = 0
        
        for user_id, training_count in trained_users:
            # Get all interactions ordered by created_at, skip first training_count
            interactions_result = await db.execute(
                select(Interaction.interaction_type)
                .where(Interaction.user_id == user_id)
                .order_by(Interaction.created_at)
                .offset(training_count)  # Skip training interactions
            )
            post_training = interactions_result.scalars().all()
            
            total_post_training += len(post_training)
            total_post_training_likes += sum(1 for i in post_training if i.value == "like")
        
        results["variants"][variant_name] = {
            "algorithm": AB_TEST_CONFIG["variants"][variant_name]["algorithm"],
            "users": len(user_list),
            "trained": trained_count,
            "training_rate": round(trained_count / max(len(user_list), 1) * 100, 1),
            "post_training_interactions": total_post_training,
            "post_training_likes": total_post_training_likes,
            "like_rate": round(total_post_training_likes / max(total_post_training, 1) * 100, 1),
        }
    
    return results


async def update_ab_test_config(
    enabled: Optional[bool] = None,
    test_name: Optional[str] = None,
    control_weight: Optional[int] = None,
    treatment_weight: Optional[int] = None,
) -> dict:
    """Update A/B test configuration."""
    global AB_TEST_CONFIG
    
    if enabled is not None:
        AB_TEST_CONFIG["enabled"] = enabled
    
    if test_name is not None:
        AB_TEST_CONFIG["test_name"] = test_name
    
    if control_weight is not None:
        AB_TEST_CONFIG["variants"]["control"]["weight"] = control_weight
    
    if treatment_weight is not None:
        AB_TEST_CONFIG["variants"]["treatment_a"]["weight"] = treatment_weight
    
    return AB_TEST_CONFIG
