"""
HTTP client for ML Service.
Provides interface to communicate with ML service via REST API.
"""

import os
import httpx
import logging
from typing import List, Dict, Optional, Tuple, Callable, TypeVar, Awaitable
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ML Service base URL (can be overridden via environment)
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml-service:8002")

T = TypeVar('T')


async def _handle_ml_request(
    operation_name: str,
    user_telegram_id: int,
    request_func: Callable[[httpx.AsyncClient], Awaitable[httpx.Response]],
    timeout: float,
    default_return: T
) -> T:
    """
    Helper function to handle ML service requests with consistent error handling.
    
    Args:
        operation_name: Name of the operation for logging
        user_telegram_id: User Telegram ID for logging
        request_func: Async function that makes the HTTP request
        timeout: Request timeout in seconds
        default_return: Default value to return on error
        
    Returns:
        Result from request_func or default_return on error
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await request_func(client)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.error(f"ML Service timeout for {operation_name} user {user_telegram_id}")
        return default_return
    except httpx.HTTPError as e:
        logger.error(f"ML Service error for {operation_name}: {e}")
        return default_return
    except Exception as e:
        logger.error(f"Unexpected error calling ML Service for {operation_name}: {e}", exc_info=True)
        return default_return


async def train_model(user_telegram_id: int) -> Tuple[bool, str, float]:
    """
    Train ML model for a user.
    Returns (success, message, training_time).
    """
    data = await _handle_ml_request(
        "train",
        user_telegram_id,
        lambda client: client.post(
            f"{ML_SERVICE_URL}/api/v1/ml/train",
            json={"user_telegram_id": user_telegram_id}
        ),
        timeout=300.0,
        default_return={"success": False, "message": "ML Service error", "training_time": 0.0}
    )
    return data.get("success", False), data.get("message", ""), data.get("training_time", 0.0)


async def predict(user_telegram_id: int, post_ids: List[int]) -> Dict[int, float]:
    """
    Get relevance predictions for specific posts.
    """
    data = await _handle_ml_request(
        "predict",
        user_telegram_id,
        lambda client: client.post(
            f"{ML_SERVICE_URL}/api/v1/ml/predict",
            json={
                "user_telegram_id": user_telegram_id,
                "post_ids": post_ids
            }
        ),
        timeout=60.0,
        default_return={"predictions": {pid: 0.5 for pid in post_ids}}
    )
    return data.get("predictions", {pid: 0.5 for pid in post_ids})


async def get_recommended_posts(
    user_telegram_id: int,
    limit: int = 10,
    exclude_interacted: bool = True
) -> List[Dict]:
    """
    Get recommended posts for user.
    """
    data = await _handle_ml_request(
        "recommendations",
        user_telegram_id,
        lambda client: client.post(
            f"{ML_SERVICE_URL}/api/v1/ml/recommendations",
            json={
                "user_telegram_id": user_telegram_id,
                "limit": limit,
                "exclude_interacted": exclude_interacted
            }
        ),
        timeout=60.0,
        default_return={"recommendations": []}
    )
    recommendations = data.get("recommendations", [])
    # Convert to format expected by API
    return [
        {
            "post_id": r["post_id"],
            "score": r["score"],
            "payload": r.get("payload", {})
        }
        for r in recommendations
    ]


async def check_training_eligibility(user_telegram_id: int) -> Tuple[bool, str]:
    """
    Check if user is eligible to start training.
    """
    data = await _handle_ml_request(
        "eligibility check",
        user_telegram_id,
        lambda client: client.get(
            f"{ML_SERVICE_URL}/api/v1/ml/eligibility/{user_telegram_id}"
        ),
        timeout=10.0,
        default_return={"eligible": False, "message": "ML Service error"}
    )
    return data.get("eligible", False), data.get("message", "")


async def on_user_interaction(user_telegram_id: int) -> bool:
    """
    Notify ML that user made an interaction; ML may recalc taste after every 2 reactions.
    Returns True if taste was recalculated.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/api/v1/ml/on-user-interaction",
                json={"user_telegram_id": user_telegram_id},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("recalculated", False)
    except Exception as e:
        logger.error(f"ML Service on_user_interaction error: {e}", exc_info=True)
        return False


async def get_post_recipients(post_id: int, text: Optional[str] = None) -> List[int]:
    """
    Post-centric delivery: get telegram_ids of users who should receive this post
    (taste clusters + mailing_enabled for the post's channel).
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {"post_id": post_id}
            if text is not None:
                payload["text"] = text
            response = await client.post(
                f"{ML_SERVICE_URL}/api/v1/ml/post-recipients",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("telegram_ids", [])
    except Exception as e:
        logger.error(f"ML Service get_post_recipients error: {e}", exc_info=True)
        return []
