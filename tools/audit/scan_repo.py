"""Pre-commit gate: look for practice-data identities and secrets in files about to be committed.

    python tools/audit/scan_repo.py --truth ../Secret-Wards-ToolKit/dev/truth/truth.json [--staged] [--where]

Reads the organiser's practice answer key LOCALLY and checks our files against it.
Two classes of finding:

  IDENTITY  full patient / relative / canary names, ID digit keys (MRN, phone, Aadhaar, ABHA,
            insurance, PAN), e-mail, DOB, village, PIN. These fail the gate (exit 1).
  GENERIC   a single common name token ("Asha") or a generic address phrase ("Ward 8").
            Reported as a count, never fails: any Indian-name gazetteer shares these.

It prints file names, categories and counts, never a matched value. With --where it adds
line numbers (still no values). Without --staged it scans every file git would track.
src/detection/gazetteer_data.py is exempt from the name-token check because it is a general
gazetteer; the overlap with the practice data is printed instead.

Why: the rules forbid hardcoding practice identities, the kit's static audit flags them, and
committing organiser truth / attacker files / our outputs would publish them.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SKIP_DIRS = {".git", ".venv", "out", "__pycache__", ".pytest_cache", "node_modules"}
FORBIDDEN_NAMES = ("truth.json", "registry.csv", "known_facts.jsonl", "raw_attack.json", "dataset_manifest.json")
GAZETTEER = "src/detection/gazetteer_data.py"
GENERIC_TYPES = {"HOUSE", "LOCALITY", "LANDMARK"}          # "H.No. 12", "Ward 8", "near Water Tank"
DIGIT_TYPES = {"MRN", "PHONE", "AADHAAR", "ABHA_NUMBER", "INSURANCE_ID"}
SECRET_PATTERNS = [
    (re.compile(r"RAKSHA_SECRET\s*=\s*['\"][^'\"\s]{6,}['\"]"), "hardcoded RAKSHA_SECRET value"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)\b(?:api[_-]?key|passwd|password|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]"), "credential-like string"),
]


def norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", s).casefold().split())


def load_surfaces(truth_path: Path) -> dict[str, tuple[str, set[str]]]:
    """category -> (class, values). class is IDENTITY or GENERIC."""
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    out: dict[str, tuple[str, set[str]]] = {}

    def add(cat, cls, val):
        out.setdefault(cat, (cls, set()))[1].add(val)

    for f in truth["files"].values():
        for u in f["units"].values():
            for e in u["entities"]:
                kind = e["type"]
                if e["match"] == "name":
                    for t in e.get("tokens") or []:
                        if len(t) >= 5:
                            add(f"{kind}:name-token", "GENERIC", norm(t))
                    if len(e["surface"].split()) >= 2 and len(e["surface"]) >= 8 and e.get("full"):
                        add(f"{kind}:full-name", "IDENTITY", norm(e["surface"]))
                elif e.get("key") and len(e["key"]) >= 5:
                    cls = "GENERIC" if kind in GENERIC_TYPES else "IDENTITY"
                    add(f"{kind}:key", cls, e["key"] if kind in DIGIT_TYPES else norm(e["key"]))
    return out


def candidate_files(staged: bool) -> list[Path]:
    cmd = (["git", "diff", "--cached", "--name-only"] if staged
           else ["git", "ls-files", "--cached", "--others", "--exclude-standard"])
    try:
        names = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
        return [ROOT / n for n in names if n and (ROOT / n).is_file()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)]


def word_rx(v: str) -> re.Pattern:
    return re.compile(rf"(?<![^\W\d_]){re.escape(v)}(?![^\W\d_])")


def gazetteer_overlap(surfaces) -> str:
    try:
        from src.detection import gazetteer_data as g
    except Exception:  # noqa: BLE001
        return "gazetteer overlap: unavailable"
    names = {norm(x) for x in g.GIVEN_NAMES + g.SURNAMES}
    practice = set()
    for cat, (_cls, vals) in surfaces.items():
        if cat.endswith("name-token"):
            practice |= vals
    both = names & practice
    return (f"gazetteer: {len(names)} general names, {len(both)} also appear in the practice data "
            f"({100 * len(both) / max(len(names), 1):.0f}% of the list); "
            f"{100 * len(both) / max(len(practice), 1):.0f}% of practice name tokens are in the list")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--where", action="store_true", help="also print line numbers (never values)")
    a = ap.parse_args()
    surfaces = load_surfaces(Path(a.truth))
    findings: dict[str, Counter] = defaultdict(Counter)
    lines: dict[tuple[str, str], list[int]] = defaultdict(list)
    for p in candidate_files(a.staged):
        rel = p.relative_to(ROOT).as_posix()
        if p.name in FORBIDDEN_NAMES or rel.startswith(("out/", "my_output")):
            findings[rel]["BLOCK:forbidden-file"] += 1
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if len(raw) > 2_000_000 or b"\x00" in raw[:4096]:
            findings[rel]["BLOCK:binary-or-large"] += 1
            continue
        text = raw.decode("utf-8", errors="replace")
        for rx, label in SECRET_PATTERNS:
            if rx.search(text):
                findings[rel][f"BLOCK:{label}"] += 1
        text_lines = text.splitlines()
        norm_lines = [norm(x) for x in text_lines]
        hay = " ".join(norm_lines)
        # digit identifiers are matched inside a run of digits joined by space / dash / dot / slash,
        # like the official scorer, not across unrelated numbers on the same line
        digit_lines = [[re.sub(r"\D", "", m.group(0)) for m in re.finditer(r"\d(?:[ \-./]?\d)*", x)]
                       for x in text_lines]
        digits = " ".join(r for ln in digit_lines for r in ln)
        for cat, (cls, vals) in surfaces.items():
            if rel == GAZETTEER and cat.endswith("name-token"):
                continue
            kind = cat.split(":")[0]
            n = 0
            for v in vals:
                if cat.endswith(("name-token", "full-name")):
                    hit = word_rx(v).search(hay) is not None
                    where = (lambda v=v: [i + 1 for i, x in enumerate(norm_lines) if word_rx(v).search(x)])
                elif kind in DIGIT_TYPES:
                    hit = v in digits
                    where = (lambda v=v: [i + 1 for i, runs in enumerate(digit_lines) if any(v in r for r in runs)])
                else:
                    hit = v in hay
                    where = (lambda v=v: [i + 1 for i, x in enumerate(norm_lines) if v in x])
                if hit:
                    n += 1
                    if a.where:
                        lines[(rel, f"{cls}:{cat}")].extend(where())
            if n:
                findings[rel][f"{cls}:{cat}"] += n
    n_identity = n_block = n_generic = 0
    for rel in sorted(findings):
        parts = []
        for k, v in sorted(findings[rel].items()):
            parts.append(f"{k} x{v}")
            if k.startswith("IDENTITY"):
                n_identity += v
            elif k.startswith("BLOCK"):
                n_block += v
            else:
                n_generic += v
        print(f"{rel}: " + ", ".join(parts))
        if a.where:
            for (r, k), ls in sorted(lines.items()):
                if r == rel and k.startswith(("IDENTITY", "BLOCK")):
                    print(f"      {k} at lines {sorted(set(ls))[:12]}")
    print(gazetteer_overlap(surfaces))
    print(f"TOTAL identity={n_identity} blocked={n_block} generic={n_generic}")
    return 1 if (n_identity or n_block) else 0


if __name__ == "__main__":
    sys.exit(main())
