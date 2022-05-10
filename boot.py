# This file is executed on every boot (including wake-boot from deepsleep)
print('Booting...')

#import uos
#uos.dupterm(None, 1) # disable REPL on UART(0)
from machine import Pin

# free up memory
import esp
esp.osdebug(None)
import gc
gc.collect()

#import webrepl
#webrepl.start()

import config

def ap_connect():
  # open access point
  ap = network.WLAN(network.AP_IF)
  ap.active(True)
  ap.config(essid=config.AP_SSID,
            authmode=network.AUTH_WPA_WPA2_PSK,
            password=config.AP_PASSWORD)

def wifi_connect():
    # connect to wifi network / station interface
    import network
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('Connecting to network...')
        sta_if.active(True)
        try:
            sta_if.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        except:
            print("Defined SSID not found.")
        while not sta_if.isconnected():
            pass
    print('Network config:', sta_if.ifconfig())

wifi_connect()
