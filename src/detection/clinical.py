"""D2: Clinical Shield. Finds medical values that must survive byte-for-byte.

`detect_clinical(text)` runs on a normalized view and returns protected SpanCandidates
(tier TIER_PROTECTED, action KEEP). Bare hospital wards ("Ward 20") are returned with
source "ward_bare": the caller decides if they are an address locality instead.

Generic patterns only protect the value itself ("650 mg", "14.0 g/dL"), never the words
before it, so a clinical span can never swallow a patient's name.
"""
from __future__ import annotations

import re

from .. import contracts as c
from . import clinical_lexicon as lx
from . import clinical_patterns as P

_CHAIN = re.compile(
    r"\s*(?:,\s*)?(?:"
    + P.FREQ_PATTERN.pattern + "|" + P.FREQ_WORD.pattern + "|" + P.DURATION.pattern + "|"
    + P.ROUTE.pattern
    + r"|\d+\s?puffs?|after each loose stool|after food|before food|at night|once daily"
    r"|twice daily|thrice daily|daily|every \d+ hours"
    + r")"
)
_DRUG_CONT = re.compile(r"\s+(?:\+\s+)?([A-Za-z][A-Za-z\-]*)")
_BARE_NUM = re.compile(r"\s+\d{2,4}(?![\d.]|\s?(?:mg|mcg|g|ml)\b)")
_DOSE_AFTER = re.compile(r"\s*(?:" + P.DOSE.pattern + r")")


def _cand(start, end, category, source, confidence=0.9):
    return c.SpanCandidate(start, end, category, None, confidence, c.TIER_PROTECTED, source, c.KEEP)


def _extend_chain(text: str, end: int) -> int:
    while True:
        m = _CHAIN.match(text, end)
        if not m or m.end() == end:
            return end
        end = m.end()


def _medications(text: str, out: list) -> None:
    for m in P.DRUG.finditer(text):
        start, end = m.start(), m.end()
        before = text[max(0, start - 14):start]
        fm = re.search(r"(?:" + P.FORM.pattern + r")\s+$", before, re.IGNORECASE)
        if fm:
            start -= len(before) - fm.start()
        for _ in range(4):
            cm = _DRUG_CONT.match(text, end)
            if not cm or cm.group(1).casefold() not in lx.DRUGS | lx.DOSAGE_FORMS:
                break
            end = cm.end()
        dm = _DOSE_AFTER.match(text, end)
        if dm:
            end = dm.end()
        else:
            bm = _BARE_NUM.match(text, end)
            if bm:
                end = bm.end()
        end = _extend_chain(text, end)
        out.append(_cand(start, end, c.MEDICATION, "drug"))
    # form-prefixed unknown drug followed by a dose: "Tab Xyzomab 50 mg"
    for m in P.FORM.finditer(text):
        tail = text[m.end():m.end() + 60]
        dm = re.match(r"\s+((?:[A-Za-z][\w\-]*\s+){1,3}?)(" + P.DOSE.pattern + ")", tail)
        if dm:
            end = _extend_chain(text, m.end() + dm.end())
            out.append(_cand(m.start(), end, c.MEDICATION, "form_drug", 0.8))


def _clause_end(text: str, start: int, limit: int = 120) -> int:
    m = P.CLAUSE_END.search(text, start, min(len(text), start + limit))
    return m.start() if m else min(len(text), start + limit)


def _complaints_and_history(text: str, out: list) -> None:
    for m in P.COMPLAINT_HEAD.finditer(text):
        nxt = re.match(r"([A-Za-z]+|\d)", text[m.end():])
        if not nxt:
            continue
        word = nxt.group(1)
        if word.casefold() in lx.SYMPTOMS or word.islower() or word.isdigit():
            out.append(_cand(m.start(), _clause_end(text, m.end()), c.COMPLAINT, "c/o"))
    for m in P.COMPLAINT_LABEL.finditer(text):
        out.append(_cand(m.start(), _clause_end(text, m.end()), c.COMPLAINT, "complaint_label"))
    for m in P.HISTORY_HEAD.finditer(text):
        if re.match(r"\s*[A-Z][a-z]+\s+[A-Z][a-z]+", text[m.end():]) and \
                text[m.end():m.end() + 1].isupper() and m.group(0).strip().upper() == "H/O":
            # "H/O <Name Surname>" is unusual; still protect the clause, names win in resolver
            pass
        out.append(_cand(m.start(), _clause_end(text, m.end()), c.HISTORY, "history"))


