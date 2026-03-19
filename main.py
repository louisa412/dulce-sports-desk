import os
import requests
import feedparser
from openai import OpenAI


LINE_TOKEN = os.getenv("LINE_TOKEN")
USER_ID = os.getenv("USER_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


def send_line(message: str) -> None:
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "to": USER_ID,
        "messages": [{"type": "text", "text": message}],
    }

    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()


def split_title_and_source(raw_title: str) -> tuple[str, str]:
    parts = raw_title.rsplit(" - ", 1)
    if len(parts) == 2:
        title, source = parts[0].strip(), parts[1].strip()
        return title, source
    return raw_title.strip(), "未知來源"


def fetch_entries(feed_url: str, limit: int = 12) -> list[dict]:
    feed = feedparser.parse(feed_url)
    items = []

    for entry in feed.entries[:limit]:
        raw_title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()
        link = entry.get("link", "").strip()

        if not raw_title:
            continue

        title, source = split_title_and_source(raw_title)

        items.append({
            "title": title,
            "summary": summary,
            "source": source,
            "link": link,
        })

    return items


def looks_like_noise(title: str) -> bool:
    noise_keywords = [
        "live",
        "watch",
        "stream",
        "tv channel",
        "how to watch",
        "odds",
        "betting",
        "prediction",
        "highlights",
        "player ratings",
        "quiz",
    ]
    lower_title = title.lower()
    return any(keyword in lower_title for keyword in noise_keywords)


def score_arsenal(title: str, summary: str) -> int:
    text = f"{title} {summary}".lower()
    score = 0

    if any(k in text for k in ["injury", "injured", "fitness", "return", "recovery", "out for"]):
        score += 4
    if any(k in text for k in ["transfer", "sign", "bid", "deal", "target"]):
        score += 3
    if any(k in text for k in ["arteta", "press conference", "rotation", "lineup", "starting xi"]):
        score += 2
    if any(k in text for k in ["champions league", "premier league", "title race"]):
        score += 2

    return score


def score_spain(title: str, summary: str) -> int:
    text = f"{title} {summary}".lower()
    score = 0

    if any(k in text for k in ["squad", "call-up", "called up", "selected", "selection"]):
        score += 4
    if any(k in text for k in ["injury", "injured", "withdraw", "ruled out"]):
        score += 4
    if any(k in text for k in ["coach", "manager", "tactics", "formation"]):
        score += 2
    if any(k in text for k in ["qualifier", "nations league", "world cup", "euro"]):
        score += 2

    return score


def score_f1(title: str, summary: str) -> int:
    text = f"{title} {summary}".lower()
    score = 0

    if any(k in text for k in ["ferrari", "leclerc", "charles leclerc"]):
        score += 2
    if any(k in text for k in ["qualifying", "grid", "pole", "practice", "race"]):
        score += 3
    if any(k in text for k in ["setup", "pace", "upgrade", "strategy", "tyre", "tire"]):
        score += 3
    if any(k in text for k in ["penalty", "crash", "incident", "dnf"]):
        score += 4

    return score


def ai_note(topic: str, title: str, summary: str) -> str:
    prompt = f"""
你是體育新聞編輯。請根據以下資訊，用繁體中文寫一句 18~28 字的「這代表什麼」。
要求：
1. 只寫一句
2. 不要重複標題
3. 不要寫得太空泛
4. 語氣像晨間快報編輯
5. 不要加引號

主題：{topic}
標題：{title}
摘要：{summary}
"""
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            max_output_tokens=60,
        )
        text = response.output_text.strip()
        return text if text else "代表近期動向值得留意"
    except Exception:
        return "代表近期動向值得留意"


