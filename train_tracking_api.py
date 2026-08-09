import time
import network
import requests
import gc
import sensor
import math

'''
JSON Schema:

    {
        "train_code": "E204",
        "train_type": "COMMUTER", <- commuter/intercity/enterprise/translink/DART
        "origin": "Dundalk",
        "destination": "Connolly",
        "direction": "South",
        "is_unscheduled": false,
        "scheduled_epoch_time": 1722953700,
        "api_polled_epoch_time": 1722953580,
        "api_delay_mins": 2,
        "observed_epoch_time": 1722953820,
        "actual_delay_sec": 120,
        "api_error_sec": 0,
        "station_observer": "Rush and Lusk"
    }
'''

INT_MAX = math.inf

WIFI_SSID = "eir85227665"
WIFI_PASS = "xV2dSg9ruH"

STATE_API_POLL = 0
STATE_ARMED_WATCH = 1
STATE_INFER_LOG = 2

# Track ROI over train lines (x, y, w, h)
TRACK_ROI = (100, 100, 120, 80)

MOTION_THRESHOLD = 25

train_tracker = {}
global_counter = 0
current_state = STATE_API_POLL
last_api_check = 0
poll_interval = 0
armed_state_start = 0
state_direction = "Unknown"

# --- Safe Integer Conversion Helper ---
def safe_int(val, default=999):
    """Safely converts string values (including negative ints like '-1') to integers."""
    if not val:
        return default
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        return default

# --- XML Helper ---
def get_tag_value(xml_block, tag_name, default=""):
    start_tag = f"<{tag_name}>"
    end_tag = f"</{tag_name}>"

    start_pos = xml_block.find(start_tag)
    if start_pos == -1:
        return default

    start_pos += len(start_tag)
    end_pos = xml_block.find(end_tag, start_pos)

    if end_pos == -1:
        return default

    return xml_block[start_pos:end_pos].strip()

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1

    if wlan.isconnected():
        print("Connected! IP:", wlan.ifconfig()[0])
        return True

    print("Wi-Fi Connection Failed.")
    return False

