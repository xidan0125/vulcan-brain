"""
Soul Feed API - 高质量信息流 + 知识卡片图像生成 (Gemini 3 Pro Image Preview)

CEO 决策辅助系统 - 高质量信息源聚合
自动化版本：后台定时刷新 + MongoDB 缓存
"""

import os
import json
import uuid
import base64
import logging
import asyncio
import feedparser
import re
import random
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bson import ObjectId
from contextlib import asynccontextmanager

from api.routers.auth_router import get_current_user
from vulcan_libs.store import store

logger = logging.getLogger("FeedAPI")

router = APIRouter(tags=["feed"])

# Static folder for generated card images
CARDS_DIR = "/home/xinyue/vulcan-brain/static/cards"
os.makedirs(CARDS_DIR, exist_ok=True)

# ==================== 自动化配置 ====================

REFRESH_INTERVAL_MINUTES = 15  # 每15分钟自动刷新
CACHE_COLLECTION = "feed_cache"  # MongoDB 缓存集合
CACHE_TTL_HOURS = 2  # 缓存有效期

# RSSHub 镜像列表 (按优先级排序)
RSSHUB_MIRRORS = [
    "https://rsshub.rssforever.com",
    "https://rsshub.app",
    "https://rss.shab.fun",
    "https://hub.slarker.me",
]


# ==================== Pydantic Models ====================

class CardGenerateRequest(BaseModel):
    url: Optional[str] = None
    content: Optional[str] = None
    news_id: Optional[str] = None
    style: Optional[str] = "infographic"


class CardInteractRequest(BaseModel):
    card_id: str
    action_type: str
    action_value: Optional[str] = None


# ==================== XP & 游戏化配置 ====================

XP_REWARDS = {
    "card_generated": 10,
    "card_interact": 5,
    "card_saved": 3,
    "daily_first_card": 20,
}

LEVEL_THRESHOLDS = [
    0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000, 5200,
    6500, 8000, 10000, 12500, 15500, 19000, 23000, 27500, 32500, 38000,
]

LEVEL_TITLES = {
    1: "实习生", 5: "经理", 10: "总监", 15: "VP", 20: "CEO", 25: "董事长"
}


def calculate_level(total_xp: int) -> int:
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if total_xp < threshold:
            return i
    return len(LEVEL_THRESHOLDS)


def get_level_title(level: int) -> str:
    for threshold_level in sorted(LEVEL_TITLES.keys(), reverse=True):
        if level >= threshold_level:
            return LEVEL_TITLES[threshold_level]
    return "新手"


# ==================== 高质量信息源配置 (15个源) ====================

