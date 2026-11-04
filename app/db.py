import os

import dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


dotenv.load_dotenv(override=True)

DATABASE_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_ENDPOINT')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def create_db_engine() -> Engine:
    """Create the pooled engine with bounded connection/query timeouts."""
    return create_engine(
        DATABASE_URL,
        pool_size=10,  # number of connections to keep
        max_overflow=20,  # allow extra temporary connections
        pool_timeout=30,  # seconds to wait before giving up
        pool_recycle=1800,  # recycle connections every 30 minutes
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
            "options": f"-c statement_timeout={int(os.getenv('DB_STATEMENT_TIMEOUT_MS', '30000'))}",
        },
    )


engine = create_db_engine()


def get_connection():
    """Get a pooled DBAPI connection (psycopg2 under the hood)."""
    return engine.raw_connection()
