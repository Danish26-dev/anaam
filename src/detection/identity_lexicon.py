"""D7: self-harvested identity lexicon (built at run time from the input itself).

Pass 1 harvests high-confidence identities: names from name columns and strong context
rules, identifier values, ID templates and village names. Pass 2 finds them again in free
text, file names and metadata, across scripts and spelling variants.

Matching rules (precision first):
  * full name   two or more adjacent tokens that match the same person (spelling folded with
                `loose_form`, or cross-script / variant with `name_key`)  -> explicit tier
  * one token   a single token whose folded spelling equals a harvested name token -> weak
                tier (protected clinical spans and doctor lines win against it)
  * fuzzy-only  single tokens matching only by `name_key` are never redacted; they are
                kept for linkage as the plan requires.
Doctor names are harvested separately and protect their full-name mentions.
Everything stays in memory. Nothing here is logged or written to disk.
"""
from __future__ import annotations

import re
from collections import defaultdict

try:
    from .. import contracts as c
except ImportError:  # loaded as a top-level `detection` package (Omkar's sys.path layout)
    import contracts as c
from .gazetteer_data import GENERIC_NAME_TOKENS
from .identifiers import IdTemplates, id_digit_core
from .names import HONORIFICS, NON_NAME, NON_NAME_DEVA, TITLES
from .normalization import tokenize
from .transliteration import loose_form, name_key

_GAP = re.compile(r"^[ \t_.\-]{1,3}$")
_DIGIT_RUN = re.compile(r"(?<![\d])\d{2,}(?:[ \-.]\d{2,}){0,4}(?![\d])")
ROLE_PATIENT, ROLE_RELATIVE, ROLE_DOCTOR, ROLE_OTHER = "patient", "relative", "doctor", "other"


# generic parts (Kaur, Devi, Khatoon, ...) compared by folded spelling so the Devanagari
# forms (कौर, ख़ातून) are recognised as generic too
_GENERIC_LOOSE = {loose_form(g) for g in GENERIC_NAME_TOKENS | TITLES | HONORIFICS} - {""}


def _name_tokens(name: str) -> list[str]:
    out = []
    for t in tokenize(name):
        if t.script == "digit":
            continue
        low = t.text.casefold()
        if t.script == "latin" and (low in NON_NAME or low in GENERIC_NAME_TOKENS or low in TITLES
                                    or low in HONORIFICS or len(low) < 2):
            continue
        if t.script == "deva" and (t.text in NON_NAME_DEVA or loose_form(t.text) in _GENERIC_LOOSE):
            continue
        out.append(t.text)
    return out


