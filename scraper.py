import requests
from bs4 import BeautifulSoup
import os
import imaplib
import email
from email.header import decode_header

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

def clean_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(errors='ignore')
                break
            elif part.get_content_type() == "text/html":
                html = part.get_payload(decode=True).decode(errors='ignore')
                body = BeautifulSoup(html, "html.parser").get_text()
    else:
        body = msg.get_payload(decode=True).decode(errors='ignore')
    return " ".join(body.split())[:250].replace('<', '&lt;').replace('>', '&gt;')

# --- 2. 執行監控 ---
def run():
    # 網頁公告部分
    for t in TARGETS:
        try:
            res = requests.get(t["url"], timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            item = soup.select_one(t["selector"])
            if item:
                title, link = (item.get('title') or item.text.strip()), item.get('href')
                old = open(t["file"], "r").read().strip() if os.path.exists(t["file"]) else ""
                if title != old:
                    send_tg(f"<b>📢 {t['name']}</b>\n{title}\n🔗 <a href='{link}'>詳情</a>")
                    with open(t["file"], "w", encoding="utf-8") as f: f.write(title)
        except: pass

    # Webmail 部分
    if not EMAIL_USER: return
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("INBOX")
        _, msgs = mail.search(None, "ALL")
        last_id = msgs[0].split()[-1].decode()
        old_id = open("last_mail_id.txt", "r").read().strip() if os.path.exists("last_mail_id.txt") else ""
        if last_id != old_id:
            _, data = mail.fetch(last_id, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subj, enc = decode_header(msg["Subject"])[0]
            if isinstance(subj, bytes): subj = subj.decode(enc or "utf-8")
            
            # 【精準過濾】排除公佈欄與 Moodle 登入通知
            ignore = ["公佈欄", "Bulletin", "Moodle教學平台 新登入紀錄", "Moodle教學平台: 新登入紀錄"]
            if any(kw in subj for kw in ignore):
                print(f"自動過濾重複或無用郵件: {subj}")
            else:
                summary = clean_body(msg)
                send_tg(f"<b>📩 Webmail 新郵件</b>\n<b>標題:</b> {subj}\n\n<b>內容摘要:</b>\n{summary}...")
            
            with open("last_mail_id.txt", "w") as f: f.write(last_id)
        mail.logout()
    except: pass

if __name__ == "__main__": run()
