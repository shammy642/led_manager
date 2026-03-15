import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.app import app
from app.db import get_session
from app.services.update_manager import UpdateManager, UpdateResult, UpdateStepResult


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


def _make_client(session, mock_manager):
    def get_session_override():
        return session

    def get_manager_override():
        return mock_manager

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[UpdateManager.from_env] = get_manager_override
    client = TestClient(app)
    return client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


class MockUpdateManager:
    def __init__(self, result: UpdateResult):
        self._result = result
        self.restart_called = False

    def run_update(self, ssid: str, password: str) -> UpdateResult:
        return self._result

    def restart_service(self, delay_seconds: float = 2.0) -> None:
        self.restart_called = True


def _success_result() -> UpdateResult:
    return UpdateResult(
        success=True,
        steps=[
            UpdateStepResult(step="wifi_on", success=True, output=""),
            UpdateStepResult(step="wifi_connect", success=True, output="connected"),
            UpdateStepResult(step="git_pull", success=True, output="Already up to date."),
            UpdateStepResult(step="wifi_off", success=True, output=""),
        ],
    )


def _failure_result(failed_step: str) -> UpdateResult:
    steps = [UpdateStepResult(step="wifi_on", success=True, output="")]
    if failed_step in ("wifi_connect", "git_pull"):
        steps.append(UpdateStepResult(step="wifi_connect", success=(failed_step != "wifi_connect"), output="no AP" if failed_step == "wifi_connect" else "connected"))
    if failed_step == "git_pull":
        steps.append(UpdateStepResult(step="git_pull", success=False, output="not a repo"))
    if failed_step == "wifi_on":
        steps = [UpdateStepResult(step="wifi_on", success=False, output="blocked")]
    return UpdateResult(success=False, steps=steps)


# ---------------------------------------------------------------------------
# GET /update/
# ---------------------------------------------------------------------------

def test_get_update_page(session):
    mock = MockUpdateManager(_success_result())
    client = _make_client(session, mock)
    response = client.get(app.url_path_for("read_update"))
    assert response.status_code == 200
    assert "Update" in response.text
    assert "update-status" in response.text


# ---------------------------------------------------------------------------
# POST /update/ — success
# ---------------------------------------------------------------------------

def test_post_update_success(session):
    mock = MockUpdateManager(_success_result())
    client = _make_client(session, mock)
    response = client.post(
        app.url_path_for("run_update"),
        data={"ssid": "MyWifi", "password": "secret"},
    )
    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#update-status"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert "update-status" in response.text
    assert "Update complete" in response.text
    assert "Already up to date." in response.text


def test_post_update_success_schedules_restart(session):
    # BackgroundTasks run synchronously inside TestClient
    mock = MockUpdateManager(_success_result())
    client = _make_client(session, mock)

    # Patch restart_service to avoid sleeping
    original = mock.restart_service
    calls = []
    mock.restart_service = lambda delay_seconds=2.0: calls.append(delay_seconds)

    client.post(
        app.url_path_for("run_update"),
        data={"ssid": "ssid", "password": "pw"},
    )
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# POST /update/ — failures
# ---------------------------------------------------------------------------

def test_post_update_failure_wifi_on(session):
    mock = MockUpdateManager(_failure_result("wifi_on"))
    client = _make_client(session, mock)
    response = client.post(
        app.url_path_for("run_update"),
        data={"ssid": "ssid", "password": "pw"},
    )
    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#update-status"
    assert "Update failed" in response.text
    assert "blocked" in response.text


def test_post_update_failure_connect(session):
    mock = MockUpdateManager(_failure_result("wifi_connect"))
    client = _make_client(session, mock)
    response = client.post(
        app.url_path_for("run_update"),
        data={"ssid": "ssid", "password": "pw"},
    )
    assert response.status_code == 200
    assert "Update failed" in response.text
    assert "no AP" in response.text


def test_post_update_failure_git_pull(session):
    mock = MockUpdateManager(_failure_result("git_pull"))
    client = _make_client(session, mock)
    response = client.post(
        app.url_path_for("run_update"),
        data={"ssid": "ssid", "password": "pw"},
    )
    assert response.status_code == 200
    assert "Update failed" in response.text
    assert "not a repo" in response.text


def test_post_update_failure_does_not_restart(session):
    mock = MockUpdateManager(_failure_result("wifi_on"))
    client = _make_client(session, mock)
    calls = []
    mock.restart_service = lambda delay_seconds=2.0: calls.append(delay_seconds)
    client.post(
        app.url_path_for("run_update"),
        data={"ssid": "ssid", "password": "pw"},
    )
    assert calls == []
