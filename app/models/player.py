from typing import TYPE_CHECKING, List

from pydantic import ConfigDict
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
	from app.models.device import Device


class Player(SQLModel, table=True):
	model_config = ConfigDict(validate_assignment=True)
	id: int | None = Field(default=None, primary_key=True)
	name: str = Field(index=True, nullable=False, unique=True)

	devices: List["Device"] = Relationship(back_populates="player")
