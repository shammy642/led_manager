from collections.abc import Iterator
from sqlmodel import Session, SQLModel, create_engine

# Import all models so SQLModel knows about them for table creation
from app.models.device import Device  # noqa: F401
from app.models.player import Player  # noqa: F401
from app.models.receiver import Receiver  # noqa: F401
from dotenv import load_dotenv
import os

load_dotenv()

db_location = os.getenv("DB_LOCATION", "./ip_manager.db")
sqlite_url = f"sqlite:///{db_location}"

engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """Yield a SQLModel session for request-scoped database work."""
    with Session(engine) as session:
        yield session