def check_trains():
    stations = {"Donabate", "Rush%20and%20Lusk", "Drogheda", "Dublin%20Connolly"} # Search each station a certain period of time ahead to speed up API calls
    next_train_north = INT_MAX
    next_train_south = INT_MAX

    for station in stations:
        API_URL = f"http://api.irishrail.ie/realtime/realtime.asmx/getStationDataByNameXML?StationDesc={station}"
        print(f"\n--- Checking API Data for {station} ---")

        try:
            res = requests.get(API_URL)
            if res.status_code == 200:
                if hasattr(res, "text") and isinstance(res.text, str):
                    xml_text = res.text
                elif hasattr(res, "content"):
                    data = res.content
                    xml_text = data.decode("utf-8") if isinstance(data, bytes) else str(data)
                else:
                    xml_text = str(res)

                if hasattr(res, "close"):
                    res.close()
                elif hasattr(res, "socket"):
                    res.socket.close()

                train_blocks = xml_text.split("<objStationData>")
                train_count = len(train_blocks) - 1

                for block in train_blocks[1:]:
                    train_code = get_tag_value(block, "Traincode", "Unknown")
                    origin = get_tag_value(block, "Origin", "")
                    destination = get_tag_value(block, "Destination", "")
                    train_type = get_tag_value(block, "Traintype", "")

                    # Use safe_int helper to prevent 'base 10' string parsing crashes
                    due_in_raw = get_tag_value(block, "Duein", "999")
                    due_in = safe_int(due_in_raw, 999)

                    late_mins_raw = get_tag_value(block, "Late", "0")
                    late_mins = safe_int(late_mins_raw, 0)

                    last_loc = get_tag_value(block, "Lastlocation", "No location info")

                    local_due = INT_MAX

                    if "Belfast" in origin or "Belfast" in destination or train_type == "INTERCITY":
                        line_name = "Belfast Intercity"
                    else:
                        line_name = "Drogheda/Dundalk Commuter"

                    delay_str = "On Time" if late_mins == 0 else f"{late_mins} mins late"

                    northbound_destinations = ("Belfast", "Drogheda", "Dundalk")
                    southbound_destinations = ("Dublin Connolly", "Dublin Pearse", "Grand Canal Dock", "Dun Laoighre", "Bray")

                    if destination in northbound_destinations:
                        direction = "North"
                    elif destination in southbound_destinations:
                        direction = "South"
                    else:
                        continue

                    if "North" in direction:
                        if "Rush%20and%20Lusk" in station or "Donabate" in station:
                            local_due = due_in
                        elif "Belfast" in destination and "Drogheda" in station:
                            if 17 <= due_in <= 22:
                                local_due = due_in - 15

                        if 0 <= local_due < next_train_north:
                            next_train_north = local_due

                    elif "South" in direction:# Have it find the next Belfast train and ignore the rest to
                                                            # speed up Connolly API check, can I query just Belfast destination form Connolly on API?
                        if "Rush%20and%20Lusk" in station or "Donabate" in station:
                            local_due = due_in
                        elif "Belfast" in origin and "Dublin%20Connolly" in station:
                            if 17 <= due_in <= 22:
                                local_due = due_in - 15

                        if 0 <= local_due < next_train_south:
                                next_train_south = local_due

                    update_schedule_from_api(
                            train_code=train_code,
                            origin=origin,
                            destination=destination,
                            direction=direction,
                            scheduled_time=get_tag_value(block, "Schdepart", "00:00"),
                            due_in=due_in,
                            late_mins=late_mins
                    )

                    # Filter out negative numbers (trains already departing/passed)
                    '''
                    if 0 <= due_in < next_train_mins and direction == "North":
                        if direction == "North" and due_in < next_north_train:
                            next_train_north = due_in
                        elif due_in < next_south_train:
                            next_train_south = due_in
                    '''

                    if 0 <= local_due <= 5:
                        print(f"[{line_name} - {direction}bound] Code: {train_code}")
                        print(f"  Due in: {due_in} mins | Delay: {delay_str}")
                        print(f"  Destination: {destination}")
                        print(f"  Status/Location: {last_loc}")
                        print("-" * 40)

                if train_count == 0:
                    print("No upcoming trains found in the next 90 mins.")

            else:
                print(f"HTTP Error: {res.status_code}")
                if hasattr(res, "close"):
                    res.close()
                elif hasattr(res, "socket"):
                    res.socket.close()

        except Exception as e:
            print("API Error:", e)

    gc.collect()
    return next_train_south, next_train_north  # return lowest time for north/south if it is within the bounds for each, return direction too??


# --- HELPER 1: Register or Update API Schedule Data ---
def update_schedule_from_api(train_code, origin, destination, direction, scheduled_time, due_in, late_mins):
    """
    Called in STATE_API_POLL whenever new API data arrives.
    If the train isn't in train_tracker yet, it adds it.
    """
    if train_code not in train_tracker:
        train_tracker[train_code] = {
            "scheduled_time": scheduled_time,  # e.g., "14:15"
            "api_due_mins": due_in,
            "api_delay_mins": late_mins,
            "origin": origin,
            "destination": destination,
            "direction": direction,
            "camera_detected": False,
            "camera_timestamp": None,
            "actual_delay_sec": None,
            "is_unscheduled": False
        }
    else:
        # Update live API estimates if the camera hasn't spotted it yet
        if not train_tracker[train_code]["camera_detected"]:
            train_tracker[train_code]["api_due_mins"] = due_in
            train_tracker[train_code]["api_delay_mins"] = late_mins


def find_matching_train_code(direction=None):
    """
    Searches train_tracker for an undetected scheduled train due within 5 mins.
    Returns the train_code string if found, otherwise returns None.
    """
    for code, data in train_tracker.items():
        if not data["camera_detected"] and not data["is_unscheduled"]:
            # Match if the train is due between 0 and 5 minutes from now
            if direction in data["direction"]:
                return code
    return None

