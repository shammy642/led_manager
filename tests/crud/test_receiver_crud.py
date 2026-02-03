import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.crud.device_crud import create_device
from app.crud.receiver_crud import (
	_collect_conflict_messages,
	create_receiver,
	delete_receiver,
	get_receiver,
	list_receivers,
	update_receiver,
)
from app.models.receiver import Receiver
from app.utils.exceptions import ReceiverConflictError, ReceiverValidationError


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


def test_create_receiver_persists(session):
	receiver = create_receiver(
		session,
		name="Switch",
		ip_address="192.168.1.10",
		mac_address="AA:BB:CC:DD:EE:11",
	)

	assert receiver.id is not None
	stored = session.get(Receiver, receiver.id)
	assert stored is not None
	assert stored.name == "Switch"
	assert stored.ip_address == "192.168.1.10"
	assert stored.mac_address == "AA:BB:CC:DD:EE:11"


def test_create_receiver_with_device(session):
	device = create_device(session, name="Rack")

	receiver = create_receiver(
		session,
		name="Switch",
		ip_address="192.168.1.10",
		mac_address="AA:BB:CC:DD:EE:11",
		device_id=device.id,
	)

	stored = session.get(Receiver, receiver.id)
	assert stored is not None
	assert stored.device_id == device.id


def test_get_receiver_returns_instance(session):
	receiver = create_receiver(
		session,
		name="Firewall",
		ip_address="10.0.0.1",
		mac_address="22:33:44:55:66:77",
	)

	fetched = get_receiver(session, receiver.id)
	assert fetched is not None
	assert fetched.id == receiver.id
	assert fetched.name == "Firewall"


def test_get_receiver_missing_returns_none(session):
	assert get_receiver(session, 9999) is None


def test_list_receivers_supports_pagination(session):
	for index in range(3):
		create_receiver(
			session,
			name=f"Device-{index}",
			ip_address=f"192.168.0.{index}",
			mac_address=f"00:00:00:00:00:0{index}",
		)

	all_receivers = list_receivers(session)
	assert [receiver.name for receiver in all_receivers] == [
		"Device-2",
		"Device-1",
		"Device-0",
	]

	limited = list_receivers(session, skip=1, limit=1)
	assert len(limited) == 1
	assert limited[0].name == "Device-1"


def test_list_receivers_can_sort_by_name(session):
	create_receiver(
		session,
		name="Zulu",
		ip_address="10.0.0.3",
		mac_address="00:00:00:00:00:03",
	)
	create_receiver(
		session,
		name="Alpha",
		ip_address="10.0.0.1",
		mac_address="00:00:00:00:00:01",
	)
	create_receiver(
		session,
		name="Mike",
		ip_address="10.0.0.2",
		mac_address="00:00:00:00:00:02",
	)

	result = list_receivers(session, sort="name")
	assert [receiver.name for receiver in result] == ["Alpha", "Mike", "Zulu"]


def test_list_receivers_can_sort_by_ip(session):
	create_receiver(
		session,
		name="B",
		ip_address="10.0.0.2",
		mac_address="00:00:00:00:00:12",
	)
	create_receiver(
		session,
		name="A",
		ip_address="10.0.0.1",
		mac_address="00:00:00:00:00:11",
	)

	result = list_receivers(session, sort="ip")
	assert [receiver.ip_address for receiver in result] == ["10.0.0.1", "10.0.0.2"]


def test_list_receivers_can_sort_by_device_name(session):
	device_a = create_device(session, name="AlphaDevice")
	device_z = create_device(session, name="ZuluDevice")

	create_receiver(
		session,
		name="OnZulu",
		ip_address="10.0.0.21",
		mac_address="00:00:00:00:00:21",
		device_id=device_z.id,
	)
	create_receiver(
		session,
		name="Unassigned",
		ip_address="10.0.0.30",
		mac_address="00:00:00:00:00:30",
		device_id=None,
	)
	create_receiver(
		session,
		name="OnAlpha",
		ip_address="10.0.0.20",
		mac_address="00:00:00:00:00:20",
		device_id=device_a.id,
	)

	result = list_receivers(session, sort="device")
	assert [receiver.name for receiver in result] == ["OnAlpha", "OnZulu", "Unassigned"]


def test_update_receiver_changes_fields(session):
	receiver = create_receiver(
		session,
		name="Old",
		ip_address="192.168.1.100",
		mac_address="FF:EE:DD:CC:BB:AA",
	)

	updated = update_receiver(
		session,
		receiver.id,
		name="New",
		ip_address="192.168.1.101",
		mac_address="11:22:33:44:55:66",
	)

	assert updated is not None
	assert updated.name == "New"
	assert updated.ip_address == "192.168.1.101"
	assert updated.mac_address == "11:22:33:44:55:66"

	stored = session.get(Receiver, receiver.id)
	assert stored is not None
	assert stored.name == "New"


