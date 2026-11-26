"""D9: leak checks on candidate output text.

Two independent checks (a name the detector never understood can only be caught by the
first, so both exist):

  1. KNOWN values: every name token, ID digit run, phone and village harvested from the
     input is searched in the output (after the same normalization the official scorer
     uses, plus decoding of base64 / escapes inside it). A hit is a leak even if no
     detector would call it PII. Hits inside a protected clinical span are allowed
     ("Dr. Venkatesh Rao" keeps its doctor token).
  2. RESIDUAL detection: the detection engine runs again on the output. A direct
     identifier or explicit name that survives is a leak. Placeholders, pseudonyms,
     shifted dates, banded ages and 3-digit PIN prefixes are allowed.

Findings carry positions and categories, never the matched text.
"""
from __future__ import annotations

import re

from core import interfaces as c
from detection.attachments import find_payloads
from detection.clinical import detect_clinical
from detection.engine import DetectionEngine
from detection.normalization import TextView
from detection.transliteration import loose_form, name_key

HEADER_WEAK = frozenset({"postposition", "postposition_deva", "bigram", "lexicon_token", "lexicon_place"})
DEFAULT_ALLOWED_CATEGORIES = frozenset({
    c.DATE, c.DOB, c.AGE, c.TEHSIL, c.DISTRICT, c.DOCTOR, c.WARD, c.ORGANIZATION,
})
_DIGIT_RUN = re.compile(r"(?<!\d)\d(?:[ \-./]?\d)*(?!\d)")
# \w splits Devanagari words at vowel signs (combining marks), so the script range is explicit
_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|[\u0900-\u0963\u0971-\u097F]+")


