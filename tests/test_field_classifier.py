import pytest

from src.detection import field_classifier as fc


@pytest.mark.parametrize("header,values,expected", [
    ("Patient Name", ["Tarun Kakati", "Swaroop Hegde"], fc.NAME_PATIENT),
    ("Patient's Name", ["Rohini Acharya"], fc.NAME_PATIENT),
    ("Naam", ["सान्वी हेगड़े", "Ishvarya Mondal"], fc.NAME_PATIENT),
    ("LastName", ["Patel", "Lodhi"], fc.NAME_PATIENT),
    ("Pita/Pati ka Naam", ["D/o गोपीनाथ मंडल"], fc.NAME_RELATIVE),
    ("Relative Name", ["Parveez Kakati"], fc.NAME_RELATIVE),
    ("Guardian", ["S/O IBRAHIM MENON"], fc.NAME_RELATIVE),
    ("Relation", ["S/o", "W/o"], fc.RELATION_VALUE),
    ("Mobile", ["+91 72462 08919"], fc.PHONE),
    ("Contact#", ["98765 43210", "7140840254"], fc.PHONE),
    ("Mobile No", ["068127-45590"], fc.PHONE),
    ("Aadhaar No", ["331444027505", "XXXX XXXX 2093"], fc.AADHAAR),
    ("Aadhar", ["9034 8688 4169"], fc.AADHAAR),
    ("ABHA No", ["90-6549-3147-0151"], fc.ABHA_NUMBER),
    ("payer_pan", ["LMNPA2468C"], fc.PAN),
    ("pmjay_id", ["PMJAY-UP-8758791961"], fc.INSURANCE_ID),
    ("policy_no", ["POL/44/22262805"], fc.INSURANCE_ID),
    ("UHID", ["SNJ/26/052715"], fc.MRN),
    ("Reg No", ["JJH-0006739"], fc.MRN),
    ("PatientID", ["UHID-039164"], fc.MRN),
    ("patient_ref", ["UHID-063763"], fc.MRN),
    ("hospital_uhid", ["JJH-0023443"], fc.MRN),
    ("DOB", ["12/04/1977"], fc.DOB),
    ("DOB (MM/DD/YYYY)", ["04/20/1979"], fc.DOB),
    ("Janm Tithi", ["29-07-1978"], fc.DOB),
    ("Age", ["48", "55"], fc.AGE),
    ("Umar", ["47 वर्ष"], fc.AGE),
    ("age_sex", ["65/F"], fc.AGE_SEX),
    ("Ling", ["महिला", "F"], fc.GENDER),
    ("Address", ["H.No. 364, Ward 20"], fc.ADDRESS),
    ("Pata", ["मकान नं. 32"], fc.ADDRESS),
    ("Village/Mohalla", ["Ramwara Kalan"], fc.VILLAGE),
    ("Gaon", ["चंदपुरा खुर्द"], fc.VILLAGE),
    ("Gram/Mohalla", ["Shivpur"], fc.VILLAGE),
    ("City", ["Shivkheda"], fc.VILLAGE),
    ("Tehsil", ["Lalganj"], fc.TEHSIL),
    ("Jila", ["बाराबंकी"], fc.DISTRICT),
    ("PIN", ["203080"], fc.PIN),
    ("Pin Code", ["220205"], fc.PIN),
    ("Postal Code", ["220205"], fc.PIN),
    ("package_code", ["MG006A"], fc.REFERENCE),
    ("Zip", ["296358"], fc.PIN),
    ("ref_doctor", ["Dr. Vandana Kulshrestha"], fc.NAME_DOCTOR),
    ("bill_no", ["BL/26/000248"], fc.REFERENCE),
    ("sample_id", ["S26000187"], fc.REFERENCE),
    ("test", ["Haemoglobin"], fc.CLINICAL),
    ("complaints", ["C/O fever x 3 days"], fc.FREE_TEXT),
    ("remarks", ["called by Rohini Acharya 93041-14798"], fc.FREE_TEXT),
])
def test_headers(header, values, expected):
    assert fc.classify_field(header, values) == expected


@pytest.mark.parametrize("header,parents,expected", [
    ("name", ("patients", "guardian"), fc.NAME_RELATIVE),
    ("name", ("facility",), fc.ORGANIZATION),
    ("name", ("panels",), fc.ORGANIZATION),
    ("name", ("visits", "patient"), fc.NAME_PATIENT),
    ("name", ("tickets", "meta", "raised_by"), fc.NAME_PERSON),
    ("callback", ("tickets", "meta", "raised_by"), fc.PHONE),
    ("first", ("patients", "name"), fc.NAME_PATIENT),
    ("local", ("patients", "name"), fc.NAME_PATIENT),
    ("aadhar_no", ("patients", "ids"), fc.AADHAAR),
    ("mobile", ("patients", "contact"), fc.PHONE),
    ("village", ("patients", "address"), fc.VILLAGE),
])
def test_json_parent_context(header, parents, expected):
    assert fc.classify_header(header, parents) == expected


@pytest.mark.parametrize("header,values,expected", [
    ("col_7", ["98765 43210", "+91 70000 12345"], fc.PHONE),
    ("x", ["asha@example.com"], fc.EMAIL),
    ("field3", ["Thangam Devi", "Ramesh Kumar", "Kamla"], fc.NAME_PERSON),
    ("field4", ["8371 9372 5099"], fc.AADHAAR),
    ("misc", ["KMC-0012345", "KMC-0012399"], fc.OTHER_ID),
    ("from", ["Sitapur", "Lucknow"], fc.FREE_TEXT),
])
def test_unknown_headers_by_values(header, values, expected):
    assert fc.classify_field(header, values) == expected


@pytest.mark.parametrize("parents,key,expected", [
    (("entry", "resource", "name", "given"), "given", fc.NAME_PATIENT),
    (("entry", "resource", "contact", "name"), "text", fc.NAME_RELATIVE),
    (("entry", "resource", "identifier"), "value", fc.MRN),
    (("entry", "resource", "telecom"), "value", fc.PHONE),
    (("entry", "resource", "address"), "city", fc.VILLAGE),
    (("entry", "resource", "address"), "postalCode", fc.PIN),
    (("entry", "resource", "address"), "district", fc.DISTRICT),
    (("entry", "resource", "extension"), "valueString", fc.NAME_PERSON),
    (("entry", "resource"), "birthDate", fc.DOB),
])
def test_fhir_patient(parents, key, expected):
    assert fc.classify_header(key, parents, fhir_type="Patient") == expected


def test_fhir_other_resources():
    assert fc.classify_header("text", ("entry", "resource", "name"), "Practitioner") == fc.NAME_DOCTOR
    assert fc.classify_header("display", ("entry", "resource", "subject"), "Composition") == fc.NAME_PATIENT
    assert fc.classify_header("value", ("entry", "resource", "identifier"), "Encounter") == fc.MRN
    assert fc.classify_header("display", ("entry", "resource", "code", "coding"), "Condition") == fc.FREE_TEXT
