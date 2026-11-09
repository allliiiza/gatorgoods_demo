import flask
import json
import random
import secrets
import os
from pathlib import Path
from pydantic import ValidationError


from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound


import crud
import schemas
import auth
import database
import images
import models

app = flask.Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

SECRET_KEY = os.getenv("GATORGOODS_SECRET_KEY")
if SECRET_KEY is None:
    raise Exception("You must set environment variable GATORGOODS_SECRET_KEY to run this API.")
app.config["SECRET_KEY"] = SECRET_KEY


# ===== main routes =====

# TODO: if user is signed in, reroute to dashboard!!
@app.route('/')
@app.route('/index.html')
@database.with_db
def serve_index(db: Session):
    """Render the home page, or redirect logged-in users to the dashboard."""
    db_user = auth.get_current_user(db)
    if db_user:
        return flask.redirect("dashboard.html")

    categories = crud.list_categories(db)

    return flask.render_template('index.html', categories=categories, logged_in=False)


@app.route("/message/<int:conversation_id>", methods=["POST"])
@database.with_db
@auth.login_required
def message(conversation_id: int, db: Session, current_user: models.User):
    """Send a message in an existing conversation and redirect back to the inbox."""
    print(flask.request.form)
    message = flask.request.form.get("content")
    if not message:
        return flask.redirect(flask.url_for("inbox", conversation_id=conversation_id))

    new_message = crud.send_message(db, current_user, schemas.SendMessage(
        conversation_id=conversation_id,
        message=message
    ))

    print(new_message)

    return flask.redirect(flask.url_for("inbox", conversation_id=conversation_id))


@app.route("/new-conversation/<int:listing_id>", methods=["POST"])
@database.with_db
@auth.login_required
def new_conversation(listing_id: int, db: Session, current_user: models.User):
    """Create a new conversation for a listing and send the initial message."""
    db_listing = crud.get_listing_by_id(db, listing_id)
    if not db_listing:
        flask.abort(404, "Listing ID not found")

    # you can't send a message to yourself
    if current_user.id == db_listing.seller_id:
        return flask.redirect(flask.url_for("inbox"))

    message = flask.request.form.get("message")
    if not message:
        return flask.redirect(flask.url_for("inbox"))

    db_conversation = crud.create_conversation(db, current_user, schemas.ConversationCreate(
        recipient_id=db_listing.seller_id,
        listing_id=listing_id,
        initial_message = message
    ))

    return flask.redirect(flask.url_for("inbox", conversation_id=db_conversation.id))


@app.post("/toggle-bookmark/<int:listing_id>")
@database.with_db
@auth.login_required
def toggle_bookmark(db: Session, current_user: models.User, listing_id: int):
    """Toggle the current user's bookmark for a listing and return a JSON success response."""
    success = True
    if crud.is_bookmarked(db, current_user, listing_id):
        success = crud.delete_bookmark(db, current_user, listing_id)
    else:
        db_bookmark = crud.create_bookmark(db, current_user, listing_id)
        if not db_bookmark:
            success = False
    return flask.jsonify({"success": success})


@app.route("/inbox.html")
@app.route("/inbox")
@database.with_db
@auth.login_required
def inbox(db: Session, current_user: models.User):
    """Render the current user's inbox and selected conversation messages."""
    conversations = list(reversed(crud.get_user_conversations(db, current_user)))

    selected_id = flask.request.args.get("conversation_id", default=1, type=int)

    selected_conversation = None
    for convo in conversations:
        if convo.id == selected_id:
            selected_conversation = convo
            crud.try_mark_conversation_read(db, current_user, convo.id)
            break

    messages = crud.get_messages(db, current_user, selected_id)

    return flask.render_template(
        "inbox.html",
        conversations=conversations,
        selected_conversation=selected_conversation,
        messages=messages,
        current_user=current_user,
        logged_in=True
    )


