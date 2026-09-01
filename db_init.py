"""Initialize the PostgreSQL schema without creating demo accounts."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from database import init_db


if __name__ == "__main__":
    init_db()
    print("NIRIKSHA PostgreSQL schema initialized.")
