from ipaddress import ip_address
from typing import TYPE_CHECKING, Optional

from pydantic import ConfigDict, field_validator
from sqlmodel import Field, Relationship, SQLModel

from app.models.device import Device  # noqa: F401

if TYPE_CHECKING:
    from app.models.device import Device


_HEX_CHARS = "0123456789abcdefABCDEF"


class Receiver(SQLModel, table=True):
    model_config = ConfigDict(validate_assignment=True)
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False, unique=True)
    ip_address: str = Field(index=True, nullable=False, unique=True)
    mac_address: str = Field(index=True, nullable=False, unique=True)
    device_id: int | None = Field(default=None, foreign_key="device.id")
    device: Optional["Device"] = Relationship(back_populates="receivers")

    @field_validator("ip_address", mode="before")
    @classmethod
    def _validate_ip_address(cls, value: str) -> str:
        return str(ip_address(value))

    @field_validator("mac_address", mode="before")
    @classmethod
    def _validate_mac_address(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("MAC address must be a string.")

        compact = value.strip().replace(":", "").replace("-", "")

        if len(compact) != 12 or any(char not in _HEX_CHARS for char in compact):
            raise ValueError("Invalid MAC address format.")

        compact = compact.upper()
        return ":".join(compact[i : i + 2] for i in range(0, 12, 2))
    
    
