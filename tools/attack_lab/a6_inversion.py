"""A6: pseudonym inversion.

For each patient we KNOW the true originals for (practice-only, via dev/truth/truth.json),
build a dictionary of common transforms of those originals -- case changes, digits-only,
unkeyed hashes (MD5/SHA-1/SHA-256/SHA-512, full and truncated prefixes), base64, reversal
-- and check whether that patient's actual exported pseudonym equals, prefixes, or embeds
any transform. HMAC-with-secret pseudonyms (which is what pseudonyms.py produces) should
never match an UNKEYED hash of the original, by construction; this attack exists to catch
a regression (e.g. someone swapping HMAC for plain SHA-256 "for simplicity").
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass


def _unkeyed_transforms(original: str) -> set[str]:
    """Every unkeyed transform the attacker would try against one original value."""
    out = {original, original.lower(), original.upper()}
    digits_only = "".join(ch for ch in original if ch.isdigit())
    if digits_only:
        out.add(digits_only)
    for value in list(out):
        out.add(value[::-1])  # reversal
    for algo in ("md5", "sha1", "sha256", "sha512"):
        for value in (original, original.lower(), digits_only):
            if not value:
                continue
            h = hashlib.new(algo, value.encode("utf-8")).hexdigest()
            out.add(h)
            for prefix_len in (8, 12, 16):
                if len(h) >= prefix_len:
                    out.add(h[:prefix_len])
    try:
        out.add(base64.b64encode(original.encode("utf-8")).decode("ascii").rstrip("="))
    except Exception:  # noqa: BLE001 - defensive, non-ASCII originals are rare here
        pass
    return out


@dataclass
class A6Result:
    total_patients_checked: int
    inverted_patients: list[str]

    @property
    def inversion_rate(self) -> float:
        return len(self.inverted_patients) / self.total_patients_checked if self.total_patients_checked else 0.0


def run_a6(patient_originals: dict[str, list[str]], pseudonym_by_patient: dict[str, str]) -> A6Result:
    """patient_originals: true patient id -> list of known original strings (UHID, Aadhaar,
    phone, ABHA, full Latin name, ...), gathered from truth.json (practice-only).
    pseudonym_by_patient: true patient id -> the pseudonym Anaam actually assigned them.
    """
    inverted = []
    for true_patient, originals in patient_originals.items():
        pseudonym = pseudonym_by_patient.get(true_patient)
        if not pseudonym:
            continue
        pseudonym_clean = pseudonym.removeprefix("PSN-").lower()
        transforms: set[str] = set()
        for original in originals:
            transforms |= _unkeyed_transforms(original)
        transforms_lower = {t.lower() for t in transforms if len(t) >= 6}

        hit = any(
            pseudonym_clean == t or pseudonym_clean.startswith(t) or t in pseudonym_clean
            for t in transforms_lower
        )
        if hit:
            inverted.append(true_patient)

    return A6Result(total_patients_checked=len(patient_originals), inverted_patients=inverted)
