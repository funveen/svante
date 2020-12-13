# svante.py
# Named after Svante Arrhenius

# LIBRARIES --------------------------------------------------------------------

print('loading Svante...')

from machine import Pin, PWM, I2C
import math
import time
import uasyncio as asyncio
import tinyweb

# TODO:
# make sensor readings error-prone
# implement pressure assisted co2 calibration
# make webserver and sensor readings asynchronous
# test logging


# CONSTANTS & SETUP ------------------------------------------------------------

# CO2 Thresholds (ppm).
#
# Recommendation from REHVA (Federation of European Heating, Ventilation and Air Conditioning associations, rehva.eu)
# for preventing COVID-19 aerosol spread especially in schools:
# - warn: 800, critical: 1000
# (https://www.rehva.eu/fileadmin/user_upload/REHVA_COVID-19_guidance_document_V3_03082020.pdf)
#
# General air quality recommendation by the German Federal Environmental Agency (2008):
# - warn: 1000, critical: 2000
# (https://www.umweltbundesamt.de/sites/default/files/medien/pdfs/kohlendioxid_2008.pdf)
#
WARN_LEVEL = 800
CRITICAL_LEVEL = 1000


# MODULES IMPLEMENTATION ---------------------------------------------------

class LED:
    def __init__ (self, pin=14):
        # Neopixel to display different colour codes
        import neopixel
        self.pixels = neopixel.NeoPixel(Pin(pin, Pin.OUT), 1)
        self._rgb = (0, 0, 0)
        self._h = 0.5 # between 0 and 1
        self.set()

    def set(self):
        self.pixels[0] = (int(round(self._rgb[0] * self._h)),
                          int(round(self._rgb[1] * self._h)),
                          int(round(self._rgb[2] * self._h)))
        self.pixels.write()

    @property
    def brightness(self):
        return self._h

    @brightness.setter
    def brightness(self, h):
        if h >= 0 and h <=1 and isinstance(h, float):
            self._h = h
            self.set()
        else:
            print("Only brightness values between 0 and 1")

    def red (self):
        self._rgb = (255,0,0)
        self.set()

    def yellow (self):
        self._rgb = (255,200,0)
        self.set()

    def green (self):
        self._rgb = (0,255,0)
        self.set()

    def blue (self):
        self._rgb = (0,0,255)
        self.set()

    def white (self):
        self._rgb = (255,255,255)
        self.set()

    def off (self):
        self._rgb = (0,0,0)
        self.set()

class Display:
    def __init__ (self, i2c, width=64, height=48):
        # OLED module to display values
        import ssd1306
        self.oled = ssd1306.SSD1306_I2C(width, height, i2c)
        self.clear()

    def clear (self):
        self.oled.fill(0)
        self.oled.show()

    def startup (self):
        self.oled.fill(0)
        self.oled.text('Init...', 5, 19)
        self.oled.show()

    def tphco2 (self, temp, pres, humi, co2c, x=41):
        # pressure to be provided in Pascal, displayed in hPa
        # x: horizontal unit position
        self.oled.fill(0)

        self.oled.text(str(round(temp,1)), 0, 0)
        self.oled.pixel(x,0,1)
        self.oled.pixel(x+1,0,1)
        self.oled.pixel(x,1,1)
        self.oled.pixel(x+1,1,1)
        self.oled.text("C", x+3, 0)

        self.oled.text(str(round(pres/100)), 0, 12)
        self.oled.text("hPa", x, 12)

        self.oled.text(str(round(humi,1)), 0, 24)
        self.oled.text("%", x, 24)

        if not math.isnan(co2c):
            self.oled.text(str(round(co2c)), 0, 36)
        else:
            self.oled.text("---", 0, 36)
        self.oled.text("ppm", x, 36)
        try:
            self.oled.show()
        except:
            print('Cannot update display.')
            #  File "ssd1306.py", line 95, in show
            #  File "ssd1306.py", line 115, in write_cmd
            #  OSError: [Errno 19] ENODEV

