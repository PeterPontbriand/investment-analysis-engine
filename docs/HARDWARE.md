# Hardware Requirements & Model Modes

This document describes the hardware expectations for running **Financial Data Agents** and the two supported operating modes.

Nothing in this project constitutes financial advice. See the main [README](../README.md) for the full disclaimer.

---

## Two Supported Modes

In this document, **supported** means the mode is an explicit project target with documented configuration expectations. It does not imply that every model/hardware combination has been individually validated or is covered by continuous integration.

| Mode | Target Models (examples) | Typical VRAM / Memory | Intended Audience | Status |
|------|---------------------------|------------------------|-------------------|--------|
| **Light Mode** (recommended default) | `qwen2.5-coder:14b-instruct-q4_K_M` or smaller quantized models | ~8–16 GB VRAM **or** 32 GB+ unified memory (Apple Silicon / high-end mini-PC) | Most users, including the Illustrative Use Case retail/professional investor | Must be fully usable before Milestone v0.2.5 |
| **Full Dual-Tier Mode** | Fast tier ≈14B + Deep tier ≈32B (`qwen2.5-coder:32b` or `deepseek-r1:32b`) | ~24–28 GB VRAM (or equivalent high unified memory) | Users with workstation-class local hardware who want deeper multi-step reasoning and report synthesis | Supported workstation-class path; not required for basic useful analysis |

**Light Mode is the path that external testers and non-technical users are expected to use.**  
Full Dual-Tier Mode remains available for those who have the hardware and want maximum reasoning capability.

---

## Recommended Hardware (2026 consumer landscape)

The configurations below are recommendations, not hard dependencies. Model availability, quantization formats, drivers, and local inference performance change over time; the project should continue to define support primarily by resource requirements and validated modes rather than by any single vendor or product model.

### Light Mode (simplest path for most users)

**Highest simplicity (preferred for non-technical users):**
- **Apple Silicon** — Mac Mini or Mac Studio with **32 GB+ unified memory is the minimum supported target for Light Mode** (M2/M3/M4 Pro/Max class).  
  Ollama installs as a simple application; models load into unified memory with minimal configuration. Silent and low-power.
- **High-end mini-PCs** with large unified/shared memory (e.g., AMD Ryzen AI Max / Strix Halo platforms such as certain Minisforum, Geekom, Framework Desktop, or similar boxes with 64 GB shared memory). Pre-built, Windows-native Ollama support.

**Discrete GPU option (still relatively simple):**
- NVIDIA RTX 4060 Ti 16 GB (or similar) + 32–64 GB system RAM — comfortable for quantized 14B-class models.
- Used RTX 3090 24 GB remains a strong value choice if you already have one or can source one inexpensively; it can also run many quantized 32B models if you later move toward Full Mode.

### Full Dual-Tier Mode

- Single high-VRAM NVIDIA card in the 24 GB class (RTX 3090 / 4090 or newer 50-series equivalents) or multi-GPU setups, **or**
- High unified-memory systems (64–128 GB) on Apple Silicon or AMD Strix Halo / Ryzen AI Max+ platforms that can comfortably hold both a 14B and a 32B quantized model (or swap between them).

Traditional custom PC builds with large discrete GPUs offer the highest throughput but introduce driver, cooling, and power complexity that most non-technical users should avoid.

---

## Practical Guidance

1. **Start with Light Mode.**  
   Pull a 14B-class quantized model and confirm you can run a complete analysis end-to-end before considering larger models.

2. **System RAM** should generally be at least as large as the model footprint you intend to load (64 GB is a comfortable recommendation for more demanding local-AI work).

3. **Installation simplicity matters.**  
   For non-technical users the project prioritizes paths where Ollama can be installed with minimal steps (drag-and-drop on macOS, simple installer on Windows mini-PCs). Complex driver and CUDA setup is intentionally de-emphasized for the default experience.

4. **The project will not assume dual-tier hardware is available.**  
   All core single-step analysis capabilities (data retrieval, Graham-style valuation, momentum indicators, basic risk metrics, and report generation) are required to work usefully under Light Mode.

---

## Relationship to Project Milestones

- Light Mode must be documented, installable, and usable **before** the Real-User Validation Checkpoint (Milestone v0.2.5).
- External testers recruited for v0.2.5 are expected to use Light Mode unless they independently have dual-tier hardware.
- Full Dual-Tier Mode continues to be developed and remains the path for deeper multi-step autonomy and higher-fidelity synthesis once the core loop has proven useful.

---

*This document is kept in sync with the Master Plan and Discovery Workbook. Hardware recommendations reflect the 2026 consumer local-AI landscape (discrete 16–24 GB GPUs, Apple unified memory, and high-memory mini-PCs).*
