
class ReceiverError(Exception):
    """Base class for receiver-related domain errors."""


class ReceiverValidationError(ReceiverError):
    """Raised when receiver data fails model validation."""

    def __init__(self, messages: dict[str, str]):
        self.messages = messages
        super().__init__(messages)


class ReceiverConflictError(ReceiverError):
    """Raised when receiver data violates uniqueness constraints."""

    def __init__(self, messages: dict[str, str] | None = None):
        resolved = messages or {
            "conflict": "Receiver with the same name, IP address, or MAC address already exists.",
        }
        self.messages = resolved
        super().__init__(messages)


class DeviceError(Exception):
    """Base class for device-related domain errors."""


class DeviceValidationError(DeviceError):
    """Raised when device data fails model validation."""

    def __init__(self, messages: dict[str, str]):
        self.messages = messages
        super().__init__(messages)


class DeviceConflictError(DeviceError):
    """Raised when device data violates uniqueness constraints."""

    def __init__(self, messages: dict[str, str] | None = None):
        resolved = messages or {
            "conflict": "Device with the same name already exists.",
        }
        self.messages = resolved
        super().__init__(messages)


class PlayerError(Exception):
    """Base class for player-related domain errors."""


class PlayerValidationError(PlayerError):
    """Raised when player data fails model validation."""

    def __init__(self, messages: dict[str, str]):
        self.messages = messages
        super().__init__(messages)


class PlayerConflictError(PlayerError):
    """Raised when player data violates uniqueness constraints."""

    def __init__(self, messages: dict[str, str] | None = None):
        resolved = messages or {
            "conflict": "Player with the same name already exists.",
        }
        self.messages = resolved
        super().__init__(messages)
