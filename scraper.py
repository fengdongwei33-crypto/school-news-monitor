import requests
from bs4 import BeautifulSoup
import os

# --- 設定區：台科大全校公告 ---
NEWS_URL = "https://bulletin.ntust.edu.tw/p/403-1045-1391-1.php?Lang=zh-tw"
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FILE_PATH = "last_news.txt"

def send_tg(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    requests.post(url, data=payload)

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(NEWS_URL, headers=headers, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        # 精準定位：找公告表格中的第一則標題
        # 台科大的標題通常在 class 為 prop_title 的 div 裡的 <a> 標籤
        news_item = soup.select_one(".table_01 .prop_title a") or soup.select_one("td a[title]")
        
        if news_item:
            # 優先抓取 title 屬性，那裡有完整的標題文字
            new_title = news_item.get('title') or news_item.text.strip()
            new_link = news_item.get('href')
            
            # 讀取舊紀錄
            old_news = ""
            if os.path.exists(FILE_PATH):
                with open(FILE_PATH, "r", encoding="utf-8") as f:
                    old_news = f.read().strip()
            
            # 邏輯判斷：如果有新消息
            if new_title != old_news:
                message = f"<b>📢 台科大新公告</b>\n\n{new_title}\n\n🔗 <a href='{new_link}'>點此查看詳情</a>"
                send_tg(message)
                
                # 更新紀錄檔
                with open(FILE_PATH, "w", encoding="utf-8") as f:
                    f.write(new_title)
                print(f"成功發送：{new_title}")
            else:
                print("目前沒有新消息。")
                
    except Exception as e:
        print(f"發生錯誤: {e}")

if __name__ == "__main__":
    scrape()
