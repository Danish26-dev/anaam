from detection.normalization import TextView, digits_only, normalize_key, tokenize


def test_phone_forms_compare_equal():
    assert digits_only("9876543210") == digits_only("98 7654 3210") == digits_only("९८७६५४३२१०")


def test_zero_width_removed_and_offsets_map_back():
    original = "Ta\u200brun Kakati"
    view = TextView.of(original)
    assert view.text == "Tarun Kakati"
    start = view.text.index("Tarun")
    a, b = view.span_to_original(start, start + len("Tarun"))
    assert original[a:b] == "Ta\u200brun"


def test_homoglyphs_fold_to_latin():
    cyrillic = "\u0410nita"  # Cyrillic capital A
    assert TextView.of(cyrillic).text == "Anita"
    assert normalize_key(cyrillic) == "anita"


def test_devanagari_digits_and_offsets():
    original = "मोबाइल: ७५२८२१०५८७"
    view = TextView.of(original)
    assert view.text.endswith("7528210587")
    i = view.text.index("7528210587")
    a, b = view.span_to_original(i, i + 10)
    assert original[a:b] == "७५२८२१०५८७"


def test_diacritics_stripped_but_devanagari_kept():
    assert TextView.of("Jos\u00e9").text == "Jose"
    assert TextView.of("रीना").text == "रीना"


def test_fullwidth_digits():
    assert digits_only("\uff19\uff18\uff17") == "987"


def test_tokenize_scripts():
    toks = tokenize("Rina रीना 42 Addison's")
    assert [(t.text, t.script) for t in toks] == [
        ("Rina", "latin"), ("रीना", "deva"), ("42", "digit"), ("Addison's", "latin")]
