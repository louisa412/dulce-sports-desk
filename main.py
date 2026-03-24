import sys
import requests
from config import LINE_TOKEN, TEST_USER_ID
from services.news_fetcher import (
    fetch_entries,
    pick_top_news,
    score_arsenal,
    score_spain,
    score_f1,
)
from services.ai_engine import generate_all_content
from utils.line_renderer import build_flex_messages


def send_to_line(messages, is_test=True):
    """
    發送訊息到 LINE。
    測試模式使用 push API；正式模式使用 broadcast API。
    回傳 True/False 表示是否成功。
    """
    url = (
        "https://api.line.me/v2/bot/message/push"
        if is_test
        else "https://api.line.me/v2/bot/message/broadcast"
    )

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {"messages": messages}

    # 測試模式一定要有收件人
    if is_test:
        if not TEST_USER_ID:
            print("❌ 錯誤：測試模式缺少 TEST_USER_ID，已取消發送。")
            return False
        payload["to"] = TEST_USER_ID
        print(f"📡 正在發送【測試推播】到 ID: {TEST_USER_ID[:6]}...")
    else:
        print("🚀 正在啟動【正式全體廣播】...")

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            mode = "測試" if is_test else "廣播"
            print(f"✨ LINE {mode} 成功！")
            return True

        print(f"🚩 LINE API 報錯: {r.status_code} - {r.text}")
        return False
    except requests.RequestException as e:
        print(f"❌ LINE 網路連線異常: {e}")
        return False


def main():
    if not LINE_TOKEN:
        print("❌ 錯誤：找不到 LINE_TOKEN，請檢查 .env 或 config.py")
        return

    # 參數有 test 就走測試；否則走正式廣播
    is_test = len(sys.argv) > 1 and sys.argv[1].lower() == "test"
    print(f"--- 啟動模式：{'測試模式' if is_test else '正式廣播'} ---")

    # 1) 抓取各分類新聞
    print("📡 正在從 Google News 抓取戰報...")
    arsenal = pick_top_news(
        fetch_entries("https://news.google.com/rss/search?q=Arsenal&hl=en-US"),
        score_arsenal,
    )
    spain = pick_top_news(
        fetch_entries("https://news.google.com/rss/search?q=Spain+national+team+football&hl=en-US"),
        score_spain,
    )
    f1 = pick_top_news(
        fetch_entries("https://news.google.com/rss/search?q=Charles+Leclerc+OR+Ferrari+F1&hl=en-US"),
        score_f1,
    )

    # 2) 合併呼叫 Gemini（Key 名稱需與 ai_engine.py 一致）
    categories_data = {
        "Arsenal": arsenal,
        "Spain": spain,
        "Leclerc / F1": f1,
    }

    print("🧠 正在一次性生成所有 AI 深度戰報（節省 API 額度模式）...")
    all_notes, ov_text = generate_all_content(categories_data)

    # 3) 摘要回填
    if all_notes:
        if "Arsenal" in all_notes:
            for it, n in zip(arsenal, all_notes["Arsenal"]):
                it["note"] = n

        if "Spain" in all_notes:
            for it, n in zip(spain, all_notes["Spain"]):
                it["note"] = n

        if "Leclerc / F1" in all_notes:
            for it, n in zip(f1, all_notes["Leclerc / F1"]):
                it["note"] = n
    else:
        print("⚠️ AI 生成內容為空，將使用預設摘要。")

    # 4) 構建並發送 LINE 訊息
    print("🎨 正在構建 Flex Message 介面...")
    msgs = build_flex_messages(arsenal, spain, f1, ov_text)

    if not msgs:
        print("⚠️ 無內容可發送，請檢查新聞抓取邏輯。")
        return

    success = send_to_line(msgs, is_test)
    if not success:
        print("❌ 任務結束：LINE 發送失敗。")
        return

    print("✅ 任務執行完畢。")


if __name__ == "__main__":
    main()
