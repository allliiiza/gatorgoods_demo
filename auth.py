import secrets
import os
import typing
import datetime
import functools
from jose import jwt, JWTError
import passlib.context

from flask import request, abort
import flask

from sqlalchemy.orm import Session

import crud, models, database

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = passlib.context.CryptContext(schemes=["bcrypt"])


def verify_password(plain_password, hashed_password):
    """Return whether a plain-text password matches a stored password hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Return a hashed version of the given password."""
    return pwd_context.hash(password)


def login(email: str, password: str, db: Session):
    """Authenticate a user by email and password, store their email in the session, and return the user."""
    db_user = crud.get_user_by_email(db, email)

    if not db_user:
        return None

    if not verify_password(password, db_user.password_hash):
        return None

    if db_user.is_banned or db_user.is_deactivated:
        return None

    flask.session["user_email"] = db_user.email

    return db_user


def logout():
    """Clear the current Flask session to log out the user."""
    flask.session.clear()


def get_current_user(db: Session):
    """Return the currently logged-in user from the Flask session, or None if no user is logged in."""
    email = flask.session.get("user_email")
    if email is None:
        return None

    db_user = crud.get_user_by_email(db, email)

    return db_user


def login_required(f):
    """Require a logged-in, active user before allowing access to the wrapped route."""
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        db = kwargs.pop("db")
        if not db:
            db = database.get_db()

        email = get_current_user(db)
        if email is None:
            # TODO: add "message"
            return flask.redirect(flask.url_for("serve_authentication", mode="login", msg="You must log in to view this page."))

        current_user = get_current_user(db)
        if current_user is None:
            return flask.redirect(flask.url_for("serve_dashboard", mode="login", msg="You must log in to view this page."))
        if current_user.is_banned or current_user.is_deactivated:
            logout()
            return flask.redirect(flask.url_for("serve_dashboard", mode="login", msg="You are banned."))

        return f(*args, **kwargs, db=db, current_user=current_user)
    return wrapped


def verify_member_match(member_a: models.User | None, member_b: models.User | None):
    """Just throws forbidden exception if the members do not match."""
    if member_a is None \
            or member_b is None \
            or member_a.id != member_b.id:
        # raise exception even for nonexistent member so members cannot discover each other
        abort(403, "You do not have permission to alter this member.")
