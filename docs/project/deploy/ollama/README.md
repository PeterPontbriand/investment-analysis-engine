# Ollama Deployment Artifacts

This directory is the canonical repository location for Ollama Modelfiles. Do not add duplicate Modelfiles at the repository root.

## Application model

`Modelfile.agents` configures the optional Financial Data Agents application model. It is an application runtime artifact and is independent of the model used by Cline to implement the repository.

Create or refresh its local alias from the repository root with:

```powershell
ollama create financial-data-agents -f docs/project/deploy/ollama/Modelfile.agents
```

Changing this artifact affects application-model behavior and requires review against the applicable Ollama/schema evaluation requirements.

## Historical Step 2.5 Cline implementation model

`Modelfile.cline-step-2.5` preserves the local model configuration tested while implementing the Step 2.5 Golden Suite. The installed `qwen3-coder:30b` tag resolved to the intended 30.5B-total/3.3B-active `Q4_K_M` model with tool support, but the implementation experiment was subsequently rejected after repeated incomplete artifacts and false verification reports. This file is historical evidence, not an active model recommendation.

Create the dedicated alias from the repository root with:

```powershell
ollama create financial-data-agents-step-2-5 -f docs/project/deploy/ollama/Modelfile.cline-step-2.5
```

Section 19 and the audit record in the [Step 2.5 Golden Suite Slice Plan](../../milestones/v0.2/step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md) explain the historical configuration and failure. Do not use that retired workflow to begin new implementation work.

For Step 3.1, follow the bounded slices, independent verification, and current local-model advice in the [Step 3.1 SQLite Slice Plan](../../milestones/v0.2/step-3.1/STEP_3_1_SQLITE_SLICE_PLAN.md). The exact primary bakeoff model is the local Ollama tag `glm-4.7-flash`; configure that same model ID in Cline. It is not promoted to an approved implementation model, and no Step 3.1 alias is frozen, until it passes two consecutive independently verified micro-slices. A tool smoke test alone is insufficient.

This development alias is not the model-under-evaluation configuration for the optional real-local-Ollama Golden Suite mode. Record those empirical settings separately.
