import network
import urequests as requests
import ujson as json
import utime
import ubinascii
import machine
import bluetooth
from micropython import const

# --- CONFIGURATION SETTINGS ---
WIFI_SSID = "Add SSID here"
WIFI_PASSWORD = "Add Passphrase here"
API_ENDPOINT = "http://emfcamp.illumo.dev/api/"
SCAN_INTERVAL_SECONDS = 60

# --- GLOBAL STATE ---
# Stores the latest incoming GPS coordinates received from BLE
latest_gps = {
    "latitude": None,
    "longitude": None,
    "accuracy": None,
    "updated_at": 0
}

# --- BLE SYSTEM DEFINITIONS (Nordic UART Service - NUS) ---
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_FLAG_WRITE = const(0x0008)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_NOTIFY = const(0x0010)

_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX = (bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"), _FLAG_NOTIFY)
_UART_RX = (bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"), _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE)
_UART_SERVICE = (_UART_UUID, (_UART_TX, _UART_RX))

def get_unique_device_id():
    """
    Retrieves the local ESP32 Wi-Fi interface's MAC address and formats it
    into a standardized, unique lowercase string: "xx:xx:xx:xx:xx:xx".
    """
    try:
        # Create a temporary WLAN instance to query the MAC address
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        raw_mac = wlan.config("mac")
        
        # Convert binary bytes (e.g. b'$\xecJ\x01\xbc\xdf') to hexadecimal formatted string
        mac_formatted = ":".join("{:02x}".format(b) for b in raw_mac)
        return mac_formatted
    except Exception as e:
        # Fallback to machine unique ID if Wi-Fi stack isn't initialized yet
        print("[System API] Failed to extract Wi-Fi MAC, using Machine UUID instead:", e)
        raw_id = machine.unique_id()
        return ubinascii.hexlify(raw_id).decode('utf-8')

def advertising_payload(name=None, services=None, show_flags=True):
    """
    Builds a standard BLE advertising payload without external dependency helper files.
    Provides optional flags setting to allow splitting packets into scan responses.
    """
    payload = bytearray()

    def append(adv_type, value):
        payload.append(len(value) + 1)
        payload.append(adv_type)
        payload.extend(value)

    if show_flags:
        # Flags (General Discoverable Mode, BR/EDR Not Supported)
        append(0x01, b"\x06")

    # Complete 128-bit Service UUIDs (Reversed to match standard BLE endianness)
    if services:
        for uuid in services:
            b = bytes(uuid)
            if len(b) == 16:
                append(0x07, bytes(reversed(b)))

    # Complete Local Name
    if name:
        append(0x09, name.encode("utf-8"))

    return payload


class ESP32BLEManager:
    """
    Handles BLE Peripheral startup, connection monitoring, and reception callbacks.
    """
    def __init__(self, name="ESP32-S3-Scanner", on_gps_received=None):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)
        
        # Register standard Nordic UART Service
        ((self._tx_handle, self._rx_handle),) = self._ble.gatts_register_services((_UART_SERVICE,))
        
        # Expand buffer size to hold full string payload and enable append mode
        self._ble.gatts_set_buffer(self._rx_handle, 100, True)
        
        self._connections = set()
        self._on_gps_received = on_gps_received
        self._name = name
        
        # Split advertising data to prevent exceeding the 31-byte legacy limit
        self._payload = advertising_payload(services=[_UART_UUID], show_flags=True)
        self._scan_resp = advertising_payload(name=self._name, show_flags=False)
        self.advertise()

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            print("\n[BLE] Client connected (Handle: {})".format(conn_handle))
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            print("\n[BLE] Client disconnected. Restarting advertising...")
            if conn_handle in self._connections:
                self._connections.remove(conn_handle)
            self.advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self._rx_handle:
                raw_value = self._ble.gatts_read(self._rx_handle)
                if self._on_gps_received:
                    self._on_gps_received(raw_value)

    def advertise(self):
        print("[BLE] Advertising as '{}'...".format(self._name))
        # Advertise every 100ms passing both the primary payload and the scan response
        self._ble.gap_advertise(100000, adv_data=self._payload, resp_data=self._scan_resp)

    def send_notification(self, msg):
        """Sends a response string back to the Web Bluetooth app."""
        for conn_handle in self._connections:
            try:
                self._ble.gatts_notify(conn_handle, self._tx_handle, msg)
            except Exception as e:
                print("[BLE] Send failed:", e)


# Global instance reference for the callback to respond to
ble_mgr = None
# Dynamically loaded on startup to act as unique identifier
DEVICE_ID = "00:00:00:00:00:00"

def handle_incoming_gps_data(raw_data):
    """
    Processes incoming BLE data. Handles either CSV or JSON coordinate uploads.
    """
    global latest_gps, ble_mgr
    try:
        data_str = raw_data.decode("utf-8").strip()
        print("\n[BLE RX] Incoming Payload:", data_str)
        
        lat, lon, acc = None, None, None
        
        # 1. Attempt to parse JSON
        if data_str.startswith("{"):
            try:
                parsed = json.loads(data_str)
                lat = float(parsed.get("lat") or parsed.get("latitude"))
                lon = float(parsed.get("lon") or parsed.get("lng") or parsed.get("longitude"))
                acc = float(parsed.get("acc") or parsed.get("accuracy") or 0.0)
            except Exception as je:
                print("[BLE] Parsing payload as JSON failed, attempting CSV...", je)
        
        # 2. Fallback to parsing CSV: "lat,lon,accuracy"
        if lat is None or lon is None:
            parts = data_str.split(",")
            if len(parts) >= 2:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                acc = float(parts[2].strip()) if len(parts) >= 3 else 0.0

        if lat is not None and lon is not None:
            latest_gps = {
                "latitude": lat,
                "longitude": lon,
                "accuracy": acc,
                "updated_at": utime.time()
            }
            print("[GPS SYNC] Coords updated: Lat {}, Lon {}, Acc {}m".format(lat, lon, acc))
            
            # Send confirmation back to Android/Chrome
            if ble_mgr:
                ble_mgr.send_notification("ACK: {} , {}".format(lat, lon))
        else:
            print("[BLE] Payload parsing failed. Coordinates not parsed.")
            if ble_mgr:
                ble_mgr.send_notification("ERR: Invalid format")
                
    except Exception as e:
        print("[BLE RX Error] Exception processing data:", e)
        if ble_mgr:
            try:
                ble_mgr.send_notification("ERR: {}".format(str(e)[:15]))
            except:
                pass


# --- STANDARD OPERATIONS & WI-FI FUNCTIONALITIES ---
def format_bssid(bssid_bytes):
    return ":".join("{:02x}".format(b) for b in bssid_bytes)


def connect_to_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("Connecting to Wi-Fi: {}...".format(WIFI_SSID))
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        attempt = 0
        while not wlan.isconnected() and attempt < 15:
            utime.sleep(1)
            attempt += 1
            print(".", end="")
        print("")
        
    if wlan.isconnected():
        print("Connected! IP Info:", wlan.ifconfig())
        return wlan
    else:
        print("Failed to establish Wi-Fi uplink.")
        return None


def scan_and_post(wlan):
    if not wlan or not wlan.isconnected():
        print("Cannot scan, Wi-Fi disconnected.")
        return False
        
    print("Initiating local Wi-Fi environmental scan...")
    try:
        scan_results = wlan.scan()
    except Exception as e:
        print("Error during hardware scan:", e)
        return False

    networks_list = []
    for item in scan_results:
        try:
            ssid = item[0].decode("utf-8")
        except UnicodeError:
            ssid = str(item[0])
            
        networks_list.append({
            "ssid": ssid,
            "bssid": format_bssid(item[1]),
            "rssi": item[3],
            "channel": item[2],
            "security": item[4],
            "hidden": bool(item[5])
        })
        
    # Check age of the latest GPS sync to evaluate coordinates relevancy
    gps_age = -1
    if latest_gps["updated_at"] > 0:
        gps_age = utime.time() - latest_gps["updated_at"]

    # Construct the JSON payload containing both Wi-Fi and GPS coordinates
    payload = {
        "device_id": DEVICE_ID,
        "total_aps_found": len(networks_list),
        "scanned_at_ms": utime.ticks_ms(),
        "networks": networks_list,
        "gps": {
            "latitude": latest_gps["latitude"],
            "longitude": latest_gps["longitude"],
            "accuracy": latest_gps["accuracy"],
            "age_seconds": gps_age
        }
    }
    
    api = API_ENDPOINT + "calibrate"
    # whereami to get location
    
    print("Posting payload to {}...".format(api))
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(api, json=payload, headers=headers)
        
        print("API Response Status Code:", response.status_code)
        
        # Parse the JSON response to look for triangulated coordinates
        if response.status_code in (200, 201):
            try:
                try:
                    res_json = response.json()
                except:
                    res_json = json.loads(response.text)
                
                est_lat = (res_json.get("lat") or 
                           res_json.get("latitude") or 
                           res_json.get("estimated_lat") or 
                           res_json.get("estimated_latitude"))
                           
                est_lon = (res_json.get("lon") or 
                           res_json.get("longitude") or 
                           res_json.get("lng") or 
                           res_json.get("estimated_lon") or 
                           res_json.get("estimated_longitude") or 
                           res_json.get("estimated_lng") or
                           res_json.get("long"))
                
                if est_lat is not None and est_lon is not None:
                    print("\n" + "="*50)
                    print("[WIFI TRIANGULATION GEOLOCATION RECOVERY]")
                    print("  Estimated Latitude : {}".format(est_lat))
                    print("  Estimated Longitude: {}".format(est_lon))
                    
                    est_accuracy = res_json.get("accuracy") or res_json.get("precision")
                    if est_accuracy is not None:
                        print("  Estimation Margin  : ±{} meters".format(est_accuracy))
                    print("="*50 + "\n")
                else:
                    print("[API Response Parser] No triangulated parameters mapped inside response JSON:")
                    print("  Raw Data:", res_json)
                    
            except Exception as parse_error:
                print("[API Response Parser] Failed parsing payload content:", parse_error)
                try:
                    print("  Raw Text Payload:", response.text)
                except:
                    pass
        else:
            print("[API Warn] Endpoint returned non-success response code.")
            
        response.close()
        return True
    except Exception as e:
        print("Failed to post data to API. Error:", e)
        return False

def main():
    global ble_mgr, DEVICE_ID
    print("Starting Freenove ESP32-S3 BLE & Wardriving Agent...")

    # 1. Fetch hardware network interface MAC Address to establish DEVICE_ID uniqueness
    DEVICE_ID = get_unique_device_id()
    print("[SYSTEM] Unique Device Identifier Locked: {}".format(DEVICE_ID))

    # Start the BLE Peripheral Server first (Clients can connect even during Wi-Fi setup)
    ble_mgr = ESP32BLEManager(name="ESP32-S3-Scanner", on_gps_received=handle_incoming_gps_data)
    
    # Establish Wi-Fi Connection
    wlan = connect_to_wifi()
    
    while True:
        if wlan is None or not wlan.isconnected():
            print("Uplink down. Attempting reconnection...")
            wlan = connect_to_wifi()
            
        if wlan and wlan.isconnected():
            success = scan_and_post(wlan)
        else:
            print("Skipping scan cycle: Hardware network is offline.")
            
        print("Sleeping for {} seconds...".format(SCAN_INTERVAL_SECONDS))
        utime.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

