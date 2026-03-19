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
    {"name": "台科大公告", "url": "https://bulletin.ntust.edu.tw/p/403-1045-1391-1.php?Lang=zh-tw", "file": "last_news.txt", "selector": ".mtitle a, .table_01 .prop_title a"},
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

def clean_body_and_attachments(msg):
    body = ""
    attachments = []
    try:
        if msg.is_multipart():
            for part in msg.walk():
                # 偵測附檔
                filename = part.get_filename()
                if filename:
                    # 解碼附檔名稱 (處理中文亂碼)
                    decoded_fn, charset = decode_header(filename)[0]
                    if isinstance(decoded_fn, bytes):
                        try:
                            decoded_fn = decoded_fn.decode(charset or 'utf-8', errors='ignore')
                        except:
                            decoded_fn = decoded_fn.decode('big5', errors='ignore')
                    attachments.append(decoded_fn)
                    continue # 找到附檔就記錄，跳過內文解析

                # 擷取內文
                content_type = part.get_content_type()
                if content_type == "text/plain" and not body:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                elif content_type == "text/html" and not body:
                    html = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                    # 加入 separator 讓 HTML 標籤轉成漂亮換行
                    body = BeautifulSoup(html, "html.parser").get_text(separator='\n')
        else:
            # 【關鍵修復】處理圖書館這種「單一 HTML 包裹」的信件
            content_type = msg.get_content_type()
            raw_body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
            if "html" in content_type:
                body = BeautifulSoup(raw_body, "html.parser").get_text(separator='\n')
            else:
                body = raw_body
    except Exception as e:
        print(f"解析內文發生錯誤: {e}")
        
    # 優化排版：保留換行與段落，去除多餘的空白行
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    full_text = "\n".join(lines)
    
    # 3500 字安全防護線
    if len(full_text) > 3500:
        full_text = full_text[:3500] + "\n\n(⚠️ 信件過長，為避免推播失敗，請至 Webmail 觀看完整內容)"
        
    return full_text.replace('<', '&lt;').replace('>', '&gt;'), attachments

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
            # 加入偽裝，突破學校防火牆
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            res = requests.get(t["url"], headers=headers, timeout=20)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select(t["selector"])[:10]
            
            old_titles = open(t["file"], "r", encoding="utf-8").read().splitlines() if os.path.exists(t["file"]) else []
            
            current_titles = []
            new_alerts = []
            
            for item in items:
                # 強制壓平網頁標題的換行與空白，避免被誤判為新公告而重複推播
                title = " ".join((item.get('title') or item.text).split())
                current_titles.append(title)
                
                raw_link = item.get('href')
                link = urllib.parse.urljoin(t["url"], raw_link) if raw_link else t["url"]
                
                if title and title not in old_titles:
                    new_alerts.append(f"<b>📢 {t['name']}</b>\n{title}\n🔗 <a href='{link}'>詳情</a>")
            
            for alert_msg in reversed(new_alerts):
                send_tg(alert_msg)
            
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
        
        # 改用 UID 搜尋，確保刪信不會影響判斷
        status, msgs = mail.uid('search', None, "ALL")
        all_uids = msgs[0].split()
        if not all_uids: return
        
        latest_uid = int(all_uids[-1])
        old_uid = 0
        if os.path.exists("last_mail_id.txt"):
            content = open("last_mail_id.txt", "r").read().strip()
            if content.isdigit(): old_uid = int(content)

        if latest_uid > old_uid:
            start_uid = max(old_uid + 1, latest_uid - 4)
            uids_to_fetch = [uid for uid in all_uids if start_uid <= int(uid) <= latest_uid]

            for uid in uids_to_fetch:
                _, data = mail.uid('fetch', uid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                subj = get_decoded_subject(msg)
                
                # 過濾：公佈欄、Moodle、以及新登入紀錄
                ignore = ["臺科公佈欄(NTUST Bulletin)", "新登入紀錄"]
                if not any(kw in subj for kw in ignore):
                    
                    full_text, attachments = clean_body_and_attachments(msg)
                    
                    # 組合附檔提示文字
                    attach_text = ""
                    if attachments:
                        attach_list = "\n".join([f"📄 {a}" for a in attachments])
                        attach_text = f"\n\n<b>📎 附檔:</b>\n{attach_list}"
                    
                    # 發送 Telegram
                    send_tg(f"<b>📩 Webmail 新郵件</b>\n<b>標題:</b> {subj}\n\n<b>完整內容:</b>\n{full_text}{attach_text}")
            
            with open("last_mail_id.txt", "w") as f: 
                f.write(str(latest_uid))
        mail.logout()
    except Exception as e:
        print(f"Mail Error: {e}")

if __name__ == "__main__":
    run()
