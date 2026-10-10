# Installation & Configuration

This guide covers the current pre-v1.0 installation and configuration process for Investment Analysis Engine.

Installing the application currently involves **three main things**:

1. install the small set of required software tools;
2. copy Investment Analysis Engine to an installation folder and let `uv` set up the supporting software it needs; and
3. provide the identification or credentials required by any data sources you want to use.

You do **not** need a GPU or a local AI model to run direct deterministic analysis.

If Git, Python virtual environments, and environment variables are already familiar to you, the [Quick Start](QUICKSTART.md) is much shorter.

---

## 1. Installation

### Install the required tools

Git is a widely used program for copying software projects from services such as GitHub and, later, getting updates to those projects. You do not need to learn Git's developer features to follow this guide.

You need:

- [Git](https://git-scm.com/downloads/) — used here to download Investment Analysis Engine and later obtain updates.
- [Python 3.12 or newer](https://www.python.org/downloads/) — the programming language Investment Analysis Engine uses.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — sets up the supporting Python software Investment Analysis Engine needs and runs its commands.
- Internet access when you want live market or filing data.

**One more Git term you will see:** a Git *repository* is simply the project's collection of files plus a record of how those files have changed over time. You do not need to understand Git internals to install the application.

### Choose an installation folder

Open a terminal (PowerShell, Windows Terminal, Git Bash, macOS Terminal, or a Linux shell), change to the folder where you want Investment Analysis Engine to live, and run:

```bash
git clone https://github.com/PeterPontbriand/investment-analysis-engine.git
cd investment-analysis-engine
```

The new `investment-analysis-engine` folder is referred to throughout the user documentation as the **installation folder**.

### Set up the application

From inside the installation folder, run:

```bash
uv sync
```

This lets `uv` download and set up the supporting Python software that Investment Analysis Engine needs.

The first analysis that needs local storage initializes a missing or verified
empty database automatically. Existing databases require explicit upgrades.

For database location overrides, upgrades, backups, and recovery, see
[Local Database Operations](DATABASE.md). Set any database override before the first analysis.

Then check that the command is available:

```bash
uv run ian --help
```

If you see the Investment Analysis Engine help text, the command is available. Help
does not open or verify the database.

---

## 2. Configuration

Configuration tells Investment Analysis Engine how to identify itself to certain data services and, optionally, how to use services for which you have an account.

### SEC EDGAR identification

Analysis strategies that use company filings can obtain public financial facts from the U.S. [SEC](GLOSSARY.md#sec) [EDGAR](GLOSSARY.md#edgar) system.

The SEC asks automated software to identify itself in the HTTP `User-Agent` header. Investment Analysis Engine therefore requires `SEC_USER_AGENT` before requesting SEC data.

Use a real, reachable identity such as:

```text
Your Name your-email@example.com
```

This is **not** a financial assumption, brokerage identity, SEC account, or analysis value. It is simply responsible identification for automated access to the SEC's public systems.

See the SEC's [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) and [Developer Resources](https://www.sec.gov/about/developer-resources).

#### Recommended: create a `.env` configuration file

In the Investment Analysis Engine installation folder, create a plain-text file named `.env` containing:

```dotenv
SEC_USER_AGENT="Your Name your-email@example.com"
```

Replace `Your Name` and `your-email@example.com` with your actual name and a real email address that you can receive mail at. Do **not** leave the example identity unchanged.

Investment Analysis Engine loads this file automatically. The project's Git configuration excludes `.env` and `.env*` so that local credentials are not accidentally committed.

#### Temporary alternative: set it only for the current terminal

PowerShell:

```powershell
$env:SEC_USER_AGENT = "Your Name your-email@example.com"
```

Git Bash, macOS, or Linux:

```bash
export SEC_USER_AGENT="Your Name your-email@example.com"
```

The temporary form disappears when that terminal session ends.

The [Analysis Strategy Guides](strategies/README.md) describe supported data sources and any provider-specific limits for each strategy.

### Engine settings

Every engine setting is read from an environment variable named `IAN_<NAME>`, in any letter case. The documented spelling is upper case, for example `IAN_DATA_DIR`, `IAN_DATABASE_URL`, `IAN_LOG_DIR` or `IAN_RELIABILITY_LIMITS__OVERALL_TIMEOUT_SECONDS` (two underscores separate a group from the field inside it). Names without the `IAN_` prefix are not read.

The provider credential keeps its own name and is the only exception: `SEC_USER_AGENT`, also in any letter case. Do not add the `IAN_` prefix to it.

A `.env` file therefore contains the provider credential as above plus any settings you override, for example:

```dotenv
SEC_USER_AGENT="Your Name your-email@example.com"
IAN_DATA_DIR="E:/FinancialData"
```

At startup (including `ian --help`) the application prints one sentence naming the variable to the error stream and exits with code 2 when an `IAN_` variable matches no setting (usually a typo), when two variables that differ only by letter case are both set for the same setting, or when a variable's value is not valid for its setting (the sentence says what was wrong and never repeats the value). The application name, version and text encoding are fixed and cannot be overridden.

### Optional: local AI

Direct deterministic analysis does not require Ollama or a GPU.

If you want to use optional local-AI orchestration/synthesis features, see [Hardware & Local AI](HARDWARE.md). You can add local AI after confirming that ordinary analysis commands work.

---

## 3. Verify the setup

First check the application itself:

```bash
uv run ian --help
```

If you configured `SEC_USER_AGENT`, a simple Graham analysis is a useful live-data check:

```bash
uv run ian graham-number KO
```

You can also verify the annual-fundamentals growth strategy:

```bash
uv run ian fcf-growth MSFT
```

Once installation is working, continue with the [Usage Guide](USAGE.md). The [Smoke Testing Commands](SMOKE_TESTING.md) provide a broader human-executed check.

---

## 4. Troubleshooting

### A database readiness error appears

The message identifies the selected database and a next action without requiring
`--diagnostics`. Inspect it with `uv run --no-sync ian db status`.
For an upgrade-required error, stop application processes and back up existing
data before `uv run --no-sync ian db upgrade` against the same target.
Preserve incompatible or corrupt storage for inspection; do not delete it or
stamp its revision. See [Local Database Operations](DATABASE.md) for error codes,
target overrides, locking and recovery.

### "SEC EDGAR access is not configured"

Check that `SEC_USER_AGENT` is present in the `.env` file in the Investment Analysis Engine installation folder, or set it in the current terminal as shown above.

### `git`, `python`, or `uv` is "not recognized" / "command not found"

The corresponding prerequisite is either not installed or its executable is not available to the terminal. Revisit the official installation link for that tool, then open a new terminal and try again.

### `uv sync` fails

Confirm that:

- you are inside the `investment-analysis-engine` installation folder;
- your Python version satisfies the project requirement; and
- your Internet connection can reach the package sources used by `uv`.

### A ticker returns no usable result

That does not necessarily mean installation failed. A security may lack data required by a particular method. See the relevant [Analysis Strategy Guide](strategies/README.md) and use `--details` / `--diagnostics` where appropriate.

### Direct analysis works but local-AI features do not

That is possible by design. Deterministic analysis and optional local-AI features are separate capabilities. See [Hardware & Local AI](HARDWARE.md).

---

## Security and privacy reminders

- Do not put real API keys, email addresses, or any other secrets anywhere in the installation folder except in the `.env` file.
- Treat `.env` as private local configuration.
- Use a genuine SEC User-Agent identity suitable for automated access.
- Review the terms, permissions, and licensing of any data service you use.
