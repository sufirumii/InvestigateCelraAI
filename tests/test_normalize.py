from investigatecelra.engine import normalize as nz


def test_simhash_detects_a_near_duplicate_rewrite():
    a = "Regulator approves the therapy for adults with the severe condition after a priority review"
    b = "Regulator approves the therapy for adults with the severe condition following a priority review"
    assert nz.hamming(nz.simhash(a), nz.simhash(b)) <= 7


def test_simhash_separates_unrelated_stories():
    a = "Regulator approves the therapy for adults with the condition"
    b = "Quarterly revenue rose on strong demand in the consumer division"
    assert nz.hamming(nz.simhash(a), nz.simhash(b)) > 7


def test_html_is_stripped_without_losing_word_boundaries():
    out = nz.strip_html("<p>First line.</p><p>Second line.</p>")
    assert "First line." in out and "Second line." in out
    assert "<" not in out


def test_sentence_splitting_survives_abbreviations():
    text = (
        "The therapy was approved by the U.S. FDA in March of this year. "
        "Enrolment in the confirmatory study then closed to new participants."
    )
    assert len(nz.sentences(text)) == 2


def test_key_figures_are_extracted_with_their_kind():
    kinds = {f["kind"] for f in nz.key_figures("HR=0.71, p=0.004 across 512 patients")}
    assert {"hazard ratio", "p-value", "patients"} <= kinds