RSS_SOURCES = {
    # ===== Tier 1: 顶级商业分析 =====
    "stratechery": {
        "name": "Stratechery",
        "url": "https://stratechery.com/feed/",
        "tags": ["深度分析", "科技战略"],
        "tier": 1,
        "language": "en",
        "description": "Ben Thompson 科技商业深度分析",
        "weight": 10
    },
    "mckinsey": {
        "name": "McKinsey Insights",
        "url": "https://www.mckinsey.com/insights/rss",
        "tags": ["管理", "战略", "咨询"],
        "tier": 1,
        "language": "en",
        "description": "麦肯锡管理洞见",
        "weight": 10
    },
    "hbr": {
        "name": "哈佛商业评论",
        "url": "http://feeds.harvardbusiness.org/harvardbusiness",
        "tags": ["管理", "领导力", "战略"],
        "tier": 1,
        "language": "en",
        "description": "HBR 管理与领导力洞见",
        "weight": 10
    },
    "future_a16z": {
        "name": "Future (a16z)",
        "url": "https://future.com/feed/",
        "tags": ["VC洞察", "科技趋势"],
        "tier": 1,
        "language": "en",
        "description": "a16z Future 编辑平台 - 科技趋势",
        "weight": 10
    },

    # ===== Tier 2: 融资与交易 =====
    "crunchbase": {
        "name": "Crunchbase News",
        "url": "https://news.crunchbase.com/feed/",
        "tags": ["融资", "创业", "VC"],
        "tier": 2,
        "language": "en",
        "description": "全球创业融资动态",
        "weight": 8
    },
    "techcrunch": {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "tags": ["科技", "创业", "融资"],
        "tier": 2,
        "language": "en",
        "description": "TechCrunch 科技创业新闻",
        "weight": 8
    },
    "bloomberg_tech": {
        "name": "Bloomberg Tech",
        "url": "https://feeds.bloomberg.com/technology/news.rss",
        "tags": ["科技", "市场", "融资"],
        "tier": 2,
        "language": "en",
        "description": "彭博科技新闻 (OpenAI/Waymo等重磅)",
        "weight": 9
    },
    "hn_best": {
        "name": "Hacker News Best",
        "url": "https://hnrss.org/best",
        "tags": ["Tech", "趋势", "开发"],
        "tier": 2,
        "language": "en",
        "description": "Hacker News 精选 (高赞内容)",
        "weight": 7
    },
    "reuters_tech": {
        "name": "Reuters Tech",
        "url": "{RSSHUB}/reuters/channel/tech",
        "tags": ["科技", "全球", "企业"],
        "tier": 2,
        "language": "en",
        "description": "路透社科技报道",
        "weight": 8,
        "rsshub": True
    },

    # ===== Tier 3: 中文深度 (via RSSHub) =====
    "latepost": {
        "name": "晚点LatePost",
        "url": "{RSSHUB}/latepost",
        "tags": ["深度报道", "互联网", "独家"],
        "tier": 3,
        "language": "zh",
        "description": "中国互联网深度独家报道",
        "weight": 9,
        "rsshub": True
    },
    "caixin": {
        "name": "财新网",
        "url": "{RSSHUB}/caixin/latest",
        "tags": ["财经", "深度", "调查"],
        "tier": 3,
        "language": "zh",
        "description": "财新网深度财经报道",
        "weight": 9,
        "rsshub": True
    },
    "wallstreetcn": {
        "name": "华尔街见闻",
        "url": "{RSSHUB}/wallstreetcn/live/global",
        "tags": ["财经", "市场", "快讯"],
        "tier": 3,
        "language": "zh",
        "description": "全球财经快讯",
        "weight": 7,
        "rsshub": True
    },
    "36kr": {
        "name": "36氪",
        "url": "https://36kr.com/feed",
        "tags": ["科技", "创业"],
        "tier": 3,
        "language": "zh",
        "description": "36氪科技创业",
        "weight": 6
    },
    "huxiu": {
        "name": "虎嗅",
        "url": "https://www.huxiu.com/rss/0.xml",
        "tags": ["科技", "商业", "评论"],
        "tier": 3,
        "language": "zh",
        "description": "虎嗅商业科技",
        "weight": 6
    },

    # ===== Tier 4: 产品发现 =====
    "producthunt": {
        "name": "Product Hunt",
        "url": "https://www.producthunt.com/feed",
        "tags": ["产品", "创新", "工具"],
        "tier": 4,
        "language": "en",
        "description": "最新产品发现",
        "weight": 5
    },
}

# 质量过滤关键词
LOW_QUALITY_KEYWORDS = [
    "广告", "sponsored", "affiliate", "点击", "立即", "限时",
    "免费领取", "抢购", "秒杀", "优惠券", "红包"
]

# 高价值关键词 (CEO 决策相关)
HIGH_VALUE_KEYWORDS = [
    # 融资
    "融资", "funding", "raised", "series", "估值", "valuation", "IPO",
    # 战略
    "战略", "strategy", "收购", "acquisition", "并购", "merger",
    # AI/Tech
    "AI", "人工智能", "GPT", "LLM", "机器学习", "AGI",
    # 市场
    "市场", "market", "增长", "growth", "营收", "revenue",
    # 管理
    "领导力", "leadership", "管理", "management", "组织",
]


def resolve_rsshub_url(url: str) -> str:
    """解析 RSSHub URL，选择可用镜像"""
    if "{RSSHUB}" in url:
        return url.replace("{RSSHUB}", RSSHUB_MIRRORS[0])
    return url


def calculate_quality_score(title: str, summary: str, source: dict) -> int:
    """计算内容质量分数"""
    score = source.get("weight", 5) * 10  # 基础分 (来源权重)

    text = f"{title} {summary}".lower()

    # 低质量内容扣分
    for keyword in LOW_QUALITY_KEYWORDS:
        if keyword.lower() in text:
            score -= 20

    # 高价值内容加分
    for keyword in HIGH_VALUE_KEYWORDS:
        if keyword.lower() in text:
            score += 5

    # 长度加分 (深度内容)
    if len(summary) > 500:
        score += 10
    if len(summary) > 1000:
        score += 10

    return max(0, min(100, score))




# ==================== 抓取文章全文 ====================
async def fetch_article_content(url: str, timeout: int = 10) -> str:
    """从URL抓取文章全文"""
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; VulcanBrain/1.0)"}
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # 移除无用标签
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
                tag.decompose()

            # 尝试找文章主体
            article = soup.find("article") or soup.find(class_=re.compile(r"article|content|post|entry", re.I)) or soup.find("main")

            if article:
                text = article.get_text(separator="\n", strip=True)
            else:
                body = soup.find("body")
                text = body.get_text(separator="\n", strip=True) if body else ""

            # 清理多余空行
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            text = "\n".join(lines)

            return text[:8000] if len(text) > 8000 else text

    except Exception as e:
        logger.warning(f"抓取文章失败 {url}: {e}")
        return ""

