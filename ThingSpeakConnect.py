import http.client, urllib, socket
import time

def postToThingspeak(payload):  
    headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}
    not_connected = 1
    while (not_connected):
        try:
            conn = http.client.HTTPConnection("api.thingspeak.com:80")
            conn.connect()
            not_connected = 0
        except (http.client.HTTPException, socket.error) as ex:
            print('error: %s' %ex)
            time.sleep(5)  #retry after 5 seconds delay

    conn.request("POST", "/update", payload, headers)
    response = conn.getresponse()
    print(response.status, response.reason, payload, time.strftime("%c"))
    data = response.read()
    conn.close()
    return
