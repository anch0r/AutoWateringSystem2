import threading
from ThingSpeakConnect import postToThingspeak
from ValveControl import watering30sec

def threadDispatcher(task,args_ = None):   
    try:
        if task == 'UPLOAD_DATA':              
            t = threading.Thread(target = postToThingspeak,args=(args_,))
            t.start()
            return
        if task == 'WATERING':
            t = threading.Thread(target = watering30sec)
            t.start()
            return
    except RuntimeError:
        print('thread dispatcher error \n')
        return
