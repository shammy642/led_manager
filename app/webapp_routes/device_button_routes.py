from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.crud import device_crud
from app.db import get_session

device_buttons_router = APIRouter()
device_buttons_router.prefix = "/ui/device"
templates = Jinja2Templates(directory="app/templates")


@device_buttons_router.post("/{device_id}/edit", response_class=HTMLResponse, name="edit_device_button")
def edit_device_button(
    request: Request,
    device_id: int,
    session: Session = Depends(get_session),
):
    device = device_crud.get_device(session, device_id)
    return templates.TemplateResponse(
        "partials/device_row.html",
        {
            "request": request,
            "mode": "edit",
            "device": device,
        },
        status_code=status.HTTP_200_OK,
    )


@device_buttons_router.post("/{device_id}/cancel", response_class=HTMLResponse, name="cancel_device_button")
def cancel_device_button(
    request: Request,
    device_id: int,
    session: Session = Depends(get_session),
):
    device = device_crud.get_device(session, device_id)
    return templates.TemplateResponse(
        "partials/device_row.html",
        {
            "request": request,
            "mode": "view",
            "device": device,
        },
        status_code=status.HTTP_200_OK,
    )


@device_buttons_router.post("/add", response_class=HTMLResponse, name="add_device_button")
def add_device_button(
    request: Request,
    session: Session = Depends(get_session),
):
    return templates.TemplateResponse(
        "partials/device_row.html",
        {
            "request": request,
            "mode": "new",
        },
        status_code=status.HTTP_200_OK,
    )
