import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.models.receiver import Receiver


@pytest.fixture
def in_memory_engine():
	"""Provide an in-memory SQLite engine that shares a single connection."""
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
	"""Yield a session bound to the shared in-memory engine."""
	with Session(in_memory_engine) as session:
		yield session


def test_receiver_defaults():
	receiver = Receiver(
		name="Office Router",
		ip_address="192.168.0.1",
		mac_address="AA:BB:CC:DD:EE:FF",
	)

	assert receiver.id is None
	assert receiver.name == "Office Router"
	assert receiver.ip_address == "192.168.0.1"
	assert receiver.mac_address == "AA:BB:CC:DD:EE:FF"


def test_receiver_persistence(session):
	receiver = Receiver(
		name="Lobby Printer",
		ip_address="10.0.0.42",
		mac_address="11:22:33:44:55:66",
	)

	session.add(receiver)
	session.commit()
	session.refresh(receiver)

	stored = session.get(Receiver, receiver.id)
	assert receiver.id is not None
	assert stored is not None
	assert stored.name == "Lobby Printer"
	assert stored.ip_address == "10.0.0.42"
	assert stored.mac_address == "11:22:33:44:55:66"


def test_receiver_indexes_exist(in_memory_engine):
	inspector = inspect(in_memory_engine)
	index_columns = {tuple(index["column_names"]) for index in inspector.get_indexes("receiver")}

	assert ("name",) in index_columns
	assert ("ip_address",) in index_columns
	assert ("mac_address",) in index_columns


def test_receiver_rejects_invalid_ip_address():
	with pytest.raises(ValidationError):
		Receiver.model_validate(
			{
				"name": "Invalid Device",
				"ip_address": "not-an-ip12312321",
				"mac_address": "AA:BB:CC:DD:EE:FF",
			}
		)


def test_receiver_rejects_invalid_mac_address():
	with pytest.raises(ValidationError):
		Receiver.model_validate(
			{
				"name": "Invalid MAC",
				"ip_address": "10.0.0.1",
				"mac_address": "ZZ:ZZ:ZZ:ZZ:ZZ:ZZ",
			}
		)


def test_receiver_normalizes_mac_address():
	receiver = Receiver.model_validate(
		{
			"name": "Normalized",
			"ip_address": "10.0.0.2",
			"mac_address": "aa-bb-cc-dd-ee-ff",
		}
	)
	assert receiver.mac_address == "AA:BB:CC:DD:EE:FF"