class LeakVerifier:
    def __init__(self, engine: DetectionEngine, allowed_tokens: set[str] | None = None,
                 allowed_categories: frozenset[str] = DEFAULT_ALLOWED_CATEGORIES,
                 allow_full_pin: bool = False) -> None:
        self.engine = engine
        self.allowed_tokens = {t.casefold() for t in (allowed_tokens or set())}
        self.allowed_categories = allowed_categories
        self.allow_full_pin = allow_full_pin
        self._known: dict | None = None

    # ------------------------------------------------------------------ index
    def refresh(self) -> None:
        """Rebuild the known-value index (call after the engine's prepare pass)."""
        k = self.engine.lexicon.known_values()
        names = {t for t in k["name_tokens"] if len(t) >= 3}
        self._known = {
            "name_exact": {TextView.of(t).text.casefold() for t in names},
            "name_loose": {loose_form(t) for t in names if len(loose_form(t)) >= 4},
            "name_skel": {name_key(t) for t in names if len(name_key(t)) >= 3},
            "doctor": {TextView.of(t).text.casefold() for t in k["doctor_tokens"]},
            "doctor_full_rx": self._doctor_regex(k["doctor_full"]),
            "ids": {d for d in k["digit_ids"] if len(d) >= 6} | {d for d in k["digit_cores"] if len(d) >= 5},
            "places": set(k["places"]),
        }

    @staticmethod
    def _doctor_regex(full_names: set[str]):
        parts = [r"[ \t]+".join(re.escape(TextView.of(w).text) for w in n.split()) for n in sorted(full_names)]
        return re.compile(r"(?<![A-Za-z])(?:" + "|".join(parts) + r")(?![A-Za-z])", re.IGNORECASE) if parts else None

    # ------------------------------------------------------------------ scans
    def _views(self, text: str) -> list[tuple[str, int]]:
        """(normalized text, original offset base). Encoded payload contents are appended."""
        out = [(TextView.of(text).text, 0)]
        for p in find_payloads(text):
            if p.decoded:
                out.append((TextView.of(p.decoded).text, -1))
        return out

    def scan_known(self, text: str) -> list[c.LeakFinding]:
        if self._known is None:
            self.refresh()
        k = self._known
        findings: list[c.LeakFinding] = []
        for norm, base in self._views(text):
            protected = [(s.start, s.end) for s in detect_clinical(norm) if s.proposed_action == c.KEEP]
            if k["doctor_full_rx"] is not None:   # a harvested doctor's full name stays, with or without "Dr."
                protected += [(m.start(), m.end()) for m in k["doctor_full_rx"].finditer(norm)]
            pos = lambda a, b: (a, b) if base == 0 else (-1, -1)   # offsets only for the main view
            for m in _WORD.finditer(norm):
                tok = m.group(0)
                low = tok.casefold()
                if low in self.allowed_tokens or len(low) < 3:
                    continue
                # exact or spelling-folded match; the skeleton (cross-script) only for Devanagari
                # tokens, because short Latin skeletons collide with ordinary words
                is_deva = any("\u0900" <= ch <= "\u097f" for ch in tok)
                hit = (low in k["name_exact"] or loose_form(tok) in k["name_loose"]
                       or (is_deva and len(name_key(tok)) >= 3 and name_key(tok) in k["name_skel"]))
                if not hit:
                    continue
                if any(s <= m.start() and m.end() <= e for s, e in protected):
                    continue
                if low in k["doctor"] and self._inside_doctor_context(norm, m.start()):
                    continue
                s, e = pos(m.start(), m.end())
                findings.append(c.LeakFinding(s, e, "KNOWN_NAME", c.CONTENT if base == 0 else c.BASE64))
            for m in _DIGIT_RUN.finditer(norm):
                d = re.sub(r"\D", "", m.group(0))
                if d in k["ids"] or (len(d) in (11, 12, 13) and d[-10:] in k["ids"]):
                    s, e = pos(m.start(), m.end())
                    findings.append(c.LeakFinding(s, e, "KNOWN_ID", c.CONTENT if base == 0 else c.BASE64))
            if k["places"]:
                toks = [(m.start(), m.end(), name_key(m.group(0))) for m in _WORD.finditer(norm)]
                for i in range(len(toks)):
                    for size in (3, 2, 1):
                        if i + size <= len(toks):
                            key = " ".join(t[2] for t in toks[i:i + size])
                            if key in k["places"]:
                                s, e = pos(toks[i][0], toks[i + size - 1][1])
                                findings.append(c.LeakFinding(s, e, "KNOWN_PLACE",
                                                              c.CONTENT if base == 0 else c.BASE64))
                                break
        return findings

    @staticmethod
    def _inside_doctor_context(norm: str, start: int) -> bool:
        return bool(re.search(r"(?:\bDr|\bDR|\bDoctor|डॉ|डा)\.?\s+(?:[A-Z][\w'’]*\s+){0,2}$",
                              norm[max(0, start - 40):start]))

    def scan_residual(self, text: str, order: str | None = None, structured: bool = False,
                      header_len: int = 0) -> list[c.LeakFinding]:
        """`structured` (CSV/JSON/FHIR): an ID-shaped token with no label is probably a bill or
        visit number, so only labelled, learned or known identifiers count there."""
        findings = []
        for s in self.engine.detect_text(text, order):
            if s.action == c.KEEP or s.category in self.allowed_categories:
                continue
            if structured and s.reason_code == "id_shape":
                continue
            if s.start < header_len and (s.reason_code in HEADER_WEAK):
                continue
            if self._is_allowed_surface(text[s.start:s.end], s.category):
                continue
            findings.append(c.LeakFinding(s.start, s.end, f"RESIDUAL_{s.category}", c.CONTENT))
        return findings

    def _is_allowed_surface(self, surface: str, category: str) -> bool:
        s = surface.strip()
        low = s.casefold()
        if low in self.allowed_tokens or any(len(t) >= 6 and t in low for t in self.allowed_tokens):
            return True                                        # pseudonyms
        if re.fullmatch(r"\[[A-Z\- ]+\]", s):                  # typed placeholders
            return True
        if category == c.PIN:
            return self.allow_full_pin or bool(re.fullmatch(r"\d{3}\*{3}", s))
        return False

    def scan(self, text: str, order: str | None = None, structured: bool = False,
             header_len: int = 0) -> list[c.LeakFinding]:
        """`header_len`: characters of a CSV header row. Weak guesses inside it are ignored
        ("Pita/Pati ka Naam" is a label, not a name); identifiers and known values still count."""
        found = self.scan_known(text) + self.scan_residual(text, order, structured, header_len)
        seen, out = set(), []
        for f in found:
            key = (f.start, f.end, f.category)
            if key not in seen:
                seen.add(key)
                out.append(f)
        return out
