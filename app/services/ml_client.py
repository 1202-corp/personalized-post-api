"""
HTTP client for ML Service.
Provides interface to communicate with ML service via REST API.
"""

import httpx
import logging
from typing import List, Dict, Optional, Tuple
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ML Service base URL
ML_SERVICE_URL = "http://ml-service:8002"


async def train_model(user_telegram_id: int) -> Tuple[bool, str, float]:
    """
    Train ML model for a user.
    Returns (success, message, training_time).
    """
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/api/v1/ml/train",
                json={"user_telegram_id": user_telegram_id}
            )
            response.raise_for_status()
            data = response.json()
            return data["success"], data["message"], data["training_time"]
    except httpx.TimeoutException:
        logger.error(f"ML Service timeout for user {user_telegram_id}")
        return False, "ML Service timeout", 0.0
    except httpx.HTTPError as e:
        logger.error(f"ML Service error for user {user_telegram_id}: {e}")
        return False, f"ML Service error: {str(e)}", 0.0
    except Exception as e:
        logger.error(f"Unexpected error calling ML Service: {e}", exc_info=True)
        return False, f"Error: {str(e)}", 0.0


async def predict(user_telegram_id: int, post_ids: List[int]) -> Dict[int, float]:
    """
    Get relevance predictions for specific posts.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/api/v1/ml/predict",
                json={
                    "user_telegram_id": user_telegram_id,
                    "post_ids": post_ids
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("predictions", {})
    except httpx.TimeoutException:
        logger.error(f"ML Service timeout for prediction user {user_telegram_id}")
        return {pid: 0.5 for pid in post_ids}
    except httpx.HTTPError as e:
        logger.error(f"ML Service error for prediction: {e}")
        return {pid: 0.5 for pid in post_ids}
    except Exception as e:
        logger.error(f"Unexpected error calling ML Service: {e}", exc_info=True)
        return {pid: 0.5 for pid in post_ids}


async def get_recommended_posts(
    user_telegram_id: int,
    limit: int = 10,
    exclude_interacted: bool = True
) -> List[Dict]:
    """
    Get recommended posts for user.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ML_SERVICE_URL}/api/v1/ml/recommendations",
                json={
                    "user_telegram_id": user_telegram_id,
                    "limit": limit,
                    "exclude_interacted": exclude_interacted
                }
            )
            response.raise_for_status()
            data = response.json()
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
    except httpx.TimeoutException:
        logger.error(f"ML Service timeout for recommendations user {user_telegram_id}")
        return []
    except httpx.HTTPError as e:
        logger.error(f"ML Service error for recommendations: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error calling ML Service: {e}", exc_info=True)
        return []


async def check_training_eligibility(user_telegram_id: int) -> Tuple[bool, str]:
    """
    Check if user is eligible to start training.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{ML_SERVICE_URL}/api/v1/ml/eligibility/{user_telegram_id}"
            )
            response.raise_for_status()
            data = response.json()
            return data.get("eligible", False), data.get("message", "")
    except httpx.TimeoutException:
        logger.error(f"ML Service timeout for eligibility check user {user_telegram_id}")
        return False, "ML Service timeout"
    except httpx.HTTPError as e:
        logger.error(f"ML Service error for eligibility check: {e}")
        return False, f"ML Service error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error calling ML Service: {e}", exc_info=True)
        return False, f"Error: {str(e)}"

