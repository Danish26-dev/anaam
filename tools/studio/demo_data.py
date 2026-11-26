"""Write the Release Studio's synthetic demo dataset (every person, number and place is invented).

    python tools/studio/demo_data.py --out frontend/demo-data/input

Three fictional hospitals, five fictional patients, every supported format, English, Hindi and
Hinglish, a name in a file name, a base64 attachment and one truncated file. Deterministic.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
from pathlib import Path

# Verhoeff tables, so the demo Aadhaar numbers have valid check digits like real-format data.
_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
      [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
      [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def aadhaar(stem11: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(stem11)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    full = stem11 + str(_INV[c])
    return f"{full[:4]} {full[4:8]} {full[8:]}"


PATIENTS = [
    {"name": "Ritika Venkataraman", "deva": None, "rel": "W/o Sridhar Venkataraman", "age": 38, "sex": "F",
     "dob": "14/03/1987", "phone": "9381046627", "aadhaar": aadhaar("72831904561"), "village": "Kesarbagh",
     "district": "Lucknow", "pin": "226014", "uhid": "SHY-2026-00418"},
    {"name": "Harjeet Bhullar", "deva": "हरजीत भुल्लर", "rel": "S/o Gurnam Bhullar", "age": 61, "sex": "M",
     "dob": "02/11/1964", "phone": "9915203378", "aadhaar": aadhaar("51402987336"), "village": "Mehrauli Khurd",
     "district": "Sitapur", "pin": "261001", "uhid": "SHY-2026-00419"},
    {"name": "Saanvi Pathrikar", "deva": "सान्वी पत्रिकर", "rel": "D/o Mohan Pathrikar", "age": 9, "sex": "F",
     "dob": "21/07/2016", "phone": "8840173095", "aadhaar": aadhaar("38820145679"), "village": "Bansgaon",
     "district": "Barabanki", "pin": "225001", "uhid": "SHY-2026-00420"},
    {"name": "Imtiaz Qureshi", "deva": "इम्तियाज़ कुरैशी", "rel": "S/o Rafiq Qureshi", "age": 47, "sex": "M",
     "dob": "09/01/1979", "phone": "7398562104", "aadhaar": aadhaar("60917328845"), "village": "Gulabpur",
     "district": "Hardoi", "pin": "241001", "uhid": "SHY-2026-00421"},
    {"name": "Leela Domnikar", "deva": "लीला डोमनिकर", "rel": "W/o Prakash Domnikar", "age": 72, "sex": "F",
     "dob": "30/05/1953", "phone": "9452870631", "aadhaar": aadhaar("84473029118"), "village": "Chandanpura",
     "district": "Unnao", "pin": "209801", "uhid": "SHY-2026-00422"},
]


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def build(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    # Hospital 1: Sahyog District Hospital, registration export (CSV)
    rows = ["UHID,Patient Name,Guardian,Age,Gender,Mobile,Aadhaar No,Village,District,PIN Code,Registered On"]
    for i, p in enumerate(PATIENTS):
        rows.append(f'{p["uhid"]},{p["name"]},{p["rel"]},{p["age"]},{p["sex"]},{p["phone"]},"{p["aadhaar"]}",'
                    f'{p["village"]},{p["district"]},{p["pin"]},{3 + i:02d}/02/2026')
    write(root, "sahyog_district_hospital/registration_feb2026.csv", "\n".join(rows) + "\n")

    # Hospital 1: OPD visits (JSON), one record per visit, with a scanned referral as base64
    referral = base64.b64encode(f"Referral note. Patient: {PATIENTS[1]['name']}, Mobile {PATIENTS[1]['phone']}. "
                                "Known diabetic, refer to medicine OPD.".encode()).decode()
    visits = {"hospital": "Sahyog District Hospital", "export": "opd-visits-v2", "visits": [
        {"uhid": PATIENTS[0]["uhid"], "patient_name": PATIENTS[0]["name"], "visit_date": "04/02/2026",
         "complaint": "C/O fever and body ache for 3 days", "diagnosis": "Dengue fever (A90)",
         "vitals": {"bp": "110/70 mmHg", "pulse": "96/min", "temp": "101.4 F"},
         "medicines": [{"drug": "Paracetamol", "dose": "650 mg", "frequency": "1-1-1", "days": 5}],
         "lab": {"platelets": "92,000 /cumm", "ns1_antigen": "positive"}},
        {"uhid": PATIENTS[1]["uhid"], "patient_name": PATIENTS[1]["name"], "visit_date": "05/02/2026",
         "complaint": "Burning in feet, increased thirst", "diagnosis": "Type 2 diabetes mellitus (E11.9)",
         "vitals": {"bp": "142/88 mmHg", "pulse": "82/min"},
         "medicines": [{"drug": "Metformin", "dose": "500 mg", "frequency": "1-0-1", "days": 30}],
         "lab": {"hba1c": "8.4 %", "fbs": "168 mg/dL"},
         "attachments": [{"type": "referral_scan", "encoding": "base64", "data": referral}]},
        {"uhid": PATIENTS[3]["uhid"], "patient_name": PATIENTS[3]["name"], "visit_date": "07/02/2026",
         "complaint": "Cough with expectoration for 2 weeks", "diagnosis": "Pulmonary tuberculosis (A15.0)",
         "vitals": {"bp": "118/76 mmHg", "spo2": "95 %"},
         "medicines": [{"drug": "Isoniazid", "dose": "300 mg", "frequency": "1-0-0", "days": 180}],
         "lab": {"sputum_afb": "positive (2+)"}}]}
    write(root, "sahyog_district_hospital/opd_visits.json", json.dumps(visits, ensure_ascii=False, indent=2) + "\n")

    # Hospital 2: Navjeevan Nursing Home, discharge summary (English) with the name in the file name
    p = PATIENTS[0]
    write(root, f"navjeevan_nursing_home/discharge_{p['name'].replace(' ', '_')}.txt", f"""NAVJEEVAN NURSING HOME, LUCKNOW
