from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.crud import device_crud, receiver_crud
from app.db import get_session
from app.models.sort import ReceiverSort
from app.utils.exceptions import ReceiverConflictError, ReceiverValidationError
from app.utils.form_parsing import parse_optional_int_field

receivers_router = APIRouter(prefix="/receivers")
templates = Jinja2Templates(directory="app/templates")

@receivers_router.get("/", response_class=HTMLResponse, name="read_receivers")
def read_receivers(
    request: Request,
    sort: ReceiverSort = ReceiverSort.newest,
    session: Session = Depends(get_session),
):
    receivers = receiver_crud.list_receivers(session, sort=sort.value)
    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "receivers",
            "receivers": receivers,
            "devices": devices,
            "receivers_sort": sort.value,
        },
        status_code=status.HTTP_200_OK,
    )


@receivers_router.post("/", name="create_receiver")
def create_receiver_route(
    request: Request,
    name: str = Form(...),
    ip_address: str = Form(...),
    mac_address: str = Form(...),
    device_id: str | None = Form(None),
    session: Session = Depends(get_session),
):
    try:
        parsed_device_id = parse_optional_int_field(
            device_id,
            field_name="device_id",
            invalid_message="Invalid device selection.",
        )
        receiver_crud.create_receiver(
            session,
            name=name,
            ip_address=ip_address,
            mac_address=mac_address,
            device_id=parsed_device_id,
        )
    except (ReceiverValidationError, ReceiverConflictError) as exc:
        devices = device_crud.list_devices(session)
        response = templates.TemplateResponse(
            "partials/receiver_row.html",
            {
                "request": request,
                "mode": "new",
                "devices": devices,
                "create_errors": {
                    "name": exc.messages.get("name"),
                    "ip_address": exc.messages.get("ip_address"),
                    "mac_address": exc.messages.get("mac_address"),
                    "device_id": exc.messages.get("device_id"),
                },
                "create_form": {
                    "name": name,
                    "ip_address": ip_address,
                    "mac_address": mac_address,
                    "device_id": device_id,
                },
            },
        )

        response.headers["HX-Retarget"] = "#receiver-new"
        response.headers["HX-Reswap"] = "outerHTML"
        return response

    receivers = receiver_crud.list_receivers(session)
    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "receivers",
            "receivers": receivers,
            "devices": devices,
        },
        status_code=status.HTTP_200_OK,
    )
    


@receivers_router.post("/{receiver_id}/update", name="update_receiver")
def update_receiver_route(
    request: Request,
    receiver_id: int,
    name: str = Form(...),
    ip_address: str = Form(...),
    mac_address: str = Form(...),
    device_id: str | None = Form(None),
    session: Session = Depends(get_session),
):
    try:
        parsed_device_id = parse_optional_int_field(
            device_id,
            field_name="device_id",
            invalid_message="Invalid device selection.",
        )
        receiver_crud.update_receiver(
            session,
            receiver_id,
            name=name,
            ip_address=ip_address,
            mac_address=mac_address,
            device_id=parsed_device_id,
        )
    except (ReceiverValidationError, ReceiverConflictError) as exc:
        receiver = receiver_crud.get_receiver(session, receiver_id)
        devices = device_crud.list_devices(session)
        response = templates.TemplateResponse(
            "partials/receiver_row.html",
            {
                "request": request,
                "mode": "edit",
                "receiver": receiver,
                "devices": devices,
                "update_errors": {
                    receiver_id: [
                        exc.messages.get("name"),
                        exc.messages.get("ip_address"),
                        exc.messages.get("mac_address"),
                        exc.messages.get("device_id"),
                    ]
                },
            },
        )

        response.headers["HX-Retarget"] = f"#receiver-{receiver_id}"
        response.headers["HX-Reswap"] = "outerHTML"
        return response
    
    receivers = receiver_crud.list_receivers(session)
    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "receivers",
            "receivers": receivers,
            "devices": devices,
        },
        status_code=status.HTTP_200_OK,
    )


@receivers_router.post("/{receiver_id}/delete", name="delete_receiver")
def delete_receiver_route(
    request: Request,
    receiver_id: int,
    session: Session = Depends(get_session),
):
    receiver_crud.delete_receiver(session, receiver_id)
    return RedirectResponse(
        url=request.url_for("read_receivers"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
