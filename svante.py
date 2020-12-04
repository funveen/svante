# svante.py
# Named after Svante Arrhenius

# LIBRARIES --------------------------------------------------------------------

print('loading Svante...')

from machine import Pin, PWM, I2C
import math
import time

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
        self.off()

    def colour (self, c):
        if c == "green":
            self.pixels[0] = (0,255,0)
        elif c == "yellow":
            self.pixels[0] = (255,200,0)
        elif c == "red":
            self.pixels[0] = (255,0,0)
        elif c == "blue":
            self.pixels[0] = (0,0,255)
        elif c == "white":
            self.pixels[0] = (255,255,255)
        else:
            pass
        self.pixels.write()
        self.status = True

    def red (self):
        self.pixels[0] = (255,0,0)
        self.pixels.write()
        self.status = True

    def yellow (self):
        self.pixels[0] = (255,200,0)
        self.pixels.write()
        self.status = True

    def green (self):
        self.pixels[0] = (0,255,0)
        self.pixels.write()
        self.status = True

    def blue (self):
        self.pixels[0] = (0,0,255)
        self.pixels.write()
        self.status = True

    def white (self):
        self.pixels[0] = (255,255,255)
        self.pixels.write()
        self.status = True

    def off (self):
        self.pixels[0] = (0,0,0)
        self.pixels.write()
        self.status = False

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
        self.oled.show()

class Sensor:
    def __init__ (self, i2c):
        print('initialising sensors...')
        # BME280 sensor to measure temperature,pressure and humidity
        from bme280_float import BME280 #https://github.com/robert-hh/BME280
        # SCD30 sensor to measure CO2 concentration
        from scd30 import SCD30 #https://github.com/agners/micropython-scd30
        self.bme = BME280(i2c=i2c)
        self.scd30 = SCD30(i2c=i2c, addr=0x61)
        # allow scd30 to initialize, so values are available
        time.sleep_ms(2000)
        self.temp = 0
        self.pres = 0
        self.humi = 0
        self.co2c = 0
        self.temp2 = 0
        self.humi2 = 0

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
    def __init__ (self, led, display, sensor, port=80):
        print('starting webserver...')
        try:
          import usocket as socket
        except:
          import socket
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(('', port))
        self.s.listen(5)
        self.led = led
        self.display = display
        self.sensor = sensor

    def get_page(self):
      html = """<html><head> <title>Svante Web Interface</title> <meta name="viewport" content="width=device-width, initial-scale=1">
      <link rel="icon" href="data:,"> <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
      h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none;
      border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
      .button2{background-color: #4286f4;}</style></head><body> <h1>Svante Web Interface</h1>
      <p>Temperature: <strong>""" + str(round(self.sensor.temp,1)) + """</strong> &#176;C</p>
      <p>Pressure: <strong>""" + str(round(self.sensor.pres/100)) + """</strong> hPa</p>
      <p>Humidity: <strong>""" + str(round(self.sensor.humi,1)) + """</strong> &#37;</p>
      <p>CO<sub>2</sub> concentraion: <strong>""" + str(round(self.sensor.co2c)) + """</strong> ppm</p>
      <p><a href="/?read"><button class="button">READ</button></a></p>
      </body></html>"""
      return html

    def run(self):
      conn, addr = self.s.accept()
      print('Got a connection from %s' % str(addr))
      request = conn.recv(1024)
      request = str(request)
      print('Content = %s' % request)
      read = request.find('/?read')
      if read == 6:
        print('LED ON')
        self.led.blue()
      response = self.get_page()
      conn.send('HTTP/1.1 200 OK\n')
      conn.send('Content-Type: text/html\n')
      conn.send('Connection: close\n\n')
      conn.sendall(response)
      conn.close()


# MAIN IMPLEMENTATION ----------------------------------------------------------

# initialise modules and sensors
i2c = I2C(scl=Pin(5), sda=Pin(4)) # TODO: id required, e.g. -1
led = LED()
display = Display(i2c)
display.startup()
sensor = Sensor(i2c)
webs = WebServer(led, display, sensor)

def run(sleep=2000):
    while True:
        sensor.read()

        # led
        if sensor.co2c >= CRITICAL_LEVEL:
            led.red()
        elif sensor.co2c >= WARN_LEVEL:
            led.yellow()
        else:
            led.green()

        # display
        display.tphco2(sensor.temp, sensor.pres, sensor.humi, sensor.co2c)
        webs.run()
        time.sleep_ms(sleep)

run()