@app.route("/edit-profile.html")
@database.with_db
@auth.login_required
def serve_edit_profile(db, current_user):
    """Render the edit profile page for the current user."""
    return flask.render_template(
            "edit-profile.html",
            current_user=current_user,
            logged_in=True
    )

@app.route("/profile.html")
@database.with_db
@auth.login_required
def serve_profile(db: Session, current_user: models.User):
    """Render a user's profile page with their reviews and active listings."""
    user_id = flask.request.args.get("id")
    if user_id is None:
        user_id = current_user.id

    try:
        user_id = int(user_id)
    except ValueError:
        user_id = current_user.id

    db_user = crud.get_user_by_id(db, user_id)
    if not db_user:
        db_user = current_user

    reviews = crud.get_reviews_for_user(db, db_user)

    listings = [listing for listing in db_user.listings if listing.status == models.ListingStatus.ACTIVE]

    return flask.render_template(
            "profile.html",
            logged_in=True,
            user=db_user,
            reviews=reviews,
            current_user=current_user,
            listings=listings
    )

@app.route("/settings.html")
@database.with_db
@auth.login_required
def serve_settings(db: Session, current_user: models.User):
    """Render the settings page for the current user."""
    return flask.render_template(
            "settings.html",
            current_user=current_user,
            msg=flask.request.args.get("msg"),
            logged_in=True
    )


@app.route("/update-settings", methods=["POST"])
@database.with_db
@auth.login_required
def update_settings(db: Session, current_user: models.User):
    """Validate and update the current user's profile settings."""
    profile_image_path = images.upload_profile_image(current_user)
    print(profile_image_path)

    try:
        settings_update = schemas.SettingsUpdate(
            display_name=(flask.request.form.get("display_name") or "").strip(),
            pronouns=((flask.request.form.get("pronouns") or "").strip() or None),
            bio=((flask.request.form.get("bio") or "").strip() or None),
            notifications_enabled=flask.request.form.get("notifications_enabled") == "on",
            profile_image_path=profile_image_path
        )
    except ValidationError:
        return flask.redirect(flask.url_for("serve_settings", msg="Please check your profile settings fields."))

    result = crud.update_user_settings(db, current_user, settings_update)
    if type(result) == str:
        return flask.redirect(flask.url_for("serve_settings", msg=result))

    return flask.redirect(flask.url_for("serve_settings", msg="Settings updated."))


@app.route("/update-password", methods=["POST"])
@database.with_db
@auth.login_required
def update_password(db: Session, current_user: models.User):
    """Validate and update the current user's password."""
    try:
        password_update = schemas.PasswordUpdate(
            current_password=flask.request.form.get("current_password") or "",
            new_password=flask.request.form.get("new_password") or "",
            confirm_password=flask.request.form.get("confirm_password") or ""
        )
    except ValidationError:
        return flask.redirect(flask.url_for("serve_settings", msg="Password must be at least 8 characters."))

    result = crud.update_user_password(db, current_user, password_update)
    if type(result) == str:
        return flask.redirect(flask.url_for("serve_settings", msg=result))

    return flask.redirect(flask.url_for("serve_settings", msg="Password updated."))


@app.route("/deactivate-account", methods=["POST"])
@database.with_db
@auth.login_required
def deactivate_account(db: Session, current_user: models.User):
    """Deactivate the current user's account, log them out, and redirect to login."""
    crud.deactivate_user(db, current_user)
    auth.logout()
    return flask.redirect(flask.url_for("serve_authentication", mode="login", msg="Your account has been deactivated."))


@app.route("/delete-account", methods=["POST"])
@database.with_db
@auth.login_required
def delete_account(db: Session, current_user: models.User):
    """Delete the current user's account, log them out, and redirect to login."""
    crud.delete_user_account(db, current_user)
    auth.logout()
    return flask.redirect(flask.url_for("serve_authentication", mode="login", msg="Your account has been deleted."))

