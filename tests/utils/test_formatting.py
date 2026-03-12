import pytest

from pydantic import BaseModel, ValidationError

from app.utils.formatting import format_validation_errors, to_snake_case


class SampleModel(BaseModel):
    name: str
    tags: list[int]


def test_to_snake_case_removes_special_characters():
    assert to_snake_case("Hello @ World!") == "hello_world"
    assert to_snake_case("Hello@World") == "helloworld"

def test_to_snake_case_strips_whitespace():
    assert to_snake_case("  leading and trailing  ") == "leading_and_trailing"

def test_to_snake_case_handles_hyphens():
    assert to_snake_case("some-mixed_string-here") == "some_mixed_string_here"

def test_to_snake_case_handles_empty_string():
    assert to_snake_case("") == ""

def test_to_snake_case_lowercases():
    assert to_snake_case("UPPERCASE") == "uppercase"


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
