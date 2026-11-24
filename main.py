import asyncio
import logging
import RPi.GPIO as GPIO
import urllib.parse

# 匯入我們剛剛改寫好的三個非同步/同步子模組
from CWA import getDataFromCWA_async
from ThingSpeakConnect import upload_data_async
from ValveControl import init_gpio, closeValve, trigger_spray_async

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === 您的原始參數設定 ===
timeCalibration = -0.5  # 原本用於校正 Thread 漂移，在 asyncio.sleep 中通常不需要，但仍保留
dataUploadTimeout = 600.0  # 每 10 分鐘（600秒）抓取並上傳一次數據
wateringTimeout = 3600.0  # 基礎噴水間隔：1 小時（3600秒）
thingSpeakApiKey = ''  # 填入您的 ThingSpeak API Key

# 溫度區間定義與季節噴水額外延遲（原始設定）
hotTemp = 25.0
warmTemp = 20.0
chillTemp = 15.0
warmTempWateringDelay = 3600.0  # 溫暖季節額外延遲 1 小時
chillTempWateringDelay = 10800.0  # 寒冷季節額外延遲 3 小時

# 全域共享狀態（單執行緒安全，不需要加鎖 Lock）
shared_status = {
    "temperature": None,
    "humidity": None,
    "last_watering_time": 0.0  # 記錄上一次成功觸發噴水的時間戳
}


async def data_loop():
    """
    任務一：數據更新循環
    每 10 分鐘精準執行一次。負責從 CWA 抓資料、安全檢查、打包傳給 ThingSpeak。
    """
    while True:
        try:
            print('--- [Data Task] 開始執行數據更新任務 ---')

            # 1. 非同步抓取 CWA 資料（網路等待時，會釋放 CPU 讓噴水或關機任務先跑）
            temp = await getDataFromCWA_async('AirTemperature')
            humidity = await getDataFromCWA_async('RelativeHumidity')

            # 存入全局變數更新狀態
            shared_status["temperature"] = temp
            shared_status["humidity"] = humidity

            if humidity is not None and temp is not None:
                # 這裡可以保留您原本想要的校正邏輯，例如：temp = calibration(temp)
                print(f'Temp={temp:0.1f}*  Humidity={humidity:0.1f}%')
                print('get data from CWA checkpoint passed')

                # 2. 原始安全機制：如果數值超出正常地球範圍，判定感測器故障，強制關閥
                if (humidity < 0.0 or humidity > 101.0) or (temp < 0.0 or temp > 50.0):
                    print('⚠️ sensor malfunction, force close valve')
                    closeValve()
                    # 發生異常時，本次不執行上傳，等待 10 分鐘後再次嘗試
                    # 清空全域變數，避免 watering_loop 誤用異常數據去判斷澆水
                    shared_status["temperature"] = None
                    shared_status["humidity"] = None
                    continue

                    # 3. 準備 Payload 並非同步上傳至 ThingSpeak（不再透過舊的 ThreadDispatcher）
                thingSpeakParams = urllib.parse.urlencode({
                    'field1': temp,
                    'field2': humidity,
                    'key': thingSpeakApiKey
                })

                # 呼叫我們改寫好的非同步上傳函式
                await upload_data_async(thingSpeakParams)
                print('global timer checkpoint passed')

        except Exception as e:
            logging.error(f"data_loop 發生錯誤: {e}")

        # 精準等待 10 分鐘 (包含您可以手動加上您原本的 timeCalibration，如 dataUploadTimeout + timeCalibration)
        await asyncio.sleep(dataUploadTimeout)


async def watering_loop():
    """
    任務二：電磁閥噴水檢查循環
    每 5 秒（可自行調整）快速掃描一次當前溫濕度狀態是否符合您原始的「溫度季節三大條件」。
    """
    # 獲取 asyncio 事件循環的時間軸，用於高精度時間差計算
    loop = asyncio.get_event_loop()

    # 剛啟動時，初始化上次噴水時間
    shared_status["last_watering_time"] = loop.time() - wateringTimeout - chillTempWateringDelay

    while True:
        try:
            temp = shared_status["temperature"]
            humidity = shared_status["humidity"]
            current_time = loop.time()

            # 計算距離上次噴水已經過了幾秒
            time_passed = current_time - shared_status["last_watering_time"]

            # 原始條件：濕度與溫度資料都必須存在，且濕度低於 70% 才會觸發
            if humidity is not None and humidity < 70.0 and temp is not None:

                # 【條件 1】：炎熱季節 (>= 25度)，間隔達到基礎 1 小時
                if temp >= hotTemp and time_passed >= wateringTimeout:
                    print('🔥 hot & humidity < 70%, watering 20 sec...\n')
                    await trigger_spray_async(duration=20)
                    shared_status["last_watering_time"] = loop.time()  # 記錄新時間戳

                # 【條件 2】：溫暖季節 (20 ~ 25度之間)，間隔達到 1 小時 + 額外 1 小時延遲
                elif (warmTemp <= temp < hotTemp) and time_passed >= (wateringTimeout + warmTempWateringDelay):
                    print('🌤️ humidity < 70% (Warm Season), watering 1520 sec...\n')
                    await trigger_spray_async(duration=20)
                    shared_status["last_watering_time"] = loop.time()

                # 【條件 3】：寒冷季節 (15 ~ 20度之間)，間隔達到 1 小時 + 額外 3 小時延遲
                elif (chillTemp <= temp < warmTemp) and time_passed >= (wateringTimeout + chillTempWateringDelay):
                    print('❄️ humidity < 70% (Chill Season), watering 1520 sec...\n')
                    await trigger_spray_async(duration=20)
                    shared_status["last_watering_time"] = loop.time()

        except Exception as e:
            logging.error(f"watering_loop 發生錯誤: {e}")

        # 每 5 秒巡檢一次條件，反應速度相較原本的 10 分鐘大幅提升
        await asyncio.sleep(5)


async def main():
    print('🚀 樹莓派自動噴霧系統 [Asyncio 非同步完全體] 啟動...')

    # 1. 啟動時先將硬體引腳初始化
    init_gpio()

    # 2. 同時併發運行「數據循環」與「噴水巡檢循環」
    # 這兩個無窮循環會交織運行在樹莓派的單個執行緒中，共享記憶體，完全不卡死
    await asyncio.gather(
        data_loop(),
        watering_loop()
    )


if __name__ == "__main__":
    try:
        # 啟動 asyncio 事件循環
        asyncio.run(main())
    except KeyboardInterrupt:
        # 當您在終端機按下 Ctrl+C 時，會直接跳進這裡，不再需要像以前一樣苦等 10 分鐘
        print('\n🛑 使用者手動中斷，正在安全關閉系統...')
    except Exception as e:
        print('🛑 系統發生非預期嚴重錯誤')
        logging.error(e)
    finally:
        # 無論如何結束程式（中斷或報錯），最後都必定強制關閉電磁閥，並清理引腳
        closeValve()
        GPIO.cleanup()
        print('✨ watering system safely stopped and GPIO cleaned up.')
