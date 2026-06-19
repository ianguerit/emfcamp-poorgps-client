import network
import machine
import binascii
import urequests as requests
import ujson as json
import utime
from .BLEManager import BLEManager

API_ENDPOINT = "http://poorgps.emfcamp.illumo.dev/api/"

class Location:
    """
    Handles managing location
    """
    def __init__(self):
        self.available_sources = [
            "wifi", # Surrounding WiFi hotspots
            "gps_hexpansion", # GPS Hexpansion (todo)
            "ble_pwa" # BLE PWA app hosted at https://poorgps.emfcamp.illumo.dev/calibrate
        ]
        self.current_source = "wifi"
        self.current_state = "red" # amber or #green

        self.current_location = {
            "source": None,
            "latitude": None,
            "longitude": None,
            "accuracy": None,
            "updated_at": 0
        }
        self.local_villages = []

        # Used for identifying unique devices making requests
        self.device_id = "00:00:00:00:00:00"
        self.get_unique_device_id()

        self.ble_mgr = None

    def update_location(self):

        match self.current_source:
            case "wifi":
                # don't want to trigger this too frequently?
                networks = self.update_local_networks()
                self.update_wifi_location(networks)
            #case "gps_hexpansion":
            #    # Not yet implemented
            #    print("gps hexpansion not yet supported")
            #case "bluetooth_pwa":
            #    # triggered externally
            #    print("no action")


    def set_source(self, source):
        print("Changing source from "+self.current_source+" to "+source)
        self.current_state = "red"
        # actions to deactivate
        match self.current_source:
            #case "wifi":
            #    # Handled in update
            #case "gps_hexpansion":
            #    # Not yet implemented
            case "ble_pwa":
                self.ble_mgr = None

        self.current_source = source
        # do soemthing to update?

        # actions to activate
        match self.current_source:
            #case "wifi":
            #    # Handled in update
            #case "gps_hexpansion":
            #    # Not yet implemented
            case "ble_pwa":
                self.ble_mgr = BLEManager(name="Poor GPS", on_gps_received=self.handle_incoming_gps_data)


    def toggle_source(self):
        current_index = self.available_sources.index(self.current_source)
        next_index = (current_index + 1) % len(self.available_sources)
        self.set_source(self.available_sources[next_index])
        return self.current_source


    def update_local_networks(self):

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
                "bssid": self.format_bssid(item[1]),
                "rssi": item[3],
                "channel": item[2],
                "security": item[4],
                "hidden": bool(item[5])
            })

        # return found networks
        return networks_list
    
    def update_wifi_location(self, networks_list):

        # Construct the JSON payload containing both Wi-Fi and GPS coordinates
        payload = {
            "device_id": self.device_id,
            "total_aps_found": len(networks_list),
            "scanned_at_ms": utime.ticks_ms(),
            "networks": networks_list
        }
        
        if self.current_location["source"] in ("ble_pwa","gps_hexpansion"):
            # Check age of the latest GPS sync to evaluate coordinates relevancy
            gps_age = -1
            if self.current_location["updated_at"] > 0:
                gps_age = utime.time() - self.current_locatio["updated_at"]
            payload["gps"] = {
                "latitude": self.current_location["latitude"],
                "longitude": self.current_location["longitude"],
                "accuracy": self.current_location["accuracy"],
                "age_seconds": gps_age
            }

            api = API_ENDPOINT + "calibrate"

        else:
            api = API_ENDPOINT + "whereami"

        
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

                    print("Response:", res_json)
                    
                    status = res_json.get("status") # estimate, not-found
                    detail = res_json.get("detail") # human description

                    est_lat = res_json.get("lat")
                    est_lon = res_json.get("lon")
                    
                    if est_lat is not None and est_lon is not None:
                       
                        est_accuracy = res_json.get("accuracy")
                        
                        print("[Updating villages...]")
                        self.local_villages = res_json.get("local_villages")

                        if self.current_location["source"] == "wifi":
                            print("[Updating estimated location...]")
                            print("  Latitude : {}".format(est_lat))
                            print("  Longitude: {}".format(est_lon))
                            print("  Accuracy : ±{} meters".format(est_accuracy))
                            self.current_location["latitude"] = est_lat
                            self.current_location["longitude"] = est_lon
                            self.current_location["accuracy"] = est_accuracy
                            self.current_location["updated_at"] =  res_json.get("updated_at")

                            self.current_state = "amber"
                        
                    else:
                        print("[API Response Parser] No triangulated parameters mapped inside response JSON:")
                        
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

    def handle_ble_state_change(status):
        match status:
            case "connect":
                self.current_state = "amber"
            case "disconnect":
                self.current_state = "red"

    def handle_incoming_gps_data(raw_data):
        """
        Processes incoming BLE data. Handles either CSV or JSON coordinate uploads.
        """
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
                self.current_location = {
                    "source": "ble_pwa",
                    "latitude": lat,
                    "longitude": lon,
                    "accuracy": acc,
                    "updated_at": utime.time()
                }
                print("[GPS SYNC] Coords updated: Lat {}, Lon {}, Acc {}m".format(lat, lon, acc))

                self.current_state = "green"
                
                # Send confirmation back to Android/Chrome
                if self.ble_mgr:
                    self.ble_mgr.send_notification("ACK: {} , {}".format(lat, lon))
            else:
                print("[BLE] Payload parsing failed. Coordinates not parsed.")
                if self.ble_mgr:
                   self.ble_mgr.send_notification("ERR: Invalid format")
                    
        except Exception as e:
            print("[BLE RX Error] Exception processing data:", e)
            if self.ble_mgr:
                try:
                    self.ble_mgr.send_notification("ERR: {}".format(str(e)[:15]))
                except:
                    pass

    def connect_to_wifi(self):
        wlan = network.WLAN(network.STA_IF)

        if wlan.active():
            print("Resetting Wi-Fi radio state...")
            wlan.disconnect()
            wlan.active(False)
            utime.sleep_ms(500) # Crucial: gives the hardware chip time to power down

        # 2. Start a fresh, clean hardware session
        wlan.active(True)
        utime.sleep_ms(100)

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


    def format_bssid(bssid_bytes):
        return ":".join("{:02x}".format(b) for b in bssid_bytes)

    def get_unique_device_id(self):
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
            self.device_id = mac_formatted
        except Exception as e:
            # Fallback to machine unique ID if Wi-Fi stack isn't initialized yet
            print("[System API] Failed to extract Wi-Fi MAC, using Machine UUID instead:", e)
            if hasattr(machine, 'unique_id'):
                raw_id = machine.unique_id()
                self.device_id = binascii.hexlify(raw_id).decode('utf-8')
