from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound, IntegrityError
import sqlalchemy as sa
import sqlalchemy.orm as orm
import models, schemas, auth
from datetime import datetime
import shlex    # thanks stack overflow: https://stackoverflow.com/questions/79968/split-a-string-by-spaces-preserving-quoted-substrings-in-python#79985
import typing
import math


def get_listing_by_id(db: Session, listing_id: int) -> models.Listing | None:
    """Return the listing with the given ID, or None if no matching listing exists."""
    return db.query(models.Listing).filter_by(id=listing_id).first()


def get_listing_image_by_path(db: Session, image_path: str) -> models.ListingImage | None:
    """Return the listing image with the given image path, or None if no matching image exists."""
    return db.query(models.ListingImage).filter_by(image_path=image_path).first()


def create_course_tag(db: Session, name: str):
    """Create and return a new course tag with the given course code."""
    db_course = models.CourseTag(course_code=name)
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course


def create_category(db: Session, name: str):
    """Create and return a new listing category with the given name."""
    db_category = models.Category(name=name)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def create_pickup_location(db: Session, name: str, description: str):
    """Create and return a new pickup location with the given name and description."""
    db_location = models.PickupLocation(name=name, description=description)
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    return db_location


def create_listing_image(db: Session, image_path: str, listing_id: int):
    """Create and return a new image for an existing listing, using the next display order."""
    db_listing = get_listing_by_id(db, listing_id)
    if db_listing is None:
        return None

    max_display_order = db.query(sa.func.max(models.ListingImage.display_order)) \
        .filter_by(listing_id=listing_id) \
        .scalar()
    next_display_order = 0 if max_display_order is None else max_display_order + 1

    db_image = models.ListingImage(
            image_path=image_path,
            listing_id=listing_id,
            display_order=next_display_order
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


def create_listing(db: Session, req_listing: schemas.ListingCreateAuthorized):
    """Create and return a new listing with its category, pickup location, optional course tag, and images."""
    db_category = db.query(models.Category).filter_by(name=req_listing.category_name).first()
    if db_category is None:
        raise NoResultFound(f"could not find category {req_listing.category_name}")

    db_pickup_location = db.query(models.PickupLocation).filter_by(name=req_listing.pickup_location_name).first()
    if db_pickup_location is None:
        raise NoResultFound(f"could not find pickup location {req_listing.pickup_location_name}")

    db_course_tag = db.query(models.CourseTag).filter_by(course_code=req_listing.course_code).first()
    course_tag_id = None
    if db_course_tag:
        course_tag_id = db_course_tag.id

    db_listing = models.Listing(
        title=req_listing.title,
        description=req_listing.description,
        price=req_listing.price,
        seller_id=req_listing.seller.id,
        category_id=db_category.id,
        course_tag_id=course_tag_id,
        pickup_location_id=db_pickup_location.id
    )
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)

    for idx, im in enumerate(req_listing.images):
        db_image = models.ListingImage(
                listing_id=db_listing.id,
                image_path=im,
                display_order=idx
        )
        db.add(db_image)
        db.commit()

    return db_listing


def create_user(db: Session, req_user: schemas.UserCreate):
    """Create and return a new user after validating their SFSU email and hashing their password."""
    if req_user.email.split("@")[1] != "sfsu.edu":
        return "Users must have a valid SFSU email address."

    db_user = models.User(
            display_name=req_user.display_name,
            bio=req_user.bio,
            email=req_user.email,
            password_hash=auth.get_password_hash(req_user.password))

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except IntegrityError:
        db.rollback()
        return "Email or username is already taken."

    return db_user


def edit_user_moderator(db: Session, user_id: int, is_moderator: bool):
    """Update and return a user's moderator status, or None if the user does not exist."""
    db_user = db.query(models.User).filter_by(id=user_id).first()
    if not db_user:
        return None

    db_user.is_moderator = is_moderator
    db.commit()
    db.refresh(db_user)
    return db_user


def list_course_ids(db: Session):
    """Provide a list of course ID names."""

    db_course_tags = db.query(models.CourseTag).order_by(models.CourseTag.course_code).all()
    return [course_tag.course_code for course_tag in db_course_tags]


