import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.app import app
from app.crud.device_crud import create_device
from app.crud.player_crud import add_device_to_player, create_player
from app.crud.receiver_crud import create_receiver
from app.db import get_session
from app.services.ping_dependencies import get_ping_probe
from app.services.monitor_hub import reset_monitor_hub_for_tests


class ImmediateProbe:
	async def ping_once(self, ip_address: str, *, timeout_seconds: float) -> float | None:  # noqa: ARG002
		return 7.0


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

	def get_ping_probe_override():
		return ImmediateProbe()

	app.dependency_overrides[get_session] = get_session_override
	app.dependency_overrides[get_ping_probe] = get_ping_probe_override
	yield TestClient(app)
	app.dependency_overrides.clear()
	reset_monitor_hub_for_tests()


def test_monitor_pings_websocket_streams_receiver_results(client, session):
	stop_path = app.url_path_for("stop_monitoring")
	start_path = app.url_path_for("start_monitoring")
	pings_ws_path = app.url_path_for("monitor_pings_ws")
	client.post(stop_path)
	client.post(start_path)

	player = create_player(session, name="P1")
	device = create_device(session, name="D1")
	add_device_to_player(session, player.id, device.id)

	receiver = create_receiver(
		session,
		name="R1",
		ip_address="10.0.0.1",
		mac_address="AA:BB:CC:DD:EE:11",
		device_id=device.id,
	)
	assert receiver.id is not None

	with client.websocket_connect(pings_ws_path) as ws:
		msg = ws.receive_json()

	assert msg["seq"] >= 1
	assert isinstance(msg["results"], list)
	assert len(msg["results"]) == 1
	result = msg["results"][0]
	assert result["receiver_id"] == receiver.id
	assert result["status"] == "ok"
	assert result["rtt_ms"] == 7.0

	# Reset global state for other tests.
	client.post(stop_path)


def test_monitor_pings_websocket_broadcasts_to_multiple_clients(client, session, monkeypatch):
	monkeypatch.setenv("MONITOR_PING_INTERVAL_SECONDS", "0.02")
	stop_path = app.url_path_for("stop_monitoring")
	start_path = app.url_path_for("start_monitoring")
	pings_ws_path = app.url_path_for("monitor_pings_ws")
	client.post(stop_path)
	client.post(start_path)

	player = create_player(session, name="P1")
	device = create_device(session, name="D1")
	add_device_to_player(session, player.id, device.id)

	receiver = create_receiver(
		session,
		name="R1",
		ip_address="10.0.0.1",
		mac_address="AA:BB:CC:DD:EE:11",
		device_id=device.id,
	)
	assert receiver.id is not None

	with client.websocket_connect(pings_ws_path) as ws1:
		with client.websocket_connect(pings_ws_path) as ws2:
			msg1 = ws1.receive_json()
			msg2 = ws2.receive_json()

	assert len(msg1["results"]) == 1
	assert len(msg2["results"]) == 1
	assert msg1["results"][0]["receiver_id"] == receiver.id
	assert msg2["results"][0]["receiver_id"] == receiver.id

	client.post(stop_path)


def test_monitor_control_websocket_receives_reload_on_toggle(client):
	stop_path = app.url_path_for("stop_monitoring")
	start_path = app.url_path_for("start_monitoring")
	control_ws_path = app.url_path_for("monitor_control_ws")
	client.post(stop_path)

	with client.websocket_connect(control_ws_path) as ws:
		initial = ws.receive_json()
		assert initial["type"] == "monitoring"
		assert initial["active"] is False

		client.post(start_path)
		msg = ws.receive_json()
		assert msg["type"] == "monitoring"
		assert msg["active"] is True

		client.post(stop_path)
		stopped = ws.receive_json()

	assert stopped["type"] == "monitoring"
	assert stopped["active"] is False


def test_monitor_control_websocket_receives_monitoring_on_redundant_stop(client):
	stop_path = app.url_path_for("stop_monitoring")
	control_ws_path = app.url_path_for("monitor_control_ws")
	client.post(stop_path)

	with client.websocket_connect(control_ws_path) as ws:
		initial = ws.receive_json()
		assert initial["type"] == "monitoring"
		assert initial["active"] is False

		client.post(stop_path)
		repeat = ws.receive_json()

	assert repeat["type"] == "monitoring"
	assert repeat["active"] is False
