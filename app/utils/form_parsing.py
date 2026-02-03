from app.utils.exceptions import ReceiverValidationError


def parse_optional_int_field(
    raw_value: str | None,
    *,
    field_name: str,
    invalid_message: str,
) -> int | None:
    if raw_value is None:
        return None

    cleaned = raw_value.strip()
    if not cleaned:
        return None

    try:
        return int(cleaned)
    except ValueError as exc:
        raise ReceiverValidationError({field_name: invalid_message}) from exc
