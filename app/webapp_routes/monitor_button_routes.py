from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.monitor_hub import get_monitor_hub

monitor_buttons_router = APIRouter(prefix="/monitor")
templates = Jinja2Templates(directory="app/templates")


@monitor_buttons_router.get(
	"/toggle",
	response_class=HTMLResponse,
	name="read_monitor_toggle",
)
async def read_monitor_toggle(request: Request):
	hub = get_monitor_hub()
	return templates.TemplateResponse(
		"buttons/monitor_toggle_button.html",
		{
			"request": request,
			"monitoring_active": hub.monitoring_active,
		},
		status_code=status.HTTP_200_OK,
	)


@monitor_buttons_router.post("/stop", response_class=HTMLResponse, name="stop_monitoring")
async def stop_monitoring(request: Request):
	hub = get_monitor_hub()
	await hub.set_monitoring_active(False)
	await hub.broadcast_monitoring_state()
	return templates.TemplateResponse(
		"buttons/monitor_toggle_button.html",
		{
			"request": request,
			"monitoring_active": hub.monitoring_active,
		},
		status_code=status.HTTP_200_OK,
	)


@monitor_buttons_router.post("/start", response_class=HTMLResponse, name="start_monitoring")
async def start_monitoring(request: Request):
	hub = get_monitor_hub()
	await hub.set_monitoring_active(True)
	await hub.broadcast_monitoring_state()
	return templates.TemplateResponse(
		"buttons/monitor_toggle_button.html",
		{
			"request": request,
			"monitoring_active": hub.monitoring_active,
		},
		status_code=status.HTTP_200_OK,
	)
