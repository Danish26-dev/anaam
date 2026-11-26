"""D9: clinical preservation check.

Compares the protected clinical values found in the ORIGINAL text with those found in the
OUTPUT text, as multisets of normalized strings. Reports only category counts, never text.
Values that the privacy layer is allowed to transform (dates, ages) are not protected values.
"""
from __future__ import annotations

from collections import Counter

from core import interfaces as c
from detection.clinical import detect_clinical
from detection.normalization import normalize_key

# Medical content only. Ward and organization names are protected from being read as PII,
# but they also occur inside addresses ("Ward 8" as a locality) and file-level metadata,
# where redacting them is correct; counting them as clinical loss quarantined good files.
CORE = (c.MEDICATION, c.DOSE, c.FREQUENCY, c.VITAL, c.LAB, c.DIAGNOSIS, c.DIAGNOSIS_CODE, c.PROCEDURE,
        c.COMPLAINT, c.HISTORY, c.EPONYM, c.DOCTOR)


def protected_multiset(text: str, categories=CORE) -> Counter:
    out: Counter = Counter()
    for s in detect_clinical(text):
        if s.proposed_action == c.KEEP and s.category in categories:
            out[(s.category, normalize_key(text[s.start:s.end]))] += 1
    return out


def clinical_loss(original: str, output: str) -> dict[str, int]:
    """Category -> number of protected values present in `original` but missing in `output`."""
    before, after = protected_multiset(original), protected_multiset(output)
    lost: Counter = Counter()
    for key, n in before.items():
        missing = n - after.get(key, 0)
        if missing > 0:
            lost[key[0]] += missing
    return dict(lost)
