# SPDX-License-Identifier: Apache-2.0
"""Agent2Agent (A2A) exposure: each Vigil agent gets its own agent card and RPC route.

This lets another organisation's agent (for example a bank's fraud-ops agent)
discover Vigil's skills from ``/a2a/<name>/.well-known/agent-card.json`` and call
them over JSON-RPC. The routes sit behind the same API-key middleware as ``/v1``.
"""

from __future__ import annotations

from urllib.parse import urlparse

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models import BaseLlm
from starlette.applications import Starlette

from vigil.agents.adk_agents import build_agents, specialists
from vigil.services import Services


def build_a2a_apps(
    svc: Services, public_base_url: str, model: str | BaseLlm | None = None
) -> dict[str, Starlette]:
    """Builds one A2A Starlette app per agent.

    Args:
        svc: Shared services.
        public_base_url: URL clients use to reach this service (goes in the cards).
        model: Optional model override (tests).

    Returns:
        Mapping of agent name to a Starlette app whose routes are attached when
        its lifespan starts (see :func:`vigil.api.main.lifespan`).
    """
    u = urlparse(public_base_url)
    host = u.hostname or "localhost"
    port = u.port or (443 if u.scheme == "https" else 80)
    root = build_agents(svc, model)
    agents = {"vigil": root, **specialists(build_agents(svc, model))}
    return {
        name: to_a2a(
            agent, host=host, port=port, protocol=u.scheme or "http", rpc_path=f"a2a/{name}"
        )
        for name, agent in agents.items()
    }
