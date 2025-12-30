#!/usr/bin/env python3
"""
Feed RSS 自动刷新脚本 - 由 cron/PM2 调度运行
每 15 分钟执行一次
"""

import asyncio
import sys
import os
import logging
import uuid
import re
from datetime import datetime, timezone

# 添加项目路径
sys.path.insert(0, '/home/xinyue/vulcan-brain')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("FeedCron")

# 使用独立的 Motor 客户端
from motor.motor_asyncio import AsyncIOMotorClient
import feedparser

MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "vulcan_brain"
CACHE_COLLECTION = "feed_cache"

# RSSHub 镜像
RSSHUB_MIRRORS = [
    "https://rsshub.rssforever.com",
    "https://rsshub.app",
]

# RSS 信息源配置 (15个高质量源)
RSS_SOURCES = {
    # ===== Tier 1: 顶级商业分析 =====
    "stratechery": {"name": "Stratechery", "url": "https://stratechery.com/feed/", "tier": 1, "language": "en", "tags": ["深度分析", "科技战略"], "weight": 10},
    "mckinsey": {"name": "McKinsey Insights", "url": "https://www.mckinsey.com/insights/rss", "tier": 1, "language": "en", "tags": ["管理", "战略", "咨询"], "weight": 10},
    "hbr": {"name": "哈佛商业评论", "url": "http://feeds.harvardbusiness.org/harvardbusiness", "tier": 1, "language": "en", "tags": ["管理", "领导力", "战略"], "weight": 10},
    "future_a16z": {"name": "Future (a16z)", "url": "https://future.com/feed/", "tier": 1, "language": "en", "tags": ["VC洞察", "科技趋势"], "weight": 10},

    # ===== Tier 2: 融资与全球新闻 =====
    "crunchbase": {"name": "Crunchbase News", "url": "https://news.crunchbase.com/feed/", "tier": 2, "language": "en", "tags": ["融资", "创业", "VC"], "weight": 8},
    "techcrunch": {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "tier": 2, "language": "en", "tags": ["科技", "创业", "融资"], "weight": 8},
    "bloomberg_tech": {"name": "Bloomberg Tech", "url": "https://feeds.bloomberg.com/technology/news.rss", "tier": 2, "language": "en", "tags": ["科技", "市场", "融资"], "weight": 9},
    "reuters_world": {"name": "Reuters World", "url": "{RSSHUB}/reuters/world", "tier": 2, "language": "en", "tags": ["全球", "政治", "商业"], "weight": 9, "rsshub": True},
    "hn_best": {"name": "Hacker News Best", "url": "https://hnrss.org/best", "tier": 2, "language": "en", "tags": ["Tech", "趋势", "开发"], "weight": 7},

    # ===== Tier 3: 中文深度 =====
    "latepost_podcast": {"name": "晚点聊 LateTalk", "url": "https://feeds.fireside.fm/latetalk/rss", "tier": 3, "language": "zh", "tags": ["深度访谈", "科技", "创业"], "weight": 10},
    "caixin": {"name": "财新网", "url": "{RSSHUB}/caixin/latest", "tier": 3, "language": "zh", "tags": ["财经", "深度", "调查"], "weight": 9, "rsshub": True},
    "wallstreetcn": {"name": "华尔街见闻", "url": "{RSSHUB}/wallstreetcn/live/global", "tier": 3, "language": "zh", "tags": ["财经", "市场", "快讯"], "weight": 7, "rsshub": True},
    "36kr": {"name": "36氪", "url": "https://36kr.com/feed", "tier": 3, "language": "zh", "tags": ["科技", "创业"], "weight": 6},
    "huxiu": {"name": "虎嗅", "url": "https://www.huxiu.com/rss/0.xml", "tier": 3, "language": "zh", "tags": ["科技", "商业", "评论"], "weight": 6},

    # ===== Tier 4: 产品发现 =====
    "producthunt": {"name": "Product Hunt", "url": "https://www.producthunt.com/feed", "tier": 4, "language": "en", "tags": ["产品", "创新", "工具"], "weight": 5},
}

# 质量关键词
HIGH_VALUE_KEYWORDS = ["融资", "funding", "raised", "series", "估值", "valuation", "IPO", "战略", "strategy", "收购", "acquisition", "AI", "人工智能", "GPT"]
LOW_QUALITY_KEYWORDS = ["广告", "sponsored", "affiliate", "点击", "立即", "限时"]



