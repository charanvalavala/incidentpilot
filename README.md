# IncidentPilot

IncidentPilot is a stateful incident-triage simulator. A bounded workflow reads logs, metrics, and runbook entries, records evidence, forms a scenario diagnosis, and pauses for human approval before it records a simulated action. SQLite checkpoints every transition and exposes a replayable event trace.

## What it demonstrates

- Tool-based investigation across read-only log, metric, and runbook sources, with a strict tool allowlist.
- Optional Ollama planner and structured diagnoser; malformed or out-of-policy model output falls back to the scenario policy.
- A persistent incident state machine with versioned SQLite checkpoints and an event trace.
- A human approval or rejection gate before action recording.
- Four synthetic seeded failure scenarios and a side-effect-free evaluator for read-only tool policy, evidence references, and approval gating. Scripted fallback labels are not reported as model accuracy.
- A browser dashboard for investigation, evidence inspection, trace review, and action approval.
- Docker packaging for local deployment.

## Run locally

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
uvicorn incidentpilot.api:app --reload
```

Open `http://127.0.0.1:8000`. The API stores incidents in `data/runtime/incidents.sqlite3`; set `INCIDENT_DB` to use a different path. It retains at most 250 incidents, limits incident creation and evaluation requests, and writes no incident records when the evaluator runs.

On macOS or Linux, use:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export PYTHONPATH=src
uvicorn incidentpilot.api:app --reload
```

The default scenario uses the deterministic policy path and needs no model service. To enable local model-based planning and diagnosis, set `INCIDENT_LLM_ENABLED=true`, configure `OLLAMA_URL` and `OLLAMA_MODEL`, and start Ollama. Every requested tool is checked against the read-only allowlist, model evidence references are validated, and no model output can bypass the approval gate. The optional Ollama path is not included in the deterministic demo evaluation.

## API

- `GET /api/scenarios`
- `POST /api/incidents` with `{"scenario":"api-latency-after-release"}`
- `GET /api/incidents/{incident_id}`
- `GET /api/incidents/{incident_id}/trace`
- `POST /api/incidents/{incident_id}/approval` with a reviewer and decision
- `POST /api/evaluate` with up to 20 scenario cases. The evaluator checks policy behavior without persisting incidents.

For the focused test suite:

```powershell
$env:PYTHONPATH = "src"
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

```bash
python -m pip install -r requirements-dev.txt
PYTHONPATH=src python -m pytest -q
```

### Local model evaluation

`data/model-eval-20.jsonl` contains 20 hand-authored synthetic cases across the four seeded root-cause classes. Run the optional Ollama planner and diagnoser over that set with:

```powershell
$env:INCIDENT_LLM_ENABLED = "true"
$env:OLLAMA_MODEL = "qwen2.5:3b"
$env:PYTHONPATH = "src"
python -m incidentpilot.model_evaluation
```

```bash
INCIDENT_LLM_ENABLED=true OLLAMA_MODEL=qwen2.5:3b PYTHONPATH=src python -m incidentpilot.model_evaluation
```

The report separates valid planner responses, diagnosis coverage, evidence-reference validity, model-only root-cause accuracy, and fallback rate. Accuracy excludes fallback diagnoses. This is a synthetic, four-class diagnostic check; it is not a production incident benchmark. The model evaluation requires a running Ollama server and is not part of CI.

## Safety boundary

The bundled environment is a simulator. Its tools cannot connect to cloud accounts, clusters, databases, or production APIs. Approval records a decision under an unverified reviewer label and a simulated outcome; it does not execute infrastructure changes. The evaluator checks the read-only tool boundary, evidence references, and approval-gate presence. Scripted scenario diagnoses are excluded from model accuracy, and the checks do not estimate recovery time or production incident resolution quality. In-process request limits reset on restart and are a demo safeguard rather than shared protection across proxy or multi-worker deployments.

Build and run with a persistent database volume:

```powershell
docker build -t incidentpilot .
docker run --rm -p 8000:8000 -v incidentpilot-data:/app/data/runtime incidentpilot
```

For Ollama running on the host, set `OLLAMA_URL=http://host.docker.internal:11434` in the container environment.

The repository includes a Render Blueprint at `render.yaml` for the simulator-only web demo. It leaves the Ollama model disabled because a local model service is not part of that deployment.

## Extending the system

Add a new scenario to `data/scenarios.json` with logs, metrics, a runbook, an expected diagnosis, and a proposed action. Add the matching labeled case to `data/eval.json`. A production integration would need authenticated read-only adapters, identity and role checks, an auditable approval system, idempotent change APIs, and explicit rollout and rollback policies before any write tool could exist.
