from pathlib import Path

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "RUNTIME_AGENTS.md"


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