def ai_overview(arsenal: list[dict], spain: list[dict], f1: list[dict]) -> str:
    def top_line(label: str, items: list[dict]) -> str:
        if not items:
            return f"{label}：今日無明顯重點"
        return f"{label}：{items[0]['title']}"

    prompt = f"""
你是晨間運動快報編輯。請根據以下三區最重要新聞，
用繁體中文寫 2 句內的今日精選摘要。
要求：
1. 精煉
2. 像人在整理重點
3. 不要條列
4. 不超過 60 字

{top_line("Arsenal", arsenal)}
{top_line("Spain", spain)}
{top_line("Leclerc / F1", f1)}
"""
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            max_output_tokens=80,
        )
        text = response.output_text.strip()
        return text if text else "今天的重點集中在最上方三則精選新聞。"
    except Exception:
        return "今天的重點集中在最上方三則精選新聞。"


def pick_top_news(entries: list[dict], topic: str, scorer, top_n: int = 5) -> list[dict]:
    scored = []
    seen_titles = set()

    for entry in entries:
        title = entry["title"]

        if title in seen_titles:
            continue
        seen_titles.add(title)

        if looks_like_noise(title):
            continue

        score = scorer(entry["title"], entry["summary"])
        if score <= 0:
            continue

        note = ai_note(topic, entry["title"], entry["summary"])

        scored.append({
            "title": entry["title"],
            "score": score,
            "note": note,
            "source": entry["source"],
            "link": entry["link"],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


def build_section(title: str, items: list[dict]) -> str:
    lines = [title]

    if not items:
        lines.append("- 今日暫無明顯重點")
        return "\n".join(lines)

    for item in items:
        lines.append(f"- {item['title']}")
        lines.append(f"  → {item['note']}｜{item['source']}")

    return "\n".join(lines)


def build_overview(arsenal: list[dict], spain: list[dict], f1: list[dict]) -> str:
    lines = ["👉 今日精選摘要"]
    lines.append(ai_overview(arsenal, spain, f1))
    lines.append("")

    if arsenal:
        lines.append(f"⚽ Arsenal：{arsenal[0]['title']}")
        lines.append(f"連結：{arsenal[0]['link']}")
    if spain:
        lines.append(f"🇪🇸 Spain：{spain[0]['title']}")
        lines.append(f"連結：{spain[0]['link']}")
    if f1:
        lines.append(f"🏎️ Leclerc / F1：{f1[0]['title']}")
        lines.append(f"連結：{f1[0]['link']}")

    if not arsenal and not spain and not f1:
        lines.append("今天沒有抓到夠重要的明顯重點。")

    return "\n".join(lines)


def main() -> None:
    arsenal_feed = (
        "https://news.google.com/rss/search?"
        "q=Arsenal&hl=en-US&gl=US&ceid=US:en"
    )
    spain_feed = (
        "https://news.google.com/rss/search?"
        "q=Spain+national+team+football&hl=en-US&gl=US&ceid=US:en"
    )
    f1_feed = (
        "https://news.google.com/rss/search?"
        "q=Charles+Leclerc+OR+Ferrari+F1&hl=en-US&gl=US&ceid=US:en"
    )

    arsenal_entries = fetch_entries(arsenal_feed, limit=12)
    spain_entries = fetch_entries(spain_feed, limit=12)
    f1_entries = fetch_entries(f1_feed, limit=12)

    arsenal_news = pick_top_news(arsenal_entries, "Arsenal", score_arsenal, top_n=5)
    spain_news = pick_top_news(spain_entries, "Spain", score_spain, top_n=5)
    f1_news = pick_top_news(f1_entries, "Leclerc / F1", score_f1, top_n=5)

    message_parts = [
        "📊 Dulce's Sports Desk｜今日運動快報",
        "",
        build_section("⚽ Arsenal", arsenal_news),
        "",
        build_section("🇪🇸 Spain", spain_news),
        "",
        build_section("🏎️ Leclerc / F1", f1_news),
        "",
        build_overview(arsenal_news, spain_news, f1_news),
    ]

    message = "\n".join(message_parts)

    if len(message) > 4500:
        message = message[:4400] + "\n...\n（內容過長，已截斷）"

    send_line(message)


if __name__ == "__main__":
    main()
