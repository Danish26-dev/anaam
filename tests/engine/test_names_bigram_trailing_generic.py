"""Unlabeled bigram names whose second token is a generic name-part (Bano, Devi, Kaur,
Singh, Begum, ...) must still be detected whole, not left half-redacted.

Found via dev/truth.json's FHIR narrative text ("Shabana Bano, 27 yrs, female, ..."):
detect_names' bigram path required EVERY token to be individually "identifying"
(BIGRAM's `all(_is_identifying(t) for t in toks)` check), so a real first name plus a
generic surname part -- not identifying on its own per docs/DATASET.md, but part of a
real patient's name together with the first name -- was silently dropped instead of
redacted whole. The label/relation/honorific paths already tolerate this via
trim_name's "keep if ANY token identifies" rule; the bigram path now matches that.
Invented names, not the real practice-data patient.
"""
from detection.engine import DetectionEngine

_NAME_CATEGORIES = {"PERSON_NAME", "PATIENT_NAME", "RELATIVE_NAME"}


def _names(text):
    """The redacted/pseudonymized name spans the real resolver keeps, regardless of
    which of names.py's several overlapping rules won (bigram, honorific, ...) -- what
    matters for a leak check is whether the whole name is covered, not which category
    label the winning candidate carries.
    """
    return [text[s.start:s.end] for s in DetectionEngine().detect_text(text) if s.category in _NAME_CATEGORIES]


def test_bigram_with_trailing_generic_surname_is_detected_whole():
    assert _names("Shabana Bano, 27 yrs, female, SNJ/26/064545") == ["Shabana Bano"]


def test_bigram_with_trailing_generic_surname_variants():
    assert _names("Priya Kaur, 34 yrs, female") == ["Priya Kaur"]
    assert _names("Noor Begum, 52 yrs, female") == ["Noor Begum"]


def test_bigram_of_two_generic_parts_alone_is_still_not_a_name():
    # Neither token individually identifies anyone, and together they are still just
    # generic name parts with no identifying token at all -- correctly not a name.
    assert _names("Kumar Devi, 40 yrs, female") == []


def test_bigram_with_an_ordinary_common_word_is_still_rejected():
    # A plain common-word bigram (not a name at all) must not slip through just
    # because one word happens to be capitalized at a sentence start.
    assert _names("General Hospital, 2 beds available") == []
