"""D8: encoded payloads (base64, \\uXXXX escapes, %-encoding, HTML entities, hex).

The scorer decodes these before searching for leaks, so a name inside a base64 attachment
is a leak. `find_payloads(text)` returns every encoded run that decodes to readable text.
`sanitize_payload(payload, scrub)` scrubs the decoded text with the supplied function and
re-encodes it in the same encoding. Binary payloads (PDF, JPEG) are reported as unsafe:
they cannot be checked, so the caller must replace or quarantine them.
"""
from __future__ import annotations

import base64
import binascii
import html
import re
from urllib.parse import quote, unquote   # pure string helpers; no network
from dataclasses import dataclass

BASE64_RUN = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/=])")
UNICODE_ESCAPES = re.compile(r"(?:\\u[0-9a-fA-F]{4}){2,}")
PERCENT_RUN = re.compile(r"(?<![\w%])(?:[\w.~\-/:+]*%[0-9A-Fa-f]{2})+[\w.~\-]*")
HTML_ENTITY_RUN = re.compile(r"(?:&#(?:x[0-9a-fA-F]+|\d+);|&[a-zA-Z]{2,8};){2,}")
HEX_RUN = re.compile(r"(?<![0-9a-fA-F])(?:[0-9a-fA-F]{2}){12,}(?![0-9a-fA-F])")

BINARY_MAGIC = (b"%PDF", b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"PK\x03\x04", b"\xd0\xcf\x11\xe0",
                b"II*\x00", b"MM\x00*", b"RIFF", b"\x1f\x8b")
SAFE_BINARY_PLACEHOLDER = "[attachment removed]"


@dataclass
class Payload:
    start: int
    end: int
    encoding: str          # base64 | unicode_escape | percent | html | hex
    decoded: str | None    # None for binary payloads
    binary: bool = False


def _printable_ratio(s: str) -> float:
    if not s:
        return 0.0
    ok = sum(1 for ch in s if ch.isprintable() or ch in "\n\r\t")
    return ok / len(s)


def _decode_bytes(raw: bytes) -> tuple[str | None, bool]:
    """(text, binary). Only known file signatures count as binary payloads: a run that
    decodes to neither text nor a known file type is ordinary text (a URL path, a word)."""
    if raw.startswith(BINARY_MAGIC):
        return None, True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, False
    if _printable_ratio(text) < 0.9 or not re.search(r"[A-Za-z\u0900-\u097F]{2}", text):
        return None, False
    return text, False


def decode_base64(token: str) -> tuple[str | None, bool]:
    try:
        raw = base64.b64decode(token + "=" * (-len(token) % 4), validate=True)
    except (binascii.Error, ValueError):
        return None, False
    if len(raw) < 12:
        return None, False
    return _decode_bytes(raw)


def find_payloads(text: str) -> list[Payload]:
    out: list[Payload] = []
    for m in BASE64_RUN.finditer(text):
        tok = m.group(0)
        if tok.isalpha() and (tok.islower() or tok.isupper() or len(tok) < 40):
            continue  # an ordinary long word, not base64
        decoded, binary = decode_base64(tok)
        if decoded is not None or binary:
            out.append(Payload(m.start(), m.end(), "base64", decoded, binary))
    for m in UNICODE_ESCAPES.finditer(text):
        try:
            decoded = m.group(0).encode("ascii").decode("unicode_escape")
        except UnicodeDecodeError:
            continue
        out.append(Payload(m.start(), m.end(), "unicode_escape", decoded))
    for m in PERCENT_RUN.finditer(text):
        decoded = unquote(m.group(0), errors="strict") if _valid_percent(m.group(0)) else None
        if decoded and decoded != m.group(0) and _printable_ratio(decoded) > 0.9:
            out.append(Payload(m.start(), m.end(), "percent", decoded))
    for m in HTML_ENTITY_RUN.finditer(text):
        out.append(Payload(m.start(), m.end(), "html", html.unescape(m.group(0))))
    for m in HEX_RUN.finditer(text):
        tok = m.group(0)
        if tok.isdigit():
            continue
        try:
            decoded, binary = _decode_bytes(bytes.fromhex(tok))
        except ValueError:
            continue
        if decoded is not None:
            out.append(Payload(m.start(), m.end(), "hex", decoded))
    out.sort(key=lambda p: (p.start, -(p.end - p.start)))
    kept: list[Payload] = []
    for p in out:
        if kept and p.start < kept[-1].end:
            continue
        kept.append(p)
    return kept


def _valid_percent(s: str) -> bool:
    try:
        unquote(s, errors="strict")
        return True
    except UnicodeDecodeError:
        return False


def encode(text: str, encoding: str) -> str:
    if encoding == "base64":
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    if encoding == "unicode_escape":
        return "".join(f"\\u{ord(ch):04x}" if ord(ch) > 127 else ch for ch in text)
    if encoding == "percent":
        return quote(text, safe=" ")
    if encoding == "html":
        return "".join(f"&#{ord(ch)};" if ord(ch) > 127 or ch in "<>&\"'" else ch for ch in text)
    if encoding == "hex":
        return text.encode("utf-8").hex()
    raise ValueError("unknown encoding")


def sanitize_payload(payload: Payload, scrub) -> tuple[str, bool]:
    """(replacement, changed). `scrub(text) -> (clean_text, n_edits)` is the text detector."""
    if payload.binary or payload.decoded is None:
        return encode(SAFE_BINARY_PLACEHOLDER, payload.encoding if payload.encoding != "hex" else "base64"), True
    clean, n = scrub(payload.decoded)
    if not n:
        return "", False
    return encode(clean, payload.encoding), True
