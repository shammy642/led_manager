from pydantic import ValidationError


def format_validation_errors(exc: ValidationError) -> dict[str, str]:
    """Return readable messages for each path in a Pydantic validation error."""
    messages: dict[str, str] = {}
    for error in exc.errors():
        path = " -> ".join(str(part) for part in error.get("loc", ()))
        if path:
            messages[path] = error["msg"]
        else:
            messages["root"] = error["msg"]
    return messages 