# ==================== RSS 获取与缓存 ====================

async def fetch_rss_with_fallback(source_key: str, source: dict) -> List[dict]:
    """获取 RSS，对 RSSHub 源尝试多个镜像"""
    items = []

    if source.get("rsshub"):
        # 尝试多个 RSSHub 镜像
        for mirror in RSSHUB_MIRRORS:
            url = source["url"].replace("{RSSHUB}", mirror)
            try:
                items = await fetch_single_rss(url, source, source_key)
                if items:
                    logger.info(f"[{source_key}] 成功从 {mirror} 获取 {len(items)} 条")
                    break
            except Exception as e:
                logger.warning(f"[{source_key}] {mirror} 失败: {e}")
                continue
    else:
        url = resolve_rsshub_url(source["url"])
        items = await fetch_single_rss(url, source, source_key)

    return items


async def fetch_single_rss(url: str, source: dict, source_key: str) -> List[dict]:
    """获取单个 RSS 源"""
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(
            None,
            lambda: feedparser.parse(url, agent="Mozilla/5.0 (compatible; VulcanBrain/1.0)")
        )

        if feed.bozo and not feed.entries:
            logger.warning(f"[{source_key}] RSS 解析错误: {feed.bozo_exception}")
            return []

        items = []
        for entry in feed.entries[:15]:  # 每源最多15条
            title = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            link = entry.get("link", "")

            # 清理 HTML
            summary = re.sub(r'<[^>]+>', '', summary)[:500]

            # 计算质量分
            quality_score = calculate_quality_score(title, summary, source)

            # 过滤低质量内容
            if quality_score < 30:
                continue

            # 解析时间
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
                "published_at": published.isoformat() if published else None,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            })

        return items

    except Exception as e:
        logger.error(f"[{source_key}] 获取失败: {e}")
        return []



def smart_sort_items(items: list) -> list:
    """智能排序: 时间优先 + 来源多样化交叉排列"""
    from datetime import datetime as dt
    
    # 1. 先按发布时间排序 (最新优先)
    def get_timestamp(item):
        if item.get("published_at"):
            try:
                pub = item["published_at"]
                if isinstance(pub, str):
                    return dt.fromisoformat(pub.replace("Z", "+00:00"))
            except:
                pass
        return dt.min
    
    items.sort(key=lambda x: get_timestamp(x), reverse=True)
    
    # 2. 交叉排列不同来源，避免同源聚集
    by_source = {}
    for item in items:
        source = item.get("source_key", item.get("source", "unknown"))
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(item)
    
    # 轮询交叉排列
    result = []
    source_queues = list(by_source.values())
    
    while source_queues:
        empty_queues = []
        for i, queue in enumerate(source_queues):
            if queue:
                result.append(queue.pop(0))
            if not queue:
                empty_queues.append(i)
        for i in reversed(empty_queues):
            source_queues.pop(i)
    
    return result


async def fetch_all_feeds() -> List[dict]:
    """并发获取所有 RSS 源"""
    tasks = []
    for key, source in RSS_SOURCES.items():
        tasks.append(fetch_rss_with_fallback(key, source))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items = []
    for result in results:
        if isinstance(result, list):
            all_items.extend(result)
        elif isinstance(result, Exception):
            logger.error(f"RSS 任务异常: {result}")

    # 智能排序: 时间优先 + 来源交叉
    all_items = smart_sort_items(all_items)

    return all_items


# ==================== 缓存管理 ====================

async def get_cached_feed() -> Optional[List[dict]]:
    """从 MongoDB 获取缓存的 feed"""
    try:
        db = store.db
        cache = await db[CACHE_COLLECTION].find_one({"type": "feed_items"})

        if cache:
            cached_at = cache.get("cached_at")
            if cached_at:
                # 检查缓存是否过期
                if isinstance(cached_at, str):
                    cached_at = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))

                age = datetime.now(timezone.utc) - cached_at.replace(tzinfo=timezone.utc)
                if age < timedelta(hours=CACHE_TTL_HOURS):
                    logger.info(f"[Cache] 命中缓存，{len(cache.get('items', []))} 条，年龄 {age.total_seconds()//60:.0f} 分钟")
                    return cache.get("items", [])
                else:
                    logger.info(f"[Cache] 缓存过期，年龄 {age.total_seconds()//60:.0f} 分钟")

        return None
    except Exception as e:
        logger.error(f"[Cache] 读取缓存失败: {e}")
        return None


