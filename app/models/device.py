from typing import TYPE_CHECKING, List, Optional

from pydantic import ConfigDict
from sqlmodel import Field, Relationship, SQLModel

from app.models.player import Player  # noqa: F401

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.receiver import Receiver


class Device(SQLModel, table=True):
    model_config = ConfigDict(validate_assignment=True)
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False, unique=True)
    player_id: Optional[int] = Field(default=None, foreign_key="player.id")

    player: Optional["Player"] = Relationship(back_populates="devices")
    receivers: List["Receiver"] = Relationship(back_populates="device")
