from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field

from app.models import UserStatus, InteractionType


# ============== User Schemas ==============

class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    """Request schema for creating or getting a user.
    
    Example:
        {
            "telegram_id": 123456789,
            "username": "johndoe",
            "first_name": "John",
            "last_name": "Doe",
            "language": "ru_RU"
        }
    """
    language: Optional[str] = Field(
        None,
        description="Language code from Telegram (e.g., 'ru', 'en') or locale (e.g., 'ru_RU', 'en_US')",
        examples=["ru_RU", "en_US", "ru", "en"]
    )


class UserUpdate(BaseModel):
    """Request schema for updating user fields.
    
    Example:
        {
            "status": "TRAINED",
            "is_trained": true,
            "bonus_channels_count": 2
        }
    """
    status: Optional[UserStatus] = Field(None, description="User status (NEW, ACTIVE, TRAINED, INACTIVE)")
    is_trained: Optional[bool] = Field(None, description="Whether user has completed training")
    bonus_channels_count: Optional[int] = Field(None, description="Number of bonus channels available", ge=0)
    initial_best_post_sent: Optional[bool] = Field(None, description="Whether initial best post was sent")


class UserResponse(UserBase):
    id: int
    status: UserStatus
    is_trained: bool
    bonus_channels_count: int
    initial_best_post_sent: Optional[bool] = False
    language: Optional[str] = "en_US"
    last_activity_at: datetime
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class LanguageUpdate(BaseModel):
    """Request schema for updating user language.
    
    Example:
        {
            "language": "ru_RU"
        }
    """
    language: str = Field(..., description="Language locale code (e.g., 'ru_RU', 'en_US')", examples=["ru_RU", "en_US"])


class LanguageResponse(BaseModel):
    language: str


class UserFeedTargetResponse(BaseModel):
    telegram_id: int
    status: UserStatus
    is_trained: Optional[bool] = None
    bonus_channels_count: Optional[int] = None
    initial_best_post_sent: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class UserActivityUpdate(BaseModel):
    """Request schema for updating user activity timestamp.
    
    Example:
        {
            "telegram_id": 123456789
        }
    """
    telegram_id: int = Field(..., description="Telegram user ID", examples=[123456789])


# ============== Channel Schemas ==============

class ChannelBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    title: str


class ChannelCreate(ChannelBase):
    """Request schema for creating a channel.
    
    Example:
        {
            "telegram_id": -1001234567890,
            "username": "example_channel",
            "title": "Example Channel",
            "is_default": false
        }
    """
    is_default: bool = Field(False, description="Whether this channel is a default training channel")


class ChannelUpdate(BaseModel):
    """Request schema for updating channel fields.
    
    Example:
        {
            "title": "Updated Channel Title",
            "is_default": true,
            "is_active": true
        }
    """
    title: Optional[str] = Field(None, description="Channel title", examples=["My Channel"])
    is_default: Optional[bool] = Field(None, description="Whether channel is a default training channel")
    is_active: Optional[bool] = Field(None, description="Whether channel is active")


class ChannelResponse(ChannelBase):
    id: int
    is_default: bool
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserChannelAdd(BaseModel):
    """Request schema for associating a channel with a user.
    
    Example:
        {
            "user_telegram_id": 123456789,
            "channel_username": "example_channel",
            "is_for_training": true,
            "is_bonus": false
        }
    """
    user_telegram_id: int = Field(..., description="Telegram user ID", examples=[123456789])
    channel_username: str = Field(..., description="Channel username (with or without @)", examples=["example_channel", "@example_channel"])
    is_for_training: bool = Field(False, description="Whether channel is used for training")
    is_bonus: bool = Field(False, description="Whether channel is a bonus channel")


# ============== Post Schemas ==============

class PostBase(BaseModel):
    telegram_message_id: int
    text: Optional[str] = None
    media_type: Optional[str] = None
    media_file_id: Optional[str] = None
    posted_at: datetime


class PostCreate(PostBase):
    """Request schema for creating a post.
    
    Example:
        {
            "channel_telegram_id": -1001234567890,
            "telegram_message_id": 12345,
            "text": "Post content here",
            "media_type": "photo",
            "media_file_id": "123,456",
            "posted_at": "2024-01-01T12:00:00"
        }
    """
    channel_telegram_id: int = Field(..., description="Telegram channel ID", examples=[-1001234567890])


class PostBulkCreate(BaseModel):
    """Request schema for bulk creating posts.
    
    Example:
        {
            "channel_telegram_id": -1001234567890,
            "posts": [
                {
                    "telegram_message_id": 12345,
                    "text": "Post 1",
                    "posted_at": "2024-01-01T12:00:00"
                },
                {
                    "telegram_message_id": 12346,
                    "text": "Post 2",
                    "posted_at": "2024-01-01T13:00:00"
                }
            ]
        }
    """
    channel_telegram_id: int = Field(..., description="Telegram channel ID", examples=[-1001234567890])
    posts: List[PostBase] = Field(..., description="List of posts to create", min_length=1)


