from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserActivityUpdate,
    LogCreate,
    LogResponse,
    UserFeedTargetResponse,
    LanguageUpdate,
    LanguageResponse,
)
from app.repositories.user_repository import UserRepository
from app.services import user_service
from app.models import UserStatus

router = APIRouter(prefix="/users", tags=["users"])


# ============== List/Create ==============

@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    """
    List all users with pagination.
    
    Returns a paginated list of all users in the system.
    
    **Parameters:**
    - `skip`: Number of users to skip (default: 0)
    - `limit`: Maximum number of users to return (default: 50, max: 100)
    
    **Example Request:**
    ```
    GET /api/v1/users/?skip=0&limit=10
    ```
    
    **Example Response:**
    ```json
    [
        {
            "id": 1,
            "telegram_id": 123456789,
            "username": "johndoe",
            "first_name": "John",
            "last_name": "Doe",
            "status": "TRAINED",
            "is_trained": true,
            "bonus_channels_count": 2,
            "initial_best_post_sent": true,
            "language": "ru_RU",
            "last_activity_at": "2024-01-01T12:00:00",
            "created_at": "2024-01-01T10:00:00"
        }
    ]
    ```
    """
    from app.repositories.user_repository import UserRepository
    users = await UserRepository.get_all(session)
    paginated_users = users[skip:skip + limit]
    return paginated_users


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new user or return existing one.
    
    If a user with the given `telegram_id` already exists, returns the existing user.
    Otherwise, creates a new user with the provided data.
    
    **Request Body:**
    ```json
    {
        "telegram_id": 123456789,
        "username": "johndoe",
        "first_name": "John",
        "last_name": "Doe",
        "language": "ru_RU"
    }
    ```
    
    **Example Response (New User):**
    ```json
    {
        "id": 1,
        "telegram_id": 123456789,
        "username": "johndoe",
        "first_name": "John",
        "last_name": "Doe",
        "status": "NEW",
        "is_trained": false,
        "bonus_channels_count": 0,
        "initial_best_post_sent": false,
        "language": "ru_RU",
        "last_activity_at": "2024-01-01T12:00:00",
        "created_at": "2024-01-01T12:00:00"
    }
    ```
    
    **Note:** Language is automatically normalized from Telegram format (e.g., "ru" → "ru_RU").
    """
    user, is_new = await user_service.get_or_create_user(session, user_data)
    return user


# ============== Specific endpoints (before parameterized routes) ==============

@router.post("/activity", status_code=status.HTTP_204_NO_CONTENT)
async def update_activity(
    activity_data: UserActivityUpdate,
    session: AsyncSession = Depends(get_session)
):
    """
    Update user's last activity timestamp.
    
    Updates the `last_activity_at` field to the current time.
    Used to track user engagement.
    
    **Request Body:**
    ```json
    {
        "telegram_id": 123456789
    }
    ```
    
    **Response:**
    - `204 No Content`: Activity timestamp updated successfully
    
    **Errors:**
    - `404 Not Found`: User with the given Telegram ID does not exist
    """
    success = await user_service.update_user_activity(session, activity_data.telegram_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


@router.post("/logs", response_model=LogResponse, status_code=status.HTTP_201_CREATED)
async def create_log(
    log_data: LogCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a user activity log entry."""
    try:
        log = await user_service.create_log(session, log_data)
        return log
    except (ValueError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/feed-targets", response_model=List[UserFeedTargetResponse])
async def get_feed_targets(
    session: AsyncSession = Depends(get_session)
):
    """
    Get users eligible for feed auto-delivery.
    
    Returns users with status TRAINED or ACTIVE who are eligible
    to receive automated feed posts.
    
    **Example Request:**
    ```
    GET /api/v1/users/feed-targets
    ```
    
    **Example Response:**
    ```json
    [
        {
            "telegram_id": 123456789,
            "status": "TRAINED",
            "is_trained": true,
            "bonus_channels_count": 2,
            "initial_best_post_sent": true
        }
    ]
    ```
    """
    users = await user_service.get_users_by_statuses(
        session,
        [UserStatus.TRAINED, UserStatus.ACTIVE],
    )
    return users


# ============== Parameterized routes ==============

@router.get("/{telegram_id}", response_model=UserResponse)
async def get_user(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Get user by Telegram ID.
    
    Returns detailed information about a specific user.
    
    **Parameters:**
    - `telegram_id`: Telegram user ID (path parameter)
    
    **Example Request:**
    ```
    GET /api/v1/users/123456789
    ```
    
    **Example Response:**
    ```json
    {
        "id": 1,
        "telegram_id": 123456789,
        "username": "johndoe",
        "first_name": "John",
        "last_name": "Doe",
        "status": "TRAINED",
        "is_trained": true,
        "bonus_channels_count": 2,
        "initial_best_post_sent": true,
        "language": "ru_RU",
        "last_activity_at": "2024-01-01T12:00:00",
        "created_at": "2024-01-01T10:00:00"
    }
    ```
    
    **Errors:**
    - `404 Not Found`: User with the given Telegram ID does not exist
    """
    user = await user_service.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.patch("/{telegram_id}", response_model=UserResponse)
async def update_user(
    telegram_id: int,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_session)
):
    """
    Update user fields.
    
    Partially updates user information. Only provided fields will be updated.
    
    **Parameters:**
    - `telegram_id`: Telegram user ID (path parameter)
    
    **Request Body (all fields optional):**
    ```json
    {
        "status": "TRAINED",
        "is_trained": true,
        "bonus_channels_count": 2,
        "initial_best_post_sent": true
    }
    ```
    
    **Example Response:**
    ```json
    {
        "id": 1,
        "telegram_id": 123456789,
        "username": "johndoe",
        "first_name": "John",
        "last_name": "Doe",
        "status": "TRAINED",
        "is_trained": true,
        "bonus_channels_count": 2,
        "initial_best_post_sent": true,
        "language": "ru_RU",
        "last_activity_at": "2024-01-01T12:00:00",
        "created_at": "2024-01-01T10:00:00"
    }
    ```
    
    **Errors:**
    - `404 Not Found`: User with the given Telegram ID does not exist
    """
    user = await user_service.update_user(session, telegram_id, user_update)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.get("/{telegram_id}/language", response_model=LanguageResponse)
async def get_user_language(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Get user's preferred language.
    
    Returns the language locale code for the user (e.g., "ru_RU", "en_US").
    
    **Example Request:**
    ```
    GET /api/v1/users/123456789/language
    ```
    
    **Example Response:**
    ```json
    {
        "language": "ru_RU"
    }
    ```
    
    **Errors:**
    - `404 Not Found`: User with the given Telegram ID does not exist
    """
    user = await user_service.get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return LanguageResponse(language=user.language or "en_US")


@router.put("/{telegram_id}/language", status_code=status.HTTP_204_NO_CONTENT)
async def set_user_language(
    telegram_id: int,
    language_data: LanguageUpdate,
    session: AsyncSession = Depends(get_session)
):
    """
    Set user's preferred language.
    
    Updates the user's language preference. Language code should be in locale format (e.g., "ru_RU", "en_US").
    
    **Request Body:**
    ```json
    {
        "language": "ru_RU"
    }
    ```
    
    **Response:**
    - `204 No Content`: Language updated successfully
    
    **Errors:**
    - `404 Not Found`: User with the given Telegram ID does not exist
    """
    from app.services.user_service import UserService
    success = await UserService.update_user_language(session, telegram_id, language_data.language)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


@router.post("/{telegram_id}/training-complete", status_code=status.HTTP_200_OK)
async def mark_training_complete(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Mark user training as complete (called from MiniApp).
    
    Always publishes event to Redis so main-bot can send completion message.
    """
    from app.services.user_service import UserService
    from app.exceptions import NotFoundError
    
    try:
        user_status, notified = await UserService.mark_training_complete(session, telegram_id)
        return {"status": "ok", "user_status": user_status.value, "notified": notified}
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{telegram_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    telegram_id: int,
    hard: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """
    Delete a user.
    
    By default, performs a soft delete (marks user as deleted but keeps data).
    Use `hard=true` query parameter for permanent deletion.
    
    **Parameters:**
    - `telegram_id`: Telegram user ID (path parameter)
    - `hard`: If true, permanently deletes user. If false, soft deletes (default: false)
    
    **Example Request (Soft Delete):**
    ```
    DELETE /api/v1/users/123456789
    ```
    
    **Example Request (Hard Delete):**
    ```
    DELETE /api/v1/users/123456789?hard=true
    ```
    
    **Response:**
    - `204 No Content`: User successfully deleted
    
    **Errors:**
    - `404 Not Found`: User with the given Telegram ID does not exist
    
    **Warning:** Hard delete permanently removes all user data and cannot be undone.
    """
    # Get user by telegram_id first to get user.id
    user = await UserRepository.get_by_telegram_id(session, telegram_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    # Delete using business logic (soft delete + cleanup or hard delete)
    from app.services.user_service import UserService
    deleted_user = await UserService.delete_user(session, user.id, hard=hard)
    if not deleted_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    await session.commit()
