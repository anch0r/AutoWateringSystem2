import sys
import time
import urllib
import logging
import RPi.GPIO as GPIO
from ValveControl import openValve, closeValve, watering30sec
from ThreadDispatcher import threadDispatcher
from CWA import getDataFromCWA
from ThingSpeakConnect import postToThingspeak

timeCalibration = -0.5       #timing error calibration
dataUploadTimeout = 600.0    #upload sensor data to thingSpeak every 10 minutes
wateringTimeout = 3600.0     #watering timeout(1 hour)
thingSpeakApiKey = ''
thingSpeakParams = None
humidity = None
temperature = None
hotTemp = 25.0
warmTemp = 20.0
chillTemp = 15.0
warmTempWateringDelay = 3600.0    #delay additional 1 hour in warm seasons
chillTempWateringDelay = 10800.0  #delay additional 3 hour in chill seasons

#timer initialize
dataUploadTimer = time.time()
wateringTimer =  time.time()

try:
    while True:
        loopTimer = time.time()
        #avoid using time.sleep() for timing out in main thread
        if ((loopTimer - dataUploadTimer) >= dataUploadTimeout):
            print('global timer checkpoint passed')
            temperature = getDataFromCWB('AirTemperature')
            humidity = getDataFromCWB('RelativeHumidity')
            print('get data from CWB checkpoint passed')
            if humidity is not None and temperature is not None:
                temperature = calibration(temperature)
                print('Temp={0:0.1f}*  Humidity={1:0.1f}%'.format(temperature, humidity))
                thingSpeakParams = urllib.parse.urlencode({'field1': temperature, 'field2': humidity, 'key': thingSpeakApiKey})
                threadDispatcher('UPLOAD_DATA',thingSpeakParams)                
                dataUploadTimer = time.time() + timeCalibration
            if (humidity is not None and (humidity < 0.0 or humidity > 101.0)) or (temperature is not None and (temperature < 0.0 or temperature > 50.0)):
                print('sensor malfunction, force close valve')
                closeValve()
                continue
            if humidity is not None and humidity < 70.0 and temperature is not None:
                if temperature >= hotTemp and (loopTimer - wateringTimer) >= wateringTimeout:           
                    print('hot & humidity < 70%, watering 30 sec...\n')
                    threadDispatcher('WATERING')
                    wateringTimer = time.time()
                if (warmTemp <= temperature < hotTemp) and (loopTimer - wateringTimer) >= (wateringTimeout + warmTempWateringDelay):           
                    print('humidity < 70%, watering 30 sec...\n')
                    threadDispatcher('WATERING')
                    wateringTimer = time.time()
                if (chillTemp <= temperature < warmTemp) and (loopTimer - wateringTimer) >= (wateringTimeout + chillTempWateringDelay):           
                    print('humidity < 70%, watering 30 sec...\n')
                    threadDispatcher('WATERING')
                    wateringTimer = time.time()
            
except KeyboardInterrupt:
    closeValve()    #probably not thread-safe, must check
    print('watering system stpped')
    
except Exception as e:
    closeValve()    #probably not thread-safe, must check
    print('unexpected error occured')
    logging.error(e)

finally:
    GPIO.cleanup()