class PostUpdate(BaseModel):
    """Request schema for updating post fields.
    
    Example:
        {
            "text": "Updated post text",
            "relevance_score": 0.85
        }
    """
    text: Optional[str] = Field(None, description="Post text content", examples=["Updated post content"])
    media_type: Optional[str] = Field(None, description="Media type (photo, video, etc.)", examples=["photo", "video"])
    media_file_id: Optional[str] = Field(None, description="Comma-separated media file IDs", examples=["123,456"])
    relevance_score: Optional[float] = Field(None, description="ML relevance score (0.0-1.0)", ge=0.0, le=1.0, examples=[0.85])


class PostResponse(PostBase):
    id: int
    channel_id: int
    relevance_score: Optional[float] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PostWithChannel(PostResponse):
    channel_username: Optional[str] = None
    channel_title: str


# ============== Interaction Schemas ==============

class InteractionCreate(BaseModel):
    """Request schema for creating a user interaction with a post.
    
    Example:
        {
            "user_telegram_id": 123456789,
            "post_id": 42,
            "interaction_type": "like"
        }
    """
    user_telegram_id: int = Field(..., description="Telegram user ID", examples=[123456789])
    post_id: int = Field(..., description="Post ID", examples=[42])
    interaction_type: InteractionType = Field(..., description="Type of interaction (like, dislike)", examples=["like", "dislike"])


class InteractionResponse(BaseModel):
    id: int
    user_id: int
    post_id: int
    interaction_type: InteractionType
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============== ML Mock Schemas ==============

class TrainRequest(BaseModel):
    """Request schema for training ML model.
    
    Example:
        {
            "user_telegram_id": 123456789
        }
    """
    user_telegram_id: int = Field(..., description="Telegram user ID", examples=[123456789])


class TrainResponse(BaseModel):
    success: bool
    message: str
    training_time: float


class PredictRequest(BaseModel):
    """Request schema for getting ML predictions.
    
    Example:
        {
            "user_telegram_id": 123456789,
            "post_ids": [1, 2, 3, 4, 5]
        }
    """
    user_telegram_id: int = Field(..., description="Telegram user ID", examples=[123456789])
    post_ids: List[int] = Field(..., description="List of post IDs to predict", min_length=1, examples=[[1, 2, 3, 4, 5]])


class PredictResponse(BaseModel):
    predictions: dict[int, float]  # post_id -> relevance_score


class BestPostRequest(BaseModel):
    """Request schema for getting best posts for a user.
    
    Example:
        {
            "user_telegram_id": 123456789,
            "limit": 10
        }
    """
    user_telegram_id: int = Field(..., description="Telegram user ID", examples=[123456789])
    limit: int = Field(1, description="Maximum number of posts to return", ge=1, le=50, examples=[10])


class BestPostResponse(BaseModel):
    posts: List[PostWithChannel]


# ============== Scraper Command Schemas ==============

class ScrapeCommand(BaseModel):
    channel_username: str
    limit: int = 7


class ScrapeResponse(BaseModel):
    success: bool
    channel_username: str
    posts_count: int
    message: str


class JoinChannelCommand(BaseModel):
    channel_username: str


class JoinChannelResponse(BaseModel):
    success: bool
    channel_username: str
    channel_id: Optional[int] = None
    message: str


# ============== Log Schemas ==============

class LogCreate(BaseModel):
    """Request schema for creating a user activity log entry.
    
    Example:
        {
            "user_telegram_id": 123456789,
            "action": "post_like",
            "details": "post_id=42"
        }
    """
    user_telegram_id: int = Field(..., description="Telegram user ID", examples=[123456789])
    action: str = Field(..., description="Action name", examples=["post_like", "training_started", "feed_viewed"])
    details: Optional[str] = Field(None, description="Additional action details", examples=["post_id=42"])


class LogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    details: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============== Training Posts Request ==============

class TrainingPostsRequest(BaseModel):
    """Request schema for getting training posts.
    
    Example:
        {
            "user_telegram_id": 123456789,
            "channel_usernames": ["@durov", "@telegram"],
            "posts_per_channel": 7
        }
    """
    user_telegram_id: int = Field(..., description="Telegram user ID", examples=[123456789])
    channel_usernames: List[str] = Field(..., description="List of channel usernames", min_length=1, examples=[["@durov", "@telegram"]])
    posts_per_channel: int = Field(7, description="Number of posts to fetch per channel", ge=1, le=50, examples=[7])