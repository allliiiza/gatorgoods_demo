import enum
import sqlalchemy as sa
import sqlalchemy.orm as orm
import typing
import datetime
from database import Base


# TODO: determine varchar length


class ReportStatus(str, enum.Enum):
    """Enumeration of possible report review statuses."""
    SUBMITTED = "submitted"
    RESOLVED = "resolved"


class ListingStatus(str, enum.Enum):
    """Enumeration of possible listing lifecycle statuses."""
    SUBMITTED = "submitted"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SOLD = "sold"
    DELETED = "deleted"


class SFSUAffiliation(str, enum.Enum):
    """Enumeration of possible SFSU affiliation types."""
    STUDENT = "student"
    ALUM = "alum"
    PROFESSOR = "professor"


class User(Base):
    """Database model representing a user account."""
    __tablename__ = "users"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    email: orm.Mapped[str] = orm.mapped_column(sa.String(length=254), unique=True, nullable=False)
    password_hash: orm.Mapped[str] = orm.mapped_column(sa.String(length=256), nullable=False)
    display_name: orm.Mapped[str] = orm.mapped_column(sa.String(length=64), unique=True, nullable=False)
    bio: orm.Mapped[str] = orm.mapped_column(sa.Text, nullable=True)
    pronouns: orm.Mapped[str] = orm.mapped_column(sa.Text, nullable=True)
    profile_image_path: orm.Mapped[str] = orm.mapped_column(sa.String(length=128), nullable=True)
    notifications_enabled: orm.Mapped[bool] = orm.mapped_column(nullable=False, default=True)

    is_moderator: orm.Mapped[bool] = orm.mapped_column(nullable=False, default=False)
    is_banned: orm.Mapped[bool] = orm.mapped_column(nullable=False, default=False)
    is_deactivated: orm.Mapped[bool] = orm.mapped_column(nullable=False, default=False)

    listings: orm.Mapped[typing.List["Listing"]] = orm.relationship("Listing", back_populates="seller", foreign_keys="Listing.seller_id")
    reviews_written: orm.Mapped[typing.List["Review"]] = orm.relationship("Review", back_populates="author", foreign_keys="Review.author_id")
    reviews: orm.Mapped[typing.List["Review"]] = orm.relationship("Review", back_populates="user", foreign_keys="Review.user_id")
    saved_searches: orm.Mapped[typing.List["SavedSearch"]] = orm.relationship("SavedSearch", back_populates="user", foreign_keys="SavedSearch.user_id")
    bookmarks: orm.Mapped[typing.List["Bookmark"]] = orm.relationship("Bookmark", back_populates="user", foreign_keys="Bookmark.user_id")
    reports: orm.Mapped[typing.List["UserReport"]] = orm.relationship("UserReport", back_populates="user", foreign_keys="UserReport.user_id")

    @property
    def rating(self):
        ratings = sum([review.score for review in self.reviews])
        num_ratings = len(self.reviews)
        if num_ratings == 0:
            return 0
        return ratings / num_ratings

    conversations_sent: orm.Mapped[typing.List["Conversation"]] = orm.relationship(
            "Conversation",
            back_populates="original_sender",
            foreign_keys="[Conversation.original_sender_id]",
            order_by="Conversation.last_message"
    )
    conversations_received: orm.Mapped[typing.List["Conversation"]] = orm.relationship(
            "Conversation",
            back_populates="original_recipient",
            foreign_keys="[Conversation.original_recipient_id]",
            order_by="Conversation.last_message"
    )

    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())


class ListingReport(Base):
    """Database model representing a report submitted against a listing."""
    __tablename__ = "listing_reports"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    status: orm.Mapped[ReportStatus] = orm.mapped_column(nullable=False, default=ReportStatus.SUBMITTED)

    listing_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("listings.id"), nullable=False)
    listing: orm.Mapped["Listing"] = orm.relationship("Listing", back_populates="reports")


class MessageReport(Base):
    """Database model representing a report submitted against a message."""
    __tablename__ = "message_reports"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    status: orm.Mapped[ReportStatus] = orm.mapped_column(nullable=False, default=ReportStatus.SUBMITTED)

    message_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("messages.id"), nullable=False)
    message: orm.Mapped["Message"] = orm.relationship("Message", back_populates="reports")


class UserReport(Base):
    """Database model representing a report submitted against a user."""
    __tablename__ = "user_reports"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    status: orm.Mapped[ReportStatus] = orm.mapped_column(nullable=False, default=ReportStatus.SUBMITTED)

    user_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    user: orm.Mapped["User"] = orm.relationship("User", back_populates="reports")


class Bookmark(Base):
    """Database model representing a user's saved listing."""
    __tablename__ = "bookmarks"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    user_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    user: orm.Mapped["User"] = orm.relationship("User", back_populates="bookmarks")

    listing_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("listings.id"), nullable=False)
    listing: orm.Mapped["Listing"] = orm.relationship("Listing", back_populates="bookmarks")


