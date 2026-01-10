from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from app.models import UserStatus, InteractionType


# ============== User Schemas ==============

class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    status: Optional[UserStatus] = None
    is_trained: Optional[bool] = None
    bonus_channels_count: Optional[int] = None
    initial_best_post_sent: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    status: UserStatus
    is_trained: bool
    bonus_channels_count: int
    initial_best_post_sent: Optional[bool] = False
    language: Optional[str] = "en"
    last_activity_at: datetime
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class LanguageUpdate(BaseModel):
    language: str


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
    telegram_id: int


# ============== Channel Schemas ==============

class ChannelBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    title: str


class ChannelCreate(ChannelBase):
    is_default: bool = False


class ChannelResponse(ChannelBase):
    id: int
    is_default: bool
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserChannelAdd(BaseModel):
    user_telegram_id: int
    channel_username: str
    is_for_training: bool = False
    is_bonus: bool = False


# ============== Post Schemas ==============

class PostBase(BaseModel):
    telegram_message_id: int
    text: Optional[str] = None
    media_type: Optional[str] = None
    media_file_id: Optional[str] = None
    posted_at: datetime


class PostCreate(PostBase):
    channel_telegram_id: int


class PostBulkCreate(BaseModel):
    channel_telegram_id: int
    posts: List[PostBase]


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
    user_telegram_id: int
    post_id: int
    interaction_type: InteractionType


class InteractionResponse(BaseModel):
    id: int
    user_id: int
    post_id: int
    interaction_type: InteractionType
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============== ML Mock Schemas ==============

class TrainRequest(BaseModel):
    user_telegram_id: int


class TrainResponse(BaseModel):
    success: bool
    message: str
    training_time: float


class PredictRequest(BaseModel):
    user_telegram_id: int
    post_ids: List[int]


class PredictResponse(BaseModel):
    predictions: dict[int, float]  # post_id -> relevance_score


class BestPostRequest(BaseModel):
    user_telegram_id: int
    limit: int = 1


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
    user_telegram_id: int
    action: str
    details: Optional[str] = None


class LogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    details: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============== Training Posts Request ==============

class TrainingPostsRequest(BaseModel):
    user_telegram_id: int
    channel_usernames: List[str]
    posts_per_channel: int = 7