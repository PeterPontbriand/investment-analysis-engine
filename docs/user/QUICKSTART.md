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
`database_url` before the first analysis if using a nondefault location. Existing
schemas require explicit upgrades after stopping processes and backing up data:

```bash
uv run --no-sync ian db status
uv run --no-sync ian db upgrade
```

The maintenance group is hidden from top-level help; use `db --help`. See
[Local Database Operations](DATABASE.md) for upgrades, backups, and recovery.

## Configure SEC EDGAR

Create `.env` in the project root:

```dotenv
SEC_USER_AGENT="Your Name your-email@example.com"
```

Optional Massive access:

```dotenv
MASSIVE_API_KEY="your-massive-api-key"
```

`.env` / `.env*` are excluded by the repository's Git ignore rules.

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
