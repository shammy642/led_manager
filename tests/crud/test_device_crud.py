import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.crud.device_crud import (
	_collect_conflict_messages,
	create_device,
	delete_device,
	get_device,
	list_devices,
	update_device,
)
from app.crud.player_crud import create_player
from app.models.device import Device
from app.utils.exceptions import DeviceConflictError
from app.utils.exceptions import DeviceValidationError


@pytest.fixture
def in_memory_engine():
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	SQLModel.metadata.create_all(engine)
	try:
		yield engine
	finally:
		SQLModel.metadata.drop_all(engine)


@pytest.fixture
def session(in_memory_engine):
	with Session(in_memory_engine) as session:
		yield session


def test_create_device_persists(session):
	device = create_device(session, name="Switch")

	assert device.id is not None
	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.name == "Switch"


def test_get_device_returns_instance(session):
	device = create_device(session, name="Firewall")
	fetched = get_device(session, device.id)
	assert fetched is not None
	assert fetched.id == device.id


def test_get_device_missing_returns_none(session):
	assert get_device(session, 9999) is None


def test_list_devices_supports_pagination(session):
	for index in range(3):
		create_device(session, name=f"Device-{index}")

	all_devices = list_devices(session)
	assert [device.name for device in all_devices] == [
		"Device-2",
		"Device-1",
		"Device-0",
	]

	limited = list_devices(session, skip=1, limit=1)
	assert len(limited) == 1
	assert limited[0].name == "Device-1"


def test_list_devices_can_sort_by_name(session):
	create_device(session, name="Zulu")
	create_device(session, name="Alpha")
	create_device(session, name="Mike")

	result = list_devices(session, sort="name")
	assert [device.name for device in result] == ["Alpha", "Mike", "Zulu"]


def test_update_device_changes_fields(session):
	device = create_device(session, name="Old")

	updated = update_device(session, device.id, name="New")
	assert updated is not None
	assert updated.name == "New"

	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.name == "New"


def test_update_device_sets_player_id(session):
	player = create_player(session, name="Alice")
	device = create_device(session, name="Matrix")

	updated = update_device(session, device.id, player_id=player.id)
	assert updated is not None
	assert updated.player_id == player.id

	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.player_id == player.id


def test_update_device_clears_player_id(session):
	player = create_player(session, name="Bob")
	device = create_device(session, name="Encoder", player_id=player.id)

	updated = update_device(session, device.id, player_id=None)
	assert updated is not None
	assert updated.player_id is None

	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.player_id is None


def test_update_device_invalid_player_raises_validation_error(session):
	device = create_device(session, name="Decoder")

	with pytest.raises(DeviceValidationError) as exc_info:
		update_device(session, device.id, player_id=9999)

	assert "player_id" in exc_info.value.messages


def test_update_device_missing_returns_none(session):
	assert update_device(session, 9999, name="Ghost") is None


def test_delete_device_removes_instance(session):
	device = create_device(session, name="Temp")

	result = delete_device(session, device.id)
	assert result is True
	assert session.get(Device, device.id) is None


def test_delete_device_missing_returns_false(session):
	assert delete_device(session, 9999) is False


def test_collect_conflict_messages_detects_existing_values(session):	
	stored = create_device(session, name="Device")

	messages = _collect_conflict_messages(session, name=stored.name)
	assert messages == {"name": "Name 'Device' is already in use."}


def test_collect_conflict_messages_respects_exclude_id(session):
	stored = create_device(session, name="Primary")

	messages = _collect_conflict_messages(session, name=stored.name, exclude_id=stored.id)
	assert messages == {}


def test_create_device_duplicate_name_raises_conflict(session):
	create_device(session, name="Switch")

	with pytest.raises(DeviceConflictError) as exc_info:
		create_device(session, name="Switch")

	assert exc_info.value.messages == {"name": "Name 'Switch' is already in use."}
