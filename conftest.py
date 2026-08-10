import sys
from unittest.mock import MagicMock

def ticks_diff(ticks1, ticks2):
    return ticks1 - ticks2

# Mock MicroPython hardware modules so CPython on laptop doesn't crash
sys.modules["sensor"] = MagicMock()
sys.modules["network"] = MagicMock()
sys.modules["ntptime"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["tf"] = MagicMock()

mock_time = MagicMock()
mock_time.ticks_ms.return_value = 0
mock_time.ticks_diff.side_effect = ticks_diff
sys.modules["utime"] = mock_time
sys.modules["time"] = mock_time

import pytest
import train_tracking_api


@pytest.fixture(autouse=True)
def reset_global_state():
    """Automatically resets all module-level state variables before each test."""
    train_tracking_api.current_state = train_tracking_api.STATE_API_POLL
    train_tracking_api.last_api_check = 0
    train_tracking_api.poll_interval = 300000
    train_tracking_api.extra_bg_frame = None
    train_tracking_api.global_counter = 0

    if hasattr(train_tracking_api, "train_tracker"):
        train_tracking_api.train_tracker.clear()

    yield

