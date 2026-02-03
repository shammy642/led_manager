from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass
from typing import Protocol


class PingProbe(Protocol):
    async def ping_once(self, ip_address: str, *, timeout_seconds: float) -> float | None:
        """Return RTT in milliseconds, or None if no reply."""


@dataclass(frozen=True)
class SubprocessIcmpPingProbe:
    """Cross-platform ICMP ping using the system `ping` binary.

    Notes:
    - Browsers can't send ICMP. This runs server-side.
    - Uses an asyncio timeout AND passes a platform-specific timeout to `ping`.
    """

    _windows_rtt = re.compile(r"time[=<]\s*([0-9]+)\s*ms", re.IGNORECASE)
    _posix_rtt = re.compile(r"time[=<]?\s*([0-9]+(?:\.[0-9]+)?)\s*ms", re.IGNORECASE)

    def _build_command(self, ip_address: str, *, timeout_seconds: float) -> list[str]:
        if sys.platform.startswith("win"):
            timeout_ms = max(1, int(timeout_seconds * 1000))
            return ["ping", "-n", "1", "-w", str(timeout_ms), ip_address]

        # Linux: -W is in seconds (integer).
        # macOS: -W exists and is milliseconds in newer versions.
        # We still enforce the timeout with asyncio.wait_for regardless.
        if sys.platform == "darwin":
            timeout_ms = max(1, int(timeout_seconds * 1000))
            return ["ping", "-n", "-c", "1", "-W", str(timeout_ms), ip_address]

        timeout_int = max(1, int(timeout_seconds))
        return ["ping", "-n", "-c", "1", "-W", str(timeout_int), ip_address]

    def _parse_rtt_ms(self, output: str) -> float | None:
        if sys.platform.startswith("win"):
            match = self._windows_rtt.search(output)
            return float(match.group(1)) if match else None

        match = self._posix_rtt.search(output)
        return float(match.group(1)) if match else None

    async def ping_once(self, ip_address: str, *, timeout_seconds: float) -> float | None:
        cmd = self._build_command(ip_address, timeout_seconds=timeout_seconds)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        try:
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return None
        except asyncio.CancelledError:
            proc.kill()
            await proc.communicate()
            raise

        text = (stdout or b"").decode(errors="ignore")
        return self._parse_rtt_ms(text)
