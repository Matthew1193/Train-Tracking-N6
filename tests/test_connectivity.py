from unittest.mock import patch, MagicMock
import train_tracking_api
import math

@patch("train_tracking_api.requests.get")
def test_check_trains_http_error(mock_get):
    """Ensure non-200 responses don't crash the tracker and return default fallback."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    next_due_south, next_due_north = train_tracking_api.check_trains()
    
    assert next_due_south == math.inf
    assert next_due_north == math.inf

