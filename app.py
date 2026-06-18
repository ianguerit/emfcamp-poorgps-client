# This is likely not yet working

import app

from events.input import Buttons, BUTTON_TYPES
from app_components import Menu, Notification, clear_background
from tildagonos import tildagonos, led_colours
import wifi
import network
import math
import binascii
import urequests as requests
import json
import time
from .Location import Location
from .Avatar import draw_handle_avatar, generate_random_handle

# --- GLOBAL STATE ---

# Menu options
#main_menu_items = ["Main", "Calibrate", "Debug"]
location_modes = ["wifi_hotspot", "wifi_scan", "gps_hexpansion", "bluetooth"]

class PoorGPS(app.App):
    
    def __init__(self):
        self.button_states = Buttons(self)
        #self.menu = Menu(
        #    self,
        #    main_menu_items,
        #    select_handler=self.select_handler,
        #    back_handler=self.back_handler,
        #)
        #self.current_screen = "menu";
        self.notification = None
        self.get_mac();
        self.my_handle = generate_random_handle()
        self.my_peers = [
            {"handle": "Gamer101",   "x": -60, "y": -40},
            {"handle": "EctoCooler", "x": 50,  "y": -50},
            {"handle": "CodeWiz",    "x": -20, "y": 60},
        ]
        self.location = Location()

    #def select_handler(self, item, idx):
    #    self.notification = Notification('' + item + '')
    #    match item:
    #        case "Map":
    #            self.current_screen = "main"
    #        case "Calibrate":
    #            self.current_screen = "calibrate"
    #        case "Debug":
    #            self.current_screen = "debug"

    #def back_handler(self):
    #    match self.current_screen:
    #        case "menu":
    #            self.minimise()
    #        case _:
    #            self.current_screen = "menu"

    def update(self, delta):
        # Every 0.05 seconds
        #if self.button_states.get(BUTTON_TYPES["CANCEL"]):
        #    # The button_states do not update while you are in the background.
        #    # Calling clear() ensures the next time you open the app, it stays open.
        #    # Without it the app would close again immediately.
        #    self.button_states.clear()
        #    self.minimise()
        #self.menu.update(delta)
        if self.notification:
            self.notification.update(delta)
        if self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.button_states.clear()
            # switch to next location mode
            self.location.toggle_source()

    #def background_update
    # Every 0.05 seconds

    def draw(self, ctx):
        clear_background(ctx)
        if self.notification:
            self.notification.draw(ctx)

        # match self.current_screen:
        #     case "map":
        #         self.draw_menu(ctx)
        #     case "calibrate":
        #         self.draw_calibrate(ctx)
        #     case "debug":
        #         self.draw_debug(ctx)
        #     case _:
        #         self.draw_radar(ctx)
        self.draw_radar(ctx)
        #ctx.save()
        #ctx.rgb(0.2, 0, 0).rectangle(-120, -120, 240, 240).fill()
        #ctx.rgb(1, 0, 0).move_to(-80, 0).text("EMF PS")
        #ctx.restore()



    def draw_radar(self, ctx):

        ctx.save()

        match self.location.current_state:
            case "red": # none
                ctx.rgb(1, 0, 0);
            case "amber": # low 
                ctx.rgb(1, 0.8, 0);
            case "green": # high
                ctx.rgb(0, 1, 0);

        ctx.font_size = 12
        ctx.font = "Material Icons"
        ctx.move_to(70, -70)
        match self.location.current_source:
            case "wifi":
                ctx.text("\ue63e") # WiFi
            case "gps_hexpansion":
                ctx.text("\eb3a") # satelite
            case "ble_pwa":
                if self.location.current_state == "green":
                    ctx.text("\e1a8") # BLE connected
                else:
                    ctx.text("\e1aa") # BLE connecting

        ctx.font = "Camp Font 1"
        ctx.font_size = 12
        
        if self.location.current_location["latitude"] is not None:
            ctx.move_to(-80,-20)
            ctx.text(self.location.current_location["latitude"])
            ctx.move_to(-80, 0)
            ctx.text(self.location.current_location["longitude"])
            ctx.move_to(-80, 20)
            ctx.text(self.location.current_location["accuracy"])
            ctx.move_to(-80, 40)
            ctx.text(self.location.current_location["source"])
            ctx.move_to(-80, 60)
            ctx.text(self.location.current_location["updated_at"])
        
                
        ctx.restore()


    # Stats
    # Show all wifi by signal strength
    def draw_debug(self, ctx):
        clear_background(ctx)

        # Draw a subtle background radar boundary
        ctx.rgba(0.1, 0.1, 0.15, 1.0)
        ctx.arc(0, 0, 115, 0, 2 * math.pi, True)
        ctx.fill()

        # 1. Draw your own custom handle avatar right in the center
        ctx.save()
        draw_handle_avatar(ctx, self.my_handle, size=25)
        ctx.restore()

        # 2. Loop through and draw everyone else nearby
        for peer in self.my_peers:
            ctx.save()
            ctx.translate(peer["x"], peer["y"])

            # Draw their procedural avatar
            draw_handle_avatar(ctx, peer["handle"], size=20)

            # Print their handle text directly under their avatar
            ctx.rgb(0.8, 0.8, 0.8)
            # Center the text slightly relative to its size
            # ctx.text(peer["handle"], -20, 30)

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
