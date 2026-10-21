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


def _secret_key():
    key = os.environ.get("SECRET_KEY")
    # Vercel sets VERCEL=1. A deployed site must never fall back to the public dev key,
    # because anyone could then forge the CSRF tokens that protect every form.
    if not key and os.environ.get("VERCEL"):
        raise RuntimeError("SECRET_KEY is not set. Add it in Vercel → Settings → Environment Variables.")
    return key or "dev-only-not-secret"


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Units offered on the food form. Add to this list to extend it.
    UNITS = ["g", "ml", "unit", "slice", "can"]
    # Serverless: open a connection per use and let Supabase's pooler do the pooling.
    # prepare_threshold=None turns off prepared statements, which the pooler doesn't support.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"poolclass": NullPool, "connect_args": {"prepare_threshold": None}}
        if SQLALCHEMY_DATABASE_URI.startswith("postgresql")
        else {}
    )


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