def list_categories(db: Session):
    """Provide a list of category names."""

    db_categories = db.query(models.Category).order_by(models.Category.name).all()
    return [category.name for category in db_categories]


def list_pickup_locations(db: Session):
    """Provide a list of pickup location names."""

    db_pickup_locations = db.query(models.PickupLocation).order_by(models.PickupLocation.name).all()
    return [location.name for location in db_pickup_locations]


def get_unapproved_listings(db: Session, current_user: models.User):
    """Return submitted listings awaiting approval if the current user is a moderator."""
    if not current_user.is_moderator:
        return None

    db_listings = db.query(models.Listing).filter_by(status=models.ListingStatus.SUBMITTED).all()
    db_listings = [schemas.ListingDisplayThumbnail.model_validate(listing) for listing in db_listings]

    return db_listings


def approve_listing(db: Session, listing_id: int):
    """Approve a submitted listing and return it, or False if it cannot be approved."""
    db_listing = db.query(models.Listing).filter_by(id = listing_id).first()
    if not db_listing:
        return False

    if db_listing.status != models.ListingStatus.SUBMITTED:
        return False

    db_listing.status = models.ListingStatus.ACTIVE
    db.commit()
    db.refresh(db_listing)
    return db_listing


def reject_listing(db: Session, listing_id: int):
    """Reject a submitted listing and return it, or False if it cannot be rejected."""
    db_listing = db.query(models.Listing).filter_by(id = listing_id).first()
    if not db_listing:
        return False

    if db_listing.status != models.ListingStatus.SUBMITTED:
        return False

    db_listing.status = models.ListingStatus.DELETED
    db.commit()
    db.refresh(db_listing)
    return db_listing


def search_listings(db: Session, query: schemas.ListingSearchQuery, user: models.User | None = None) -> typing.Tuple[int, int, typing.List[schemas.ListingDisplayThumbnail]]:
    """Search the database. Takes a ListingSearchQuery, optionally filters on category,
    price, pickup location, and returns a list of thumbnail displays (ListingDisplayThumbnail)."""

    # start the query
    db_listings = db.query(models.Listing).filter_by(status=models.ListingStatus.ACTIVE)

    # apply all our filters (if they exist)
    if query.min_price is not None:
        db_listings = db_listings.filter(models.Listing.price >= query.min_price)

    if query.max_price is not None:
        db_listings = db_listings.filter(models.Listing.price <= query.max_price)

    if len(query.categories) > 0:
        db_listings = db_listings.join(models.Category).filter(
        models.Category.name.in_(query.categories)
    )
    if len(query.pickup_locations) > 0:
        db_listings = db_listings.join(models.PickupLocation).filter(
        models.PickupLocation.name.in_(query.pickup_locations)
    )

    # use shlex to tokenize (so quoted phrases are merged)
    try:
        query_tokens = shlex.split(query.query)
    except ValueError:
        query_tokens = query.query.replace("\"", "").split()

    for ss in query_tokens:
        db_listings = db_listings.filter(sa.or_(models.Listing.title.like(f"%{ss}%"),
                                                models.Listing.description.like(f"%{ss}%")))

    # sort search
    if query.sort_by == schemas.ListingSortBy.PRICE_ASC:
        db_listings = db_listings.order_by(models.Listing.price.asc())
    elif query.sort_by == schemas.ListingSortBy.PRICE_DESC:
        db_listings = db_listings.order_by(models.Listing.price.desc())
    elif query.sort_by == schemas.ListingSortBy.CREATED_ASC:
        db_listings = db_listings.order_by(models.Listing.created_at.asc())
    elif query.sort_by == schemas.ListingSortBy.CREATED_DESC:
        db_listings = db_listings.order_by(models.Listing.created_at.desc())
    elif query.sort_by == schemas.ListingSortBy.ITEM_NAME_ASC:
        db_listings = db_listings.order_by(models.Listing.title.asc())
    elif query.sort_by == schemas.ListingSortBy.ITEM_NAME_DESC:
        db_listings = db_listings.order_by(models.Listing.title.desc())
    elif query.sort_by == schemas.ListingSortBy.MOST_VIEWED_ASC:
        db_listings = db_listings.order_by(models.Listing.view_count.asc())
    elif query.sort_by == schemas.ListingSortBy.MOST_VIEWED_DESC:
        db_listings = db_listings.order_by(models.Listing.view_count.desc())
    else:
    	# PostgreSQL-compatible ranking
    	db_listings = db_listings.order_by(
        	(
            		models.Listing.view_count -
            		(
                		sa.func.extract('epoch', sa.func.now()) -
                		sa.func.extract('epoch', models.Listing.created_at)
            		)
        	).desc()
    	)

    ITEMS_PER_PAGE = 15

    item_count = db_listings.count()
    page_count = int(math.ceil(db_listings.count() / ITEMS_PER_PAGE))

    db_listings = db_listings.offset(ITEMS_PER_PAGE * (query.page - 1)).limit(ITEMS_PER_PAGE)

    db_listings = db_listings.all()
    db_listings = [schemas.ListingDisplayThumbnail.model_validate(listing) for listing in db_listings]

    # add conversation stub
    if user:
        for listing in db_listings:
            conv = get_conversation(db, user, listing.id)
            if conv:
                listing.conversation_exists = True
                listing.conversation_id = conv.id
            listing.bookmarked = is_bookmarked(db, user, listing.id)

    return item_count, page_count, db_listings


