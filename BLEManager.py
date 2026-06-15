import bluetooth
from micropython import const

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


class BLEManager:
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


