from collections.abc import Sequence
from typing import Literal

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.models.device import Device
from app.models.sort import DeviceSort
from app.models.form_error import FormError
from app.utils.exceptions import DeviceConflictError, DeviceValidationError
from app.utils.formatting import format_validation_errors


def _validate_player_id(session: Session, player_id: int | None) -> None:
	if player_id is None:
		return

	# Avoid circular import at module import time.
	from app.crud import player_crud

	if player_crud.get_player(session, player_id) is None:
		raise DeviceValidationError({"player_id": "Selected player does not exist."})


def _collect_conflict_messages(
	session: Session,
	*,
	name: str | None,
	exclude_id: int | None = None,
) -> FormError:
	messages: FormError = {}

	with session.no_autoflush:
		if name is not None:
			statement = select(Device).where(Device.name == name)
			if exclude_id is not None:
				statement = statement.where(Device.id != exclude_id)
			if session.exec(statement).first() is not None:
				messages["name"] = f"Name '{name}' is already in use."

	return messages


def create_device(
	session: Session,
	*,
	name: str,
	player_id: int | None = None,
) -> Device:
	_validate_player_id(session, player_id)
	try:
		device = Device(name=name, player_id=player_id)
	except ValidationError as exc:
		raise DeviceValidationError(format_validation_errors(exc)) from exc

	session.add(device)
	try:
		session.commit()
	except IntegrityError as exc:
		session.rollback()
		conflicts = _collect_conflict_messages(session, name=device.name)
		raise DeviceConflictError(conflicts if any(conflicts.values()) else None) from exc

	session.refresh(device)
	return device


def get_device(session: Session, device_id: int) -> Device | None:
	return session.get(Device, device_id)


def list_devices(
	session: Session,
	*,
	skip: int = 0,
	limit: int = 100,
	sort: Literal["newest", "name"] | DeviceSort = "newest",
) -> Sequence[Device]:
	statement = select(Device).options(selectinload(Device.player))
	resolved_sort = sort.value if isinstance(sort, DeviceSort) else sort
	if resolved_sort == "name":
		statement = statement.order_by(Device.name.asc(), Device.id.desc())
	else:
		statement = statement.order_by(Device.id.desc())
	return session.exec(statement.offset(skip).limit(limit)).all()


def update_device(
	session: Session,
	device_id: int,
	*,
	name: str | None = None,
	player_id: int | None = None,
) -> Device | None:
	device = session.get(Device, device_id)
	if device is None:
		return None

	_validate_player_id(session, player_id)

	try:
		if name is not None:
			device.name = name
		device.player_id = player_id
	except ValidationError as exc:
		raise DeviceValidationError(format_validation_errors(exc)) from exc

	session.add(device)
	try:
		session.commit()
	except IntegrityError as exc:
		session.rollback()
		conflicts = _collect_conflict_messages(session, name=device.name, exclude_id=device.id)
		raise DeviceConflictError(conflicts if any(conflicts.values()) else None) from exc

	session.refresh(device)
	return device


def delete_device(session: Session, device_id: int) -> bool:
	device = session.get(Device, device_id)
	if device is None:
		return False

	session.delete(device)
	session.commit()
	return True
