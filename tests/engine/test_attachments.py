import base64

from detection.attachments import decode_base64, encode, find_payloads, sanitize_payload


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def fake_scrub(text):
    n = text.count("Dorje Lhamo")
    return text.replace("Dorje Lhamo", "[NAME]"), n


def test_base64_text_found_and_rescrubbed():
    data = b64("Consent witnessed by Dorje Lhamo, phone 8921593556.")
    text = f'{{"data": "{data}"}}'
    [p] = find_payloads(text)
    assert p.encoding == "base64" and "Dorje" in p.decoded
    repl, changed = sanitize_payload(p, fake_scrub)
    assert changed
    assert "Dorje" not in base64.b64decode(repl).decode()


def test_clean_payload_unchanged():
    [p] = find_payloads(b64("Referral for follow-up of Hypothyroidism, unspecified."))
    assert sanitize_payload(p, fake_scrub) == ("", False)


def test_binary_payload_flagged():
    data = base64.b64encode(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3 binary stream here").decode()
    [p] = find_payloads(data)
    assert p.binary and p.decoded is None


def test_long_words_and_uuids_are_not_payloads():
    assert not find_payloads("Pancreaticoduodenectomyxx and urn:uuid:ad12498f-1df9-4895-8cc5-ef79c3b941a0")
    assert not find_payloads("RESOURCETYPEBUNDLEDOCUMENTENTRY")


def test_unicode_escapes():
    text = r"name \u0930\u0940\u0928\u093e here"
    [p] = find_payloads(text)
    assert p.encoding == "unicode_escape" and p.decoded == "रीना"
    assert encode("रीना", "unicode_escape") == r"\u0930\u0940\u0928\u093e"


def test_html_entities_and_percent():
    [p] = find_payloads("&#2352;&#2368;&#2344;&#2366;")
    assert p.decoded == "रीना"
    [q] = find_payloads("path=Meenakshi%20Iyer%5F063763")
    assert q.decoded == "Meenakshi Iyer_063763"


def test_decode_base64_rejects_garbage():
    assert decode_base64("AAAAAAAAAAAAAAAAAAAAAAAAAAAA") == (None, True) or \
        decode_base64("AAAAAAAAAAAAAAAAAAAAAAAAAAAA")[0] is None
