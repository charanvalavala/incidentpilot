from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(
    os.getenv("INCIDENT_DB", str(ROOT / "data" / "runtime" / "incidents.sqlite3"))
)
STATIC_DIR = ROOT / "static"
SCENARIOS_PATH = ROOT / "data" / "scenarios.json"
LLM_ENABLED = os.getenv("INCIDENT_LLM_ENABLED", "false").lower() == "true"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
MODEL_BACKEND = os.getenv("INCIDENT_MODEL_BACKEND", "classifier")
HF_MODEL = os.getenv("INCIDENT_HF_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
TRANSFORMERS_METHOD = os.getenv("INCIDENT_TRANSFORMERS_METHOD", "candidate-scoring")
