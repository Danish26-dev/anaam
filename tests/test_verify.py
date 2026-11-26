import json

import pytest

from src import contracts as c
from src.detection.engine import DetectionEngine
from src.verify.clinical import clinical_loss
from src.verify.release import FileCandidate, ReleaseGate
from src.verify import structure as st

SECRET = "s3cr3t-value-xyz"


def make_gate(secret=SECRET):
    e = DetectionEngine()
    for name, role in [("Dorje Lhamo", "patient"), ("Venkatesh Kurian", "relative"), ("Venkatesh Rao", "doctor"),
                       ("रुचिका मेनन", "patient")]:
        e.lexicon.add_name(name, role)
    e.lexicon.add_id("KMC-2026-04512", c.MRN)
    e.lexicon.add_id("+91 98765 43210", c.PHONE)
    e.lexicon.add_place("Chandpur Kalan")
    g = ReleaseGate(e, allowed_tokens={"PSN-AB12CD34EF56GH78"}, secret=secret)
    g.prepare()
    return g


def codes(g, text, **kw):
    return g.verify_file(FileCandidate(text=text, **kw))


def test_clean_output_is_released():
    g = make_gate()
    r = codes(g, "[PATIENT] PSN-AB12CD34EF56GH78 BP 128/84. Tab Metformin 500 mg 1-0-1 x 14 days. Seen by Dr. Venkatesh Rao.")
    assert r.passed and r.terminal_action == c.RELEASE


@pytest.mark.parametrize("text,code", [
    ("Visitor Dorje was here", "KNOWN_NAME"),
    ("relative Kurian called", "KNOWN_NAME"),
    ("ref 04512 filed", "KNOWN_ID"),
    ("call 98765-43210 now", "KNOWN_ID"),
    ("lives in Chandpur Kalan", "KNOWN_PLACE"),
    ("नाम रुचिका", "KNOWN_NAME"),
])
def test_known_values_are_found_even_without_a_detector(text, code):
    r = codes(make_gate(), text)
    assert not r.passed and code in r.safe_reason_codes


def test_doctor_token_inside_doctor_line_is_allowed_but_not_elsewhere():
    g = make_gate()
    assert codes(g, "Review with Dr. Venkatesh Rao.").passed
    assert "KNOWN_NAME" in codes(g, "Venkatesh sahab ka BP 120/80").safe_reason_codes


def test_full_doctor_name_without_prefix_is_allowed():
    g = make_gate()
    assert codes(g, "09:40 - Venkatesh Rao took round.").passed
    assert not codes(g, "09:40 - Venkatesh Kurian took round.").passed


def test_encoded_payload_leak_is_found():
    import base64
    blob = base64.b64encode(b"Consent witnessed by Dorje Lhamo, phone 98765 43210.").decode()
    r = codes(make_gate(), json.dumps({"scan": blob}), fmt="json")
    assert not r.passed
    assert any(x in r.safe_reason_codes for x in ("KNOWN_NAME", "KNOWN_ID"))


def test_residual_detector_catches_unknown_identifier():
    r = codes(make_gate(), "Contact: 7012345678 for results")
    assert not r.passed and any(x.startswith("RESIDUAL_") for x in r.safe_reason_codes)


def test_findings_never_contain_values():
    r = codes(make_gate(), "Dorje Lhamo 98765 43210")
    blob = json.dumps(r.safe_reason_codes) + json.dumps([f.__dict__ for f in r.findings])
    for v in ("Dorje", "Lhamo", "98765", "43210"):
        assert v not in blob


def test_allowed_generalizations():
    g = make_gate()
    assert codes(g, "Age 45-49, PIN 226***, admitted 12-03-2026").passed


def test_full_pin_flagged_unless_policy_allows():
    g = make_gate()
    assert not codes(g, "PIN: 226012").passed
    g.leaks.allow_full_pin = True
    assert codes(g, "PIN: 226012").passed


def test_rescrub_then_release():
    g = make_gate()
    cand = FileCandidate(text="Seen: Dorje at gate, mob 98765 43210. BP 120/80.", original_text=None)
    res, fixed = g.verify_and_fix(cand)
    assert res.passed and "Dorje" not in fixed.text and "98765" not in fixed.text and "BP 120/80" in fixed.text


