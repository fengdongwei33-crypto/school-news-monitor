import requests
from bs4 import BeautifulSoup
import os
import imaplib
import email
from email.header import decode_header
import urllib.parse
import time

# --- 1. 設定區 ---
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
    time.sleep(1) # 避免連續推播被 Telegram API 阻擋

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
                    break # 找到 HTML 也要跳出，避免繼續覆蓋
        else:
            body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
    except Exception as e:
        print(f"Body parsing error: {e}")
    return " ".join(body.split())[:250].replace('<', '&lt;').replace('>', '&gt;')

# 解析多段式郵件標題
def get_decoded_subject(msg):
    subject_header = msg.get("Subject", "(無主旨)")
    decoded_list = decode_header(subject_header)
    subj = ""
    for text, charset in decoded_list:
        if isinstance(text, bytes):
            subj += text.decode(charset or 'utf-8', errors='ignore')
        else:
            subj += text
    return subj

# --- 2. 執行監控 ---
def run():
    # --- 網頁公告部分 ---
    for t in TARGETS:
        try:
            res = requests.get(t["url"], timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select(t["selector"])[:10]
            
            # 讀取舊紀錄 (改為讀取多筆清單，避免排序亂掉導致重複推播)
            old_titles = open(t["file"], "r", encoding="utf-8").read().splitlines() if os.path.exists(t["file"]) else []
            
            current_titles = []
            new_alerts = []
            
            for item in items:
                title = item.get('title') or item.text.strip()
                current_titles.append(title)
                # 處理相對路徑轉絕對路徑
                raw_link = item.get('href')
                link = urllib.parse.urljoin(t["url"], raw_link) if raw_link else t["url"]
                
                if title and title not in old_titles:
                    new_alerts.append(f"<b>📢 {t['name']}</b>\n{title}\n🔗 <a href='{link}'>詳情</a>")
            
            # 反轉清單，確保 Telegram 發送順序是由舊到最新
            for alert_msg in reversed(new_alerts):
                send_tg(alert_msg)
            
            # 將最新的 10 筆標題覆寫回紀錄檔
            if current_titles:
                with open(t["file"], "w", encoding="utf-8") as f:
                    f.write("\n".join(current_titles))
        except Exception as e:
            print(f"Error checking {t['name']}: {e}")

    # --- Webmail 部分 ---
    if not EMAIL_USER: return
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("INBOX")
        
        # 改用 UID 搜尋，確保刪信不會影響序號判斷
        status, msgs = mail.uid('search', None, "ALL")
        all_uids = msgs[0].split()
        if not all_uids: return
        
        latest_uid = int(all_uids[-1])
        old_uid = 0
        if os.path.exists("last_mail_id.txt"):
            content = open("last_mail_id.txt", "r").read().strip()
            if content.isdigit(): old_uid = int(content)

        if latest_uid > old_uid:
            # 最多往前追溯 5 封，避免初次執行或中斷太久大洗版
            start_uid = max(old_uid + 1, latest_uid - 4)
            
            # 因為 UID 可能不連續，我們尋找大於 old_uid 且在抓取範圍內的實際 UID
            uids_to_fetch = [uid for uid in all_uids if start_uid <= int(uid) <= latest_uid]

            for uid in uids_to_fetch:
                _, data = mail.uid('fetch', uid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                subj = get_decoded_subject(msg)
                
                # 過濾邏輯
                ignore = ["臺科公佈欄(NTUST Bulletin)", "新登入紀錄"]
                if not any(kw in subj for kw in ignore):
                    summary = clean_body(msg)
                    send_tg(f"<b>📩 Webmail 新郵件</b>\n<b>標題:</b> {subj}\n\n<b>摘要:</b>\n{summary}...")
            
            with open("last_mail_id.txt", "w") as f: 
                f.write(str(latest_uid))
        mail.logout()
    except Exception as e:
        print(f"Mail Error: {e}")

if __name__ == "__main__":
    run()
