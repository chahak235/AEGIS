import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Read DATABASE_URL from backend/.env (never committed to Git).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _database_url() -> str:
    url = os.environ["DATABASE_URL"]
    # Neon gives "postgresql://..."; SQLAlchemy needs to be told which driver.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
