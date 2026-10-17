"""The generic loader for a strategy's settings.

A strategy's shipped defaults live in ``settings.toml`` beside the module that defines its settings model. A user may
override any subset of the keys in ``<settings folder>/strategies/<alias>.toml``. This module merges the two per key
and validates the result into the settings model the caller names; it knows no strategy. A strategy's settings are
read once per process.
"""

import sys
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from investment_analysis_engine.core.settings_error import StrategySettingsError

_SHIPPED_FILE_NAME = "settings.toml"
_USER_FOLDER_NAME = "strategies"

_cache: dict[tuple[str, type[BaseModel], Path], BaseModel] = {}


def clear_strategy_settings_cache() -> None:
    """Forget every loaded settings object, so the next load reads the files again; tests use it to isolate."""
    _cache.clear()


def shipped_settings_path(model: type[BaseModel]) -> Path:
    """Return the path of the shipped ``settings.toml``, which sits in the folder of the module defining ``model``."""
    module_file = getattr(sys.modules[model.__module__], "__file__", None)
    if module_file is None:
        raise TypeError(f"The module {model.__module__} of {model.__name__} has no file.")
    return Path(module_file).resolve().parent / _SHIPPED_FILE_NAME


def user_settings_path(alias: str, settings_folder: Path) -> Path:
    """Return the path of the user's override file for the strategy ``alias``; the file may not exist."""
    return settings_folder / _USER_FOLDER_NAME / f"{alias}.toml"


def load_strategy_settings[T: BaseModel](alias: str, model: type[T], settings_folder: Path) -> T:
    """Load the shipped defaults of ``model``, apply the user's keys over them and validate the result.

    Args:
        alias: The strategy's alias, which names the user's file.
        model: The strategy's settings model; its shipped defaults are ``settings.toml`` beside its module.
        settings_folder: The user's settings folder, which may hold ``strategies/<alias>.toml``.

    Returns:
        The validated settings, the same object on every call with the same arguments.

    Raises:
        StrategySettingsError: If the shipped file is missing, either file is not valid TOML, or the merged
            values do not satisfy ``model``. The message names, as a full path, the file the offending key came
            from and, when a key is at fault, the key and the rule it broke; it never includes the value. A
            missing user file is normal.
    """
    key = (alias, model, settings_folder)
    cached = _cache.get(key)
    if cached is not None:
        if not isinstance(cached, model):
            raise TypeError(f"The cached settings for {alias} are not a {model.__name__}.")
        return cached
    shipped_path = shipped_settings_path(model)
    user_path = user_settings_path(alias, settings_folder)
    shipped = _read(shipped_path)
    if shipped is None:
        raise StrategySettingsError(f"Settings file {shipped_path} is missing.")
    user = _read(user_path) or {}
    origins = {name: (user_path if name in user else shipped_path) for name in shipped | user}
    try:
        loaded = model.model_validate(shipped | user)
    except ValidationError as error:
        raise StrategySettingsError(_describe(error, origins, user_path if user else shipped_path)) from None
    _cache[key] = loaded
    return loaded


def _read(path: Path) -> dict[str, Any] | None:
    """Return the keys of the TOML file ``path``, or ``None`` when the file does not exist."""
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return None
    except tomllib.TOMLDecodeError as error:
        raise StrategySettingsError(f"Settings file {path} is not valid TOML: {str(error).rstrip('.')}.") from None


def _describe(error: ValidationError, origins: dict[str, Path], whole_model_file: Path) -> str:
    """Describe the first invalid key in a message that names its file and the key, and never the value."""
    first = error.errors(include_input=False, include_url=False, include_context=False)[0]
    rule = first["msg"].removeprefix("Value error, ").rstrip(".")
    location = ".".join(str(part) for part in first["loc"])
    if not location:
        return f"Settings file {whole_model_file} is invalid: {rule}."
    origin = origins.get(str(first["loc"][0]), whole_model_file)
    return f"Settings file {origin} is invalid: {location}: {rule}."
