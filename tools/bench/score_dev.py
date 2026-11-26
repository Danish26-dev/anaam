"""DEV-ONLY stricter leak scorer, modelled on docs/SCORING.md of the toolkit.

Differences from the kit's check_dev.py (which only checks whole surfaces per file):
  * record-level: each truth unit is located in the output (CSV row, JSON pointer, doc,
    @header, @filename, @file); a missing JSON record falls back to the whole file;
  * name entities are scored per identifying token, digit identifiers on their digit key
    across separators, PINs as exact 6-digit runs, DOBs on any date format;
  * both sides normalized (NFKC, homoglyphs, zero-width, Indic digits, diacritics, case)
    and hidden payloads (base64, hex, \\u escapes, HTML entities, %-encoding) decoded;
  * tokens inside the unit's preserve probes are allowed ("Dr. Ramesh" keeps "Ramesh").
Recall is reported per type, per script and per channel; contextual precision per trap.
This is an estimate for development, not the official score. It prints practice-data
surfaces with --show, which is acceptable only because the practice data is synthetic.

    python tools/bench/score_dev.py --output out/bench --dev ../Secret-Wards-ToolKit/dev
"""
from __future__ import annotations

import argparse
import base64
import binascii
import csv
import html
import io
import json
import re
import sys
import unicodedata
from urllib.parse import unquote   # pure string helper; no network
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.detection.dates import find_dates  # noqa: E402
from src.detection.normalization import TextView  # noqa: E402

_WORD = re.compile(r"[a-z0-9\u0900-\u097f]+")
TYPE_WEIGHTS = {"AADHAAR": 1.0, "ABHA_NUMBER": 1.0, "ABHA_ADDRESS": 1.0, "PHONE": 1.0, "EMAIL": 1.0, "MRN": 1.0,
                "PAN": 1.0, "INSURANCE_ID": 0.8, "PATIENT_NAME": 1.0, "RELATIVE_NAME": 0.8, "DOB": 0.7,
                "HOUSE": 0.6, "LOCALITY": 0.6, "LANDMARK": 0.5, "VILLAGE": 0.5, "PIN": 0.5, "AADHAAR_MASKED": 0.5}
_B64 = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


def norm(s: str) -> str:
    t = TextView.of(unicodedata.normalize("NFKC", s)).text
    return " ".join(t.casefold().split())


def decode_hidden(text: str) -> str:
    extra = []
    for m in _B64.finditer(text):
        tok = m.group(0)
        try:
            extra.append(base64.b64decode(tok + "=" * (-len(tok) % 4)).decode("utf-8", errors="ignore"))
        except (binascii.Error, ValueError):
            pass
    for m in re.finditer(r"(?:\\u[0-9a-fA-F]{4})+", text):
        try:
            extra.append(m.group(0).encode().decode("unicode_escape"))
        except UnicodeDecodeError:
            pass
    for m in re.finditer(r"(?<![0-9a-fA-F])(?:[0-9a-fA-F]{2}){8,}(?![0-9a-fA-F])", text):
        try:
            extra.append(bytes.fromhex(m.group(0)).decode("utf-8", errors="ignore"))
        except ValueError:
            pass
    if "&" in text:
        extra.append(html.unescape(text))
    if "%" in text:
        extra.append(unquote(text))
    return text + ("\n" + "\n".join(extra) if extra else "")


def read_text(p: Path) -> str:
    raw = p.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def pointer_get(obj, pointer):
    for part in [p.replace("~1", "/").replace("~0", "~") for p in pointer.split("/")[1:]]:
        if isinstance(obj, list):
            obj = obj[int(part)]
        else:
            obj = obj[part]
    return obj


