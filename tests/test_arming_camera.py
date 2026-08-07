from unittest.mock import patch, MagicMock
import train_tracking_api


@patch("train_tracking_api.requests.get")
def test_arming_camera_under_three_mins(mock_get): 
    train_tracking_api.train_tracker.clear()
    train_tracking_api.current_state = train_tracking_api.STATE_API_POLL

    fake_xml = """<ArrayOfObjStationData>
        <objStationData>
            <Traincode>E204</Traincode>
            <Origin>Dundalk</Origin>
            <Destination>Connolly</Destination>
            <Traintype>Commuter</Traintype>
            <Duein>2</Duein>
            <Late>0</Late>
            <Schdepart>14:15</Schdepart>
        </objStationData>
    </ArrayOfObjStationData>"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = fake_xml
    mock_get.return_value = mock_response

    new_state = train_tracking_api.run_state_tick(now=1000)

    assert new_state == train_tracking_api.STATE_ARMED_WATCH
    assert (
        train_tracking_api.current_state == train_tracking_api.STATE_ARMED_WATCH
    )

@patch("train_tracking_api.requests.get")
def test_polling_interval_change(mock_get):
    fake_xml = """<ArrayOfObjStationData>
        <objStationData>
            <Traincode>E204</Traincode>
            <Origin>Dundalk</Origin>
            <Destination>Connolly</Destination>
            <Traintype>Commuter</Traintype>
            <Duein>8</Duein>
            <Late>0</Late>
            <Schdepart>14:15</Schdepart>
        </objStationData>
    </ArrayOfObjStationData>"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = fake_xml
    mock_get.return_value = mock_response

    _ = train_tracking_api.run_state_tick(now=1000)

    assert train_tracking_api.poll_interval == 120000

    train_tracking_api.train_tracker.clear()
    train_tracking_api.current_state = train_tracking_api.STATE_API_POLL
    train_tracking_api.last_api_check = 0


    fake_xml = """<ArrayOfObjStationData>
        <objStationData>
            <Traincode>E204</Traincode>
            <Origin>Dundalk</Origin>
            <Destination>Connolly</Destination>
            <Traintype>Commuter</Traintype>
            <Duein>13</Duein>
            <Late>0</Late>
            <Schdepart>14:15</Schdepart>
        </objStationData>
    </ArrayOfObjStationData>"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = fake_xml
    mock_get.return_value = mock_response

    _ = train_tracking_api.run_state_tick(now=200000)

    assert train_tracking_api.poll_interval == 300000

def test_watchdog_timer_armed_state():
    mock_stats = MagicMock()
    mock_stats.max = 0
    train_tracking_api.sensor.snapshot.return_value.difference.return_value.get_statistics.return_value = (
        mock_stats
    )

    mock_img = MagicMock()
    mock_img.difference.return_value.get_statistics.return_value = mock_stats
    train_tracking_api.sensor.snapshot.return_value = mock_img
    train_tracking_api.extra_bg_frame = mock_img

    train_tracking_api.current_state = train_tracking_api.STATE_ARMED_WATCH
    train_tracking_api.armed_state_start = 1000

    _ = train_tracking_api.run_state_tick(now = 310000)

    assert train_tracking_api.current_state == train_tracking_api.STATE_API_POLL