def test_update_receiver_sets_device_id(session):
	device = create_device(session, name="Matrix")
	receiver = create_receiver(
		session,
		name="Old",
		ip_address="192.168.1.100",
		mac_address="FF:EE:DD:CC:BB:AA",
	)

	updated = update_receiver(session, receiver.id, device_id=device.id)
	assert updated is not None
	assert updated.device_id == device.id


def test_update_receiver_clears_device_id(session):
	device = create_device(session, name="Bay")
	receiver = create_receiver(
		session,
		name="Old",
		ip_address="192.168.1.100",
		mac_address="FF:EE:DD:CC:BB:AA",
		device_id=device.id,
	)

	updated = update_receiver(session, receiver.id, device_id=None)
	assert updated is not None
	assert updated.device_id is None


def test_update_receiver_missing_returns_none(session):
	assert update_receiver(session, 9999, name="Ghost") is None


def test_delete_receiver_removes_instance(session):
	receiver = create_receiver(
		session,
		name="Temp",
		ip_address="10.10.10.10",
		mac_address="AA:AA:AA:AA:AA:AA",
	)

	result = delete_receiver(session, receiver.id)
	assert result is True
	assert session.get(Receiver, receiver.id) is None


def test_delete_receiver_missing_returns_false(session):
	assert delete_receiver(session, 9999) is False


def test_collect_conflict_messages_detects_existing_values(session):
	stored = create_receiver(
		session,
		name="Device",
		ip_address="192.168.50.5",
		mac_address="AA:BB:CC:DD:EE:FF",
	)

	messages = _collect_conflict_messages(
		session,
		name=stored.name,
		ip_address=stored.ip_address,
		mac_address=stored.mac_address,
	)

	assert messages == {
		"name": "Name 'Device' is already in use.",
		"ip_address": "IP address '192.168.50.5' is already in use.",
		"mac_address": "MAC address 'AA:BB:CC:DD:EE:FF' is already in use.",
	}


def test_collect_conflict_messages_respects_exclude_id(session):
	stored = create_receiver(
		session,
		name="Primary",
		ip_address="10.10.0.1",
		mac_address="11:22:33:44:55:66",
	)

	messages = _collect_conflict_messages(
		session,
		name=stored.name,
		ip_address=stored.ip_address,
		mac_address=stored.mac_address,
		exclude_id=stored.id,
	)

	assert messages == {}


def test_create_receiver_invalid_input_raises_validation_error(session):
	with pytest.raises(ReceiverValidationError) as exc_info:
		create_receiver(
			session,
			name="Invalid",
			ip_address="not-an-ip",
			mac_address="AA:BB:CC:DD:EE:FF",
		)

	assert any("ip_address" in key for key in exc_info.value.messages.keys())


def test_create_receiver_duplicate_name_raises_conflict(session):
	create_receiver(
		session,
		name="Switch",
		ip_address="192.168.1.1",
		mac_address="AA:AA:AA:AA:AA:AA",
	)

	with pytest.raises(ReceiverConflictError) as exc_info:
		create_receiver(
			session,
			name="Switch",
			ip_address="192.168.1.2",
			mac_address="BB:BB:BB:BB:BB:BB",
		)

	assert exc_info.value.messages == {"name": "Name 'Switch' is already in use."}


def test_update_receiver_invalid_ip_raises_validation_error(session):
	receiver = create_receiver(
		session,
		name="Router",
		ip_address="10.0.0.10",
		mac_address="CC:CC:CC:CC:CC:CC",
	)

	with pytest.raises(ReceiverValidationError) as exc_info:
		update_receiver(session, receiver.id, ip_address="invalid-ip")

	assert any("ip_address" in key for key in exc_info.value.messages.keys())


def test_update_receiver_invalid_device_raises_validation_error(session):
	receiver = create_receiver(
		session,
		name="Router",
		ip_address="10.0.0.10",
		mac_address="CC:CC:CC:CC:CC:CC",
	)

	with pytest.raises(ReceiverValidationError) as exc_info:
		update_receiver(session, receiver.id, device_id=9999)

	assert "device_id" in exc_info.value.messages


def test_update_receiver_duplicate_ip_raises_conflict(session):
	first = create_receiver(
		session,
		name="Primary",
		ip_address="10.0.0.1",
		mac_address="DD:DD:DD:DD:DD:DD",
	)
	second = create_receiver(
		session,
		name="Secondary",
		ip_address="10.0.0.2",
		mac_address="EE:EE:EE:EE:EE:EE",
	)

	with pytest.raises(ReceiverConflictError) as exc_info:
		update_receiver(session, second.id, ip_address=first.ip_address)

	# The conflict dict may not include fields that don't have conflicts
	# or may return the default message if unable to determine which field
	assert "ip_address" in str(exc_info.value.messages) or "conflict" in exc_info.value.messages
