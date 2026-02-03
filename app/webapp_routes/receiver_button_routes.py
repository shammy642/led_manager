from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from app.crud import device_crud, receiver_crud
from app.db import get_session
from app.services.dnsmasq_manager import DnsmasqManager, DnsmasqCommandError

receiver_buttons_router = APIRouter()
receiver_buttons_router.prefix = "/ui/receiver"
templates = Jinja2Templates(directory="app/templates")

@receiver_buttons_router.post("/{receiver_id}/edit", response_class=HTMLResponse, name="edit_receiver_button")
def edit_receiver_button(
    request: Request,
    receiver_id: int,
    session: Session = Depends(get_session)
):
    receiver = receiver_crud.get_receiver(session, receiver_id)
    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "partials/receiver_row.html",
        {
            "request": request,
            "mode": "edit",
            "receiver": receiver,
            "devices": devices,
        },
        status_code=status.HTTP_200_OK,
    )

@receiver_buttons_router.post("/{receiver_id}/cancel", response_class=HTMLResponse, name="cancel_receiver_button")
def cancel_receiver_button(
    request: Request,
    receiver_id: int,
    session: Session = Depends(get_session)
):
    receiver = receiver_crud.get_receiver(session, receiver_id)
    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "partials/receiver_row.html",
        {
            "request": request,
            "mode": "view",
            "receiver": receiver,
            "devices": devices,
        },
        status_code=status.HTTP_200_OK,
    )

@receiver_buttons_router.post("/cancel", response_class=HTMLResponse, name="cancel_new_receiver")
def cancel_receiver_button(
    request: Request,
    receiver_id: int,
    session: Session = Depends(get_session)
):
    receiver = receiver_crud.get_receiver(session, receiver_id)
    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "partials/receiver_row.html",
        {
            "request": request,
            "receiver": receiver,
            "devices": devices,
        },
        status_code=status.HTTP_200_OK,
    )

@receiver_buttons_router.post("/add", response_class=HTMLResponse, name="add_receiver_button")
def add_receiver_button(
    request: Request,
    session: Session = Depends(get_session),
):
    devices = device_crud.list_devices(session)
    return templates.TemplateResponse(
        "partials/receiver_row.html",
        {
            "request": request,
            "mode": "new",
            "devices": devices,
        },
        status_code=status.HTTP_200_OK,
    )


@receiver_buttons_router.post("/apply", response_class=HTMLResponse, name="apply_receiver_changes")
def apply_receiver_changes(
    request: Request,
    session: Session = Depends(get_session),
    manager: DnsmasqManager | None = Depends(DnsmasqManager.from_env),
):
    if manager is None:
        return templates.TemplateResponse(
            "partials/apply_changes_status.html",
            {
                "request": request,
                "status": "error",
                "message": "DNSMasq is not configured. Set DNSMASQ_DHCP_CONF_PATH to the dhcp.conf file path.",
            },
            status_code=status.HTTP_200_OK,
        )

    receivers = receiver_crud.list_receivers(session, sort="name")
    reservations = [
        {"name": receiver.name, "ip_address": receiver.ip_address, "mac_address": receiver.mac_address}
        for receiver in receivers
    ]

    try:
        manager.apply(reservations)
    except DnsmasqCommandError as exc:
        return templates.TemplateResponse(
            "partials/apply_changes_status.html",
            {
                "request": request,
                "status": "error",
                "message": f"DNSMasq command failed: {' '.join(exc.command)}",
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "partials/apply_changes_status.html",
            {
                "request": request,
                "status": "error",
                "message": f"Failed to apply changes: {exc}",
            },
            status_code=status.HTTP_200_OK,
        )

    return templates.TemplateResponse(
        "partials/apply_changes_status.html",
        {
            "request": request,
            "status": "success",
            "message": f"Applied {len(reservations)} reservations.",
        },
        status_code=status.HTTP_200_OK,
    )