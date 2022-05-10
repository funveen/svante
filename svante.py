# svante.py
# Named after Svante Arrhenius

# LIBRARIES --------------------------------------------------------------------

print('Loading Svante...')

from machine import Pin, PWM, I2C
import math
import time
import uasyncio as asyncio

# TODO:
# double check asyncio and shutdown
# optimise measurement/display intervals and adjust sensors accordingly for energy efficiency (consider average values in between intervals)
# addtraffic lights to web page
# use common config file for py and js
# add configuration to web pages (wifi, switch LED on/off, switch display on/off)


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

# How often a sensor reading is taken and processed (seconds)
MEASUREMENT_INTERVAL = 10
# How many sensor readings should be stored
MAX_SAMPLE_HISTORY = 20


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
        # x: horizontal unit position
        self.oled.fill(0)

        self.oled.text(str(temp), 0, 0)
        self.oled.pixel(x,0,1)
        self.oled.pixel(x+1,0,1)
        self.oled.pixel(x,1,1)
        self.oled.pixel(x+1,1,1)
        self.oled.text("C", x+3, 0)

        self.oled.text(str(pres), 0, 12)
        self.oled.text("hPa", x, 12)

        self.oled.text(str(humi), 0, 24)
        self.oled.text("%", x, 24)

        self.oled.text(str(co2c), 0, 36)
        self.oled.text("ppm", x, 36)
        try:
            self.oled.show()
        except:
            print('Cannot update display.')

class Readings:
    def __init__ (self, factor=1, *args):
        self._latest = 0 # separate value to avoid handling empty lists
        self._list = []
        self.factor = factor # optional factor to multiply new values
        self.args = args # potentially the number of digits for round(), as round(5.3,0) returns float, but round(5.3) returns int

    @property
    def value(self):
        return self._latest

    @value.setter
    def value (self, v):
        # evaluate and replace nan
        v = 0.0 if math.isnan(v) else v
        # round or convert according to init values for factor and optional digits
        v = round(v*self.factor,*self.args)
        self._latest = v
        self._list.append(v)
        if len(self._list) > MAX_SAMPLE_HISTORY:
            self._list.pop(0)

    @property
    def history (self):
        return self._list

class Sensor:
    def __init__ (self, i2c):
        print('Initialising sensors...')
        # BME280 sensor to measure temperature,pressure and humidity
        from bme280_float import BME280 #https://github.com/robert-hh/BME280
        # SCD30 sensor to measure CO2 concentration
        from scd30 import SCD30 #https://github.com/agners/micropython-scd30
        self.bme = BME280(i2c=i2c)
        self.scd30 = SCD30(i2c=i2c, addr=0x61)
        self.temp = Readings(1,1)
        self.pres = Readings(1/100) # convert from Pa to hPa, pass no rounding digits to get int
        self.humi = Readings(1,1)
        self.co2c = Readings(1) # pass no rounding digits to get int
        self.temp2 = Readings(1,1)
        self.humi2 = Readings(1,1)
        # allow BME280 to initialize, so values are available
        time.sleep_ms(2000)
        print('BME280 ready.')
        # set ambient pressure calibration to SCD30 (to be set in mbar or hPa)
        try:
            self.scd30.start_continous_measurement(ambient_pressure=round(self.bme.read_compensated_data()[1]/100))
        except:
            print('Cannot set ambient pressure to SCD30')
        # allow SCD30 to initialize, so values are available
        while self.scd30.get_status_ready() == 0:
            time.sleep_ms(100)
        print('SCD30 ready.')
        self.read()

    def read (self):
        try:
            self.temp.value, self.pres.value, self.humi.value = self.bme.read_compensated_data()
        except:
            print("Cannot read BME280.")
        try:
            self.co2c.value, self.temp2.value, self.humi2.value = self.scd30.read_measurement()
        except:
            print("Cannot read SCD30")

    def get_values (self):
        return self.temp.value, self.pres.value, self.humi.value, self.co2c.value

    def print_values (self):
        print(self.temp.value, " C")
        print(self.pres.value, " hPa")
        print(self.humi.value, " %")
        print(self.co2c.value, " ppm")
        print(self.temp2.value, " C")
        print(self.humi2.value, " %")

class WebServer:
    def __init__ (self, led, display, sensor, host='0.0.0.0', port=80, timeout=5):
        print('Starting webserver...')
        import tinyweb #https://github.com/belyalov/tinyweb
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

    async def charts (self, request, response):
        await response.send_file('html/charts.html')

    ### plain history values

    async def temperature (self, request, response):
        await response.start_html()
        await response.send(str(self.sensor.temp.history))

    async def pressure (self, request, response):
        await response.start_html()
        await response.send(str(self.sensor.pres.history))

    async def humidity (self, request, response):
        await response.start_html()
        await response.send(str(self.sensor.humi.history))

    async def co2concentration (self, request, response):
        await response.start_html()
        await response.send(str(self.sensor.co2c.history))

    def run (self):
        self.app.add_route('/', self.index)
        self.app.add_route('/charts', self.charts)

        self.app.add_route('/temperature', self.temperature)
        self.app.add_route('/pressure', self.pressure)
        self.app.add_route('/humidity', self.humidity)
        self.app.add_route('/co2concentration', self.co2concentration)

        self.app.run(host=self.host, port=self.port) #loop_forever=False

    def get_page(self):
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
        <p>Temperature: <strong>""" + str(self.sensor.temp.value) + """ (""" + str(self.sensor.temp2.value) + """)</strong> &#176;C</p>
        <p>Pressure: <strong>""" + str(self.sensor.pres.value) + """</strong> hPa</p>
        <p>Humidity: <strong>""" + str(self.sensor.humi.value) + """ (""" + str(self.sensor.humi2.value) + """)</strong> &#37;</p>
        <p>CO<sub>2</sub> concentraion: <strong>""" + str(self.sensor.co2c.value) + """</strong> ppm</p>
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
async def measurement(sleep):
    while True:
        print('Measurement!')
        sensor.read()
        if sensor.co2c.value >= CRITICAL_LEVEL:
            led.red()
        elif sensor.co2c.value >= WARN_LEVEL:
            led.yellow()
        else:
            led.green()
        display.tphco2(sensor.temp.value, sensor.pres.value, sensor.humi.value, sensor.co2c.value)
        await asyncio.sleep(sleep)

asyncio.create_task(measurement(sleep=MEASUREMENT_INTERVAL))

async def shutdown():
    print('Shutdown is running.')  # Happens in both cases
    await asyncio.sleep(1)
    print('done')

try:
    webserver.run()
except KeyboardInterrupt: # is this even working?
    print('Keyboard interrupt at loop level.')
    asyncio.run(shutdown())
