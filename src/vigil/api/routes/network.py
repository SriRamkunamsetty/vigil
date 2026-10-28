# SPDX-License-Identifier: Apache-2.0
"""Mule-network investigation and cross-bank signal exchange."""

from __future__ import annotations

import base64
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from vigil.api.deps import Caller, Svc
from vigil.network.exchange import RateLimited, SignalLookup
from vigil.obs import audit_logger

router = APIRouter(prefix="/v1", tags=["network"])
RingId = Annotated[str, Path(pattern=r"^R-\d{2,4}$")]


@router.get("/network/rings", summary="Suspected mule rings in the demo graph")
async def rings(svc: Svc) -> dict[str, object]:
    """Ring summaries (synthetic data only)."""
    net, res = svc.network()
    return {
        "accounts": len(net.accounts),
        "transfers": len(net.transfers),
        "flagged_accounts": sum(1 for n in res.nodes.values() if n.score >= 0.5),
        "rings": [
            {
                "ring_id": r.ring_id,
                "accounts": len(r.members),
                "victims": r.victims,
                "exposure_inr": r.exposure_inr,
                "score": r.score,
                "layering_depth": r.layering_depth,
            }
            for r in res.rings
        ],
    }


@router.get("/network/rings/{ring_id}", summary="One ring with graph and case note")
async def ring_detail(ring_id: RingId, svc: Svc, ai: bool = True) -> dict[str, object]:
    """Graph payload plus a case note (Gemini-written if enabled, otherwise deterministic)."""
    view = svc.ring_view(ring_id)
    if view is None:
        raise HTTPException(404, "Unknown ring.")
    _, res = svc.network()
    ring = next(r for r in res.rings if r.ring_id == ring_id)
    note = await svc.composer.case_note(ring) if (ai and svc.composer) else ring.narrative
    top = sorted((res.nodes[m] for m in ring.members), key=lambda n: -n.score)[:6]
    return {**view, "case_note": note, "top_accounts": [n.model_dump() for n in top]}


class ApprovalIn(BaseModel):
    """Explicit human approval."""

    approved: bool
    analyst: str = Field(
        min_length=2, max_length=64, description="Who approved (for the audit trail)."
    )


@router.post(
    "/network/rings/{ring_id}/publish", summary="Share a ring's hashed identifiers (human-approved)"
)
async def publish_ring(
    ring_id: RingId, body: ApprovalIn, svc: Svc, caller: Caller
) -> dict[str, object]:
    """Publishes keyed hashes to the consortium. Refuses unless a human approved."""
    if not body.approved:
        raise HTTPException(400, "Publishing requires explicit human approval.")
    _, res = svc.network()
    ring = next((r for r in res.rings if r.ring_id == ring_id), None)
    if ring is None:
        raise HTTPException(404, "Unknown ring.")
    try:
        for acct in ring.members:
            svc.exchange.publish(caller, "payee", acct)
    except RateLimited as e:
        raise HTTPException(429, "Publishing too fast for this institution.") from e
    audit_logger.info(
        "ring_published",
        extra={
            "caller": caller,
            "ring_id": ring_id,
            "count": len(ring.members),
            "approved_by": body.analyst,
        },
    )
    return {"published": len(ring.members), "reporter": caller, "stats": svc.exchange.stats()}


Kind = Literal["payee", "account", "phone", "device"]


class SignalIn(BaseModel):
    """Identifier to publish, look up or retract."""

    kind: Kind = "payee"
    identifier: str = Field(min_length=3, max_length=256)
    confidence: float = Field(0.9, ge=0, le=1)


@router.post("/signals/publish", summary="Publish a hashed signal")
async def publish(body: SignalIn, svc: Svc, caller: Caller) -> dict[str, object]:
    """The identifier is hashed immediately and never stored or logged."""
    try:
        svc.exchange.publish(caller, body.kind, body.identifier, body.confidence)
    except RateLimited as e:
        raise HTTPException(429, "Publishing too fast for this institution.") from e
    audit_logger.info("signal_published", extra={"caller": caller, "kind": body.kind})
    return {
        "status": "published",
        "lookup": svc.exchange.lookup(body.kind, body.identifier).model_dump(),
    }


@router.post("/signals/lookup", response_model=SignalLookup, summary="Look up an identifier")
async def lookup(body: SignalIn, svc: Svc) -> SignalLookup:
    """Returns no reporter identities, only the count and corroboration state."""
    return svc.exchange.lookup(body.kind, body.identifier)


@router.post("/signals/retract", summary="Withdraw your own report")
async def retract(body: SignalIn, svc: Svc, caller: Caller) -> dict[str, bool]:
    """Lets an institution withdraw a mistaken report (appeals)."""
    ok = svc.exchange.retract(caller, body.kind, body.identifier)
    audit_logger.info("signal_retracted", extra={"caller": caller, "kind": body.kind, "found": ok})
    return {"retracted": ok}


@router.get("/signals/stats", summary="Aggregate counts")
async def stats(svc: Svc) -> dict[str, int]:
    """No identifiers are exposed."""
    return svc.exchange.stats()


@router.get("/signals/bloom", summary="Bloom filter of corroborated signals")
async def bloom(svc: Svc, fp_rate: float = 0.01) -> dict[str, object]:
    """Compact export for institution-side caches (no false negatives)."""
    fp_rate = min(max(fp_rate, 0.0001), 0.2)
    bf = svc.exchange.export_bloom(fp_rate)
    return {
        "m_bits": bf.m,
        "k_hashes": bf.k,
        "fp_rate": fp_rate,
        "bits_b64": base64.b64encode(bytes(bf.bits)).decode(),
    }