def test_unfixable_goes_to_quarantine():
    g = make_gate()
    cand = FileCandidate(text="{ not json Dorje", fmt="json")
    res, _ = g.verify_and_fix(cand)
    assert not res.passed and res.terminal_action == c.QUARANTINE


def test_secret_in_output_aborts():
    r = codes(make_gate(), f"debug {SECRET}")
    assert r.terminal_action == c.ABORT_RELEASE and r.safe_reason_codes == ["SECRET_IN_OUTPUT"]


def test_clinical_loss_detected_by_category():
    original = "BP 128/84. Tab Metformin 500 mg 1-0-1 x 14 days. Dr. Venkatesh Rao."
    assert clinical_loss(original, original) == {}
    lost = clinical_loss(original, "[REDACTED]. [REDACTED]. Dr. Venkatesh Rao.")
    assert lost.get(c.VITAL) == 1 and lost.get(c.MEDICATION, 0) >= 1 and c.DOCTOR not in lost


def test_clinical_loss_blocks_release():
    g = make_gate()
    r = codes(g, "[REDACTED] only", original_text="BP 128/84. Tab Metformin 500 mg 1-0-1 x 14 days.")
    assert not r.passed and any(x.startswith("CLINICAL_LOSS_") for x in r.safe_reason_codes)


def test_csv_shape_and_json_shape():
    assert st.check_csv("a,b\n1,2\n", ",", 2, 1) == []
    assert "CSV_ROW_COUNT" in st.check_csv("a,b\n1,2\n", ",", 2, 5)
    assert "JSON_PATHS_LOST" in st.check_json_shape({"a": {"b": 1}}, {"a": {}})
    assert "JSON_TYPE_CHANGED" in st.check_json_shape({"a": 1}, {"a": "x"})
    assert st.check_json_shape({"age": 48}, {"age": "45-49"}, exempt_prefixes=("/age",)) == []


def test_fhir_reference_resolution():
    ok = {"resourceType": "Bundle", "entry": [{"fullUrl": "urn:uuid:1", "resource": {"resourceType": "Patient", "id": "1"}},
                                              {"fullUrl": "urn:uuid:2", "resource": {"resourceType": "Encounter", "id": "2",
                                                                                     "subject": {"reference": "urn:uuid:1"}}}]}
    assert st.check_fhir_references(ok) == []
    ok["entry"][1]["resource"]["subject"]["reference"] = "urn:uuid:gone"
    assert st.check_fhir_references(ok) == ["FHIR_UNRESOLVED_REFERENCE"]


def test_pseudonym_must_appear():
    g = make_gate()
    r = codes(g, "[PATIENT] note", pseudonyms=("PSN-AB12CD34EF56GH78",))
    assert "PSEUDONYM_MISSING" in r.safe_reason_codes


def test_release_level_checks():
    g = make_gate()
    report = {"files": [{"input_sha256": "a", "output": "sanitized/x.txt", "status": "sanitized"},
                        {"input_sha256": "b", "output": None, "status": "quarantined"}],
              "counts": {"files_total": 2, "files_sanitized": 1, "files_quarantined": 1}}
    records = [{"file": "sanitized/x.txt", "loc": "doc", "patient": "PSN-AB12CD34EF56GH78"}]
    assert g.verify_release(report, records, {"x.txt"}, {"a", "b"}).passed
    assert g.verify_release(report, records, {"x.txt"}, {"a", "b", "c"}).safe_reason_codes == ["UNACCOUNTED_INPUT"]
    bad = dict(report, counts={"files_total": 9, "files_sanitized": 1, "files_quarantined": 1})
    assert "REPORT_COUNTS_INCONSISTENT" in g.verify_release(bad, records, {"x.txt"}, {"a", "b"}).safe_reason_codes
    leaky = dict(report, files=report["files"] + [{"input_sha256": "z", "output": None, "status": "quarantined",
                                                   "reason": "Dorje Lhamo"}])
    assert not g.verify_release(leaky, records, {"x.txt"}, {"a", "b"}).passed
