"""Knowledge graph over the intelligence corpus.

Nodes are resolved gazetteer entities plus the events themselves; edges are
derived from co-occurrence within a single document and from structured trial
records. Implemented directly on adjacency dictionaries — a property graph
without a database dependency — with a Cypher export for teams that want to
load the same model into Neo4j.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

EDGE_RULES: list[tuple[str, str, str]] = [
    ("company", "asset",      "DEVELOPS"),
    ("asset",   "target",     "INHIBITS"),
    ("asset",   "indication", "INDICATED_FOR"),
    ("asset",   "modality",   "FORMULATED_AS"),
    ("asset",   "technology", "SUPPORTED_BY"),
    ("company", "target",     "PURSUES"),
    ("company", "indication", "DEVELOPS_FOR"),
    ("company", "modality",   "USES_MODALITY"),
    ("company", "technology", "APPLIES"),
    ("company", "company",    "CO_MENTIONED"),
    ("target",  "indication", "IMPLICATED_IN"),
    ("target",  "modality",   "ADDRESSED_BY"),
    ("modality", "indication", "APPLIED_TO"),
    ("technology", "indication", "SUPPORTS_WORK_IN"),
    ("technology", "target", "SUPPORTS_WORK_ON"),
]

# Company↔company edges are only meaningful for real relationships.
PARTNER_EVENTS = {"partnership", "ma_activity"}


@dataclass
class GraphNode:
    id: str
    label: str
    kind: str
    subtype: str = ""
    weight: float = 0.0
    events: int = 0
    setbacks: int = 0
    tags: set[str] = field(default_factory=set)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "subtype": self.subtype,
            "weight": round(self.weight, 2),
            "events": self.events,
            "setbacks": self.setbacks,
            "tags": sorted(self.tags),
        }


@dataclass
class GraphEdge:
    source: str
    target: str
    rel: str
    weight: float = 0.0
    items: set[str] = field(default_factory=set)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.rel)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "rel": self.rel,
            "weight": round(self.weight, 2),
            "evidence": len(self.items),
            "items": sorted(self.items)[:6],
        }


class KnowledgeGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[tuple[str, str, str], GraphEdge] = {}
        self._adj: dict[str, set[str]] = defaultdict(set)

    # -- construction -----------------------------------------------------
    def add_node(self, node_id: str, label: str, kind: str, subtype: str = "") -> GraphNode:
        node = self.nodes.get(node_id)
        if node is None:
            node = GraphNode(id=node_id, label=label, kind=kind, subtype=subtype)
            self.nodes[node_id] = node
        return node

    def add_edge(self, a: str, b: str, rel: str, weight: float, item_id: str) -> None:
        if a == b:
            return
        src, dst = sorted((a, b))
        key = (src, dst, rel)
        edge = self.edges.get(key)
        if edge is None:
            edge = GraphEdge(source=src, target=dst, rel=rel)
            self.edges[key] = edge
        edge.weight += weight
        edge.items.add(item_id)
        self._adj[src].add(dst)
        self._adj[dst].add(src)

    def ingest_item(self, item: dict) -> None:
        """Add one analysed story to the graph."""
        mentions = item.get("entities") or []
        if not mentions:
            return
        item_id = item["id"]
        signal = float(item.get("signal", {}).get("value", 40.0)) / 100.0
        event_type = item.get("classification", {}).get("eventType", "general")
        is_setback = bool(item.get("classification", {}).get("isSetback"))

        resolved = []
        for m in mentions:
            node = self.add_node(m["id"], m["name"], m["kind"], m.get("subtype", ""))
            node.weight += signal * (1.5 if m.get("inTitle") else 1.0)
            node.events += 1
            if is_setback:
                node.setbacks += 1
            if item.get("sector"):
                node.tags.add(item["sector"])
            resolved.append(m)

        rule_index = {(a, b): rel for a, b, rel in EDGE_RULES}
        for i, left in enumerate(resolved):
            for right in resolved[i + 1:]:
                lk, rk = left["kind"], right["kind"]
                if lk == "company" and rk == "company" and event_type not in PARTNER_EVENTS:
                    continue
                rel = rule_index.get((lk, rk)) or rule_index.get((rk, lk))
                if not rel:
                    continue
                if lk == "company" and rk == "company":
                    rel = "ALLIED_WITH" if event_type == "partnership" else "ACQUISITION_LINK"
                w = signal * (1.0 + 0.5 * (left.get("inTitle", False) or right.get("inTitle", False)))
                self.add_edge(left["id"], right["id"], rel, w, item_id)

    def ingest_trial(self, trial: dict) -> None:
        """Structured registry records give us high-confidence edges."""
        sponsor = trial.get("sponsorEntityId")
        if not sponsor:
            return
        self.add_node(sponsor, trial.get("sponsor", sponsor), "company")
        trial_node_id = f"trial:{trial['id']}"
        self.add_node(trial_node_id, trial.get("nctId") or trial["id"], "trial", trial.get("phase", ""))
        self.add_edge(sponsor, trial_node_id, "SPONSORS", 1.2, trial["id"])
        for eid, name, kind in trial.get("linkedEntities", []):
            self.add_node(eid, name, kind)
            self.add_edge(trial_node_id, eid, "STUDIES", 1.0, trial["id"])

    # -- queries ----------------------------------------------------------
    def degree(self, node_id: str) -> int:
        return len(self._adj.get(node_id, ()))

    def neighbourhood(self, node_id: str, depth: int = 1, limit: int = 90) -> dict:
        if node_id not in self.nodes:
            return {"nodes": [], "edges": []}
        seen = {node_id}
        frontier = deque([(node_id, 0)])
        while frontier:
            current, d = frontier.popleft()
            if d >= depth:
                continue
            for nb in sorted(self._adj.get(current, ()), key=lambda n: -self.nodes[n].weight):
                if nb in seen:
                    continue
                seen.add(nb)
                frontier.append((nb, d + 1))
                if len(seen) >= limit:
                    frontier.clear()
                    break
        return self.subgraph(seen)

    def subgraph(self, node_ids: set[str]) -> dict:
        nodes = [self.nodes[n].as_dict() for n in node_ids if n in self.nodes]
        edges = [
            e.as_dict()
            for e in self.edges.values()
            if e.source in node_ids and e.target in node_ids
        ]
        return {"nodes": nodes, "edges": edges}

    def shortest_path(self, a: str, b: str, max_depth: int = 6) -> list[dict]:
        """Breadth-first path — 'how is this company connected to that target?'"""
        if a not in self.nodes or b not in self.nodes:
            return []
        if a == b:
            return [{"node": self.nodes[a].as_dict(), "rel": None}]
        prev: dict[str, str] = {}
        seen = {a}
        q = deque([(a, 0)])
        found = False
        while q:
            cur, d = q.popleft()
            if d >= max_depth:
                continue
            for nb in self._adj.get(cur, ()):
                if nb in seen:
                    continue
                seen.add(nb)
                prev[nb] = cur
                if nb == b:
                    found = True
                    q.clear()
                    break
                q.append((nb, d + 1))
        if not found:
            return []
        chain = [b]
        while chain[-1] != a:
            chain.append(prev[chain[-1]])
        chain.reverse()
        out = []
        for i, nid in enumerate(chain):
            rel = None
            if i > 0:
                rel = self._relation(chain[i - 1], nid)
            out.append({"node": self.nodes[nid].as_dict(), "rel": rel})
        return out

    def _relation(self, a: str, b: str) -> str | None:
        src, dst = sorted((a, b))
        for (s, d, rel) in self.edges:
            if s == src and d == dst:
                return rel
        return None

    def pagerank(self, damping: float = 0.85, iterations: int = 24) -> dict[str, float]:
        """Plain power iteration over the undirected adjacency."""
        n = len(self.nodes)
        if n == 0:
            return {}
        rank = {k: 1.0 / n for k in self.nodes}
        for _ in range(iterations):
            nxt = {k: (1.0 - damping) / n for k in self.nodes}
            for node, nbrs in self._adj.items():
                if not nbrs:
                    continue
                share = damping * rank.get(node, 0.0) / len(nbrs)
                for nb in nbrs:
                    if nb in nxt:
                        nxt[nb] += share
            rank = nxt
        return rank

    def hubs(self, kind: str | None = None, limit: int = 12) -> list[dict]:
        pr = self.pagerank()
        rows = []
        for nid, node in self.nodes.items():
            if kind and node.kind != kind:
                continue
            d = node.as_dict()
            d["degree"] = self.degree(nid)
            d["centrality"] = round(pr.get(nid, 0.0) * 1000, 3)
            rows.append(d)
        rows.sort(key=lambda r: (-r["centrality"], -r["degree"]))
        return rows[:limit]

    def stats(self) -> dict:
        kinds: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            kinds[n.kind] += 1
        rels: dict[str, int] = defaultdict(int)
        for e in self.edges.values():
            rels[e.rel] += 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "byKind": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
            "byRelationship": dict(sorted(rels.items(), key=lambda kv: -kv[1])),
            "density": round(
                (2 * len(self.edges)) / max(1, len(self.nodes) * (len(self.nodes) - 1)), 6
            ),
        }

    # -- export -----------------------------------------------------------
    def to_cypher(self, limit: int = 4000) -> str:
        """Emit the same graph as Neo4j-loadable Cypher."""
        lines = ["// InvestigateCelra knowledge graph export", "// Generated deterministically from the analysed corpus.", ""]
        for node in list(self.nodes.values())[:limit]:
            label = "".join(p.capitalize() for p in node.kind.split("_")) or "Entity"
            props = (
                f'{{id: "{_esc(node.id)}", name: "{_esc(node.label)}", '
                f'weight: {node.weight:.2f}, events: {node.events}, setbacks: {node.setbacks}}}'
            )
            lines.append(f"MERGE (:{label} {props});")
        lines.append("")
        for edge in list(self.edges.values())[:limit]:
            src = self.nodes[edge.source]
            dst = self.nodes[edge.target]
            ls = "".join(p.capitalize() for p in src.kind.split("_"))
            ld = "".join(p.capitalize() for p in dst.kind.split("_"))
            lines.append(
                f'MATCH (a:{ls} {{id: "{_esc(edge.source)}"}}), (b:{ld} {{id: "{_esc(edge.target)}"}}) '
                f'MERGE (a)-[:{edge.rel} {{weight: {edge.weight:.2f}, evidence: {len(edge.items)}}}]->(b);'
            )
        return "\n".join(lines)


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build(items: list[dict], trials: list[dict] | None = None) -> KnowledgeGraph:
    kg = KnowledgeGraph()
    for item in items:
        kg.ingest_item(item)
    for trial in trials or []:
        kg.ingest_trial(trial)
    return kg
