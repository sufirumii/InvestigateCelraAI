from investigatecelra.engine.entities import default_gazetteer, primary_company


def scan(text, title=""):
    """Mentions for a document, exactly as the pipeline builds them."""
    return default_gazetteer().extract(title, text)


def test_acronym_targets_require_exact_case():
    """Regression: the target MET must not match the ordinary verb 'met'.

    Before the strict-case rule for short acronyms, 'met' in "met its primary
    endpoint" resolved to the MET receptor and dominated every entity list.
    """
    hits = {m.entity.id for m in scan("The study met its primary endpoint.")}
    assert "target:met" not in hits
    hits = {m.entity.id for m in scan("An inhibitor of MET was evaluated.")}
    assert "target:met" in hits


def test_longest_match_wins():
    names = {m.entity.name for m in scan("Bristol Myers Squibb reported results")}
    assert "Bristol Myers Squibb" in names


def test_aliases_resolve_to_the_canonical_entity():
    ids = {m.entity.id for m in scan("Results were reported by MSD this morning.")}
    assert "company:merck-and-co" in ids


def test_primary_company_prefers_the_title():
    mentions = scan("Pfizer and Novartis both commented.", title="Novartis reports readout")
    top = primary_company(mentions)
    assert top is not None and top.name == "Novartis"


def test_title_mentions_are_flagged():
    mentions = scan("body text", title="Pfizer reports")
    assert any(m.in_title for m in mentions)


def test_core_coverage_companies_carry_metadata():
    g = default_gazetteer()
    core = [e for e in g.entities.values() if e.meta.get("coverage") == "core"]
    assert len(core) >= 25
    assert all(e.kind == "company" for e in core)
    assert sum(1 for e in core if e.meta.get("ticker")) >= 25
