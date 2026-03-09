import requests
from bs4 import BeautifulSoup
import os

# --- 設定監控目標清單 ---
TARGETS = [
    {
        "name": "台科大全校公告",
        "url": "https://bulletin.ntust.edu.tw/p/403-1045-1391-1.php?Lang=zh-tw",
        "file": "last_news.txt",
        "selector": ".table_01 .prop_title a" # 全校公告的結構
    },
    {
        "name": "台科大語言中心",
        "url": "https://lc.ntust.edu.tw/p/403-1070-1053-1.php?Lang=zh-tw",
        "file": "last_lc_news.txt",
        "selector": ".mtitle a" # 語言中心的結構
    }
]

TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_tg(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    requests.post(url, data=payload)

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for target in TARGETS:
        try:
            res = requests.get(target["url"], headers=headers, timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')

            # 根據不同頁面抓取第一則公告
            news_item = soup.select_one(target["selector"])
            
            if news_item:
                new_title = news_item.get('title') or news_item.text.strip()
                new_link = news_item.get('href')
                
                # 讀取該目標的舊紀錄
                old_title = ""
                if os.path.exists(target["file"]):
                    with open(target["file"], "r", encoding="utf-8") as f:
                        old_title = f.read().strip()
                
                # 比對
                if new_title != old_title:
                    message = f"<b>📢 {target['name']} 新消息</b>\n\n{new_title}\n\n🔗 <a href='{new_link}'>點此查看詳情</a>"
                    send_tg(message)
                    
                    # 存下新紀錄
                    with open(target["file"], "w", encoding="utf-8") as f:
                        f.write(new_title)
                    print(f"[{target['name']}] 成功發送：{new_title}")
                else:
                    print(f"[{target['name']}] 目前沒有新消息。")
                    
        except Exception as e:
            print(f"[{target['name']}] 發生錯誤: {e}")

if __name__ == "__main__":
    scrape()
