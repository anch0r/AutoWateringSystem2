import asyncio
import logging
import httpx

# 您原本的 API 網址，請在 URL 中填入您的 Authorization Token
BASE_URL_XINZHUANG = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001?Authorization=CWB-API-token&StationName=%E6%96%B0%E8%8E%8A&WeatherElement='
BASE_URL_TAIPEI = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization=CWB-API-token&StationName=%E8%87%BA%E5%8C%97&WeatherElement='


async def getDataFromCWA_async(requestedElem):
    url = BASE_URL_XINZHUANG + requestedElem
    data_get = False

    # 建立一個非同步的 HTTP 客戶端
    async with httpx.AsyncClient() as client:
        while not data_get:
            try:
                print(f"[CWA] 正在請求數據: {requestedElem}...")
                # 使用 client.get 並加上 await，且設定 10 秒超時，網路卡住時會釋放 CPU
                response = await client.get(url, timeout=10.0)

                # 檢查 HTTP 狀態碼
                response.raise_for_status()

            except httpx.HTTPStatusError as hse:
                logging.error(f"HTTP 錯誤: {hse}")
                if hse.response.status_code == 429:  # Too many requests
                    print('⚠️ 觸發 API 限制，非同步等待 1 天...')
                    await asyncio.sleep(86400)  # 非同步等待，其他任務（如噴水）仍會正常運作！
                else:
                    print('網路請求失敗，10 秒後重試...')
                    await asyncio.sleep(10)
                continue

            except (httpx.RequestError, Exception) as e:
                logging.error(f"網路連線或未預期錯誤: {e}")
                await asyncio.sleep(10)
                continue

            # 解析 JSON 數據
            try:
                data = response.json()
                if data is not None:
                    # 依據中央氣象署最新的 JSON 架構解析數據
                    weatherElem = float(data['records']['Station'][0]['WeatherElement'][requestedElem])

                    # 您的特有邏輯：如果觀測值小於 0 (可能新莊站故障或維護中)，切換到台北測站
                    if weatherElem < 0.0:
                        print(f"⚠️ 新莊站數據異常({weatherElem})，自動切換至台北觀測站...")
                        url = BASE_URL_TAIPEI + requestedElem
                        continue

                    data_get = True
                    return weatherElem
                else:
                    return 101.0
            except Exception as e:
                logging.error(f"解析 JSON 失敗: {e}")
                logging.error('failed to get data from CWA')
                return 101.0
