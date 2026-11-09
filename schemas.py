from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import models
import typing
import enum


class ListingSortBy(str, enum.Enum):
    """Enumeration of available listing sort options."""
    DEFAULT = "-"
    PRICE_ASC = "Least expensive"
    PRICE_DESC = "Most expensive"
    CREATED_ASC = "Least recently created"
    CREATED_DESC = "Most recently created"
    ITEM_NAME_ASC = "Alphabetical"
    ITEM_NAME_DESC = "Reverse alphabetical"
    MOST_VIEWED_ASC = "Most viewed"
    MOST_VIEWED_DESC = "Least viewed"


class ListingCreate(BaseModel):
    """Schema for creating a listing before attaching the authenticated seller."""
    title: str
    description: str | None
    price: float
    category_name: str
    course_code: str | None = None
    pickup_location_name: str
    images: typing.List[str]


class ListingDisplayShort(BaseModel):
    """Placeholder schema for a shortened listing display."""
    pass


class UserReference(BaseModel):
    """Schema containing basic identifying information for a user."""
    id: int
    display_name: str

    class Config:
        from_attributes = True


# version of ListingCreate with an attached user
class ListingCreateAuthorized(ListingCreate):
    """Schema for creating a listing with an attached authenticated seller."""
    seller: UserReference


class ListingSearchQuery(BaseModel):
    """Schema for listing search filters, sorting, and pagination."""
    query: str
    page: int = 1
    min_price: float | None = None
    max_price: float | None = None
    categories: typing.List[str] = []
    pickup_locations: typing.List[str] = []
    sort_by: ListingSortBy = ListingSortBy.DEFAULT


class ListingDisplayThumbnail(BaseModel):
    """Schema for displaying a listing preview in search results or listing grids."""
    id: int
    title: str
    description: str
    price: float
    seller_name: str
    seller: models.User
    category_name: str
    course_code: str | None
    pickup_location_name: str | None
    top_image_path: str | None
    conversation_exists: bool = False
    conversation_id: int | None = None
    bookmarked: bool | None = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class UserConversationThumbnail(BaseModel):
    """Schema for displaying a conversation preview in the inbox."""
    id: int
    preview: str
    other_user_name: str
    unread: bool
    updated_at: datetime


class SendMessage(BaseModel):
    """Schema for sending a message to an existing conversation."""
    conversation_id: int
    message: str


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation with an initial message."""
    recipient_id: int
    listing_id: int
    initial_message: str


class MessageView(BaseModel):
    """Schema for displaying a message and whether it belongs to the current user."""
    content: str
    is_from_current_user: bool


class ListingDisplayFull(BaseModel):
    """Schema for displaying complete listing details."""
    id: int
    title: str
    description: str
    price: float
    images: typing.List[str]
    top_image_path: str | None
    category_name: str
    pickup_location_name: str
    created_at: datetime
    updated_at: datetime
    seller_name: str
    seller_rating: float


class PickupLocationGet(BaseModel):
    """Schema for displaying pickup location details."""
    id: int
    name: str
    description: str
    seller_name: str
    seller_rating: float


class CategoryGet(BaseModel):
    """Schema for displaying category details."""
    id: int
    name: str


class UserCreate(BaseModel):
    """Schema for creating a new user account."""
    email: EmailStr
    password: str
    display_name: str
    bio: str | None = None


class Login(BaseModel):
    """Schema for user login credentials."""
    email: EmailStr
    password: str


class Profile(BaseModel):
    """Schema for displaying a user's profile information."""
    id: int
    email: EmailStr
    display_name: str
    bio: str | None = None
    pronouns: str | None = None
    profile_image_path: str | None = None
    notifications_enabled: bool = True
    is_moderator: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EditProfile(BaseModel):
    """Schema for validating editable profile fields."""
    display_name: str | None = Field(default=None, min_length=3, max_length=64)
    bio: str | None = Field(default=None, max_length=500)
    profile_image_path: str | None = Field(default=None, max_length=128)


class SettingsUpdate(BaseModel):
    """Schema for validating user settings updates."""
    display_name: str = Field(min_length=3, max_length=64)
    pronouns: str | None = Field(default=None, max_length=64)
    bio: str | None = None
    notifications_enabled: bool = True
    profile_image_path: str | None = Field(default=None, max_length=128)


class PasswordUpdate(BaseModel):
    """Schema for validating a user password change request."""
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str


class ReviewCreate(BaseModel):
    """Schema for creating or updating a user review."""
    user_id: int
    score: int = Field(ge=1, le=5)
    title: str = Field(min_length=1, max_length=30)
    review_text: str | None
