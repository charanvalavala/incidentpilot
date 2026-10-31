from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from incidentpilot.config import (
    LLM_ENABLED,
    OLLAMA_MODEL,
    MODEL_BACKEND,
    HF_MODEL,
    TRANSFORMERS_METHOD,
)
from incidentpilot.reasoning import diagnose_with_model, plan_tools

ROOT = Path(__file__).resolve().parents[2]
EVAL_PATH = ROOT / "data" / "model-eval-20.jsonl"


def run(cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not LLM_ENABLED and MODEL_BACKEND != "classifier":
        raise RuntimeError(
            "Set INCIDENT_LLM_ENABLED=true and configure the selected language-model backend before running this evaluation."
        )
    if not cases:
        raise ValueError("At least one model evaluation case is required.")
    allowed_causes = sorted({str(case["expected_root_cause"]) for case in cases})
    rows = []
    for case in cases:
        started = time.perf_counter()
        selected_tools, planner_mode = plan_tools({"summary": case["summary"]})
        evidence = [item for item in case["evidence"] if item["tool"] in selected_tools]
        diagnosis = diagnose_with_model(evidence, allowed_causes)
        allowed_refs = {item["id"] for tool in evidence for item in tool["items"]}
        evidence_refs_valid = diagnosis is not None and set(
            diagnosis["evidence_refs"]
        ).issubset(allowed_refs)
        rows.append(
            {
                "case": case["id"],
                "expected_root_cause": case["expected_root_cause"],
                "predicted_root_cause": diagnosis["root_cause"] if diagnosis else None,
                "planner_mode": planner_mode,
                "diagnosis_fallback": diagnosis is None,
                "evidence_refs_valid": evidence_refs_valid,
                "model_root_cause_match": diagnosis is not None
                and diagnosis["root_cause"] == case["expected_root_cause"],
                "latency_seconds": round(time.perf_counter() - started, 2),
            }
        )
        print(f"Evaluated {case['id']}", flush=True)
    count = len(rows)
    model_diagnoses = [row for row in rows if not row["diagnosis_fallback"]]
    report = {
        "model": (
            "TF-IDF + LogisticRegression (20 synthetic training cases)"
            if MODEL_BACKEND == "classifier"
            else HF_MODEL if MODEL_BACKEND == "transformers" else OLLAMA_MODEL
        ),
        "backend": MODEL_BACKEND,
        "transformers_method": (
            TRANSFORMERS_METHOD if MODEL_BACKEND == "transformers" else None
        ),
        "model_revision": (
            "7ae557604adf67be50417f59c2c2f167def9a775"
            if MODEL_BACKEND == "transformers"
            and HF_MODEL == "Qwen/Qwen2.5-0.5B-Instruct"
            else None
        ),
        "diagnosis_method": (
            "TF-IDF supervised classification"
            if MODEL_BACKEND == "classifier"
            else (
                "Conditional likelihood scoring of fixed cause descriptions"
                if MODEL_BACKEND == "transformers"
                and TRANSFORMERS_METHOD == "candidate-scoring"
                else "Schema-validated generated JSON"
            )
        ),
        "cases": count,
        "valid_tool_call_rate": (
            None
            if MODEL_BACKEND == "classifier"
            else sum(row["planner_mode"] != "policy-fallback" for row in rows) / count
        ),
        "end_to_end_accuracy": sum(row["model_root_cause_match"] for row in rows)
        / count,
        "diagnosis_coverage": len(model_diagnoses) / count,
        "diagnosis_fallback_rate": sum(row["diagnosis_fallback"] for row in rows)
        / count,
        "evidence_ref_valid_rate": (
            sum(row["evidence_refs_valid"] for row in model_diagnoses)
            / len(model_diagnoses)
            if model_diagnoses
            else None
        ),
        "model_root_cause_accuracy": (
            sum(row["model_root_cause_match"] for row in model_diagnoses)
            / len(model_diagnoses)
            if model_diagnoses
            else None
        ),
        "accuracy_denominator": len(model_diagnoses),
        "scope": "Hand-authored synthetic cases across four seeded root-cause classes. Accuracy is measured only on valid model diagnoses; fallback cases are reported separately.",
        "details": rows,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports" / "model-evaluation.json"
    )
    parser.add_argument("--cases", type=Path, default=EVAL_PATH)
    arguments = parser.parse_args()
    cases = [
        json.loads(line)
        for line in arguments.cases.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    try:
        report = run(cases)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "details"}, indent=2
        )
    )
    print(f"Wrote {arguments.output}")


if __name__ == "__main__":
    main()