@app.route("/dashboard.html")
@database.with_db
@auth.login_required
def serve_dashboard(db: Session, current_user: models.User):
    """Render the dashboard with the current user's listings, bookmarks, reviews, and form options."""
    return flask.render_template(
            "dashboard.html",
            user = current_user,
            display_name = current_user.display_name,
            bio = current_user.bio,
            listings_active = [listing for listing in current_user.listings if listing.status == models.ListingStatus.ACTIVE],
            listings_review = [listing for listing in current_user.listings if listing.status == models.ListingStatus.SUBMITTED],
            bookmarks = crud.get_bookmarked_listings(db, current_user),
            reviews = crud.get_reviews_for_user(db, current_user),
            categories = crud.list_categories(db),
            course_tags = crud.list_course_ids(db),
            pickup_locations = crud.list_pickup_locations(db),
            msg = flask.request.args.get("msg"),
            logged_in=True
    )

@app.route("/create-listing", methods=["POST"])
@database.with_db
@auth.login_required
def create_listing(db: Session, current_user: models.User):
    """Validate listing form data, create a submitted listing, and upload its images."""
    upload_files = images.get_upload_files()
    if len(upload_files) == 0:
        return flask.redirect(flask.url_for("serve_dashboard", msg="Please add at least one listing image."))

    for uploaded_file in upload_files:
        images.verify_image_upload(uploaded_file)
        images.get_allowed_image_suffix(uploaded_file.filename)

    course_code = (flask.request.form.get("course_code") or flask.request.form.get("course_id") or "").strip()
    if course_code == "" or course_code == "None":
        course_code = None

    print(flask.request.form)

    try:
        listing_request = schemas.ListingCreateAuthorized(
            title=(flask.request.form.get("title") or "").strip(),
            description=((flask.request.form.get("description") or "").strip() or None),
            price=flask.request.form.get("price", type=float),
            category_name=(flask.request.form.get("category") or flask.request.form.get("category") or "").strip(),
            course_code=course_code,
            pickup_location_name=(flask.request.form.get("pickup_location") or flask.request.form.get("pickup_location") or "").strip(),
            images=[],
            seller=schemas.UserReference.model_validate(current_user)
        )
    except ValidationError:
        return flask.redirect(flask.url_for("serve_dashboard", msg="Please check the listing form fields."))

    try:
        db_listing = crud.create_listing(db, listing_request)
    except NoResultFound as exc:
        return flask.redirect(flask.url_for("serve_dashboard", msg=str(exc)))

    images.upload_listing_images(db, current_user, db_listing.id)
    return flask.redirect(flask.url_for("serve_dashboard", msg="Listing submitted for approval."))


@app.route("/reviews/<int:user_id>", methods=["POST"])

@database.with_db
@auth.login_required
def submit_review(db: Session, current_user: models.User, user_id: int):
    """Create or update a review for a user and redirect back to the previous page."""
    redirect_target = flask.request.form.get("next") or flask.request.referrer or flask.url_for("serve_dashboard")

    try:
        review = schemas.ReviewCreate(
            user_id=user_id,
            score=flask.request.form.get("rating", type=int),
            title=(flask.request.form.get("review_title") or "").strip(),
            review_text=((flask.request.form.get("review_text") or "").strip() or None)
        )
    except ValidationError as exc:
        flask.abort(400, exc.errors())
    result = crud.create_review(db, current_user, review)
    if result is None:
        flask.abort(404, "Listing ID not found")
    if result is False:
        flask.abort(403, "You cannot review your own listing.")

    return flask.redirect(redirect_target)


@app.route("/listing-review")
@app.route("/listing-review.html")
@database.with_db
@auth.login_required
def listing_review(db: Session, current_user: models.User):
    """Render the listing review page for moderators."""
    listings = crud.get_unapproved_listings(db, current_user)
    if listings is None:
        flask.abort(403, "You must be a moderator to view this page.")

    return flask.render_template(
        "listing-review.html",
        listings=listings,
        current_user=current_user,
        logged_in=True
    )


