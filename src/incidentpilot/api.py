from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from incidentpilot import store
from incidentpilot.config import STATIC_DIR
from incidentpilot.engine import approve, create, evaluate_cases, scenarios
from incidentpilot.limits import enforce_limit

app = FastAPI(title="IncidentPilot", version="1.0.0", description="Stateful incident triage, read-only evidence tools, trace replay, and human approval gating.")


class StartRequest(BaseModel):
    scenario: str


class ApprovalRequest(BaseModel):
    approved: bool
    actor: str = Field(min_length=2, max_length=80)


class EvalRequest(BaseModel):
    cases: list[dict[str, str]] = Field(min_length=1, max_length=20)


@app.on_event("startup")
def initialize():
    store.initialize()


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "environment": "simulator"}


@app.get("/api/scenarios")
def list_scenarios():
    return [{"id": key, "name": value["name"], "summary": value["summary"]} for key, value in scenarios().items()]


@app.get("/api/incidents")
def list_incidents():
    return store.recent_incidents()


@app.post("/api/incidents")
def start_incident(request: Request, payload: StartRequest):
    enforce_limit(request, "create-incident", 8)
    try:
        return create(payload.scenario)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return incident


@app.get("/api/incidents/{incident_id}/trace")
def get_trace(incident_id: str):
    if store.get_incident(incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return store.events(incident_id)


@app.post("/api/incidents/{incident_id}/approval")
def record_approval(incident_id: str, request: ApprovalRequest):
    try:
        return approve(incident_id, request.approved, request.actor)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Incident not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/evaluate")
def evaluate(request: Request, payload: EvalRequest):
    enforce_limit(request, "evaluate", 3)
    try:
        return evaluate_cases(payload.cases)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
