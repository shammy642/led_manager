from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator

from app.services.ping_probe import PingProbe


@dataclass(frozen=True)
class PingTarget:
    receiver_id: int
    ip_address: str
    name: str


@dataclass(frozen=True)
class PingResult:
    receiver_id: int
    seq: int
    status: str  # "ok" | "timeout" | "error"
    rtt_ms: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "receiver_id": self.receiver_id,
            "seq": self.seq,
            "status": self.status,
            "rtt_ms": self.rtt_ms,
        }


@dataclass(frozen=True)
class PingTickResult:
    seq: int
    results: list[PingResult]

    def as_dict(self) -> dict[str, object]:
        return {
            "seq": self.seq,
            "results": [result.as_dict() for result in self.results],
        }


class PingManager:
    """Runs fixed-tick pings across a set of receivers.

    Requirements satisfied:
    - Pings are launched together each tick (fan-out tasks).
    - Any ping not finished by the next tick is cancelled and treated as timeout.
    - Tick scheduling uses monotonic time to minimize drift.
    """

    def __init__(
        self,
        *,
        interval_seconds: float,
        probe: PingProbe,
        targets: list[PingTarget],
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        self._interval = float(interval_seconds)
        self._probe = probe
        self._targets = targets
        self._stop = asyncio.Event()
        self._seq = 0

    def request_stop(self) -> None:
        self._stop.set()

    async def run(self) -> AsyncIterator[PingTickResult]:
        loop = asyncio.get_running_loop()
        next_tick = loop.time()

        while not self._stop.is_set():
            now = loop.time()
            if now < next_tick:
                await asyncio.sleep(next_tick - now)

            tick_start = loop.time()
            tick_end = tick_start + self._interval

            self._seq += 1
            seq = self._seq

            async def _one(target: PingTarget) -> PingResult:
                try:
                    rtt = await self._probe.ping_once(
                        target.ip_address,
                        timeout_seconds=self._interval,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    return PingResult(
                        receiver_id=target.receiver_id,
                        seq=seq,
                        status="error",
                        rtt_ms=None,
                    )

                if rtt is None:
                    return PingResult(
                        receiver_id=target.receiver_id,
                        seq=seq,
                        status="timeout",
                        rtt_ms=None,
                    )

                return PingResult(
                    receiver_id=target.receiver_id,
                    seq=seq,
                    status="ok",
                    rtt_ms=rtt,
                )

            tasks_by_id = {
                target.receiver_id: asyncio.create_task(_one(target)) for target in self._targets
            }

            try:
                results_by_id: dict[int, PingResult] = {}

                pending = set(tasks_by_id.values())
                while pending and not self._stop.is_set():
                    remaining = tick_end - loop.time()
                    if remaining <= 0:
                        break

                    done, pending = await asyncio.wait(
                        pending,
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in done:
                        result = task.result()
                        results_by_id[result.receiver_id] = result

                # Tick boundary: cancel anything still running.
                pending_receiver_ids = {
                    receiver_id
                    for receiver_id, task in tasks_by_id.items()
                    if not task.done()
                }
                if pending_receiver_ids:
                    for task in tasks_by_id.values():
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks_by_id.values(), return_exceptions=True)

                    for receiver_id in pending_receiver_ids:
                        results_by_id[receiver_id] = PingResult(
                            receiver_id=receiver_id,
                            seq=seq,
                            status="timeout",
                            rtt_ms=None,
                        )

                # Emit exactly once per tick, so the UI can update all at once.
                ordered_results = [
                    results_by_id[target.receiver_id]
                    for target in self._targets
                    if target.receiver_id in results_by_id
                ]
                yield PingTickResult(seq=seq, results=ordered_results)
            finally:
                # Prevent task leaks on shutdown.
                for task in tasks_by_id.values():
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks_by_id.values(), return_exceptions=True)

            next_tick = next_tick + self._interval
