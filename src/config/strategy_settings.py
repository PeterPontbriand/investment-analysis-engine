"""The generic loader for a strategy's settings file.

A strategy's editable defaults live in ``config/strategies/<alias>.toml``. This module reads such a file and
validates it into the settings model the caller names; it knows no strategy. A file is read once per process.
"""

import tomllib
from pathlib import Path

from pydantic import BaseModel, ValidationError

from src.core.settings_error import StrategySettingsError

_cache: dict[tuple[str, type[BaseModel], Path], BaseModel] = {}


def clear_strategy_settings_cache() -> None:
    """Forget every loaded settings object, so the next load reads the files again; tests use it to isolate."""
    _cache.clear()


def load_strategy_settings[T: BaseModel](alias: str, model: type[T], directory: Path) -> T:
    """Load and validate ``<directory>/<alias>.toml`` into ``model``, once per process.

    Args:
        alias: The strategy's alias, which names the file.
        model: The strategy's settings model.
        directory: The folder that holds the settings files.

    Returns:
        The validated settings, the same object on every call with the same arguments.

    Raises:
        StrategySettingsError: If the file is missing, is not valid TOML or does not satisfy ``model``. The
            message names the file relative to the project root and, when a key is at fault, the key and the
            rule it broke; it never includes the value.
    """
    key = (alias, model, directory)
    cached = _cache.get(key)
    if cached is not None:
        if not isinstance(cached, model):
            raise TypeError(f"The cached settings for {alias} are not a {model.__name__}.")
        return cached
    shown = f"config/strategies/{alias}.toml"
    try:
        with (directory / f"{alias}.toml").open("rb") as handle:
            values = tomllib.load(handle)
    except FileNotFoundError:
        raise StrategySettingsError(f"Settings file {shown} is missing.") from None
    except tomllib.TOMLDecodeError as error:
        raise StrategySettingsError(f"Settings file {shown} is not valid TOML: {str(error).rstrip('.')}.") from None
    try:
        loaded = model.model_validate(values)
    except ValidationError as error:
        raise StrategySettingsError(_describe(shown, error)) from None
    _cache[key] = loaded
    return loaded


def _describe(shown: str, error: ValidationError) -> str:
    """Describe the first invalid key in a message that names the file and key and never the value."""
    first = error.errors(include_input=False, include_url=False, include_context=False)[0]
    rule = first["msg"].removeprefix("Value error, ").rstrip(".")
    location = ".".join(str(part) for part in first["loc"])
    if not location:
        return f"Settings file {shown} is invalid: {rule}."
    return f"Settings file {shown} is invalid: {location}: {rule}."
