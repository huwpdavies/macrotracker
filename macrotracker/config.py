import os

from dotenv import load_dotenv

# Reads a local .env file if there is one. On Vercel the variables come from project settings.
load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-secret")
    DATABASE_URL = os.environ.get("DATABASE_URL")
