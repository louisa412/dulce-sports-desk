import json
from config import SECTION_TITLE_COLOR, SECTION_ACCENT_COLOR, OVERVIEW_ACCENT_COLOR

def build_news_item_component(item, index):
    return [
        {
            "type": "box", "layout": "baseline", "spacing": "sm",
            "contents": [
                {"type": "text", "text": item.get("freshness_label", ""), "size": "xxs", "color": "#D32F2F", "weight": "bold", "flex": 0},
                {"type": "text", "text": f"{index}. {item['title']}", "weight": "bold", "size": "sm", "wrap": True, "maxLines": 2, "flex": 1, "action": {"type": "uri", "uri": item["link"]}},
            ],
        },
        {
            "type": "text", 
            "text": item.get("note", item.get("summary", "閱讀更多內容")), 
            "size": "xs", "color": "#475569", "wrap": True, 
            "maxLines": 15,  # 提高到 15 行，確保長摘要必出
            "margin": "sm"
        },
        {"type": "button", "style": "link", "height": "sm", "action": {"type": "uri", "label": "閱讀原文", "uri": item["link"]}},
        {"type": "separator", "margin": "md"}
    ]

def build_overview_bubble(text, highlights):
    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": OVERVIEW_ACCENT_COLOR, "paddingAll": "16px",
            "contents": [{"type": "text", "text": "今日精華總覽", "weight": "bold", "size": "xl", "color": "#FFFFFF"}]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md", "paddingAll": "16px",
            "contents": [
                {
                    "type": "text", 
                    "text": text, 
                    "wrap": True, 
                    "maxLines": 15,  # 總覽導讀也要大空間
                    "size": "sm", "color": "#1E1B4B"
                }
            ]
        }
    }

def build_flex_messages(arsenal, spain, f1, overview_text):
    msgs = []
    # 各類別戰報
    for title, news in [("⚽ Arsenal", arsenal), ("🇪🇸 Spain", spain), ("🏎️ Leclerc / F1", f1)]:
        if news:
            bubble = build_section_bubble(title, news, SECTION_ACCENT_COLOR)
            msgs.append({"type": "flex", "altText": f"{title}摘要", "contents": bubble})
    
    # 今日精選摘要 (放在最後一張卡片)
    ov_bubble = build_overview_bubble(overview_text, [])
    msgs.append({"type": "flex", "altText": "今日精選摘要", "contents": ov_bubble})
    return msgs

def build_section_bubble(title, items, color):
    body = []
    for i, it in enumerate(items, 1):
        body.extend(build_news_item_component(it, i))
    if body and body[-1]["type"] == "separator": body.pop()
    
    return {
        "type": "bubble", "size": "giga",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": color, "paddingAll": "16px",
            "contents": [{"type": "text", "text": title, "weight": "bold", "size": "xl", "color": "#FFFFFF"}]
        },
        "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": body}
    }