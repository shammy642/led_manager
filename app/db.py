from collections.abc import Iterator
from sqlmodel import Session, SQLModel, create_engine

# Import all models so SQLModel knows about them for table creation
from app.models.device import Device  # noqa: F401
from app.models.player import Player  # noqa: F401
from app.models.receiver import Receiver  # noqa: F401

sqlite_name = "ip_address_manager"
sqlite_url = f"postgresql+psycopg://127.0.0.1:5432/{sqlite_name}"

engine = create_engine(sqlite_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """Yield a SQLModel session for request-scoped database work."""
    with Session(engine) as session:
        yield session
