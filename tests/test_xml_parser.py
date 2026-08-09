from unittest.mock import patch, MagicMock
import train_tracking_api
import math

def test_safe_int_valid():
    assert train_tracking_api.safe_int("5") == 5
    assert train_tracking_api.safe_int("0") == 0

def test_safe_int_negative_numbers():
    assert train_tracking_api.safe_int("-1") == -1
    assert train_tracking_api.safe_int("-5") == -5

def test_safe_int_invalid_or_empty():
    assert train_tracking_api.safe_int("") == 999
    assert train_tracking_api.safe_int("corrupted_data") == 999
    assert train_tracking_api.safe_int("10 mins late", default=0) == 0

def test_get_tag_value_extraction():
    xml_snippet = "<objStationData><Traincode>E108</Traincode><Duein>4</Duein></objStationData>"
    assert train_tracking_api.get_tag_value(xml_snippet, "Traincode") == "E108"
    assert train_tracking_api.get_tag_value(xml_snippet, "Duein") == "4"
    assert train_tracking_api.get_tag_value(xml_snippet, "NonExistentTag") == ""

@patch("train_tracking_api.requests.get")
def test_check_trains_empty_xml(mock_get):
    """Ensure empty XML responses (no trains running) are handled gracefully."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<ArrayOfObjStationData></ArrayOfObjStationData>"
    mock_get.return_value = mock_response

    next_due_south, next_due_north = train_tracking_api.check_trains()
    
    assert next_due_north == math.inf
    assert next_due_south == math.inf
    assert len(train_tracking_api.train_tracker) == 0

def test_safe_int_type_robustness():
    assert train_tracking_api.safe_int(None) == 999
    assert train_tracking_api.safe_int("  7  ") == 7
    assert train_tracking_api.safe_int("3.14") == 999  # Float strings fail standard int()


def test_get_tag_value_self_closing_and_whitespace():
    assert train_tracking_api.get_tag_value("<objStationData><Traincode/></objStationData>", "Traincode") == ""
    assert train_tracking_api.get_tag_value("<Duein>  5  </Duein>", "Duein") == "5"