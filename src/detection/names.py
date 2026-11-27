"""D6: multilingual person-name detection from context (no name list needed).

Rules, strongest first:
  label        "Name:", "Patient Name:", "नाम:", "मरीज़ का नाम:", "Attendant:" ...
  relation     S/o, D/o, W/o, C/O <Name>, "son of", पिता का नाम ...
  timelog      "18:40 - <Name> (attendant ...)", "14:00 - <Name> - K/C/O ..."
  sender       "[30/05/26, 9:32 pm] <Name>:" (WhatsApp forwards)
  by           "called by <Name> <Surname>", "witnessed by ...", "<Name>'s attendant"
  honorific    "<Name> ji / sahab / behenji / didi / babu / bhai", "<नाम> जी"
  postposition "<Name> ka BP", "<नाम> <उपनाम> को 8 दिन से" (weak)
  bigram       two unknown Title-case words in running text (weak)

Each candidate is trimmed so that it contains at least one identifying token: a token
that is not a common word, a clinical term, a place, a title or a generic name part.
"""
from __future__ import annotations

import re

from core import interfaces as c
from . import clinical_lexicon as clx
from .gazetteer_data import (COMMON_WORDS, GENERIC_NAME_TOKENS, HINDI_COMMON_WORDS, KIN_TERMS, MONTHS,
                             NOT_NAME_BEFORE_HONORIFIC, POSTFIX_HONORIFICS, POSTFIX_HONORIFICS_DEVA,
                             PREFIX_TITLES, PREFIX_TITLES_DEVA, STATES, UP_DISTRICTS)
from .normalization import DEVANAGARI_LETTERS as DL


def _words(items):
    return {w.casefold() for item in items for w in re.split(r"[\s/\-]+", item) if w}


NON_NAME = (set(COMMON_WORDS) | {w.casefold() for w in clx.DRUGS} | {w.casefold() for w in clx.DOSAGE_FORMS}
            | set(clx.SYMPTOMS) | _words(clx.LAB_TESTS) | _words(clx.DISEASES) | _words(clx.DEPARTMENTS)
            | _words(clx.DEGREES) | _words(clx.ORG_SUFFIXES) | set(clx.ORG_WORDS) | _words(UP_DISTRICTS)
            | _words(STATES) | set(MONTHS) | _words(clx.PROCEDURES) | _words(clx.FREQUENCY_WORDS)
            | {"icd", "loinc", "snomed", "fhir", "uhid", "mrn", "ipd", "opd", "abha", "aadhaar", "aadhar",
               "pan", "pmjay", "dob", "rx", "sos", "na", "nil", "tbd", "unknown", "anonymous", "male",
               "female", "transgender", "ward", "bed", "tehsil", "distt", "dist", "district", "gram",
               "village", "mohalla", "pin", "road", "street", "colony", "nagar", "block", "sector",
               "consultant", "attendant", "resident", "intern", "sister", "nurse", "staff", "officer",
               "cmo", "mo", "rmo", "hod", "ot", "icu", "er", "lama", "dama", "ok", "yes", "no", "id",
               "asha", "anm", "anganwadi", "worker", "workers", "team", "admin", "clerk", "desk"})
NON_NAME -= {"asha"}  # a real given name; "ASHA worker" is protected by the clinical shield
# Generic name parts in Devanagari behave like their Latin forms in GENERIC_NAME_TOKENS ("Mohd",
# "Mohammad"): not a name on their own, but part of the name when they lead one, so
# "मोहम्मद आरिफ" is redacted whole, not just "आरिफ".
GENERIC_NAME_TOKENS_DEVA = frozenset({"मो", "मोहम्मद", "मोहम्मद", "मुहम्मद"})
NON_NAME_DEVA = (set(HINDI_COMMON_WORDS) | {"श्री", "श्रीमती", "स्व"}) | GENERIC_NAME_TOKENS_DEVA
TITLES = set(PREFIX_TITLES) | {"dr", "doctor"}
HONORIFICS = set(POSTFIX_HONORIFICS) | set(KIN_TERMS)

