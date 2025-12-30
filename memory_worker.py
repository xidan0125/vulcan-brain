"""
Memory Extractor Worker - 独立微服务
Port 8003 - 同步调用 llama.cpp，不阻塞主 API
"""

from flask import Flask, request, jsonify
import requests
import json
import re
import os
import logging
from pymongo import MongoClient
from datetime import datetime, timezone

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MemoryWorker")

# 配置
LLAMA_URL = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8002/v1")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# MongoDB
mongo = MongoClient(MONGO_URI)
db = mongo.vulcan_brain

EXTRACTION_PROMPT = """从用户消息中提取值得记忆的信息。

## 记忆分层
- **core**: 核心记忆（名字、核心角色、语言偏好）
- **contextual**: 情境记忆（地域、兴趣、专业背景）
- **background**: 背景记忆（一次性事实）

## 示例
消息: "叫我老王就行"
输出: {{"extractions": [{{"key": "nickname", "value": "老王", "category": "identity", "tier": "core", "confidence": 0.95}}]}}

消息: "我是四川人"
输出: {{"extractions": [{{"key": "hometown", "value": "四川", "category": "identity", "tier": "contextual", "confidence": 0.9}}]}}

消息: "帮我查下天气"
输出: {{"extractions": []}}

---
当前消息: {message}

只输出 JSON (/no_think):
{{"extractions": [{{"key": "键名", "value": "值", "category": "identity|preference|fact", "tier": "core|contextual|background", "confidence": 0.9}}]}}
"""

SYSTEM_PROMPT = """You are a JSON extraction engine.
Rules:
- Output ONLY valid JSON
- No explanations, no thinking
- If nothing to extract, output {"extractions": []}
"""


def call_llama(message: str) -> list:
    """同步调用 llama.cpp"""
    prompt = EXTRACTION_PROMPT.format(message=message)

    try:
        resp = requests.post(
            f"{LLAMA_URL}/chat/completions",
            json={
                "model": "/home/xinyue/models/Qwen3-8B-Q4_K_M.gguf",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 300
            },
            timeout=120
        )
        resp.raise_for_status()

        content = resp.json()["choices"][0]["message"]["content"]

        # 处理 thinking 标签
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        content = re.sub(r"<think>\s*</think>\s*", "", content)

        # 提取 JSON
        if "```" in content:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)

        content = content.strip()
        if not content.startswith("{"):
            start = content.find("{")
            if start >= 0:
                content = content[start:]

        data = json.loads(content)
        return data.get("extractions", [])

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return []


def save_pending(user_id: str, session_id: str, extraction: dict, context: str):
    """保存到 pending_memories"""
    doc = {
        "user_id": user_id,
        "session_id": session_id,
        "key": extraction.get("key", "").strip().lower().replace(" ", "_"),
        "value": extraction.get("value", ""),
        "category": extraction.get("category", "fact"),
        "tier": extraction.get("tier", "contextual"),
        "confidence": float(extraction.get("confidence", 0.8)),
        "context": context,
        "status": "pending",
        "created_at": datetime.now(timezone.utc)
    }
    db.pending_memories.insert_one(doc)
    logger.info(f"Saved pending: {doc['key']}={doc['value']}")


@app.route("/extract", methods=["POST"])
def extract():
    """提取记忆并保存"""
    data = request.json
    message = data.get("message", "")
    user_id = data.get("user_id", "anonymous")
    session_id = data.get("session_id", "")

    # 跳过短消息
    if len(message.strip()) < 5:
        return jsonify({"status": "skipped", "reason": "too_short"})

    # 跳过问候/问句
    skip_patterns = [
        r"^(你好|hi|hello|hey|嗨|哈喽)",
        r"^(谢谢|thanks|thank you|好的|ok|行|嗯|哦)",
        r"\?$", r"？$"
    ]
    for pattern in skip_patterns:
        if re.match(pattern, message.strip().lower(), re.IGNORECASE):
            return jsonify({"status": "skipped", "reason": "greeting_or_question"})

    logger.info(f"Extracting from: {message[:50]}...")

    extractions = call_llama(message)

    for ext in extractions:
        if ext.get("key") and ext.get("value"):
            save_pending(user_id, session_id, ext, message)

    return jsonify({
        "status": "ok",
        "extracted": len(extractions),
        "keys": [e.get("key") for e in extractions]
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "memory-worker"})


if __name__ == "__main__":
    logger.info("Starting Memory Worker on port 8003")
    app.run(host="127.0.0.1", port=8003, threaded=True)
