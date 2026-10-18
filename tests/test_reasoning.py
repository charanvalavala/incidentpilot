from incidentpilot import reasoning


def test_planner_falls_back_when_model_requests_unknown_tool(monkeypatch):
    monkeypatch.setattr(reasoning, "generate_json", lambda system, payload: {"tools": ["write_to_cluster"]})

    tools, mode = reasoning.plan_tools({"summary": "latency is rising"})

    assert tools == ["read_logs", "read_metrics", "read_runbook"]
    assert mode == "policy-fallback"


def test_diagnosis_rejects_evidence_ids_outside_the_tool_results(monkeypatch):
    evidence = [{"tool": "read_logs", "items": [{"id": "log-1", "message": "timeout"}]}]
    monkeypatch.setattr(
        reasoning,
        "generate_json",
        lambda system, payload: {
            "summary": "A dependency timed out.",
            "root_cause": "inventory_dependency_latency",
            "confidence": 0.8,
            "evidence_refs": ["log-not-present"],
        },
    )

    assert reasoning.diagnose_with_model(evidence, ["inventory_dependency_latency"]) is None


def test_diagnosis_accepts_only_allowed_causes_and_evidence(monkeypatch):
    evidence = [{"tool": "read_logs", "items": [{"id": "log-1", "message": "timeout"}]}]
    monkeypatch.setattr(
        reasoning,
        "generate_json",
        lambda system, payload: {
            "summary": "A dependency timed out.",
            "root_cause": "inventory_dependency_latency",
            "confidence": 0.8,
            "evidence_refs": ["log-1"],
        },
    )

    result = reasoning.diagnose_with_model(evidence, ["inventory_dependency_latency"])

    assert result["root_cause"] == "inventory_dependency_latency"
    assert result["evidence_refs"] == ["log-1"]
