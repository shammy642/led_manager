import pytest
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.models.device import Device


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


def test_device_defaults():
	device = Device(name="Main Server")

	assert device.id is None
	assert device.name == "Main Server"
	assert device.player_id is None


def test_device_persistence(session):
	device = Device(name="Backup Device")

	session.add(device)
	session.commit()
	session.refresh(device)

	stored = session.get(Device, device.id)
	assert device.id is not None
	assert stored is not None
	assert stored.name == "Backup Device"


def test_device_indexes_exist(in_memory_engine):
	inspector = inspect(in_memory_engine)
	index_columns = {tuple(index["column_names"]) for index in inspector.get_indexes("device")}

	assert ("name",) in index_columns


def test_device_unique_name(session):
	device1 = Device(name="Production")
	session.add(device1)
	session.commit()

	device2 = Device(name="Production")
	session.add(device2)
	
	with pytest.raises(Exception):  # IntegrityError
		session.commit()
