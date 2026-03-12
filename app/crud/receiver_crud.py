from collections.abc import Sequence
from typing import Literal

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.crud import device_crud
from app.models.device import Device
from app.models.form_error import FormError
from app.models.receiver import Receiver
from app.models.sort import ReceiverSort
from app.utils.exceptions import ReceiverConflictError, ReceiverValidationError
from app.utils.formatting import format_validation_errors


def _validate_device_id(session: Session, device_id: int | None) -> None:
	if device_id is None:
		return
	if device_crud.get_device(session, device_id) is None:
		raise ReceiverValidationError({"device_id": "Selected device does not exist."})


def _collect_conflict_messages(
	session: Session,
	*,
	name: str | None,
	ip_address: str | None,
	mac_address: str | None,
	exclude_id: int | None = None,
) -> FormError:
	messages = {}

	with session.no_autoflush:
		def _check(column, value, label: str, key: str) -> None:
			if value is None:
				return
			statement = select(Receiver).where(column == value)
			if exclude_id is not None:
				statement = statement.where(Receiver.id != exclude_id)
			if session.exec(statement).first() is not None:
				messages[key] = f"{label} '{value}' is already in use."

		_check(Receiver.name, name, "Name", "name")
		_check(Receiver.ip_address, ip_address, "IP address", "ip_address")
		_check(Receiver.mac_address, mac_address, "MAC address", "mac_address")
	return messages


def create_receiver(
	session: Session,
	*,
	name: str,
	ip_address: str,
	mac_address: str,
	device_id: int | None = None,
) -> Receiver:
	_validate_device_id(session, device_id)
	try:
		receiver = Receiver(
			name=name,
			ip_address=ip_address,
			mac_address=mac_address,
			device_id=device_id,
		)
	except ValidationError as exc:
		raise ReceiverValidationError(format_validation_errors(exc)) from exc
	
	session.add(receiver)
	try:
		session.commit()
	except IntegrityError as exc:
		session.rollback()
		conflicts = _collect_conflict_messages(
			session,
			name=receiver.name,
			ip_address=receiver.ip_address,
			mac_address=receiver.mac_address,
		)
		raise ReceiverConflictError(conflicts if any(conflicts.values()) else None) from exc

	session.refresh(receiver)
	return receiver


def get_receiver(session: Session, receiver_id: int) -> Receiver | None:
	return session.get(Receiver, receiver_id)


def list_receivers(
	session: Session,
	*,
	skip: int = 0,
	limit: int = 100,
	sort: Literal["newest", "name", "device", "ip"] | ReceiverSort = "newest",
) -> Sequence[Receiver]:
	statement = select(Receiver)
	resolved_sort = sort.value if isinstance(sort, ReceiverSort) else sort
	
	if resolved_sort == "ip":
		# IP sorting is best done in Python because SQLite has no native network address type
		results = session.exec(statement).all()
		import ipaddress
		results.sort(key=lambda r: (ipaddress.ip_address(r.ip_address), -r.id if r.id is not None else 0))
		return results[skip : skip + limit]

	if resolved_sort == "name":
		statement = statement.order_by(Receiver.name.asc(), Receiver.id.desc())
	elif resolved_sort == "device":
		statement = (
			statement.outerjoin(Device, Receiver.device_id == Device.id)
			.order_by(Device.name.is_(None), Device.name.asc(), Receiver.id.desc())
		)
	else:
		statement = statement.order_by(Receiver.id.desc())
	return session.exec(statement.offset(skip).limit(limit)).all()


def update_receiver(
	session: Session,
	receiver_id: int,
	*,
	name: str | None = None,
	ip_address: str | None = None,
	mac_address: str | None = None,
	device_id: int | None = None,
) -> Receiver | None:
	receiver = session.get(Receiver, receiver_id)
	if receiver is None:
		return None

	_validate_device_id(session, device_id)

	try:
		if name is not None:
			receiver.name = name
		if ip_address is not None:
			receiver.ip_address = ip_address
		if mac_address is not None:
			receiver.mac_address = mac_address
		receiver.device_id = device_id
	except ValidationError as exc:
		raise ReceiverValidationError(format_validation_errors(exc)) from exc

	session.add(receiver)
	try:
		session.commit()
	except IntegrityError as exc:
		session.rollback()
		conflicts = _collect_conflict_messages(
			session,
			name=receiver.name,
			ip_address=receiver.ip_address,
			mac_address=receiver.mac_address,
			exclude_id=receiver.id,
		)
		raise ReceiverConflictError(conflicts if any(conflicts.values()) else None) from exc

	session.refresh(receiver)
	return receiver


def delete_receiver(session: Session, receiver_id: int) -> bool:
	receiver = session.get(Receiver, receiver_id)
	if receiver is None:
		return False

	session.delete(receiver)
	session.commit()
	return True
