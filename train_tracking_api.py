import time
import network
import requests
import gc

# --- Configuration ---
WIFI_SSID = "Matthew's Hotspot"
WIFI_PASS = "yyq447ty746djia"

STATION_NAME = "Malahide"
API_URL = f"http://api.irishrail.ie/realtime/realtime.asmx/getStationDataByNameXML?StationDesc={STATION_NAME}"

# Helper function to extract text between XML tags without external XML libraries
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

# --- Connect to Wi-Fi ---
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

# --- Fetch & Parse Irish Rail API ---
# --- Fetch & Parse Irish Rail API ---
def check_trains():
    print(f"\n--- Checking Trains for {STATION_NAME} ---")

    next_train_mins = 999

    try:
        res = requests.get(API_URL)
        if res.status_code == 200:

            # 1. Safely handle both string and raw byte responses
            if hasattr(res, "text") and isinstance(res.text, str):
                xml_text = res.text
            elif hasattr(res, "content"):
                data = res.content
                xml_text = data.decode("utf-8") if isinstance(data, bytes) else str(data)
            else:
                xml_text = str(res)

            # 2. Safely close socket connection across different MicroPython request implementations
            if hasattr(res, "close"):
                res.close()
            elif hasattr(res, "socket"):
                res.socket.close()

            # --- Parse XML String ---
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
                    print(f"  Current Status/Location: {last_loc}")
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

    # Force garbage collection to keep socket and memory free
    gc.collect()

    return next_train_mins

# --- Main Dynamic Polling Loop ---
if connect_wifi():
    while True:
        shortest_wait = check_trains()

        if shortest_wait <= 10:
            poll_interval = 120  # 2 minutes
            print(">> Train approaching soon! Polling interval set to 2 minutes.")
        else:
            poll_interval = 300  # 5 minutes
            print(">> No imminent trains. Polling interval set to 5 minutes.")

        time.sleep(poll_interval)