def increment_listing_view(db: Session, listing_id: int):
    """Increment the view count for a listing, or raise NoResultFound if the listing does not exist."""
    db_listing = db.query(models.Listing).filter_by(id=listing_id).first()

    if db_listing is None:
        raise NoResultFound(f"No listing with id {listing_id}")

    db_listing.view_count += 1
    db.commit()


def get_user_by_id(db: Session, user_id: int) -> models.User:
    """Return the user with the given ID, or None if no matching user exists."""
    return db.query(models.User).filter_by(id=user_id).first()


def get_user_by_email(db: Session, email: str) -> models.User:
    """Return the user with the given email address, or None if no matching user exists."""
    return db.query(models.User).filter_by(email=email).first()


def get_user_conversations(db: Session, user: models.User):
    """Return conversation thumbnails for all conversations sent or received by the user."""
    conversations = []

    db_conversations_received = user.conversations_received
    for conv in db_conversations_received:
        preview = conv.messages[-1].message
        if len(preview) > 30:
            preview = f"{preview[:28]}..."
        conversations.append(schemas.UserConversationThumbnail(
            id = conv.id,
            preview = preview,
            other_user_name = conv.original_sender.display_name,
            unread = not conv.messages[-1].is_read,
            updated_at = conv.updated_at
        ))

    db_conversations_sent = user.conversations_sent
    for conv in db_conversations_sent:
        preview = conv.messages[-1].message
        if len(preview) > 30:
            preview = f"{preview[:28]}..."
        conversations.append(schemas.UserConversationThumbnail(
            id = conv.id,
            preview = preview,
            other_user_name = conv.original_recipient.display_name,
            unread = not conv.messages[-1].is_read,
            updated_at = conv.updated_at
        ))

    #conversations = sorted(conversations, key=lambda obj: obj.updated_at)

    return conversations


def send_message(db: Session, sender: models.User, message: schemas.SendMessage):
    """Create and return a new message in an existing conversation."""
    db_convo = db.query(models.Conversation).filter_by(id=message.conversation_id).first()
    if db_convo is None:
        return None
    db_convo.last_message = sa.func.now()

    db_message = models.Message(
            conversation_id = message.conversation_id,
            sender_id = sender.id,
            message = message.message
    )

    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def create_conversation(db: Session, sender: models.User, conversation: schemas.ConversationCreate):
    """Create and return a new conversation with an initial message, or return an existing conversation if one already exists."""
    db_conv_search = get_conversation(db, sender, conversation.listing_id)
    if db_conv_search:
        return db_conv_search.first()

    db_conversation = models.Conversation(
            original_sender_id = sender.id,
            original_recipient_id = conversation.recipient_id,
            listing_id = conversation.listing_id
    )

    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)

    send_message(db, sender, schemas.SendMessage(
        conversation_id = db_conversation.id,
        message = conversation.initial_message
    ))
    db.refresh(db_conversation)
    return db_conversation