async def update_feed_cache(items: List[dict]):
    """更新 MongoDB 缓存"""
    try:
        db = store.db
        await db[CACHE_COLLECTION].update_one(
            {"type": "feed_items"},
            {"$set": {
                "type": "feed_items",
                "items": items,
                "cached_at": datetime.now(timezone.utc),
                "sources_count": len(RSS_SOURCES),
                "items_count": len(items)
            }},
            upsert=True
        )
        logger.info(f"[Cache] 缓存已更新，{len(items)} 条内容")
    except Exception as e:
        logger.error(f"[Cache] 更新缓存失败: {e}")


async def get_feed_with_cache() -> List[dict]:
    """获取 feed，优先使用缓存"""
    # 尝试从缓存获取
    cached = await get_cached_feed()
    if cached:
        return cached

    # 缓存未命中，实时获取
    logger.info("[Cache] 缓存未命中，实时获取...")
    items = await fetch_all_feeds()

    # 更新缓存
    if items:
        await update_feed_cache(items)

    return items


# ==================== 后台定时刷新 ====================

_scheduler_started = False
_scheduler_lock = threading.Lock()


def start_background_scheduler():
    """启动后台定时刷新任务"""
    global _scheduler_started

    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    async def refresh_task():
        """定时刷新任务"""
        while True:
            try:
                logger.info(f"[Scheduler] 开始自动刷新 RSS ({len(RSS_SOURCES)} 个源)...")
                items = await fetch_all_feeds()

                if items:
                    await update_feed_cache(items)
                    logger.info(f"[Scheduler] 自动刷新完成，{len(items)} 条内容")
                else:
                    logger.warning("[Scheduler] 自动刷新返回空结果")

            except Exception as e:
                logger.error(f"[Scheduler] 自动刷新失败: {e}")

            # 等待下次刷新
            await asyncio.sleep(REFRESH_INTERVAL_MINUTES * 60)

    def run_scheduler():
        """在新线程中运行调度器"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(refresh_task())

    # 启动后台线程
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info(f"[Scheduler] 后台刷新已启动，间隔 {REFRESH_INTERVAL_MINUTES} 分钟")




# ==================== Gemini 图像生成 ====================

async def generate_card_image_gemini(title: str, insights: List[str], key_data: List[dict], tags: List[str] = None) -> Optional[str]:
    """使用 Gemini 生成高质量知识卡片图像 - 专业信息图设计"""
    try:
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY 未设置")
            return None

        client = genai.Client(api_key=api_key)

        # 构建数据文本
        data_section = ""
        if key_data:
            data_items = []
            for d in key_data:
                trend_icon = "↑" if d.get("trend") == "up" else "↓" if d.get("trend") == "down" else "→"
                data_items.append(f"{d['label']}: {d['value']} {trend_icon}")
            data_section = "\n".join(data_items)

        insights_section = "\n".join([f"• {i}" for i in insights]) if insights else ""
        tags_section = " | ".join(tags[:4]) if tags else ""

        # 漫画风格知识卡片 prompt
        prompt = f"""Create a visually engaging COMIC-STYLE knowledge card that explains complex concepts through creative visual metaphors.

CONTENT TO VISUALIZE:
Title: {title}
Key Data: {data_section if data_section else "N/A"}  
Core Insights: {insights_section if insights_section else "N/A"}
Topic Tags: {tags_section if tags_section else "Business"}

