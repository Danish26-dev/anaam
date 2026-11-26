from src import contracts as c
from src.detection.engine import DetectionEngine


def engine():
    e = DetectionEngine(filename_key=b"test-key")
    e.lexicon.add_name("Ishwarya Mondal", "patient")
    e.lexicon.add_name("Zoya Dsouza", "patient")
    e.lexicon.add_id("JJH-0046225", c.MRN)
    return e


def test_harmless_headers_are_untouched():
    e = engine()
    cells = ["Reg No", "Naam", "Janm Tithi", "Pita/Pati ka Naam", "Pata", "Gaon", "Pin Code", "Mobile No"]
    assert e.sanitize_header(cells) == cells


def test_headers_holding_identifiers_are_renamed_and_unique():
    e = engine()
    out = e.sanitize_header(["time", "JJH-0046225 Zoya", "JJH-0048323 Jaspreet", "JJH-0051908 Neha"])
    assert out[0] == "time"
    assert all("JJH" not in x and "Zoya" not in x for x in out[1:])
    assert len(set(out)) == len(out)


def test_file_names_with_pii_are_renamed_deterministically():
    e = engine()
    a = e.sanitize_path("discharge/Discharge_Summary_Ishwarya_Mondal_JJH-0043532.txt")
    b = e.sanitize_path("discharge/Discharge_Summary_Ishwarya_Mondal_JJH-0043532.txt")
    assert a == b and a.endswith(".txt") and a.startswith("discharge/")
    assert "Reena" not in a and "JJH" not in a and "0043532" not in a
    assert e.sanitize_path("lab/7629298201_report_0010.json").count("7629298201") == 0
    assert e.sanitize_path("notes/nursing_adm000611.txt").find("000611") < 0


def test_distinct_pii_names_never_collide():
    e = engine()
    a = e.sanitize_path("lab/7629298201_report_0010.json")
    b = e.sanitize_path("lab/7585745402_report_0022.json")
    assert a != b


def test_clean_file_names_unchanged():
    # (see also test_identifiers: digit groups never span a line break)
    e = engine()
    for p in ("clean/drug_formulary.csv", "opd/arogya_opd_2026_02.json", "fhir/bundle_08fb8ae4.json",
              "registration/sanjeevani_registration (1).csv"):
        assert e.sanitize_path(p) == p


def test_pii_keys_renamed_others_kept():
    e = engine()
    m = e.sanitize_keys(["generated", "by_name", "Zoya Dsouza", "JJH-0046225"])
    assert set(m) == {"Zoya Dsouza", "JJH-0046225"}
    assert len(set(m.values())) == 2 and not set(m.values()) & {"generated", "by_name"}


def test_dict_keyed_by_unknown_names_is_renamed_but_schema_keys_are_not():
    e = engine()
    names = ["Dorje Lhamo", "Debashis Kakati", "Meenakshi Iyer", "Sourav Mondal"]
    assert set(e.sanitize_keys(names)) == set(names)
    schema = ["Visit Date", "Patient Status", "Record Count"]
    assert e.sanitize_keys(["generated", "visits", "count"]) == {}
    assert len(e.sanitize_keys(["by_name"] + names)) == 4


def test_changed_secret_changes_renamed_path():
    a = DetectionEngine(filename_key=b"k1")
    b = DetectionEngine(filename_key=b"k2")
    p = "lab/7629298201_report_0010.json"
    assert a.sanitize_path(p) != b.sanitize_path(p)
