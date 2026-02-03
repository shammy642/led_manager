from collections.abc import Sequence

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.crud import device_crud
from app.models.device import Device
from app.models.form_error import FormError
from app.models.player import Player
from app.utils.exceptions import PlayerConflictError, PlayerValidationError
from app.utils.formatting import format_validation_errors


def _collect_conflict_messages(
	session: Session,
	*,
	name: str | None,
	exclude_id: int | None = None,
) -> FormError:
	messages: FormError = {}

	with session.no_autoflush:
		if name is not None:
			statement = select(Player).where(Player.name == name)
			if exclude_id is not None:
				statement = statement.where(Player.id != exclude_id)
			if session.exec(statement).first() is not None:
				messages["name"] = f"Name '{name}' is already in use."

	return messages


def create_player(
	session: Session,
	*,
	name: str,
) -> Player:
	try:
		player = Player(name=name)
	except ValidationError as exc:
		raise PlayerValidationError(format_validation_errors(exc)) from exc

	session.add(player)
	try:
		session.commit()
	except IntegrityError as exc:
		session.rollback()
		conflicts = _collect_conflict_messages(session, name=player.name)
		raise PlayerConflictError(conflicts if any(conflicts.values()) else None) from exc

	session.refresh(player)
	return player


def get_player(session: Session, player_id: int) -> Player | None:
	return session.get(Player, player_id)


def get_player_with_devices_and_receivers(session: Session, player_id: int) -> Player | None:
	statement = (
		select(Player)
		.where(Player.id == player_id)
		.options(selectinload(Player.devices).selectinload(Device.receivers))
	)
	return session.exec(statement).first()


def list_players(
	session: Session,
	*,
	skip: int = 0,
	limit: int = 100,
) -> Sequence[Player]:
	return session.exec(select(Player).order_by(Player.id.desc()).offset(skip).limit(limit)).all()


def list_players_with_devices_and_receivers(
	session: Session,
	*,
	skip: int = 0,
	limit: int = 100,
) -> Sequence[Player]:
	statement = (
		select(Player)
		.options(selectinload(Player.devices).selectinload(Device.receivers))
		.order_by(Player.id.desc())
		.offset(skip)
		.limit(limit)
	)
	return session.exec(statement).all()


def update_player(
	session: Session,
	player_id: int,
	*,
	name: str | None = None,
) -> Player | None:
	player = session.get(Player, player_id)
	if player is None:
		return None

	try:
		if name is not None:
			player.name = name
	except ValidationError as exc:
		raise PlayerValidationError(format_validation_errors(exc)) from exc

	session.add(player)
	try:
		session.commit()
	except IntegrityError as exc:
		session.rollback()
		conflicts = _collect_conflict_messages(session, name=player.name, exclude_id=player.id)
		raise PlayerConflictError(conflicts if any(conflicts.values()) else None) from exc

	session.refresh(player)
	return player


def delete_player(session: Session, player_id: int) -> bool:
	player = session.get(Player, player_id)
	if player is None:
		return False

	devices = session.exec(select(Device).where(Device.player_id == player_id)).all()
	for device in devices:
		device.player_id = None
		session.add(device)

	session.delete(player)
	session.commit()
	return True


def add_device_to_player(session: Session, player_id: int, device_id: int) -> Device:
	player = session.get(Player, player_id)
	if player is None:
		raise PlayerValidationError({"player_id": "Selected player does not exist."})

	device = device_crud.get_device(session, device_id)
	if device is None:
		raise PlayerValidationError({"device_id": "Selected device does not exist."})

	if device.player_id is not None and device.player_id != player_id:
		raise PlayerValidationError({
			"device_id": "Selected device is already assigned to another player.",
		})

	device.player_id = player_id
	session.add(device)
	session.commit()
	session.refresh(device)
	return device


def remove_device_from_player(session: Session, player_id: int, device_id: int) -> Device:
	player = session.get(Player, player_id)
	if player is None:
		raise PlayerValidationError({"player_id": "Selected player does not exist."})

	device = device_crud.get_device(session, device_id)
	if device is None:
		raise PlayerValidationError({"device_id": "Selected device does not exist."})

	if device.player_id != player_id:
		raise PlayerValidationError({"device_id": "Selected device is not assigned to this player."})

	device.player_id = None
	session.add(device)
	session.commit()
	session.refresh(device)
	return device
