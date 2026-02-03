import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.crud.device_crud import create_device
from app.crud.player_crud import (
	_collect_conflict_messages,
	add_device_to_player,
	create_player,
	delete_player,
	get_player,
	list_players,
	list_players_with_devices_and_receivers,
	remove_device_from_player,
	update_player,
)
from app.crud.receiver_crud import create_receiver
from app.models.device import Device  # noqa: F401
from app.models.player import Player
from app.models.receiver import Receiver  # noqa: F401
from app.utils.exceptions import PlayerConflictError, PlayerValidationError


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


def test_create_player_persists(session):
	player = create_player(session, name="Alice")

	assert player.id is not None
	stored = session.get(Player, player.id)
	assert stored is not None
	assert stored.name == "Alice"


def test_get_player_returns_instance(session):
	player = create_player(session, name="Bob")
	fetched = get_player(session, player.id)
	assert fetched is not None
	assert fetched.id == player.id


def test_get_player_missing_returns_none(session):
	assert get_player(session, 9999) is None


def test_list_players_supports_pagination(session):
	for index in range(3):
		create_player(session, name=f"Player-{index}")

	all_players = list_players(session)
	assert [player.name for player in all_players] == [
		"Player-2",
		"Player-1",
		"Player-0",
	]

	limited = list_players(session, skip=1, limit=1)
	assert len(limited) == 1
	assert limited[0].name == "Player-1"


def test_update_player_changes_fields(session):
	player = create_player(session, name="Old")

	updated = update_player(session, player.id, name="New")
	assert updated is not None
	assert updated.name == "New"

	stored = session.get(Player, player.id)
	assert stored is not None
	assert stored.name == "New"


def test_update_player_missing_returns_none(session):
	assert update_player(session, 9999, name="Ghost") is None


def test_delete_player_removes_instance(session):
	player = create_player(session, name="Temp")

	result = delete_player(session, player.id)
	assert result is True
	assert session.get(Player, player.id) is None


def test_delete_player_unassigns_devices(session):
	player = create_player(session, name="TempWithDevices")
	device = create_device(session, name="Attached", player_id=player.id)

	result = delete_player(session, player.id)
	assert result is True
	assert session.get(Player, player.id) is None

	stored_device = session.get(Device, device.id)
	assert stored_device is not None
	assert stored_device.player_id is None


def test_delete_player_missing_returns_false(session):
	assert delete_player(session, 9999) is False


def test_collect_conflict_messages_detects_existing_values(session):
	stored = create_player(session, name="Player")

	messages = _collect_conflict_messages(session, name=stored.name)
	assert messages == {"name": "Name 'Player' is already in use."}


def test_collect_conflict_messages_respects_exclude_id(session):
	stored = create_player(session, name="Primary")

	messages = _collect_conflict_messages(session, name=stored.name, exclude_id=stored.id)
	assert messages == {}


def test_create_player_duplicate_name_raises_conflict(session):
	create_player(session, name="Alice")

	with pytest.raises(PlayerConflictError) as exc_info:
		create_player(session, name="Alice")

	assert exc_info.value.messages == {"name": "Name 'Alice' is already in use."}


def test_add_device_to_player_assigns_player_id(session):
	player = create_player(session, name="Player")
	device = create_device(session, name="Device")

	updated_device = add_device_to_player(session, player.id, device.id)
	assert updated_device.player_id == player.id

	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.player_id == player.id


def test_add_device_to_player_missing_player_raises(session):
	device = create_device(session, name="Device")
	with pytest.raises(PlayerValidationError) as exc_info:
		add_device_to_player(session, 9999, device.id)
	assert exc_info.value.messages == {"player_id": "Selected player does not exist."}


def test_add_device_to_player_missing_device_raises(session):
	player = create_player(session, name="Player")
	with pytest.raises(PlayerValidationError) as exc_info:
		add_device_to_player(session, player.id, 9999)
	assert exc_info.value.messages == {"device_id": "Selected device does not exist."}


def test_add_device_to_player_already_assigned_to_other_player_raises(session):
	player_a = create_player(session, name="PlayerA")
	player_b = create_player(session, name="PlayerB")
	device = create_device(session, name="Device", player_id=player_b.id)

	with pytest.raises(PlayerValidationError) as exc_info:
		add_device_to_player(session, player_a.id, device.id)
	assert exc_info.value.messages == {
		"device_id": "Selected device is already assigned to another player.",
	}


def test_list_players_with_devices_and_receivers_includes_nested_relationships(session):
	player_with_device = create_player(session, name="WithDevice")
	player_without_device = create_player(session, name="WithoutDevice")

	device = create_device(session, name="Dev", player_id=player_with_device.id)
	create_receiver(
		session,
		name="Recv",
		ip_address="10.0.0.10",
		mac_address="AA:BB:CC:DD:EE:11",
		device_id=device.id,
	)
	create_device(session, name="UnassignedDevice", player_id=None)

	players = list_players_with_devices_and_receivers(session)
	assert [player.name for player in players] == ["WithoutDevice", "WithDevice"]

	with_device = next(player for player in players if player.name == "WithDevice")
	without_device = next(player for player in players if player.name == "WithoutDevice")

	assert len(with_device.devices) == 1
	assert with_device.devices[0].name == "Dev"
	assert [receiver.name for receiver in with_device.devices[0].receivers] == ["Recv"]

	assert without_device.devices == []


def test_remove_device_from_player_clears_player_id(session):
	player = create_player(session, name="Player")
	device = create_device(session, name="Device", player_id=player.id)

	updated_device = remove_device_from_player(session, player.id, device.id)
	assert updated_device.player_id is None

	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.player_id is None


def test_remove_device_from_player_not_assigned_raises(session):
	player_a = create_player(session, name="PlayerA")
	player_b = create_player(session, name="PlayerB")
	device = create_device(session, name="Device", player_id=player_b.id)

	with pytest.raises(PlayerValidationError) as exc_info:
		remove_device_from_player(session, player_a.id, device.id)
	assert exc_info.value.messages == {
		"device_id": "Selected device is not assigned to this player.",
	}
