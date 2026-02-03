import pytest

from app.utils.exceptions import (
    DeviceConflictError,
    DeviceValidationError,
    PlayerConflictError,
    PlayerValidationError,
    ReceiverConflictError,
    ReceiverValidationError,
)


def test_receiver_validation_error_messages_and_str():
    messages = {"name": "Name is required", "ip_address": "IP address is invalid"}

    error = ReceiverValidationError(messages)

    assert error.messages == messages


def test_device_validation_error_messages_and_str():
    messages = {"name": "Name is required"}

    error = DeviceValidationError(messages)

    assert error.messages == messages


def test_player_validation_error_messages_and_str():
    messages = {"name": "Name is required"}

    error = PlayerValidationError(messages)

    assert error.messages == messages


@pytest.mark.parametrize(
    "messages, expected",
    [
        (None, {
            "conflict": "Receiver with the same name, IP address, or MAC address already exists.",
        }),
        ({"name": "Duplicate receiver"}, {"name": "Duplicate receiver"}),
    ],
)
def test_receiver_conflict_error_messages_and_str(messages, expected):
    error = ReceiverConflictError(messages)

    assert error.messages == expected


@pytest.mark.parametrize(
    "messages, expected",
    [
        (None, {
            "conflict": "Device with the same name already exists.",
        }),
        ({"name": "Duplicate device"}, {"name": "Duplicate device"}),
    ],
)
def test_device_conflict_error_messages_and_str(messages, expected):
    error = DeviceConflictError(messages)

    assert error.messages == expected


@pytest.mark.parametrize(
    "messages, expected",
    [
        (None, {
            "conflict": "Player with the same name already exists.",
        }),
        ({"name": "Duplicate player"}, {"name": "Duplicate player"}),
    ],
)
def test_player_conflict_error_messages_and_str(messages, expected):
    error = PlayerConflictError(messages)

    assert error.messages == expected
