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

In the settings folder (see [Where the application keeps its files](#where-the-application-keeps-its-files)), create a plain-text file named `.env` containing:

```dotenv
SEC_USER_AGENT="Your Name your-email@example.com"
```

Replace `Your Name` and `your-email@example.com` with your actual name and a real email address that you can receive mail at. Do **not** leave the example identity unchanged.

Investment Analysis Engine loads this file automatically, and only from the settings folder: a `.env` file in the folder you run it from, or in the folder you cloned, is not read. A value set in the terminal wins over the same value in the file. The file lives outside any project folder, so it cannot be committed by accident.

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

### Where the application keeps its files

The application keeps your settings, database and logs in folders of your own user account, not in the folder you installed it from:

| | Settings folder | Data folder (the database) | Log folder |
| :--- | :--- | :--- | :--- |
| Windows | `%APPDATA%\investment-analysis-engine` | `%LOCALAPPDATA%\investment-analysis-engine` | `%LOCALAPPDATA%\investment-analysis-engine\Logs` |
| macOS | `~/Library/Application Support/investment-analysis-engine` | the same folder | `~/Library/Logs/investment-analysis-engine` |
| Linux | `$XDG_CONFIG_HOME/investment-analysis-engine` | `$XDG_DATA_HOME/investment-analysis-engine` | `$XDG_STATE_HOME/investment-analysis-engine/log` |

On Linux the `XDG_*` variables usually are not set, and the folders are then `~/.config`, `~/.local/share` and `~/.local/state` below your home folder. The application never creates a folder just by looking for it: the database folder appears when the database is first needed, and the log folder when a command starts.

Inside them:

- `.env` in the settings folder holds your settings and the SEC identity (see below);
- `strategies/<name>.toml` in the settings folder holds your own values for an analysis method (see [Strategy settings files](#strategy-settings-files));
- `investment-analysis-engine.sqlite3` in the data folder is the database (see [Local Database Operations](DATABASE.md));
- `app.log` and a `trajectories` folder in the log folder are the application log and the run telemetry.

Three variables move a folder, and each must be a full (absolute) path: `IAN_CONFIG_DIR` for the settings folder, `IAN_DATA_DIR` for the data folder and `IAN_LOG_DIR` for the log folder. `IAN_TELEMETRY_LOG_DIR` moves the telemetry alone and otherwise follows the log folder. `IAN_DATABASE_URL` names the database file directly and wins over `IAN_DATA_DIR`. `IAN_CONFIG_DIR` has to be set in the terminal's own environment, because it says where `.env` is; it cannot be set inside `.env`, and the application stops with a message if it is.

A relative path in any of these is refused, with a message that names the variable. On Windows, a path Git Bash writes as `/e/Data` is refused too, because Windows would place it under the root of the current drive; write `E:/Data`.

The application only reads the settings folder and never writes to it.

### Engine settings

Every engine setting is read from an environment variable named `IAN_<NAME>`, in any letter case. The documented spelling is upper case, for example `IAN_DATA_DIR`, `IAN_DATABASE_URL`, `IAN_LOG_DIR` or `IAN_RELIABILITY_LIMITS__OVERALL_TIMEOUT_SECONDS` (two underscores separate a group from the field inside it). Names without the `IAN_` prefix are not read.

The provider credential keeps its own name and is the only exception: `SEC_USER_AGENT`, also in any letter case. Do not add the `IAN_` prefix to it.

A `.env` file therefore contains the provider credential as above plus any settings you override, for example:

```dotenv
SEC_USER_AGENT="Your Name your-email@example.com"
IAN_DATA_DIR="E:/FinancialData"
```

The values `IAN_DATA_DIR`, `IAN_LOG_DIR`, `IAN_TELEMETRY_LOG_DIR` and the file path in `IAN_DATABASE_URL` must be absolute paths.

At startup (including `ian --help`) the application prints a one-sentence message naming the variable to the error stream and exits with code 2 when an `IAN_` variable matches no setting (usually a typo), when two variables that differ only by letter case are both set for the same setting, or when a variable's value is not valid for its setting (the message says what was wrong and never repeats the value). The application name, version and text encoding are fixed and cannot be overridden.

### Strategy settings files

Some analysis methods have tunable values: Momentum (the two moving-average windows, the RSI period and the first day of the price history) and Graham Growth (its constants). Their defaults ship inside the application and are not edited. To use other values, create a file named after the method in the `strategies` folder of your settings folder: `strategies/momentum.toml` or `strategies/graham-growth.toml`. The file may hold only the keys you want to change; every other key keeps its shipped default. For example, a `strategies/momentum.toml` holding only `rsi_period = 21` changes the RSI period and nothing else. The keys are listed in each method's guide ([Momentum](strategies/MOMENTUM.md), [Graham Growth](strategies/GRAHAM_GROWTH.md)).

Changes take effect at the next command you run. A watchlist selection keeps the windows and RSI period it was created with, so editing those values changes only selections created afterwards; the first day of the price history applies whenever an analysis or refresh runs. Graham Growth's constants apply when an analysis runs, and each saved run records the constants it used.

Every file is checked at startup, including by `ian --help`. A missing file of your own is normal. If a file is not valid TOML or holds an unknown key or an invalid value, every command stops with exit code 2 and prints one message that gives the full path of the file the key came from, names the key and says what is wrong. The message never repeats the value. Correct the key it names, or delete your file to return to the shipped defaults.

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

Check that `SEC_USER_AGENT` is present in the `.env` file in your settings folder, or set it in the current terminal as shown above.

### `git`, `python`, or `uv` is "not recognized" / "command not found"

The corresponding prerequisite is either not installed or its executable is not available to the terminal. Revisit the official installation link for that tool, then open a new terminal and try again.

### `uv sync` fails

Confirm that:

- you are inside the `investment-analysis-engine` installation folder;
- your Python version satisfies the project requirement; and
- your Internet connection can reach the package sources used by `uv`.

### An error starts with a line about Yahoo Finance or SEC EDGAR

After a command fails because a data provider failed, the application sends one small test request to that provider
and prints what it found as the first line. It tests the provider, not your request. The line is one of seven; the
examples name Yahoo Finance, and SEC EDGAR reads the same.

- **"is not answering: a test request also failed"**: the provider could not be reached. Check your connection, a
  proxy, and for SEC EDGAR the `SEC_USER_AGENT` identity, then try again.
- **"is limiting requests: a test request was also refused"**: the provider is throttling you. Wait before trying again.
- **"answered a test request in a form this application does not read"**: the provider changed what it sends. This is
  not caused by your command or your settings; report it.
- **"returned no data for a known test ticker. It may be limiting requests."**: the provider answered with nothing for
  a ticker that always has data. Yahoo Finance can do this when it throttles, so wait and try again.
- **"answered a test request normally. The failure may be specific to this request."**: the provider works, so look
  at the ticker, the date or the options you used.
- **"was not checked (the provider check is turned off)"**: you used `--no-provider-check` or set
  `IAN_PROVIDER_CHECK=false`. Remove either to see a verdict.
- **"could not be checked"**: no verdict was reached, for example SEC access is not set up (see above).

Set `IAN_PROVIDER_CHECK=false` to turn the check off for every command, and `IAN_PROVIDER_CHECK_TIMEOUT_SECONDS`
(default `10`) to change its time limit. With `--json` the same request is sent, no line is printed, and the finding
is the document's `provider_check` element; a failed call can then take up to 12 seconds longer per implicated
provider, which `--no-provider-check` avoids. See [Usage](USAGE.md#after-a-provider-failure-the-first-line) for the
details.

### A ticker returns no usable result

That does not necessarily mean installation failed. A security may lack data required by a particular method. See the relevant [Analysis Strategy Guide](strategies/README.md) and use `--details` / `--diagnostics` where appropriate.

### Direct analysis works but local-AI features do not

That is possible by design. Deterministic analysis and optional local-AI features are separate capabilities. See [Hardware & Local AI](HARDWARE.md).

---

## Security and privacy reminders

- Do not put real API keys, email addresses, or any other secrets anywhere except in the `.env` file in your settings folder.
- Treat `.env` as private local configuration.
- Use a genuine SEC User-Agent identity suitable for automated access.
- Review the terms, permissions, and licensing of any data service you use.
