
class Airport:
    def __init__(self, code, lat, lng, airportName):
        self.code = code
        self.lat = lat
        self.lng = lng
        self.name = airportName
        self.flightCategory = None
        self.isCalculated = False
