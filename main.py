import requests
import os
import feedparser

LINE_TOKEN = os.getenv("LINE_TOKEN")
USER_ID = os.getenv("USER_ID")

def send_line(message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "to": USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    requests.post(url, headers=headers, json=data)

def get_news(feed_url, limit=2):
    feed = feedparser.parse(feed_url)
    items = []
    for entry in feed.entries[:limit]:
        items.append(f"- {entry.title}")
    return items

def main():
    arsenal_feed = "https://news.google.com/rss/search?q=Arsenal&hl=en-US&gl=US&ceid=US:en"
    spain_feed = "https://news.google.com/rss/search?q=Spain+national+team&hl=en-US&gl=US&ceid=US:en"
    f1_feed = "https://news.google.com/rss/search?q=Leclerc+Ferrari&hl=en-US&gl=US&ceid=US:en"

    arsenal_news = get_news(arsenal_feed)
    spain_news = get_news(spain_feed)
    f1_news = get_news(f1_feed)

    message = "📊 Dulce's 運動快報\n\n"

    if arsenal_news:
        message += "⚽ Arsenal\n" + "\n".join(arsenal_news) + "\n\n"

    if spain_news:
        message += "🇪🇸 西班牙\n" + "\n".join(spain_news) + "\n\n"

    if f1_news:
        message += "🏎️ Leclerc / F1\n" + "\n".join(f1_news) + "\n\n"

    send_line(message)

if __name__ == "__main__":
    main()
