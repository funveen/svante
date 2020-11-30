# svante.py
# Named after Svante Arrhenius

# LIBRARIES --------------------------------------------------------------------

# load basic liberaries
from machine import Pin, PWM, I2C
import math
import time

# Neopixel to display different colour codes
import neopixel

# OLED module to display values
import ssd1306

# BME280 sensor to measure temperature,pressure and humidity
import bme280_float as bme280 #https://github.com/robert-hh/BME280

# SCD30 sensor to measure CO2 concentration
from scd30 import SCD30 #https://github.com/agners/micropython-scd30

# CONSTANTS & SETUP ------------------------------------------------------------

# CO2 Thresholds (ppm)
#
# Recommendation from REHVA (Federation of European Heating, Ventilation and Air Conditioning associations, rehva.eu)
# for preventing COVID-19 aerosol spread especially in schools:
# - warn: 800, critical: 1000
# (https://www.rehva.eu/fileadmin/user_upload/REHVA_COVID-19_guidance_document_V3_03082020.pdf)
#
# General air quality recommendation by the German Federal Environmental Agency (2008):
# - warn: 1000, critical: 2000
# (https://www.umweltbundesamt.de/sites/default/files/medien/pdfs/kohlendioxid_2008.pdf)

level_warn = 800
level_critical = 1000

# initialise modules and sensors
i2c = I2C(scl=Pin(5), sda=Pin(4)) # TODO: id required, e.g. -1

pixels = neopixel.NeoPixel(Pin(14, Pin.OUT), 1)
oled = ssd1306.SSD1306_I2C(64, 48, i2c)
bme = bme280.BME280(i2c=i2c)
scd30 = SCD30(i2c=i2c, addr=0x61)

# allow scd30 to initialize, so values are available
time.sleep_ms(2000)

# TODO:
# make sensor readings error-prone
# implement pressure assisted co2 calibration
# implement object oriented approach
# implement uasyncio for continuous updates
# test logging
# test webserver and interface


# MAIN IMPLEMENTATION ----------------------------------------------------------

def colour (c):
    if c == "g":
        pixels[0] = (0, 255, 0)
    elif c == "y":
        pixels[0] = (255, 200, 0)
    elif c == "r":
        pixels[0] = (255, 0, 0)
    else: # display blue
        pixels[0] = (0, 0 ,255)
    pixels.write()

co2 = (0,0,0)

def tph(sleep=2000):
    x = 41# unit position

    #while True:
    values = bme.read_compensated_data()
    try:
        co2 = scd30.read_measurement()
    except:
        print("Cannot read CO2 sensor")


    if co2[0] >= 1500:
        colour("r")
    elif co2[0] >= 1000:
        colour("y")
    else:
        colour("g")

    oled.fill(0)

    #oled.text("T", 0, 0)
    oled.text(str(round(values[0],1)), 0, 0)
    oled.pixel(x,0,1)
    oled.pixel(x+1,0,1)
    oled.pixel(x,1,1)
    oled.pixel(x+1,1,1)
    oled.text("C", x+3, 0)

    #oled.text("P", 0, 16)
    oled.text(str(round(values[1]/100)), 0, 12)
    oled.text("hPa", x, 12)

    #oled.text("H", 0, 32)
    oled.text(str(round(values[2],1)), 0, 24)
    oled.text("%", x, 24)

    if not math.isnan(co2[0]):
        oled.text(str(round(co2[0])), 0, 36)
    else:
        oled.text("---", 0, 36)

    oled.text("ppm", x, 36)

    oled.show()
    time.sleep_ms(sleep)

tph()