@app.route("/approve/<int:listing_id>", methods=["POST", "GET"])
@database.with_db
@auth.login_required
def approve_listing(db: Session, current_user: models.User, listing_id: int):
    """Approve a submitted listing if the current user is a moderator."""
    if not current_user.is_moderator:
        flask.abort(403, "You must be a moderator to perform this action.")

    result = crud.approve_listing(db, listing_id)
    return flask.redirect(flask.url_for("serve_dashboard"))


@app.route("/reject/<int:listing_id>", methods=["POST", "GET"])
@database.with_db
@auth.login_required
def reject_listing(db: Session, current_user: models.User, listing_id: int):
    """Reject a submitted listing if the current user is a moderator."""
    if not current_user.is_moderator:
        flask.abort(403, "You must be a moderator to perform this action.")

    result = crud.reject_listing(db, listing_id)
    return flask.redirect(flask.url_for("serve_dashboard"))


@app.route("/search")
@app.route("/search.html")
@database.with_db
def serve_search(db: Session):
    """Render the search page with filtered listing results."""
    # only take the first 40 characters of a query, for validation purposes
    query_text = flask.request.args.get("query", "").strip()[:40]

    selected_category = flask.request.args.get("category", "").strip()
    page = flask.request.args.get("page", type=int)
    min_price = flask.request.args.get("min_price", type=float)
    max_price = flask.request.args.get("max_price", type=float)

    current_user = auth.get_current_user(db)

    search_query = schemas.ListingSearchQuery(
        query=query_text,
        min_price=min_price,
        max_price=max_price,
        categories=[selected_category] if selected_category else [],
        page=page if page is not None and page > 0 else 1
    )

    item_count, page_count, listings = crud.search_listings(db, search_query, current_user)
    categories = crud.list_categories(db)

    return flask.render_template(
        "search.html",
        listings=listings,
        categories=categories,
        query_text=query_text,
        selected_category=selected_category,
        min_price=min_price,
        max_price=max_price,
        result_count=item_count,
        page_count = page_count,
        current_user=current_user,
        logged_in=current_user is not None
    )

@app.route("/api/listings/<int:listing_id>/images", methods=["POST"])
@database.with_db
@auth.login_required
def upload_listing_images(db, current_user, listing_id):
    """Upload images for a listing and return the saved image paths as JSON."""
    saved_images = images.upload_listing_images(db, current_user, listing_id)

    return flask.jsonify({"images": saved_images}), 201


@app.route("/listing-images/<image_name>")
@database.with_db
@auth.login_required
def serve_listing_image(db, current_user, image_name):
    """Serve a protected listing image if it exists and is registered in the database."""
    image_path = flask.url_for("serve_listing_image", image_name=image_name)
    db_image = crud.get_listing_image_by_path(db, image_path)
    if db_image is None:
        flask.abort(404, "Listing image not found.")

    # Block-list ownership checks can be added here once that feature is implemented.
    absolute_image_path = images.PROTECTED_IMAGE_DIR / image_name
    if not absolute_image_path.is_file():
        flask.abort(404, "Listing image file is missing.")

    return flask.send_from_directory(str(images.PROTECTED_IMAGE_DIR), image_name)

@app.route("/profile-images/<image_name>")
def serve_profile_image(image_name):
    """Serve a profile image file if it exists."""
    absolute_image_path = images.PROFILE_IMAGE_DIR / image_name
    if not absolute_image_path.is_file():
        flask.abort(404, "Profile image file is missing.")

    return flask.send_from_directory(str(images.PROFILE_IMAGE_DIR), image_name)


@app.teardown_appcontext
def close_db(error):
    """Close the database session stored in Flask's request context."""
    db: Session = flask.g.pop('db', None)
    if db is not None:
        db.close()

# ===== team member pages =====

