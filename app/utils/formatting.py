import re
from pydantic import ValidationError


def to_snake_case(text: str) -> str:
    """
    Remove all special characters, strip the output, and turn it into snake_case.
    """
    # Remove special characters (keeping alphanumerics and whitespace/hyphens for word boundaries)
    clean_text = re.sub(r'[^\w\s-]', '', text)
    # Strip, replace spaces/hyphens with underscores, and make lowercase
    return re.sub(r'[-\s]+', '_', clean_text.strip()).lower()


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

