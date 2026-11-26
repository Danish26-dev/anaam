import pytest

from src import contracts as c
from src.detection.clinical import detect_clinical


def covered(text, needle, categories=None):
    """True if some protected span fully covers `needle`."""
    i = text.index(needle)
    j = i + len(needle)
    for s in detect_clinical(text):
        if s.start <= i and s.end >= j and (categories is None or s.category in categories):
            return True
    return False


@pytest.mark.parametrize("text,needle", [
    ("1. Tab Amlodipine 5 mg 0-0-1 x 2 wks", "Tab Amlodipine 5 mg 0-0-1 x 2 wks"),
    ("Dr ne bola Dolo 650 BD x 5 days lena hai", "Dolo 650 BD x 5 days"),
    ("Paracetamol 650 mg diya.", "Paracetamol 650 mg"),
    ("Tab Ferrous sulphate + Folic acid 100 mg + 0.5 mg 0-1-0 x 30 days",
     "Ferrous sulphate + Folic acid 100 mg + 0.5 mg 0-1-0 x 30 days"),
    ("Inh Salbutamol inhaler 100 mcg 2 puffs x 5 days", "Salbutamol inhaler 100 mcg 2 puffs x 5 days"),
    ("Tab Xyzomab 50 mg 1-0-1", "Tab Xyzomab 50 mg 1-0-1"),
    ("frequency 1-0-1 daily", "1-0-1"),
])
def test_medications_and_frequencies(text, needle):
    assert covered(text, needle)


@pytest.mark.parametrize("text,needle", [
    ("Shahid sahab ka BP 117/82, pulse 106. Bukhar 103 F.", "BP 117/82"),
    ("Shahid sahab ka BP 117/82, pulse 106. Bukhar 103 F.", "pulse 106"),
    ("Shahid sahab ka BP 117/82, pulse 106. Bukhar 103 F.", "Bukhar 103 F"),
    ("SpO2 94%. Haemoglobin 8.6 g/dL. Random Blood Sugar 235 mg/dL.", "Haemoglobin 8.6 g/dL"),
    ("SpO2 94%. Haemoglobin 8.6 g/dL. Random Blood Sugar 235 mg/dL.", "Random Blood Sugar 235 mg/dL"),
    ("HbA1c 8.2%", "HbA1c 8.2%"),
    ("RBS 145 mg/dL.", "RBS 145 mg/dL"),
])
def test_vitals_and_labs(text, needle):
    assert covered(text, needle)


@pytest.mark.parametrize("text,needle,cat", [
    ("C/O: fever x 7 days, body ache\nK/C/O: I10", "C/O: fever x 7 days, body ache", c.COMPLAINT),
    ("Presenting complaints: C/O fever for 3 days, generalised weakness.",
     "C/O fever for 3 days, generalised weakness", c.COMPLAINT),
    ("14:00 - Mohd. Faizal - K/C/O addison's disease. Attendant", "K/C/O addison's disease", c.HISTORY),
    ("History: H/O TB 10 yrs back, completed ATT\n", "H/O TB 10 yrs back, completed ATT", c.HISTORY),
    ("Diagnosis: Typhoid fever (A01.0); ", "A01.0", c.DIAGNOSIS_CODE),
    ("rarely, Addison's disease crisis.", "Addison's disease", c.EPONYM),
    ("Parkinson's disease", "Parkinson's disease", c.EPONYM),
    ("Treated for Essential (primary) hypertension.", "hypertension", c.DIAGNOSIS),
    ("Procedure: Cataract surgery (phacoemulsification) done", "Cataract surgery", c.PROCEDURE),
])
def test_diagnoses_and_history(text, needle, cat):
    assert covered(text, needle, {cat})


def test_care_of_relative_is_not_a_complaint():
    spans = detect_clinical("C/O Parveez Kakati, H.No. 364")
    assert not [s for s in spans if s.category == c.COMPLAINT]


@pytest.mark.parametrize("text,needle,cat", [
    ("Review in OPD after 2 weeks with Dr. Ramesh Srivastava.", "Dr. Ramesh Srivastava", c.DOCTOR),
    ("Dr. Harjeet Bedi (MD Pulmonary Medicine)", "Dr. Harjeet Bedi (MD Pulmonary Medicine)", c.DOCTOR),
    ("NURSING NOTES - Ward 8 (Medicine), Bed 2", "Ward 8 (Medicine)", c.WARD),
    ("Jeevan Jyoti Charitable Hospital, Barabanki", "Jeevan Jyoti Charitable Hospital", c.ORGANIZATION),
    ("JEEVAN JYOTI CHARITABLE HOSPITAL, BARABANKI", "JEEVAN JYOTI CHARITABLE HOSPITAL", c.ORGANIZATION),
    ("Arogya Seva Sadan - OPD Prescription", "Arogya Seva Sadan", c.ORGANIZATION),
    ("Referred by ASHA worker of the village.", "ASHA worker", c.CLINICAL_CONTEXT),
])
def test_context_protection(text, needle, cat):
    assert covered(text, needle, {cat})


def test_generic_lab_value_does_not_swallow_a_name():
    text = "Mahesh has Random Blood Sugar 235 mg/dL"
    i = text.index("Mahesh")
    assert not [s for s in detect_clinical(text) if s.start <= i < s.end]


def test_name_next_to_drug_is_not_protected():
    text = "Mohammad Arif takes Dolo 650 mg"
    i = text.index("Arif")
    assert not [s for s in detect_clinical(text) if s.start <= i < s.end]
    assert covered(text, "Dolo 650 mg")


def test_bare_ward_flagged():
    spans = detect_clinical("H.No. 364, Ward 20, Mohalla Raja Bazar")
    assert any(s.source == "ward_bare" for s in spans)
