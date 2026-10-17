# Quick Start for Experienced Developers

This is the terse installation/configuration version. If any step is unfamiliar, use the full [Installation & Configuration Guide](INSTALLATION.md).

## Prerequisites

- Git
- Python 3.12+
- `uv`
- Internet access for live data

## Install

```bash
git clone https://github.com/PeterPontbriand/investment-analysis-engine.git
cd investment-analysis-engine
uv sync
```

Fresh storage initializes automatically on first persistence use. Set
`IAN_DATABASE_URL` before the first analysis if using a nondefault location. Existing
schemas require explicit upgrades after stopping processes and backing up data:

```bash
ian db status
ian db upgrade
```

The maintenance group is hidden from top-level help; use `db --help`. See
[Local Database Operations](DATABASE.md) for upgrades, backups, and recovery.

## Configure SEC EDGAR

Create `.env` in your settings folder (on Windows `%APPDATA%\investment-analysis-engine`; see [Where the application keeps its files](INSTALLATION.md#where-the-application-keeps-its-files) for other systems):

```dotenv
SEC_USER_AGENT="Your Name your-email@example.com"
```

The settings folder is outside the repository, so the file cannot be committed. Create the folder first if it does not exist.

## Smoke test

```bash
uv run ian --help
uv run ian graham-number KO
uv run ian momentum AAPL
uv run ian fcf-growth MSFT
```

Commands that access SEC EDGAR require `SEC_USER_AGENT`. For a broader human-executed check, use the [Smoke Testing Commands](SMOKE_TESTING.md).

## Next

- [Usage Guide](USAGE.md)
- [Analysis Strategy Guides](strategies/README.md)
- [Hardware & Local AI](HARDWARE.md) — only if you want local-model features
