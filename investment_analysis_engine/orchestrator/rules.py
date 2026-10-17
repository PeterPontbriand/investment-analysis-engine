from pathlib import Path

from investment_analysis_engine.core.repository_root import REPOSITORY_ROOT

DEFAULT_RULES_PATH = REPOSITORY_ROOT / "RUNTIME_AGENTS.md"


def load_runtime_rules(path: Path | str | None = None) -> str:
    """Load RUNTIME_AGENTS.md (or a provided path). Returns empty string if missing."""
    p = Path(path) if path is not None else DEFAULT_RULES_PATH
    try:
        return p.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except Exception:
        # Optional: log warning
        return ""