def smart_sort_items(items: list) -> list:
    """智能排序: 时间优先 + 来源多样化交叉排列"""
    from datetime import datetime
    
    # 1. 先按发布时间排序 (最新优先)
    def get_timestamp(item):
        if item.get("published"):
            try:
                return datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
            except:
                pass
        return datetime.min
    
    items.sort(key=lambda x: get_timestamp(x), reverse=True)
    
    # 2. 交叉排列不同来源，避免同源聚集
    # 按来源分组
    by_source = {}
    for item in items:
        source = item["source_key"]
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(item)
    
    # 轮询交叉排列
    result = []
    source_queues = list(by_source.values())
    
    while source_queues:
        # 每轮从每个来源取一个
        empty_queues = []
        for i, queue in enumerate(source_queues):
            if queue:
                result.append(queue.pop(0))
            if not queue:
                empty_queues.append(i)
        
        # 移除空队列
        for i in reversed(empty_queues):
            source_queues.pop(i)
    
    return result

def calculate_quality_score(title: str, summary: str, source: dict) -> int:
    score = source.get("weight", 5) * 10
    text = f"{title} {summary}".lower()
    for kw in LOW_QUALITY_KEYWORDS:
        if kw.lower() in text: score -= 20
    for kw in HIGH_VALUE_KEYWORDS:
        if kw.lower() in text: score += 5
    if len(summary) > 500: score += 10
    if len(summary) > 1000: score += 10
    return max(0, min(100, score))


async def fetch_rss(source_key: str, source: dict) -> list:
    """获取单个 RSS 源"""
    items = []

    if source.get("rsshub"):
        # 尝试 RSSHub 镜像
        for mirror in RSSHUB_MIRRORS:
            url = source["url"].replace("{RSSHUB}", mirror)
            result = await _fetch_single(url, source, source_key)
            if result:
                items = result
                logger.info(f"[{source_key}] 从 {mirror} 获取 {len(items)} 条")
                break
    else:
        items = await _fetch_single(source["url"], source, source_key)
        if items:
            logger.info(f"[{source_key}] 获取 {len(items)} 条")

    return items


async def _fetch_single(url: str, source: dict, source_key: str) -> list:
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(
            None,
            lambda: feedparser.parse(url, agent="Mozilla/5.0 (compatible; VulcanBrain/1.0)")
        )

        if feed.bozo and not feed.entries:
            return []

        items = []
        for entry in feed.entries[:15]:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            link = entry.get("link", "")

            summary = re.sub(r'<[^>]+>', '', summary)[:500]
            quality_score = calculate_quality_score(title, summary, source)

            if quality_score < 30:
                continue

            published = None
            if entry.get("published_parsed"):
                published = datetime(*entry.published_parsed[:6])
            elif entry.get("updated_parsed"):
                published = datetime(*entry.updated_parsed[:6])

            items.append({
                "id": str(uuid.uuid4())[:8],
                "source_key": source_key,
                "source": source["name"],
                "tier": source["tier"],
                "title": title,
                "summary": summary,
                "url": link,
                "tags": source["tags"],
                "language": source.get("language", "en"),
                "quality_score": quality_score,
                "published": published.isoformat() if published else None,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            })

        return items
    except Exception as e:
        logger.warning(f"[{source_key}] 失败: {e}")
        return []


async def main():
    logger.info(f"[Cron] 开始刷新 {len(RSS_SOURCES)} 个信息源...")

    # 并发获取所有 RSS
    tasks = [fetch_rss(key, source) for key, source in RSS_SOURCES.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items = []
    for result in results:
        if isinstance(result, list):
            all_items.extend(result)

    # 排序
    all_items = smart_sort_items(all_items)

    logger.info(f"[Cron] 获取到 {len(all_items)} 条内容")

    if all_items:
        # 使用独立的 Motor 客户端写入
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]

        await db[CACHE_COLLECTION].update_one(
            {"type": "feed_items"},
            {"$set": {
                "type": "feed_items",
                "items": all_items,
                "cached_at": datetime.now(timezone.utc),
                "sources_count": len(RSS_SOURCES),
                "items_count": len(all_items)
            }},
            upsert=True
        )

        client.close()
        logger.info(f"[Cron] 缓存已更新")

        # 统计
        by_source = {}
        for item in all_items:
            by_source[item['source']] = by_source.get(item['source'], 0) + 1
        logger.info(f"[Cron] 来源统计: {by_source}")
    else:
        logger.warning("[Cron] 未获取到任何内容")


if __name__ == "__main__":
    asyncio.run(main())
