# Installation & Configuration

This guide covers the current pre-v1.0 installation and configuration process for Financial Data Agents.

Installing the application currently involves **three main things**:

1. install the small set of required software tools;
2. copy Financial Data Agents to an installation folder and let `uv` set up the supporting software it needs; and
3. provide the identification or credentials required by any data sources you want to use.

You do **not** need a GPU or a local AI model to run direct deterministic analysis.

If Git, Python virtual environments, and environment variables are already familiar to you, the [Quick Start](QUICKSTART.md) is much shorter.

---

## 1. Installation

### Install the required tools

Git is a widely used program for copying software projects from services such as GitHub and, later, getting updates to those projects. You do not need to learn Git's developer features to follow this guide.

You need:

- [Git](https://git-scm.com/downloads/) — used here to download Financial Data Agents and later obtain updates.
- [Python 3.12 or newer](https://www.python.org/downloads/) — the programming language Financial Data Agents uses.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — sets up the supporting Python software Financial Data Agents needs and runs its commands.
- Internet access when you want live market or filing data.

**One more Git term you will see:** a Git *repository* is simply the project's collection of files plus a record of how those files have changed over time. You do not need to understand Git internals to install the application.

### Choose an installation folder

Open a terminal (PowerShell, Windows Terminal, Git Bash, macOS Terminal, or a Linux shell), change to the folder where you want Financial Data Agents to live, and run:

```bash
git clone https://github.com/PeterPontbriand/financial-data-agents.git
cd financial-data-agents
```

The new `financial-data-agents` folder is referred to throughout the user documentation as the **installation folder**.

### Set up the application

From inside the installation folder, run:

```bash
uv sync
```

This lets `uv` download and set up the supporting Python software that Financial Data Agents needs.

Then check that the command is available:

```bash
uv run financial-agents --help
```

If you see the Financial Data Agents help text, the basic installation is working.

---

## 2. Configuration

Configuration tells Financial Data Agents how to identify itself to certain data services and, optionally, how to use services for which you have an account.

### SEC EDGAR identification

The Graham and Free Cash Flow & Earnings Growth strategies can obtain public company financial facts from the U.S. [SEC](GLOSSARY.md#sec) [EDGAR](GLOSSARY.md#edgar) system.

The SEC asks automated software to identify itself in the HTTP `User-Agent` header. Financial Data Agents therefore requires `SEC_USER_AGENT` before requesting SEC data.

Use a real, reachable identity such as:

```text
Your Name your-email@example.com
```

This is **not** a financial assumption, brokerage identity, SEC account, or analysis value. It is simply responsible identification for automated access to the SEC's public systems.

See the SEC's [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) and [Developer Resources](https://www.sec.gov/about/developer-resources).

#### Recommended: create a `.env` configuration file

In the Financial Data Agents installation folder, create a plain-text file named `.env` containing:

```dotenv
SEC_USER_AGENT="Your Name your-email@example.com"
```

Replace `Your Name` and `your-email@example.com` with your actual name and a real email address that you can receive mail at. Do **not** leave the example identity unchanged.

Financial Data Agents loads this file automatically. The project's Git configuration excludes `.env` and `.env*` so that local credentials are not accidentally committed.

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

### Optional: Massive market-data access

[Massive](GLOSSARY.md#massive) is a commercial financial-market-data service. Financial Data Agents can optionally use it for supported current market/fundamental data in the Graham Growth Value method.

You do **not** need Massive to run the Graham Number, Momentum, or Free Cash Flow & Earnings Growth strategies.

A **Massive API key** is a credential supplied by Massive that allows software to access data permitted by your Massive account/plan. If you already have or want Massive access:

1. obtain an API key from your Massive account;
2. review the [Massive REST API quickstart](https://massive.com/docs/rest/quickstart); and
3. add the key as another line in the same `.env` file:

```dotenv
MASSIVE_API_KEY="your-massive-api-key"
```

Keep the key private. Your Massive plan must permit the data/endpoints you intend to use.

For exactly what the current integration can supply, see [Graham Analysis Strategy — Data sources](strategies/GRAHAM.md#data-sources).

### Optional: local AI

Direct deterministic analysis does not require Ollama or a GPU.

If you want to use optional local-AI orchestration/synthesis features, see [Hardware & Local AI](HARDWARE.md). You can add local AI after confirming that ordinary analysis commands work.

---

## 3. Verify the setup

First check the application itself:

```bash
uv run financial-agents --help
```

If you configured `SEC_USER_AGENT`, a simple Graham analysis is a useful live-data check:

```bash
uv run financial-agents graham KO
```

You can also verify the annual-fundamentals growth strategy:

```bash
uv run financial-agents fcf-growth MSFT
```

Once installation is working, continue with the [Usage Guide](USAGE.md). The [Smoke Testing Commands](SMOKE_TESTING.md) provide a broader human-executed check.

---

## 4. Troubleshooting

### "SEC EDGAR access is not configured"

Check that `SEC_USER_AGENT` is present in the `.env` file in the Financial Data Agents installation folder, or set it in the current terminal as shown above.

### "Massive access is not configured"

This matters only if you explicitly ask Financial Data Agents to use Massive. Set `MASSIVE_API_KEY` in `.env` or in the current terminal.

### `git`, `python`, or `uv` is "not recognized" / "command not found"

The corresponding prerequisite is either not installed or its executable is not available to the terminal. Revisit the official installation link for that tool, then open a new terminal and try again.

### `uv sync` fails

Confirm that:

- you are inside the `financial-data-agents` installation folder;
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
