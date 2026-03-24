from google import genai
from google.genai import types
import json
import os
import re
import time
from config import GEMINI_API_KEY


def get_client():
    """
    初始化並回傳 Gemini API Client
    """
    # 優先從環境變數抓取（適用於 GitHub Actions）
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key:
        print("❌ 錯誤：找不到 GEMINI_API_KEY，請檢查環境變數或 config.py")
        return None

    # 初始化新版 GenAI Client (google-genai SDK)
    # 明確指定 API 版本為 v1，避免落回預設 v1beta
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(api_version="v1")
    )


def generate_all_content(categories_data):
    """
    使用 AI 一次性生成所有分類的新聞深度摘要與今日導讀
    """
    client = get_client()
    if not client:
        return {}, "❌ API Key 未設定，無法生成 AI 內容。"

    # 檢查是否有資料
    if not any(categories_data.values()):
        return {}, "今日暫無新的運動新聞動態。"

    # 構建傳送給 AI 的簡化資料結構
    combined_payload = {}
    for cat, items in categories_data.items():
        combined_payload[cat] = [
            {"id": i + 1, "title": it["title"], "summary": it["summary"]}
            for i, it in enumerate(items)
        ]

    prompt = """
    你是專業運動新聞主編。請針對以下各分類的新聞，分別撰寫約 120 字的【繁體中文】深度摘要。

    要求：
    1. 每個摘要都必須是【繁體中文】，內容專業且引人入勝。不可只是重述標題。
    2. 最後寫一段 100 字內的【繁體中文】今日精華導讀（overview）。
    3. 必須回傳純 JSON 格式，不得包含任何 Markdown 以外的解釋文字，格式如下：
    {
      "summaries": { "分類名": [ {"id": 1, "note": "..."} ] },
      "overview": "..."
    }

    資料來源：
    """
    prompt = prompt + json.dumps(combined_payload, ensure_ascii=False)

    # --- 重試機制設定 ---
    max_retries = 3
    retry_delay = 5  # 每次失敗後等待的秒數
    # 優先使用低成本 Flash Lite；可由環境變數 GEMINI_MODEL 覆寫
    target_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    for attempt in range(max_retries):
        try:
            print(f"📡 正在嘗試 AI 生成 (第 {attempt + 1}/{max_retries} 次)，模型：{target_model}...")

            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config={
                    "responseMimeType": "application/json",
                    "temperature": 0.7
                }
                },
            )

            if not response or not response.text:
                raise ValueError("AI 回傳內容為空")

            # 淨化 JSON 字串（處理 AI 有時會吐出 ```json ... ``` 的情況）
            raw_text = response.text.strip()
            clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_text, flags=re.MULTILINE)

            res_data = json.loads(clean_json)

            # 解析並對應回原本的資料格式
            all_notes = {}
            for cat, items in categories_data.items():
                cat_notes = res_data.get("summaries", {}).get(cat, [])
                # 建立 id -> note 的對照表
                note_dict = {
                    str(d["id"]): d["note"]
                    for d in cat_notes
                    if "id" in d and "note" in d
                }
                # 依序放回，若 AI 漏掉則給予預設文字
                all_notes[cat] = [
                    note_dict.get(str(i + 1), "分析完成，請見詳情。")
                    for i in range(len(items))
                ]

            print("✅ AI 生成內容成功！")
            return all_notes, res_data.get("overview", "今日體育重點導讀已生成。")

        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ 第 {attempt + 1} 次嘗試失敗: {error_msg}")

            # 如果是頻率限制 (429)，等待更久一點
            if "429" in error_msg:
                print(f"   原因：觸發 Quota 限制。等待 {retry_delay * 2} 秒後重試...")
                time.sleep(retry_delay * 2)
            elif attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print("❌ 已達到最大重試次數，AI 生成失敗。")
                return {}, f"今日焦點導讀（自動生成中）：{error_msg}"

    return {}, "今日焦點導讀：AI 生成暫時不可用。"
