from core import interfaces as c
from detection.identity_lexicon import IdentityLexicon


def lex():
    x = IdentityLexicon()
    x.add_name("Tarun Kakati", "patient")
    x.add_name("Parveez Kakati", "relative")
    x.add_name("Nilufar Dsouza", "patient")
    x.add_name("Harleen Pillai", "patient")
    x.add_name("Mohammad Faizal", "patient")
    x.add_name("Padmini Reddy", "patient")
    x.add_name("Dr. Vandana Kulshrestha", "doctor")
    x.add_id("SNJ/26/052715", c.MRN)
    x.add_id("UHID-063763", c.MRN)
    x.add_id("+91 72462 08919", c.PHONE)
    x.add_place("Ramwara Kalan")
    x.add_place("Chandpura Khurd")
    return x


def found(x, text):
    return {(text[s.start:s.end], s.category, s.source) for s in x.find(text)}


def test_full_name_variants_and_scripts():
    x = lex()
    assert ("TARUN KAKATI", c.PATIENT_NAME, "lexicon_full") in found(x, "pt TARUN KAKATI seen")
    assert ("Tarun Kakaty", c.PATIENT_NAME, "lexicon_full") in found(x, "Tarun Kakaty, 48")
    assert ("नीलुफ़र डिसूज़ा", c.PATIENT_NAME, "lexicon_full") in found(x, "नाम नीलुफ़र डिसूज़ा आयु")
    assert ("Harlin Pillai", c.PATIENT_NAME, "lexicon_full") in found(x, "name Harlin Pillai,")
    assert ("Swaroop_Hegde", c.PATIENT_NAME, "lexicon_full") not in found(x, "Swaroop_Hegde")


def test_filename_style_and_single_tokens():
    x = lex()
    x.add_name("Swaroop Hegde", "patient")
    assert ("Swaroop_Hegde", c.PATIENT_NAME, "lexicon_full") in found(x, "Discharge_Summary_Swaroop_Hegde_SNJ.txt")
    assert ("Faizal", c.PATIENT_NAME, "lexicon_token") in found(x, "Faizal sahab ka BP")
    assert ("फ़ैज़ल", c.PATIENT_NAME, "lexicon_token") in found(x, "मोहम्मद फ़ैज़ल को")


def test_spelling_variant_single_token_is_redacted():
    x = lex()
    assert ("Harlin", c.PATIENT_NAME, "lexicon_token") in found(x, "Harlin came")


def test_fuzzy_single_token_is_not_redacted():
    x = lex()
    assert not [f for f in found(x, "Harsh came") if f[0] == "Harsh"]


def test_cross_script_single_token_with_schwa():
    x = lex()
    x.add_name("Sanvi Hegde", "patient")
    assert ("सान्वी", c.PATIENT_NAME, "lexicon_token") in found(x, "सान्वी को बुखार")


def test_relative_role_and_doctor_protection():
    x = lex()
    assert ("Parveez Kakati", c.RELATIVE_NAME, "lexicon_full") in found(x, "C/O Parveez Kakati,")
    assert ("Vandana Kulshrestha", c.DOCTOR, "lexicon_doctor") in found(x, "Consultant: Vandana Kulshrestha")
    assert not [f for f in found(x, "Vandana came") if f[1] != c.DOCTOR]


def test_common_words_never_match():
    x = lex()
    x.add_name("Patient Asha", "patient")
    assert not [f for f in found(x, "asha worker") if f[2] == "lexicon_token"]


def test_ids_and_cores():
    x = lex()
    got = found(x, r"D:\HIS\exports\opd\Meenakshi_Iyer_063763\visits.json")
    assert ("063763", c.MRN, "lexicon_id") in got
    assert ("7246208919", c.PHONE, "lexicon_id") in found(x, "call 7246208919 now")
    assert ("SNJ/26/064999", c.MRN, "id_template") in found(x, "ref SNJ/26/064999 ok")
    assert not found(x, "WBC 13000 /uL")


def test_places():
    x = lex()
    assert ("Ramwara Kalan", c.VILLAGE, "lexicon_place") in found(x, "from Ramwara Kalan village")
    assert ("चंदपुरा खुर्द", c.VILLAGE, "lexicon_place") in found(x, "ग्राम: चंदपुरा खुर्द")
    assert not [f for f in found(x, "Kalan") if f[2] == "lexicon_place"]
