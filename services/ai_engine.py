from google import genai
import json
import os
import re
from config import GEMINI_API_KEY

def get_client():
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key: return None
    return genai.Client(api_key=key)

def generate_all_content(categories_data):
    client = get_client()
    if not client: return {}, "❌ API Key 未設定。"

    if not any(categories_data.values()): 
        return {}, "今日暫無新的運動新聞動態。"
    
    combined_payload = {}
    for cat, items in categories_data.items():
        combined_payload[cat] = [{"id": i+1, "title": it["title"], "summary": it["summary"]} for i, it in enumerate(items)]

    prompt = f"""
    你是專業運動新聞主編。請針對以下各分類的新聞，分別撰寫約 120 字的【繁體中文】深度摘要。
    
    要求：
    1. 每個摘要都必須是【繁體中文】，內容專業。
    2. 最後寫一段 100 字內的【繁體中文】今日精華導讀。
    3. 必須回傳純 JSON 格式，格式如下：
    {{
      "summaries": {{ "Arsenal": [ {{"id": 1, "note": "..."}} ], "Spain": [...], "Leclerc / F1": [...] }},
      "overview": "..."
    }}
    
    資料：{json.dumps(combined_payload, ensure_ascii=False)}
    """

    try:

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        res_data = json.loads(response.text)
        
        all_notes = {}
        for cat, items in categories_data.items():
            cat_notes = res_data.get("summaries", {}).get(cat, [])
            note_dict = {str(d['id']): d['note'] for d in cat_notes if 'id' in d and 'note' in d}
            all_notes[cat] = [note_dict.get(str(i+1), "分析中...") for i in range(len(items))]
            
        return all_notes, res_data.get("overview", "今日體育重點導讀（自動生成中）。")

    except Exception as e:
        print(f"❌ AI 合併生成失敗: {e}")
        # 如果還是 429，至少在 Terminal 印出詳細原因
        return {}, f"今日焦點導讀（生成失敗：{type(e).__name__}）"
