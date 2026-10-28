# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from vigil.agents.runtime import AgentRuntime
from vigil.services import Services


def get_svc(request: Request) -> Services:
    """Returns the app's :class:`Services`."""
    svc: Services = request.app.state.services
    return svc


def get_runtime(request: Request) -> AgentRuntime:
    """Returns the app's :class:`AgentRuntime`."""
    rt: AgentRuntime = request.app.state.runtime
    return rt


def get_caller(request: Request) -> str:
    """Institution/caller identity set by the security middleware."""
    return str(request.scope.get("state", {}).get("caller", "public"))


Svc = Annotated[Services, Depends(get_svc)]
Runtime = Annotated[AgentRuntime, Depends(get_runtime)]
Caller = Annotated[str, Depends(get_caller)]