DISCHARGE SUMMARY

Patient Name : {p['name']}
{p['rel']}
Age/Sex      : {p['age']} Y / {p['sex']}
DOB          : {p['dob']}
Contact      : +91 {p['phone'][:5]} {p['phone'][5:]}
UHID         : {p['uhid']}
Address      : H.No. 27, Mohalla Naya Tola, near Hanuman Mandir, {p['village']}, {p['district']} {p['pin']}

Date of admission : 06/02/2026
Date of discharge : 11/02/2026

Diagnosis: Dengue fever with thrombocytopenia (A91).
Course: Admitted with fever and platelet count of 48,000 /cumm. Managed with IV fluids
(NS 1 L over 8 hrs) and Inj. Pantoprazole 40 mg IV OD. Platelets improved to 1,32,000 /cumm.
At discharge: BP 116/74 mmHg, pulse 84/min, afebrile.

Advice on discharge:
1. Tab. Paracetamol 650 mg 1-1-1 x 3 days
2. ORS 1 sachet in 1 L water, sip throughout the day
Review in OPD after 1 week with CBC. Treating doctor: Dr. Anjali Khandekar (MD Medicine).
""")

    # Hospital 2: nursing note in Hindi / Hinglish
    p = PATIENTS[1]
    write(root, "navjeevan_nursing_home/nursing_note_ward3.txt", f"""नर्सिंग नोट - वार्ड 3
मरीज़ का नाम: {p['deva']}
पिता का नाम: गुरनाम भुल्लर
मोबाइल: {p['phone']}
दिनांक: 08/02/2026

08:00 - patient ka BP 146/90 mmHg, sugar (RBS) 212 mg/dL. Dr. Khandekar ko inform kiya.
10:30 - Inj. Insulin regular 6 units SC diya gaya.
14:00 - मरीज़ ने खाना ठीक से खाया। pulse 80/min, SpO2 97 %.
""")

    # Hospital 3: Arogya Diagnostics, lab report (TSV)
    lab = ["Sample ID\tPatient\tAge\tSex\tTest\tResult\tUnit\tRef Range\tCollected"]
    for i, (pt, test, val, unit, ref) in enumerate([
            (PATIENTS[2], "Haemoglobin", "10.2", "g/dL", "11.5-15.5"),
            (PATIENTS[2], "TLC", "12400", "/cumm", "4000-11000"),
            (PATIENTS[4], "Serum Creatinine", "1.9", "mg/dL", "0.6-1.2"),
            (PATIENTS[4], "HbA1c", "7.1", "%", "4.0-5.6"),
            (PATIENTS[3], "ESR", "62", "mm/hr", "0-20")]):
        lab.append(f"AD-{55210 + i}\t{pt['name']}\t{pt['age']}\t{pt['sex']}\t{test}\t{val}\t{unit}\t{ref}\t0{8 + i % 2}/02/2026")
    write(root, "arogya_diagnostics/lab_results.tsv", "\n".join(lab) + "\n")

    # Hospital 3: FHIR R4 document bundle for one patient
    p = PATIENTS[4]
    bundle = {"resourceType": "Bundle", "type": "document", "entry": [
        {"fullUrl": "urn:uuid:5f0c2a9e-0b7d-4a51-9e1f-3c6d2b8a7e10", "resource": {
            "resourceType": "Patient", "id": "pt-422",
            "identifier": [{"system": "urn:sahyog:uhid", "value": p["uhid"]}],
            "name": [{"text": p["name"]}], "gender": "female", "birthDate": "1953-05-30",
            "telecom": [{"system": "phone", "value": p["phone"]}],
            "address": [{"text": f"{p['village']}, {p['district']} {p['pin']}"}]}},
        {"fullUrl": "urn:uuid:9a6d1c44-2f3e-4b8a-8c1d-7e5f4a3b2c19", "resource": {
            "resourceType": "Condition", "id": "cond-1", "subject": {"reference": "urn:uuid:5f0c2a9e-0b7d-4a51-9e1f-3c6d2b8a7e10"},
            "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "N18.3"}],
                     "text": "Chronic kidney disease, stage 3"}, "recordedDate": "2026-02-09"}},
        {"fullUrl": "urn:uuid:c2b7e8f1-6a4d-4e3b-9f2a-1d8c7b6a5e43", "resource": {
            "resourceType": "Observation", "id": "obs-1", "status": "final",
            "subject": {"reference": "urn:uuid:5f0c2a9e-0b7d-4a51-9e1f-3c6d2b8a7e10"},
            "code": {"text": "Serum creatinine"}, "valueQuantity": {"value": 1.9, "unit": "mg/dL"},
            "effectiveDateTime": "2026-02-09T08:30:00+05:30",
            "note": [{"text": f"Sample collected at home visit. Contact daughter-in-law on {p['phone']}."}]}}]}
    write(root, "arogya_diagnostics/fhir_bundle_0209.json", json.dumps(bundle, ensure_ascii=False, indent=2) + "\n")

    # A truncated export: must be quarantined, never copied
    write(root, "sahyog_district_hospital/opd_visits_partial.json", '{"visits": [{"uhid": "SHY-2026-0042')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="frontend/demo-data/input")
    a = ap.parse_args()
    build(Path(a.out))
    print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
