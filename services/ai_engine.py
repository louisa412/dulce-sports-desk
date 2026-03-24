from google import genai
import json
import os
import re

from config import GEMINI_API_KEY

# 先用 2.x；若帳號/區域不可用再往下嘗試
DEFAULT_MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]


def get_client():
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key:
        print("❌ 錯誤：找不到 GEMINI_API_KEY")
        return None
    return genai.Client(api_key=key)


def generate_all_content(categories_data):
    client = get_client()
    if not client:
        return {}, "❌ API Key 未設定。"

    if not any(categories_data.values()):
        return {}, "今日暫無新的運動新聞動態。"

    payload = {
        cat: [
            {"id": i + 1, "title": item["title"], "summary": item["summary"]}
            for i, item in enumerate(items)
        ]
        for cat, items in categories_data.items()
    }

    prompt = f"""
你是專業運動新聞主編。請針對以下各分類的新聞，分別撰寫約 120 字的【繁體中文】深度摘要。

要求：
1. 每個摘要都必須是【繁體中文】，內容專業且引人入勝。
2. 最後寫一段 100 字內的【繁體中文】今日精華導讀（overview）。
3. 必須回傳純 JSON，不要包含 Markdown 標籤（如 ```json），格式如下：
{{
  "summaries": {{ "Arsenal": [ {{"id": 1, "note": "..."}} ], "Spain": [...], "Leclerc / F1": [...] }},
  "overview": "..."
}}

資料來源：{json.dumps(payload, ensure_ascii=False)}
"""

    # 模型候選：先吃環境變數，再補預設清單（去重）
    model_candidates = []
    env_model = os.getenv("GEMINI_MODEL")
    if env_model:
        model_candidates.append(env_model)
    for model in DEFAULT_MODELS:
        if model not in model_candidates:
            model_candidates.append(model)

    try:
        response = None
        selected_model = None
        last_error = None

        for model in model_candidates:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
                selected_model = model
                break
            except Exception as e:
                last_error = e
                if "NOT_FOUND" not in str(e):
                    raise
                print(f"⚠️ 模型 {model} 不可用，改試下一個...")

        if not response:
            raise last_error or ValueError("沒有可用的 Gemini 模型")
        if not response.text:
            raise ValueError("AI 回傳內容為空")

        # 有些模型可能包 ```json ... ```，先清掉再解析
        clean_text = re.sub(
            r"^```json\s*|\s*```$", "", response.text.strip(), flags=re.MULTILINE
        )
        data = json.loads(clean_text)

        notes = {}
        for cat, items in categories_data.items():
            rows = data.get("summaries", {}).get(cat, [])
            row_map = {str(r["id"]): r["note"] for r in rows if "id" in r and "note" in r}
            notes[cat] = [row_map.get(str(i + 1), "分析完成，請見詳情。") for i in range(len(items))]

        print(f"✅ 已使用模型：{selected_model}")
        return notes, data.get("overview", "今日體育重點導讀已生成。")

    except Exception as e:
        print(f"❌ AI 生成失敗詳細原因: {e}")
        return {}, f"今日焦點導讀（暫由系統自動生成）：{type(e).__name__}"