def unit_texts(path: Path, fmt: str, delimiter: str | None, locs) -> dict[str, str]:
    """loc -> raw text of that unit (whole file as fallback)."""
    try:
        text = read_text(path)
    except OSError:
        return {}
    out = {}
    rows = data = None
    if fmt in ("csv", "tsv"):
        try:
            rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter or ","))
        except csv.Error:
            rows = None
    elif fmt in ("json", "fhir"):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
    for loc in locs:
        if loc.startswith("row:") and rows is not None:
            i = int(loc[4:]) + 1
            out[loc] = (delimiter or ",").join(rows[i]) if i < len(rows) else ""
        elif loc == "@header" and rows is not None:
            out[loc] = (delimiter or ",").join(rows[0]) if rows else ""
        elif loc.startswith("/") and data is not None:
            try:
                out[loc] = json.dumps(pointer_get(data, loc), ensure_ascii=False)
            except (KeyError, IndexError, ValueError, TypeError):
                out[loc] = text
        else:
            out[loc] = text
    return out


def count_token(tok: str, hay: str) -> int:
    t = re.escape(norm(tok))
    if any("\u0900" <= ch <= "\u097f" for ch in tok):
        return len(re.findall(rf"(?<![\u0900-\u097f]){t}(?![\u0900-\u097f])", hay))
    return len(re.findall(rf"(?<![a-z0-9]){t}(?![a-z0-9])", hay))


def digit_runs(hay: str) -> list[str]:
    return [re.sub(r"\D", "", m.group(0)) for m in re.finditer(r"\d(?:[ \-./]?\d)*", hay)]


def count_key(e: dict, hay: str, key: str) -> int:
    match = e["match"]
    if match == "name":
        return count_token(key, hay)
    if match == "digits":
        return sum(r.count(key) for r in digit_runs(hay))
    if match == "digits_exact":
        return sum(1 for r in re.findall(r"(?<!\d)\d{6}(?!\d)", hay) if r == key)
    if match == "dob":
        n = 0
        for order in ("dmy", "mdy"):
            n += sum(1 for _, _, d, _ in find_dates(hay, order) if d and d.isoformat() == key)
        return min(n, 1) if n else 0
    return hay.count(norm(key))


