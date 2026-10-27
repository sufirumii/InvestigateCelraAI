"""The classifier is the one component whose output an analyst must trust.

These cases are written as an analyst would state them: given this sentence,
the desk must reach this label. No fixture text is presented to the user
anywhere; it exists only to pin the rules down.
"""

from investigatecelra.engine import classify as clf


def label(title: str, body: str = "") -> str:
    return clf.classify(title, body).event_type


def test_missed_endpoint_is_a_trial_failure():
    assert label("Phase 3 study did not meet its primary endpoint") == "trial_failure"


def test_discontinuation_is_separated_from_failure():
    assert label("Company discontinues development of its lead programme") == "program_discontinuation"


def test_clinical_hold_is_a_safety_event():
    assert label("FDA places clinical hold on the trial after a serious adverse event") == "safety_event"


def test_complete_response_letter_is_a_regulatory_rejection():
    assert label("FDA issues complete response letter for the application") == "regulatory_rejection"


def test_approval_is_positive():
    c = clf.classify("FDA approves the therapy for adults with the condition", "")
    assert c.event_type == "regulatory_approval"
    assert c.polarity > 0
    assert not c.is_setback


def test_negation_guard_does_not_flip_an_approval_into_a_rejection():
    c = clf.classify("Regulator approves therapy; no safety signal was observed", "")
    assert c.event_type == "regulatory_approval"


def test_title_evidence_outweighs_body_mentions():
    c = clf.classify(
        "Partnership signed to co-develop the programme",
        "The release also recalls that an earlier study missed its primary endpoint.",
    )
    assert c.event_type == "partnership"


def test_setbacks_are_flagged_consistently():
    for t in ["Trial terminated for futility", "Programme deprioritised in restructuring"]:
        assert clf.classify(t, "").is_setback


def test_phase_detection():
    assert clf.detect_phase("results from the Phase III trial") == "phase 3"
    assert clf.detect_phase("a first-in-human Phase 1 study") == "phase 1"


def test_limitations_are_quoted_verbatim_not_paraphrased():
    body = (
        "The readout was positive. However, the open-label design limits "
        "interpretation of the secondary endpoints. Enrolment continues."
    )
    found = clf.extract_limitations(body)
    assert found
    assert found[0]["statement"] in body


def test_classification_is_deterministic():
    a = clf.classify("Phase 2 trial missed its primary endpoint", "")
    b = clf.classify("Phase 2 trial missed its primary endpoint", "")
    assert a.as_dict() == b.as_dict()