class Listing(Base):
    """Database model representing an item listing posted by a seller."""
    __tablename__ = "listings"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    seller_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    seller: orm.Mapped["User"] = orm.relationship("User", back_populates="listings")

    @property
    def seller_name(self):
        return self.seller.display_name

    conversations: orm.Mapped[typing.List["Conversation"]] = orm.relationship("Conversation", back_populates="listing", foreign_keys="Conversation.listing_id")
    bookmarks: orm.Mapped[typing.List["Bookmark"]] = orm.relationship("Bookmark", back_populates="listing", foreign_keys="Bookmark.listing_id")
    reports: orm.Mapped[typing.List["ListingReport"]] = orm.relationship("ListingReport", back_populates="listing", foreign_keys="ListingReport.listing_id")

    title: orm.Mapped[str] = orm.mapped_column(sa.String(length=256), nullable=False)
    description: orm.Mapped[str] = orm.mapped_column(sa.Text, nullable=True)
    price: orm.Mapped[float] = orm.mapped_column(nullable=False)

    # NOTE: should category id be nullable?
    # NOTE: do we need bidirectional relationship?
    category_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("categories.id"), nullable=False)
    category: orm.Mapped["Category"] = orm.relationship("Category")

    course_tag_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("course_tags.id"), nullable=True)
    course_tag: orm.Mapped["CourseTag"] = orm.relationship("CourseTag")

    @property
    def category_name(self):
        return self.category.name

    @property
    def course_code(self):
        if self.course_tag:
            return self.course_tag.course_code
        return None

    pickup_location_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("pickup_locations.id"), nullable=True)
    pickup_location: orm.Mapped["PickupLocation"] = orm.relationship("PickupLocation")

    @property
    def pickup_location_name(self):
        return self.pickup_location.name

    status: orm.Mapped[ListingStatus] = orm.mapped_column(nullable=False, default=ListingStatus.SUBMITTED)
    view_count: orm.Mapped[int] = orm.mapped_column(nullable=False, default=0)
    message_count: orm.Mapped[int] = orm.mapped_column(nullable=False, default=0)

    images: orm.Mapped[typing.List["ListingImage"]] = orm.relationship("ListingImage", back_populates="listing", foreign_keys="ListingImage.listing_id", order_by="(ListingImage.display_order, ListingImage.id)")

    @property
    def top_image_path(self):
        if len(self.images) == 0:
            return None
        return self.images[0].image_path

    @property
    def image_paths(self):
        return [im.image_path for im in self.images]

    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())


class ListingImage(Base):
    """Database model representing an uploaded image attached to a listing."""
    __tablename__ = "listing_images"
    __table_args__ = (sa.Index("ix_listing_images_listing_id_display_order", "listing_id", "display_order"),)

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    listing_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("listings.id"), nullable=False)
    listing: orm.Mapped["Listing"] = orm.relationship("Listing", back_populates="images")

    image_path: orm.Mapped[str] = orm.mapped_column(sa.String(length=128), nullable=False)
    display_order: orm.Mapped[int] = orm.mapped_column(nullable=False, default=0)


class Review(Base):
    """Database model representing a review written by one user for another user."""
    __tablename__ = "reviews"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    user_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    user: orm.Mapped["User"] = orm.relationship("User", back_populates="reviews", foreign_keys=[user_id])

    author_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    author: orm.Mapped["User"] = orm.relationship("User", back_populates="reviews_written", foreign_keys=[author_id])

    score: orm.Mapped[float] = orm.mapped_column(nullable=False)
    review_text: orm.Mapped[str] = orm.mapped_column(sa.Text, nullable=True)
    title: orm.Mapped[str] = orm.mapped_column(sa.String(length=30), nullable=False)

    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())


class Category(Base):
    """Database model representing a listing category."""
    __tablename__ = "categories"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    name: orm.Mapped[str] = orm.mapped_column(sa.String(length=128), nullable=False, unique=True)


class CourseTag(Base):
    """Database model representing a course code tag that can be attached to listings."""
    __tablename__ = "course_tags"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    course_code: orm.Mapped[str] = orm.mapped_column(sa.String(length=64), nullable=False, unique=True)


class PickupLocation(Base):
    """Database model representing a possible pickup location for listings."""
    __tablename__ = "pickup_locations"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    name: orm.Mapped[str] = orm.mapped_column(sa.String(length=256), nullable=False, unique=True)
    description: orm.Mapped[str] = orm.mapped_column(sa.Text, nullable=True)


class SavedSearch(Base):
    """Database model representing a user's saved search criteria."""
    __tablename__ = "saved_searches"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    user_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    user: orm.Mapped["User"] = orm.relationship("User", back_populates="saved_searches")

    keyword: orm.Mapped[str] = orm.mapped_column(sa.String(length=1024), nullable=False)

    category_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("categories.id"), nullable=False)
    #category: orm.Mapped["Category"] = orm.relationship("Category", back_populates="saved_searches")

    pickup_location_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("pickup_locations.id"), nullable=False)
    #pickup_location: orm.Mapped["PickupLocation"] = orm.relationship("PickupLocation")

    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())


class Conversation(Base):
    """Database model representing a message thread between two users about a listing."""
    __tablename__ = "conversations"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    listing_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("listings.id"), nullable=True)
    listing: orm.Mapped[typing.Optional["Listing"]] = orm.relationship("Listing", back_populates="conversations")

    original_sender_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    original_sender: orm.Mapped["User"] = orm.relationship("User", back_populates="conversations_sent", foreign_keys=[original_sender_id])

    original_recipient_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    original_recipient: orm.Mapped["User"] = orm.relationship("User", back_populates="conversations_received", foreign_keys=[original_recipient_id])

    messages: orm.Mapped[typing.List["Message"]] = orm.relationship("Message", back_populates="conversation", foreign_keys="Message.conversation_id", order_by="Message.id")

    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    last_message: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class Message(Base):
    """Database model representing a single message in a conversation."""
    __tablename__ = "messages"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True)

    conversation_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("conversations.id"), nullable=False)
    conversation: orm.Mapped["Conversation"] = orm.relationship("Conversation", back_populates="messages")

    sender_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=False)
    sender: orm.Mapped["User"] = orm.relationship("User")

    message: orm.Mapped[str] = orm.mapped_column(sa.Text, nullable=False)
    is_read: orm.Mapped[bool] = orm.mapped_column(nullable=False, default=False)

    reports: orm.Mapped[typing.List["MessageReport"]] = orm.relationship("MessageReport", back_populates="message", foreign_keys="MessageReport.message_id")

    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
