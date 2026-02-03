import asyncio

from app.services.ping_manager import PingManager, PingTarget


class _FakeProbe:
	def __init__(self, *, rtt_ms: float | None, sleep_seconds: float = 0.0):
		self._rtt_ms = rtt_ms
		self._sleep_seconds = sleep_seconds

	async def ping_once(self, ip_address: str, *, timeout_seconds: float) -> float | None:  # noqa: ARG002
		if self._sleep_seconds:
			await asyncio.sleep(self._sleep_seconds)
		return self._rtt_ms


def test_ping_manager_emits_one_result_per_target():
	async def _run() -> list[tuple[int, str, float | None]]:
		probe = _FakeProbe(rtt_ms=12.3)
		manager = PingManager(
			interval_seconds=0.05,
			probe=probe,
			targets=[
				PingTarget(receiver_id=1, ip_address="10.0.0.1", name="A"),
				PingTarget(receiver_id=2, ip_address="10.0.0.2", name="B"),
			],
		)

		results: list[tuple[int, str, float | None]] = []
		async for tick in manager.run():
			for result in tick.results:
				results.append((result.receiver_id, result.status, result.rtt_ms))
			manager.request_stop()
		return results

	results = asyncio.run(_run())
	assert {receiver_id for receiver_id, _, _ in results} == {1, 2}
	assert all(status == "ok" for _, status, _ in results)
	assert all(rtt is not None for _, _, rtt in results)


def test_ping_manager_reports_timeout_for_slow_pings():
	async def _run() -> list[tuple[int, str, float | None]]:
		probe = _FakeProbe(rtt_ms=1.0, sleep_seconds=0.2)
		manager = PingManager(
			interval_seconds=0.05,
			probe=probe,
			targets=[PingTarget(receiver_id=1, ip_address="10.0.0.1", name="A")],
		)

		results: list[tuple[int, str, float | None]] = []
		async for tick in manager.run():
			for result in tick.results:
				results.append((result.receiver_id, result.status, result.rtt_ms))
			manager.request_stop()
		return results

	results = asyncio.run(_run())
	assert results == [(1, "timeout", None)]
