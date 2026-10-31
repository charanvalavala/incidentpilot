import json
from functools import lru_cache
from pathlib import Path


def features(evidence):
    rows = []
    for tool in evidence:
        if tool["tool"] == "read_runbook":
            continue
        for item in tool["items"]:
            rows.append(
                str(item.get("message", item.get("name", ""))).replace("_", " ")
            )
    return " ".join(rows)


@lru_cache(maxsize=1)
def model():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    path = Path(__file__).resolve().parents[2] / "data/model-eval-20.jsonl"
    training = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    pipeline = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
        LogisticRegression(
            C=2, class_weight="balanced", max_iter=1000, random_state=42
        ),
    )
    pipeline.fit(
        [features(row["evidence"]) for row in training],
        [row["expected_root_cause"] for row in training],
    )
    return pipeline


def diagnose(evidence):
    text = features(evidence)
    if not text.strip():
        return None
    pipeline = model()
    probabilities = pipeline.predict_proba([text])[0]
    order = probabilities.argsort()[::-1]
    best = int(order[0])
    if (
        probabilities[best] < 0.35
        or probabilities[best] - probabilities[int(order[1])] < 0.05
    ):
        return None
    label = str(pipeline.classes_[best])
    references = [
        item["id"]
        for tool in evidence
        if tool["tool"] != "read_runbook"
        for item in tool["items"]
    ]
    return {
        "summary": "The trained classifier suggests " + label.replace("_", " ") + ".",
        "root_cause": label,
        "confidence": float(probabilities[best]),
        "evidence_refs": references,
        "scoring": "TF-IDF + logistic regression, trained on twenty synthetic cases; confidence is not calibrated",
    }