class Sensor:
    def __init__ (self, i2c):
        print('initialising sensors...')
        # BME280 sensor to measure temperature,pressure and humidity
        from bme280_float import BME280 #https://github.com/robert-hh/BME280
        # SCD30 sensor to measure CO2 concentration
        from scd30 import SCD30 #https://github.com/agners/micropython-scd30
        self.bme = BME280(i2c=i2c)
        self.scd30 = SCD30(i2c=i2c, addr=0x61)
        self.temp = 0
        self.pres = 0
        self.humi = 0
        self.co2c = 0
        self.temp2 = 0
        self.humi2 = 0
        # allow BME280 to initialize, so values are available
        time.sleep_ms(2000)
        self.read()
        # set ambient pressure calibration to SCD30 (to be set in mbar or hPa)
        try:
            self.scd30.start_continous_measurement(ambient_pressure=round(self.pres/100))
        except:
            print('Cannot set ambient pressure to SCD30')
        # allow SCD30 to initialize, so values are available
        while self.scd30.get_status_ready() == 0:
            time.sleep_ms(100)
        print('scd30 ready')

    def read (self):
        self.temp, self.pres, self.humi = self.bme.read_compensated_data()
        try:
            self.co2c, self.temp2, self.humi2 = self.scd30.read_measurement()
        except:
            print("Cannot read CO2 sensor")

    def get_values (self):
        return self.temp, self.pres, self.humi, self.co2c

    def print_values (self):
        print(self.temp, " C")
        print(self.pres/100, " hPa")
        print(self.humi, " %")
        print(self.co2c, " ppm")
        print(self.temp2, " C")
        print(self.humi2, " %")

class WebServer:
    def __init__ (self, led, display, sensor, host='0.0.0.0', port=80, timeout=5):
        self.led = led
        self.display = display
        self.sensor = sensor
        self.host = host
        self.port = port
        self.timeout = timeout
        self.app = tinyweb.webserver(request_timeout=self.timeout)

    async def index (self, request, response):
        # Start HTTP response with content-type text/html
        await response.start_html()
        # Send actual HTML page
        page = self.get_page()
        await response.send(page)

    def run (self):
        self.app.add_route('/', self.index)
        self.app.run(host=self.host, port=self.port) #loop_forever=False

    def get_page(self):
        if not math.isnan(self.sensor.co2c):
            co2c = str(round(self.sensor.co2c))
        else:
            co2c = "---"
        html = """
        <html><head><title>Svante Web Interface</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="icon" href="data:,">
        <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
        h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none;
        border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
        .button2{background-color: #4286f4;}</style>
        </head><body>
        <h1>Svante Web Interface</h1>
        <p>Temperature: <strong>""" + str(round(self.sensor.temp,1)) + """ (""" + str(round(self.sensor.temp2,1)) + """)</strong> &#176;C</p>
        <p>Pressure: <strong>""" + str(round(self.sensor.pres/100)) + """</strong> hPa</p>
        <p>Humidity: <strong>""" + str(round(self.sensor.humi,1)) + """ (""" + str(round(self.sensor.humi2,1)) + """)</strong> &#37;</p>
        <p>CO<sub>2</sub> concentraion: <strong>""" + co2c + """</strong> ppm</p>
        <p><a href="/?read"><button class="button">READ</button></a></p>
        </body></html>\n"""
        return html


# MAIN IMPLEMENTATION ----------------------------------------------------------

# initialise modules and sensors
i2c = I2C(scl=Pin(5), sda=Pin(4)) # TODO: id required, e.g. -1
display = Display(i2c)
display.startup()
led = LED()
sensor = Sensor(i2c)
webserver = WebServer(led, display, sensor)

#TODO: move to class!!!
# seperate measurement into continuous sensor logging, display and led updating, define them as coros for asyncio!!!
async def measurement(sleep=5):
    while True:
        print('M')
        sensor.read()
        if sensor.co2c >= CRITICAL_LEVEL:
            led.red()
        elif sensor.co2c >= WARN_LEVEL:
            led.yellow()
        else:
            led.green()
        display.tphco2(sensor.temp, sensor.pres, sensor.humi, sensor.co2c)
        await asyncio.sleep(sleep)

asyncio.create_task(measurement())

async def shutdown():
    print('Shutdown is running.')  # Happens in both cases
    await asyncio.sleep(1)
    print('done')

try:
    webserver.run()
except KeyboardInterrupt: # is this even working?
    print('Keyboard interrupt at loop level.')
    asyncio.run(shutdown())
