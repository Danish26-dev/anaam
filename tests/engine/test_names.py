import pytest

from core import interfaces as c
from detection.names import detect_names


def names(text):
    return {(text[s.start:s.end], s.category) for s in detect_names(text)}


def surfaces(text):
    return {text[s.start:s.end] for s in detect_names(text)}


@pytest.mark.parametrize("text,surface,cat", [
    ("Name: Padmini Reddy   Age: 48/F   Reg No", "Padmini Reddy", c.PATIENT_NAME),
    ("Name: RUDRA CHETTIAR   Age: 91/M", "RUDRA CHETTIAR", c.PATIENT_NAME),
    ("Patient Name: Gurvinder Bajwa        Age/Sex: 46 Yrs/M", "Gurvinder Bajwa", c.PATIENT_NAME),
    ("मरीज़ का नाम: ईश्वर्या मंडल    आयु: 65 वर्ष", "ईश्वर्या मंडल", c.PATIENT_NAME),
    ("नाम: हरलीन पिल्लई   आयु: 21 वर्ष", "हरलीन पिल्लई", c.PATIENT_NAME),
    ("पिता का नाम: चंद्रकांत मंडल\nपंजीकरण", "चंद्रकांत मंडल", c.RELATIVE_NAME),
    ("Attendant: Chandrakant Mondal, Mob. 7528210587", "Chandrakant Mondal", c.RELATIVE_NAME),
    ("Patient's Name: Sudeshna Pattnaik", "Sudeshna Pattnaik", c.PATIENT_NAME),
])
def test_label_names(text, surface, cat):
    assert (surface, cat) in names(text)


@pytest.mark.parametrize("text,surface", [
    ("S/o Jasleen Bajwa\nAddress", "Jasleen Bajwa"),
    ("Guardian S/O IBRAHIM MENON,", "IBRAHIM MENON"),
    ("Attendant (S/o Zubair) informed about diet.", "Zubair"),
    ("D/o गोपीनाथ मंडल", "गोपीनाथ मंडल"),
    ("C/O Yashwant Reddy, Ward 8", "Yashwant Reddy"),
    ("W/O BHAVESH GOGOI", "BHAVESH GOGOI"),
    ("Discharge note\nAsha, W/o Kamal, discharged", "Kamal"),
])
def test_relatives(text, surface):
    assert (surface, c.RELATIVE_NAME) in names(text)


@pytest.mark.parametrize("text,surface", [
    ("Discharge note\nAsha, W/o Kamal, discharged", "Asha"),
    ("Zainab, W/o Salim, discharged in stable condition.", "Zainab"),
])
def test_fragment_patient_before_relation(text, surface):
    assert (surface, c.PATIENT_NAME) in names(text)


@pytest.mark.parametrize("text,surface", [
    ("Shahid sahab ka BP 117/82", "Shahid sahab"),
    ("Anita behenji ka BP 112/78", "Anita behenji"),
    ("Report of Asha ji  48 Y / F", "Asha ji"),
    ("Treated conservatively. Jaspreet bhai ki condition ab stable hai.", "Jaspreet bhai"),
    ("14:00 - Mohd. Faizal - K/C/O addison's disease.", "Mohd. Faizal"),
    ("Sample received from Harish's attendant (S/o Kiaan Pillai).", "Harish"),
    ("Anita ka BP 112/74, dawai time pe le rahe hain.", "Anita"),
    ("हरलीन पिल्लई को 8 दिन से बुखार है।", "हरलीन पिल्लई"),
])
def test_patient_mentions(text, surface):
    assert surface in surfaces(text)


@pytest.mark.parametrize("text,surface", [
    ("18:40 - Zubin Merchant (attendant, bed 12), mob 6939559143", "Zubin Merchant"),
    ("AMB-436,Sitapur,Lucknow,called by Rohini Acharya 93041-14798", "Rohini Acharya"),
    ("Consent witnessed by Dorje Lhamo, phone 8921593556.", "Dorje Lhamo"),
    ("[30/05/26, 9:32 pm] Kamal Bhaiya: <attachment: report.pdf>", "Kamal Bhaiya"),
])
def test_canary_style_contexts(text, surface):
    assert surface in surfaces(text)


@pytest.mark.parametrize("text", [
    "C/O: fever x 7 days, body ache",
    "Presenting complaints: C/O fever for 3 days, generalised weakness.",
    "Review in OPD after 2 weeks with Dr. Ramesh Srivastava.",
    "Dr. Ramesh Srivastava reviewed the patient.",
    "19:10 - Dr. Ramesh Srivastava took evening round.",
    "Next morning 06:00 - Patient ne raat theek se neend li.",
    "Referred by ASHA worker of the village.",
    "Jeevan Jyoti Charitable Hospital - OPD Prescription",
    "Differential diagnosis includes typhoid, malaria and, rarely, Addison's disease crisis.",
    "Drug Name: Paracetamol",
    "Random Blood Sugar 245 mg/dL",
    "Dr ne bola Dolo 650 BD x 5 days lena hai",
    "Medications on discharge:\n 1. Cap Doxycycline 100 mg",
    "मरीज़ को 2 दिन से बुखार था।",
    "Tehsil Lalganj, Distt. Rae Bareli",
    "Course in hospital: Patient admitted with above complaints.",
])
def test_no_false_names(text):
    assert not surfaces(text), surfaces(text)
