# Hardware & Local AI

Financial Data Agents' direct deterministic analysis strategies do **not** require a GPU or a local AI model.

This guide matters only if you want to use the application's optional local-LLM features through Ollama.

## Two local-AI operating modes

| Mode | Typical target | Approximate local-model memory | Best fit |
|---|---|---|---|
| **Light Mode** (recommended) | Quantized ~14B-class model or smaller | ~8–16 GB VRAM or 32 GB+ unified memory | Most users; bounded local planning/selection/synthesis |
| **Full Dual-Tier Mode** | Fast ~14B tier + deeper ~32B tier | ~24–28 GB VRAM or equivalent high unified memory | Users with workstation-class hardware who want deeper multi-step reasoning/synthesis |

These are project support targets, not a promise that every model/hardware combination has been individually validated.

## Start with Light Mode

Light Mode is the recommended configuration for most people.

Examples of reasonably approachable hardware include:

- Apple Silicon systems with 32 GB+ unified memory;
- high-memory mini-PCs using modern AMD unified/shared-memory platforms; and
- NVIDIA systems with roughly 16 GB or more VRAM for comfortable 14B-class quantized-model use.

A used RTX 3090-class 24 GB card or newer high-VRAM hardware can also accommodate larger local models, but custom GPU systems add driver, cooling, power, and installation complexity.

## Full Dual-Tier Mode

Full Dual-Tier Mode is optional. It is intended for users who already have enough local memory/VRAM to run a faster execution model plus a larger reasoning/synthesis model, or to swap between them comfortably.

Typical configurations include:

- a high-VRAM NVIDIA GPU in the ~24 GB class or above;
- multiple GPUs; or
- high-unified-memory systems in roughly the 64–128 GB class.

## Practical guidance

1. **Get deterministic analysis working first.** Complete [Installation & Configuration](INSTALLATION.md) and run an ordinary strategy command before adding local AI.
2. **Start with Light Mode.** Confirm a complete local-AI workflow before considering larger models.
3. **Memory matters more than branding.** Model size, quantization, context length, and inference software determine actual memory requirements.
4. **Installation simplicity matters.** Pre-built systems and straightforward Ollama installations are preferable for users who do not want to manage GPU drivers/CUDA stacks.
5. **Local AI must never change financial arithmetic.** Analysis strategies remain deterministic whether or not a model is available.

## Related documentation

- [Installation & Configuration](INSTALLATION.md)
- [Usage Guide](USAGE.md)
- [Evaluations & Golden Suite](../EVALUATIONS.md) — optional empirical local-model evaluation and its separation from deterministic results
- [Glossary — Light Mode](GLOSSARY.md#light-mode)
- [Glossary — Full Dual-Tier Mode](GLOSSARY.md#full-dual-tier-mode)
