import requests
from bs4 import BeautifulSoup
import os

# --- 台科大全校公告網址 ---
URL = "https://www.ntust.edu.tw/p/403-1000-14.php" 
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FILE_PATH = "last.txt"

def send_telegram(msg):
    api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    requests.post(api_url, data=payload)

def scrape():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        res = requests.get(URL, headers=headers, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        # 台科大公告列表的精準定位：抓取第一則公告
        # 通常在 .mtitle 或是包含公告連結的 <a> 標籤中
        news_tag = soup.select_one('.mtitle a') or soup.select_one('.listBS a')
        
        if not news_tag:
            print("找不到公告標籤，可能網頁結構變了")
            return

        new_title = news_tag.text.strip()
        new_link = news_tag.get('href')

        # 讀取舊紀錄 (就像你在 C 語言裡讀取存檔一樣)
        if os.path.exists(FILE_PATH):
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                old_title = f.read().strip()
        else:
            old_title = ""

    # 邏輯判斷：如果有新內容
        if new_title != old_title:
            message = f"<b>📢 台科大最新公告</b>\n\n標題：{new_title}\n\n🔗 <a href='{new_link}'>點此查看詳情</a>"
            send_telegram(message)
            
            # 存下這次的標題，下次比對用
            with open(FILE_PATH, "w", encoding="utf-8") as f:
                f.write(new_title)
            print(f"成功發送新消息：{new_title}")
        else:
            print("目前沒有新公告。")

    except Exception as e:
        print(f"發生錯誤: {e}")

if __name__ == "__main__":
    scrape()
