from incidentpilot import engine, reasoning, store


def test_empty_evidence_references_rejected(monkeypatch):
    monkeypatch.setattr(
        reasoning,
        "generate_json",
        lambda *args: {
            "root_cause": "x",
            "summary": "Cause",
            "confidence": 0.8,
            "evidence_refs": [],
        },
    )
    assert reasoning.diagnose_with_model([], ["x"]) is None


def test_conflicting_diagnosis_escalates_instead_of_using_seeded_action():
    scenario = engine.scenarios()["payment-connection-pool"]
    evidence = engine.collect_evidence(scenario, list(engine.READ_TOOLS))
    proposal = engine.propose_action(
        scenario,
        {"root_cause": "expired_identity_certificate", "evidence_refs": ["log-111"]},
        evidence,
    )
    assert proposal["abstained"]
    assert proposal["action"] == "escalate for human investigation"


def test_policy_uses_observed_evidence_not_hidden_scenario_label(monkeypatch):
    monkeypatch.setattr(engine, "diagnose_with_model", lambda *args: None)
    scenario = engine.scenarios()["payment-connection-pool"]
    scenario["diagnosis"]["root_cause"] = "expired_identity_certificate"
    evidence = engine.collect_evidence(scenario, list(engine.READ_TOOLS))
    diagnosis, _ = engine.diagnose(scenario, evidence)
    assert diagnosis["root_cause"] == "database_connection_pool_exhaustion"
    assert not engine.propose_action(scenario, diagnosis, evidence)["abstained"]


def test_conflicting_observed_causes_escalate():
    evidence = [
        {
            "tool": "read_logs",
            "items": [
                {"id": "a", "message": "connection pool exhausted"},
                {"id": "b", "message": "connection acquire timeout"},
                {"id": "c", "message": "x509 certificate expired"},
                {"id": "d", "message": "certificate renewal failed"},
            ],
        }
    ]
    assert engine.evidence_cause(evidence) == ("insufficient_evidence", [])


def test_low_confidence_triggers_additional_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATABASE_PATH", tmp_path / "iterative.sqlite3")
    store.initialize()
    monkeypatch.setattr(
        engine, "plan_tools", lambda scenario: (["read_logs"], "transformers")
    )
    calls = []

    def diagnose(scenario, evidence):
        calls.append([item["tool"] for item in evidence])
        return {
            "root_cause": "database_connection_pool_exhaustion",
            "summary": "Pool pressure",
            "confidence": 0.4,
            "evidence_refs": [evidence[0]["items"][0]["id"]],
        }, "transformers"

    monkeypatch.setattr(engine, "diagnose", diagnose)
    incident = engine.create("payment-connection-pool")
    assert calls[0] == ["read_logs"]
    assert set(calls[1]) == set(engine.READ_TOOLS)
    assert len(incident["state"]["evidence"]) == 3
