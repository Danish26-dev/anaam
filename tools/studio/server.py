"""Anaam Release Studio: a local-only adapter between the frontend and the real CLI.

    python tools/studio/server.py [--port 8765] [--kit ../Secret-Wards-ToolKit]

* Binds to 127.0.0.1 only and rejects any Host header that is not localhost (DNS-rebinding guard).
  No CORS headers: only the page this server serves can call it.
* A release runs the unchanged CLI (`python main.py --input ... --output ...`) as a subprocess.
  The engine is not duplicated here.
* Uploaded files are written to a per-release folder under out/studio/releases/, used for the
  run and the before/after checks, then deleted, also on failure. Only output-derived data is
  served: report.json, records.jsonl, sanitized files, and counts computed from them.
* RAKSHA_SECRET comes from the environment; if unset, a random per-session secret is used.
  It is never logged, returned or written by this server.
* Request logs show method, route and status only, never bodies or file names.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import uuid
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from detection.engine import DetectionEngine  # noqa: E402
from verify import structure as st  # noqa: E402
from verify.clinical import protected_multiset  # noqa: E402
from verify.leaks import LeakVerifier  # noqa: E402
from verify.release import ReleaseGate  # noqa: E402

DIST = ROOT / "frontend" / "dist"
RELEASES = ROOT / "out" / "studio" / "releases"
EVIDENCE = ROOT / "out" / "studio" / "evidence.json"
MAX_FILES = 400
MAX_BYTES = 60 * 1024 * 1024
SUPPORTED = {".csv", ".tsv", ".json", ".txt"}
_SAFE_SEGMENT = re.compile(r"^[^\x00-\x1f\\:*?\"<>|]+$")
_ID = re.compile(r"^[0-9a-f]{12}$")
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml",
        ".png": "image/png", ".woff2": "font/woff2", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8",
        ".csv": "text/csv; charset=utf-8", ".tsv": "text/tab-separated-values; charset=utf-8",
        ".jsonl": "application/x-ndjson; charset=utf-8"}

STATE: dict = {"secret": None, "secret_source": None, "kit": None, "lock": threading.Lock(), "releases": {}}


# ----------------------------------------------------------------------------- helpers
def safe_rel(path: str) -> PurePosixPath | None:
    p = PurePosixPath(path.replace("\\", "/"))
    if p.is_absolute() or not p.parts or any(x in ("", ".", "..") or not _SAFE_SEGMENT.match(x) for x in p.parts):
        return None
    return p


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def summary_path(rid: str) -> Path:
    return RELEASES / rid / "summary.json"


def save_summary(rid: str, summary: dict) -> None:
    with STATE["lock"]:
        STATE["releases"][rid] = summary
        summary_path(rid).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def load_releases() -> None:
    if not RELEASES.is_dir():
        return
    for d in RELEASES.iterdir():
        sp = d / "summary.json"
        if d.is_dir() and _ID.match(d.name) and sp.is_file():
            s = json.loads(sp.read_text(encoding="utf-8"))
            if s.get("status") in ("queued", "running", "verifying"):
                s["status"], s["error"] = "failed", "interrupted"   # the server stopped mid-run
                (d / "input").exists() and shutil.rmtree(d / "input", ignore_errors=True)
            STATE["releases"][d.name] = s


# ----------------------------------------------------------------------------- release run
def assurance(inp: Path, out: Path, pipeline_ok: bool) -> dict:
    """Checks computed on the released files (and the inputs, before they are deleted)."""
    res: dict = {}
    report_p, records_p = out / "report.json", out / "records.jsonl"
    if not pipeline_ok or not report_p.exists():
        return {"status": "BLOCKED", "reason": "pipeline_failed"}
    report = json.loads(report_p.read_text(encoding="utf-8"))
    records = [json.loads(x) for x in records_p.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if records_p.exists() else []
    by_sha = {hashlib.sha256(p.read_bytes()).hexdigest(): p for p in inp.rglob("*") if p.is_file()}

    # contract: the kit's own validator when the kit is available
    kit = STATE["kit"]
    if kit and (kit / "validate_output.py").is_file():
        proc = subprocess.run([sys.executable, str(kit / "validate_output.py"), "--input", str(inp), "--output", str(out)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        text = proc.stdout + proc.stderr
        res["contract"] = {"evaluated": True, "ok": "CONTRACT OK" in text,
                           "errors": sum(1 for ln in text.splitlines() if ln.strip().startswith("ERROR"))}
    else:
        res["contract"] = {"evaluated": False}

    pseudonyms = {r["patient"] for r in records if r.get("patient")}
    leaks = LeakVerifier(DetectionEngine(), pseudonyms)
    leaks.refresh()
    residual, structural, files = Counter(), Counter(), []
    clin_before, clin_kept = Counter(), Counter()
    for f in report.get("files", []):
        entry = {"output": f.get("output"), "status": f["status"], "reason": f.get("reason"),
                 "input_sha256": f["input_sha256"], "records": 0, "residual": 0, "structure": [],
                 "clinical_before": 0, "clinical_kept": 0}
        if f["status"] == "sanitized" and f.get("output"):
            entry["records"] = sum(1 for r in records if r["file"] == f["output"])
            text = (out / f["output"]).read_text(encoding="utf-8", errors="replace")
            fmt = PurePosixPath(f["output"]).suffix.lower().lstrip(".")
            findings = leaks.scan_residual(text, structured=fmt in ("csv", "tsv", "json"))
            entry["residual"] = len(findings)
            residual.update(x.category for x in findings)
            codes = st.check_utf8(text.encode("utf-8", errors="surrogatepass"))
            if fmt == "json":
                errs, parsed = st.check_json(text)
                codes += errs
                if parsed is not None and isinstance(parsed, dict) and parsed.get("resourceType") == "Bundle":
                    codes += st.check_fhir_references(parsed)
            entry["structure"] = sorted(set(codes))
            structural.update(entry["structure"])
            src = by_sha.get(f["input_sha256"])
            if src is not None:
                b, a = protected_multiset(src.read_text(encoding="utf-8", errors="replace")), protected_multiset(text)
                for key, n in b.items():
                    clin_before[key[0]] += n
                    clin_kept[key[0]] += min(n, a.get(key, 0))
                    entry["clinical_before"] += n
                    entry["clinical_kept"] += min(n, a.get(key, 0))
        files.append(entry)

    clusters: dict[str, list[dict]] = {}
    for r in records:
        if r.get("patient"):
            clusters.setdefault(r["patient"], []).append({"file": r["file"], "loc": r["loc"]})
    res["files"] = files
    res["residual"] = {"total": sum(residual.values()), "by_category": dict(residual)}
    res["structure"] = {"total": sum(structural.values()), "codes": dict(structural)}
    res["clinical"] = {"before": sum(clin_before.values()), "kept": sum(clin_kept.values()),
                       "by_category": [{"category": k, "before": clin_before[k], "kept": clin_kept[k]}
                                       for k in sorted(clin_before)]}
    res["identity"] = {"records": len(records), "linked_records": sum(len(v) for v in clusters.values()),
                       "patients": len(clusters),
                       "clusters": [{"pseudonym": p, "records": v} for p, v in
                                    sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0]))][:200]}
    res["counts"], res["timing"], res["resources"] = report.get("counts", {}), report.get("timing", {}), report.get("resources", {})

    # release-wide: every input accounted for, report/manifest consistent with the exported tree,
    # the secret nowhere in report or manifest, no known values in them (verify.release)
    sanitized = out / "sanitized"
    exported = {p.relative_to(sanitized).as_posix() for p in sanitized.rglob("*") if p.is_file()} \
        if sanitized.is_dir() else set()
    gate = ReleaseGate(DetectionEngine(), pseudonyms, secret=STATE["secret"])
    gate.prepare()
    rw = gate.verify_release(report, records, exported, set(by_sha))
    unexpected = sorted(set(exported) - {str(f.get("output", "")).replace("sanitized/", "", 1)
                                          for f in report.get("files", []) if f.get("output")})
    res["release_wide"] = {"evaluated": True, "passed": rw.passed and not unexpected,
                           "codes": rw.safe_reason_codes + (["UNDECLARED_OUTPUT_FILE"] if unexpected else [])}

    blocked = (res["contract"].get("evaluated") and not res["contract"].get("ok")) or res["structure"]["total"] > 0 \
        or not res["release_wide"]["passed"]
    review = res["residual"]["total"] > 0 or res["clinical"]["kept"] < res["clinical"]["before"] \
        or not res["contract"].get("evaluated")
    res["status"] = "BLOCKED" if blocked else ("VERIFICATION REQUIRED" if review else "VERIFIED")
    return res


def run_release(rid: str) -> None:
    base = RELEASES / rid
    inp, out = base / "input", base / "output"
    summary = STATE["releases"][rid]
    try:
        summary.update(status="running", stage="pipeline")
        save_summary(rid, summary)
        env = dict(os.environ, RAKSHA_SECRET=STATE["secret"], PYTHONIOENCODING="utf-8")
        t0 = dt.datetime.now()
        proc = subprocess.run([sys.executable, "main.py", "--input", str(inp), "--output", str(out)],
                              cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=900)
        summary["pipeline"] = {"exit_code": proc.returncode,
                               "seconds": round((dt.datetime.now() - t0).total_seconds(), 2),
                               # main.py prints only counts on success and a safe reason code on failure
                               "message": ((proc.stdout if proc.returncode == 0 else proc.stderr).strip().splitlines() or [""])[-1][:200]}
        summary.update(status="verifying", stage="verification")
        save_summary(rid, summary)
        summary["assurance"] = assurance(inp, out, proc.returncode == 0)
        summary.update(status="complete" if proc.returncode == 0 else "failed", stage="done", finished_at=now())
    except Exception as exc:  # noqa: BLE001 - report a safe code, never the exception text
        summary.update(status="failed", stage="done", error=type(exc).__name__, finished_at=now())
    finally:
        shutil.rmtree(inp, ignore_errors=True)        # raw uploads never persist
        save_summary(rid, summary)


def create_release(files: list[dict]) -> tuple[int, dict]:
    if not isinstance(files, list) or not files:
        return 400, {"error": "no_files"}
    if len(files) > MAX_FILES:
        return 400, {"error": "too_many_files"}
    decoded, total = [], 0
    seen = set()
    for f in files:
        rel = safe_rel(str(f.get("path", ""))) if isinstance(f, dict) else None
        if rel is None:
            return 400, {"error": "unsafe_path"}
        if rel.as_posix().lower() in seen:
            return 400, {"error": "duplicate_path"}
        seen.add(rel.as_posix().lower())
        try:
            data = base64.b64decode(str(f.get("data", "")), validate=True)
        except (binascii.Error, ValueError):
            return 400, {"error": "bad_encoding"}
        total += len(data)
        if total > MAX_BYTES:
            return 413, {"error": "too_large"}
        decoded.append((rel, data))
    rid = uuid.uuid4().hex[:12]
    inp = RELEASES / rid / "input"
    for rel, data in decoded:
        dest = inp.joinpath(*rel.parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    summary = {"id": rid, "created_at": now(), "status": "queued", "stage": "queued",
               "files_uploaded": len(decoded), "bytes_uploaded": total,
               "unsupported_extensions": sum(1 for rel, _ in decoded if rel.suffix.lower() not in SUPPORTED)}
    save_summary(rid, summary)
    threading.Thread(target=run_release, args=(rid,), daemon=True).start()
    return 202, summary


# ----------------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "AnaamStudio"
    sys_version = ""

    def log_message(self, fmt, *args):  # route and status only
        route = urlparse(self.path).path
        route = re.sub(r"/api/releases/[0-9a-f]{12}(/.*)?", "/api/releases/<id>/...", route)
        sys.stderr.write(f"{self.command} {route} {args[1] if len(args) > 1 else ''}\n")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("127.0.0.1", "localhost")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                         "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._json(403, {"error": "host_not_allowed"})
        path = unquote(urlparse(self.path).path)
        if path == "/api/health":
            return self._json(200, {"ok": True, "engine": "main.py (Anaam CLI)", "offline": True,
                                    "secret_source": STATE["secret_source"],
                                    "kit_available": bool(STATE["kit"]), "evidence_available": EVIDENCE.is_file(),
                                    "supported_extensions": sorted(SUPPORTED)})
        if path == "/api/evidence":
            if not EVIDENCE.is_file():
                return self._json(404, {"available": False})
            return self._send(200, EVIDENCE.read_bytes(), "application/json")
        if path == "/api/releases":
            with STATE["lock"]:
                items = sorted(STATE["releases"].values(), key=lambda s: s["created_at"], reverse=True)
            return self._json(200, [{k: s.get(k) for k in ("id", "created_at", "finished_at", "status", "stage",
                                                           "files_uploaded")} | {"verdict": (s.get("assurance") or {}).get("status"),
                                                                                 "counts": (s.get("assurance") or {}).get("counts")}
                                    for s in items])
        m = re.fullmatch(r"/api/releases/([0-9a-f]{12})(?:/(.*))?", path)
        if m:
            rid, rest = m[1], m[2]
            s = STATE["releases"].get(rid)
            if s is None:
                return self._json(404, {"error": "not_found"})
            if not rest:
                return self._json(200, s)
            out = RELEASES / rid / "output"
            if rest in ("report.json", "records.jsonl"):
                target = out / rest
            elif rest.startswith("sanitized/") and (rel := safe_rel(rest)) is not None:
                target = out.joinpath(*rel.parts)
            else:
                return self._json(404, {"error": "not_found"})
            if not target.is_file() or not target.resolve().is_relative_to(out.resolve()):
                return self._json(404, {"error": "not_found"})
            disp = "attachment" if "download=1" in (urlparse(self.path).query or "") else "inline"
            return self._send(200, target.read_bytes(), MIME.get(target.suffix.lower(), "application/octet-stream"),
                              {"Content-Disposition": f'{disp}; filename="{target.name}"'})
        return self._static(path)

    def _static(self, path: str):
        if not DIST.is_dir():
            return self._send(503, b"Frontend not built: run `npm run build` in frontend/.", "text/plain; charset=utf-8")
        rel = safe_rel(path.lstrip("/")) if path not in ("", "/") else None
        target = DIST.joinpath(*rel.parts) if rel else DIST / "index.html"
        if not target.is_file():
            target = DIST / "index.html"                       # client-side routes
        return self._send(200, target.read_bytes(), MIME.get(target.suffix.lower(), "application/octet-stream"))

    def do_POST(self):  # noqa: N802
        if not self._host_ok():
            return self._json(403, {"error": "host_not_allowed"})
        if urlparse(self.path).path != "/api/releases":
            return self._json(404, {"error": "not_found"})
        if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
            return self._json(415, {"error": "json_required"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BYTES * 4 // 3 + 1_000_000:
            return self._json(413, {"error": "too_large"})
        try:
            body = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "bad_json"})
        code, obj = create_release(body.get("files") if isinstance(body, dict) else None)
        return self._json(code, obj)


def main() -> int:
    ap = argparse.ArgumentParser(description="Anaam Release Studio (local only)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--kit", default=str(ROOT.parent / "Secret-Wards-ToolKit"))
    a = ap.parse_args()
    if os.environ.get("RAKSHA_SECRET"):
        STATE["secret"], STATE["secret_source"] = os.environ["RAKSHA_SECRET"], "environment"
    else:
        STATE["secret"], STATE["secret_source"] = secrets.token_urlsafe(32), "session"
    kit = Path(a.kit)
    STATE["kit"] = kit.resolve() if (kit / "validate_output.py").is_file() else None
    RELEASES.mkdir(parents=True, exist_ok=True)
    load_releases()
    httpd = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"Anaam Release Studio on http://127.0.0.1:{a.port}  (local only; secret from {STATE['secret_source']})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
