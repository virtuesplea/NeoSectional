from urllib.request import urlopen
import xml.etree.ElementTree as ET
import time
#from neopixel import *
import sys
import os
import forecastio

# DarkSky API Key
DARKSKY_API_KEY = ""

# time to sleep between refreshing the visibilty data and updating the LEDs
SLEEP_TIME      = 3600

# LED strip configuration
LED_COUNT       = 50    # number of LED pixels
LED_PIN         = 18    # GPIO pin connected to the pixels (18 uses PWM!)
#LED_PIN         = 10    # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ     = 10    # LED signal frequecy in hertz (usually 800khz)
LED_DMA         = 5     # DMA channel to use for generating signal (try 5)
LED_INVERT      = False # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL     = 0     # set to 1 for GPIOs 13, 19, 41, 45, or 53
#LED_STRIP       = ws.WS2811_STRIP_GRB   # strip type and colour ordering

# AWC (Aviation Weather Center) doesn't provide VFR/IFR forecasts for many of
#   the small airports we're interested in
#   so instead we're going to determine this manually using current visibility
#   provided by the Dark Sky API
# These variables can be changed in order to change the IFR/VFR calculation
# These are in miles
VFR_MIN     = 5
MVFR_MIN    = 3
IFR_MIN     = 1

# LED colors
LED_MODIFIER      = 1  # set to 0 for darkest and 255 for brighest
LED_CALC_MODIFIER  = 0.5  # LEDs will use the same colors for DarkSky and AWC forecasts,
                                #   with brightness used to differentiate
VFR_GREEN       = 255
VFR_RED         = 0
VFR_BLUE        = 0
MVFR_GREEN      = 0
MVFR_RED        = 0
MVFR_BLUE       = 255
IFR_GREEN       = 0
IFR_RED         = 255
IFR_BLUE        = 255
NO_REPORT_GREEN = 255 
NO_REPORT_RED   = 255
NO_REPORT_BLUE  = 255
"""
VFR_COLOR       = Color(VFR_GREEN * LED_MODIFIER, VFR_RED * LED_MODIFIER, VFR_BLUE * LED_MODIFIER)
VFR_CALC_COLOR      = Color(VFR_GREEN * LED_CALC_MODIFIER, VFR_RED * LED_CALC_MODIFIER, VFR_BLUE * LED_CALC_MODIFIER) 
MVFR_COLOR      = Color(MVFR_GREEN * LED_MODIFIER, MVFR_RED * LED_MODIFIER, MVFR_BLUE * LED_MODIFIER)
MVRF_CALC_COLOR     = Color(MVFR_GREEN * LED_CALC_MODIFIER, MVFR_RED * LED_CALC_MODIFIER, MVFR_BLUE * LED_CALC_MODIFIER)
IFR_COLOR       = Color(IFR_GREEN * LED_MODIFIER, IFR_RED * LED_MODIFIER, IFR_BLUE * LED_MODIFIER)
IFR_CALC_COLOR      = Color(IFR_GREEN * LED_CALC_MODIFIER, IFR_RED * LED_CALC_MODIFIER, IFR_BLUE * LED_CALC_MODIFIER)
LIFR_COLOR      = Color(LIFR_GREEN * LED_MODIFIER, LIFR_RED * LED_MODIFIER, LIFR_BLUE * LED_MODIFIER)
LIFR_CALC_COLOR     = Color(LIFR_GREEN * LED_CALC_MODIFIER, LIFR_RED * LED_CALC_MODIFIER, LIFR_BLUE * LED_CALC_MODIFIER)
NO_REPORT_COLOR = Color(NO_REPORT_GREEN, NO_REPORT_RED, NO_REPORT_BLUE)
"""

airportDict = {}

class Airport:
    def __init__(self, code, lat, lng, airportName):
        self.code = code
        self.lat = lat
        self.lng = lng
        self.name = airportName.strip()
        self.flightCategory = None
        self.isCalculated = False

    def print(self):
        if self.flightCategory is None:
            print(self.name + " at " + str(self.lat) + ", " + str(self.lng) + " is not reported")
        else:
            print(self.name + " at " + str(self.lat) + ", " + str(self.lng) + " is " + self.flightCategory)

