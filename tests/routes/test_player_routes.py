
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.app import app
from app.crud.device_crud import create_device
from app.crud.player_crud import create_player
from app.crud.receiver_crud import create_receiver
from app.db import get_session
from app.models.device import Device
from app.models.player import Player
from app.models.receiver import Receiver  # noqa: F401


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


def test_add_device_to_player_assigns_device(client, session):
	player = create_player(session, name="P1")
	device = create_device(session, name="D1")
	add_device_path = app.url_path_for("add_device_to_player", player_id=player.id)

	response = client.post(
		add_device_path,
		data={"device_id": device.id},
		follow_redirects=False,
	)

	assert response.status_code == 200
	assert f"id=\"player-{player.id}\"" in response.text
	assert "D1" in response.text
	assert f"player-{player.id}-device-{device.id}" in response.text
	# After a successful add, the row re-renders with the add-device toggle unchecked
	assert (
		f"id=\"player-{player.id}-add-device-toggle\"" in response.text
		and "checked" not in response.text.split(f"id=\"player-{player.id}-add-device-toggle\"")[-1].split(">", 1)[0]
	)
	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.player_id == player.id


def test_add_device_to_player_rejects_device_already_assigned(client, session):
	player_a = create_player(session, name="PA")
	player_b = create_player(session, name="PB")
	device = create_device(session, name="D1", player_id=player_b.id)
	add_device_path = app.url_path_for("add_device_to_player", player_id=player_a.id)

	response = client.post(
		add_device_path,
		data={"device_id": device.id},
		follow_redirects=False,
	)

	assert response.status_code == 200
	assert f"id=\"player-{player_a.id}\"" in response.text
	assert "already assigned" in response.text
	# Keep the add-device form open on validation errors
	assert f"id=\"player-{player_a.id}-add-device-toggle\"" in response.text
	assert (
		"checked" in response.text.split(f"id=\"player-{player_a.id}-add-device-toggle\"")[-1].split(">", 1)[0]
	)

	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.player_id == player_b.id


def test_remove_device_from_player_clears_assignment(client, session):
	player = create_player(session, name="P1")
	device = create_device(session, name="D1", player_id=player.id)
	remove_device_path = app.url_path_for(
		"remove_device_from_player",
		player_id=player.id,
		device_id=device.id,
	)

	response = client.post(
		remove_device_path,
		follow_redirects=False,
	)

	assert response.status_code == 303
	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.player_id is None


def test_remove_device_from_player_rejects_not_assigned(client, session):
	player_a = create_player(session, name="PA")
	player_b = create_player(session, name="PB")
	device = create_device(session, name="D1", player_id=player_b.id)
	remove_device_path = app.url_path_for(
		"remove_device_from_player",
		player_id=player_a.id,
		device_id=device.id,
	)

	response = client.post(
		remove_device_path,
		follow_redirects=False,
	)

	assert response.status_code == 400
	assert "not assigned" in response.text
	stored = session.get(Device, device.id)
	assert stored is not None
	assert stored.player_id == player_b.id


def test_monitor_page_displays_players(client, session):
	create_player(session, name="Alice")
	create_player(session, name="Bob")
	read_monitor_path = app.url_path_for("read_monitor")

	response = client.get(read_monitor_path)
	assert response.status_code == 200
	assert "text/html" in response.headers["content-type"]
	assert "Alice" in response.text
	assert "Bob" in response.text


def test_monitor_page_includes_add_player_button(client):
	response = client.get(app.url_path_for("read_monitor"))
	assert response.status_code == 200
	assert "monitor-start-button" in response.text
	assert "Start Monitoring" in response.text
	assert "add-player-button" in response.text
	assert "Add Player" in response.text


def test_monitor_page_hides_receiver_latencies_when_not_monitoring(client, session):
	player = create_player(session, name="P1")
	device = create_device(session, name="D1", player_id=player.id)
	receiver = create_receiver(
		session,
		name="R1",
		ip_address="10.10.10.10",
		mac_address="AA:BB:CC:DD:EE:FF",
		device_id=device.id,
	)
	read_monitor_path = app.url_path_for("read_monitor")

	response = client.get(read_monitor_path)
	assert response.status_code == 200
	marker = f'id="receiver-latency-{receiver.id}"'
	assert marker in response.text
	attr_chunk = response.text.split(marker, 1)[1].split(">", 1)[0]
	assert "hidden" in attr_chunk


