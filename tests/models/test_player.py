import pytest
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.models.device import Device
from app.models.player import Player


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


def test_player_defaults():
	player = Player(name="Alice")

	assert player.id is None
	assert player.name == "Alice"
	assert player.devices == []


def test_player_persistence(session):
	player = Player(name="Bob")
	session.add(player)
	session.commit()
	session.refresh(player)

	stored = session.get(Player, player.id)
	assert player.id is not None
	assert stored is not None
	assert stored.name == "Bob"


def test_player_indexes_exist(in_memory_engine):
	inspector = inspect(in_memory_engine)
	index_columns = {tuple(index["column_names"]) for index in inspector.get_indexes("player")}

	assert ("name",) in index_columns


def test_player_has_many_devices(session):
	player = Player(name="Carol")
	device1 = Device(name="Device-1", player=player)
	device2 = Device(name="Device-2", player=player)

	session.add_all([player, device1, device2])
	session.commit()

	fetched = session.get(Player, player.id)
	assert fetched is not None
	assert {device.name for device in fetched.devices} == {"Device-1", "Device-2"}
	assert all(device.player_id == fetched.id for device in fetched.devices)