def detect_clinical(text: str) -> list[c.SpanCandidate]:
    out: list[c.SpanCandidate] = []
    _medications(text, out)
    for m in P.DOSE.finditer(text):
        out.append(_cand(m.start(), _extend_chain(text, m.end()), c.DOSE, "dose"))
    for m in P.FREQ_PATTERN.finditer(text):
        out.append(_cand(m.start(), m.end(), c.FREQUENCY, "freq"))
    for m in P.FREQ_WORD.finditer(text):
        out.append(_cand(m.start(), _extend_chain(text, m.end()), c.FREQUENCY, "freq_word", 0.7))
    for m in P.DURATION.finditer(text):
        out.append(_cand(m.start(), m.end(), c.DURATION, "duration"))
    for m in P.VITAL.finditer(text):
        out.append(_cand(m.start(), m.end(), c.VITAL, "vital"))
    for m in P.LAB.finditer(text):
        out.append(_cand(m.start(), m.end(), c.LAB, "lab"))
    for m in P.LAB_NAME.finditer(text):
        out.append(_cand(m.start(), m.end(), c.LAB, "lab_name", 0.6))
    for m in re.finditer(r"(?<![\w.])\d+(?:\.\d+)?\s?(?:" + P._LAB_UNIT + r")(?![A-Za-z])", text):
        out.append(_cand(m.start(), m.end(), c.LAB, "lab_value", 0.7))
    for m in P.LAB_RANGE_CTX.finditer(text):
        out.append(_cand(m.start(1), m.end(1), c.LAB_RANGE, "range"))
    for m in P.ICD10.finditer(text):
        out.append(_cand(m.start(), m.end(), c.DIAGNOSIS_CODE, "icd10"))
    for m in P.LOINC_CTX.finditer(text):
        out.append(_cand(m.start(1), m.end(1), c.DIAGNOSIS_CODE, "loinc"))
    for m in P.DISEASE.finditer(text):
        out.append(_cand(m.start(), m.end(), c.DIAGNOSIS, "disease"))
    for m in P.EPONYM.finditer(text):
        out.append(_cand(m.start(), m.end(), c.EPONYM, "eponym"))
    for m in P.PROCEDURE.finditer(text):
        out.append(_cand(m.start(), m.end(), c.PROCEDURE, "procedure"))
    _complaints_and_history(text, out)
    for m in P.DOCTOR.finditer(text):
        out.append(_cand(m.start(), m.end(), c.DOCTOR, "doctor", 0.95))
    for m in P.DOCTOR_DEVA.finditer(text):
        out.append(_cand(m.start(), m.end(), c.DOCTOR, "doctor_deva", 0.9))
    for m in P.WARD.finditer(text):
        bare = "(" not in m.group(0)
        out.append(_cand(m.start(), m.end(), c.WARD, "ward_bare" if bare else "ward"))
    for m in P.BED.finditer(text):
        out.append(_cand(m.start(), m.end(), c.CLINICAL_CONTEXT, "bed", 0.7))
    for m in P.DEPARTMENT.finditer(text):
        out.append(_cand(m.start(), m.end(), c.DEPARTMENT, "department", 0.7))
    for m in P.ORGANIZATION.finditer(text):
        out.append(_cand(m.start(), m.end(), c.ORGANIZATION, "organization", 0.85))
    for m in P.CONTEXT.finditer(text):
        out.append(_cand(m.start(), m.end(), c.CLINICAL_CONTEXT, "context"))
    return out


def doctor_name_spans(text: str) -> list[tuple[int, int]]:
    """Offsets of the name part of every doctor mention (for the doctor lexicon)."""
    spans = [(m.start(1), m.end(1)) for m in P.DOCTOR.finditer(text)]
    spans += [(m.start(1), m.end(1)) for m in P.DOCTOR_DEVA.finditer(text)]
    return spans
