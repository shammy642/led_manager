import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.update_manager import UpdateManager, UpdateStepResult


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _fail(stdout: str = "", stderr: str = "error") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout, stderr=stderr)


def _manager(runner) -> UpdateManager:
    return UpdateManager(
        nmcli_path="nmcli",
        git_path="git",
        repo_path=Path("/repo"),
        service_name="myapp",
        systemctl_path="systemctl",
        rescan_wait_seconds=0,
        command_runner=runner,
    )


# ---------------------------------------------------------------------------
# Individual step tests
# ---------------------------------------------------------------------------

def test_enable_wifi_success():
    calls = []
    def runner(cmd):
        calls.append(list(cmd))
        return _ok(stdout="OK")
    result = _manager(runner).enable_wifi()
    assert result == UpdateStepResult(step="wifi_on", success=True, output="OK")
    assert calls[0] == ["nmcli", "radio", "wifi", "on"]


def test_enable_wifi_failure():
    result = _manager(lambda _: _fail(stderr="radio disabled")).enable_wifi()
    assert result.step == "wifi_on"
    assert result.success is False
    assert "radio disabled" in result.output


def test_connect_wifi_success():
    calls = []
    def runner(cmd):
        calls.append(list(cmd))
        return _ok(stdout="connected")
    result = _manager(runner).connect_wifi("MySSID", "secret")
    assert result == UpdateStepResult(step="wifi_connect", success=True, output="connected")
    assert calls[0] == ["nmcli", "dev", "wifi", "connect", "MySSID", "password", "secret"]


def test_connect_wifi_failure():
    result = _manager(lambda _: _fail(stderr="no AP")).connect_wifi("bad", "pw")
    assert result.step == "wifi_connect"
    assert result.success is False


def test_git_pull_success():
    calls = []
    def runner(cmd):
        calls.append(list(cmd))
        return _ok(stdout="Already up to date.")
    result = _manager(runner).git_pull()
    assert result == UpdateStepResult(step="git_pull", success=True, output="Already up to date.")
    assert calls[0] == ["git", "-C", "/repo", "pull"]


def test_git_pull_failure():
    result = _manager(lambda _: _fail(stderr="not a repo")).git_pull()
    assert result.step == "git_pull"
    assert result.success is False


def test_disable_wifi_success():
    calls = []
    def runner(cmd):
        calls.append(list(cmd))
        return _ok()
    result = _manager(runner).disable_wifi()
    assert result == UpdateStepResult(step="wifi_off", success=True, output="")
    assert calls[0] == ["nmcli", "radio", "wifi", "off"]


def test_disable_wifi_failure():
    result = _manager(lambda _: _fail(stderr="busy")).disable_wifi()
    assert result.step == "wifi_off"
    assert result.success is False


def test_rescan_wifi_success():
    calls = []
    def runner(cmd):
        calls.append(list(cmd))
        return _ok()
    result = _manager(runner).rescan_wifi()
    assert result == UpdateStepResult(step="wifi_rescan", success=True, output="")
    assert calls[0] == ["nmcli", "dev", "wifi", "rescan"]


def test_rescan_wifi_failure():
    result = _manager(lambda _: _fail(stderr="failed")).rescan_wifi()
    assert result.step == "wifi_rescan"
    assert result.success is False


def test_rescan_wifi_waits_on_success():
    import time
    m = UpdateManager(rescan_wait_seconds=0.05, command_runner=lambda _: _ok())
    start = time.monotonic()
    m.rescan_wifi()
    assert time.monotonic() - start >= 0.05


def test_rescan_wifi_does_not_wait_on_failure():
    import time
    m = UpdateManager(rescan_wait_seconds=10, command_runner=lambda _: _fail())
    start = time.monotonic()
    m.rescan_wifi()
    assert time.monotonic() - start < 1


# ---------------------------------------------------------------------------
# run_update orchestration
# ---------------------------------------------------------------------------

def test_run_update_all_success():
    responses = [_ok("on"), _ok(), _ok("connected"), _ok("pulled"), _ok("off")]
    idx = 0
    def runner(cmd):
        nonlocal idx
        r = responses[idx]
        idx += 1
        return r
    result = _manager(runner).run_update("ssid", "pw")
    assert result.success is True
    assert [s.step for s in result.steps] == ["wifi_on", "wifi_rescan", "wifi_connect", "git_pull", "wifi_off"]


def test_run_update_stops_at_wifi_on_failure():
    result = _manager(lambda _: _fail()).run_update("ssid", "pw")
    assert result.success is False
    assert [s.step for s in result.steps] == ["wifi_on"]


def test_run_update_stops_at_rescan_failure_does_wifi_off():
    call_count = 0
    def runner(cmd):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _ok()   # wifi_on
        if call_count == 2:
            return _fail() # wifi_rescan
        return _ok()       # wifi_off

    result = _manager(runner).run_update("ssid", "pw")
    assert result.success is False
    assert [s.step for s in result.steps] == ["wifi_on", "wifi_rescan", "wifi_off"]
    assert call_count == 3


