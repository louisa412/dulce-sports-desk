import google.generativeai as genai
import json
import os
import re
from config import GEMINI_API_KEY

def get_model():
    # 優先從環境變數抓取，GitHub Actions 執行時會用到
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key: 
        print("❌ 錯誤：找不到 GEMINI_API_KEY")
        return None
    
    # 設定 API Key
    genai.configure(api_key=key)
    
    # 初始化穩定版模型
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.7
        }
    )
    return model

def generate_all_content(categories_data):
    model = get_model()
    if not model: return {}, "❌ API Key 未設定或初始化失敗。"

    # 檢查是否有資料
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
    3. 必須回傳純 JSON 格式，格式如下：
    {{
      "summaries": {{ 
          "分類名稱": [ {{"id": 1, "note": "..."}} ]
      }},
      "overview": "..."
    }}
    
    資料來源：{json.dumps(combined_payload, ensure_ascii=False)}
    """

    try:
        # 使用穩定版 SDK 的生成方式
        response = model.generate_content(prompt)
        
        if not response or not response.text:
            raise ValueError("AI 回傳內容為空")

        # 淨化 JSON 字串
        raw_text = response.text.strip()
        clean_json = re.sub(r'^```json\s*|\s*```$', '', raw_text, flags=re.MULTILINE)
        
        res_data = json.loads(clean_json)
        
        all_notes = {}
        for cat, items in categories_data.items():
            cat_notes = res_data.get("summaries", {}).get(cat, [])
            # 建立 ID 到 note 的映射
            note_dict = {str(d['id']): d['note'] for d in cat_notes if 'id' in d and 'note' in d}
            # 依照原始順序填入
            all_notes[cat] = [note_dict.get(str(i+1), "分析完成，請見詳情。") for i in range(len(items))]
            
        return all_notes, res_data.get("overview", "今日體育重點導讀已生成。")

    except Exception as e:
        print(f"❌ AI 生成失敗詳細原因: {str(e)}")
        # 即使失敗也回傳空資料，讓 main.py 至少能用原始摘要發送
        return {}, f"今日焦點導讀（暫由系統自動生成）：{type(e).__name__}"
