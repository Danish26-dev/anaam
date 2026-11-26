"""The seam between the pipeline's writers and the detection engine (detection/api.py).
All values are invented."""
import json

import pytest

from core.interfaces import FieldNode, FileEnvelope, RecordEnvelope
from detection import api
from export.csv_writer import render_csv
from export.json_writer import render_json_doc, render_json_records
from export.text_writer import _shift_like, render_text, render_text_document

HEADER = ["Reg No", "Naam", "Janm Tithi", "Basti", "Mobile No", "Diagnosis"]
ROWS = [
    ["QX-40112", "Tarunika Vellaswami", "07-03-1971", "Bhoorkhet", "9123406781", "Type 2 diabetes mellitus"],
    ["QX-40113", "Ojasvi Pranthal", "21-11-1984", "Bhoorkhet", "9123406782", "Essential hypertension"],
]


def _csv_envelope():
    records = []
    for i, row in enumerate(ROWS):
        fields = [FieldNode(f"col:{h}", v, "str", "content") for h, v in zip(HEADER, row)]
        records.append(RecordEnvelope(f"r{i}", "sha-csv", f"row:{i}", "csv", fields))
    return FileEnvelope("sha-csv", "reg/list.csv", "csv", "utf-8", 1, records)


@pytest.fixture()
def prepared():
    api.configure(b"test-filename-key")
    env = _csv_envelope()
    assert api.prepare([env]) == {}
    return env


def test_csv_cells_use_field_context(prepared):
    out, edits = render_csv(HEADER, ROWS, ",", {0: None, 1: None}, {0: 10, 1: 10}, {0: "r0", 1: "r1"})
    assert "Tarunika" not in out and "Vellaswami" not in out and "Ojasvi" not in out
    assert "9123406781" not in out
    assert "Type 2 diabetes mellitus" in out and "Essential hypertension" in out
    assert edits > 0


def test_unrecognised_dob_column_is_shifted_keeping_its_layout(prepared):
    out, _ = render_csv(HEADER, ROWS, ",", {0: None, 1: None}, {0: 10, 1: 10}, {0: "r0", 1: "r1"})
    assert "07-03-1971" not in out
    assert "17-03-1971" in out          # dd-mm-yyyy kept, +10 days


def test_unrecognised_village_column_is_redacted(prepared):
    # "Basti" is not a header the privacy layer recognises, so the engine must handle it.
    out, _ = render_csv(HEADER, ROWS, ",", {0: None, 1: None}, {}, {0: "r0", 1: "r1"})
    assert "Bhoorkhet" not in out


def test_changed_value_is_scanned_on_its_own(prepared):
    # The writer holds a value the detector never saw: context is not applied blindly.
    assert api.field_spans("r0", "col:Naam", "something else") is None
    assert api.field_spans("r0", "col:Naam", "Tarunika Vellaswami")


def test_pseudonyms_are_not_rescanned():
    api.configure(b"k")
    assert render_text("PSN-7K2Q9XW4ABCD")[0] == "PSN-7K2Q9XW4ABCD"


@pytest.mark.parametrize("surface,iso,offset,expected", [
    ("07-03-1971", "1971-03-07", 10, "17-03-1971"),
    ("07/03/71", "1971-03-07", 1, "08/03/71"),
    ("1971-03-07", "1971-03-07", -7, "1971-02-28"),
    ("3.7.1971", "1971-07-03", 1, "4.7.1971"),
    ("12 Mar 1971", "1971-03-12", 1, None),     # non-numeric: left to the DOB/DATE fallback
])
def test_shift_like(surface, iso, offset, expected):
    assert _shift_like(surface, iso, offset) == expected


def test_json_numbers_holding_identifiers_become_zero():
    api.configure(b"k")
    data = {"patients": [{"patient_name": "Ojasvi Pranthal", "aadhaar": 482915036271, "weight_kg": 61}]}
    env = FileEnvelope("sha-json", "p.json", "json", "utf-8", 1, [RecordEnvelope(
        "j0", "sha-json", "/patients/0", "json",
        [FieldNode("/patient_name", "Ojasvi Pranthal", "str", "content"),
         FieldNode("/aadhaar", 482915036271, "int", "content"),
         FieldNode("/weight_kg", 61, "int", "content")])])
    api.prepare([env])
    out, _ = render_json_records(data, {}, {}, {"/patients/0": "j0"})
    item = json.loads(out)["patients"][0]
    assert item["aadhaar"] == 0 and item["weight_kg"] == 61
    assert "Ojasvi" not in out


def test_json_keys_holding_pii_are_renamed():
    api.configure(b"k")
    out, _ = render_json_doc({"9123406781": {"diagnosis": "Asthma"}, "ward": "B"})
    parsed = json.loads(out)
    assert "9123406781" not in out
    assert "ward" in parsed and any(v == {"diagnosis": "Asthma"} for v in parsed.values())


def test_text_document_context_and_pseudonym():
    api.configure(b"k")
    text = "Name: Tarunika Vellaswami\nMobile 9123406781\nDx: Type 2 diabetes mellitus\n"
    env = FileEnvelope("sha-t", "n.txt", "text", "utf-8", 1,
                       [RecordEnvelope("t0", "sha-t", "doc", "text", [], text)])
    api.prepare([env])
    out, _ = render_text_document(text, "PSN-7K2Q9XW4ABCD", 0, "t0")
    assert "Tarunika" not in out and "9123406781" not in out
    assert "PSN-7K2Q9XW4ABCD" in out and "Type 2 diabetes mellitus" in out


def test_identity_evidence_comes_from_the_engine(prepared):
    ev = api.extract_identity_evidence(prepared.records[0])
    assert ev.phones == ["9123406781"]
    assert ev.patient_names
