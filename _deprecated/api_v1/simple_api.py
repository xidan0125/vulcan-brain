"""简单直连后端 - V2 智能风格"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3-thinking"

SYSTEM_PROMPT = """你是 Vulcan Brain - 一个兼具分析师洞察力、导师深度和顾问效率的高级 AI 助手。

【回答风格】
1. **结论先行**：先给出明确观点或答案
2. **多角度分析**：从不同维度剖析问题（技术/商业/风险）
3. **数据支撑**：尽可能引用具体数据、案例或趋势
4. **洞察提炼**：不只是信息罗列，要有独到见解
5. **结构清晰**：使用 bullet points 和小标题组织内容

【沟通原则】
- 像资深顾问一样：专业但不晦涩
- 像好导师一样：解释清楚"为什么"
- 像分析师一样：用证据说话

【格式要求】
- 重要结论用 **加粗**
- 复杂问题分层回答
- 适当使用类比帮助理解"""

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

def strip_think(text: str) -> str:
    result = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if not result or result == text:
        result = re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip()
    return result if result else "让我想想..."

@app.post("/api/agents/{agent_type}/chat")
async def chat(agent_type: str, req: ChatRequest):
    prompt = f"""{SYSTEM_PROMPT}

/no_think
用户问题: {req.message}

请按照上述风格回答："""

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/generate", json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 4096,
                "temperature": 0.7
            }
        })

        if resp.status_code != 200:
            return {"reply": "模型调用失败", "agent": agent_type, "session_id": "demo"}

        raw_response = resp.json().get("response", "")
        reply = strip_think(raw_response)

        return {
            "reply": reply,
            "agent": agent_type,
            "agent_name": "Vulcan Brain",
            "session_id": "demo"
        }

@app.get("/api/system/status")
async def status():
    return {"status": "ok", "model": MODEL}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
