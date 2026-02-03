from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.crud import device_crud
from app.db import get_session
from app.models.sort import DeviceSort
from app.utils.exceptions import DeviceConflictError, DeviceValidationError

devices_router = APIRouter(prefix="/devices")
templates = Jinja2Templates(directory="app/templates")


@devices_router.get("/", response_class=HTMLResponse, name="read_devices")
def read_devices(
    request: Request,
    sort: DeviceSort = DeviceSort.newest,
    session: Session = Depends(get_session),
):
    devices = device_crud.list_devices(session, sort=sort.value)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "devices",
            "devices": devices,
            "devices_sort": sort.value,
        },
        status_code=status.HTTP_200_OK,
    )


@devices_router.post("/", name="create_device")
def create_device_route(
    request: Request,
    name: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        device_crud.create_device(session, name=name)
    except (DeviceValidationError, DeviceConflictError) as exc:
        response = templates.TemplateResponse(
            "partials/device_row.html",
            {
                "request": request,
                "mode": "new",
                "create_errors": {
                    "name": exc.messages.get("name"),
                },
                "create_form": {
                    "name": name,
                },
            },
        )
        response.headers["HX-Retarget"] = "#device-new"
        response.headers["HX-Reswap"] = "outerHTML"
        return response

    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "devices",
            "devices": devices,
        },
        status_code=status.HTTP_200_OK,
    )


@devices_router.post("/{device_id}/update", name="update_device")
async def update_device_route(
    request: Request,
    device_id: int,
    name: str = Form(...),
    player_id: str | None = Form(None),
    session: Session = Depends(get_session),
):
    try:
        form_data = await request.form()
        player_id_is_present = "player_id" in form_data

        parsed_player_id: int | None
        if not player_id_is_present:
            device = device_crud.get_device(session, device_id)
            parsed_player_id = device.player_id if device is not None else None
        elif player_id is None or not player_id.strip():
            parsed_player_id = None
        else:
            try:
                parsed_player_id = int(player_id)
            except ValueError as exc:
                raise DeviceValidationError({"player_id": "Invalid player selection."}) from exc

        device_crud.update_device(session, device_id, name=name, player_id=parsed_player_id)
    except (DeviceValidationError, DeviceConflictError) as exc:
        device = device_crud.get_device(session, device_id)
        response = templates.TemplateResponse(
            "partials/device_row.html",
            {
                "request": request,
                "mode": "edit",
                "device": device,
                "update_errors": {
                    device_id: [
                        exc.messages.get("name"),
                        exc.messages.get("player_id"),
                    ]
                },
            },
        )
        response.headers["HX-Retarget"] = f"#device-{device_id}"
        response.headers["HX-Reswap"] = "outerHTML"
        return response

    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "devices",
            "devices": devices,
        },
        status_code=status.HTTP_200_OK,
    )


@devices_router.post("/{device_id}/delete", name="delete_device")
def delete_device_route(
    request: Request,
    device_id: int,
    session: Session = Depends(get_session),
):
    device_crud.delete_device(session, device_id)
    return RedirectResponse(
        url=request.url_for("read_devices"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