def get_conversation(db: Session, sender: models.User, listing_id: int):
    """Return the conversation started by the given user for the given listing, or None if it does not exist."""
    db_conversation = db.query(models.Conversation).filter_by(listing_id=listing_id, original_sender_id=sender.id)
    return db_conversation.first()


def get_messages(db: Session, current_user: models.User, conversation_id: int):
    """Return viewable messages for a conversation, marking which messages were sent by the current user."""
    db_conversation = db.query(models.Conversation).filter_by(id=conversation_id).first()
    if not db_conversation:
        return []

    messages = []
    for message in db_conversation.messages:
        messages.append(schemas.MessageView(
            content = message.message,
            is_from_current_user = message.sender_id == current_user.id
        ))

    return messages


def try_mark_conversation_read(db: Session, current_user: models.User, conversation_id: int):
    """Mark the latest message in a conversation as read if it was sent by another user."""
    db_convo = db.query(models.Conversation).filter_by(id=conversation_id).first()
    if not db_convo:
        return

    db_message = db_convo.messages[-1]
    if db_message.sender_id != current_user.id:
        db_message.is_read = True
    db.commit()
    db.refresh(db_convo)
    return db_convo


def create_bookmark(db: Session, current_user: models.User, listing_id: int):
    """Create and return a bookmark for the current user and listing."""
    db_bookmark = models.Bookmark(user_id=current_user.id, listing_id=listing_id)
    db.add(db_bookmark)
    db.commit()
    db.refresh(db_bookmark)
    return db_bookmark


def delete_bookmark(db: Session, current_user: models.User, listing_id: int):
    """Delete the current user's bookmark for a listing and return whether deletion succeeded."""
    db_bookmark = db.query(models.Bookmark).filter_by(listing_id=listing_id, user_id=current_user.id).first()
    if not db_bookmark:
        return False
    db.delete(db_bookmark)
    db.commit()
    return True


def is_bookmarked(db: Session, current_user: models.User, listing_id: int):
    """Return True if the current user has bookmarked the listing, otherwise False."""
    db_bookmark = db.query(models.Bookmark).filter_by(listing_id=listing_id, user_id=current_user.id).first()
    if db_bookmark is None:
        return False
    return True


def get_bookmarked_listings(db: Session, current_user: models.User):
    """Return all listings bookmarked by the current user."""
    listings = []
    for bookmark in current_user.bookmarks:
        listings.append(get_listing_by_id(db, bookmark.listing_id))
    return listings



def get_reviews_for_user(db: Session, current_user: models.User):
    """Return reviews for the current user, ordered from newest to oldest."""
    return db.query(models.Review) \
        .filter_by(user_id=current_user.id) \
        .order_by(models.Review.created_at.desc()) \
        .all()


def create_review(db: Session, current_user: models.User, review: schemas.ReviewCreate):
    """Create or update a review written by the current user for another user."""
    db_user = get_user_by_id(db, review.user_id)
    if db_user is None:
        return None

    db_review = db.query(models.Review).filter_by(
        user_id=review.user_id,
        author_id=current_user.id
    ).first()

    if db_review is None:
        db_review = models.Review(
            user_id=review.user_id,
            author_id=current_user.id,
            score=review.score,
            title=review.title,
            review_text=review.review_text
        )
        db.add(db_review)
    else:
        db_review.score = review.score
        db_review.title = review.title
        db_review.review_text = review.review_text

    db.commit()
    db.refresh(db_review)
    return db_review


def update_user_settings(db: Session, current_user: models.User, settings_update: schemas.SettingsUpdate):
    """Update and return the current user's profile settings."""
    current_user.display_name = settings_update.display_name
    if settings_update.pronouns is not None:
        current_user.pronouns = settings_update.pronouns
    if settings_update.bio is not None:
        current_user.bio = settings_update.bio
    current_user.notifications_enabled = settings_update.notifications_enabled
    if settings_update.profile_image_path is not None:
        current_user.profile_image_path = settings_update.profile_image_path

    try:
        db.commit()
        db.refresh(current_user)
    except IntegrityError:
        db.rollback()
        return "Display name is already taken."

    return current_user


