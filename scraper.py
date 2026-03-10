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
    requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"})

# --- 2. 網頁監控邏輯 ---
def check_news():
    for target in TARGETS:
        try:
            res = requests.get(target["url"], timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            item = soup.select_one(target["selector"])
            if item:
                title, link = (item.get('title') or item.text.strip()), item.get('href')
                old = open(target["file"], "r").read().strip() if os.path.exists(target["file"]) else ""
                if title != old:
                    send_tg(f"<b>📢 {target['name']}新消息</b>\n\n{title}\n\n🔗 <a href='{link}'>查看詳情</a>")
                    with open(target["file"], "w", encoding="utf-8") as f: f.write(title)
        except: pass

# --- 3. 信箱監控邏輯 (過濾公佈欄) ---
def check_mail():
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
            # 過濾 logic: 只要標題含有公佈欄或 bulletin 就跳過發送
            if not any(kw in subj for kw in ["公佈欄", "bulletin", "Bulletin"]):
                send_tg(f"<b>📩 Webmail 新郵件</b>\n\n標題：{subj}")
            with open("last_mail_id.txt", "w") as f: f.write(last_id)
        mail.logout()
    except: pass

if __name__ == "__main__":
    check_news()
    check_mail()
