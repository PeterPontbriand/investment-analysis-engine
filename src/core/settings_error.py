"""The error raised when the process environment cannot be mapped onto the engine settings."""


class SettingsEnvironmentError(ValueError):
    """Raised when the process environment cannot be mapped onto the engine settings unambiguously.

    The message is one sentence that names the offending variable or variables, so a command-line entry point
    can print it as is.
    """
