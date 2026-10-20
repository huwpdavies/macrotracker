import os

from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

# Reads a local .env file if there is one. On Vercel the variables come from project settings.
load_dotenv()


def _database_uri():
    url = os.environ.get("DATABASE_URL")
    if not url:
        return "sqlite:///local.db"
    # SQLAlchemy needs to be told to use the psycopg (v3) driver.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-secret")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Serverless: open a connection per use and let Supabase's pooler do the pooling.
    # prepare_threshold=None turns off prepared statements, which the pooler doesn't support.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"poolclass": NullPool, "connect_args": {"prepare_threshold": None}}
        if SQLALCHEMY_DATABASE_URI.startswith("postgresql")
        else {}
    )


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
