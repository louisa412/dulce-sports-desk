import feedparser
import re
from datetime import datetime, timedelta, timezone
from time import mktime
from html import unescape
from config import RECENT_HOURS, BACKFILL_HOURS, CATEGORY_NEWS_COUNT, SUMMARY_FALLBACK_TEXT

def strip_html(text):
    if not text: return ""
    cleaned = unescape(text)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"https?://\S+|www\.\S+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()

def split_title_and_source(raw_title):
    parts = raw_title.rsplit(" - ", 1)
    if len(parts) == 2:
        return strip_html(parts[0]), strip_html(parts[1])
    return strip_html(raw_title), "未知來源"

def fetch_entries(feed_url, limit=20):
    feed = feedparser.parse(feed_url)
    items = []
    for entry in feed.entries[:limit]:
        title, source = split_title_and_source(entry.get("title", ""))
        items.append({
            "title": title, "source": source, "link": entry.get("link", ""),
            "summary": strip_html(entry.get("summary", "")),
            "published_at": datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc) if entry.get("published_parsed") else None
        })
    return items

def score_arsenal(title, summary):
    text = f"{title} {summary}".lower()
    score = 0
    if any(k in text for k in ["injury", "injured", "fitness", "return"]): score += 4
    if any(k in text for k in ["transfer", "sign", "bid", "deal"]): score += 3
    if any(k in text for k in ["arteta", "press conference", "lineup"]): score += 2
    if any(k in text for k in ["arsenal", "gunners", "saka", "odegaard"]): score += 1
    return score

def score_spain(title, summary):
    text = f"{title} {summary}".lower()
    score = 0
    if any(k in text for k in ["squad", "call-up", "selected"]): score += 4
    if any(k in text for k in ["coach", "manager", "tactics"]): score += 2
    return score

def score_f1(title, summary):
    text = f"{title} {summary}".lower()
    score = 0
    if any(k in text for k in ["ferrari", "leclerc"]): score += 2
    if any(k in text for k in ["qualifying", "race", "pole"]): score += 3
    return score

def pick_top_news(entries, scorer, top_n=CATEGORY_NEWS_COUNT):
    recent, backfill = [], []
    seen = set()
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=RECENT_HOURS)
    cutoff_48h = now - timedelta(hours=BACKFILL_HOURS)

    for e in entries:
        if e["title"] in seen or e["published_at"] is None or e["published_at"] < cutoff_48h: continue
        seen.add(e["title"])
        score = scorer(e["title"], e["summary"])
        if score <= 0: continue
        e.update({"score": score, "freshness_label": "24h" if e["published_at"] >= cutoff_24h else "稍早"})
        (recent if e["published_at"] >= cutoff_24h else backfill).append(e)

    recent.sort(key=lambda x: (x["score"], x["published_at"]), reverse=True)
    backfill.sort(key=lambda x: (x["score"], x["published_at"]), reverse=True)
    res = recent[:top_n]
    if len(res) < top_n: res.extend(backfill[: top_n - len(res)])
    return res