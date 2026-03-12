import imaplib
import os

# --- 1. 設定區 ---
IMAP_SERVER = "mail.ntust.edu.tw"
# 建議一樣透過環境變數讀取，確保帳密安全
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def mark_all_as_read():
    if not EMAIL_USER or not EMAIL_PASS:
        print("請確認已設定 EMAIL_USER 與 EMAIL_PASS 環境變數。")
        return

    try:
        print("連線至信箱伺服器中...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        
        # 選擇收件匣 (預設為 INBOX)
        mail.select("INBOX")
        
        # 核心邏輯 1：只搜尋「未讀 (UNSEEN)」的信件，避免浪費時間處理舊信
        print("正在搜尋未讀信件...")
        status, response = mail.search(None, "UNSEEN")
        
        if status != "OK":
            print("搜尋失敗。")
            return
            
        # 將回傳的位元組資料轉換為信件 ID 列表
        unread_msg_nums = response[0].split()
        
        if not unread_msg_nums:
            print("🎉 太棒了！你的信箱目前沒有未讀信件。")
        else:
            print(f"找到 {len(unread_msg_nums)} 封未讀信件，開始批次標記為已讀...")
            
            # 核心邏輯 2：逐一將這些未讀信件加上 \Seen (已讀) 標籤
            for num in unread_msg_nums:
                mail.store(num, '+FLAGS', '\\Seen')
                
            print("✅ 處理完成！所有信件均已成功標記為已讀。")

        # 養成好習慣：關閉信箱並登出
        mail.close()
        mail.logout()

    except Exception as e:
        print(f"發生錯誤: {e}")

if __name__ == "__main__":
    mark_all_as_read()
