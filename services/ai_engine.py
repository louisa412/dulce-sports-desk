from google import genai
import json
import os
import re
from config import GEMINI_API_KEY

def get_client():
    # 優先從環境變數抓取，GitHub Actions 執行時會用到
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key: 
        print("❌ 錯誤：找不到 GEMINI_API_KEY")
        return None
    return genai.Client(api_key=key)

def generate_all_content(categories_data):
    client = get_client()
    if not client: return {}, "❌ API Key 未設定。"

    # 檢查是否有資料，沒資料就不浪費 API 額度
    if not any(categories_data.values()): 
        return {}, "今日暫無新的運動新聞動態。"
    
    combined_payload = {}
    for cat, items in categories_data.items():
        combined_payload[cat] = [{"id": i+1, "title": it["title"], "summary": it["summary"]} for i, it in enumerate(items)]

    prompt = f"""
    你是專業運動新聞主編。請針對以下各分類的新聞，分別撰寫約 120 字的【繁體中文】深度摘要。
    
    要求：
    1. 每個摘要都必須是【繁體中文】，內容專業且引人入勝。
    2. 最後寫一段 100 字內的【繁體中文】今日精華導讀（overview）。
    3. 必須回傳純 JSON 格式，不要包含任何 Markdown 標籤（如 ```json），格式如下：
    {{
      "summaries": {{ "Arsenal": [ {{"id": 1, "note": "..."}} ], "Spain": [...], "Leclerc / F1": [...] }},
      "overview": "..."
    }}
    
    資料來源：{json.dumps(combined_payload, ensure_ascii=False)}
    """

    try:
        # 模型名稱使用最標準的字串，解決 404 問題
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        if not response or not response.text:
            raise ValueError("AI 回傳內容為空")

        # 【關鍵修復】淨化 JSON 字串：有些 AI 會皮癢加上 ```json ... ```
        raw_text = response.text.strip()
        clean_json = re.sub(r'^```json\s*|\s*```$', '', raw_text, flags=re.MULTILINE)
        
        res_data = json.loads(clean_json)
        
        all_notes = {}
        for cat, items in categories_data.items():
            cat_notes = res_data.get("summaries", {}).get(cat, [])
            # 建立 ID 到 note 的映射
            note_dict = {str(d['id']): d['note'] for d in cat_notes if 'id' in d and 'note' in d}
            # 依照原始順序填入，若沒對應到則顯示預設文字
            all_notes[cat] = [note_dict.get(str(i+1), "分析完成，請見詳情。") for i in range(len(items))]
            
        return all_notes, res_data.get("overview", "今日體育重點導讀已生成。")

    except Exception as e:
        print(f"❌ AI 生成失敗詳細原因: {str(e)}")
        # 即使失敗也回傳空資料，讓 main.py 至少能用原始摘要發送，不至於完全沒訊息
        return {}, f"今日焦點導讀（暫由系統自動生成）：{type(e).__name__}"
