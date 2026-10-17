"""The package root: the one place that counts folders up from a source file.

``PACKAGE_ROOT`` is the folder of the ``investment_analysis_engine`` package. Every other module that needs a path
inside the package imports it. The package never names the folder that contains it.
"""

from pathlib import Path
from typing import Final

PACKAGE_ROOT: Final = Path(__file__).resolve().parents[1]
