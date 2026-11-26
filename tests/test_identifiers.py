import pytest

from src import contracts as c
from src.detection.identifiers import IdTemplates, detect_identifiers, id_digit_core, id_template
from src.detection.normalization import TextView


def found(text, **kw):
    view = TextView.of(text)
    return {(text[slice(*view.span_to_original(s.start, s.end))], s.category)
            for s in detect_identifiers(view.text, **kw)}


@pytest.mark.parametrize("text,surface", [
    ("Mobile: +91 72462 08919", "+91 72462 08919"),
    ("8276233002", "8276233002"),
    ("Mobile No 068127-45590 x", "068127-45590"),
    ("Mob. 75282-10587", "75282-10587"),
    ("telecom +91-7670584730", "+91-7670584730"),
    ("मोबाइल: ७५६००१००३४", "७५६००१००३४"),
    ("called by Kaveri 93041-14798", "93041-14798"),
    ("call karo 8382353960", "8382353960"),
    ("Phone (0522) 2345678", "(0522) 2345678"),
])
def test_phones(text, surface):
    assert (surface, c.PHONE) in found(text)


@pytest.mark.parametrize("text,surface,cat", [
    ("Aadhaar 331444027505", "331444027505", c.AADHAAR),
    ("8371 9372 5099", "8371 9372 5099", c.AADHAAR),
    ("5580-4308-2913", "5580-4308-2913", c.AADHAAR),
    ("XXXX XXXX 2093", "XXXX XXXX 2093", c.AADHAAR_MASKED),
    ("ABHA 90-6549-3147-0151", "90-6549-3147-0151", c.ABHA_NUMBER),
    ("payer QRTXZ7391L ok", "QRTXZ7391L", c.PAN),
    ("meenakshi.iyer4417@example.com", "meenakshi.iyer4417@example.com", c.EMAIL),
    ("asha.rajput@abdm", "asha.rajput@abdm", c.ABHA_ADDRESS),
    ("PMJAY-UP-8758791961", "PMJAY-UP-8758791961", c.INSURANCE_ID),
    ("POL/44/22262805", "POL/44/22262805", c.INSURANCE_ID),
    ("98XXXXXX10", "98XXXXXX10", c.PHONE_MASKED),
])
def test_national_ids(text, surface, cat):
    assert (surface, cat) in found(text)


@pytest.mark.parametrize("text,surface", [
    ("UHID: JJH-0048323        IPD No", "JJH-0048323"),
    ("IPD No: IP/26/00521", "IP/26/00521"),
    ("Reg No: SNJ/26/060622", "SNJ/26/060622"),
    ("पंजीकरण सं.: JJH-0043532", "JJH-0043532"),
    ("आईपीडी सं.: IP/26/00574", "IP/26/00574"),
    ("Bed 2 - ADM000611", "ADM000611"),
    ("DHH2026-018208", "DHH2026-018208"),
    ("DHH-IPD-00162", "DHH-IPD-00162"),
    ("IPD-2026-00243", "IPD-2026-00243"),
    ("Patient ID: K7-55", "K7-55"),
])
def test_hospital_ids(text, surface):
    assert (surface, c.MRN) in found(text)


@pytest.mark.parametrize("text", [
    "1. Tab Amlodipine 5 mg 0-0-1 x 2 wks", "BP 117/82, pulse 106", "Haemoglobin 14.0 g/dL",
    "LOINC 718-7", "A01.0", "range 150000-410000", "amount 49500", "S26000187",
    "OPD/26/02/00085", "AMB-436", "MG006A", "2026-04-21T17:15:00+05:30",
    "urn:uuid:ad12498f-1df9-4895-8cc5-ef79c3b941a0", "SNOMED 373942005", "COVID-19",
])
def test_non_identifiers(text):
    assert not found(text), found(text)


def test_learned_template_catches_unseen_format():
    tpl = IdTemplates()
    assert tpl.add("KMC#77-1234")
    text = "seen at kmc: KMC#77-9921 today"
    assert ("KMC#77-9921", c.MRN) in found(text, templates=tpl)


def test_digit_groups_never_span_a_line_break():
    text = "09:15 - Someone (visitor), mob 9562448057\n09:40 - next entry"
    got = found(text)
    assert ("9562448057", c.PHONE) in got
    assert not any("\n" in s for s, _ in got)
    assert not found("ref 1234 5678\n9012")                     # no Aadhaar across lines
    assert ("8371 9372 5099", c.AADHAAR) in found("id: 8371 9372 5099\nnext")


def test_template_and_core():
    assert id_template("SNJ/26/052715") == r"SNJ/\d{1,3}/\d{5,7}"
    assert id_template("12345") is None
    assert id_digit_core("SNJ/26/052715") == "052715"


def test_filename_ids_case_insensitive():
    assert ("adm000611", c.MRN) in found("nursing adm000611.txt", case_insensitive_ids=True)
