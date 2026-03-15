from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.db import create_db_and_tables
from app.webapp_routes.receiver_routes import receivers_router
from app.webapp_routes.receiver_button_routes import receiver_buttons_router
from app.webapp_routes.device_routes import devices_router
from app.webapp_routes.device_button_routes import device_buttons_router
from app.webapp_routes.monitor_routes import monitor_router
from app.webapp_routes.monitor_button_routes import monitor_buttons_router
from app.webapp_routes.monitor_ws_routes import monitor_ws_router
from app.webapp_routes.player_button_routes import player_buttons_router
from app.webapp_routes.update_routes import update_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(receivers_router)
app.include_router(receiver_buttons_router)
app.include_router(devices_router)
app.include_router(device_buttons_router)
app.include_router(player_buttons_router)
app.include_router(monitor_router)
app.include_router(monitor_buttons_router)
app.include_router(monitor_ws_router)
app.include_router(update_router)


@app.get("/")
def read_root(request: Request):
    return RedirectResponse(url=request.url_for("read_monitor"))
