from unittest.mock import patch, MagicMock
from train_tracking_api import find_matching_train_code, train_tracker

def test_find_matching_train_code():
    # Seed local state
    train_tracker.clear()
    train_tracker["E108"] = {
        "camera_detected": False,
        "is_unscheduled": False,
        "api_due_mins" : 2,
        "track_due_mins": 1
    }
    
    # Should match E108 because track_due_mins is in window [-1, 1]
    matched_code = find_matching_train_code()
    assert matched_code == "E108"

@patch("train_tracking_api.requests.get")
def test_check_trains_mocked_api(mock_get):
    train_tracker.clear()

    # Mock fake XML response from Irish Rail API
    fake_xml = """<ArrayOfObjStationData>
        <objStationData>
            <Traincode>E108</Traincode>
            <Origin>Dundalk</Origin>
            <Destination>Bray</Destination>
            <Traintype>Commuter</Traintype>
            <Duein>4</Duein>
            <Late>0</Late>
            <Schdepart>14:15</Schdepart>
        </objStationData>
    </ArrayOfObjStationData>"""
    
    # Configure mock response object
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = fake_xml
    mock_get.return_value = mock_response

    from train_tracking_api import check_trains
    next_due = check_trains("Rush and Lusk", "http://fake-api-url")
    
    assert next_due == 4
    assert "E108" in train_tracker
    assert train_tracker["E108"]["scheduled_time"] == "14:15"