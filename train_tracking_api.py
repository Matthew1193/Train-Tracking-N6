import time
import network
import requests
import gc
import sensor

# --- Configuration ---
WIFI_SSID = "eir85227665"
WIFI_PASS = "xV2dSg9ruH"

STATION_NAME = "Donabate"
API_URL = f"http://api.irishrail.ie/realtime/realtime.asmx/getStationDataByNameXML?StationDesc={STATION_NAME}"

# State Definitions
STATE_API_POLL = 0
STATE_ARMED_WATCH = 1
STATE_INFER_LOG = 2

# Track ROI over train lines (x, y, w, h) - adjust for your frame view
TRACK_ROI = (100, 100, 120, 80)

# Motion Detection Sensitivity (Adjust based on ambient daylight/camera distance)
MOTION_THRESHOLD = 25

# --- Helper Functions ---
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
    print(f"\n--- Checking API Data for {STATION_NAME} ---")
    next_train_mins = 999

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

                due_in_raw = get_tag_value(block, "Duein", "999")
                due_in = int(due_in_raw) if due_in_raw.isdigit() else 999

                late_mins = get_tag_value(block, "Late", "0")
                last_loc = get_tag_value(block, "Lastlocation", "No location info")

                if "Belfast" in origin or "Belfast" in destination or train_type == "INTERCITY":
                    line_name = "Belfast Intercity"
                elif "Drogheda" in destination or "Dundalk" in destination:
                    line_name = "Drogheda/Dundalk Commuter"
                else:
                    line_name = f"Commuter/DART ({origin} -> {destination})"

                delay_str = "On Time" if late_mins == "0" else f"{late_mins} mins late"

                if due_in < next_train_mins:
                    next_train_mins = due_in

                if due_in < 10:
                    print(f"[{line_name}] Code: {train_code}")
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
    return next_train_mins

def init_camera():
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.QVGA)  # 320x240
    sensor.set_auto_exposure(False, exposure_us=2000)  # High shutter speed to freeze train motion
    sensor.skip_frames(time=2000)

# --- Initializing System ---
if connect_wifi():
    init_camera()

    current_state = STATE_API_POLL
    last_api_check = 0
    poll_interval = 300000  # Default 5 mins in ms
    next_train_due = 999
    extra_bg_frame = None   # Frame reference for optical motion detection

    while True:
        now = time.ticks_ms()

        # --- STATE 0: API Polling Loop ---
        if current_state == STATE_API_POLL:
            if time.ticks_diff(now, last_api_check) >= poll_interval or last_api_check == 0:
                next_train_due = check_trains()
                last_api_check = time.ticks_ms()

                if next_train_due <= 3:
                    print(">> Train in <= 3 mins! Arming camera motion watch...")
                    extra_bg_frame = sensor.snapshot().copy() # Grab baseline static frame
                    current_state = STATE_ARMED_WATCH
                elif next_train_due <= 10:
                    poll_interval = 120000  # Poll every 2 mins
                else:
                    poll_interval = 300000  # Poll every 5 mins

        # --- STATE 1: Motion Watch (Frame Differencing) ---
        elif current_state == STATE_ARMED_WATCH:
            img = sensor.snapshot()

            # Compute frame difference inside TRACK_ROI vs initial baseline frame
            diff_img = img.difference(extra_bg_frame)
            stats = diff_img.get_statistics(roi=TRACK_ROI)

            # If pixel change in ROI exceeds threshold, a train is passing!
            if stats.max()[0] > MOTION_THRESHOLD:
                print(">> Motion Detected in ROI! Capturing frame for classification...")
                current_state = STATE_INFER_LOG

            # Update baseline frame continuously to adapt to slow sunlight changes
            extra_bg_frame = img.copy()

        # --- STATE 2: Inference & Logging ---
        elif current_state == STATE_INFER_LOG:
            # Capture clean high-speed frame
            img = sensor.snapshot()

            # -------------------------------------------------------------
            # TODO:
            # 1. Run local quantized TFLite / Edge Impulse model on 'img'
            # 2. Extract classification class and confidence score
            # 3. Save snapshot to SD Card or HTTP POST payload to database
            # -------------------------------------------------------------

            print(">> Event logged successfully. Cooling down for 3 mins...")
            poll_interval = 180000  # Wait 3 mins for train to fully pass
            last_api_check = time.ticks_ms()
            current_state = STATE_API_POLL

        time.sleep_ms(10)  # CPU yield