ROLE_RELATIVE = frozenset("""father husband mother guardian relative attendant wife son daughter spouse kin
nominee informant caller witness contact emergency brother sister uncle aunt bystander parent parents
pita pati mata patni beta beti पिता पति माता पत्नी पुत्र पुत्री अभिभावक परिजन""".split())
ROLE_DOCTOR = frozenset("doctor dr consultant physician surgeon referring referred ref treating".split())
ROLE_SKIP = frozenset("""drug test hospital lab file ward panel medicine medication brand generic company product
scheme package procedure organization organisation org department insurer tpa user display report sample
item form field column disease diagnosis village district tehsil city street state facility center centre
unit bed device system plan policy gaon gram jila zila pharmacy chemist store shop clinic school""".split())
ROLE_PATIENT_LABELS = ("Patient", "PATIENT", "Pt", "Mareez", "Marij", "Rogi", "Beneficiary", "Applicant",
                       "Visitor", "Client", "Member", "Insured", "Claimant")
RELATIVE_LABELS = ("Attendant", "Guardian", "Father", "Husband", "Mother", "Informant", "Caller",
                   "Relative", "Witness", "Nominee", "Contact person", "Next of kin", "Accompanied by",
                   "Brought by", "Raised by", "Escort", "Bystander", "Wife", "Son", "Daughter")

_TOK = r"(?:(?:Mohd|Md|Sk|Muhd|Mohd)\.|[A-Z][a-z]+(?:['’][a-z]+)?|[A-Z]{2,}(?![a-z])|[A-Z]\.(?=[ ]?[A-Z]))"
_SEP = r"(?:[ ]|(?<=\.)(?=[A-Z]))"
_PHRASE = rf"{_TOK}(?:{_SEP}{_TOK}){{0,3}}"
_PHRASE13 = rf"{_TOK}(?:{_SEP}{_TOK}){{0,2}}"
_ANYWORD = r"(?:[A-Za-z][A-Za-z'’\-]*\.?)"
_DTOK = rf"[{DL}]+"
_DPHRASE = rf"{_DTOK}(?:[ ]{_DTOK}){{0,3}}"
_HON_ALT = "|".join(sorted(HONORIFICS, key=len, reverse=True))
_HON_DEVA_ALT = "|".join(sorted(POSTFIX_HONORIFICS_DEVA, key=len, reverse=True))

LABEL = re.compile(
    rf"(?P<label>(?:\b[A-Za-z][A-Za-z'’.]*[ ]){{0,3}}?(?:Name|NAME|name|Naam|naam)\b(?:[ ]of(?:[ ]the)?[ ][A-Za-z]+)?"
    rf"|(?:{_DTOK}[ ]){{0,3}}नाम"
    rf"|\b(?:{'|'.join(ROLE_PATIENT_LABELS + RELATIVE_LABELS)})\b|मरीज़|मरीज|रोगी)"
    rf"[ \t]*(?:\([^)\n]{{0,20}}\))?[ \t]*[:=][ \t]*"
)
RELATION = re.compile(
    r"(?<![A-Za-z/])(?P<rel>[SDW][ ]?/[ ]?[Oo]|[SDW]\.[ ]?[Oo]\.|C[ ]?/[ ]?[Oo]|[Ss]on of|[Dd]aughter of|"
    r"[Ww]ife of|[Hh]usband of|[Cc]are of|पुत्र|पुत्री|पत्नी|सुपुत्र|सुपुत्री)(?![A-Za-z])\.?[ \t]*[:\-]?[ \t]*"
)
TIMELOG = re.compile(
    rf"(?m)(?:^|[ \t])\d{{1,2}}:\d{{2}}(?:[ ]?[AaPp]\.?[Mm]\.?)?[ \t]*[-–:][ \t]*(?P<name>{_PHRASE})[ \t]*(?=[(\-–,]|$)")
