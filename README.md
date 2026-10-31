# IncidentPilot

A measured incident classifier and optional LLM investigation workflow, with evidence checks and a review gate.

[Instant saved walkthrough](https://charanvalavala.github.io/demos/incidentpilot/) · [Live app](https://charan-incidentpilot.onrender.com)

## What runs

The default backend is a real TF-IDF + logistic regression classifier trained on twenty hand-authored synthetic cases. It reads log messages and metric names, excludes untrusted runbook text from classification, and abstains when its score or margin is too low. The workflow then checks observed signals against the diagnosis. A conflicting or unsupported diagnosis produces escalation rather than a scenario's hidden prewritten action.

This classifier is small enough for the public CPU demo. It classifies four predefined causes; it is not an open-ended autonomous SRE. Probabilities are uncalibrated. Evidence references identify supplied observations, not independently proven causal support.

SQLite records evidence collection, diagnosis, proposal and approval decisions. Investigation tools only read bundled scenarios. The optional model planner selects allowed tools; if selected evidence is insufficient or confidence is low, the workflow gathers the remaining tools and re-evaluates. Approval records a simulation only. Reviewer names are unverified labels, not authenticated identities.

## Measured AI results

| Backend | Data | Valid diagnosis coverage | Correct diagnoses |
| --- | --- | ---: | ---: |
| Unconstrained Qwen JSON | 20 development cases | 0/20 | 0/20 |
| Qwen conditional likelihood over fixed cause descriptions | Same 20 development cases | 20/20 | 10/20 |
| Qwen conditional likelihood | 8 new synthetic stress cases | 8/8 | 4/8 |
| TF-IDF + logistic regression | 8 stress cases, trained only on the 20 development cases | 8/8 | 8/8 |

The stress set includes misleading historical notes and prompt-like runbook instructions. It is only eight hand-authored cases across the same four cause classes, with recognizable language. Perfect classifier scores on this tiny set do not demonstrate production reliability, novel-cause detection or robustness to arbitrary adversaries. LLM candidate scoring changes the diagnosis method; it does not repair the model's free-form JSON capability. Set `INCIDENT_TRANSFORMERS_METHOD=generated-json` to reproduce the unconstrained method. The failed initial run is retained in `reports/unconstrained-model-baseline.json`.

`reports/classifier-heldout.json`, `reports/model-evaluation.json` and `reports/transformers-heldout.json` retain case-level outputs and fallback/coverage denominators. The LLM planner selected valid tools on these runs; the classifier's planner metric is null because it uses a fixed read-tool policy. Reference validity checks check IDs only; the response-action gate is a separate check.

## Reproduce model comparisons

Default trained classifier:

```bash
INCIDENT_MODEL_BACKEND=classifier PYTHONPATH=src python -m incidentpilot.model_evaluation --cases data/model-eval-stress-8.jsonl --output reports/classifier-heldout.json
```

For the actual local CPU Qwen path, install `requirements-model.txt`, then:

```bash
INCIDENT_LLM_ENABLED=true INCIDENT_MODEL_BACKEND=transformers PYTHONPATH=src python -m incidentpilot.model_evaluation --cases data/model-eval-stress-8.jsonl --output reports/transformers-heldout.json
```

The model revision is pinned, downloads are large, and CPU inference is slow. Set `HF_HOME` to reuse a cache. In PowerShell set `$env:INCIDENT_LLM_ENABLED="true"`, `$env:INCIDENT_MODEL_BACKEND="transformers"`, `$env:PYTHONPATH="src"`, then run the same Python command.

Ollama remains available with `INCIDENT_MODEL_BACKEND=ollama`, `INCIDENT_LLM_ENABLED=true`, and a running `OLLAMA_URL` / `OLLAMA_MODEL`. Its generated JSON is schema-validated. Ollama scores for a different model are not implied by the Transformers report.

## Deployment and verification

```bash
docker build -t incidentpilot .
docker run --rm -p 8000:8000 incidentpilot
```

The default image needs scikit-learn, not a language-model server. Set `INCIDENT_DB` to persist SQLite outside an ephemeral container. The saved walkthrough contains four recorded investigations; selecting them does not call a backend. It exposes the saved benchmark and policy checks; approval controls explicitly require the live simulator.

Tests cover empty/unknown references, unknown tools, conflicting diagnosis/action, independence from hidden scenario labels, classifier prompt isolation, and a full create/reject/replay API journey. Auth, live telemetry connectors, production mutations and real-world root-cause accuracy are outside this demo's scope.

Model: [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct). Training and evaluation fixtures are original synthetic examples, not private operational logs.

## Reproduce

Python 3.12 is recommended. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=src uvicorn incidentpilot.api:app --reload
```

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
$env:PYTHONPATH = "src"
uvicorn incidentpilot.api:app --reload
```

Open http://127.0.0.1:8000. Run regressions with `PYTHONPATH=src python -m pytest -q` (PowerShell: set `PYTHONPATH` as above, then `python -m pytest -q`). GitHub Actions runs this suite, builds the Docker image and checks container health/frontend assets on pushes and pull requests.

The frontend is plain JavaScript modules. `ui.js` owns requests, cancellation, timeouts, feedback and escaping; `app.js` owns application state and rendering. Requests use per-operation abort controllers. Static saved outputs are in `static/sample.json`; they never masquerade as fresh model responses.
