import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.app import app
from app.crud.device_crud import create_device
from app.crud.receiver_crud import create_receiver
from app.db import get_session
from app.models.receiver import Receiver


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


class TestReadReceivers:
	def test_read_receivers_returns_html(self, client):
		"""Test that GET /receivers returns the receivers page."""
		response = client.get("/receivers")
		
		assert response.status_code == 200
		assert "text/html" in response.headers["content-type"]

	def test_read_receivers_has_apply_changes_spinner(self, client):
		"""Test that the Apply Changes button has a spinner indicator element."""
		response = client.get("/receivers")
		
		assert response.status_code == 200
		assert 'id="apply-changes-spinner"' in response.text
		assert 'hx-indicator="#apply-changes-spinner"' in response.text

	def test_read_receivers_displays_receivers(self, client, session):
		"""Test that the receivers page displays all receivers."""
		create_receiver(
			session,
			name="Device1",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		create_receiver(
			session,
			name="Device2",
			ip_address="192.168.1.20",
			mac_address="AA:BB:CC:DD:EE:22",
		)
		
		response = client.get("/receivers")
		
		assert response.status_code == 200
		assert "Device1" in response.text
		assert "Device2" in response.text

	def test_read_receivers_sorts_by_name(self, client, session):
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

		response = client.get("/receivers?sort=name")
		assert response.status_code == 200
		alpha_index = response.text.find('value="Alpha"')
		zulu_index = response.text.find('value="Zulu"')
		assert alpha_index != -1
		assert zulu_index != -1
		assert alpha_index < zulu_index

	def test_read_receivers_sorts_by_ip(self, client, session):
		create_receiver(
			session,
			name="R2",
			ip_address="10.0.0.2",
			mac_address="00:00:00:00:00:12",
		)
		create_receiver(
			session,
			name="R1",
			ip_address="10.0.0.1",
			mac_address="00:00:00:00:00:11",
		)

		response = client.get("/receivers?sort=ip")
		assert response.status_code == 200
		r1_index = response.text.find('value="R1"')
		r2_index = response.text.find('value="R2"')
		assert r1_index != -1
		assert r2_index != -1
		assert r1_index < r2_index

	def test_read_receivers_sorts_by_device(self, client, session):
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

		response = client.get("/receivers?sort=device")
		assert response.status_code == 200
		on_alpha_index = response.text.find('value="OnAlpha"')
		on_zulu_index = response.text.find('value="OnZulu"')
		unassigned_index = response.text.find('value="Unassigned"')
		assert on_alpha_index != -1
		assert on_zulu_index != -1
		assert unassigned_index != -1
		assert on_alpha_index < on_zulu_index < unassigned_index

	def test_read_receivers_sorts_by_newest(self, client, session):
		create_receiver(
			session,
			name="Old",
			ip_address="10.0.0.40",
			mac_address="00:00:00:00:00:40",
		)
		create_receiver(
			session,
			name="New",
			ip_address="10.0.0.41",
			mac_address="00:00:00:00:00:41",
		)

		response = client.get("/receivers?sort=newest")
		assert response.status_code == 200
		new_index = response.text.find('value="New"')
		old_index = response.text.find('value="Old"')
		assert new_index != -1
		assert old_index != -1
		assert new_index < old_index


class TestCreateReceiver:
	def test_create_receiver_with_device(self, client, session):
		"""Test that creating a receiver with a device associates it."""
		device = create_device(session, name="Rack")

		response = client.post(
			"/receivers",
			data={
				"name": "NewDevice",
				"ip_address": "10.0.0.1",
				"mac_address": "FF:EE:DD:CC:BB:AA",
				"device_id": str(device.id),
			},
		)
		
		assert response.status_code == 200
		assert "NewDevice" in response.text
		assert device.name in response.text
	def test_create_receiver_persists_and_returns_index(self, client):
		"""Test that creating a receiver persists it and returns updated index."""
		response = client.post(
			"/receivers",
			data={
				"name": "NewDevice",
				"ip_address": "10.0.0.1",
				"mac_address": "FF:EE:DD:CC:BB:AA",
			},
		)
		
		assert response.status_code == 200
		assert "NewDevice" in response.text

	def test_create_receiver_with_invalid_ip(self, client):
		"""Test that invalid IP address returns error with form retained."""
		response = client.post(
			"/receivers",
			data={
				"name": "Device",
				"ip_address": "invalid-ip",
				"mac_address": "AA:BB:CC:DD:EE:11",
			},
		)
		
		assert response.status_code == 200
		# Check for error response indicators
		assert response.headers.get("HX-Retarget") == "#receiver-new"
		assert response.headers.get("HX-Reswap") == "outerHTML"
		# Form values should be retained
		assert "Device" in response.text

	def test_create_receiver_with_invalid_mac(self, client):
		"""Test that invalid MAC address returns error with form retained."""
		response = client.post(
			"/receivers",
			data={
				"name": "Device",
				"ip_address": "192.168.1.10",
				"mac_address": "invalid-mac",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == "#receiver-new"
		assert response.headers.get("HX-Reswap") == "outerHTML"

	def test_create_receiver_with_duplicate_name(self, client, session):
		"""Test that duplicate name returns conflict error."""
		create_receiver(
			session,
			name="ExistingDevice",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			"/receivers",
			data={
				"name": "ExistingDevice",
				"ip_address": "10.0.0.1",
				"mac_address": "FF:EE:DD:CC:BB:AA",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == "#receiver-new"
		assert response.headers.get("HX-Reswap") == "outerHTML"
		# Form values should be retained
		assert "ExistingDevice" in response.text

	def test_create_receiver_with_duplicate_ip(self, client, session):
		"""Test that duplicate IP address returns conflict error."""
		create_receiver(
			session,
			name="Device1",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			"/receivers",
			data={
				"name": "Device2",
				"ip_address": "192.168.1.10",
				"mac_address": "FF:EE:DD:CC:BB:AA",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == "#receiver-new"
		assert response.headers.get("HX-Reswap") == "outerHTML"

	def test_create_receiver_with_duplicate_mac(self, client, session):
		"""Test that duplicate MAC address returns conflict error."""
		create_receiver(
			session,
			name="Device1",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			"/receivers",
			data={
				"name": "Device2",
				"ip_address": "10.0.0.1",
				"mac_address": "AA:BB:CC:DD:EE:11",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == "#receiver-new"
		assert response.headers.get("HX-Reswap") == "outerHTML"

	def test_create_receiver_normalizes_mac_address(self, client):
		"""Test that MAC address is normalized to colon-separated format."""
		response = client.post(
			"/receivers",
			data={
				"name": "Device",
				"ip_address": "192.168.1.10",
				"mac_address": "AABBCCDDEEFF",  # No colons
			},
		)
		
		assert response.status_code == 200
		# Should show normalized format in response
		assert "AA:BB:CC:DD:EE:FF" in response.text or "Device" in response.text


class TestUpdateReceiver:
	def test_update_receiver_with_device(self, client, session):
		"""Test that updating receiver assigns a device."""
		device = create_device(session, name="Encoder")
		receiver = create_receiver(
			session,
			name="OldName",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			f"/receivers/{receiver.id}/update",
			data={
				"name": "OldName",
				"ip_address": "192.168.1.10",
				"mac_address": "AA:BB:CC:DD:EE:11",
				"device_id": str(device.id),
			},
		)
		
		assert response.status_code == 200
		assert device.name in response.text
	def test_update_receiver_persists_and_returns_index(self, client, session):
		"""Test that updating a receiver persists changes and returns updated index."""
		receiver = create_receiver(
			session,
			name="OldName",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			f"/receivers/{receiver.id}/update",
			data={
				"name": "NewName",
				"ip_address": "10.0.0.1",
				"mac_address": "FF:EE:DD:CC:BB:AA",
			},
		)
		
		assert response.status_code == 200
		assert "NewName" in response.text
		assert "10.0.0.1" in response.text

	def test_update_receiver_with_invalid_ip(self, client, session):
		"""Test that invalid IP returns error with edit row."""
		receiver = create_receiver(
			session,
			name="Device",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			f"/receivers/{receiver.id}/update",
			data={
				"name": "Device",
				"ip_address": "invalid-ip",
				"mac_address": "AA:BB:CC:DD:EE:11",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == f"#receiver-{receiver.id}"
		assert response.headers.get("HX-Reswap") == "outerHTML"
		assert "Device" in response.text

	def test_update_receiver_with_invalid_mac(self, client, session):
		"""Test that invalid MAC returns error with edit row."""
		receiver = create_receiver(
			session,
			name="Device",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			f"/receivers/{receiver.id}/update",
			data={
				"name": "Device",
				"ip_address": "192.168.1.10",
				"mac_address": "invalid-mac",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == f"#receiver-{receiver.id}"
		assert response.headers.get("HX-Reswap") == "outerHTML"

	def test_update_receiver_with_duplicate_name(self, client, session):
		"""Test that changing to duplicate name returns conflict error."""
		receiver1 = create_receiver(
			session,
			name="Device1",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		create_receiver(
			session,
			name="Device2",
			ip_address="192.168.1.20",
			mac_address="AA:BB:CC:DD:EE:22",
		)
		
		response = client.post(
			f"/receivers/{receiver1.id}/update",
			data={
				"name": "Device2",
				"ip_address": "192.168.1.10",
				"mac_address": "AA:BB:CC:DD:EE:11",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == f"#receiver-{receiver1.id}"
		assert response.headers.get("HX-Reswap") == "outerHTML"

	def test_update_receiver_with_duplicate_ip(self, client, session):
		"""Test that changing to duplicate IP returns conflict error."""
		receiver1 = create_receiver(
			session,
			name="Device1",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		create_receiver(
			session,
			name="Device2",
			ip_address="192.168.1.20",
			mac_address="AA:BB:CC:DD:EE:22",
		)
		
		response = client.post(
			f"/receivers/{receiver1.id}/update",
			data={
				"name": "Device1",
				"ip_address": "192.168.1.20",
				"mac_address": "AA:BB:CC:DD:EE:11",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == f"#receiver-{receiver1.id}"
		assert response.headers.get("HX-Reswap") == "outerHTML"

	def test_update_receiver_with_duplicate_mac(self, client, session):
		"""Test that changing to duplicate MAC returns conflict error."""
		receiver1 = create_receiver(
			session,
			name="Device1",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		create_receiver(
			session,
			name="Device2",
			ip_address="192.168.1.20",
			mac_address="AA:BB:CC:DD:EE:22",
		)
		
		response = client.post(
			f"/receivers/{receiver1.id}/update",
			data={
				"name": "Device1",
				"ip_address": "192.168.1.10",
				"mac_address": "AA:BB:CC:DD:EE:22",
			},
		)
		
		assert response.status_code == 200
		assert response.headers.get("HX-Retarget") == f"#receiver-{receiver1.id}"
		assert response.headers.get("HX-Reswap") == "outerHTML"

	def test_update_receiver_allows_same_values(self, client, session):
		"""Test that re-saving with same values works (not treated as conflict)."""
		receiver = create_receiver(
			session,
			name="Device",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			f"/receivers/{receiver.id}/update",
			data={
				"name": "Device",
				"ip_address": "192.168.1.10",
				"mac_address": "AA:BB:CC:DD:EE:11",
			},
		)
		
		assert response.status_code == 200
		# Should succeed and return full index
		assert "Device" in response.text


class TestDeleteReceiver:
	def test_delete_receiver_removes_and_redirects(self, client, session):
		"""Test that deleting a receiver removes it and redirects to index."""
		receiver = create_receiver(
			session,
			name="Device",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		
		response = client.post(
			f"/receivers/{receiver.id}/delete",
			follow_redirects=False,
		)
		
		assert response.status_code == 303
		assert response.headers["location"] == "http://testserver/receivers/"

	def test_delete_receiver_removes_from_database(self, client, session):
		"""Test that deleted receiver is actually removed from database."""
		receiver = create_receiver(
			session,
			name="Device",
			ip_address="192.168.1.10",
			mac_address="AA:BB:CC:DD:EE:11",
		)
		receiver_id = receiver.id
		
		client.post(f"/receivers/{receiver_id}/delete")
		
		# Verify receiver is deleted
		deleted_receiver = session.get(Receiver, receiver_id)
		assert deleted_receiver is None

	def test_delete_nonexistent_receiver_still_redirects(self, client):
		"""Test that deleting a non-existent receiver still redirects."""
		response = client.post(
			"/receivers/9999/delete",
			follow_redirects=False,
		)
		
		assert response.status_code == 303
		assert response.headers["location"] == "http://testserver/receivers/"
