#!/usr/bin/env python3
"""高端新闻聚合 - 硅谷视角 + 中国宏观"""

import feedparser
from datetime import datetime
from typing import List, Dict
import re
import time

# 高端信息源配置
RSS_FEEDS = {
    # 硅谷视角
    "Hacker News": "https://hnrss.org/frontpage?points=100",  # 100+赞的热门
    "TechCrunch": "https://techcrunch.com/feed/",
    # 中国宏观
    "财新": "https://rsshub.app/caixin/article",
    "第一财经": "https://rsshub.app/yicai/headline",
}

# 缓存
_news_cache = {"data": [], "timestamp": 0}
CACHE_TTL = 300

def _parse_time_ago(published: str) -> str:
    try:
        for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", 
                    "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                dt = datetime.strptime(published.replace("GMT", "+0000"), fmt)
                break
            except:
                continue
        else:
            return "刚刚"
        
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}天前"
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours}小时前"
        minutes = diff.seconds // 60
        return f"{minutes}分钟前" if minutes > 0 else "刚刚"
    except:
        return "刚刚"

def _clean_summary(summary: str, max_len: int = 120) -> str:
    clean = re.sub(r"<[^>]+>", "", summary)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_len] + "..." if len(clean) > max_len else clean

def _categorize(title: str, summary: str, source: str) -> str:
    text = (title + " " + summary).lower()
    
    # 硅谷源自动标记
    if source in ["Hacker News", "TechCrunch"]:
        if any(k in text for k in ["ai", "gpt", "llm", "openai", "anthropic", "model"]):
            return "AI"
        if any(k in text for k in ["funding", "raise", "series", "ipo", "valuation", "投资", "融资"]):
            return "融资"
        if any(k in text for k in ["startup", "founder", "yc", "创业"]):
            return "创业"
        return "硅谷"
    
    # 中国源
    if any(k in text for k in ["政策", "央行", "监管", "政府", "国务院"]):
        return "政策"
    if any(k in text for k in ["gdp", "经济", "增长", "通胀", "利率"]):
        return "宏观"
    if any(k in text for k in ["ai", "人工智能", "大模型"]):
        return "AI"
    if any(k in text for k in ["融资", "投资", "vc", "估值"]):
        return "融资"
    return "商业"

def fetch_news(limit: int = 10) -> List[Dict]:
    global _news_cache
    
    if time.time() - _news_cache["timestamp"] < CACHE_TTL and _news_cache["data"]:
        return _news_cache["data"][:limit]
    
    all_news = []
    
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                summary = _clean_summary(entry.get("summary", entry.get("description", "")))
                link = entry.get("link", "")
                published = entry.get("published", entry.get("updated", ""))
                
                all_news.append({
                    "title": title,
                    "summary": summary if summary else title[:100],
                    "category": _categorize(title, summary, source),
                    "url": link,
                    "timestamp": _parse_time_ago(published),
                    "source": source
                })
        except Exception as e:
            print(f"[News] Error fetching {source}: {e}")
    
    # 排序：优先最新
    def sort_key(item):
        ts = item["timestamp"]
        if "刚刚" in ts: return 0
        if "分钟" in ts: return 1
        if "小时" in ts: return 2
        return 3
    
    all_news.sort(key=sort_key)
    _news_cache = {"data": all_news, "timestamp": time.time()}
    
    return all_news[:limit]

if __name__ == "__main__":
    news = fetch_news(8)
    for n in news:
        print(f"[{n['source']}] [{n['category']}] {n['title'][:50]}...")
