import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.app import app
from app.crud.device_crud import create_device
from app.crud.player_crud import create_player
from app.db import get_session
from app.models.device import Device


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


class TestReadDevices:
	def test_read_receivers_displays_devices(self, client, session):
		"""Test that the index page displays all devices."""
		create_device(session, name="Encoder")
		create_device(session, name="Decoder")

		response = client.get(app.url_path_for("read_devices"))

		assert response.status_code == 200
		assert "Devices" in response.text
		assert "Reserved Receivers" not in response.text
		assert "Encoder" in response.text
		assert "Decoder" in response.text

	def test_read_devices_sorts_by_name(self, client, session):
		create_device(session, name="Zulu")
		create_device(session, name="Alpha")

		response = client.get("/devices?sort=name")
		assert response.status_code == 200
		alpha_index = response.text.find("Alpha")
		zulu_index = response.text.find("Zulu")
		assert alpha_index != -1
		assert zulu_index != -1
		assert alpha_index < zulu_index

	def test_read_devices_sorts_by_newest(self, client, session):
		create_device(session, name="Old")
		create_device(session, name="New")

		response = client.get("/devices?sort=newest")
		assert response.status_code == 200
		old_index = response.text.find("Old")
		new_index = response.text.find("New")
		assert old_index != -1
		assert new_index != -1
		assert new_index < old_index

	def test_read_devices_alias_route(self, client, session):
		"""Test that GET /devices returns the devices page (alias of /)."""
		create_device(session, name="Matrix")

		response = client.get("/devices")

		assert response.status_code == 200
		assert "Devices" in response.text
		assert "Reserved Receivers" not in response.text
		assert "Matrix" in response.text


class TestCreateDevice:
	def test_create_device_persists_and_returns_index(self, client):
		"""Test that creating a device persists it and returns updated index."""
		response = client.post(
			"/devices",
			data={
				"name": "Matrix",
			},
		)

		assert response.status_code == 200
		assert "Devices" in response.text
		assert "Reserved Receivers" not in response.text
		assert "Matrix" in response.text

	def test_create_device_duplicate_name_returns_error(self, client, session):
		"""Test that duplicate name returns conflict error."""
		create_device(session, name="Switch")

		response = client.post(
			"/devices",
			data={
				"name": "Switch",
			},
		)

		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == "#device-new"
		assert response.headers.get("HX-Reswap") == "outerHTML"
		assert "Switch" in response.text


class TestUpdateDevice:
	def test_update_device_assigns_player(self, client, session):
		player = create_player(session, name="Alice")
		device = create_device(session, name="Matrix")

		response = client.post(
			f"/devices/{device.id}/update",
			data={
				"name": "Matrix",
				"player_id": str(player.id),
			},
		)

		assert response.status_code == 200
		assert "Matrix" in response.text

		stored = session.get(Device, device.id)
		assert stored is not None
		assert stored.player_id == player.id

	def test_update_device_clears_player(self, client, session):
		player = create_player(session, name="Bob")
		device = create_device(session, name="Encoder", player_id=player.id)

		response = client.post(
			f"/devices/{device.id}/update",
			data={
				"name": "Encoder",
				"player_id": "",
			},
		)

		assert response.status_code == 200
		assert "Encoder" in response.text

		stored = session.get(Device, device.id)
		assert stored is not None
		assert stored.player_id is None

	def test_update_device_persists_and_returns_index(self, client, session):
		"""Test that updating a device persists changes and returns updated index."""
		device = create_device(session, name="OldName")

		response = client.post(
			f"/devices/{device.id}/update",
			data={
				"name": "NewName",
			},
		)

		assert response.status_code == 200
		assert "Devices" in response.text
		assert "Reserved Receivers" not in response.text
		assert "NewName" in response.text

	def test_update_device_duplicate_name_returns_error(self, client, session):
		"""Test that changing to duplicate name returns conflict error."""
		first = create_device(session, name="Primary")
		second = create_device(session, name="Secondary")

		response = client.post(
			f"/devices/{second.id}/update",
			data={
				"name": first.name,
			},
		)

		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == f"#device-{second.id}"
		assert response.headers.get("HX-Reswap") == "outerHTML"


class TestDeleteDevice:
	def test_delete_device_removes_and_redirects(self, client, session):
		"""Test that deleting a device removes it and redirects to index."""
		device = create_device(session, name="Temp")

		response = client.post(
			f"/devices/{device.id}/delete",
			follow_redirects=False,
		)

		assert response.status_code == 303
		assert response.headers["location"] == "http://testserver/devices/"

	def test_delete_device_removes_from_database(self, client, session):
		"""Test that deleted device is actually removed from database."""
		device = create_device(session, name="Cleanup")
		device_id = device.id

		client.post(f"/devices/{device_id}/delete")

		deleted_device = session.get(Device, device_id)
		assert deleted_device is None
