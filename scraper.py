import requests
from bs4 import BeautifulSoup
import os
import imaplib
import email
from email.header import decode_header

# --- 1. 設定區 ---
# 這裡將兩個網頁都納入迴圈檢查
TARGETS = [
    {"name": "台科大公告", "url": "https://bulletin.ntust.edu.tw/p/403-1045-1391-1.php?Lang=zh-tw", "file": "last_news.txt", "selector": ".table_01 .prop_title a"},
    {"name": "語言中心", "url": "https://lc.ntust.edu.tw/p/403-1070-1053-1.php?Lang=zh-tw", "file": "last_lc_news.txt", "selector": ".mtitle a"}
]
IMAP_SERVER = "mail.ntust.edu.tw"
TG_TOKEN, TG_CHAT_ID = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
EMAIL_USER, EMAIL_PASS = os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS")

def send_tg(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": msg[:4000], "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, data=payload)

def clean_body(msg):
    body = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                    break
                elif part.get_content_type() == "text/html":
                    html = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                    body = BeautifulSoup(html, "html.parser").get_text()
        else:
            body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
    except: pass
    return " ".join(body.split())[:250].replace('<', '&lt;').replace('>', '&gt;')

# --- 2. 執行監控 ---
def run():
    # 網頁公告部分：兩個來源都檢查前 10 則
    for t in TARGETS:
        try:
            res = requests.get(t["url"], timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select(t["selector"])[:10]
            
            # 讀取舊紀錄 (為了精準，建議存成一個 list 或比對最新一則)
            old_title = open(t["file"], "r").read().strip() if os.path.exists(t["file"]) else ""
            
            # 從舊到新排序檢查，確保 Telegram 訊息順序正確
            new_titles = []
            for item in reversed(items):
                title = item.get('title') or item.text.strip()
                link = item.get('href')
                
                # 如果這則標題不在舊紀錄中（簡單判斷）
                if title and title != old_title and title not in old_title:
                    send_tg(f"<b>📢 {t['name']}</b>\n{title}\n🔗 <a href='{link}'>詳情</a>")
                    new_titles.append(title)
            
            # 更新紀錄為最新的一則標題
            if items:
                latest_title = items[0].get('title') or items[0].text.strip()
                with open(t["file"], "w", encoding="utf-8") as f:
                    f.write(latest_title)
        except Exception as e:
            print(f"Error checking {t['name']}: {e}")

    # Webmail 部分 (迴圈讀取新郵件 + 摘要 + 過濾)
    if not EMAIL_USER: return
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("INBOX")
        _, msgs = mail.search(None, "ALL")
        all_ids = msgs[0].split()
        if not all_ids: return
        
        latest_id_int = int(all_ids[-1])
        old_id_int = 0
        if os.path.exists("last_mail_id.txt"):
            content = open("last_mail_id.txt", "r").read().strip()
            if content: old_id_int = int(content)

        if latest_id_int > old_id_int:
            for i in range(max(old_id_int + 1, latest_id_int - 4), latest_id_int + 1):
                _, data = mail.fetch(str(i), "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                subj, enc = decode_header(msg["Subject"])[0]
                if isinstance(subj, bytes): subj = subj.decode(enc or "utf-8")
                
                # 過濾：公佈欄、Moodle、以及轉寄的校內公告
                ignore = ["臺科公佈欄(NTUST Bulletin)", "新登入紀錄"]
                if not any(kw in subj for kw in ignore):
                    summary = clean_body(msg)
                    send_tg(f"<b>📩 Webmail 新郵件</b>\n<b>標題:</b> {subj}\n\n<b>摘要:</b>\n{summary}...")
            
            with open("last_mail_id.txt", "w") as f: f.write(str(latest_id_int))
        mail.logout()
    except Exception as e:
        print(f"Mail Error: {e}")

if __name__ == "__main__":
    run()
