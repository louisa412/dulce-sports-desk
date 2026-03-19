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


def fetch_titles(feed_url: str, limit: int = 2) -> list[str]:
    feed = feedparser.parse(feed_url)
    titles = []

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        if not title:
            continue

        if title not in titles:
            titles.append(title)

        if len(titles) >= limit:
            break

    return titles


def build_section(title: str, items: list[str]) -> str:
    if not items:
        return f"{title}\n- 今日暫無明顯更新\n"

    lines = [title]
    for item in items:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def build_overview(arsenal: list[str], spain: list[str], f1: list[str]) -> str:
    hot_topics = []

    if arsenal:
        hot_topics.append("Arsenal")
    if spain:
        hot_topics.append("Spain")
    if f1:
        hot_topics.append("Ferrari / Leclerc")

    if not hot_topics:
        return "👉 今日概況\n今天沒有抓到明顯重點新聞。"

    if len(hot_topics) == 1:
        return f"👉 今日概況\n今天的主要更新集中在 {hot_topics[0]}。"

    if len(hot_topics) == 2:
        return f"👉 今日概況\n今天較值得注意的是 {hot_topics[0]} 和 {hot_topics[1]}。"

    return "👉 今日概況\n今天 Arsenal、Spain、Ferrari / Leclerc 三邊都有更新，可以快速掃一輪。"


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

    arsenal_news = fetch_titles(arsenal_feed, limit=2)
    spain_news = fetch_titles(spain_feed, limit=2)
    f1_news = fetch_titles(f1_feed, limit=2)

    message_parts = [
        "📊 Dulce's Sports Desk｜今日運動快報\n",
        build_section("⚽ Arsenal", arsenal_news),
        build_section("🇪🇸 Spain", spain_news),
        build_section("🏎️ Leclerc / F1", f1_news),
        build_overview(arsenal_news, spain_news, f1_news),
    ]

    message = "\n".join(message_parts)

    # LINE 單則訊息長度有限，保守一點裁切
    if len(message) > 4500:
        message = message[:4400] + "\n...\n（內容過長，已截斷）"

    send_line(message)


if __name__ == "__main__":
    main()
