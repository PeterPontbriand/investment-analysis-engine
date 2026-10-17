"""The package and repository roots: the one place that counts folders up from a source file.

``PACKAGE_ROOT`` is the folder of the ``investment_analysis_engine`` package; ``REPOSITORY_ROOT`` is the folder
that holds it, the project's ``pyproject.toml`` and the other top-level folders. Every other module imports one of them.
"""

from pathlib import Path
from typing import Final

PACKAGE_ROOT: Final = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT: Final = PACKAGE_ROOT.parent
