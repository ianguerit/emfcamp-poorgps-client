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
import math
import sys
import os
from .Location import Location
from .Avatar import draw_handle_avatar, generate_random_handle

# --- GLOBAL STATE ---

if sys.implementation.name == "micropython":
    apps = os.listdir("/apps")
    path = ""
    for a in apps:
        # This is important for apps deployed to the appstore
        # The Snake app from naomi stored at
        # https://github.com/npentrel/tildagon-snake/
        # has all its files in the folder
        # npentrel_tildagon_snake
        if a == "github_user_github_repo_name":
            path = "/apps/" + a
    ASSET_PATH = path + "/assets/"
else:
    # while testing, put your files in the folder you are developing in,
    # for example: example/streak.jpg
    ASSET_PATH = "apps/PoorGPS/"

# Menu options
#main_menu_items = ["Main", "Calibrate", "Debug"]

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
        self.show_help = True

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
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
        #    # The button_states do not update while you are in the background.
        #    # Calling clear() ensures the next time you open the app, it stays open.
        #    # Without it the app would close again immediately.
            self.button_states.clear()
            self.minimise()
        #self.menu.update(delta)
        if self.notification:
            self.notification.update(delta)
        if self.button_states.get(BUTTON_TYPES["RIGHT"]):
            self.button_states.clear()
            if self.show_help:
                self.show_help = False
            # switch to next location mode
            else:
                self.location.toggle_source()

    async def background_task(self):
        while True:
            await asyncio.sleep(5)
            self.location.update_location()

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
        if self.show_help:
            self.draw_help(ctx)
        else:
            self.draw_radar(ctx)
        #ctx.save()
        #ctx.rgb(0.2, 0, 0).rectangle(-120, -120, 240, 240).fill()
        #ctx.rgb(1, 0, 0).move_to(-80, 0).text("EMF PS")
        #ctx.restore()

    def draw_help(self, ctx):
        ctx.save()
        ctx.rgb(0, 0.03, 0.19).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(1, 1, 1);
        ctx.font = "Camp Font 1"

        ctx.font_size = 14
        x = ctx.text_width("TIME")
        ctx.move_to( (x / 2) * -1, -80)
        ctx.text("TIME")

        ctx.font_size = 16
        ctx.move_to(50, -55)
        ctx.text("MODE")

        ctx.font_size = 18
        x_lat = ctx.text_width("LATITUDE")
        ctx.move_to(x_lat * -1 - 5,-20)
        ctx.text("LATITUDE")
        ctx.move_to(5 ,-20)
        ctx.text("LONGITUDE")
        ctx.move_to(-3,-20)
        ctx.text(",")

        ctx.font_size = 16
        x = ctx.text_width("Accuracy")
        ctx.move_to( (x / 2) * -1, 0)
        ctx.text("Accuracy")
        x = ctx.text_width("Source")
        ctx.move_to( (x / 2) * -1, 20)
        ctx.text("Source")
        x = ctx.text_width("UPDATED")
        ctx.move_to( (x / 2) * -1, 40)
        ctx.text("UPDATED")

        ctx.restore()

    def draw_icon_gpshexpansion(self, ctx, x, y, size):
        """
        Draws a satellite icon inside a framing hexagon using ctx vector graphics.
        x, y: Center coordinates of the hexagon.
        size: The total diameter/width of the hexagon.
        color: A tuple of (R, G, B, A) for the lines.
        """
        ctx.save()
        ctx.translate(x, y)
        
        # Configure line styles
        ctx.line_width = max(2, size // 25)
        ctx.line_join = "round"
        ctx.line_cap = "round"
        
        # --- 1. DRAW THE FRAMING HEXAGON ---
        ctx.begin_path()
        for i in range(6):
            # 60 degrees per side, offset by 30 deg (math.pi / 6) to point a flat side up
            angle = (i * math.pi / 3) + (math.pi / 6)
            hx = (size / 2) * math.cos(angle)
            hy = (size / 2) * math.sin(angle)
            if i == 0:
                ctx.move_to(hx, hy)
            else:
                ctx.line_to(hx, hy)
        ctx.close_path()
        ctx.stroke()
        
        # --- 2. DRAW THE SATELLITE (Centered & Scaled) ---
        # Scale down the internal icon so it sits comfortably inside the hex bounds
        sat_scale = size * 0.4
        
        # Satellite Main Body (a simple diagonal rectangle/cylinder)
        ctx.begin_path()
        ctx.move_to(-sat_scale * 0.1, -sat_scale * 0.4)
        ctx.line_to( sat_scale * 0.4,  sat_scale * 0.1)
        ctx.line_to( sat_scale * 0.1,  sat_scale * 0.4)
        ctx.line_to(-sat_scale * 0.4, -sat_scale * 0.1)
        ctx.close_path()
        ctx.stroke()
        
        # Cross-boom / Solar Panel Array Axis
        ctx.begin_path()
        ctx.move_to(-sat_scale * 0.5,  sat_scale * 0.5)
        ctx.line_to( sat_scale * 0.5, -sat_scale * 0.5)
        ctx.stroke()
        
        # Solar Panel 1 (Top Right)
        ctx.begin_path()
        ctx.move_to(sat_scale * 0.3, -sat_scale * 0.5)
        ctx.line_to(sat_scale * 0.5, -sat_scale * 0.3)
        ctx.line_to(sat_scale * 0.7, -sat_scale * 0.5)
        ctx.line_to(sat_scale * 0.5, -sat_scale * 0.7)
        ctx.close_path()
        ctx.stroke()
        
        # Solar Panel 2 (Bottom Left)
        ctx.begin_path()
        ctx.move_to(-sat_scale * 0.3, sat_scale * 0.5)
        ctx.line_to(-sat_scale * 0.5, sat_scale * 0.3)
        ctx.line_to(-sat_scale * 0.7, sat_scale * 0.5)
        ctx.line_to(-sat_scale * 0.5, sat_scale * 0.7)
        ctx.close_path()
        ctx.stroke()
        
        # Dish / Antenna Transmitter (pointing down-right)
        ctx.begin_path()
        # The dish arc
        ctx.move_to(sat_scale * 0.1, sat_scale * 0.5)
        ctx.line_to(sat_scale * 0.5, sat_scale * 0.1)
        ctx.stroke()
        # The signal beam tip
        ctx.begin_path()
        ctx.move_to(sat_scale * 0.4, sat_scale * 0.4)
        ctx.line_to(sat_scale * 0.55, sat_scale * 0.55)
        ctx.stroke()
        
        ctx.restore()

    def draw_icon_bluetooth(self, ctx, x, y, size):
        """
        Draws a Bluetooth icon using the ctx vector canvas.
        x, y: Center coordinates for the icon.
        size: Total height of the icon.
        color: A tuple of (R, G, B, A) normalized between 0.0 and 1.0.
        """
        ctx.save()
        
        # Move the origin to the center of where we want to draw
        ctx.translate(x, y)
        
        # Calculate geometry relative to the total height (size)
        half_h = size / 2
        quarter_h = size / 4
        width = size / 4  # Side wing width
        
        # Configure stroke settings
        ctx.line_width = max(2, size // 15)
        ctx.line_join = "round"
        ctx.line_cap = "round"
        
        # Begin drawing the continuous Bluetooth path
        ctx.begin_path()
        
        # Start at top-left wing point, move to top spine, then bottom spine, etc.
        ctx.move_to(-width, -quarter_h)  # Top left wing
        ctx.line_to(width, quarter_h)    # Down to bottom right wing
        ctx.line_to(0, half_h)           # Up-left to bottom of spine
        ctx.line_to(0, -half_h)          # Straight up to top of spine
        ctx.line_to(width, -quarter_h)   # Down to top right wing
        ctx.line_to(-width, quarter_h)   # Down-left to bottom left wing
        
        ctx.stroke()
        ctx.restore()



    def draw_arrow(self,ctx, x, y, size=80, direction="right"):
        """
        Draws a left or right arrow inside a framing hexagon using ctx vector graphics.
        x, y: Center coordinates of the hexagon.
        size: The total diameter/width of the hexagon.
        direction: "right" or "left"
        color: A tuple of (R, G, B, A) for the lines.
        """
        ctx.save()
        ctx.translate(x, y)
        
        # Configure line styles
        ctx.line_width = max(2, size // 20)
        ctx.line_join = "round"
        ctx.line_cap = "round"
        
        # --- DRAW THE ARROW (CHEVRON) ---
        # Scale arrow bounds relative to hexagon size
        arrow_width = size * 0.18
        arrow_height = size * 0.25
        
        # Determine horizontal flip based on direction string
        # If "left", we multiply X coordinates by -1
        flip = -1 if direction.lower() == "left" else 1
        
        ctx.begin_path()
        # Start at top-left of the arrow, go to the point on the right, down to bottom-left
        ctx.move_to(-arrow_width * flip, -arrow_height)
        ctx.line_to(arrow_width * flip, 0)
        ctx.line_to(-arrow_width * flip, arrow_height)
        
        ctx.stroke()
        ctx.restore()


    def draw_radar(self, ctx):

        ctx.save()

        # Clear background
        ctx.rgb(0, 0.03, 0.19).rectangle(-120, -120, 240, 240).fill()

        ctx.rgb(0.5, 0.5, 0.5)
        # Minimise
        ctx.font = "Material Icons"
        ctx.font_size = 18
        ctx.move_to(-90, -55)
        ctx.text("\ue879") # Close

        ctx.rgb(1, 1, 1)
        ctx.font = "Camp Font 1"
        ctx.font_size = 14
        hour, minute, second = time.localtime()[3:6]
        timestamp = f"{hour:02d}:{minute:02d}:{second:02d}"
        x = ctx.text_width(timestamp)
        ctx.move_to( (x / 2) * -1, -80)
        ctx.text(timestamp)

        match self.location.current_state:
            case "red": # none
                ctx.rgb(0.96, 0.32, 0.37);
            case "amber": # low 
                ctx.rgb(0.97, 0.50, 0.01);
            case "yellow":
                ctx.rgb(0.98, 0.89, 0.00);
            case "green": # high
                ctx.rgb(0.16, 0.89, 0.55);
            case "blue":
                ctx.rgb(0.18, 0.68, 0.85);

        show_standard = True
        
        match self.location.current_source:
            case "wifi":
                ctx.font = "Material Icons"
                ctx.font_size = 18
                ctx.move_to(65, -55)
                ctx.text("\ue63e") # WiFi
            case "gps_hexpansion":
                #ctx.font = "Camp Font 1"
                #ctx.font_size = 16
                #ctx.move_to(65, -55)
                self.draw_icon_gpshexpansion(ctx, 75, -65, 20)
                #ctx.text("GPS") # satelite
                #ctx.text("\eb3a") # satelite
            case "ble_pwa":
                #ctx.font = "Camp Font 1"
                #ctx.font_size = 16
                #ctx.move_to(65, -55)
                self.draw_icon_bluetooth(ctx, 75, -65, 20)
                if self.location.current_state == "green":
                    #ctx.text("BLE") # BLE connected
                    #ctx.text("\e1a8") # BLE connected
                    print("show connected")
                else:
                    #ctx.text("BLE")
                    # Actual image is 162x162, but this doesn't fit 
                    ctx.image(ASSET_PATH + "qrcode.png", -60, -60, 120, 120)
                    show_standard = False
                    #ctx.text("\e1aa") # BLE connecting

        ctx.font = "Camp Font 1"

        ctx.rgb(0.5, 0.5, 0.5)

        lat = " - "
        lng = " - "
        accuracy = ""
        source = " - "
        updated_at = ""
        
        if self.location.current_location["latitude"] is not None:
            lat = self.location.current_location["latitude"]
            lng = self.location.current_location["longitude"]
            accuracy = "±" + self.location.current_location["accuracy"]+"m"
            source = self.location.current_location["source"]
            time_tuple = time.localtime(self.location.current_location["updated_at"])
            hour, minute, second = time_tuple[3:6]
            formatted_time = f"{hour:02d}:{minute:02d}:{second:02d}"
            updated_at = formatted_time
            ctx.rgb(1, 1, 1)

        if show_standard:
            ctx.font_size = 18
            x_lat = ctx.text_width(lat)
            ctx.move_to(x_lat * -1 - 5,-20)
            ctx.text(lat)
            ctx.move_to(5,-20)
            ctx.text(lng)
            ctx.move_to(-3,-20)
            ctx.text(",")

            ctx.font_size = 16
            x = ctx.text_width(accuracy)
            ctx.move_to( (x / 2) * -1, 0)
            ctx.text(accuracy)
            x = ctx.text_width(source)
            ctx.move_to( (x / 2) * -1, 20)
            ctx.text(source)
            x = ctx.text_width(updated_at)
            ctx.move_to( (x / 2) * -1, 40)
            ctx.text(updated_at)

            ctx.rgb(0.5, 0.5, 0.5)

            self.draw_arrow(ctx, -80, 60, 30, "left")
            self.draw_arrow(ctx, 80, 60, 30, "right")

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
