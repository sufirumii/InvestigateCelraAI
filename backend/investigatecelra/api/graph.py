"""Knowledge graph endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from .. import pipeline

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("")
def graph_view(
    focus: str | None = None,
    depth: int = Query(2, ge=1, le=5),
    kinds: str | None = None,
    limit: int = Query(120, ge=10, le=600),
) -> dict:
    """Full graph, or the neighbourhood around a focus node."""
    g = pipeline.store().graph
    if focus:
        if focus not in g.nodes:
            raise HTTPException(status_code=404, detail="node not in graph")
        data = g.neighbourhood(focus, depth=depth, limit=limit)
    else:
        wanted = set(kinds.split(",")) if kinds else None
        candidates = [
            n for n in g.nodes.values() if not wanted or n.kind in wanted
        ]
        candidates.sort(key=lambda n: -(n.weight + g.degree(n.id)))
        data = g.subgraph({n.id for n in candidates[:limit]})

    stats = g.stats()
    return {
        **data,
        "focus": focus,
        # `nodes`/`edges` describe what was returned; `total` is the whole
        # graph, so the toolbar can say "83 of 214 entities" honestly.
        "stats": {
            **stats,
            "nodes": len(data["nodes"]),
            "edges": len(data["edges"]),
            "total": stats["nodes"],
            "totalEdges": stats["edges"],
        },
        "legend": sorted({n["kind"] for n in data["nodes"]}),
    }


@router.get("/node/{node_id:path}")
def node_detail(node_id: str) -> dict:
    store = pipeline.store()
    g = store.graph
    node = g.nodes.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="node not in graph")

    edges = [
        e.as_dict() for e in g.edges.values() if node_id in (e.source, e.target)
    ]
    edges.sort(key=lambda e: -e["weight"])
    item_ids = {i for e in g.edges.values() if node_id in (e.source, e.target) for i in e.items}

    from .edition import _compact

    related = [store.by_id[i] for i in item_ids if i in store.by_id]
    related.sort(key=lambda i: -i["signal"]["value"])

    return {
        "node": {**node.as_dict(), "degree": g.degree(node_id)},
        "edges": edges[:40],
        "neighbours": [
            {**g.nodes[n].as_dict(), "degree": g.degree(n)}
            for n in sorted(g._adj.get(node_id, ()), key=lambda x: -g.nodes[x].weight)[:24]
        ],
        "items": [_compact(i) for i in related[:12]],
    }


@router.get("/path")
def path(source: str, target: str, maxDepth: int = Query(6, ge=2, le=8)) -> dict:
    g = pipeline.store().graph
    chain = g.shortest_path(source, target, max_depth=maxDepth)
    return {
        "found": bool(chain),
        "length": max(0, len(chain) - 1),
        "path": chain,
    }


@router.get("/hubs")
def hubs(kind: str | None = None, limit: int = Query(12, ge=3, le=40)) -> dict:
    g = pipeline.store().graph
    return {"kind": kind, "hubs": g.hubs(kind=kind, limit=limit)}


@router.get("/export.cypher", response_class=PlainTextResponse)
def export_cypher() -> str:
    """Load the same model into Neo4j when a team wants server-side traversal."""
    return pipeline.store().graph.to_cypher()