def test_run_update_connect_failure_does_wifi_off():
    call_count = 0
    def runner(cmd):
        nonlocal call_count
        call_count += 1
        if call_count in (1, 2):
            return _ok()   # wifi_on, wifi_rescan
        if call_count == 3:
            return _fail() # wifi_connect
        return _ok()       # wifi_off

    result = _manager(runner).run_update("ssid", "pw")
    assert result.success is False
    assert [s.step for s in result.steps] == ["wifi_on", "wifi_rescan", "wifi_connect", "wifi_off"]
    assert call_count == 4


def test_run_update_git_pull_failure_does_wifi_off():
    call_count = 0
    def runner(cmd):
        nonlocal call_count
        call_count += 1
        if call_count in (1, 2, 3):
            return _ok()   # wifi_on, wifi_rescan, wifi_connect
        if call_count == 4:
            return _fail() # git_pull
        return _ok()       # wifi_off

    result = _manager(runner).run_update("ssid", "pw")
    assert result.success is False
    assert [s.step for s in result.steps] == ["wifi_on", "wifi_rescan", "wifi_connect", "git_pull", "wifi_off"]
    assert call_count == 5


def test_run_update_wifi_off_failure_marks_overall_failure():
    # All steps succeed except wifi_off → overall success should be False
    responses = [_ok(), _ok(), _ok(), _ok(), _fail()]
    idx = 0
    def runner(cmd):
        nonlocal idx
        r = responses[idx]
        idx += 1
        return r
    result = _manager(runner).run_update("ssid", "pw")
    assert result.success is False
    assert [s.step for s in result.steps] == ["wifi_on", "wifi_rescan", "wifi_connect", "git_pull", "wifi_off"]


# ---------------------------------------------------------------------------
# restart_service
# ---------------------------------------------------------------------------

def test_restart_service_no_service_name_is_noop():
    m = UpdateManager(service_name="", command_runner=lambda _: _ok())
    # Should not raise and should not call anything
    called = []
    with patch("subprocess.run", side_effect=lambda *a, **kw: called.append(a)):
        m.restart_service(delay_seconds=0)
    assert called == []


def test_restart_service_calls_systemctl():
    m = UpdateManager(service_name="myapp", systemctl_path="systemctl")
    calls = []
    with patch("subprocess.run", side_effect=lambda *a, **kw: calls.append(a) or subprocess.CompletedProcess([], 0)):
        m.restart_service(delay_seconds=0)
    assert len(calls) == 1
    assert list(calls[0][0]) == ["systemctl", "restart", "myapp"]


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------

def test_from_env_defaults(monkeypatch):
    for key in ("UPDATE_NMCLI_PATH", "UPDATE_GIT_PATH", "UPDATE_REPO_PATH", "UPDATE_SERVICE_NAME", "UPDATE_SYSTEMCTL_PATH", "UPDATE_RESCAN_WAIT_SECONDS"):
        monkeypatch.delenv(key, raising=False)

    m = UpdateManager.from_env()
    assert m._nmcli_path == "nmcli"
    assert m._git_path == "git"
    assert m._service_name == ""
    assert m._systemctl_path == "systemctl"
    assert m._repo_path == Path.cwd()
    assert m._rescan_wait_seconds == 5.0


def test_from_env_custom(monkeypatch, tmp_path):
    monkeypatch.setenv("UPDATE_NMCLI_PATH", "/usr/bin/nmcli")
    monkeypatch.setenv("UPDATE_GIT_PATH", "/usr/bin/git")
    monkeypatch.setenv("UPDATE_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("UPDATE_SERVICE_NAME", "led-manager")
    monkeypatch.setenv("UPDATE_SYSTEMCTL_PATH", "/bin/systemctl")
    monkeypatch.setenv("UPDATE_RESCAN_WAIT_SECONDS", "3.5")

    m = UpdateManager.from_env()
    assert m._nmcli_path == "/usr/bin/nmcli"
    assert m._git_path == "/usr/bin/git"
    assert m._repo_path == tmp_path
    assert m._service_name == "led-manager"
    assert m._systemctl_path == "/bin/systemctl"
    assert m._rescan_wait_seconds == 3.5


def test_from_env_invalid_rescan_wait_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("UPDATE_RESCAN_WAIT_SECONDS", "not-a-number")
    m = UpdateManager.from_env()
    assert m._rescan_wait_seconds == 5.0


# ---------------------------------------------------------------------------
# _run_step exception handling
# ---------------------------------------------------------------------------

def test_run_step_captures_exception():
    def bad_runner(cmd):
        raise OSError("command not found")

    m = UpdateManager(command_runner=bad_runner)
    result = m.enable_wifi()
    assert result.success is False
    assert "command not found" in result.output


def test_default_command_runner_executes_process():
    from app.services.update_manager import _default_command_runner

    result = _default_command_runner(["echo", "hello"])
    assert result.returncode == 0
    assert "hello" in result.stdout
