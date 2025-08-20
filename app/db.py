from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
import os
import dotenv

dotenv.load_dotenv(override=True)

DATABASE_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_ENDPOINT')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

engine: Engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # number of connections to keep
    max_overflow=20,        # allow extra temporary connections
    pool_timeout=30,        # seconds to wait before giving up
    pool_recycle=1800       # recycle connections every 30 minutes
)

def get_connection():
    """Get a pooled DBAPI connection (psycopg2 under the hood)."""
    return engine.raw_connection()