# --- HELPER 3: Log Camera Detection Event ---
def record_camera_detection(counter,  state_direction, epoch_now_sec):
    """
    Called in STATE_INFER_LOG when motion is detected and image captured.
    Updates in-memory dict AND appends the record immediately to local storage.
    """
    train_code = find_matching_train_code(state_direction)

    if train_code:
        # Match found for scheduled train
        record = train_tracker[train_code]
        record["camera_detected"] = True
        record["camera_timestamp"] = counter  # e.g., "14:18:22"

        # Simple delay math: (Actual Pass Time) - (Scheduled API Time)
        # Assuming scheduled_time converted to epoch timestamp:
        # record["actual_delay_sec"] = epoch_now_sec - scheduled_epoch_sec

        print(f">> Linked camera event to scheduled train: {train_code}")

    else:
        # No API match -> Create unscheduled entry (e.g., freight/maintenance)
        train_code = f"UNSCHED_{counter}"
        record = {
            "scheduled_time": "N/A",
            "api_due_mins": None,
            "api_delay_mins": None,
            "origin": "Unknown",
            "destination": "Unknown",
            "direction": "Unknown",
            "camera_detected": True,
            "camera_timestamp": counter,
            "actual_delay_sec": None,
            "is_unscheduled": True
        }
        train_tracker[train_code] = record
        print(f">> Unscheduled train detected! Logged as: {train_code}")

def init_camera():
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.QVGA)  # 320x240
    sensor.set_auto_exposure(False, exposure_us=2000)
    sensor.skip_frames(time=2000)


def run_state_tick(now=None):
    """Executes a single step of the state machine."""
    global current_state, last_api_check, poll_interval, extra_bg_frame, global_counter, armed_state_start, state_direction

    next_train_due_south = INT_MAX
    next_train_due_north = INT_MAX

    if now is None:
        now = time.ticks_ms()

    # --- STATE 0: API Polling Loop ---
    if current_state == STATE_API_POLL:
        if (time.ticks_diff(now, last_api_check) >= poll_interval or last_api_check == 0):
            try:
                next_train_due_south, next_train_due_north = check_trains()
            except:
                connect_wifi()

            last_api_check = now

            if next_train_due_north <= 5 or next_train_due_south <= 3:
                if next_train_due_north <= 5:
                    state_direction = "North"
                elif next_train_due_south <= 3:
                    state_direction = "South"
                print(">> Train approaching! Arming camera motion watch...")
                if sensor:
                    extra_bg_frame = sensor.snapshot().copy()
                current_state = STATE_ARMED_WATCH
                armed_state_start = now
            elif next_train_due_north <= 10 or next_train_due_south <= 10:
                poll_interval = 120000
            else:
                poll_interval = 300000

    # --- STATE 1: Motion Watch ---
    elif current_state == STATE_ARMED_WATCH:
        img = sensor.snapshot()
        if extra_bg_frame is not None:
            diff_img = img.difference(extra_bg_frame)
            stats = diff_img.get_statistics(roi=TRACK_ROI)

            if stats.max > MOTION_THRESHOLD:
                print(">> Motion Detected! Capturing frame...")
                current_state = STATE_INFER_LOG

        extra_bg_frame.replace(img)

        if time.ticks_diff(now, armed_state_start) > 300000:
            extra_bg_frame = None
            gc.collect()
            current_state = STATE_API_POLL

    # --- STATE 2: Inference & Logging ---
    elif current_state == STATE_INFER_LOG:
        img = sensor.snapshot() # image of train
        print(">> Event logged. Cooling down...")
        extra_bg_frame = None
        gc.collect()

        poll_interval = 180000
        last_api_check = now
        record_camera_detection(last_api_check, state_direction, epoch_now_sec=time.time())
        global_counter += 1
        current_state = STATE_API_POLL
        state_direction = "Unknown"

    return current_state

if __name__ == "__main__":
    if connect_wifi():
        init_camera()
        while True:
            run_state_tick()
            time.sleep_ms(10)
