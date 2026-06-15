# This is likely not yet working

import app

from events.input import Buttons, BUTTON_TYPES
from app_components import Menu, Notification, clear_background
from tildagonos import tildagonos, led_colours
import wifi
import network
import binascii
import urequests as requests
import json
import time
from BLEManager import BLEManager

# --- GLOBAL STATE ---

# Menu options
main_menu_items = ["Map", "Calibrate", "Debug"]

# Stores the latest incoming GPS coordinates received from BLE
latest_gps = {
    "latitude": None,
    "longitude": None,
    "accuracy": None,
    "updated_at": 0
}

# Global instance reference for the callback to respond to
ble_mgr = None
# Dynamically loaded on startup to act as unique identifier
DEVICE_ID = "00:00:00:00:00:00"

class PoorGPS(app.App):
    def __init__(self):
        self.button_states = Buttons(self)
        self.menu = Menu(
            self,
            main_menu_items,
            select_handler=self.select_handler,
            back_handler=self.back_handler,
        )
        self.current_screen = "menu";
        self.notification = None
        self.get_mac();

    def select_handler(self, item, idx):
        self.notification = Notification('' + item + '')
        match item:
            case "Map":
                self.current_screen = "map"
            case "Calibrate":
                self.current_screen = "calibrate"
            case "Debug":
                self.current_screen = "debug"

    def back_handler(self):
        match self.current_screen:
            case "menu":
                self.minimise()
            case _:
                self.current_screen = "menu"

    def update(self, delta):
        # Every 0.05 seconds
        #if self.button_states.get(BUTTON_TYPES["CANCEL"]):
        #    # The button_states do not update while you are in the background.
        #    # Calling clear() ensures the next time you open the app, it stays open.
        #    # Without it the app would close again immediately.
        #    self.button_states.clear()
        #    self.minimise()
        self.menu.update(delta)
        if self.notification:
            self.notification.update(delta)

    #def background_update
    # Every 0.05 seconds

    def draw(self, ctx):
        clear_background(ctx)
        if self.notification:
            self.notification.draw(ctx)

        match self.current_screen:
            case "map":
                self.draw_map(ctx)
            case "calibrate":
                self.draw_calibrate(ctx)
            case "debug":
                self.draw_debug(ctx)
            case _:
                self.menu.draw(ctx)
        
        #ctx.save()
        #ctx.rgb(0.2, 0, 0).rectangle(-120, -120, 240, 240).fill()
        #ctx.rgb(1, 0, 0).move_to(-80, 0).text("EMF PS")
        #ctx.restore()

    # Map
    # What formats is the map available in, how do we best draw this
    # What other info can we show
    def draw_map(self, ctx):
        ctx.save()
        ctx.rgb(0.2, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(1, 0, 0).move_to(-80, 0).text("MAP")
        ctx.restore()


    # Stats
    # Show all wifi by signal strength
    def draw_debug(self, ctx):
        ctx.save()
        ctx.rgb(0.2, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(1, 0, 0).move_to(-80, 0).text("DEBUG")
        ctx.restore()

    def get_mac(self):
        wlan_sta = network.WLAN(network.STA_IF)
        wlan_sta.active(True)

        wlan_mac = wlan_sta.config("mac")
        if wlan_mac:
            mac_str = binascii.hexlify(wlan_mac).decode()
            self.notification = Notification(f"MAC address: {mac_str}")
        else:
            self.notification = Notification(f"No WiFi")

    # Calibrate
    # Show QR code for website
    # Connect to a phone over BLE and exchange GPS data
    # Post GPS and signal / available WiFi to API
    # To help populate idea of where you are on the map
    def draw_calibrate(self, ctx):
        ctx.save()
        ctx.rgb(0.2, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(1, 0, 0).move_to(-80, 0).text("CALIBRATE")
        ctx.restore()
        

__app_export__ = PoorGPS
