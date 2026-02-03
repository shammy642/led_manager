# Copilot instructions (ip_address_manager)

## Project overview
- FastAPI server renders HTML via Jinja2 + HTMX partial swaps (not a JSON API).
- Data layer is SQLModel (SQLAlchemy) models + CRUD functions; routes are thin.

## Key entry points
- App wiring: [app/app.py](../app/app.py)
  - mounts static at `/static` from `app/static`
  - includes routers: [app/webapp_routes/receiver_routes.py](../app/webapp_routes/receiver_routes.py) and [app/webapp_routes/button_routes.py](../app/webapp_routes/button_routes.py)
- Database/session: [app/db.py](../app/db.py)
  - `get_session()` is injected with `Depends(get_session)`
  - `create_db_and_tables()` is called at import time in `app/app.py`

## Web UI flow (HTMX)
- `GET /` renders [app/templates/index.html](../app/templates/index.html) which includes the table partial.
- “UI button” routes live under `/ui/receiver/*` and return only a row partial:
  - example: `POST /ui/receiver/{id}/edit` returns [app/templates/partials/receiver_row.html](../app/templates/partials/receiver_row.html) with `mode='edit'`.
- Create/update error handling uses HTMX response headers:
  - on form errors, routes return `partials/receiver_row.html` and set `HX-Retarget`/`HX-Reswap` (see [app/webapp_routes/receiver_routes.py](../app/webapp_routes/receiver_routes.py)).

## Domain/data conventions
- Models are SQLModel tables with Pydantic validation and assignment validation:
  - Receiver model: [app/models/receiver.py](../app/models/receiver.py)
    - normalizes `ip_address` via `ipaddress.ip_address()`
    - normalizes `mac_address` to `AA:BB:CC:DD:EE:FF`
- CRUD functions raise domain errors instead of returning error tuples:
  - [app/crud/receiver_crud.py](../app/crud/receiver_crud.py)
    - `ReceiverValidationError` wraps formatted Pydantic `ValidationError` messages
    - `ReceiverConflictError` maps unique conflicts to field keys (`name`, `ip_address`, `mac_address`)
  - Error types: [app/utils/exceptions.py](../app/utils/exceptions.py)
  - Validation formatting helper: [app/utils/formatting.py](../app/utils/formatting.py)

## Tests (how to extend)
- Tests use in-memory SQLite + `StaticPool` and override `get_session` on the app:
  - routes: [tests/routes/test_receiver_routes.py](../tests/routes/test_receiver_routes.py)
  - CRUD: [tests/crud/test_receiver_crud.py](../tests/crud/test_receiver_crud.py)
- When adding a new route, mirror this pattern:
  - override `app.dependency_overrides[get_session]`
  - assert HTMX headers (`HX-Retarget`, `HX-Reswap`) when returning partials

## Dev workflows
- Install deps: `poetry install`
- Run dev server (recommended): `poetry run uvicorn app.app:app --reload`
  - VS Code debug config already targets this module/args: [.vscode/launch.json](../.vscode/launch.json)
- Run tests: `poetry run pytest`

## Test requirements
- When adding or modifying files, make sure that tests are added.
- 100% test coverage is required.

## Coding Standards
- Follow existing code style and patterns.
- Use type annotations throughout.
- Only use docstrings if the function is non-obvious for a senior level engineer; prefer expressive names and small functions.
- Use object oriented design where appropriate, but prefer simple functions where possible.
- Clear separation of concerns: routes should be thin and delegate to CRUD and utility functions.
- Use Pydantic/SQLModel validation features instead of manual validation where possible.
- Use HTMX features (response headers, swapping, targeting) instead of manual DOM manipulation via JavaScript where possible.

## Common pitfalls in this repo
- The default DB URL in [app/db.py](../app/db.py) points at Postgres on `127.0.0.1:5432`.
  - Tests don’t use it (they override session + engine), but running the app requires Postgres running and a database named `ip_address_manager`.
- Template partials rely on `mode` (`view`/`edit`/`new`) and `receiver_id` set in [app/templates/partials/receiver_row.html](../app/templates/partials/receiver_row.html); preserve these when changing UI behavior.
