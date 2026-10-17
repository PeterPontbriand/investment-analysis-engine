"""The runtime agent rules shipped with the package."""

from investment_analysis_engine.core.package_root import PACKAGE_ROOT

RUNTIME_RULES_PATH = PACKAGE_ROOT / "orchestrator" / "RUNTIME_AGENTS.md"


def load_runtime_rules() -> str:
    """Return the text of ``RUNTIME_AGENTS.md``, stripped.

    Raises:
        OSError: If the file shipped with the package is missing or cannot be read.
    """
    return RUNTIME_RULES_PATH.read_text(encoding="utf-8").strip()
