from unittest.mock import patch, MagicMock
import train_tracking_api
import math

def test_find_matching_train_code():
    # Seed local state
    train_tracking_api.train_tracker.clear()
    train_tracking_api.train_tracker["E108"] = {
        "camera_detected": False,
        "is_unscheduled": False,
        "api_due_mins" : 2,
        "track_due_mins": 1,
        "direction": "North",
    }
    
    # Should match E108 because track_due_mins is in window [-1, 1]
    matched_code = train_tracking_api.find_matching_train_code("North")
    assert matched_code == "E108"


@patch("train_tracking_api.update_schedule_from_api")
@patch("train_tracking_api.requests.get")
def test_check_trains_mocked_api(mock_get, mock_update_schedule):
    # Mock XML containing a Southbound train (Bray destination) due in 4 mins
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

    # Configure API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = fake_xml
    mock_get.return_value = mock_response

    # Execute function
    next_due_south, next_due_north = train_tracking_api.check_trains()

    # Assertions
    assert next_due_south == 4
    assert next_due_north == train_tracking_api.INT_MAX

    # Verify requests.get was called for each station in the set (4 times)
    assert mock_get.call_count == 4

    # Verify update_schedule_from_api was called with correct arguments
    mock_update_schedule.assert_called_with(
        train_code="E108",
        origin="Dundalk",
        destination="Bray",
        direction="South",
        scheduled_time="14:15",
        due_in=4,
        late_mins=0
    )

def test_find_matching_train_code_boundaries():
    """Verify window limits [-1, 1] for train matching."""
    train_tracker = train_tracking_api.train_tracker
    
    # Boundary test: Outside window (-2 and +2)
    train_tracker.clear()
    train_tracker["E101"] = {"track_due_mins": -2, "direction": "South", "camera_detected": False, "is_unscheduled": False}
    train_tracker["E102"] = {"track_due_mins": 2,  "direction": "North", "camera_detected": False, "is_unscheduled": False}
    assert train_tracking_api.find_matching_train_code("North") is "E102"
    assert train_tracking_api.find_matching_train_code("South") is "E101"


    # Boundary test: On exact edges (-1, 0, 1)
    train_tracker["E101"] = {"track_due_mins": -1,  "direction": "South", "camera_detected": True, "is_unscheduled": False}
    assert train_tracking_api.find_matching_train_code("South") is None

    train_tracker.clear()
    train_tracker["E104"] = {"track_due_mins": 1,  "direction": "North", "camera_detected": False, "is_unscheduled": True}
    assert train_tracking_api.find_matching_train_code("North") is None

@patch("train_tracking_api.requests.get")
def test_check_trains_multiple_trains_selects_closest(mock_get):
    """Ensure check_trains updates multiple entries and identifies the soonest train."""
    fake_xml = """<ArrayOfObjStationData>
        <objStationData>
            <Traincode>E108</Traincode>
            <Duein>15</Duein>
            <Schdepart>14:15</Schdepart>
            <Destination>Dublin Connolly</Destination>
        </objStationData>
        <objStationData>
            <Traincode>E204</Traincode>
            <Duein>3</Duein>
            <Schdepart>14:03</Schdepart>
            <Destination>Dublin Connolly</Destination>
        </objStationData>
    </ArrayOfObjStationData>"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = fake_xml
    mock_get.return_value = mock_response

    next_due_south, next_due_north = train_tracking_api.check_trains()
    
    assert next_due_south == 3
    assert next_due_north == math.inf
    assert "E108" in train_tracking_api.train_tracker
    assert "E204" in train_tracking_api.train_tracker