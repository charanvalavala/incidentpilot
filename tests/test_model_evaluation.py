import sys

import pytest

from incidentpilot import model_evaluation


def test_model_evaluation_separates_accuracy_from_fallback(monkeypatch):
    monkeypatch.setattr(model_evaluation, "LLM_ENABLED", True)
    monkeypatch.setattr(model_evaluation, "OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setattr(model_evaluation, "plan_tools", lambda scenario: (["read_logs"], "ollama"))
    monkeypatch.setattr(
        model_evaluation,
        "diagnose_with_model",
        lambda evidence, causes: {
            "summary": "Dependency timeout.",
            "root_cause": "inventory_dependency_latency",
            "confidence": 0.8,
            "evidence_refs": ["log-1"],
        },
    )
    cases = [
        {
            "id": "case-1",
            "summary": "Requests wait on inventory.",
            "expected_root_cause": "inventory_dependency_latency",
            "evidence": [{"tool": "read_logs", "items": [{"id": "log-1", "message": "timeout"}]}],
        }
    ]

    report = model_evaluation.run(cases)

    assert report["valid_tool_call_rate"] == 1.0
    assert report["diagnosis_coverage"] == 1.0
    assert report["diagnosis_fallback_rate"] == 0.0
    assert report["evidence_ref_valid_rate"] == 1.0
    assert report["model_root_cause_accuracy"] == 1.0


def test_model_evaluation_requires_an_enabled_local_model(monkeypatch):
    monkeypatch.setattr(model_evaluation, "LLM_ENABLED", False)

    try:
        model_evaluation.run([{"id": "case-1"}])
    except RuntimeError as error:
        assert "INCIDENT_LLM_ENABLED=true" in str(error)
    else:
        raise AssertionError("Model evaluation should refuse to silently score policy fallback.")


def test_model_evaluation_cli_explains_missing_model(monkeypatch, capsys):
    monkeypatch.setattr(model_evaluation, "LLM_ENABLED", False)
    monkeypatch.setattr(sys, "argv", ["incidentpilot-model-evaluation"])

    with pytest.raises(SystemExit) as error:
        model_evaluation.main()

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "Set INCIDENT_LLM_ENABLED=true" in captured.err
    assert "Traceback" not in captured.err
