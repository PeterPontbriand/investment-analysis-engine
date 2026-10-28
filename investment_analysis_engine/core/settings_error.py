"""The error raised when the process environment cannot be mapped onto the engine settings."""


class SettingsEnvironmentError(ValueError):
    """Raised when the process environment cannot be mapped onto the engine settings unambiguously.

    The message is one sentence that names the offending variable or variables, so a command-line entry point
    can print it as is.
    """


class ComponentSettingsError(ValueError):
    """Raised when a component's settings file is missing, is not valid TOML or does not satisfy its settings model.

    A component is a strategy or a provider.

    The message is one sentence that names the file relative to the project root and, when a key is at fault, the
    key and the rule it broke, never the value, so a command-line entry point can print it as is.
    """
