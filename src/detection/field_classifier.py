"""D5: classify structured fields (CSV columns, JSON keys) from their header AND values.

Header evidence uses multilingual synonym rules on a normalized header (camelCase split,
punctuation removed): "Contact#" -> PHONE, "Pita/Pati ka Naam" -> NAME_RELATIVE,
"Gram/Mohalla" -> VILLAGE. Exact practice headers are never required.
Value evidence (share of phone-like, Aadhaar-like, e-mail, ID-shaped, name-like values)
confirms the header, overrides it when it contradicts, and classifies unknown headers.
JSON keys also use their parent keys ("guardian.name" is a relative, "facility.name" is not).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import identifiers as ids
from .dates import find_dates
from .gazetteer_data import GIVEN_NAMES, SURNAMES
from .names import NON_NAME
from .normalization import TextView, tokenize
from .transliteration import loose_form

# field classes
NAME_PATIENT = "NAME_PATIENT"
NAME_RELATIVE = "NAME_RELATIVE"
NAME_PERSON = "NAME_PERSON"
NAME_DOCTOR = "NAME_DOCTOR"
RELATION_VALUE = "RELATION_VALUE"
PHONE = "PHONE"
EMAIL = "EMAIL"
AADHAAR = "AADHAAR"
ABHA_NUMBER = "ABHA_NUMBER"
ABHA_ADDRESS = "ABHA_ADDRESS"
PAN = "PAN"
MRN = "MRN"
INSURANCE_ID = "INSURANCE_ID"
OTHER_ID = "OTHER_ID"
REFERENCE = "REFERENCE"          # bill, sample, visit numbers: not personal
DOB = "DOB"
AGE = "AGE"
AGE_SEX = "AGE_SEX"
GENDER = "GENDER"
DATE = "DATE"
ADDRESS = "ADDRESS"
VILLAGE = "VILLAGE"
TEHSIL = "TEHSIL"
DISTRICT = "DISTRICT"
STATE = "STATE"
PIN = "PIN"
ORGANIZATION = "ORGANIZATION"
CLINICAL = "CLINICAL"
FREE_TEXT = "FREE_TEXT"
UNKNOWN = "UNKNOWN"

PERSON_NAME_CLASSES = frozenset({NAME_PATIENT, NAME_RELATIVE, NAME_PERSON})
DIRECT_ID_CLASSES = frozenset({PHONE, EMAIL, AADHAAR, ABHA_NUMBER, ABHA_ADDRESS, PAN, MRN, INSURANCE_ID, OTHER_ID})


def normalize_header(h: str) -> str:
    h = TextView.of(str(h)).text
    h = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", h)
    h = re.sub(r"[_\W]+", " ", h.casefold())
    return f" {h.strip()} "


def _rx(*alts: str) -> re.Pattern:
    return re.compile(r"(?<![a-z\u0900-\u097f])(?:" + "|".join(alts) + r")(?![a-z\u0900-\u097f])")


RULES: list[tuple[str, re.Pattern]] = [
    (PIN, _rx(r"pin(?: code)?", r"pincode", r"zip(?: code)?", r"postal(?: code)?", r"postalcode", r"पिन(?: कोड)?")),
    (REFERENCE, _rx(r"bill", r"invoice", r"receipt", r"sample(?: id| no)?", r"specimen", r"visit(?: id| no)",
                    r"trip", r"ticket", r"order", r"batch", r"lot", r"voucher", r"serial", r"sr no", r"s no",
                    r"loinc", r"icd(?: code)?", r"diagnosis code", r"package(?: code)?", r"procedure code",
                    r"bundle", r"encounter id", r"resource id")),
    (ABHA_ADDRESS, _rx(r"abha (?:address|addr|id)", r"phr(?: address)?", r"health id address")),
    (ABHA_NUMBER, _rx(r"abha(?: no| number)?", r"health id(?: no| number)?", r"ndhm(?: id)?", r"abdm(?: id)?")),
    (AADHAAR, _rx(r"aadhaa?r(?: no| number| card)?", r"adhaa?r(?: no)?", r"uid(?:ai)?(?: no)?", r"आधार")),
    (PAN, _rx(r"pan(?: no| number| card)?", r"payer pan", r"pan card")),
    (INSURANCE_ID, _rx(r"pm ?jay(?: id| no)?", r"policy(?: no| number| id)?", r"insurance(?: id| no)?",
                       r"insurer id", r"beneficiary id", r"member id", r"card no", r"ayushman(?: card)?",
                       r"tpa id", r"claim id", r"esic? no", r"cghs(?: no)?")),
    (MRN, _rx(r"uhid", r"mrn", r"mr no", r"cr no", r"reg(?:istration)? (?:no|number|id)", r"reg no",
              r"patient (?:id|ref|reference|no|number|code)", r"patientid", r"pid", r"hospital (?:no|id|uhid|number)",
              r"ipd(?: no| number)?", r"ip no", r"admission (?:no|id|number)", r"adm no", r"case no", r"file no",
              r"opd reg(?:istration)?(?: no)?", r"पंजीकरण(?: सं| संख्या)?", r"आईपीडी(?: सं)?", r"medical record(?: no| number)?")),
    (PHONE, _rx(r"mobile(?: no| number)?", r"mob(?: no)?", r"phone(?: no| number)?", r"ph(?: no)?", r"contact(?: no| number)?",
                r"tel(?:ephone)?", r"cell(?: no)?", r"whats ?app", r"callback", r"call back", r"landline",
                r"मोबाइल", r"फ़ोन", r"फोन", r"संपर्क")),
    (EMAIL, _rx(r"e ?mail(?: id| address)?", r"mail id")),
    (DOB, _rx(r"dob", r"d o b", r"date of birth", r"birth ?date", r"birth", r"janm(?: tithi)?", r"जन्म(?: तिथि)?")),
    (AGE_SEX, _rx(r"age sex", r"age gender", r"umar ling")),
    (AGE, _rx(r"age(?: yrs| years| in years)?", r"umar", r"umr", r"aayu", r"आयु", r"उम्र")),
    (GENDER, _rx(r"gender", r"sex", r"ling", r"लिंग")),
    (NAME_DOCTOR, _rx(r"doctor(?: name)?", r"dr(?: name)?", r"ref(?:erring|erred)? (?:doctor|dr|by)", r"ref doctor",
                      r"consultant", r"physician", r"surgeon", r"practitioner", r"treating", r"attending",
                      r"reviewed by", r"author")),
    (RELATION_VALUE, _rx(r"relation(?:ship)?", r"rel type")),
    (NAME_RELATIVE, _rx(r"father(?: s)?(?: name)?", r"husband(?: s)?(?: name)?", r"guardian(?: name)?", r"relative(?: name)?",
                        r"spouse(?: name)?", r"mother(?: s)?(?: name)?", r"pita", r"pati", r"pita pati(?: ka naam)?",
                        r"wife(?: name)?", r"nok(?: name)?", r"next of kin", r"attendant(?: name)?", r"care of", r"c o",
                        r"informant", r"nominee", r"emergency contact(?: name)?", r"पिता", r"पति", r"अभिभावक")),
    (NAME_PERSON, _rx(r"raised by", r"caller(?: name)?", r"visitor(?: name)?", r"contact person", r"requested by",
                      r"brought by", r"escort", r"witness(?: name)?", r"complainant")),
    (VILLAGE, _rx(r"village(?: mohalla)?", r"gaon", r"gram(?: mohalla)?", r"ग्राम", r"गाँव", r"गांव", r"city", r"town",
                  r"mohalla", r"locality", r"basti", r"mauza")),
    (TEHSIL, _rx(r"tehsil", r"tahsil", r"taluka", r"block", r"mandal", r"तहसील")),
    (DISTRICT, _rx(r"district", r"distt", r"dist", r"jila", r"zila", r"janpad", r"जिला", r"ज़िला")),
    (STATE, _rx(r"state", r"country")),
    (ADDRESS, _rx(r"address(?: line)?", r"addr", r"pata", r"पता", r"street", r"line", r"residence", r"house(?: no)?",
                  r"landmark", r"address note")),
    (NAME_PATIENT, _rx(r"patient(?: s)?(?: full)? name", r"patient", r"pt name", r"full name", r"name", r"naam", r"नाम",
                       r"first(?: name)?", r"fname", r"given(?: name)?", r"last(?: name)?", r"lname", r"surname",
                       r"family(?: name)?", r"middle(?: name)?", r"local(?: name)?", r"मरीज़(?: का नाम)?", r"मरीज")),
    (ORGANIZATION, _rx(r"hospital(?: name)?", r"facility(?: name)?", r"lab(?: name)?", r"laboratory", r"organi[sz]ation",
                       r"clinic", r"provider", r"department", r"dept", r"ward", r"unit", r"system", r"schema",
                       r"exported by", r"scheme", r"payer")),
    (FREE_TEXT, _rx(r"complaints?", r"history", r"notes?", r"remarks?", r"comments?", r"description", r"advice",
                    r"summary", r"course", r"text", r"div", r"narrative", r"impression", r"findings", r"display",
                    r"reason", r"instructions?", r"message", r"body", r"details", r"title", r"source(?: path)?", r"path")),
    (CLINICAL, _rx(r"drug", r"medicine", r"medication", r"strength", r"frequency", r"freq", r"duration", r"dose", r"route",
                   r"test", r"unit", r"value", r"result", r"range", r"ref range", r"reference range", r"bp", r"pulse",
                   r"temp(?: f| c)?", r"spo2", r"weight(?: kg)?", r"height", r"vitals?", r"diagnosis", r"procedure",
                   r"amount(?: inr)?", r"status", r"category", r"form", r"schedule", r"beds", r"occupied", r"cases",
                   r"visits", r"count", r"type", r"specialty", r"qualification")),
]
NON_PERSON_PARENTS = frozenset("""facility hospital lab laboratory organization organisation panel panels test tests
drug drugs medication medicine department ward wards scheme package form product item report system file export
meta coding code qualification serviceprovider location managingorganization performer""".split())
RELATIVE_PARENTS = frozenset("""guardian father husband mother relative spouse nok kin attendant contact informant nominee
relatedperson emergency""".split())
PERSON_PARENTS = frozenset("raised caller visitor requester requested witness escort brought complainant".split())
PATIENT_PARENTS = frozenset("""patient patients pt person persons beneficiary member applicant insured customer client
people registrant""".split())
_GENERIC_NAME_KEYS = ("name", "naam", "नाम", "first", "last", "given", "family", "text", "full", "local", "middle")


def parent_context(parents: tuple[str, ...]) -> str | None:
    """Nearest meaningful parent: 'relative', 'person', 'patient', 'nonperson' or None."""
    for p in reversed(parents):
        words = set(normalize_header(p).split())
        if words & RELATIVE_PARENTS:
            return "relative"
        if words & PERSON_PARENTS:
            return "person"
        if words & PATIENT_PARENTS:
            return "patient"
        if words & NON_PERSON_PARENTS:
            return "nonperson"
    return None


def classify_header(header: str, parents: tuple[str, ...] = (), fhir_type: str | None = None) -> str:
    h = normalize_header(header)
    if fhir_type:
        return _classify_fhir(h, parents, fhir_type)
    ctx = parent_context(parents)
    for cls, rx in RULES:
        if rx.search(h):
            if cls == NAME_PATIENT and h.strip() in _GENERIC_NAME_KEYS:
                return {"relative": NAME_RELATIVE, "person": NAME_PERSON, "patient": NAME_PATIENT,
                        "nonperson": ORGANIZATION}.get(ctx, NAME_PATIENT if not parents else NAME_PERSON)
            if cls in (PHONE, AGE, GENDER, DOB) and ctx == "nonperson":
                return ORGANIZATION if cls == PHONE else cls
            return cls
    if ctx == "relative" and h.strip() in ("relation", "rel"):
        return RELATION_VALUE
    return UNKNOWN


_FHIR_PERSON = {"Patient": NAME_PATIENT, "RelatedPerson": NAME_RELATIVE, "Person": NAME_PERSON}


def _classify_fhir(h: str, parents: tuple[str, ...], rtype: str) -> str:
    keys = [normalize_header(p).strip() for p in parents] + [h.strip()]
    path = " ".join(keys)
    if rtype in ("Practitioner", "PractitionerRole"):
        return NAME_DOCTOR if "name" in keys else (CLINICAL if "qualification" in keys else FREE_TEXT)
    if rtype in ("Organization", "Location", "HealthcareService"):
        return ORGANIZATION if not {"telecom", "identifier"} & set(keys) else REFERENCE
    if "display" in keys and {"subject", "patient", "beneficiary"} & set(keys):
        return NAME_PATIENT
    if "display" in keys and {"author", "performer", "requester", "practitioner", "attender", "recorder"} & set(keys):
        return NAME_DOCTOR
    if rtype in _FHIR_PERSON:
        if "contact" in keys and "name" in keys:
            return NAME_RELATIVE
        if "name" in keys:
            return _FHIR_PERSON[rtype]
        if "identifier" in keys and "value" in keys:
            return MRN
        if "telecom" in keys and "value" in keys:
            return PHONE
        if "birthdate" in path.replace(" ", ""):
            return DOB
        if "address" in keys:
            if "city" in keys:
                return VILLAGE
            if "district" in keys:
                return DISTRICT
            if "state" in keys or "country" in keys:
                return STATE
            if "postalcode" in path.replace(" ", ""):
                return PIN
            if "line" in keys or "text" in keys:
                return ADDRESS
            return FREE_TEXT
        if "extension" in keys and any(k.startswith("value") for k in keys):
            return NAME_PERSON  # the extension URL is not visible here; person data, redact
        if "gender" in keys:
            return GENDER
    if "identifier" in keys and "value" in keys:
        return MRN
    if "source" in keys and "meta" in keys:
        return MRN
    if keys and keys[-1] in ("id", "fullurl", "reference", "system", "url", "profile", "lastupdated", "status",
                             "resourcetype", "use", "code", "contenttype", "language"):
        return REFERENCE
    return FREE_TEXT


# --------------------------------------------------------------------------- value profile
_NAMEISH = {loose_form(w) for w in GIVEN_NAMES + SURNAMES}


def _name_like(v: str) -> bool:
    toks = [t for t in tokenize(TextView.of(v).text) if t.script != "digit"]
    if not 1 <= len(toks) <= 4 or re.search(r"\d", v):
        return False
    if any(t.script == "latin" and t.text.casefold() in NON_NAME for t in toks):
        return False
    return any(loose_form(t.text) in _NAMEISH for t in toks)


@dataclass
class ValueProfile:
    n: int
    phone: float
    aadhaar: float
    email: float
    pan: float
    id_shape: float
    date: float
    numeric: float
    name_like: float
    long_text: float


def profile_values(values) -> ValueProfile:
    vals = [str(v).strip() for v in values if v is not None and str(v).strip()]
    n = len(vals)
    if not n:
        return ValueProfile(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    def share(pred):
        return sum(1 for v in vals if pred(v)) / n
    def full(rx):
        return lambda v: bool(rx.fullmatch(TextView.of(v).text.strip()))
    return ValueProfile(
        n=n,
        phone=share(lambda v: bool(ids.PHONE.fullmatch(TextView.of(v).text.strip()))
                    or 10 <= len(re.sub(r"\D", "", TextView.of(v).text)) <= 13 and bool(re.fullmatch(r"[+\d\s\-().]+", v))),
        aadhaar=share(full(ids.AADHAAR)),
        email=share(full(ids.EMAIL)),
        pan=share(full(ids.PAN)),
        id_shape=share(full(ids.HOSPITAL_ID)),
        date=share(lambda v: bool(find_dates(v)) and len(v) <= 32),
        numeric=share(lambda v: bool(re.fullmatch(r"[\d.,\s/\-+%]+", v))),
        name_like=share(_name_like),
        long_text=share(lambda v: len(v.split()) >= 6),
    )


def classify_field(header: str, values, parents: tuple[str, ...] = (), fhir_type: str | None = None) -> str:
    cls = classify_header(header, parents, fhir_type)
    p = profile_values(values)
    if p.n == 0:
        return cls
    if cls in PERSON_NAME_CLASSES and (p.date > 0.6 or p.numeric > 0.6 or p.phone > 0.6):
        cls = UNKNOWN
    if cls == PHONE and p.phone < 0.3 and p.email < 0.3:
        cls = UNKNOWN if p.numeric < 0.5 else PHONE
    if cls in (DATE, DOB) and p.date < 0.5:
        cls = UNKNOWN if cls == DATE else DOB
    if cls == AGE and p.numeric < 0.5 and p.date > 0.5:
        cls = DOB
    if cls in (UNKNOWN, CLINICAL, REFERENCE, FREE_TEXT, ORGANIZATION):
        if p.email >= 0.6:
            return EMAIL
        if p.aadhaar >= 0.6:
            return AADHAAR
        if p.phone >= 0.6 and p.numeric >= 0.6 and cls not in (CLINICAL,):
            return PHONE
        if p.pan >= 0.6:
            return PAN
    if cls == UNKNOWN:
        if p.id_shape >= 0.6:
            return OTHER_ID
        if p.date >= 0.8:
            return DATE
        if p.name_like >= 0.5 and p.long_text < 0.2:
            return NAME_PERSON
        return FREE_TEXT
    return cls
