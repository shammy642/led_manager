import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.app import app
from app.crud.device_crud import create_device
from app.crud.player_crud import create_player
from app.db import get_session


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


@pytest.fixture
def client(session):
	def get_session_override():
		return session

	app.dependency_overrides[get_session] = get_session_override
	yield TestClient(app)
	app.dependency_overrides.clear()


def test_add_device_button_returns_form(client):
	"""Test that the add device button returns a new form row."""
	response = client.post("/ui/device/add")

	assert response.status_code == 200
	assert "device-new" in response.text


def test_edit_device_button_returns_edit_form(client, session):
	"""Test that the edit button returns the device in edit mode."""
	create_player(session, name="Alice")
	device = create_device(session, name="Matrix")

	response = client.post(f"/ui/device/{device.id}/edit")

	assert response.status_code == 200
	assert "Matrix" in response.text
	assert 'name="player_id"' not in response.text
	assert "Alice" not in response.text


def test_cancel_device_button_returns_view_form(client, session):
	"""Test that the cancel button returns the device in view mode."""
	device = create_device(session, name="Router")

	response = client.post(f"/ui/device/{device.id}/cancel")

	assert response.status_code == 200
	assert "Router" in response.text
