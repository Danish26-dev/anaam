import pytest

from detection.transliteration import loose_form, name_key, to_latin


@pytest.mark.parametrize("variants", [
    ["Mohammad", "Muhammad", "Mohd", "Md", "मोहम्मद"],
    ["Harish", "Hareesh", "हरीश"],
    ["Nishad", "निषाद"],
    ["Pandey", "Pande", "पांडे"],
    ["Chauhan", "Chouhan", "चौहान"],
    ["Siddiqui", "सिद्दीक़ी"],
    ["Fatima", "Fatma", "फ़ातिमा"],
    ["Khatoon", "Khatun", "ख़ातून"],
    ["Brijesh", "Brajesh"],
    ["Ansari", "अंसारी"],
    ["Barabanki", "बाराबंकी"],
    ["Sultanpur", "सुल्तानपुर"],
    ["Singh", "सिंह"],
])
def test_name_key_matches_across_scripts(variants):
    keys = {name_key(v) for v in variants}
    assert len(keys) == 1, {v: name_key(v) for v in variants}


def test_loose_form_folds_vowel_length():
    assert loose_form("Reena") == loose_form("Rina") == loose_form("रीना")
    assert loose_form("Shanthi") == loose_form("Shanti")


def test_different_names_differ():
    assert name_key("Kamal") != name_key("Ramesh")
    assert loose_form("Asha") != loose_form("Usha")


def test_to_latin_readable():
    assert to_latin("ईश्वर्या मंडल") == "eeshvaryaa mandal"
    assert to_latin("Rina") == "Rina"
