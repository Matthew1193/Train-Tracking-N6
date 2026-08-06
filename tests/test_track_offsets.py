'''
import pytest
from train_tracking_api import calculate_track_due_time, NORTH_STATION_NAME, SOUTH_STATION_NAME

def test_northbound_offset():
    # Northbound train due in 4 mins at Rush & Lusk (Offset = 4)
    # Target: 4 - 4 = 0 mins away from camera
    track_mins = calculate_track_due_time("North", NORTH_STATION_NAME, due_in=4)
    assert track_mins == 0

def test_southbound_offset():
    # Southbound train due in 3 mins at Donabate (Offset = 1)
    # Target: 3 - 1 = 2 mins away from camera
    track_mins = calculate_track_due_time("South", SOUTH_STATION_NAME, due_in=3)
    assert track_mins == 2

def test_invalid_due_time():
    assert calculate_track_due_time("North", NORTH_STATION_NAME, due_in=999) == 999
'''