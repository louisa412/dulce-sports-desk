import os
import requests
import feedparser


LINE_TOKEN = os.getenv("LINE_TOKEN")
USER_ID = os.getenv("USER_ID")


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


def fetch_entries(feed_url: str, limit: int = 12) -> list[dict]:
    feed = feedparser.parse(feed_url)
    items = []

    for entry in feed.entries[:limit]:
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()

        if not title:
            continue

        items.append({
            "title": title,
            "summary": summary,
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


def score_arsenal(title: str, summary: str) -> tuple[int, str]:
    text = f"{title} {summary}".lower()
    score = 0
    note = "一般更新"

    if any(k in text for k in ["injury", "injured", "fitness", "return", "recovery", "out for"]):
        score += 4
        note = "可能影響接下來的出賽與輪替"

    if any(k in text for k in ["transfer", "sign", "bid", "deal", "target"]):
        score += 3
        note = "與補強或陣容深度有關"

    if any(k in text for k in ["arteta", "press conference", "rotation", "lineup", "starting xi"]):
        score += 2
        note = "顯示近期先發安排可能調整"

    if any(k in text for k in ["champions league", "premier league", "title race"]):
        score += 2
        note = "與近期戰績或競爭局勢有關"

    return score, note


def score_spain(title: str, summary: str) -> tuple[int, str]:
    text = f"{title} {summary}".lower()
    score = 0
    note = "一般更新"

    if any(k in text for k in ["squad", "call-up", "called up", "selected", "selection"]):
        score += 4
        note = "與徵召名單或用人方向有關"

    if any(k in text for k in ["injury", "injured", "withdraw", "ruled out"]):
        score += 4
        note = "可能影響國家隊名單或輪替"

    if any(k in text for k in ["coach", "manager", "tactics", "formation"]):
        score += 2
        note = "與國家隊戰術安排有關"

    if any(k in text for k in ["qualifier", "nations league", "world cup", "euro"]):
        score += 2
        note = "與正式賽事備戰或結果有關"

    return score, note


def score_f1(title: str, summary: str) -> tuple[int, str]:
    text = f"{title} {summary}".lower()
    score = 0
    note = "一般更新"

    if any(k in text for k in ["ferrari", "leclerc", "charles leclerc"]):
        score += 2
        note = "與 Leclerc 或 Ferrari 動向直接相關"

    if any(k in text for k in ["qualifying", "grid", "pole", "practice", "race"]):
        score += 3
        note = "和本週比賽表現直接相關"

    if any(k in text for k in ["setup", "pace", "upgrade", "strategy", "tyre", "tire"]):
        score += 3
        note = "反映 Ferrari 當前競爭力與策略狀況"

    if any(k in text for k in ["penalty", "crash", "incident", "dnf"]):
        score += 4
        note = "屬於可能改變本站結果的重要事件"

    return score, note


def pick_top_news(entries: list[dict], scorer, top_n: int = 5) -> list[dict]:
    scored = []
    seen_titles = set()

    for entry in entries:
        title = entry["title"]

        if title in seen_titles:
            continue
        seen_titles.add(title)

        if looks_like_noise(title):
            continue

        score, note = scorer(entry["title"], entry["summary"])

        if score <= 0:
            continue

        scored.append({
            "title": entry["title"],
            "score": score,
            "note": note,
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
        lines.append(f"  → {item['note']}")

    return "\n".join(lines)


def build_overview(arsenal: list[dict], spain: list[dict], f1: list[dict]) -> str:
    counts = {
        "Arsenal": len(arsenal),
        "Spain": len(spain),
        "Ferrari / Leclerc": len(f1),
    }

    sorted_topics = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    if all(v == 0 for _, v in sorted_topics):
        return "👉 今日概況\n今天沒有抓到夠重要的明顯重點。"

    top_topic = sorted_topics[0][0]
    if len(sorted_topics) > 1 and sorted_topics[1][1] > 0:
        second_topic = sorted_topics[1][0]
        return f"👉 今日概況\n今天更新較多的是 {top_topic}，其次是 {second_topic}。"

    return f"👉 今日概況\n今天的主要更新集中在 {top_topic}。"


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

    arsenal_news = pick_top_news(arsenal_entries, score_arsenal, top_n=5)
    spain_news = pick_top_news(spain_entries, score_spain, top_n=5)
    f1_news = pick_top_news(f1_entries, score_f1, top_n=5)

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
