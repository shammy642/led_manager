import pytest

from pydantic import BaseModel, ValidationError

from app.utils.formatting import format_validation_errors


class SampleModel(BaseModel):
    name: str
    tags: list[int]


def test_format_validation_errors_returns_human_readable_messages():
    with pytest.raises(ValidationError) as exc_info:
        SampleModel.model_validate({"name": 123, "tags": ["one", 2]})

    messages = format_validation_errors(exc_info.value)

    assert any("name" in key for key in messages.keys())
    assert any("tags" in key for key in messages.keys())


def test_format_validation_errors_falls_back_to_exception_string():
    exc = ValidationError.from_exception_data("SampleModel", [])

    messages = format_validation_errors(exc)

    assert messages == {}
