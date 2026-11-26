"""D9: structural checks on candidate output (parse, shape, FHIR references, pseudonyms).

All functions return a list of safe reason codes (empty = ok). No content is included.
"""
from __future__ import annotations

import csv
import io
import json


def check_utf8(data: bytes) -> list[str]:
    try:
        (data[3:] if data.startswith(b"\xef\xbb\xbf") else data).decode("utf-8")
        return []
    except UnicodeDecodeError:
        return ["NOT_UTF8"]


def check_csv(output: str, delimiter: str, n_columns: int, n_rows: int) -> list[str]:
    try:
        rows = list(csv.reader(io.StringIO(output, newline=""), delimiter=delimiter))
    except csv.Error:
        return ["CSV_UNPARSEABLE"]
    codes = []
    if len(rows) != n_rows + 1:
        codes.append("CSV_ROW_COUNT")
    if rows and len(rows[0]) != n_columns:
        codes.append("CSV_HEADER_WIDTH")
    return codes


def check_json(output: str) -> tuple[list[str], object | None]:
    try:
        return [], json.loads(output)
    except ValueError:
        return ["JSON_UNPARSEABLE"], None


def _paths(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _paths(v, f"{prefix}/{k}")
    elif isinstance(obj, list):
        for v in obj:
            yield from _paths(v, f"{prefix}/*")
    else:
        yield prefix, type(obj).__name__


def check_json_shape(original: object, output: object, exempt_prefixes=()) -> list[str]:
    """Key-path set and leaf types must match, except exempt generalizable paths."""
    a, b = set(_paths(original)), set(_paths(output))
    codes = []
    ka = {p for p, _ in a}
    kb = {p for p, _ in b}
    missing = {p for p in ka - kb if not p.startswith(tuple(exempt_prefixes))}
    if missing:
        codes.append("JSON_PATHS_LOST")
    ta = {p: t for p, t in a if p in kb}
    for p, t in b:
        if p in ta and ta[p] != t and ta[p] != "NoneType" and t != "NoneType" and not p.startswith(tuple(exempt_prefixes)):
            codes.append("JSON_TYPE_CHANGED")
            break
    return codes


def check_fhir_references(bundle: object) -> list[str]:
    """Every Reference.reference must resolve to an entry fullUrl or Type/id in the bundle."""
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        return ["FHIR_NOT_BUNDLE"]
    urls, ids = set(), set()
    for e in bundle.get("entry") or []:
        if not isinstance(e, dict):
            continue
        if e.get("fullUrl"):
            urls.add(e["fullUrl"])
        r = e.get("resource") or {}
        if r.get("resourceType") and r.get("id"):
            ids.add(f'{r["resourceType"]}/{r["id"]}')
    bad = 0

    def walk(o):
        nonlocal bad
        if isinstance(o, dict):
            ref = o.get("reference")
            if isinstance(ref, str) and ref not in urls and ref not in ids and not ref.startswith("#"):
                bad += 1
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(bundle)
    return ["FHIR_UNRESOLVED_REFERENCE"] if bad else []


def check_pseudonym_present(output_text: str, pseudonym: str | None) -> list[str]:
    if pseudonym and pseudonym not in output_text:
        return ["PSEUDONYM_MISSING"]
    return []
