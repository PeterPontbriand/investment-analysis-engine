"""The repository root: the one place that counts folders up from a source file."""

from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
