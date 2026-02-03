from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.crud import device_crud, player_crud
from app.db import get_session

player_buttons_router = APIRouter(prefix="/ui/player")
templates = Jinja2Templates(directory="app/templates")


@player_buttons_router.post("/add", response_class=HTMLResponse, name="add_player_button")
def add_player_button(
    request: Request,
    session: Session = Depends(get_session),  # noqa: ARG001
):
    return templates.TemplateResponse(
        "partials/player_row.html",
        {
            "request": request,
            "mode": "new",
        },
        status_code=status.HTTP_200_OK,
    )


@player_buttons_router.post(
    "/{player_id}/edit",
    response_class=HTMLResponse,
    name="edit_player_button",
)
def edit_player_button(
    request: Request,
    player_id: int,
    session: Session = Depends(get_session),
):
    player = player_crud.get_player(session, player_id)
    available_devices = [
        device for device in device_crud.list_devices(session) if device.player_id is None
    ]
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


@player_buttons_router.post(
    "/{player_id}/cancel",
    response_class=HTMLResponse,
    name="cancel_player_button",
)
def cancel_player_button(
    request: Request,
    player_id: int,
    session: Session = Depends(get_session),
):
    player = player_crud.get_player(session, player_id)
    return templates.TemplateResponse(
        "partials/player_row.html",
        {
            "request": request,
            "mode": "monitor",
            "player": player,
        },
        status_code=status.HTTP_200_OK,
    )
