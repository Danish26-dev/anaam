import pytest

from src import contracts as c
from src.detection.address import address_segments, detect_address_components


def parts(text, spans):
    return {(text[s.start:s.end], s.category, s.proposed_action) for s in spans}


def test_registration_address_field():
    text = ("C/O Parveez Kakati, H.No. 364, Ward 20, Mohalla Raja Bazar, near Pani Tanki, "
            "Tehsil Lalganj, Distt. Rae Bareli")
    got = parts(text, address_segments(text, 0, len(text)))
    assert ("H.No. 364", c.HOUSE, c.REDACT) in got
    assert ("Ward 20", c.LOCALITY, c.REDACT) in got
    assert ("Mohalla Raja Bazar", c.LOCALITY, c.REDACT) in got
    assert ("near Pani Tanki", c.LANDMARK, c.REDACT) in got
    assert ("Lalganj", c.TEHSIL, c.KEEP) in got
    assert ("Rae Bareli", c.DISTRICT, c.KEEP) in got
    assert ("C/O Parveez Kakati", c.ADDRESS, c.REDACT) in got


def test_unknown_segment_is_redacted():
    text = "Plot 7 Sunrise Enclave, Tehsil Purwa, Distt. Unnao"
    got = parts(text, address_segments(text, 0, len(text)))
    assert ("Plot 7 Sunrise Enclave", c.HOUSE, c.REDACT) in got   # whole segment is removed
    text2 = "Sunrise Enclave Annexe, Tehsil Purwa, Distt. Unnao"
    assert ("Sunrise Enclave Annexe", c.ADDRESS, c.REDACT) in parts(text2, address_segments(text2, 0, len(text2)))


def test_discharge_address_line():
    text = ("Patient Name: X\nAddress: House 180, Ward 20, Mohalla Subhash Nagar, near Panchayat "
            "Bhawan, Gram Shivkheda, Tehsil Misrikh, Distt. Sitapur - 296358\nMobile: 1")
    got = parts(text, detect_address_components(text))
    assert ("House 180", c.HOUSE, c.REDACT) in got
    assert ("Shivkheda", c.VILLAGE, c.GENERALIZE_LOCATION) in got
    assert ("296358", c.PIN, c.GENERALIZE_PIN) in got
    assert ("Sitapur", c.DISTRICT, c.KEEP) in got
    assert not any("Mobile" in t for t, _, _ in got)


def test_hindi_address_line():
    text = "पता: मकान नं. 398, ग्राम नंदपुर, तहसील कादीपुर, जिला सुल्तानपुर - 295524\nमोबाइल"
    got = parts(text, detect_address_components(text))
    assert ("मकान नं. 398", c.HOUSE, c.REDACT) in got
    assert ("नंदपुर", c.VILLAGE, c.GENERALIZE_LOCATION) in got
    assert ("कादीपुर", c.TEHSIL, c.KEEP) in got
    assert ("सुल्तानपुर", c.DISTRICT, c.KEEP) in got
    assert ("295524", c.PIN, c.GENERALIZE_PIN) in got


def test_hindi_landmark_and_locality():
    text = "मकान नं. 32, जामा मस्जिद के पीछे, मोहल्ला राजा बाज़ार, तहसील नवाबगंज"
    got = parts(text, address_segments(text, 0, len(text)))
    assert ("जामा मस्जिद के पीछे", c.LANDMARK, c.REDACT) in got
    assert ("मोहल्ला राजा बाज़ार", c.LOCALITY, c.REDACT) in got


def test_village_label_stops_at_line_end():
    text = "ग्राम: रामगंज कलां\nतारीख: 03/23/2026"
    got = parts(text, detect_address_components(text))
    assert ("रामगंज कलां", c.VILLAGE, c.GENERALIZE_LOCATION) in got


@pytest.mark.parametrize("text", [
    "Ward 8 (Medicine), Bed 2", "BP near normal range", "Review after 2 weeks",
    "Platelet count below 20000 /uL requires admission",
])
def test_no_false_address(text):
    assert not [s for s in detect_address_components(text) if s.proposed_action != c.KEEP]