VISUAL STYLE (1024x768px landscape):
- Style: Japanese manga / comic book hybrid with modern flat design elements
- Color palette: Deep black background (#0a0a0a) with vibrant orange (#FF6B35) and cyan (#00D4FF) accents
- Use VISUAL METAPHORS to represent abstract concepts (e.g., data growth = rocket launching, competition = race track, risk = tightrope)

LAYOUT - Comic Panel Design:
- Main panel (60% width): Hero illustration showing the core concept as a dynamic scene with characters/objects
- Side panels (40% width): 2-3 smaller panels showing key data points with creative icons
- Title: Bold manga-style lettering with speed lines or emphasis effects
- Speech bubbles or callout boxes for key insights
- Small mascot character in corner reacting to the information

CREATIVE REQUIREMENTS:
1. DO NOT just display text and numbers - VISUALIZE them creatively
2. Use expressive cartoon characters, objects, or scenes to represent business concepts
3. Add manga-style effects: speed lines, impact stars, emotion symbols
4. Include visual humor or clever metaphors that make complex ideas memorable
5. Text should be minimal - let the visuals tell the story
6. Halftone dot shading for depth, bold black outlines
7. Dynamic composition with diagonal elements and varied panel sizes

Example approaches:
- "Market growth" → Rocket ship with data trails
- "Competition" → Characters racing on a track  
- "Risk vs Reward" → Tightrope walker over city
- "Data analysis" → Detective with magnifying glass examining charts
- "AI/Tech" → Friendly robot character explaining concepts

Make it fun, memorable, and instantly understandable at a glance!"""

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=0.8,
            )
        )

        # 提取图像
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_data = part.inline_data.data
                image_id = str(uuid.uuid4())[:8]
                image_path = f"{CARDS_DIR}/{image_id}.png"

                with open(image_path, "wb") as f:
                    f.write(image_data)

                logger.info(f"高质量图像已生成: {image_path}, 大小: {len(image_data)} bytes")
                return image_id

        return None

    except Exception as e:
        logger.error(f"Gemini 图像生成失败: {e}")
        return None


async def generate_image_async(card_id: str, title: str, insights: List[str], key_data: List[dict], tags: List[str]):
    """异步生成图片并更新数据库"""
    try:
        image_id = await generate_card_image_gemini(title, insights, key_data, tags)
        if image_id:
            db = store.db
            await db.knowledge_cards.update_one(
                {"card_id": card_id},
                {"$set": {
                    "card_type": "image",
                    "image_id": image_id,
                    "image_url": f"/static/cards/{image_id}.png",
                    "image_generated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            logger.info(f"卡片 {card_id} 图片已异步生成: {image_id}")
    except Exception as e:
        logger.error(f"异步图片生成失败: {e}")


@router.get("/api/feed")
async def get_feed(
    limit: int = 20,
    offset: int = 0,
    tier: Optional[int] = None,
    tag: Optional[str] = None,
    language: Optional[str] = None,
    user=Depends(get_current_user)
):
    """获取高质量信息流 (使用缓存)"""
    try:
        # 使用缓存获取
        items = await get_feed_with_cache()

        # 过滤
        if tier:
            items = [i for i in items if i["tier"] == tier]
        if tag:
            items = [i for i in items if tag in i["tags"]]
        if language:
            items = [i for i in items if i["language"] == language]

        # 去重 (基于标题相似度)
        seen_titles = set()
        unique_items = []
        for item in items:
            title_key = item["title"][:30].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_items.append(item)

        total = len(unique_items)
        items = unique_items[offset:offset + limit]

        return {
            "items": items,
            "total": total,
            "has_more": offset + limit < total,
            "sources_count": len(RSS_SOURCES),
            "cached": True,
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"获取 feed 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/feed/sources")
async def get_feed_sources(user=Depends(get_current_user)):
    """获取所有信息源列表"""
    sources = []
    for key, source in RSS_SOURCES.items():
        sources.append({
            "key": key,
            "name": source["name"],
            "description": source["description"],
            "tier": source["tier"],
            "language": source["language"],
            "tags": source["tags"],
            "weight": source.get("weight", 5)
        })

    sources.sort(key=lambda x: (x["tier"], -x["weight"]))
    return {"sources": sources, "total": len(sources)}


@router.get("/api/feed/tags")
async def get_feed_tags(user=Depends(get_current_user)):
    """获取所有可用标签"""
    tag_counts = {}
    for source in RSS_SOURCES.values():
        for tag in source["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # 返回与 /api/user/tags 相同的格式
    tags = [
        {"name": tag, "count": count}
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])
    ]
    return {"tags": tags, "total": len(tags)}


@router.post("/api/feed/refresh")
async def refresh_feed(user=Depends(get_current_user)):
    """手动强制刷新 RSS 缓存"""
    try:
        logger.info("[Manual] 手动触发刷新...")
        items = await fetch_all_feeds()

        if items:
            await update_feed_cache(items)

        return {
            "success": True,
            "items_count": len(items),
            "message": f"已刷新 {len(RSS_SOURCES)} 个信息源，获取 {len(items)} 条内容"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/feed/cache-status")
async def get_cache_status(user=Depends(get_current_user)):
    """获取缓存状态"""
    try:
        db = store.db
        cache = await db[CACHE_COLLECTION].find_one({"type": "feed_items"})

        if cache:
            cached_at = cache.get("cached_at")
            if isinstance(cached_at, str):
                cached_at = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))

            age_seconds = (datetime.now(timezone.utc) - cached_at.replace(tzinfo=timezone.utc)).total_seconds()

            return {
                "cached": True,
                "items_count": cache.get("items_count", 0),
                "sources_count": cache.get("sources_count", 0),
                "cached_at": cached_at.isoformat(),
                "age_minutes": round(age_seconds / 60, 1),
                "refresh_interval_minutes": REFRESH_INTERVAL_MINUTES,
                "next_refresh_in_minutes": max(0, round(REFRESH_INTERVAL_MINUTES - age_seconds / 60, 1))
            }

        return {
            "cached": False,
            "message": "缓存为空，首次访问将触发刷新"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/feed/stats")
async def get_feed_stats(user=Depends(get_current_user)):
    """获取信息流统计"""
    try:
        items = await get_feed_with_cache()

        # 按来源统计
        by_source = {}
        by_tier = {1: 0, 2: 0, 3: 0, 4: 0}
        by_language = {"en": 0, "zh": 0}

        for item in items:
            source = item["source"]
            by_source[source] = by_source.get(source, 0) + 1
            by_tier[item["tier"]] = by_tier.get(item["tier"], 0) + 1
            by_language[item["language"]] = by_language.get(item["language"], 0) + 1

        # 获取用户 XP 数据
        db = store.db
        user_id = user.get("user_id") or user.get("username")
        xp_doc = await db.user_xp.find_one({"user_id": user_id})
        total_xp = xp_doc.get("total_xp", 0) if xp_doc else 0
        level = calculate_level(total_xp)
        level_title = get_level_title(level)
        next_level_xp = LEVEL_THRESHOLDS[level] if level < len(LEVEL_THRESHOLDS) else None
        xp_to_next = (next_level_xp - total_xp) if next_level_xp else 0
        streak_days = xp_doc.get("streak_days", 0) if xp_doc else 0

        return {
            "total_items": len(items),
            "total_sources": len(RSS_SOURCES),
            "by_source": by_source,
            "by_tier": by_tier,
            "by_language": by_language,
            "tier_names": {
                1: "顶级商业分析",
                2: "融资与交易",
                3: "中文深度",
                4: "产品发现"
            },
            "auto_refresh": {
                "enabled": True,
                "interval_minutes": REFRESH_INTERVAL_MINUTES
            },
            "user_stats": {
                "total_xp": total_xp,
                "level": level,
                "level_title": level_title,
                "streak_days": streak_days,
                "next_level_xp": next_level_xp,
                "xp_to_next_level": xp_to_next
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/card/generate")
async def generate_card(
    request: CardGenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """生成知识卡片 - 优化版: 缓存 + 先文本后图片"""
    try:
        db = store.db
        news_id = request.news_id

        # 1. 检查缓存 - 如果已生成过，直接返回
        if news_id:
            existing = await db.knowledge_cards.find_one({"news_id": news_id})
            if existing:
                existing.pop("_id", None)
                logger.info(f"命中卡片缓存 (by news_id): {news_id}")
                return {"card": existing, "cached": True, "xp_gained": None}

        content = request.content or ""
        source_url = request.url
        item_tags = []
        item_title = ""

        # 2. 获取文章内容
        if news_id:
            items = await get_feed_with_cache()
            for item in items:
                if item["id"] == news_id:
                    source_url = item.get("url", "")
                    item_tags = item.get("tags", [])
                    item_title = item.get("title", "")

                    # 备用缓存检查: 按 source_url 查找 (老卡片可能没有 news_id)
                    if source_url:
                        existing = await db.knowledge_cards.find_one({"source_url": source_url})
                        if existing:
                            # 更新老记录，补上 news_id
                            await db.knowledge_cards.update_one(
                                {"_id": existing["_id"]},
                                {"$set": {"news_id": news_id}}
                            )
                            existing.pop("_id", None)
                            existing["news_id"] = news_id
                            logger.info(f"命中卡片缓存 (by source_url): {source_url[:50]}")
                            return {"card": existing, "cached": True, "xp_gained": None}
                    # 先用摘要快速响应，全文可以后台补充
                    content = f"{item['title']}\n\n{item.get('summary', '')}"
                    # 尝试抓取全文 (限时3秒)
                    try:
                        article = await asyncio.wait_for(
                            fetch_article_content(source_url),
                            timeout=3.0
                        )
                        if article and len(article) > len(item.get('summary', '')):
                            content = f"{item['title']}\n\n{article}"
                    except asyncio.TimeoutError:
                        logger.info("全文抓取超时，使用摘要")
                    break

        if not content:
            raise HTTPException(status_code=400, detail="需要提供 content 或 news_id")

        # 3. 快速分析 (使用 flash 模型)
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY 未设置")

        client = genai.Client(api_key=api_key)

        analysis_prompt = f"""你是资深商业分析师。深度分析以下内容。

内容:
{content[:3000]}

返回 JSON (严格遵守格式):
{{
    "title": "中文标题 (10-15字)",
    "summary": "2-3句话的核心摘要，概括最重要的信息和意义",
    "key_data": [
        {{"label": "指标", "value": "具体数值或事实", "trend": "up/down/neutral"}}
    ],
    "insights": ["深度洞见1", "洞见2", "洞见3"],
    "tags": ["标签1", "标签2", "标签3"],
    "vocab": [
        {{"word": "英文单词", "phonetic": "音标", "meaning": "中文释义", "example": "文中例句或常用搭配"}}
    ],
    "interaction": {{
        "enabled": true,
        "type": "agree_disagree",
        "question": "你对此有何看法?",
        "options": ["看好", "观望", "看空"]
    }}
}}

要求:
- summary 是全文最核心的2-3句话总结
- key_data 必须是文中的具体数字或事实
- insights 是分析而非复述
- 找不到数据就用定性描述
- vocab 提取3-5个文章中的高价值商业/科技英文词汇，适合职场人士学习"""

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=analysis_prompt
        )

        json_match = re.search(r'\{[\s\S]*\}', response.text)
        if not json_match:
            raise HTTPException(status_code=500, detail="AI 响应解析失败")

        card_data = json.loads(json_match.group())
        card_id = str(uuid.uuid4())[:8]

        # 合并标签
        all_tags = list(set(card_data.get("tags", []) + item_tags))[:6]

        # 4. 立即返回文本卡片
        card = {
            "card_id": card_id,
            "news_id": news_id,
            "card_type": "text",
            "image_id": None,
            "image_url": None,
            "title": card_data.get("title", "知识卡片"),
            "summary": card_data.get("summary", ""),
            "key_data": card_data.get("key_data", []),
            "insights": card_data.get("insights", []),
            "tags": all_tags,
            "vocab": card_data.get("vocab", []),
            "interaction": card_data.get("interaction", {
                "enabled": True,
                "type": "agree_disagree",
                "question": "这个信息有价值吗?",
                "options": ["有价值", "一般", "没价值"]
            }),
            "source_url": source_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_id": str(user["user_id"])
        }

        await db.knowledge_cards.insert_one(card.copy())

        # 5. 后台异步生成图片
        if request.style == "infographic":
            background_tasks.add_task(
                generate_image_async,
                card_id,
                card["title"],
                card["insights"],
                card["key_data"],
                all_tags
            )

        # 6. 奖励 XP
        xp_result = await award_xp(user["user_id"], "card_generated")

        card.pop("_id", None)
        card.pop("user_id", None)

        return {
            "card": card,
            "xp_gained": xp_result
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析错误: {e}")
        raise HTTPException(status_code=500, detail="AI 响应格式错误")
    except Exception as e:
        logger.error(f"生成卡片失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/api/card/history")
async def get_card_history(
    limit: int = 10,
    user=Depends(get_current_user)
):
    """获取用户生成的卡片历史"""
    try:
        db = store.db
        cards = await db.knowledge_cards.find(
            {"user_id": str(user["user_id"])}
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
        
        # 转换 ObjectId 为字符串
        for card in cards:
            if "_id" in card:
                del card["_id"]
        
        return {"cards": cards, "total": len(cards)}
    except Exception as e:
        logger.error(f"获取卡片历史失败: {e}")
        return {"cards": [], "total": 0}


@router.get("/api/card/{card_id}")
async def get_card(card_id: str, user=Depends(get_current_user)):
    """获取卡片详情 (轮询检查图片是否生成完成)"""
    try:
        db = store.db
        card = await db.knowledge_cards.find_one({"card_id": card_id})
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        card.pop("_id", None)
        return {"card": card}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/card/interact")
async def interact_card(request: CardInteractRequest, user=Depends(get_current_user)):
    """记录卡片交互"""
    try:
        db = store.db

        # 记录交互
        await db.card_interactions.insert_one({
            "card_id": request.card_id,
            "user_id": str(user["user_id"]),
            "action_type": request.action_type,
            "action_value": request.action_value,
            "created_at": datetime.now(timezone.utc)
        })

        # 奖励 XP
        xp_result = await award_xp(user["user_id"], "card_interact")

        return {
            "success": True,
            "xp_gained": xp_result
        }

    except Exception as e:
        logger.error(f"记录交互失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/card/save/{card_id}")
async def save_card(card_id: str, request: Request, user=Depends(get_current_user)):
    """收藏卡片 - 只保存用户选中的标签"""
    try:
        db = store.db
        
        # 获取用户选中的标签
        body = await request.json()
        selected_tags = body.get("tags", [])
        
        if not selected_tags:
            raise HTTPException(status_code=400, detail="请选择至少一个标签")
        
        # 获取完整卡片数据
        card = await db.knowledge_cards.find_one({"card_id": card_id})
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        
        # 构建保存数据 - 只保存用户选中的标签
        save_data = {
            "card_id": card_id,
            "user_id": str(user["user_id"]),
            "title": card.get("title", ""),
            "card_type": card.get("card_type", "text"),
            "image_url": card.get("image_url"),
            "key_data": card.get("key_data", []),
            "insights": card.get("insights", []),
            "tags": selected_tags,  # 用户选中的标签
            "source_url": card.get("source_url"),
            "news_id": card.get("news_id"),
            "saved_at": datetime.now(timezone.utc)
        }
        
        await db.saved_cards.update_one(
            {"card_id": card_id, "user_id": str(user["user_id"])},
            {"$set": save_data},
            upsert=True
        )
        
        logger.info(f"卡片已收藏: {card_id}, 用户选中标签: {selected_tags}")

        # 奖励 XP
        xp_result = await award_xp(user["user_id"], "card_saved")

        return {
            "success": True,
            "xp_gained": xp_result,
            "tags": selected_tags
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"收藏失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/user/tags")
async def get_user_tags(user=Depends(get_current_user)):
    """获取用户的标签库 - 从已保存的卡片中聚合"""
    try:
        db = store.db
        user_id = str(user["user_id"])
        
        # 聚合用户所有保存卡片的标签
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 50}
        ]
        
        cursor = db.saved_cards.aggregate(pipeline)
        tags = []
        async for doc in cursor:
            tags.append({"name": doc["_id"], "count": doc["count"]})
        
        return {"tags": tags, "total": len(tags)}
    
    except Exception as e:
        logger.error(f"获取用户标签失败: {e}")
        return {"tags": [], "total": 0}


@router.get("/api/user/xp")
async def get_user_xp(user=Depends(get_current_user)):
    """获取用户 XP 和等级"""
    try:
        db = store.db
        user_id = str(user["user_id"])

        xp_doc = await db.user_xp.find_one({"user_id": user_id})

        if not xp_doc:
            xp_doc = {
                "user_id": user_id,
                "total_xp": 0,
                "streak_days": 0,
                "last_activity": None
            }

        level = calculate_level(xp_doc.get("total_xp", 0))

        return {
            "total_xp": xp_doc.get("total_xp", 0),
            "level": level,
            "level_title": get_level_title(level),
            "streak_days": xp_doc.get("streak_days", 0),
            "next_level_xp": LEVEL_THRESHOLDS[level] if level < len(LEVEL_THRESHOLDS) else None
        }

    except Exception as e:
        logger.error(f"获取 XP 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def award_xp(user_id, action: str) -> dict:
    """奖励 XP"""
    try:
        db = store.db
        user_id_str = str(user_id)

        xp_amount = XP_REWARDS.get(action, 0)
        if not xp_amount:
            return {"xp_gained": 0, "total_xp": 0, "level": 1, "level_title": "新手", "level_up": False}

        # 获取当前 XP
        xp_doc = await db.user_xp.find_one({"user_id": user_id_str})
        old_xp = xp_doc.get("total_xp", 0) if xp_doc else 0
        old_level = calculate_level(old_xp)

        # 检查连续天数和每日首次奖励
        bonus_xp = 0
        streak_days = xp_doc.get("streak_days", 0) if xp_doc else 0
        last_activity = xp_doc.get("last_activity") if xp_doc else None

        now = datetime.now(timezone.utc)
        today = now.date()

        if last_activity:
            last_date = last_activity.date() if isinstance(last_activity, datetime) else last_activity
            if last_date == today - timedelta(days=1):
                streak_days += 1
                bonus_xp = min(streak_days * 2, 20)  # 连续奖励
            elif last_date != today:
                streak_days = 1
        else:
            streak_days = 1

        # 每日首次卡片奖励
        today_cards = await db.card_interactions.count_documents({
            "user_id": user_id_str,
            "created_at": {"$gte": datetime.combine(today, datetime.min.time())}
        })
        if today_cards == 0:
            bonus_xp += XP_REWARDS.get("daily_first_card", 0)

        total_gained = xp_amount + bonus_xp
        new_xp = old_xp + total_gained
        new_level = calculate_level(new_xp)

        # 更新数据库
        await db.user_xp.update_one(
            {"user_id": user_id_str},
            {"$set": {
                "total_xp": new_xp,
                "streak_days": streak_days,
                "last_activity": now
            }},
            upsert=True
        )

        return {
            "xp_gained": xp_amount,
            "bonus_xp": bonus_xp,
            "total_xp": new_xp,
            "level": new_level,
            "level_title": get_level_title(new_level),
            "level_up": new_level > old_level,
            "streak_days": streak_days
        }

    except Exception as e:
        logger.error(f"奖励 XP 失败: {e}")
        return {"xp_gained": 0, "total_xp": 0, "level": 1, "level_title": "新手", "level_up": False}


# Serve static card images
@router.get("/static/cards/{image_id}.png")
async def serve_card_image(image_id: str):
    """返回生成的卡片图像"""
    image_path = f"{CARDS_DIR}/{image_id}.png"
    if os.path.exists(image_path):
        return FileResponse(image_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Image not found")


# ==================== Card History ====================

