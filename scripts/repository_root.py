"""The repository root, for tests and scripts; the installed package never imports this module."""

from pathlib import Path
from typing import Final

from investment_analysis_engine.core.package_root import PACKAGE_ROOT

REPOSITORY_ROOT: Final[Path] = PACKAGE_ROOT.parent
