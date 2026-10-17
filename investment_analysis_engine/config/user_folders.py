"""The per-user folders the application uses, and how an environment variable overrides each.

The settings folder holds the ``.env`` file and the user's strategy settings; the data folder holds the database; the
log folder holds the application log and the trajectory telemetry. Resolving a folder never creates it.
"""

from collections.abc import Mapping
from pathlib import Path

import platformdirs

from investment_analysis_engine.config.paths import is_windows, require_absolute_path
from investment_analysis_engine.core.settings_error import SettingsEnvironmentError

APPLICATION_FOLDER_NAME = "investment-analysis-engine"
CONFIG_DIR_VARIABLE = "IAN_CONFIG_DIR"


def user_settings_folder() -> Path:
    """Return the per-user settings folder: the roaming application-data folder on Windows."""
    return Path(platformdirs.user_config_dir(APPLICATION_FOLDER_NAME, appauthor=False, roaming=True))


def user_data_folder() -> Path:
    """Return the per-user data folder, which holds the database."""
    return Path(platformdirs.user_data_dir(APPLICATION_FOLDER_NAME, appauthor=False))


def user_log_folder() -> Path:
    """Return the per-user log folder, which holds the application log and the trajectory telemetry."""
    return Path(platformdirs.user_log_dir(APPLICATION_FOLDER_NAME, appauthor=False))


def resolve_settings_folder(environ: Mapping[str, str]) -> Path:
    """Return the settings folder: ``IAN_CONFIG_DIR`` from the process environment, else the per-user folder.

    The variable is read in any letter case and an empty value counts as unset, as for every engine setting. It is
    read here, before the ``.env`` file in the folder it names can be located.

    Raises:
        SettingsEnvironmentError: If the variable is set to a path that is not absolute.
    """
    for key in sorted(environ):
        if key.upper() == CONFIG_DIR_VARIABLE and environ[key]:
            try:
                require_absolute_path(environ[key], name=CONFIG_DIR_VARIABLE, windows=is_windows())
            except ValueError as error:
                raise SettingsEnvironmentError(str(error)) from None
            return Path(environ[key]).resolve()
    return user_settings_folder()
