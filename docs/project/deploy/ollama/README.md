# Ollama Deployment Artifacts

This directory is the canonical repository location for Ollama Modelfiles. Do not add duplicate Modelfiles at the repository root.

## Application model

`Modelfile.agents` configures the optional Financial Data Agents application model. It is an application runtime artifact and is independent of the model used by Cline to implement the repository.

Create or refresh its local alias from the repository root with:

```powershell
ollama create financial-data-agents -f docs/project/deploy/ollama/Modelfile.agents
```

Changing this artifact affects application-model behavior and requires review against the applicable Ollama/schema evaluation requirements.

## Step 2.5 Cline implementation model

`Modelfile.cline-step-2.5` configures the local model recommended for Cline while implementing the Step 2.5 Golden Suite. The installed `qwen3-coder:30b` tag has been verified to resolve to the intended 30.5B-total/3.3B-active `Q4_K_M` model with tool support.

Create the dedicated alias from the repository root with:

```powershell
ollama create financial-data-agents-step-2-5 -f docs/project/deploy/ollama/Modelfile.cline-step-2.5
```

Configure Cline and the Ollama server using Section 19 of the [Step 2.5 Golden Suite Slice Plan](../../milestones/v0.2/step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md). In particular, Cline's context window must match the Modelfile's `num_ctx`, and `ollama ps` must confirm the requested context and full GPU offload before Slice A begins.

This development alias is not the model-under-evaluation configuration for the optional real-local-Ollama Golden Suite mode. Record those empirical settings separately.
