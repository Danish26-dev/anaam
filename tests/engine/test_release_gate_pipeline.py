"""Release-gate behaviour found while running it inside main.py. Invented values only."""
from core import interfaces as c
from detection.clinical import detect_clinical
from detection.engine import DetectionEngine
from verify.clinical import clinical_loss
from verify.release import FileCandidate, ReleaseGate


def _gate(names=(), pseudonyms=()):
    engine = DetectionEngine()
    for n in names:
        engine.lexicon.add_name(n, "relative")
    gate = ReleaseGate(engine, allowed_tokens=set(pseudonyms))
    gate.prepare()
    return gate


def test_letters_inside_a_pseudonym_are_not_a_residual_name():
    # The pseudonym code contains the letters of a harvested name token between digits.
    gate = _gate(names=["Dharm Vellaswami"], pseudonyms=["PSN-7K2DHARM8Z3Q7W1X"])
    text = "Patient: PSN-7K2DHARM8Z3Q7W1X\nDx: Asthma\n"
    res, fixed = gate.verify_and_fix(FileCandidate(text=text, pseudonyms=("PSN-7K2DHARM8Z3Q7W1X",)))
    assert res.passed
    assert "PSN-7K2DHARM8Z3Q7W1X" in fixed.text


def test_rescrub_keeps_pseudonyms():
    gate = _gate(names=["Dharm Vellaswami"], pseudonyms=["PSN-7K2DHARM8Z3Q7W1X"])
    out = gate.rescrub_text("PSN-7K2DHARM8Z3Q7W1X S/o Dharm Vellaswami")
    assert "PSN-7K2DHARM8Z3Q7W1X" in out and "Vellaswami" not in out


def test_ward_in_an_address_is_not_clinical_loss():
    before = "Address: H.No. 12, Ward 8, near Water Tank\nDx: Dengue fever\n"
    after = "Address: [HOUSE], [LOCALITY], [LANDMARK]\nDx: Dengue fever\n"
    assert clinical_loss(before, after) == {}


def test_patient_ids_and_hinglish_pt_are_not_lab_tests():
    # "pt-422" is a FHIR patient id and "pt" is Hinglish for patient; "PT 14.2 sec" is a lab.
    labs = lambda t: [s for s in detect_clinical(t) if s.category == c.LAB]  # noqa: E731
    assert not labs('"id": "pt-422"')
    assert not labs("pt ka BP 140/90 hai")
    assert labs("PT 14.2 sec, INR 1.1")
    assert labs("haemoglobin 10.2 g/dL")


TSV_IN = "Reg No\tNaam\tJanm Tithi\tMobile No\tDiagnosis\nQX-1\tTarunika Vellaswami\t07-03-1971\t9123406781\tAsthma\n"


def test_row_width_check_catches_merged_cells():
    from verify import structure as st
    merged = "Reg No\tNaam\tJanm Tithi\tMobile No\tDiagnosis\nQX-1\t[PERSON]\t07-03-1971 [PHONE]\tAsthma\n"
    assert st.check_csv_row_widths(merged, TSV_IN, "\t") == ["CSV_ROW_WIDTH"]
    assert st.check_csv_row_widths(TSV_IN, TSV_IN, "\t") == []


def test_tabular_rescrub_keeps_delimiters_and_header():
    import csv as _csv
    import io as _io
    gate = _gate()
    leaky = "Reg No\tNaam\tJanm Tithi\tMobile No\tDiagnosis\nQX-1\t[PATIENT]\t17-03-1971\t9123406781\tAsthma\n"
    cand = FileCandidate(text=leaky, original_text=TSV_IN, fmt="tsv", n_columns=5, n_rows=1, delimiter="\t")
    res, fixed = gate.verify_and_fix(cand)
    rows = list(_csv.reader(_io.StringIO(fixed.text), delimiter="\t"))
    assert [len(r) for r in rows] == [5, 5]
    assert rows[0] == ["Reg No", "Naam", "Janm Tithi", "Mobile No", "Diagnosis"]
    assert "9123406781" not in fixed.text and "Asthma" in fixed.text
    assert res.passed


def test_digits_across_two_cells_are_not_a_phone():
    gate = _gate()
    # "98765" ending one cell and "43210" starting the next must not read as one phone number
    # (a whole-row scan reports RESIDUAL_PHONE here, because \s in the phone pattern matches a tab)
    text = "Code\tCount\nRX-98765\t43210\n"
    tsv = FileCandidate(text=text, original_text=text, fmt="tsv", n_columns=2, n_rows=1, delimiter="\t")
    assert not [f for f in gate.verify_file(tsv).findings if f.category == "RESIDUAL_PHONE"]


def test_uuid_prefix_is_not_a_dose():
    text = "urn:uuid:81cc-7d1e-4b2a-9c3d"
    assert not [s for s in detect_clinical(text) if s.category == c.DOSE]
    assert [s for s in detect_clinical("IV fluids 81cc over 2 hours") if s.category == c.DOSE]
