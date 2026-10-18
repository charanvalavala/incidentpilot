from incidentpilot import engine


def test_policy_evaluation_does_not_count_scripted_labels_as_model_accuracy(monkeypatch):
    monkeypatch.setattr(engine, "plan_tools", lambda scenario: (["read_logs", "read_metrics", "read_runbook"], "policy-fallback"))
    monkeypatch.setattr(engine, "diagnose_with_model", lambda evidence, causes: None)
    cases = [{"scenario": "payment-connection-pool", "expected_root_cause": "database_connection_pool_exhaustion"}]

    report = engine.evaluate_cases(cases)

    assert report["cases"] == 1
    assert report["read_only_tools_rate"] == 1.0
    assert report["valid_evidence_rate"] == 1.0
    assert report["approval_gate_rate"] == 1.0
    assert report["model_root_cause_accuracy"] is None
    assert report["valid_tool_call_rate"] is None
    assert report["diagnosis_fallback_rate"] is None