def test_add_player_button_returns_new_row_form(client):
	response = client.post(app.url_path_for("add_player_button"))
	assert response.status_code == 200
	assert "player-new" in response.text
	assert "new-player-form" in response.text


def test_create_player_persists_and_returns_index(client):
	response = client.post(
		app.url_path_for("create_player"),
		data={"name": "Charlie"},
	)
	assert response.status_code == 200
	assert "Charlie" in response.text


def test_monitor_page_includes_actions_delete_button_per_player(client, session):
	player = create_player(session, name="DeleteMe")
	read_monitor_path = app.url_path_for("read_monitor")
	delete_player_path = app.url_path_for("delete_player", player_id=player.id)

	response = client.get(read_monitor_path)
	assert response.status_code == 200
	assert "Actions" in response.text
	assert delete_player_path in response.text
	assert "trash-solid-full.svg" in response.text


def test_edit_mode_includes_delete_button_per_player(client, session):
	player = create_player(session, name="DeleteMe")
	delete_player_path = app.url_path_for("delete_player", player_id=player.id)

	response = client.post(app.url_path_for("edit_player_button", player_id=player.id))
	assert response.status_code == 200
	assert delete_player_path in response.text
	assert "trash-solid-full.svg" in response.text


def test_delete_player_removes_and_redirects(client, session):
	player = create_player(session, name="Temp")
	player_id = player.id
	delete_player_path = app.url_path_for("delete_player", player_id=player_id)
	read_monitor_path = app.url_path_for("read_monitor")

	response = client.post(
		delete_player_path,
		follow_redirects=False,
	)

	assert response.status_code == 303
	assert response.headers["location"] == f"http://testserver{read_monitor_path}"
	assert session.get(Player, player_id) is None


def test_edit_player_button_returns_edit_row(client, session):
	player = create_player(session, name="Editable")
	update_player_path = app.url_path_for("update_player", player_id=player.id)

	response = client.post(app.url_path_for("edit_player_button", player_id=player.id))
	assert response.status_code == 200
	assert f"player-{player.id}" in response.text
	assert update_player_path in response.text
	assert "hx-trigger=\"input changed delay:" in response.text
	assert f"player-{player.id}-add-device-toggle" in response.text
	assert f"for=\"player-{player.id}-add-device-toggle\"" in response.text
	assert f"add-device-to-player-{player.id}" in response.text
	assert "player-row--edit" in response.text
	assert "check-solid-full.svg" in response.text
	assert "x-solid-full.svg" in response.text


def test_edit_mode_includes_add_device_selector_with_unassigned_devices(client, session):
	player = create_player(session, name="P1")
	unassigned = create_device(session, name="UnassignedDevice")
	other_player = create_player(session, name="P2")
	assigned_elsewhere = create_device(session, name="AssignedDevice", player_id=other_player.id)
	add_device_path = app.url_path_for("add_device_to_player", player_id=player.id)

	response = client.post(app.url_path_for("edit_player_button", player_id=player.id))

	assert response.status_code == 200
	assert add_device_path in response.text
	assert 'name="device_id"' in response.text
	assert f"value=\"{unassigned.id}\"" in response.text
	assert "UnassignedDevice" in response.text
	assert f"value=\"{assigned_elsewhere.id}\"" not in response.text
	assert "AssignedDevice" not in response.text


def test_cancel_player_button_returns_monitor_row(client, session):
	player = create_player(session, name="Viewable")

	response = client.post(app.url_path_for("cancel_player_button", player_id=player.id))
	assert response.status_code == 200
	assert f"player-{player.id}" in response.text
	assert "player-row--monitor" in response.text


def test_update_player_persists_and_returns_index(client, session):
	player = create_player(session, name="Old")
	update_player_path = app.url_path_for("update_player", player_id=player.id)

	response = client.post(
		update_player_path,
		data={"name": "New"},
	)
	assert response.status_code == 200
	assert "New" in response.text
	stored = session.get(Player, player.id)
	assert stored is not None
	assert stored.name == "New"


def test_update_player_duplicate_name_returns_error_row_with_hx_headers(client, session):
	player_a = create_player(session, name="A")
	player_b = create_player(session, name="B")
	update_player_path = app.url_path_for("update_player", player_id=player_b.id)

	response = client.post(
		update_player_path,
		data={"name": player_a.name},
	)
	assert response.status_code == 200
	assert response.headers.get("HX-Retarget") == f"#player-{player_b.id}"
	assert response.headers.get("HX-Reswap") == "outerHTML"
	assert "already" in response.text.lower()
