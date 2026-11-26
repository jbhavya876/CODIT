"""
REST API for Codit — Intelligent Codebase Audit & Architecture Platform.

Uses per-audit isolated GraphHandles when scoped via `codit_audit` cookie, or
the embedded demo seed dataset for un-scoped exploration queries.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.app.services import audit_service, graph_service
from backend.app.services.demo_graph import GraphHandle
from backend.app.services.graph_service import DatabaseUnavailable

router = APIRouter(prefix="/api", tags=["core"])

VALID_TYPES = {"Service", "Database", "API", "Library", "Infrastructure", "Module"}
MAX_LIMIT = 100


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})
        self.code = code
        self.message = message


def _resolve_graph(request: Optional[Request]) -> Optional[GraphHandle]:
    audit_id = audit_service.get_audit_id_from_request(request)
    return audit_service.get_graph_for_audit(audit_id)


def not_found(component_id: str) -> ApiError:
    return ApiError(404, "not_found", f"Component '{component_id}' not found.")


def must_exist(component_id: str, graph: Optional[GraphHandle] = None) -> dict:
    record = graph_service.get_component(component_id, graph=graph)
    if record is None:
        raise not_found(component_id)
    return record


def parse_limit(raw: Optional[int], default: int) -> int:
    if raw is None:
        return default
    if not 1 <= raw <= MAX_LIMIT:
        raise ApiError(400, "bad_request", f"limit must be between 1 and {MAX_LIMIT}.")
    return raw


@router.get("/health")
def health(request: Request):
    try:
        graph = _resolve_graph(request)
        return graph_service.health(graph=graph)
    except DatabaseUnavailable as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "mode": graph_service.mode(), "error": str(exc)},
        )


@router.get("/stats")
def stats(request: Request):
    return graph_service.stats(graph=_resolve_graph(request))


@router.get("/components")
def components(
    request: Request,
    q: str = Query("", description="Component name search substring"),
    type: str = Query("", description="Component type filter"),
    limit: Optional[str] = Query(None, description="Max results to return"),
):
    q_clean = q.strip()
    type_clean = type.strip()
    if type_clean and type_clean not in VALID_TYPES:
        raise ApiError(400, "bad_request", f"type must be one of {sorted(VALID_TYPES)}.")

    limit_int = 25
    if limit is not None:
        try:
            limit_int = int(limit)
        except ValueError:
            raise ApiError(400, "bad_request", "limit must be an integer.")
        if not 1 <= limit_int <= MAX_LIMIT:
            raise ApiError(400, "bad_request", f"limit must be between 1 and {MAX_LIMIT}.")

    return graph_service.search(q=q_clean, type_label=type_clean, limit=limit_int, graph=_resolve_graph(request))


@router.get("/components/{component_id}")
def component(component_id: str, request: Request):
    return must_exist(component_id, graph=_resolve_graph(request))


@router.get("/components/{component_id}/dependencies")
def component_dependencies(component_id: str, request: Request):
    graph = _resolve_graph(request)
    must_exist(component_id, graph=graph)
    return graph_service.dependencies_bundle(component_id, graph=graph)


@router.get("/components/{component_id}/impact")
def component_impact(component_id: str, request: Request):
    graph = _resolve_graph(request)
    must_exist(component_id, graph=graph)
    return graph_service.impact(component_id, graph=graph)


@router.get("/components/{component_id}/criticality")
def component_criticality(component_id: str, request: Request):
    graph = _resolve_graph(request)
    record = must_exist(component_id, graph=graph)
    score = graph_service.criticality(component_id, graph=graph)
    return {"component": record, **score}


@router.get("/criticality")
def criticality_leaderboard(
    request: Request,
    limit: Optional[str] = Query(None, description="Max items to return"),
):
    limit_int = 8
    if limit is not None:
        try:
            limit_int = int(limit)
        except ValueError:
            raise ApiError(400, "bad_request", "limit must be an integer.")
        if not 1 <= limit_int <= MAX_LIMIT:
            raise ApiError(400, "bad_request", f"limit must be between 1 and {MAX_LIMIT}.")
    return graph_service.leaderboard(limit_int, graph=_resolve_graph(request))


@router.get("/path")
def dependency_path(
    request: Request,
    from_: str = Query("", alias="from", description="Source component ID"),
    to: str = Query("", description="Target component ID"),
):
    graph = _resolve_graph(request)
    from_id = from_.strip()
    to_id = to.strip()
    if not from_id or not to_id:
        raise ApiError(400, "bad_request", "Both 'from' and 'to' query parameters are required.")
    if from_id == to_id:
        raise ApiError(400, "bad_request", "'from' and 'to' must be different components.")
    must_exist(from_id, graph=graph)
    must_exist(to_id, graph=graph)
    return graph_service.shortest_path(from_id, to_id, graph=graph)
