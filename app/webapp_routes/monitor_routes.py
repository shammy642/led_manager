
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.crud import device_crud, player_crud
from app.db import get_session
from app.services.dnsmasq_manager import DnsmasqManager
from app.services.monitor_hub import get_monitor_hub
from app.utils.exceptions import PlayerConflictError, PlayerValidationError

monitor_router = APIRouter(prefix="/monitor")
templates = Jinja2Templates(directory="app/templates")


def _list_available_devices(session: Session):
	return [device for device in device_crud.list_devices(session) if device.player_id is None]


@monitor_router.get("/", response_class=HTMLResponse, name="read_monitor")
def read_monitor(
	request: Request,
	session: Session = Depends(get_session),
	dnsmasq_manager: DnsmasqManager | None = Depends(DnsmasqManager.from_env),
):
	hub = get_monitor_hub()
	players = player_crud.list_players_with_devices_and_receivers(session)
	available_devices = _list_available_devices(session)
	
	dnsmasq_status = None
	if dnsmasq_manager:
		dnsmasq_status = dnsmasq_manager.get_status()

	return templates.TemplateResponse(
		"index.html",
		{
			"request": request,
			"active_page": "monitor",
			"players": players,
			"available_devices": available_devices,
			"monitoring_active": hub.monitoring_active,
			"dnsmasq_status": dnsmasq_status,
		},
		status_code=status.HTTP_200_OK,
	)


@monitor_router.post("/", name="create_player")
def create_player_route(
	request: Request,
	name: str = Form(...),
	session: Session = Depends(get_session),
):
	try:
		player_crud.create_player(session, name=name)
	except (PlayerValidationError, PlayerConflictError) as exc:
		response = templates.TemplateResponse(
			"partials/player_row.html",
			{
				"request": request,
				"mode": "new",
				"create_errors": {
					"name": exc.messages.get("name") or exc.messages.get("conflict"),
				},
				"create_form": {
					"name": name,
				},
			},
		)
		response.headers["HX-Retarget"] = "#player-new"
		response.headers["HX-Reswap"] = "outerHTML"
		return response

	players = player_crud.list_players_with_devices_and_receivers(session)
	available_devices = _list_available_devices(session)
	return templates.TemplateResponse(
		"index.html",
		{
			"request": request,
			"active_page": "monitor",
			"players": players,
			"available_devices": available_devices,
		},
		status_code=status.HTTP_200_OK,
	)


@monitor_router.post("/{player_id}/devices/add", name="add_device_to_player")
def add_device_to_player_route(
	request: Request,
	player_id: int,
	device_id: int = Form(...),
	session: Session = Depends(get_session),
):
	try:
		player_crud.add_device_to_player(session, player_id, device_id)
	except PlayerValidationError as exc:
		player = player_crud.get_player_with_devices_and_receivers(session, player_id)
		available_devices = _list_available_devices(session)
		message = (
			exc.messages.get("device_id")
			or exc.messages.get("player_id")
			or "Invalid request."
		)
		return templates.TemplateResponse(
			"partials/player_row.html",
			{
				"request": request,
				"mode": "edit",
				"player": player,
				"available_devices": available_devices,
				"add_device_errors": {"device_id": message},
				"add_device_form": {"device_id": device_id},
				"add_device_open": True,
			},
			status_code=status.HTTP_200_OK,
		)

	player = player_crud.get_player_with_devices_and_receivers(session, player_id)
	available_devices = _list_available_devices(session)
	return templates.TemplateResponse(
		"partials/player_row.html",
		{
			"request": request,
			"mode": "edit",
			"player": player,
			"available_devices": available_devices,
		},
		status_code=status.HTTP_200_OK,
	)


@monitor_router.post(
	"/{player_id}/devices/{device_id}/remove",
	name="remove_device_from_player",
)
def remove_device_from_player_route(
	request: Request,
	player_id: int,
	device_id: int,
	session: Session = Depends(get_session),
):
	try:
		player_crud.remove_device_from_player(session, player_id, device_id)
	except PlayerValidationError as exc:
		message = (
			exc.messages.get("device_id")
			or exc.messages.get("player_id")
			or "Invalid request."
		)
		return HTMLResponse(content=message, status_code=status.HTTP_400_BAD_REQUEST)

	redirect_to = request.headers.get("referer") or request.url_for("read_devices")
	return RedirectResponse(url=str(redirect_to), status_code=status.HTTP_303_SEE_OTHER)


@monitor_router.post("/{player_id}/delete", name="delete_player")
def delete_player_route(
	request: Request,
	player_id: int,
	session: Session = Depends(get_session),
):
	player_crud.delete_player(session, player_id)
	return RedirectResponse(
		url=request.url_for("read_monitor"),
		status_code=status.HTTP_303_SEE_OTHER,
	)


@monitor_router.post("/{player_id}/update", name="update_player")
def update_player_route(
	request: Request,
	player_id: int,
	name: str = Form(...),
	session: Session = Depends(get_session),
):
	try:
		updated = player_crud.update_player(session, player_id, name=name)
	except (PlayerValidationError, PlayerConflictError) as exc:
		player = player_crud.get_player(session, player_id)
		available_devices = _list_available_devices(session)
		response = templates.TemplateResponse(
			"partials/player_row.html",
			{
				"request": request,
				"mode": "edit",
				"player": player,
				"available_devices": available_devices,
				"update_errors": {
					player_id: [
						exc.messages.get("name") or exc.messages.get("conflict"),
					]
				},
			},
		)
		response.headers["HX-Retarget"] = f"#player-{player_id}"
		response.headers["HX-Reswap"] = "outerHTML"
		return response

	# For HTMX autosave, return only the updated row.
	if request.headers.get("HX-Request") == "true":
		available_devices = _list_available_devices(session)
		return templates.TemplateResponse(
			"partials/player_row.html",
			{
				"request": request,
				"mode": "edit",
				"player": updated,
				"available_devices": available_devices,
			},
			status_code=status.HTTP_200_OK,
		)

	players = player_crud.list_players_with_devices_and_receivers(session)
	available_devices = _list_available_devices(session)
	return templates.TemplateResponse(
		"index.html",
		{
			"request": request,
			"active_page": "monitor",
			"players": players,
			"available_devices": available_devices,
		},
		status_code=status.HTTP_200_OK,
	)