def entity_keys(e: dict) -> list[str]:
    if e["match"] == "name":
        return list(e.get("tokens") or [])
    return [e["key"]] if e.get("key") else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--dev", required=True, help="toolkit dev/ folder (input + truth)")
    ap.add_argument("--truth", default=None)
    ap.add_argument("--show", type=int, default=0)
    a = ap.parse_args()
    dev, out = Path(a.dev), Path(a.output)
    truth = json.loads(Path(a.truth or dev / "truth" / "truth.json").read_text(encoding="utf-8"))
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    renamed = {e["input_sha256"]: e.get("output") for e in report["files"]}

    leak_sum, n_ent = defaultdict(float), Counter()
    by_script, n_script = defaultdict(float), Counter()
    by_channel, n_channel = defaultdict(float), Counter()
    trap_ok, trap_n = Counter(), Counter()
    probe_ok = probe_n = 0
    tok_kept = tok_total = 0
    lost_tokens = Counter()
    examples = []
    for rel, f in truth["files"].items():
        dest = renamed.get(f["sha256"])
        out_path = out / dest if dest else None
        exported = out_path is not None and out_path.is_file()
        locs = list(f["units"].keys())
        src = unit_texts(dev / "input" / rel, f["format"], f.get("delimiter"), locs)
        dst = unit_texts(out_path, f["format"], f.get("delimiter"), locs) if exported else {}
        out_name = norm(dest or "")
        for loc, u in f["units"].items():
            in_hay = norm(decode_hidden(src.get(loc, "") if loc != "@filename" else rel))
            out_hay = norm(decode_hidden(dst.get(loc, ""))) if loc != "@filename" else out_name
            if not exported and loc != "@filename":
                out_hay = ""
            preserve = [norm(p["text"]) for p in u.get("preserve") or []]
            if exported and not loc.startswith("@"):
                skip = set()
                for e in u["entities"]:
                    skip.update(_WORD.findall(norm(e["surface"])))
                for x in u.get("exclude") or []:
                    skip.update(_WORD.findall(norm(x)))
                tin = Counter(w for w in _WORD.findall(norm(src.get(loc, ""))) if w not in skip)
                tout = Counter(_WORD.findall(norm(dst.get(loc, ""))))
                for w, n in tin.items():
                    k = min(n, tout.get(w, 0))
                    tok_kept += k
                    tok_total += n
                    if k < n:
                        lost_tokens[w] += n - k
            for p in u.get("preserve") or []:
                if exported:
                    ok = norm(p["text"]) in out_hay
                    probe_ok += ok
                    probe_n += 1
                    if p.get("trap"):
                        trap_n[p["trap"]] += 1
                        trap_ok[p["trap"]] += ok
            for e in u["entities"]:
                if e["type"] == "CANARY":
                    continue
                keys = entity_keys(e)
                leaks = []
                for k in keys:
                    occ_in = count_key(e, in_hay, k)
                    allowed = sum(in_hay.count(p) * count_key(e, p, k) for p in set(preserve) if p)
                    pii_occ = max(occ_in - allowed, 1)
                    occ_out = count_key(e, out_hay, k)
                    leaks.append(min(max(occ_out - allowed, 0), pii_occ) / pii_occ)
                leak = sum(leaks) / len(leaks) if leaks else 0.0
                leak_sum[e["type"]] += leak
                n_ent[e["type"]] += 1
                by_script[e["script"]] += leak
                n_script[e["script"]] += 1
                by_channel[e["channel"]] += leak
                n_channel[e["channel"]] += 1
                if leak > 0 and len(examples) < a.show:
                    examples.append((e["type"], e["script"], e["channel"], rel, loc, e["surface"], round(leak, 2)))
    everything = []
    for p in sorted(out.rglob("*")):
        if p.is_file():
            everything.append(p.relative_to(out).as_posix())
            everything.append(read_text(p))
    hay_all = norm(decode_hidden("\n".join(everything)))
    canaries = {tuple(e["tokens"]) for f in truth["files"].values() for u in f["units"].values()
                for e in u["entities"] if e["type"] == "CANARY"}
    canary_hits = sum(1 for toks in canaries if all(count_token(t, hay_all) for t in toks))

    rec_type = {t: 1 - leak_sum[t] / n_ent[t] for t in n_ent}
    w = sum(TYPE_WEIGHTS.get(t, 0.5) for t in rec_type)
    macro_type = sum(TYPE_WEIGHTS.get(t, 0.5) * r for t, r in rec_type.items()) / w
    rec_script = {s: 1 - by_script[s] / n_script[s] for s in n_script}
    macro_script = sum(rec_script.values()) / len(rec_script)
    recall = 0.5 * macro_type + 0.5 * macro_script
    precision = sum(trap_ok[t] / trap_n[t] for t in trap_n) / len(trap_n) if trap_n else 1.0
    f2 = 5 * precision * recall / (4 * precision + recall) if precision + recall else 0.0

    print("=" * 66)
    print(" Anaam dev scorer (token-level, record-level; estimate, not official)")
    print("=" * 66)
    print(f"recall by type (weighted macro {macro_type:.4f}):")
    for t in sorted(rec_type, key=lambda x: rec_type[x]):
        print(f"   {t:<16} recall {rec_type[t]:.4f}   ({n_ent[t]} mentions)")
    print("recall by script: " + ", ".join(f"{s} {r:.4f}" for s, r in sorted(rec_script.items())))
    print("recall by channel: " + ", ".join(f"{ch} {1 - by_channel[ch] / n_channel[ch]:.4f}"
                                           for ch in sorted(n_channel)))
    print(f"contextual precision by trap (mean {precision:.4f}):")
    for t in sorted(trap_n):
        print(f"   {t:<20} {trap_ok[t]}/{trap_n[t]}")
    print(f"clinical probes kept (record-level): {probe_ok}/{probe_n} = {probe_ok / max(probe_n, 1):.4f}")
    print(f"non-PII token retention: {tok_kept}/{tok_total} = {tok_kept / max(tok_total, 1):.4f}")
    print("   most-lost non-PII tokens: " + ", ".join(f"{w}x{n}" for w, n in lost_tokens.most_common(25)))
    print(f"canaries found in output folder: {canary_hits}/{len(canaries)}")
    print(f"estimated detection F2: {f2:.4f}  (recall {recall:.4f}, precision {precision:.4f})")
    for ex in examples:
        print("   LEAK", " | ".join(str(x) for x in ex))
    return 0


if __name__ == "__main__":
    sys.exit(main())