class IdentityLexicon:
    def __init__(self) -> None:
        self._people: list[tuple[str, tuple[str, ...]]] = []
        self._seen: dict[tuple[str, tuple[str, ...]], int] = {}
        self._by_loose: dict[str, set[tuple[int, int]]] = defaultdict(set)
        self._by_key: dict[str, set[tuple[int, int]]] = defaultdict(set)
        # cross-script: skeleton key of Devanagari tokens and of Latin tokens, kept apart
        self._by_key_script: dict[tuple[str, str], set[tuple[int, int]]] = defaultdict(set)
        self.ids: dict[str, str] = {}
        self.cores: set[str] = set()
        self.templates = IdTemplates()
        self._places: dict[tuple[str, ...], str] = {}
        self._place_max = 1

    # ------------------------------------------------------------------ harvesting
    def add_name(self, name: str, role: str) -> bool:
        toks = _name_tokens(name)
        if not toks:
            return False
        louse = tuple(loose_form(t) for t in toks)
        key = (role, louse)
        if key in self._seen:
            return False
        idx = len(self._people)
        self._seen[key] = idx
        self._people.append((role, tuple(toks)))
        for pos, t in enumerate(toks):
            lf = louse[pos]
            if len(lf) >= 3 or any("\u0900" <= ch <= "\u097f" for ch in t):
                self._by_loose[lf].add((idx, pos))
            k = name_key(t)
            if len(k) >= 2:
                self._by_key[k].add((idx, pos))
                if len(k) >= 3:
                    self._by_key_script[(k, _script(t))].add((idx, pos))
        return True

    def add_id(self, value: str, category: str) -> None:
        digits = "".join(ch for ch in value if ch.isdigit())
        if category in (c.PHONE, c.AADHAAR, c.ABHA_NUMBER) and len(digits) >= 10:
            self.ids[digits[-10:] if category == c.PHONE else digits] = category
        elif category == c.MRN:
            self.templates.add(value)
            core = id_digit_core(value)
            if len(core) >= 6 or (len(core) == 5 and core.startswith("0")):
                self.cores.add(core)
            if len(digits) >= 6:
                self.ids.setdefault(digits, c.MRN)
        elif category == c.INSURANCE_ID and len(digits) >= 8:
            self.ids.setdefault(digits, c.INSURANCE_ID)

    def add_place(self, value: str, category: str = c.VILLAGE) -> None:
        toks = [t.text for t in tokenize(value) if t.script != "digit"]
        if not toks:
            return
        if len(toks) == 1 and len(loose_form(toks[0])) < 5:
            return
        if all(t.casefold() in NON_NAME for t in toks):
            return
        key = tuple(name_key(t) for t in toks)
        if sum(len(k) for k in key) < 4 or any(len(k) < 2 for k in key):
            return
        self._places.setdefault(key, category)
        self._place_max = max(self._place_max, len(key))

    @property
    def size(self) -> int:
        return len(self._people)

    def known_values(self) -> dict:
        """Read-only view for the verifier. Values stay in memory; never log them."""
        person, doctor, doctor_full = set(), set(), set()
        for role, toks in self._people:
            (doctor if role == ROLE_DOCTOR else person).update(toks)
            if role == ROLE_DOCTOR and len(toks) >= 2:
                doctor_full.add(" ".join(toks))
        return {
            "name_tokens": person,                 # patient / relative / other names (original spelling)
            "doctor_tokens": doctor,
            "doctor_full": doctor_full,            # full doctor names ("Venkatesh Rao")
            "digit_ids": dict(self.ids),           # digits -> category
            "digit_cores": set(self.cores),
            "places": [" ".join(k) for k in self._places],   # name_key skeletons
        }

    # ------------------------------------------------------------------ matching
    def _qualifies(self, tok, single: bool) -> bool:
        low = tok.text.casefold()
        if tok.script == "latin":
            if low in NON_NAME or low in GENERIC_NAME_TOKENS or low in TITLES or low in HONORIFICS:
                return False
            if single and not tok.text[0].isupper():
                return False
            return len(low) >= 3
        return tok.text not in NON_NAME_DEVA and loose_form(tok.text) not in _GENERIC_LOOSE

    def find_names(self, text: str) -> list[c.SpanCandidate]:
        toks = [t for t in tokenize(text) if t.script != "digit"]
        if not toks or not self._people:
            return []
        strong, weak = [], []
        for t in toks:
            ok = self._qualifies(t, single=False)
            if not ok:
                strong.append(set())
                weak.append(set())
                continue
            k = name_key(t.text)
            other = "latin" if t.script == "deva" else "deva"
            # same script: folded spelling; other script: skeleton (handles schwa deletion)
            strong.append(self._by_loose.get(loose_form(t.text), set())
                          | self._by_key_script.get((k, other), set()))
            weak.append(self._by_key.get(k, set()))
        out: list[c.SpanCandidate] = []
        i, n = 0, len(toks)
        while i < n:
            if not strong[i] and not weak[i]:
                i += 1
                continue
            j = i + 1
            while j < n and (strong[j] or weak[j]) and _GAP.match(text[toks[j - 1].end:toks[j].start]):
                j += 1
            out.extend(self._match_run(text, toks, strong, weak, i, j))
            i = j
        return out

    def _match_run(self, text, toks, strong, weak, i, j) -> list[c.SpanCandidate]:
        out = []
        best = defaultdict(list)  # person -> token indexes matched (any strength)
        for k in range(i, j):
            for person, _pos in strong[k] | weak[k]:
                if not best[person] or best[person][-1] != k:
                    best[person].append(k)
        full = [(p, ks) for p, ks in best.items() if len(ks) >= 2 and ks == list(range(ks[0], ks[-1] + 1))]
        used: set[int] = set()
        if full:
            roles = {self._people[p][0] for p, _ in full}
            p, ks = max(full, key=lambda x: (len(x[1]), -x[0]))
            s, e = toks[ks[0]].start, toks[ks[-1]].end
            if roles == {ROLE_DOCTOR}:
                out.append(c.SpanCandidate(s, e, c.DOCTOR, None, 0.85, c.TIER_PROTECTED, "lexicon_doctor", c.KEEP))
            else:
                cat = _category(roles - {ROLE_DOCTOR})
                out.append(_name_cand(s, e, cat, "lexicon_full", c.TIER_EXPLICIT_IDENTITY, 0.9))
            used.update(ks)
        for k in range(i, j):
            if k in used or not strong[k] or not self._qualifies(toks[k], single=True):
                continue
            roles = {self._people[p][0] for p, _ in strong[k]} - {ROLE_DOCTOR}
            if not roles:
                continue
            out.append(_name_cand(toks[k].start, toks[k].end, _category(roles), "lexicon_token",
                                  c.TIER_WEAK, 0.7))
        return out

    def find_ids(self, text: str) -> list[c.SpanCandidate]:
        out = []
        if self.ids or self.cores:
            for m in _DIGIT_RUN.finditer(text):
                d = re.sub(r"\D", "", m.group(0))
                cat = self.ids.get(d) or (self.ids.get(d[-10:]) if len(d) in (11, 12, 13) else None)
                if cat is None and d in self.cores:
                    cat = c.MRN
                if cat:
                    out.append(c.SpanCandidate(m.start(), m.end(), cat, "patient", 0.95, c.TIER_DIRECT_ID,
                                               "lexicon_id", c.REDACT))
        for s, e in self.templates.find(text):
            out.append(c.SpanCandidate(s, e, c.MRN, "patient", 0.95, c.TIER_DIRECT_ID, "id_template", c.REDACT))
        return out

    def find_places(self, text: str) -> list[c.SpanCandidate]:
        if not self._places:
            return []
        toks = [t for t in tokenize(text) if t.script != "digit"]
        forms = [name_key(t.text) for t in toks]
        out, i = [], 0
        while i < len(toks):
            hit = None
            for size in range(min(self._place_max, len(toks) - i), 0, -1):
                key = tuple(forms[i:i + size])
                if key in self._places and all(
                        _GAP.match(text[toks[k].end:toks[k + 1].start]) or text[toks[k].end:toks[k + 1].start] == " "
                        for k in range(i, i + size - 1)):
                    hit = (size, self._places[key])
                    break
            if hit:
                size, cat = hit
                s, e = toks[i].start, toks[i + size - 1].end
                action = c.GENERALIZE_LOCATION if cat == c.VILLAGE else c.REDACT
                out.append(c.SpanCandidate(s, e, cat, "patient", 0.85, c.TIER_EXPLICIT_IDENTITY,
                                           "lexicon_place", action))
                i += size
            else:
                i += 1
        return out

    def find(self, text: str) -> list[c.SpanCandidate]:
        return self.find_names(text) + self.find_ids(text) + self.find_places(text)


def _script(token: str) -> str:
    return "deva" if any("\u0900" <= ch <= "\u097f" for ch in token) else "latin"


def _category(roles: set[str]) -> str:
    if roles == {ROLE_PATIENT}:
        return c.PATIENT_NAME
    if roles == {ROLE_RELATIVE}:
        return c.RELATIVE_NAME
    return c.PERSON_NAME


def _name_cand(s, e, cat, source, tier, conf):
    action = c.PSEUDONYMIZE if cat == c.PATIENT_NAME else c.REDACT
    role = {c.PATIENT_NAME: "patient", c.RELATIVE_NAME: "relative"}.get(cat)
    return c.SpanCandidate(s, e, cat, role, conf, tier, source, action)
