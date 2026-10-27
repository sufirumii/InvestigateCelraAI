"""Title casing repair and analyst preferences."""

from investigatecelra.engine.entities import default_gazetteer
from investigatecelra.engine.normalize import normalize_title
from investigatecelra.engine.preferences import Preferences
from investigatecelra.engine.score import portfolio_component

KEEP = default_gazetteer().cased_tokens()


def fix(title: str) -> str:
    return normalize_title(title, keep=KEEP)


def test_backronym_titles_are_repaired():
    """Registries publish titles that spell the study nickname in capitals."""
    out = fix("Survival imProvement in Lung cancEr iNduced by DenOsUmab theRapy")
    assert out == "Survival improvement in Lung cancer induced by Denosumab therapy"


def test_no_word_is_altered_only_its_case():
    src = "Survival imProvement in Lung cancEr iNduced by DenOsUmab theRapy"
    assert fix(src).lower() == src.lower()


def test_normalisation_is_idempotent():
    src = "A cancEr Study of DenOsUmab"
    assert fix(fix(src)) == fix(src)


def test_acronyms_and_identifiers_survive():
    for title in [
        "AstraZeneca Phase IIIb Study in ER-positive, HER2-negative Breast Cancer",
        "Emtricitabine and Tenofovir Alafenamide (F/TAF) in HIV-1 Infection",
        "FDA and EMA review of NSCLC therapy",
        "A Study of mRNA-1273 and BioNTech Vaccine",
        "pCR and eGFR endpoints in CKD",
    ]:
        assert fix(title) == title


def test_gazetteer_names_are_never_reshaped():
    assert "BioNTech" in KEEP and "AstraZeneca" in KEEP
    assert fix("BioNTech and AstraZeneca report") == "BioNTech and AstraZeneca report"


def test_empty_title_is_safe():
    assert fix("") == ""


# --------------------------------------------------------------- preferences
def test_unconfigured_preferences_are_neutral():
    """An unconfigured desk must rank exactly as it did before the feature."""
    assert Preferences().fit(sector="Oncology", event_type="trial_failure", company_id=None) == 0.5


def test_matching_every_stated_priority_scores_one():
    p = Preferences.from_dict({
        "sectors": ["Oncology"], "eventTypes": ["trial_failure"],
        "companies": ["company:pfizer"], "configured": True,
    })
    assert p.fit(sector="Oncology", event_type="trial_failure", company_id="company:pfizer") == 1.0
    assert p.fit(sector="Immunology", event_type="partnership", company_id="company:other") == 0.0


def test_partial_match_is_between():
    p = Preferences.from_dict({
        "sectors": ["Oncology"], "eventTypes": ["trial_failure"], "configured": True,
    })
    mid = p.fit(sector="Oncology", event_type="partnership", company_id=None)
    assert 0.0 < mid < 1.0


def test_unstated_dimensions_are_ignored_not_penalised():
    """Choosing only a sector must not punish stories for the other axes."""
    p = Preferences.from_dict({"sectors": ["Oncology"], "configured": True})
    assert p.fit(sector="Oncology", event_type="anything", company_id=None) == 1.0


def test_preferences_shift_ranking_without_dominating_it():
    low = portfolio_component(False, 0.0, 0.0)
    high = portfolio_component(False, 0.0, 1.0)
    assert high > low
    assert high <= 1.0
    # A preference match alone cannot outrank a watchlisted, highly relevant story.
    assert portfolio_component(True, 1.0, 0.0) > high


def test_round_trip_through_dict():
    payload = {
        "analyst": "R Kumar", "role": "Competitive intelligence",
        "sectors": ["Oncology"], "eventTypes": ["trial_failure"],
        "companies": ["company:pfizer"], "configured": True,
    }
    assert Preferences.from_dict(payload).as_dict() == payload


def test_describe_reports_what_was_applied():
    p = Preferences.from_dict({"sectors": ["Oncology", "Immunology"], "configured": True})
    lines = p.describe()
    assert any("Oncology" in line for line in lines)
    assert len(lines) == 3


# ------------------------------------------------------ sign-in regressions
def test_sector_vocabulary_is_available_before_any_fetch():
    """Sign-in can run before the first fetch, so the areas must not be
    derived only from the corpus."""
    from investigatecelra.pipeline import sector_vocabulary

    vocab = sector_vocabulary()
    assert len(vocab) >= 5
    assert "Oncology" in vocab
    assert len(set(vocab)) == len(vocab)


def test_saving_preferences_with_companies_writes_the_watchlist():
    """Regression: db.add_watch takes four arguments. Calling it with three
    raised TypeError inside the write and surfaced as a bare 500 — and only
    when the analyst had actually selected a company, so a click-through of
    the sign-in flow never hit it."""
    import os
    import tempfile

    os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "watch.db")
    from investigatecelra import db
    from investigatecelra import pipeline

    db.init()
    prefs = pipeline.save_preferences({
        "analyst": "Test", "sectors": ["Oncology"],
        "eventTypes": ["trial_failure"], "companies": ["company:pfizer"],
    })
    assert prefs.configured
    assert "company:pfizer" in {w["entity_id"] for w in db.get_watchlist()}


def test_deselecting_a_company_removes_it_from_the_watchlist():
    from investigatecelra import db
    from investigatecelra import pipeline

    pipeline.save_preferences({"analyst": "Test", "companies": ["company:pfizer"]})
    pipeline.save_preferences({"analyst": "Test", "companies": []})
    assert "company:pfizer" not in {w["entity_id"] for w in db.get_watchlist()}
