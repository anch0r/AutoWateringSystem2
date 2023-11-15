import RPi.GPIO as GPIO
import time

def openValve():
    RELAY = 11
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(RELAY, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.output(RELAY, GPIO.LOW)
    return

def closeValve():
    RELAY = 11
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(RELAY, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.output(RELAY, GPIO.HIGH)
    return

def watering30sec():
    try:
        openValve()
        time.sleep(30)
        closeValve()
        print('watering finished, close valve\n')
    except KeyboardInterrupt:
        closeValve()
        print('stop immediately')
    except Exception as e:
        closeValve()
        print('unexpected error occured when watering, force close valve\n')
        logging.error(e)
    finally:
        GPIO.cleanup()