# helper functions
def serve_team_member(person):
    """Render a team member profile page using data from the team member JSON file."""
    # read team member info from json file
    with open("static/team-member-info.json") as file:
        team = json.load(file)
    team_member = team[person]

    # return fill out team-member template with info
    return flask.render_template('team-member.html', team_member=team_member)

# routes
@app.route("/team.html")
def serve_team():
    """Render the team page with all team members."""
    with open("static/team-member-info.json") as file:
        team = json.load(file)

    return flask.render_template("team.html", team_list=team.values())

@app.route('/Aliza.html')
def serve_aliza():
    """Render Aliza's team member page."""
    return serve_team_member("Aliza")

@app.route('/Jasmine.html')
def serve_jasmine():
    """Render Jasmine's team member page."""
    return serve_team_member("Jasmine")

@app.route('/Evan.html')
def serve_evan():
    """Render Evan's team member page."""
    return serve_team_member("Evan")

@app.route('/Jared.html')
def serve_jared():
    """Render Jared's team member page."""
    return serve_team_member("Jared")

@app.route('/Daniel.html')
def serve_daniel():
    """Render Daniel's team member page."""
    return serve_team_member("Daniel")

@app.route('/Sarah.html')
def serve_sarah():
    """Render Sarah's team member page."""
    return serve_team_member("Sarah")

@app.route('/Mithil.html')
def serve_mithil():
    """Render Mithil's team member page."""
    return serve_team_member("Mithil")

@app.route("/authentication")
@app.route("/authentication.html")
@database.with_db
def serve_authentication(db: Session):
    """Render the login or signup page with featured listing previews."""
    db = database.get_db()

    mode = flask.request.args.get("mode", "login").strip()

    if mode not in ["login", "signup"]:
        mode = "login"

    search_query = schemas.ListingSearchQuery(
        query="",
        categories=[]
    )

    logged_in = auth.get_current_user(db) is not None

    _, _, showcase_listings = crud.search_listings(db, search_query)

    random.shuffle(showcase_listings)

    left_featured_listings = showcase_listings
    right_featured_listings = list(reversed(showcase_listings))

    msg = flask.request.args.get("msg")

    return flask.render_template(
        "authentication.html",
        mode=mode,
        left_featured_listings=left_featured_listings,
        right_featured_listings=right_featured_listings,
        msg = msg,
        logged_in = logged_in
    )


@app.route("/login", methods=["POST"])
def serve_login():
    """Authenticate a user and redirect them to the dashboard on success."""
    db = database.get_db()


    user_email = flask.request.form.get("email")
    user_password = flask.request.form.get("password")
    if user_email is None or user_password is None:
        flask.abort(400)

    db_user = auth.login(user_email, user_password, db)
    if db_user is None:
        return flask.redirect("/authentication.html?mode=login&msg=Unrecognized user credentials! Please try again.")

    
    return flask.redirect("/dashboard.html")


@app.route("/signup", methods=["POST"])
@database.with_db
def serve_signup(db: Session):
    """Create a new user account, log the user in, and redirect to the dashboard."""
    db = database.get_db()

    email = flask.request.form.get("email")
    display_name = flask.request.form.get("display_name")
    password = flask.request.form.get("password")
    confirm_password = flask.request.form.get("confirm_password")

    if password != confirm_password:
        return flask.redirect(flask.url_for("serve_authentication", mode="signup", msg="Passwords do not match."))

    if email is None or display_name is None or password is None:
        return flask.redirect(flask.url_for("serve_authentication", mode="signup", msg="Please fill out all required fields."))

    r = crud.create_user(db, schemas.UserCreate(
        email = email,
        password = password,
        display_name = display_name
    ))

    if type(r) == str:
        return flask.redirect(flask.url_for("serve_authentication", mode="signup", msg=r))

    db_user = auth.login(email, password, db)
    if db_user is None:
        return flask.redirect("/authentication.html?mode=login&msg=Unrecognized user credentials! Please try again.")

    return flask.redirect("/dashboard.html")


