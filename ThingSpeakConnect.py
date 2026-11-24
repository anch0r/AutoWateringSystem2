import asyncio
import logging
import time
import httpx


async def upload_data_async(payload: str):
    """非同步上傳數據至 ThingSpeak，若失敗則每 5 秒重試一次"""
    url = "https://api.thingspeak.com/update"

    # 將 urlencode 的字串解析回字典，方便 httpx 以 Form 表單形式 POST 發送
    # 原本的 headers {"Content-type": "application/x-www-form-urlencoded"} httpx 會自動處理
    from urllib.parse import parse_qs
    data_dict = {k: v[0] for k, v in parse_qs(payload).items()}

    not_connected = True

    async with httpx.AsyncClient() as client:
        while not_connected:
            try:
                print("[ThingSpeak] 正在嘗試上傳數據...")
                # 發送 POST 請求，設定 10 秒超時
                response = await client.post(url, data=data_dict, timeout=10.0)

                # 如果 HTTP 狀態碼不是 2xx，會觸發異常進入 except
                response.raise_for_status()

                # 成功連線並得到回應
                not_connected = False
                current_time = time.strftime("%c")
                print(
                    f"[ThingSpeak] 上傳成功! 狀態碼: {response.status_code}, Payload: {payload}, 時間: {current_time}")

                # 讀取回應內容（ThingSpeak 成功通常會回傳該 Channel 的總資料筆數）
                _ = response.text

            except (httpx.HTTPStatusError, httpx.RequestError, Exception) as ex:
                logging.error(f"[ThingSpeak] 連線或上傳失敗: {ex}")
                print('🔄 5 秒後重新嘗試上傳...')
                # 關鍵：非同步等待，此時不卡死主程式的電磁閥控制
                await asyncio.sleep(5)

        return
