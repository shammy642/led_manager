import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.app import app
from app.db import get_session
from app.services.monitor_hub import reset_monitor_hub_for_tests


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
	reset_monitor_hub_for_tests()


def test_monitor_stop_route_returns_start_button(client):
	stop_path = app.url_path_for("stop_monitoring")
	start_path = app.url_path_for("start_monitoring")
	response = client.post(stop_path)
	assert response.status_code == 200
	assert "monitor-toggle" in response.text
	assert "data-monitoring=\"false\"" in response.text
	assert "monitor-start-button" in response.text
	assert start_path in response.text


def test_monitor_start_route_returns_stop_button(client):
	stop_path = app.url_path_for("stop_monitoring")
	start_path = app.url_path_for("start_monitoring")
	response = client.post(start_path)
	assert response.status_code == 200
	assert "monitor-toggle" in response.text
	assert "data-monitoring=\"true\"" in response.text
	assert "monitor-stop-button" in response.text
	assert stop_path in response.text

	# Reset global state for other tests.
	client.post(stop_path)