@app.route("/moderator.html")
@database.with_db
@auth.login_required
def moderator(db: Session, current_user: models.User):
    """Render the moderator dashboard for reviewing reports and submitted listings."""
    if not current_user.is_moderator:
        flask.abort(403, "You must be a moderator to view this page.")

    user_reports = crud.get_user_reports(db)
    message_reports = crud.get_message_reports(db)
    listing_reports = crud.get_listing_reports(db)
    submitted_listings = crud.get_submitted_listings(db)

    return flask.render_template("/moderator.html",
                                 user_reports=user_reports,
                                 message_reports=message_reports,
                                 listing_reports=listing_reports,
                                 submitted_listings=submitted_listings,
                                 current_user=current_user,
                                 logged_in = True
    )


@app.route("/ban/<int:user_id>", methods=["POST"])
@database.with_db
@auth.login_required
def ban_user(db: Session, current_user: models.User, user_id: int):
    """Ban a user if the current user is a moderator."""
    if not current_user.is_moderator:
        flask.abort(403, "You must be a moderator to perform this function.")

    crud.ban_user(db, current_user, user_id)
    return flask.redirect("/moderator.html")


@app.route("/resolve-listing/<int:report_id>", methods=["POST"])
@database.with_db
@auth.login_required
def resolve_listing_report(db: Session, current_user: models.User, report_id: int):
    """Resolve a listing report if the current user is a moderator."""
    if not current_user.is_moderator:
        flask.abort(403, "You must be a moderator to perform this function.")

    crud.resolve_listing_report(db, current_user, report_id)
    return flask.redirect("/moderator.html")


@app.route("/resolve-user/<int:report_id>", methods=["POST"])
@database.with_db
@auth.login_required
def resolve_user_report(db: Session, current_user: models.User, report_id: int):
    """Resolve a user report if the current user is a moderator."""
    if not current_user.is_moderator:
        flask.abort(403, "You must be a moderator to perform this function.")

    crud.resolve_user_report(db, current_user, report_id)
    return flask.redirect("/moderator.html")


@app.route("/resolve-message/<int:report_id>", methods=["POST"])
@database.with_db
@auth.login_required
def resolve_message_report(db: Session, current_user: models.User, report_id: int):
    """Resolve a message report if the current user is a moderator."""
    if not current_user.is_moderator:
        flask.abort(403, "You must be a moderator to perform this function.")

    crud.resolve_message_report(db, current_user, report_id)
    return flask.redirect("/moderator.html")


@app.route("/report-user/<int:user_id>", methods=["POST"])
@database.with_db
@auth.login_required
def report_user(db: Session, current_user: models.User, user_id: int):
    """Create a user report and redirect to the dashboard."""
    crud.report_user(db, current_user, user_id)
    return flask.redirect("/dashboard.html")


@app.route("/report-listing/<int:listing_id>", methods=["POST"])
@database.with_db
@auth.login_required
def report_listing(db: Session, current_user: models.User, listing_id: int):
    """Create a listing report and redirect to the dashboard."""
    crud.report_listing(db, current_user, listing_id)
    return flask.redirect("/dashboard.html")


@app.route("/report-message/<int:message_id>", methods=["POST"])
@database.with_db
@auth.login_required
def report_message(db: Session, current_user: models.User, message_id: int):
    """Create a message report and redirect to the dashboard."""
    crud.report_message(db, current_user, message_id)
    return flask.redirect("/dashboard.html")


@app.route("/logout", methods=["GET", "POST"])
def serve_logout():
    """Log out the current user and redirect to the login page."""
    auth.logout()

    return flask.redirect(flask.url_for("serve_authentication", mode="login", msg="You are now logged out."))


# ===== start server =====
if __name__ == '__main__':
    app.run(debug=True, port=8080)
