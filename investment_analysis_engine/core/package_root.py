"""The package root: the one place that counts folders up from a source file.

``PACKAGE_ROOT`` is the folder of the ``investment_analysis_engine`` package. Every other module that needs a path
inside the package imports it.

The package names the folder that contains it in one place only, ``INSTALLATION_FOLDER``, so that ``ian about`` can
report which installation is running. That folder is the project folder of a source checkout, which ``uv`` installs in
editable mode, and it is ``None`` when the package was installed from a wheel, whose parent folder is a shared
``site-packages`` folder and not an installation.
"""

from pathlib import Path
from typing import Final

PACKAGE_ROOT: Final = Path(__file__).resolve().parents[1]


def installation_folder_of(package_root: Path) -> Path | None:
    """Return the folder holding ``package_root`` when it also holds ``pyproject.toml``, otherwise ``None``."""
    folder = package_root.parent
    return folder if (folder / "pyproject.toml").is_file() else None


INSTALLATION_FOLDER: Final[Path | None] = installation_folder_of(PACKAGE_ROOT)
"""The folder of the source checkout the code runs from, or ``None`` when it was installed from a wheel."""
