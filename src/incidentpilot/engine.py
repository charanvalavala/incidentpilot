from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from incidentpilot.config import LLM_ENABLED, SCENARIOS_PATH
from incidentpilot import store
from incidentpilot.reasoning import diagnose_with_model, plan_tools


def scenarios() -> dict[str, dict[str, Any]]:
    return json.loads(Path(SCENARIOS_PATH).read_text(encoding="utf-8"))


def tool_read_logs(scenario: dict[str, Any]) -> dict[str, Any]:
    return {"tool": "read_logs", "mode": "read-only", "items": scenario["logs"]}


def tool_read_metrics(scenario: dict[str, Any]) -> dict[str, Any]:
    return {"tool": "read_metrics", "mode": "read-only", "items": scenario["metrics"]}


def tool_read_runbook(scenario: dict[str, Any]) -> dict[str, Any]:
    return {"tool": "read_runbook", "mode": "read-only", "items": scenario["runbook"]}


READ_TOOLS = {"read_logs": tool_read_logs, "read_metrics": tool_read_metrics, "read_runbook": tool_read_runbook}


def collect_evidence(scenario: dict[str, Any], selected_tools: list[str]) -> list[dict[str, Any]]:
    return [READ_TOOLS[name](scenario) for name in selected_tools]


def diagnose(scenario: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    labels = {item["tool"]: item["items"] for item in evidence}
    decision = diagnose_with_model(evidence, sorted({item["diagnosis"]["root_cause"] for item in scenarios().values()}))
    if decision is not None:
        return decision, "ollama"
    decision = scenario["diagnosis"]
    references = [item["id"] for tool in ("read_logs", "read_metrics", "read_runbook") for item in labels.get(tool, [])[:2]]
    return {
        "summary": decision["summary"],
        "root_cause": decision["root_cause"],
        "evidence_refs": references,
    }, "policy-fallback"


def propose_action(scenario: dict[str, Any]) -> dict[str, Any]:
    action = scenario["proposed_action"]
    return {
        "action": action["name"],
        "description": action["description"],
        "impact": action["impact"],
        "execution_mode": "simulation",
        "approval_required": True,
        "policy": "No production mutation is available in this demo. The simulated action is gated on an explicit human approval event.",
    }


def create(scenario_id: str) -> dict[str, Any]:
    available = scenarios()
    if scenario_id not in available:
        raise ValueError(f"Unknown scenario. Choose one of: {', '.join(available)}")
    scenario = available[scenario_id]
    incident_id = uuid.uuid4().hex[:12]
    state = {"scenario_name": scenario["name"], "evidence": [], "diagnosis": None, "proposal": None, "approval": None, "result": None}
    store.create_incident(incident_id, scenario_id, state)
    selected_tools, planner_mode = plan_tools(scenario)
    evidence = collect_evidence(scenario, selected_tools)
    state["reasoning"] = {"planner": planner_mode, "diagnostician": "policy-fallback"}
    state["evidence"] = evidence
    store.update_incident(incident_id, state, "diagnosed", "agent.evidence_collected", {"tools": [item["tool"] for item in evidence]})
    state["diagnosis"], state["reasoning"]["diagnostician"] = diagnose(scenario, evidence)
    store.update_incident(incident_id, state, "awaiting_approval", "agent.diagnosed", state["diagnosis"])
    state["proposal"] = propose_action(scenario)
    store.update_incident(incident_id, state, "awaiting_approval", "agent.action_proposed", state["proposal"])
    return store.get_incident(incident_id)


def approve(incident_id: str, approved: bool, actor: str) -> dict[str, Any]:
    incident = store.get_incident(incident_id)
    if incident is None:
        raise KeyError(incident_id)
    state = incident["state"]
    if incident["status"] != "awaiting_approval":
        raise ValueError("This incident is not waiting for an approval decision.")
    if state.get("approval") is not None:
        raise ValueError("An approval decision has already been recorded.")
    if len(actor.strip()) < 2 or len(actor) > 80:
        raise ValueError("Provide a reviewer name between 2 and 80 characters.")
    state["approval"] = {"approved": approved, "actor": actor.strip(), "recorded_at": store.now()}
    if approved:
        state["result"] = {"status": "simulated", "message": "The approved action was recorded in the incident simulator. No external system was changed."}
        status = "resolved_simulation"
        event = "approval.granted"
    else:
        state["result"] = {"status": "rejected", "message": "The proposed action was rejected. No action was executed."}
        status = "closed_rejected"
        event = "approval.rejected"
    store.update_incident(incident_id, state, status, event, state["approval"], expected_version=incident["version"], expected_status="awaiting_approval")
    return store.get_incident(incident_id)


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    available = scenarios()
    results = []
    for case in cases:
        scenario_id = case.get("scenario")
        if scenario_id not in available:
            raise ValueError(f"Unknown scenario: {scenario_id}")
        scenario = available[scenario_id]
        selected_tools, planner_mode = plan_tools(scenario)
        evidence = collect_evidence(scenario, selected_tools)
        diagnosis, diagnostician_mode = diagnose(scenario, evidence)
        allowed_refs = {item["id"] for tool in evidence for item in tool["items"]}
        proposal = propose_action(scenario)
        result = {
            "scenario": scenario_id,
            "planner": planner_mode,
            "diagnostician": diagnostician_mode,
            "planner_fallback": planner_mode != "ollama",
            "diagnosis_fallback": diagnostician_mode != "ollama",
            "read_only_tools": all(tool in READ_TOOLS for tool in selected_tools) and all(tool["mode"] == "read-only" for tool in evidence),
            "evidence_refs_valid": all(reference in allowed_refs for reference in diagnosis["evidence_refs"]),
            "approval_gate_present": proposal["approval_required"] is True,
        }
        if diagnostician_mode == "ollama":
            result["model_root_cause_match"] = diagnosis["root_cause"] == case.get("expected_root_cause")
        results.append(result)
    model_results = [row["model_root_cause_match"] for row in results if "model_root_cause_match" in row]
    return {
        "cases": len(results),
        "read_only_tools_rate": sum(row["read_only_tools"] for row in results) / len(results) if results else 0.0,
        "valid_evidence_rate": sum(row["evidence_refs_valid"] for row in results) / len(results) if results else 0.0,
        "approval_gate_rate": sum(row["approval_gate_present"] for row in results) / len(results) if results else 0.0,
        "valid_tool_call_rate": sum(not row["planner_fallback"] for row in results) / len(results) if LLM_ENABLED and results else None,
        "planner_fallback_rate": sum(row["planner_fallback"] for row in results) / len(results) if LLM_ENABLED and results else None,
        "diagnosis_fallback_rate": sum(row["diagnosis_fallback"] for row in results) / len(results) if LLM_ENABLED and results else None,
        "model_root_cause_accuracy": sum(model_results) / len(model_results) if model_results else None,
        "details": results,
        "scope": "Side-effect-free checks validate the read-only tool boundary, evidence references, and approval gate. Scripted fallback diagnoses are not counted as model accuracy.",
    }
