from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Final

from fastapi import WebSocket

from app.services.ping_manager import PingManager, PingTarget, PingTickResult
from app.services.ping_probe import PingProbe


_ENV_INTERVAL_SECONDS: Final[str] = "MONITOR_PING_INTERVAL_SECONDS"
_DEFAULT_INTERVAL_SECONDS: Final[float] = 1.0


@dataclass(frozen=True)
class MonitorControlMessage:
    type: str

    def as_dict(self) -> dict[str, str]:
        return {"type": self.type}


@dataclass(frozen=True)
class MonitorMonitoringMessage:
    type: str
    active: bool

    def as_dict(self) -> dict[str, object]:
        return {"type": self.type, "active": self.active}


class MonitorHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._monitoring_active: bool = False

        self._control_subscribers: dict[WebSocket, _Subscriber[dict[str, object]]] = {}
        self._ping_subscribers: dict[WebSocket, _Subscriber[dict[str, object] | None]] = {}

        self._targets: list[PingTarget] = []
        self._probe: PingProbe | None = None

        self._ping_manager: PingManager | None = None
        self._ping_task: asyncio.Task[None] | None = None

    def _put_latest(self, subscriber: _Subscriber[object], payload: object) -> None:
        try:
            subscriber.queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                _ = subscriber.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                subscriber.queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def _enqueue(self, subscriber: _Subscriber[object], payload: object) -> None:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is subscriber.loop:
            self._put_latest(subscriber, payload)
            return

        # Cross-thread/event-loop safe scheduling.
        subscriber.loop.call_soon_threadsafe(self._put_latest, subscriber, payload)

    @property
    def monitoring_active(self) -> bool:
        return self._monitoring_active

    def _read_interval_seconds(self) -> float:
        raw = os.getenv(_ENV_INTERVAL_SECONDS)
        if raw is None or raw.strip() == "":
            return _DEFAULT_INTERVAL_SECONDS
        try:
            value = float(raw)
        except ValueError:
            return _DEFAULT_INTERVAL_SECONDS
        return value if value > 0 else _DEFAULT_INTERVAL_SECONDS

    async def add_control_client(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._control_subscribers.setdefault(
                websocket,
                _Subscriber(loop=asyncio.get_running_loop(), queue=asyncio.Queue(maxsize=1)),
            )

    async def remove_control_client(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._control_subscribers.pop(websocket, None)

    async def handle_control_client(self, websocket: WebSocket) -> None:
        await websocket.accept()
        await self.add_control_client(websocket)

        async with self._lock:
            subscriber = self._control_subscribers[websocket]
            queue = subscriber.queue

            # Immediately tell the client the current monitoring state.
            self._enqueue(
                subscriber,
                MonitorMonitoringMessage(
                    type="monitoring",
                    active=self._monitoring_active,
                ).as_dict(),
            )

        try:
            while True:
                queue_task = asyncio.create_task(queue.get())
                recv_task = asyncio.create_task(websocket.receive_text())
                done, pending = await asyncio.wait(
                    {queue_task, recv_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()

                if queue_task in done:
                    payload = queue_task.result()
                    await websocket.send_json(payload)
                else:
                    # Ignore any client messages.
                    _ = recv_task.result()
        except Exception:
            pass
        finally:
            await self.remove_control_client(websocket)

    async def broadcast_reload(self) -> None:
        async with self._lock:
            subscribers = list(self._control_subscribers.values())

        if not subscribers:
            return

        payload = MonitorControlMessage(type="reload").as_dict()
        for subscriber in subscribers:
            self._enqueue(subscriber, payload)

    async def broadcast_monitoring_state(self) -> None:
        async with self._lock:
            subscribers = list(self._control_subscribers.values())
            active = self._monitoring_active

        if not subscribers:
            return

        payload = MonitorMonitoringMessage(type="monitoring", active=active).as_dict()
        for subscriber in subscribers:
            self._enqueue(subscriber, payload)

    async def set_monitoring_active(self, active: bool) -> None:
        should_broadcast = False

        async with self._lock:
            if self._monitoring_active == active:
                return

            self._monitoring_active = active
            should_broadcast = True

            if not active:
                await self._stop_pings_locked(close_clients=True)

        if should_broadcast:
            await self.broadcast_monitoring_state()

    async def _ensure_ping_task_locked(self) -> None:
        if self._ping_task is not None and not self._ping_task.done():
            return
        if not self._monitoring_active:
            return
        if not self._ping_subscribers:
            return
        if self._probe is None:
            return

        interval_seconds = self._read_interval_seconds()
        manager = PingManager(interval_seconds=interval_seconds, probe=self._probe, targets=self._targets)
        self._ping_manager = manager
        self._ping_task = asyncio.create_task(self._run_ping_loop(manager))

    async def _stop_pings_locked(self, *, close_clients: bool) -> None:
        if self._ping_manager is not None:
            self._ping_manager.request_stop()

        if close_clients and self._ping_subscribers:
            subscribers = list(self._ping_subscribers.values())
            self._ping_subscribers.clear()
            for subscriber in subscribers:
                # Signal handlers to close their websocket in their own loop.
                self._enqueue(subscriber, None)

        task = self._ping_task
        self._ping_task = None
        self._ping_manager = None

        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    async def _run_ping_loop(self, manager: PingManager) -> None:
        try:
            async for tick in manager.run():
                await self._broadcast_tick(tick)

                async with self._lock:
                    if not self._monitoring_active or not self._ping_subscribers:
                        manager.request_stop()
        except asyncio.CancelledError:
            manager.request_stop()
            raise

    async def _broadcast_tick(self, tick: PingTickResult) -> None:
        async with self._lock:
            subscribers = list(self._ping_subscribers.values())

        if not subscribers:
            return

        payload = tick.as_dict()
        for subscriber in subscribers:
            self._enqueue(subscriber, payload)

    async def handle_ping_client(
        self,
        websocket: WebSocket,
        *,
        targets: list[PingTarget],
        probe: PingProbe,
    ) -> None:
        await websocket.accept()

        # Enforce global monitoring. The client should only connect when active.
        if not self.monitoring_active:
            await websocket.close(code=1008)
            return

        broadcast_reload = False

        async with self._lock:
            self._ping_subscribers.setdefault(
                websocket,
                _Subscriber(loop=asyncio.get_running_loop(), queue=asyncio.Queue(maxsize=1)),
            )
            queue = self._ping_subscribers[websocket].queue

            # Adopt the newest target snapshot from the latest page refresh.
            if self._targets != targets:
                self._targets = targets
                broadcast_reload = True

            if self._probe is None:
                self._probe = probe

            await self._ensure_ping_task_locked()

        if broadcast_reload:
            await self.broadcast_reload()

        try:
            while True:
                payload = await queue.get()
                if payload is None:
                    break
                await websocket.send_json(payload)
        except Exception:
            pass
        finally:
            async with self._lock:
                self._ping_subscribers.pop(websocket, None)
                if not self._ping_subscribers:
                    await self._stop_pings_locked(close_clients=False)

            try:
                await websocket.close(code=1000)
            except Exception:
                pass


@dataclass(frozen=True)
class _Subscriber[T]:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[T]


_HUB: MonitorHub | None = None


def get_monitor_hub() -> MonitorHub:
    global _HUB  # noqa: PLW0603
    if _HUB is None:
        _HUB = MonitorHub()
    return _HUB


def reset_monitor_hub_for_tests() -> None:
    """Reset the in-process monitor hub singleton.

    Intended for tests only to ensure global state doesn't leak between cases.
    """
    global _HUB  # noqa: PLW0603
    _HUB = None
