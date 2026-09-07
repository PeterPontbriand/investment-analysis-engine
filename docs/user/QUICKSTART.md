# Quick Start for Experienced Developers

This is the terse installation/configuration version. If any step is unfamiliar, use the full [Installation & Configuration Guide](INSTALLATION.md).

## Prerequisites

- Git
- Python 3.12+
- `uv`
- Internet access for live data

## Install

```bash
git clone https://github.com/PeterPontbriand/financial-data-agents.git
cd financial-data-agents
uv sync
uv run --no-sync alembic upgrade head
```

Set `DATABASE_URL` before migration if using a nondefault location. See
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
uv run financial-agents --help
uv run financial-agents graham-number KO
uv run financial-agents momentum AAPL
uv run financial-agents fcf-growth MSFT
```

Commands that access SEC EDGAR require `SEC_USER_AGENT`. For a broader human-executed check, use the [Smoke Testing Commands](SMOKE_TESTING.md).

## Next

- [Usage Guide](USAGE.md)
- [Analysis Strategy Guides](strategies/README.md)
- [Hardware & Local AI](HARDWARE.md) — only if you want local-model features
