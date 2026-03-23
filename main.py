import sys
import requests
import json
import os
from config import LINE_TOKEN, TEST_USER_ID, USER_ID
from services.news_fetcher import fetch_entries, pick_top_news, score_arsenal, score_spain, score_f1
from services.ai_engine import generate_all_content
from utils.line_renderer import build_flex_messages

def send_to_line(messages, is_test=True):
    # 設定目標網址：測試模式用 push，正式廣播用 broadcast
    url = "https://api.line.me/v2/bot/message/push" if is_test else "https://api.line.me/v2/bot/message/broadcast"
    
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}", 
        "Content-Type": "application/json"
    }
    
    # 建立 Payload
    payload = {"messages": messages}
    
    # 如果是測試模式才需要指定收件 ID
    if is_test:
        payload["to"] = TEST_USER_ID
        print(f"📡 正在發送【測試推播】到 ID: {TEST_USER_ID[:6]}...")
    else:
        print("🚀 正在啟動【正式全體廣播】...")

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            mode = "測試" if is_test else "廣播"
            print(f"✨ LINE {mode} 成功！")
        else:
            print(f"🚩 LINE API 報錯: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ 網路連線異常: {e}")

def main():
    if not LINE_TOKEN:
        print("❌ 錯誤：找不到 LINE_TOKEN，請檢查 .env 或 config.py")
        return

    # 1. 判斷模式
    is_test = len(sys.argv) > 1 and sys.argv[1] == "test"
    print(f"--- 啟動模式：{'測試模式' if is_test else '正式廣播'} ---")

    # 2. 抓取各分類新聞 (Spain 網址已修正空格問題)
    print("📡 正在從 Google News 抓取戰報...")
    arsenal = pick_top_news(fetch_entries("https://news.google.com/rss/search?q=Arsenal&hl=en-US"), score_arsenal)
    spain = pick_top_news(fetch_entries("https://news.google.com/rss/search?q=Spain+national+team+football&hl=en-US"), score_spain)
    f1 = pick_top_news(fetch_entries("https://news.google.com/rss/search?q=Charles+Leclerc+OR+Ferrari+F1&hl=en-US"), score_f1)

    # 3. 準備資料包，合併呼叫 Gemini
    # 注意：這裡的 Key 名稱必須與 ai_engine.py 裡的一致
    categories_data = {
        "Arsenal": arsenal,
        "Spain": spain,
        "Leclerc / F1": f1
    }

    print("🧠 正在一次性生成所有 AI 深度戰報（節省 API 額度模式）...")
    all_notes, ov_text = generate_all_content(categories_data)

    # 將生成出來的摘要填回對應的新聞物件中
    if all_notes:
        # 填入 Arsenal 摘要
        if "Arsenal" in all_notes:
            for it, n in zip(arsenal, all_notes["Arsenal"]): it["note"] = n
        
        # 填入 Spain 摘要
        if "Spain" in all_notes:
            for it, n in zip(spain, all_notes["Spain"]): it["note"] = n
            
        # 填入 F1 摘要
        if "Leclerc / F1" in all_notes:
            for it, n in zip(f1, all_notes["Leclerc / F1"]): it["note"] = n
    else:
        print("⚠️ AI 生成內容為空，將使用預設摘要。")

    # 4. 構建並發送 LINE 訊息
    print("🎨 正在構建 Flex Message 介面...")
    msgs = build_flex_messages(arsenal, spain, f1, ov_text)
    
    if msgs:
        send_to_line(msgs, is_test)
    else:
        print("⚠️ 無內容可發送，請檢查新聞抓取邏輯。")

    print("✅ 任務執行完畢。")

if __name__ == "__main__":
    main()