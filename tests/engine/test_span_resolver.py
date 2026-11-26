from core import interfaces as c
from detection.span_resolver import resolve


def cand(text, surface, category, tier, action=c.REDACT, conf=0.9, source="t", start=None):
    s = text.index(surface) if start is None else start
    return c.SpanCandidate(s, s + len(surface), category, None, conf, tier, source, action)


def show(text, spans):
    return [(text[s.start:s.end], s.category) for s in spans]


def test_name_beside_medicine():
    text = "Mohammad Arif takes Dolo 650 mg"
    got = resolve(text, [
        cand(text, "Mohammad Arif", c.PATIENT_NAME, c.TIER_EXPLICIT_IDENTITY, c.PSEUDONYMIZE),
        cand(text, "Dolo 650 mg", c.MEDICATION, c.TIER_PROTECTED, c.KEEP),
    ])
    assert show(text, got) == [("Mohammad Arif", c.PATIENT_NAME)]


def test_weak_name_inside_drug_is_dropped():
    text = "Ram takes Ramipril 5 mg"
    got = resolve(text, [
        cand(text, "Ram", c.PATIENT_NAME, c.TIER_EXPLICIT_IDENTITY),
        cand(text, "Ramipril", c.PATIENT_NAME, c.TIER_WEAK),
        cand(text, "Ramipril 5 mg", c.MEDICATION, c.TIER_PROTECTED, c.KEEP),
    ])
    assert show(text, got) == [("Ram", c.PATIENT_NAME)]


def test_doctor_protects_weak_token():
    text = "Review with Dr. Ramesh Srivastava."
    got = resolve(text, [
        cand(text, "Ramesh", c.RELATIVE_NAME, c.TIER_WEAK),
        cand(text, "Dr. Ramesh Srivastava", c.DOCTOR, c.TIER_PROTECTED, c.KEEP),
    ])
    assert got == []


def test_direct_identifier_beats_protection():
    text = "Lab ref 8371 9372 5099 Haemoglobin 14.0 g/dL"
    got = resolve(text, [
        cand(text, "8371 9372 5099", c.AADHAAR, c.TIER_DIRECT_ID),
        cand(text, "ref 8371 9372 5099 Haemoglobin", c.LAB, c.TIER_PROTECTED, c.KEEP),
    ])
    assert show(text, got) == [("8371 9372 5099", c.AADHAAR)]


def test_lower_priority_span_is_split_and_marker_dropped():
    text = "C/O Parveez Kakati, H.No. 364"
    got = resolve(text, [
        cand(text, "C/O Parveez Kakati", c.ADDRESS, c.TIER_EXPLICIT_IDENTITY, conf=0.8),
        cand(text, "Parveez Kakati", c.RELATIVE_NAME, c.TIER_EXPLICIT_IDENTITY, conf=0.95),
        cand(text, "H.No. 364", c.HOUSE, c.TIER_EXPLICIT_IDENTITY),
    ])
    assert show(text, got) == [("Parveez Kakati", c.RELATIVE_NAME), ("H.No. 364", c.HOUSE)]


def test_date_inside_history_clause_is_shifted():
    text = "H/O surgery on 12/03/2020, completed"
    got = resolve(text, [
        cand(text, "H/O surgery on 12/03/2020, completed", c.HISTORY, c.TIER_PROTECTED, c.KEEP),
        cand(text, "12/03/2020", c.DATE, c.TIER_QUASI, c.SHIFT_DATE),
    ])
    assert show(text, got) == [("12/03/2020", c.DATE)]


def test_deterministic_order():
    text = "Padmini Reddy 8276233002"
    cands = [
        cand(text, "8276233002", c.PHONE, c.TIER_DIRECT_ID),
        cand(text, "Padmini Reddy", c.PATIENT_NAME, c.TIER_EXPLICIT_IDENTITY),
        cand(text, "Padmini", c.PATIENT_NAME, c.TIER_WEAK),
    ]
    assert show(text, resolve(text, cands)) == show(text, resolve(text, list(reversed(cands))))