def convert_dms_to_dd(d, m, s):
    dd = float(d) + float(m) / 60 + float(s) / 3600
    return dd

def parseCoordinates(coorString):
    parts = coorString.split("-")
    coor = convert_dms_to_dd(parts[0], parts[1], parts[2][:-1])
    if parts[2].endswith("S") or parts[2].endswith("W"):
        return coor * -1
    else:
        return coor


def loadAirportConfigs():
    with open("airports") as f:
        airports = f.readlines()

    for l in airports:
        arr = l.split(",")
        if "-" in arr[1][1:]:
            lat = parseCoordinates(arr[1])
        else:
            lat = arr[1]
        if "-" in arr[2][1:]:
            lng = parseCoordinates(arr[2])
        else:
            lng = arr[2]
        airportDict[arr[0]] = Airport(arr[0], lat, lng, arr[3])


def lookupFlightRules():
    awc_url = "https://www.aviationweather.gov/adds/dataserver_current/httpparam?dataSource=metars&requestType=retrieve&format=xml&hoursBeforeNow=1.5&stationString="

    for key in airportDict:
        airport = airportDict[key]
        if airport.code.startswith("NULL"):
            continue

        awc_url = awc_url + airport.code + ","

    content = urlopen(awc_url).read()
    
    root = ET.fromstring(content)

    for metar in root.iter("METAR"):
        stationId = metar.find("station_id").text

        if metar.find("flight_category") is None:
            continue

        flightCategory = metar.find("flight_category").text
        if airportDict[stationId] is not None:
            if airportDict[stationId].flightCategory is None:
                airportDict[stationId].flightCategory = flightCategory


def lookupWeatherForecasts():
    for key in airportDict:
        airport = airportDict[key]
        if airport.flightCategory is None:
            forecast = forecastio.load_forecast(DARKSKY_API_KEY, airport.lat, airport.lng)
            dataPoint = forecast.currently()
            print(airport.name + ": " + str(dataPoint.cloudCover) + " " + str(dataPoint.visibility))
            if dataPoint.visibility > VFR_MIN and dataPoint.cloudCover < 0.25:
                airport.flightCategory = "VFR"
            elif dataPoint.visibility >= MVFR_MIN and dataPoint.cloudCover < 0.5:
                airport.flightCategory = "MVFR"
            elif dataPoint.visibility > IFR_MIN:
                airport.flightCategory = "IFR"
            else:
                airport.flightCategory = "LIFR"


def clearFlightCategories():
    for key in airportDict:
        airport = airportDict[key]
        airport.flightCategory = None


def lightupLeds():
    i = 0

    for key in airportDict:
        airport = airportDict[key]
        if airport.code == "NULL":
            i = i + 1
            continue

        color = NO_REPORT_COLOR

        if airport.flightCategory == "VFR":
            if airport.isCalculated:
                color = VFR_CALC_COLOR
            else:
                color = VFR_COLOR
        elif airport.flightCategory == "MVFR":
            if airport.isCalculated:
                color = MVFR_CALC_COLOR
            else:
                color = MVFR_COLOR
        elif airport.flightCategory == "IFR":
            if airport.isCalculated:
                color = IFR_CALC_COLOR
            else:
                color = IFR_COLOR
        elif airport.flightCategory == "LIFR":
            if airport.isCalculated:
                color = LIFR_CALC_COLOR
            else:
                color = LIFR_COLOR

        #strip.setPixelColor(i, color)
        #strip.show()

        i = i + 1

def printAirports():
    for key in airportDict:
        airport = airportDict[key]
        airport.print()


# main program logic
if __name__ == '__main__':
    # Create NeoPixel object using constants from top of program
    #strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_AWC_BRIGHTNESS, LED_CHANNEL, LED_STRIP)
    #strip.begin()

    # read the airport configuration file
    loadAirportConfigs()

    # start the loop
    while (True):
        # retrieve flight rules from AWC
        lookupFlightRules()

        # update forecasts from DarkSky
        lookupWeatherForecasts()

        print("")

        # light up the LEDs
        #lightupLeds()

        # wait an hour and do this again
        #time.sleep(SLEEP_TIME)

        printAirports()

        # clear out the flight rules so we can retrieve forecasts as needed
        clearFlightCategories()

        exit()
    