SENDER = re.compile(
    r"\[\d{1,2}/\d{1,2}/\d{2,4},?[ ]\d{1,2}:\d{2}(?:[ ]?[APap][Mm])?\][ ]?(?:-[ ])?(?P<name>[A-Za-z][^:\n\[\]]{1,40}?):")
BY = re.compile(rf"\b(?:by|By|BY|from|From)[ ](?P<name>{_PHRASE})(?P<poss>['’]s)?")
POSSESSIVE = re.compile(
    rf"(?P<name>{_PHRASE13})['’]s[ ](?:attendant|wife|husband|son|daughter|mother|father|family|relative|"
    rf"brother|sister|report|sample|blood|bed|file|case|condition)")
HONORIFIC = re.compile(rf"(?P<name>{_PHRASE13})[ ](?P<hon>(?i:{_HON_ALT}))(?![A-Za-z])")
HONORIFIC_DEVA = re.compile(rf"(?P<name>{_DTOK}(?:[ ]{_DTOK})?)[ ](?P<hon>{_HON_DEVA_ALT})(?![{DL}])")
POSTPOSITION = re.compile(rf"(?P<name>{_PHRASE13})[ ](?:ka|ki|ke|ko|ne)(?![A-Za-z])")
POSTPOSITION_DEVA = re.compile(rf"(?P<name>{_DTOK}(?:[ ]{_DTOK}){{1,2}})[ ](?:को|का|की|के|ने)(?![{DL}])")
BIGRAM = re.compile(r"(?<![A-Za-z.])(?P<name>[A-Z][a-z]{2,}(?:[ ][A-Z][a-z]{2,}){1,2})(?![A-Za-z])")
BEFORE_RELATION = re.compile(
    rf"(?P<name>{_PHRASE13}|{_DTOK}(?:[ ]{_DTOK})?),?[ ](?:[SDW][ ]?/[ ]?[Oo]|पत्नी|पुत्र|पुत्री)(?![A-Za-z])")
_DOCTOR_BEFORE = re.compile(r"(?:\bDr|\bDR|\bdr|\bDoctor|डॉ)\.?[ ]?$")


def _token_spans(text, s, e):
    return [(m.start() + s, m.end() + s, m.group(0)) for m in re.finditer(r"[^\s]+", text[s:e])]


def _is_identifying(tok: str) -> bool:
    t = tok.strip(".,:;()'’").casefold()
    if t.endswith("'s") or t.endswith("’s"):
        t = t[:-2]
    if len(t) < 2 or t.isdigit():
        return False
    if any("\u0900" <= ch <= "\u097f" for ch in t):
        return t not in NON_NAME_DEVA and t not in POSTFIX_HONORIFICS_DEVA and t not in PREFIX_TITLES_DEVA
    return (t not in NON_NAME and t not in GENERIC_NAME_TOKENS and t not in TITLES
            and t not in HONORIFICS and t.isalpha())


def trim_name(text: str, s: int, e: int, keep_honorific: bool = True) -> tuple[int, int] | None:
    """Shrink [s, e) to the name proper; None if no identifying token remains."""
    toks = _token_spans(text, s, e)
    def generic(tok: str) -> bool:
        t = tok.strip(".,:;").casefold()
        return t in GENERIC_NAME_TOKENS or t in GENERIC_NAME_TOKENS_DEVA

    while toks and not _is_identifying(toks[0][2]) and not generic(toks[0][2]):
        toks.pop(0)
    while toks:
        last = toks[-1][2].strip(".,:;").casefold()
        if _is_identifying(toks[-1][2]) or generic(toks[-1][2]) or (keep_honorific and last in HONORIFICS):
            break
        toks.pop()
    if not toks or not any(_is_identifying(t[2]) for t in toks):
        return None
    s2, e2 = toks[0][0], toks[-1][1]
    while e2 > s2 and text[e2 - 1] in ".,:;)'’":
        if text[e2 - 1] == "." and text[s2:e2].split()[-1].rstrip(".").casefold() in {"mohd", "md", "sk", "muhd"}:
            break
        e2 -= 1
    if text[e2 - 2:e2] in ("'s", "’s"):
        e2 -= 2
    return (s2, e2) if e2 > s2 else None


