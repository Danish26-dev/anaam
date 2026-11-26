"""DEV-ONLY: measure the release verifier.

  A) sanitized output  -> should be RELEASED (false alarms = over-blocking)
  B) raw input files   -> should be flagged   (misses = verifier blind spots)

Prints only counts and safe reason codes.

    python tools/bench/verify_bench.py --input ../Secret-Wards-ToolKit/dev/input --output out/bench
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "bench"))

import run_bench as rb  # noqa: E402
from src import contracts as c  # noqa: E402
from src.detection.engine import DetectionEngine  # noqa: E402
from src.verify.release import FileCandidate, ReleaseGate  # noqa: E402


def parse_inputs(inp: Path):
    files, texts = [], {}
    for path in sorted(p for p in inp.rglob("*") if p.is_file()):
        rel = path.relative_to(inp).as_posix()
        raw = path.read_bytes()
        text, _ = rb.decode(raw) if raw.strip() else (None, None)
        if text is None:
            continue
        s = text.lstrip()
        try:
            if s[:1] in "{[":
                import json as _j
                data = _j.loads(text)
                fmt = "fhir" if isinstance(data, dict) and data.get("resourceType") == "Bundle" else "json"
                env = rb.build(rel, raw, text, fmt, data=data)
            elif path.suffix.lower() in (".csv", ".tsv"):
                import csv, io
                delim = "\t" if path.suffix.lower() == ".tsv" else ","
                rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))
                env = rb.build(rel, raw, text, "csv", rows=rows)
            elif path.suffix.lower() == ".txt":
                env = rb.build(rel, raw, text, "text")
            else:
                continue
        except (ValueError, RecursionError):
            continue
        files.append(env)
        texts[rel] = (text, path.suffix.lower())
    return files, texts


def summarize(name, results):
    ok = sum(1 for r in results if r.passed)
    codes = Counter(x for r in results if not r.passed for x in r.safe_reason_codes)
    print(f"{name}: released {ok}/{len(results)}  flagged {len(results) - ok}")
    for k, n in codes.most_common(12):
        print(f"    {k:<28} {n}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    inp, out = Path(a.input), Path(a.output)
    files, texts = parse_inputs(inp)
    engine = DetectionEngine()
    engine.prepare(files)
    gate = ReleaseGate(engine)
    gate.prepare()

    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    out_results, flagged_out = [], []
    for e in report["files"]:
        if e["status"] != "sanitized":
            continue
        p = out / e["output"]
        text = p.read_text(encoding="utf-8")
        fmt = {".json": "json", ".csv": "csv", ".tsv": "tsv"}.get(p.suffix.lower(), "text")
        r = gate.verify_file(FileCandidate(text=text, fmt=fmt, delimiter="\t" if fmt == "tsv" else ","))
        out_results.append(r)
        if not r.passed:
            flagged_out.append((e["output"], r.safe_reason_codes))
    summarize("A) sanitized output", out_results)
    for f, codes in flagged_out[:10]:
        print("    flagged:", f, codes)

    pii_files = {rel for rel in texts if not rel.startswith("clean/")}
    raw_results = {rel: gate.verify_file(FileCandidate(text=t)) for rel, (t, _ext) in texts.items()}
    summarize("B) raw input, files with PII (want ~all flagged)", [raw_results[r] for r in pii_files])
    missed = sorted(r for r in pii_files if raw_results[r].passed)
    print("    missed:", missed[:10], "total", len(missed))
    clean = [raw_results[r] for r in texts if r.startswith("clean/")]
    summarize("C) clean documents, raw (want all released)", clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
