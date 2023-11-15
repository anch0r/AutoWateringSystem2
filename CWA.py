import urllib.request as ur
import urllib.error
import logging
import json
import time

def getDataFromCWA(requestedElem):
    baseUrl = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization=&StationName=%E6%96%B0%E8%8E%8A&WeatherElement='
    url = baseUrl + requestedElem 
    not_connected = True
    data_get = False
    while(not data_get):
        while(not_connected):
            try:
                site = ur.urlopen(url)
            except urllib.error.HTTPError as he:
                logging.error(he)
                if(he.code == 429):    #Too many requests
                    print('sleep 1 day')
                    time.sleep(86400)
                else:
                    time.sleep(10)
                continue
            except urllib.error.URLError as ue:
                logging.error(ue)
                time.sleep(10)
                continue
            except Exception as e:
                logging.error(e)
                time.sleep(10)
                continue
            not_connected = False
        try:
            page = site.read()
            contents = page.decode()
            data = json.loads(contents)
            if data is not None:
                weatherElem = float(data['records']['Station'][0]['WeatherElement'][requestedElem])
                if weatherElem < 0.0:
                    baseUrl = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization=&StationName=%E8%87%BA%E5%8C%97&WeatherElement='
                    url = baseUrl + requestedElem
                    not_connected = True
                    continue
                data_get = True
                return weatherElem
            else:
                return 101.0
        except Exception as e:
            logging.error(e)
            logging.error('failed to get data from CWB')
            return 101.0