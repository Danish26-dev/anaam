"""O3: encoding detection and decoding.

Order of attempts, per the engineering plan:
  1. UTF-8 with BOM
  2. UTF-8
  3. UTF-16 with BOM or strong evidence
  4. cp1252
  5. otherwise: undecodable -> caller quarantines

Returns both the decoded text and the detected encoding label, so the label can be
recorded on FileEnvelope.detected_encoding without re-sniffing later.
"""
from __future__ import annotations

_UTF16_LE_BOM = b"\xff\xfe"
_UTF16_BE_BOM = b"\xfe\xff"
_UTF8_BOM = b"\xef\xbb\xbf"


def _utf16_endian(raw: bytes) -> str | None:
    """Return the strongly-indicated BOM-less UTF-16 endian, if any.

    ASCII-range UTF-16LE has NUL bytes mainly in odd positions; UTF-16BE has them mainly
    in even positions. Choosing from that orientation avoids accepting a valid-but-garbled
    decode under the wrong endian merely because Python did not raise UnicodeDecodeError.
    """
    if len(raw) < 4:
        return None
    sample = raw[:4096]
    even_nulls = sum(1 for i in range(0, len(sample), 2) if sample[i] == 0)
    odd_nulls = sum(1 for i in range(1, len(sample), 2) if sample[i] == 0)
    total_pairs = max(1, len(sample) // 2)
    even_ratio = even_nulls / total_pairs
    odd_ratio = odd_nulls / total_pairs
    if odd_ratio > 0.3 and odd_ratio > even_ratio * 2:
        return "utf-16-le"
    if even_ratio > 0.3 and even_ratio > odd_ratio * 2:
        return "utf-16-be"
    return None


def decode(raw: bytes) -> tuple[str, str] | tuple[None, None]:
    """Decode raw bytes to text. Returns (text, encoding_label) or (None, None) if every
    attempt fails, in which case the caller must quarantine the file.
    """
    # A UTF-16 BOM embedded after other bytes is corruption, not a legitimate cp1252
    # character sequence. Accepting it as printable text would pass malformed exports.
    if _UTF16_LE_BOM in raw[1:] or _UTF16_BE_BOM in raw[1:]:
        return None, None

    if raw.startswith(_UTF8_BOM):
        try:
            return raw[len(_UTF8_BOM):].decode("utf-8", errors="strict"), "utf-8-sig"
        except UnicodeDecodeError:
            pass

    if raw.startswith((_UTF16_LE_BOM, _UTF16_BE_BOM)):
        try:
            # The generic codec consumes either BOM instead of leaving U+FEFF in the
            # first header/key, while still decoding with the correct endian.
            endian = "utf-16-le" if raw.startswith(_UTF16_LE_BOM) else "utf-16-be"
            return raw.decode("utf-16", errors="strict"), endian
        except UnicodeDecodeError:
            pass

    try:
        return raw.decode("utf-8", errors="strict"), "utf-8"
    except UnicodeDecodeError:
        pass

    utf16_endian = _utf16_endian(raw)
    if utf16_endian is not None:
        try:
            return raw.decode(utf16_endian, errors="strict"), utf16_endian
        except UnicodeDecodeError:
            pass

    if b"\x00" in raw:
        return None, None

    try:
        return raw.decode("cp1252", errors="strict"), "cp1252"
    except UnicodeDecodeError:
        pass

    return None, None