def _cand(s, e, category, source, tier=c.TIER_EXPLICIT_IDENTITY, conf=0.9):
    role = "relative" if category == c.RELATIVE_NAME else ("patient" if category == c.PATIENT_NAME else None)
    action = c.PSEUDONYMIZE if category == c.PATIENT_NAME else c.REDACT
    return c.SpanCandidate(s, e, category, role, conf, tier, source, action)


def _label_role(label: str) -> str | None:
    words = {w.casefold().strip(".'’") for w in re.split(r"[\s/()]+", label) if w}
    if words & ROLE_SKIP or words & ROLE_DOCTOR:
        return None
    if words & ROLE_RELATIVE or any(w.endswith("'s") and w[:-2] in ROLE_RELATIVE for w in words):
        return c.RELATIVE_NAME
    return c.PATIENT_NAME


_VALUE_LAT = re.compile(rf"{_ANYWORD}(?:[ ]{_ANYWORD}){{0,4}}")
_VALUE_STOP = frozenset("""age sex gender reg uhid mrn mob mobile phone ph dob date ipd ip no s/o d/o w/o c/o
yrs years y aged address addr ward bed""".split())


def _value_after(text: str, pos: int) -> tuple[int, int] | None:
    """The name value that follows a label at `pos` (Latin or Devanagari)."""
    m = re.match(_DPHRASE, text[pos:pos + 80])
    if m and m.group(0):
        e = pos + m.end()
        toks = _token_spans(text, pos, e)
        keep = []
        for t in toks:
            if t[2] in ("आयु", "उम्र", "पता", "मोबाइल", "उम्र:", "आयु:"):
                break
            keep.append(t)
        return (keep[0][0], keep[-1][1]) if keep else None
    m = _VALUE_LAT.match(text, pos)
    if not m:
        return None
    toks = _token_spans(text, pos, m.end())
    keep = []
    for t in toks:
        w = t[2].strip(".,:;").casefold()
        if w in _VALUE_STOP or re.match(r"^[sdwc]/o$", w):
            break
        keep.append(t)
    return (keep[0][0], keep[-1][1]) if keep else None


def _relation_value(text: str, pos: int) -> tuple[int, int] | None:
    seg = text[pos:pos + 80]
    m = re.match(rf"(?:(?:Shri|Sri|Sh|Late|Lt|Mr|Mohd|Md|Smt|श्री|स्व)\.?[ ])?(?:{_PHRASE}|{_DPHRASE})", seg)
    if not m:
        return None
    return pos + m.start(), pos + m.end()


