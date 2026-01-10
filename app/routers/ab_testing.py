"""
A/B Testing API endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services import ab_testing_service

router = APIRouter(prefix="/ab-testing", tags=["ab-testing"])


class ABTestConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    test_name: Optional[str] = None
    control_weight: Optional[int] = None
    treatment_weight: Optional[int] = None


@router.get("/results")
async def get_ab_test_results(db: AsyncSession = Depends(get_session)):
    """Get A/B test results with metrics per variant."""
    return await ab_testing_service.get_ab_test_results(db)


@router.get("/config")
async def get_ab_test_config():
    """Get current A/B test configuration."""
    return ab_testing_service.AB_TEST_CONFIG


@router.post("/config")
async def update_ab_test_config(config: ABTestConfigUpdate):
    """Update A/B test configuration."""
    return await ab_testing_service.update_ab_test_config(
        enabled=config.enabled,
        test_name=config.test_name,
        control_weight=config.control_weight,
        treatment_weight=config.treatment_weight,
    )


@router.get("/user/{user_id}/variant")
async def get_user_variant(user_id: int):
    """Get the A/B test variant assigned to a user."""
    variant = ab_testing_service.get_user_variant(
        user_id, 
        ab_testing_service.AB_TEST_CONFIG["test_name"]
    )
    algorithm = ab_testing_service.get_algorithm_for_user(user_id)
    
    return {
        "user_id": user_id,
        "variant": variant,
        "algorithm": algorithm,
    }


@router.get("/llm-costs")
async def get_llm_costs():
    """Get LLM reranker cost statistics."""
    from app.services import llm_reranker_service
    return llm_reranker_service.get_cost_stats()
