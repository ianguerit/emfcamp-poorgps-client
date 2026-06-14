# Poor GPS (client / app)
Pairs with the proof of concept server

Overall this is currently proof of concept (working on app seperately and I don't yet have a badge).

Tested test.py as working with an ESP32-S3.

Be sure to update the variables at the top of the file

Update the main network details to match a working network `WIFI_SSID` and `WIFI_PASSWORD`.

This will pull from badge settings.

`API_ENDPOINT` currently points at my server - you are welcome to use, but note data may be cleared.

Once you have it loaded / running, you can connect to BLE with the companion web page https://emfcamp.illumo.dev/scanner to help with calibration (combine your mobile GPS with the data collected to provide a baseline).
