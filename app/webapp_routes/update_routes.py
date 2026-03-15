from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.update_manager import UpdateManager

update_router = APIRouter(prefix="/update")
templates = Jinja2Templates(directory="app/templates")


@update_router.get("/", response_class=HTMLResponse, name="read_update")
def read_update(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "active_page": "update"},
        status_code=status.HTTP_200_OK,
    )


@update_router.post("/", response_class=HTMLResponse, name="run_update")
def run_update_route(
    request: Request,
    background_tasks: BackgroundTasks,
    ssid: str = Form(...),
    password: str = Form(...),
    update_manager: UpdateManager = Depends(UpdateManager.from_env),
) -> HTMLResponse:
    result = update_manager.run_update(ssid, password)

    if result.success:
        background_tasks.add_task(update_manager.restart_service)

    response = templates.TemplateResponse(
        "partials/update_status.html",
        {"request": request, "result": result},
        status_code=status.HTTP_200_OK,
    )
    response.headers["HX-Retarget"] = "#update-status"
    response.headers["HX-Reswap"] = "outerHTML"
    return response
