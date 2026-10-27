"""API contract tests.

These run against an empty database on purpose. The desk has no bundled
corpus, so the correct behaviour with no network is to serve valid, empty
responses rather than to invent content.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ["ALLOW_NETWORK"] = "false"
os.environ["DATABASE_PATH"] = "/tmp/investigatecelra-test.db"

from investigatecelra.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", [
    "/api/health", "/api/meta", "/api/edition", "/api/items", "/api/setbacks",
    "/api/markets", "/api/companies", "/api/preferences",
    "/api/method", "/api/excelra", "/api/trials", "/api/search?q=trial",
    "/api/export/brief.md", "/api/export/signals.csv",
])
def test_endpoint_responds(client, path):
    assert client.get(path).status_code == 200


def test_graph_api_is_gone(client):
    """The knowledge graph was removed; no API route should still answer."""
    for path in ("/api/graph", "/api/graph/hubs", "/api/graph/export.cypher"):
        assert client.get(path).status_code == 404


def test_no_graph_assets_remain(client):
    """The SPA catch-all will serve index.html for any path, so check the
    shipped frontend itself rather than the response code."""
    from pathlib import Path

    frontend = Path(__file__).resolve().parent.parent / "frontend"
    assert not (frontend / "graph.html").exists()
    assert not (frontend / "js" / "graphview.js").exists()
    assert not (frontend / "js" / "popout.js").exists()
    assert not (frontend / "js" / "views" / "graph.js").exists()
    assert "#/graph" not in (frontend / "js" / "app.js").read_text()


def test_edition_is_empty_rather_than_fabricated(client):
    body = client.get("/api/edition").json()
    assert body["lead"] is None
    assert body["features"] == []
    assert body["stats"]["analysed"] == 0


def test_refresh_refuses_to_run_without_network(client):
    r = client.post("/api/refresh")
    assert r.status_code >= 400
    assert "network" in r.text.lower()


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "InvestigateCelra" in r.text


def test_unknown_item_is_a_404(client):
    assert client.get("/api/items/does-not-exist").status_code == 404
