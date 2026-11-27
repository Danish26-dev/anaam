"""Devanagari generic name parts lead a name like their Latin forms. Invented names."""
from detection.engine import DetectionEngine


def _names(text):
    return [text[s.start:s.end] for s in DetectionEngine().detect_text(text) if s.category == "PATIENT_NAME"]


def test_leading_devanagari_generic_part_is_redacted_with_the_name():
    assert _names("मरीज़ का नाम: मोहम्मद आरिफ") == ["मोहम्मद आरिफ"]
    assert _names("नाम: मोहम्मद आरिफ खान") == ["मोहम्मद आरिफ खान"]


def test_generic_part_alone_is_not_a_name():
    assert _names("मोहम्मद") == []


def test_latin_form_unchanged():
    assert _names("Patient Name: Mohammad Arif") == ["Mohammad Arif"]
