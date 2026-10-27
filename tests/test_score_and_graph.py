from investigatecelra.engine import graph as kg
from investigatecelra.engine import score


def sample_score(**over):
    kwargs = dict(
        age_days=1.0, half_life=9.0, tier="registry", event_weight=0.9,
        classification_confidence=0.8, phase_weight=0.9,
        entity_kinds={"company": 1, "target": 1, "indication": 1},
        distinct_sources=3, on_watchlist=True, relevance_strength=0.7,
    )
    kwargs.update(over)
    return score.compute(**kwargs)


def test_score_is_bounded():
    hot = sample_score()
    cold = sample_score(
        age_days=400.0, tier="unknown", event_weight=0.1,
        classification_confidence=0.1, phase_weight=0.1,
        entity_kinds={}, distinct_sources=1, on_watchlist=False,
        relevance_strength=0.0,
    )
    assert 0.0 <= cold.value < hot.value <= 100.0


def test_bands_are_ordered_and_exhaustive():
    assert score.band(72.0) == "critical"
    assert score.band(58.0) == "high"
    assert score.band(42.0) == "moderate"
    assert score.band(41.9) == "routine"


def test_weights_sum_to_one():
    assert abs(sum(score.WEIGHTS.values()) - 1.0) < 1e-9


def test_components_reconstruct_the_total():
    s = sample_score().as_dict()
    rebuilt = sum(c["contribution"] for c in s["components"].values())
    assert abs(rebuilt - s["value"]) < 0.2


def test_recency_decays_by_half_over_one_half_life():
    fresh = score.recency_component(0.0, 9.0)
    aged = score.recency_component(9.0, 9.0)
    assert abs(aged - fresh / 2) < 1e-6


def build_graph():
    g = kg.KnowledgeGraph()
    g.add_node("a", "Alpha Ltd", "company")
    g.add_node("b", "BX-1", "asset")
    g.add_node("c", "KRAS", "target")
    g.add_edge("a", "b", "DEVELOPS", 1.0, "item1")
    g.add_edge("b", "c", "INHIBITS", 1.0, "item1")
    return g


def test_shortest_path_is_symmetric():
    g = build_graph()
    assert len(g.shortest_path("a", "c")) == len(g.shortest_path("c", "a")) == 3


def test_shortest_path_returns_empty_for_unknown_nodes():
    assert build_graph().shortest_path("a", "missing") == []


def test_pagerank_ranks_the_hub_first():
    g = kg.KnowledgeGraph()
    g.add_node("hub", "Hub", "company")
    for i in range(5):
        g.add_node(f"n{i}", f"N{i}", "asset")
        g.add_edge("hub", f"n{i}", "DEVELOPS", 1.0, f"item{i}")
    assert g.hubs(limit=1)[0]["id"] == "hub"


def test_cypher_export_is_valid_looking_and_escaped():
    g = kg.KnowledgeGraph()
    g.add_node("a", "O'Neill Therapeutics", "company")
    g.add_node("b", "BX-1", "asset")
    g.add_edge("a", "b", "DEVELOPS", 1.0, "item1")
    cypher = g.to_cypher()
    assert "MERGE" in cypher and "DEVELOPS" in cypher
    assert "O\\'Neill" in cypher or "O''Neill" in cypher or "O\'Neill" in cypher


def test_graph_stats_are_consistent():
    st = build_graph().stats()
    assert st["nodes"] == 3 and st["edges"] == 2
