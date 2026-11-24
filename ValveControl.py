import asyncio
import logging
import time
import concurrent.futures  # 用於執行緒池
import RPi.GPIO as GPIO

# 固定使用硬體引腳 11 (GPIO 17)
RELAY = 11

# 建立一個專屬於硬體控制的背景執行緒池（只需 1 條執行緒即可）
hardware_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

def init_gpio():
    """初始化 GPIO 設定（建議在 main 啟動時呼叫一次即可）"""
    GPIO.setmode(GPIO.BOARD)
    # 預設輸出高電位（繼電器關閉狀態）
    GPIO.setup(RELAY, GPIO.OUT, initial=GPIO.HIGH)


def openValve():
    # 確保引腳模式正確
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BOARD)
        
    # 🛠️【核心修正】每次開閥前，都重新將引腳設定為輸出模式並給予低電位
    # 這樣就能完美解決上一次關閥時執行 cleanup 導致引腳被清空的問題！
    GPIO.setup(RELAY, GPIO.OUT)
    print("[Hardware] 設定GPIO引腳，準備開啟電磁閥...")
    """開啟電磁閥"""
    GPIO.output(RELAY, GPIO.LOW)
    print("💧 [Hardware] 電磁閥已開啟...")


def closeValve():
    """強制關閉電磁閥"""
    # 為了安全，關閉時確保引腳有初始化，避免未初始化引腳失效
    try:
        if GPIO.getmode() is None:
            GPIO.setmode(GPIO.BOARD)
        GPIO.setup(RELAY, GPIO.OUT)
        GPIO.output(RELAY, GPIO.HIGH)
        time.sleep(0.05) # 稍微物理阻塞 50 毫秒
        
        # 2. 第二次強效關閉（防止暫態突波導致的引腳失效）
        GPIO.output(RELAY, GPIO.HIGH)
        
        # 3. 軟體模擬 Ctrl+C 的引腳釋放行為
        GPIO.cleanup(RELAY) 
        print("❌ [Hardware] 電磁閥已關閉。")
    except Exception as e:
        print(f"⚠️ 強制關閉電磁閥時發生硬體異常: {e}")


def _blocking_spray_timer(duration: int):
    """
    【核心修正】這個函數會在背景的獨立執行緒中執行。
    它使用傳統的 time.sleep(duration)，擁有作業系統級的強制搶佔權，
    計時絕對精準，完全不受 asyncio 網路任務的排隊干擾！
    """
    try:
        openValve()
        time.sleep(duration)  # 👈 實打實的物理阻塞計時，保證不超噴
        closeValve()
    except Exception as e:
        closeValve()
        raise e

async def trigger_spray_async(duration: int = 20):
    """非同步噴水任務：開啟電磁閥並倒數指定秒數，非阻塞"""
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(hardware_executor, _blocking_spray_timer, duration)
        print(f'✨ 噴水任務完成，安全關閉電磁閥（計時 {duration} 秒）\n')

    except asyncio.CancelledError:
        # 當主程式被 Ctrl+C 中斷，asyncio 會主動取消這個運行中的任務
        closeValve()
        print('🛑 噴水任務收到取消訊號，電磁閥已立刻緊急關閉！')
        raise  # 必須拋出，讓上層知道任務已被取消

    except Exception as e:
        closeValve()
        print('⚠️ 噴水過程中發生未預期錯誤，已強制關閉電磁閥！\n')
        logging.error(e)
