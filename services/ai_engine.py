from google import genai
from google.genai import types
import json
import os
import re
import time
from typing import Any
from config import GEMINI_API_KEY


def get_client():
    """初始化並回傳 Gemini API Client。"""
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key:
        print("❌ 錯誤：找不到 GEMINI_API_KEY，請檢查環境變數或 config.py")
        return None

    # 明確指定 API 版本為 v1，避免預設 v1beta
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(api_version="v1"),
    )


def _extract_json_text(raw_text):
    """
    從模型輸出中盡量抽出 JSON 文字：
    1) 優先移除 ```json ... ``` fence
    2) 若仍非純 JSON，擷取第一個 {...} 區塊
    """
    text = (raw_text or "").strip()
    if not text:
        return ""

    cleaned = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    match = re.search(r"\{[\s\S]*\}", cleaned)
    return match.group(0).strip() if match else cleaned


def _build_note_mapping(cat_notes: list[Any], expected_count: int, category: str):
    """建立摘要對照並記錄 fallback 原因。"""
    note_by_id = {}
    fallback_reasons = {}

    for idx, row in enumerate(cat_notes, 1):
        if not isinstance(row, dict):
            print(f"⚠️ [{category}] 第 {idx} 筆不是 dict，跳過。內容={row}")
            continue

        raw_id = row.get("id")
        note_text = str(row.get("note", "")).strip()
        if raw_id is None:
            print(f"⚠️ [{category}] 缺少 id，跳過。內容={row}")
            continue

        normalized_id = str(raw_id).strip()
        if normalized_id.isdigit():
            normalized_id = str(int(normalized_id))

        if not note_text:
            fallback_reasons[normalized_id] = "note 為空字串"
            continue

        note_by_id[normalized_id] = note_text

    resolved_notes = []
    for nid in range(1, expected_count + 1):
        key = str(nid)
        note = note_by_id.get(key)
        if note:
            resolved_notes.append(note)
        else:
            reason = fallback_reasons.get(key, "AI 未回傳此 id")
            print(f"⚠️ [{category}] id={key} 觸發 fallback：{reason}")
            resolved_notes.append("分析完成，請見詳情。")

    return resolved_notes


def generate_all_content(categories_data):
    """使用 AI 一次性生成所有分類的新聞深度摘要與今日導讀。"""
    client = get_client()
    if not client:
        return {}, "❌ API Key 未設定，無法生成 AI 內容。"

    if not any(categories_data.values()):
        return {}, "今日暫無新的運動新聞動態。"

    combined_payload = {}
    for cat, items in categories_data.items():
        combined_payload[cat] = [
            {"id": i + 1, "title": it.get("title", ""), "summary": it.get("summary", "")}
            for i, it in enumerate(items)
        ]

    prompt = """
    你是專業運動新聞主編。請針對以下每一則新聞，逐則撰寫約 120 字​:codex-terminal-citation[codex-terminal-citation]{line_range_start=1 line_range_end=190 terminal_chunk_id=繁體中文】深度摘要。

    要求：
    1. 每個分類中的每一則新聞都必須輸出一筆摘要，id 必須與輸入資料 id 完全一致。
    2. 每個摘要都必須是【繁體中文】，內容專業且引人入勝，不可只是重述標題。
    3. 最後寫一段 100 字內的【繁體中文】今日精華導讀（overview）。
    4. 必須回傳純 JSON 格式，不得包含 Markdown 或其他解釋文字，格式如下：
    {
      "summaries": {
        "分類名": [
          {"id": 1, "note": "..."},
          {"id": 2, "note": "..."}
        ]
      },
      "overview": "..."
    }

    資料來源：
    """
    prompt = prompt + json.dumps(combined_payload, ensure_ascii=False)

    max_retries = 3
    retry_delay = 5
    target_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    gen_config = types.GenerateContentConfig(
        # 先移除 response_mime_type，避免部分端點將其序列化為
        # responseMimeType 後在 generation_config 觸發 400 INVALID_ARGUMENT。
        temperature=0.7,
    )

    for attempt in range(max_retries):
        try:
            print(f"📡 正在嘗試 AI 生成 (第 {attempt + 1}/{max_retries} 次)，模型：{target_model}...")

            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=gen_config,
            )

            raw_text = getattr(response, "text", None)
            if not raw_text:
                raise ValueError("AI 回傳內容為空")

            print("🧾 Gemini 原始 response.text：")
            print(raw_text)

            clean_json = _extract_json_text(raw_text)
            res_data = json.loads(clean_json)

            all_notes = {}
            for cat, items in categories_data.items():
                cat_notes = res_data.get("summaries", {}).get(cat, [])
                print(f"📦 [{cat}] 解析到 {len(cat_notes)} 筆摘要，預期 {len(items)} 筆。")
                all_notes[cat] = _build_note_mapping(cat_notes, len(items), cat)

            overview = res_data.get("overview", "").strip() if isinstance(res_data, dict) else ""
            if not overview:
                overview = "今日體育重點導讀已生成。"

            print("✅ AI 生成內容成功！")
            return all_notes, overview

        except json.JSONDecodeError as e:
            print(f"⚠️ 第 {attempt + 1} 次 JSON 解析失敗: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return {}, "今日焦點導讀：AI 回傳格式異常，稍後再試。"

        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ 第 {attempt + 1} 次嘗試失敗: {error_msg}")

            # 若 lite 模型暫不可用，回退到 flash 再試一次
            if ("404" in error_msg or "NOT_FOUND" in error_msg) and target_model == "gemini-2.5-flash-lite":
                target_model = "gemini-2.5-flash"
                print("   備援：改用 gemini-2.5-flash 後重試。")
                continue

            if "429" in error_msg:
                print(f"   原因：觸發 Quota 限制。等待 {retry_delay * 2} 秒後重試...")
                time.sleep(retry_delay * 2)
            elif attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print("❌ 已達到最大重試次數，AI 生成失敗。")
                return {}, f"今日焦點導讀（自動生成中）：{error_msg}"

    return {}, "今日焦點導讀：AI 生成暫時不可用。"
