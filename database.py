import sqlalchemy as sa
import sqlalchemy.orm as orm
from sqlalchemy import event
import pydantic_settings
import os
import flask
import functools


class Settings(pydantic_settings.BaseSettings):
    database_url: str | None = os.getenv("DATABASE_URL")

    class Config:
        env_file = ".env"


settings = Settings()

if settings.database_url is None:
    raise Exception("Could not find database URL in environment variables!!")
engine = sa.create_engine(settings.database_url,
                          pool_size=2,
                          max_overflow=2,
                          pool_timeout=10,
                          pool_recycle=1800,
                          pool_pre_ping=True)
SessionLocal = orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = orm.declarative_base()


def get_db():
    """Dependency that provides a database session."""
    if 'db' not in flask.g:
        flask.g.db = SessionLocal()
    return flask.g.db


def with_db(f):
    """Decorator that injects a database session into the wrapped function."""
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        db = get_db()

        return f(*args, **kwargs, db=db)
    return wrapped
