# SPDX-License-Identifier: Apache-2.0
"""Health, metadata and evaluation results."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from vigil import MODEL_VERSION
from vigil.api.deps import Runtime, Svc

router = APIRouter(tags=["meta"])
_RESULTS = [
    Path("artifacts/eval/results.json"),
    Path(__file__).resolve().parents[2] / "web" / "results.json",
]


@router.get("/healthz", summary="Liveness")
async def healthz() -> dict[str, str]:
    """Process is up."""
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness")
async def readyz(svc: Svc, rt: Runtime) -> dict[str, object]:
    """Dependencies are constructed. Gemini is optional and never affects readiness."""
    svc.network()
    return {"status": "ready", "agents": rt.mode, "llm_enabled": svc.llm is not None}


@router.get("/v1/meta", summary="Version and configuration (no secrets)")
async def meta(svc: Svc, rt: Runtime) -> dict[str, object]:
    """What this deployment is running."""
    s = svc.settings
    return {
        "name": "Vigil",
        "model_version": MODEL_VERSION,
        "env": s.env,
        "auth_mode": s.auth_mode,
        "llm_enabled": svc.llm is not None,
        "agent_mode": rt.mode,
        "models": {"reasoning": s.model_reasoning, "fast": s.model_fast, "live": s.model_live},
        "languages": ["en", "hi", "te"],
        "a2a": s.a2a_enabled,
        "data": "All demo data is synthetic. No real customer data is processed.",
        "decision_policy": "The tier is computed by a deterministic, explainable model. Gemini only explains and can only add concern.",
    }


@router.get("/v1/eval/results", summary="Latest offline evaluation")
async def eval_results() -> dict[str, object]:
    """Results of ``vigil-eval`` on synthetic data (see docs/EVALUATION.md for limits)."""
    for p in _RESULTS:
        if p.is_file():
            data: dict[str, object] = json.loads(p.read_text(encoding="utf-8"))
            return data
    raise HTTPException(404, "Run `vigil-eval` to generate results.")
