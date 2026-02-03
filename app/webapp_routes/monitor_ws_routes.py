from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket
from sqlmodel import Session

from app.crud import player_crud
from app.db import get_session
from app.services.monitor_hub import get_monitor_hub
from app.services.ping_dependencies import get_ping_probe
from app.services.ping_manager import PingTarget
from app.services.ping_probe import PingProbe

monitor_ws_router = APIRouter()


@monitor_ws_router.websocket("/ws/monitor/control", name="monitor_control_ws")
async def monitor_control_ws(websocket: WebSocket):
	hub = get_monitor_hub()
	await hub.handle_control_client(websocket)


@monitor_ws_router.websocket("/ws/monitor/pings", name="monitor_pings_ws")
async def monitor_pings_ws(
	websocket: WebSocket,
	session: Session = Depends(get_session),
	probe: PingProbe = Depends(get_ping_probe),
):
	hub = get_monitor_hub()
	players = player_crud.list_players_with_devices_and_receivers(session)
	targets: list[PingTarget] = []
	for player in players:
		for device in player.devices:
			for receiver in device.receivers:
				if receiver.id is None:
					continue
				targets.append(
					PingTarget(
						receiver_id=receiver.id,
						ip_address=receiver.ip_address,
						name=receiver.name,
					)
				)

	await hub.handle_ping_client(websocket, targets=targets, probe=probe)
