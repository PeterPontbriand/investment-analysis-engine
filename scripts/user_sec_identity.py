"""Print the ``SEC_USER_AGENT`` value from the ``.env`` file of the settings folder, and nothing else.

The live-check scripts use it to find the identity the SEC requires when the variable is not set in the terminal. The
settings folder is located by the package's own resolver, so ``IAN_CONFIG_DIR`` is honoured. The key is found in any
letter case. Nothing is printed when the file or the key is missing. If two spellings of the key are present, the
script exits with code 2 and a message that names the spellings, never a value.

Run it as a module from the repository root: ``uv run --no-sync python -m scripts.user_sec_identity``.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

from dotenv import dotenv_values

from investment_analysis_engine.config.user_folders import resolve_settings_folder

KEY = "SEC_USER_AGENT"


def main(environ: Mapping[str, str] | None = None) -> int:
    """Print the identity and return 0, or return 2 when two spellings of the key are present."""
    path = resolve_settings_folder(os.environ if environ is None else environ) / ".env"
    if not path.is_file():
        return 0
    found = {name: value for name, value in dotenv_values(path).items() if name.upper() == KEY}
    if len(found) > 1:
        spellings = " and ".join(sorted(found))
        sys.stderr.write(f"{path} sets {spellings}, which differ only by letter case; set exactly one.\n")
        return 2
    value = next(iter(found.values()), None)
    if value:
        sys.stdout.write(f"{value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
