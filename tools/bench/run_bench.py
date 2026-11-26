"""DEV-ONLY detection bench. Not the submission pipeline (Omkar owns ingestion/serialization).

It reads an input tree with minimal adapters, runs Danish's DetectionEngine, applies spans
with typed placeholders (no pseudonyms, no date shifting, no linking) and writes the
contract layout so the kit's check_dev.py can measure detection and clinical preservation:

    python tools/bench/run_bench.py --input ../Secret-Wards-ToolKit/dev/input --output out/bench
    python ../Secret-Wards-ToolKit/check_dev.py --output out/bench --show 20

Only counts are printed. Never point it at real data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src import contracts as c  # noqa: E402
from src.detection.engine import DetectionEngine, apply_placeholders  # noqa: E402


# ------------------------------------------------------------------ minimal adapters
def decode(raw: bytes) -> tuple[str | None, str | None]:
    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            return raw[3:].decode("utf-8"), "utf-8-sig"
        except UnicodeDecodeError:
            return None, None
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            return None, None
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    if b"\xff" in raw or b"\xfe" in raw:
        return None, None
    try:
        text = raw.decode("cp1252")
    except UnicodeDecodeError:
        return None, None
    if "Ã" in text or "Â" in text:
        return None, None
    return text, "cp1252"


def esc(k: str) -> str:
    return k.replace("~", "~0").replace("/", "~1")


def leaves(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, f"{path}/{esc(str(k))}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaves(v, f"{path}/{i}")
    else:
        yield path, obj


def last_key(path: str) -> str:
    parts = [p for p in path.split("/") if p and not p.isdigit()]
    return parts[-1].replace("~1", "/").replace("~0", "~") if parts else ""


def vtype(v) -> str:
    return {str: "str", int: "int", float: "float", bool: "bool", type(None): "null"}.get(type(v), "str")


def record_roots(data) -> list[str]:
    if not isinstance(data, dict) or data.get("resourceType") == "Bundle":
        return []
    return [f"/{esc(k)}" for k, v in data.items()
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)]


def build(rel, raw, text, fmt, data=None, rows=None, delim=None):
    sha = hashlib.sha256(raw).hexdigest()
    f = c.FileEnvelope(sha, rel, fmt, None, len(raw))
    if fmt in ("csv", "tsv"):
        header, body = rows[0], rows[1:]
        for i, row in enumerate(body):
            fields = [c.FieldNode(f"col:{j}", v, "str", c.CONTENT, header[j] if j < len(header) else "")
                      for j, v in enumerate(row)]
            f.records.append(c.RecordEnvelope(f"{sha}:row:{i}", sha, f"row:{i}", fmt, fields))
    elif fmt in ("json", "fhir"):
        roots = record_roots(data) if fmt == "json" else []
        groups: dict[str, list] = {}
        for p, v in leaves(data):
            loc = "doc" if not roots else "@file"
            for r in roots:
                if p.startswith(r + "/"):
                    loc = "/".join(p.split("/")[:len(r.split("/")) + 1])
                    break
            groups.setdefault(loc, []).append(c.FieldNode(p, v, vtype(v), c.CONTENT, last_key(p)))
        for loc, fields in groups.items():
            f.records.append(c.RecordEnvelope(f"{sha}:{loc}", sha, loc, fmt, fields))
    else:
        f.records.append(c.RecordEnvelope(f"{sha}:doc", sha, "doc", "text", [], text))
    return f


def apply_to_value(value, spans):
    if not spans:
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if all(s.action in (c.KEEP, c.GENERALIZE_AGE, c.SHIFT_DATE) and s.category != c.DOB for s in spans):
            return value
        return 0
    return apply_placeholders(str(value), spans)


def rename_keys(obj, engine):
    if isinstance(obj, dict):
        mapping = engine.sanitize_keys(list(obj.keys()))
        return {mapping.get(k, k): rename_keys(v, engine) for k, v in obj.items()}
    if isinstance(obj, list):
        return [rename_keys(v, engine) for v in obj]
    return obj


def set_pointer(obj, path, value):
    parts = [p.replace("~1", "/").replace("~0", "~") for p in path.split("/")[1:]]
    cur = obj
    for p in parts[:-1]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    t0 = time.monotonic()
    inp, out = Path(a.input), Path(a.output)
    san = out / "sanitized"
    san.mkdir(parents=True, exist_ok=True)
    sys.setrecursionlimit(3000)
    parsed, report_files = [], []
    for path in sorted(p for p in inp.rglob("*") if p.is_file()):
        rel = path.relative_to(inp).as_posix()
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        text, _enc = decode(raw) if raw.strip() else (None, None)
        reason = None
        try:
            if text is None:
                raise ValueError("undecodable_or_empty")
            s = text.lstrip()
            data, is_json = None, False
            if s[:1] in "{[":
                try:
                    data, is_json = json.loads(text), True
                except ValueError:
                    if path.suffix.lower() == ".json" or path.suffix.lower() in (".csv", ".tsv"):
                        raise
            if is_json:
                fmt = "fhir" if isinstance(data, dict) and data.get("resourceType") == "Bundle" else "json"
                parsed.append((rel, raw, build(rel, raw, text, fmt, data=data), data, None))
            elif path.suffix.lower() in (".csv", ".tsv"):
                delim = "\t" if path.suffix.lower() == ".tsv" or text.split("\n", 1)[0].count("\t") > \
                    text.split("\n", 1)[0].count(",") else ","
                rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))
                if not rows:
                    raise ValueError("empty_table")
                parsed.append((rel, raw, build(rel, raw, text, "csv", rows=rows), rows, delim))
            elif path.suffix.lower() == ".txt":
                parsed.append((rel, raw, build(rel, raw, text, "text"), text, None))
            else:
                raise ValueError("unsupported_format")
        except (ValueError, RecursionError, csv.Error) as exc:
            reason = exc.args[0] if isinstance(exc, ValueError) and str(exc).isidentifier() else type(exc).__name__
            report_files.append({"input_sha256": sha, "output": None, "status": "quarantined", "reason": reason})

    engine = DetectionEngine()
    engine.prepare([p[2] for p in parsed])
    records_out, n_ids = [], 0
    for rel, raw, f, payload, delim in parsed:
        out_rel = engine.sanitize_path(rel)
        dest = san / out_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dets = {r.locator: engine.detect_record(r, f) for r in f.records}
        n_ids += sum(1 for d in dets.values() for s in d.spans if s.action != c.KEEP)
        if f.detected_format == "csv":
            rows = payload
            header = engine.sanitize_header(rows[0])
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=delim, lineterminator="\n")
            w.writerow(header)
            for i, row in enumerate(rows[1:]):
                det = dets[f"row:{i}"]
                new = [apply_to_value(v, [s for s in det.spans if s.field_path == f"col:{j}"])
                       for j, v in enumerate(row)]
                w.writerow(new)
                records_out.append({"file": f"sanitized/{out_rel}", "loc": f"row:{i}", "patient": None})
            dest.write_text(buf.getvalue(), encoding="utf-8", newline="")
        elif f.detected_format in ("json", "fhir"):
            data = payload
            for r in f.records:
                det = dets[r.locator]
                for n in r.fields:
                    spans = [s for s in det.spans if s.field_path == n.path]
                    if spans and n.path:
                        set_pointer(data, n.path, apply_to_value(n.value, spans))
                    elif spans and not n.path:
                        data = apply_to_value(n.value, spans)
                if r.locator != "@file":
                    records_out.append({"file": f"sanitized/{out_rel}", "loc": r.locator, "patient": None})
            data = rename_keys(data, engine)
            dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            det = dets["doc"]
            dest.write_text(apply_placeholders(payload, [s for s in det.spans if s.field_path == ""]),
                            encoding="utf-8", newline="")
            records_out.append({"file": f"sanitized/{out_rel}", "loc": "doc", "patient": None})
        report_files.append({"input_sha256": hashlib.sha256(raw).hexdigest(),
                             "output": f"sanitized/{out_rel}", "status": "sanitized"})

    with open(out / "records.jsonl", "w", encoding="utf-8") as fh:
        for r in records_out:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    n_san = sum(e["status"] == "sanitized" for e in report_files)
    report = {"schema": "raksha-report/1", "files": report_files,
              "counts": {"files_total": len(report_files), "files_sanitized": n_san,
                         "files_quarantined": len(report_files) - n_san, "records_processed": len(records_out),
                         "identifiers_detected": n_ids, "records_linked": 0, "records_generalized": 0,
                         "records_suppressed": 0, "records_quarantined": 0},
              "timing": {"seconds": round(time.monotonic() - t0, 2)}, "resources": {"peak_rss_mb": 0.0}}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"files {len(report_files)} sanitized {n_san} records {len(records_out)} "
          f"edits {n_ids} seconds {report['timing']['seconds']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
