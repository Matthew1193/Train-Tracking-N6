import pytest
from train_tracking_api import safe_int, get_tag_value

def test_safe_int_valid():
    assert safe_int("5") == 5
    assert safe_int("0") == 0

def test_safe_int_negative_numbers():
    # Irish Rail sends negative numbers for trains already departing
    assert safe_int("-1") == -1
    assert safe_int("-5") == -5

def test_safe_int_invalid_or_empty():
    assert safe_int("") == 999
    assert safe_int("corrupted_data") == 999
    assert safe_int("10 mins late", default=0) == 0

def test_get_tag_value_extraction():
    xml_snippet = "<objStationData><Traincode>E108</Traincode><Duein>4</Duein></objStationData>"
    assert get_tag_value(xml_snippet, "Traincode") == "E108"
    assert get_tag_value(xml_snippet, "Duein") == "4"
    assert get_tag_value(xml_snippet, "NonExistentTag") == ""