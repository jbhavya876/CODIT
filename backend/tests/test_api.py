"""
API tests, run against the embedded demo backend (no CognoDB needed):

    cd backend && python -m pytest tests/ -v

The demo backend and the CognoDB backend implement the same query functions, so
these tests pin the API contract; the Cypher itself can be replayed against a
live instance via database/seed.py's built-in smoke test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root

from app import create_app  # noqa: E402
from database import seed_data  # noqa: E402


class ApiTestClient:
    def __init__(self, app):
        from starlette.testclient import TestClient
        self._tc = TestClient(app, raise_server_exceptions=False)

    def get(self, url, **kwargs):
        res = self._tc.get(url, **kwargs)
        res.get_json = res.json
        return res

    def post(self, url, **kwargs):
        res = self._tc.post(url, **kwargs)
        res.get_json = res.json
        return res


@pytest.fixture()
def client():
    app = create_app({"GRAPH_BACKEND": "demo"})
    return ApiTestClient(app)


# --- basics ----------------------------------------------------------------------


def test_health_reports_demo_backend(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "ok"
    assert body["mode"] == "demo"


def test_stats_match_seed_dataset(client):
    body = client.get("/api/stats").get_json()
    assert body["nodes"]["Service"] == len(seed_data.SERVICES)
    assert body["nodes"]["Database"] == len(seed_data.DATABASES)
    assert body["teams"] == len(seed_data.TEAMS)
    assert sum(body["relationships"].values()) == seed_data.REL_COUNT


def test_search_by_name_and_type_filter(client):
    body = client.get("/api/components?q=postgres").get_json()
    assert len(body) == 1
    assert body[0]["component"]["name"] == "PostgreSQL"

    dbs = client.get("/api/components?type=Database&limit=50").get_json()
    assert len(dbs) == len(seed_data.DATABASES)
    assert all(row["type"] == "Database" for row in dbs)


def test_search_rejects_unknown_type(client):
    res = client.get("/api/components?type=Widget")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "bad_request"


def test_component_detail_includes_owner(client):
    body = client.get("/api/components/svc-payment").get_json()
    assert body["owner"] == "Payments Team"
    assert body["type"] == "Service"


def test_unknown_component_is_404(client):
    res = client.get("/api/components/svc-nope")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "not_found"


# --- graph traversal ---------------------------------------------------------------


def test_direct_dependents_of_postgresql(client):
    body = client.get("/api/components/db-postgresql/dependencies").get_json()
    dependent_names = {row["component"]["name"] for row in body["dependents"]}
    assert {"Auth Service", "Payment Service", "User Profile Service",
            "Order Service", "Analytics Service", "Reporting Service"} <= dependent_names
    assert body["dependencies"] == []  # PostgreSQL depends on nothing


def test_impact_is_multi_hop_and_consistent_with_criticality(client):
    impact = client.get("/api/components/db-postgresql/impact").get_json()
    assert impact["total"] >= 10
    assert impact["max_depth"] >= 2  # the assignment's >=2 hops requirement
    names_direct = {r["component"]["name"] for r in impact["direct"]}
    names_indirect = {r["component"]["name"] for r in impact["indirect"]}
    assert "Auth Service" in names_direct
    assert {"Checkout Service", "Customer Portal"} <= names_indirect
    assert not (names_direct & names_indirect)  # disjoint buckets

    criticality = client.get("/api/components/db-postgresql/criticality").get_json()
    assert criticality["total"] == impact["total"]
    assert criticality["tier"] == "HIGH"


def test_impact_of_leaf_is_empty(client):
    body = client.get("/api/components/svc-customer-portal/impact").get_json()
    assert body["total"] == 0  # nothing depends on the portal


def test_dependency_paths_portal_to_postgresql(client):
    body = client.get("/api/path?from=svc-customer-portal&to=db-postgresql").get_json()
    assert body["found"] is True
    paths = body["paths"]
    assert paths[0]["hops"] >= 2
    # The canonical chain from the assignment brief must appear among the paths.
    chain_names = [[n["name"] for n in p["nodes"]] for p in paths]
    assert ["Customer Portal", "Checkout Service", "Payment Service",
            "Auth Service", "PostgreSQL"] in chain_names


def test_path_not_found_and_validation(client):
    body = client.get("/api/path?from=infra-k8s&to=svc-customer-portal").get_json()
    assert body["found"] is False

    assert client.get("/api/path?from=&to=").status_code == 400
    assert client.get("/api/path?from=svc-cart&to=svc-cart").status_code == 400
    assert client.get("/api/path?from=svc-nope&to=svc-cart").status_code == 404


def test_criticality_leaderboard_ranks_shared_components_first(client):
    body = client.get("/api/criticality").get_json()
    # The container platform legitimately has the largest blast radius.
    assert body[0]["component"]["name"] == "Kubernetes Cluster"
    assert body[0]["tier"] == "HIGH"
    by_name = {row["component"]["name"]: row for row in body}
    pg_crit = client.get("/api/components/db-postgresql/criticality").get_json()
    assert pg_crit["tier"] == "HIGH"
    assert by_name["PostgreSQL"]["reach"] == pg_crit["total"]
    reaches = [row["reach"] for row in body]
    assert reaches == sorted(reaches, reverse=True)


def test_library_vulnerability_style_impact(client):
    # If PyJWT had a flaw, who is transitively at risk? (Log4Shell question.)
    body = client.get("/api/components/lib-pyjwt/impact").get_json()
    affected = {r["component"]["name"] for r in body["direct"] + body["indirect"]}
    assert {"Auth Service", "Payment Service", "Checkout Service"} <= affected


def test_error_envelope_shape(client):
    body = client.get("/api/components/svc-nope").get_json()
    assert set(body["error"]) == {"code", "message"}
