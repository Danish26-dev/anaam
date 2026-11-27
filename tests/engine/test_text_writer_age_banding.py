"""Free-text documents must band ages the same way structured CSV/JSON fields do.

Found via dev/input's own practice discharge notes: a Devanagari discharge summary's
"आयु: 97 वर्ष" (age 97) released the EXACT age, while the same patient's registration
CSV row correctly banded it. detection.engine.apply_placeholders treats GENERALIZE_AGE
spans as KEEP (its own docstring: "dates and ages are kept" -- written as a dev helper,
never meant to carry O10's privacy policy), and render_text (the real free-text writer)
never applied any age-banding transformation before calling it. This mattered most for
exactly the patients closest to the top-coded 90+ band (the "97-year-old with a rare
procedure" trap docs/ATTACKS.md names directly): an unbanded 95-99 reads as meaningfully
more identifying than a truthful "90+".
"""
from export.text_writer import render_text, render_text_document


def test_devanagari_age_is_banded_in_free_text():
    text = "मरीज़ का नाम: शालिनी    आयु: 46 वर्ष / महिला"
    rendered, _ = render_text(text, age_band_years=5)
    assert "46" not in rendered
    assert "45-49" in rendered


def test_top_coded_age_is_banded_to_the_open_ended_band():
    text = "आयु: 97 वर्ष / पुरुष"
    rendered, _ = render_text(text, age_band_years=5)
    assert "97" not in rendered
    assert "90+" in rendered


def test_latin_age_label_is_banded():
    text = "Age: 46 Yrs / F"
    rendered, _ = render_text(text, age_band_years=5)
    assert "46" not in rendered
    assert "45-49" in rendered


def test_render_text_document_forwards_age_band_years():
    text = "Patient Name: Test Person\nAge: 97 Yrs / M\n"
    rendered, _ = render_text_document(text, pseudonym="PSN-TEST1234", age_band_years=5)
    assert "97" not in rendered
    assert "90+" in rendered


def test_wider_age_band_configuration_is_respected():
    text = "Age: 46 Yrs / F"
    rendered, _ = render_text(text, age_band_years=10)
    assert "46" not in rendered
    assert "40-49" in rendered
