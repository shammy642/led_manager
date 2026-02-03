import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.app import app
from app.crud.device_crud import create_device
from app.crud.receiver_crud import create_receiver
from app.db import get_session
from app.services.dnsmasq_manager import DnsmasqManager


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


def test_add_receiver_button_returns_form(client):
	"""Test that the add receiver button returns a new form row."""
	response = client.post("/ui/receiver/add")
	
	assert response.status_code == 200
	assert "receiver-new" in response.text


def test_add_receiver_button_includes_device_options(client, session):
	"""Test that device options are rendered in the new row."""
	device = create_device(session, name="Dock")

	response = client.post("/ui/receiver/add")

	assert response.status_code == 200
	assert device.name in response.text


def test_edit_receiver_button_returns_edit_form(client, session):
	"""Test that the edit button returns the receiver in edit mode."""
	device = create_device(session, name="Matrix")
	receiver = create_receiver(
		session,
		name="Device",
		ip_address="192.168.1.10",
		mac_address="AA:BB:CC:DD:EE:11",
		device_id=device.id,
	)
	
	response = client.post(f"/ui/receiver/{receiver.id}/edit")
	
	assert response.status_code == 200
	assert "Device" in response.text
	assert device.name in response.text


def test_cancel_receiver_button_returns_view_form(client, session):
	"""Test that the cancel button returns the receiver in view mode."""
	device = create_device(session, name="Switch")
	receiver = create_receiver(
		session,
		name="Device",
		ip_address="192.168.1.10",
		mac_address="AA:BB:CC:DD:EE:11",
		device_id=device.id,
	)
	
	response = client.post(f"/ui/receiver/{receiver.id}/cancel")
	
	assert response.status_code == 200
	assert "Device" in response.text
	assert device.name in response.text


def test_cancel_new_receiver_with_path_param(client, session):
	"""Test that the cancel path-based route works."""
	receiver = create_receiver(
		session,
		name="Device",
		ip_address="192.168.1.10",
		mac_address="AA:BB:CC:DD:EE:11",
	)
	# This tests the {receiver_id}/cancel path, not /cancel
	response = client.post(f"/ui/receiver/{receiver.id}/cancel")
	
	assert response.status_code == 200


def test_apply_receiver_changes_calls_dnsmasq_apply(client, session):
	receiver = create_receiver(
		session,
		name="R1",
		ip_address="10.0.0.10",
		mac_address="AA:BB:CC:DD:EE:FF",
	)

	class _FakeManager:
		def __init__(self) -> None:
			self.applied = None

		def apply(self, devices):
			self.applied = list(devices)

	fake = _FakeManager()

	def _dnsmasq_override():
		return fake

	app.dependency_overrides[DnsmasqManager.from_env] = _dnsmasq_override
	try:
		response = client.post("/ui/receiver/apply")
	finally:
		app.dependency_overrides.pop(DnsmasqManager.from_env, None)

	assert response.status_code == 200
	assert "Applied" in response.text
	assert fake.applied == [
		{"name": receiver.name, "ip_address": receiver.ip_address, "mac_address": receiver.mac_address}
	]


def test_apply_receiver_changes_returns_error_when_unconfigured(client):
	response = client.post("/ui/receiver/apply")
	assert response.status_code == 200
	assert "DNSMASQ_DHCP_CONF_PATH" in response.text