def update_user_password(db: Session, current_user: models.User, password_update: schemas.PasswordUpdate):
    """Update and return the current user's password after validating the current and confirmed passwords."""
    if password_update.new_password != password_update.confirm_password:
        return "New passwords do not match."

    if not auth.verify_password(password_update.current_password, current_user.password_hash):
        return "Current password is incorrect."

    current_user.password_hash = auth.get_password_hash(password_update.new_password)
    db.commit()
    db.refresh(current_user)
    return current_user


def deactivate_user(db: Session, current_user: models.User):
    """Deactivate and return the current user account."""
    current_user.is_deactivated = True
    db.commit()
    db.refresh(current_user)
    return current_user


def delete_user_account(db: Session, current_user: models.User):
    """Anonymize, deactivate, and return the current user account."""
    current_user.display_name = f"deleted_user_{current_user.id}"
    current_user.email = f"deleted_user_{current_user.id}@deleted.local"
    current_user.bio = None
    current_user.pronouns = None
    current_user.profile_image_path = None
    current_user.notifications_enabled = False
    current_user.is_deactivated = True
    db.commit()
    db.refresh(current_user)
    return current_user


def get_listings_for_user(db: Session, current_user: models.User):
    """Return all listings owned by the current user."""
    return current_user.listings


def ban_user(db: Session, current_user: models.User, banned_user_id: int):
    """Ban a user by ID if the current user is a moderator."""
    if not current_user.is_moderator:
        return None

    db_user = get_user_by_id(db, banned_user_id)
    db_user.is_banned = True
    db_user.display_name = f"{db_user.display_name} (BANNED)"
    db.commit()
    db.refresh(db_user)
    return db_user


def report_user(db: Session, current_user: models.User, user_id: int):
    """Create and return a report for a user."""
    db_report = models.UserReport(user_id = user_id)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def report_listing(db: Session, current_user: models.User, listing_id: int):
    """Create and return a report for a listing."""
    db_report = models.ListingReport(listing_id = listing_id)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def report_message(db: Session, current_user: models.User, message_id: int):
    """Create and return a report for a message."""
    db_report = models.MessageReport(message_id = message_id)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def resolve_listing_report(db: Session, current_user: models.User, report_id: int):
    """Resolve and return a listing report if the current user is a moderator."""
    if not current_user.is_moderator:
        return None

    db_report = db.query(models.ListingReport).filter_by(id = report_id).first()
    if db_report:
        db_report.status = models.ReportStatus.RESOLVED
    db.commit()
    db.refresh(db_report)
    return db_report


def resolve_message_report(db: Session, current_user: models.User, report_id: int):
    """Resolve and return a message report if the current user is a moderator."""
    if not current_user.is_moderator:
        return None

    db_report = db.query(models.MessageReport).filter_by(id = report_id).first()
    if db_report:
        db_report.status = models.ReportStatus.RESOLVED
    db.commit()
    db.refresh(db_report)
    return db_report


def resolve_user_report(db: Session, current_user: models.User, report_id: int):
    """Resolve and return a user report if the current user is a moderator."""
    if not current_user.is_moderator:
        return None

    db_report = db.query(models.UserReport).filter_by(id = report_id).first()
    if db_report:
        db_report.status = models.ReportStatus.RESOLVED
    db.commit()
    db.refresh(db_report)
    return db_report


def get_user_reports(db: Session):
    """Return all submitted user reports."""
    return db.query(models.UserReport).filter_by(status = models.ReportStatus.SUBMITTED).all()


def get_listing_reports(db: Session):
    """Return all submitted listing reports."""
    return db.query(models.ListingReport).filter_by(status = models.ReportStatus.SUBMITTED).all()


def get_message_reports(db: Session):
    """Return all submitted message reports."""
    return db.query(models.MessageReport).filter_by(status = models.ReportStatus.SUBMITTED).all()


def get_submitted_listings(db: Session):
    """Return all listings with submitted status."""
    return db.query(models.Listing).filter_by(status = models.ListingStatus.SUBMITTED).all()