def detect_names(text: str) -> list[c.SpanCandidate]:
    out: list[c.SpanCandidate] = []

    def add(s, e, category, source, tier=c.TIER_EXPLICIT_IDENTITY, conf=0.9, keep_hon=True):
        t = trim_name(text, s, e, keep_hon)
        if t:
            out.append(_cand(t[0], t[1], category, source, tier, conf))

    for m in LABEL.finditer(text):
        label = m.group("label")
        category = _label_role(label)
        if category is None:
            continue
        v = _value_after(text, m.end())
        if v and re.match(r"(?:Dr|DR|dr|Doctor|डॉ)\b\.?", text[v[0]:v[1]]):
            continue  # a doctor's name stays
        if v:
            strict = not re.search(r"name|naam|नाम", label, re.IGNORECASE)
            if strict and not re.match(_TOK + "|" + _DTOK, text[v[0]:v[1]]):
                continue  # "Patient: admitted ..." is not a name
            add(v[0], v[1], category, "label", conf=0.95)
    for m in RELATION.finditer(text):
        rel = m.group("rel").replace(" ", "").upper()
        v = _relation_value(text, m.end())
        if not v:
            continue
        if rel.startswith("C/O"):
            first = text[v[0]:v[1]].split()[0].strip(".,").casefold()
            if first in clx.SYMPTOMS or first in NON_NAME:
                continue
        add(v[0], v[1], c.RELATIVE_NAME, "relation", conf=0.95)
    for m in TIMELOG.finditer(text):
        tail = text[m.end("name"):m.end("name") + 14].casefold()
        if re.match(r"^\s*(?:dr|doctor)\b", m.group("name").casefold()):
            continue
        cat = c.RELATIVE_NAME if re.match(r"\s*\((?:attendant|relative|visitor|guardian)", tail) else c.PATIENT_NAME
        add(m.start("name"), m.end("name"), cat, "timelog")
    for m in SENDER.finditer(text):
        add(m.start("name"), m.end("name"), c.RELATIVE_NAME, "sender")
    for m in BY.finditer(text):
        name = m.group("name")
        if re.match(r"(?:Dr|DR|Doctor)\b", name):
            continue
        n_ident = sum(_is_identifying(t) for t in name.split())
        if n_ident >= 2 or (m.group("poss") and n_ident >= 1):
            add(m.start("name"), m.end("name"), c.PERSON_NAME, "by")
    for m in POSSESSIVE.finditer(text):
        add(m.start("name"), m.end("name"), c.PATIENT_NAME, "possessive")
    for rx, src in ((HONORIFIC, "honorific"), (HONORIFIC_DEVA, "honorific_deva")):
        for m in rx.finditer(text):
            if _DOCTOR_BEFORE.search(text[max(0, m.start() - 8):m.start()]):
                continue
            hon = m.group("hon").casefold()
            cat = c.RELATIVE_NAME if hon in KIN_TERMS and hon not in ("didi",) else c.PATIENT_NAME
            add(m.start("name"), m.end("hon"), cat, src)
    for m in POSTPOSITION.finditer(text):
        if _DOCTOR_BEFORE.search(text[max(0, m.start() - 8):m.start()]):
            continue
        add(m.start("name"), m.end("name"), c.PATIENT_NAME, "postposition", c.TIER_WEAK, 0.6)
    for m in POSTPOSITION_DEVA.finditer(text):
        add(m.start("name"), m.end("name"), c.PATIENT_NAME, "postposition_deva", c.TIER_WEAK, 0.6)
    for m in BEFORE_RELATION.finditer(text):
        before = text[max(0, m.start() - 12):m.start()]
        if re.search(r"(?:[SDWC][ ]?/[ ]?[Oo]|Name|नाम)[ :]*$", before):
            continue  # "S/o Ramesh S/o ..." chains and labelled values are handled above
        add(m.start("name"), m.end("name"), c.PATIENT_NAME, "before_relation")
    for m in BIGRAM.finditer(text):
        if _DOCTOR_BEFORE.search(text[max(0, m.start() - 8):m.start()]):
            continue
        toks = m.group("name").split()
        # Requiring every token to be individually identifying rejected a real name
        # whenever its second token was a generic name-part on its own (docs/DATASET.md:
        # "Devi, Kumar, Md. and ji don't identify anyone on their own" -- but "Shabana
        # Bano" together is a specific person, same as the label/relation/honorific
        # paths above already treat it via trim_name's "keep if ANY token identifies,
        # allow a generic token to ride along" rule). A plain common word (NON_NAME) in
        # the bigram still rejects it outright, so "General Hospital"-shaped false
        # positives stay excluded; only a generic NAME PART bypasses the all() check.
        def _generic_part(tok: str) -> bool:
            t = tok.strip(".,:;").casefold()
            return t in GENERIC_NAME_TOKENS or t in GENERIC_NAME_TOKENS_DEVA

        if all(_is_identifying(t) or _generic_part(t) for t in toks) and any(_is_identifying(t) for t in toks):
            add(m.start("name"), m.end("name"), c.PERSON_NAME, "bigram", c.TIER_WEAK, 0.5)
    return out
