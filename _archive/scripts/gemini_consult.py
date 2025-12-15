#!/usr/bin/env python3
"""
调用 Gemini API 进行架构咨询
"""
import json
import google.generativeai as genai
from pathlib import Path

# 配置
GEMINI_API_KEY = "AIzaSyBZpfHZtDajDj60ixhGLWulJSceRdf7Vpo"
MODEL_NAME = "gemini-2.0-flash-exp"  # 稳定版本

genai.configure(api_key=GEMINI_API_KEY)

def consult_gemini(file_path: str, analysis: str, question: str) -> str:
    """
    向 Gemini 咨询架构问题
    """
    # 读取文件
    content = Path(file_path).read_text(encoding='utf-8')
    
    prompt = f"""
你是一位资深 Python/FastAPI 架构师。请审核以下代码拆分方案。

## 当前文件
文件路径: {file_path}
文件大小: {len(content)} 字符, {len(content.splitlines())} 行

## 文件内容
```python
{content}
```

## Claude 的初步分析
{analysis}

## 问题
{question}

## 输出要求
请用中文回答，给出：
1. 对 Claude 方案的评价（优点/问题）
2. 你建议的拆分方案（如有不同）
3. 具体的目录结构
4. 拆分时需要注意的依赖关系和潜在风险
5. 建议的执行顺序（先拆哪个模块）
"""
    
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 4000
        }
    )
    
    return response.text


if __name__ == "__main__":
    analysis = """
api_server.py 包含 10+ 个功能模块：

| 模块 | 行数 | 功能 |
|------|------|------|
| FastAPI 初始化 | ~70 | 中间件、启动事件 |
| 全局状态管理 | ~120 | Kernel 实例、GPU 状态 |
| P0 核心对话 | ~125 | Chat stream SSE |
| P1 系统状态 | ~40 | Status、Health check |
| 代码执行 | ~70 | Sandbox API |
| P2 记忆系统 | ~80 | Memory API (AContext) |
| P3 知识库 | ~200 | Upload、RAG、LightRAG |
| P4 灵魂配置 | ~100 | Soul config CRUD |
| Agent Chat | ~170 | Agent 聊天、会话管理 |
| LOD Agent | ~90 | LOD 模式 Agent |
| MCP Protocol | ~80 | MCP 协议支持 |

我的初步拆分建议：
```
routers/
├── chat_router.py      # P0 核心对话
├── system_router.py    # P1 系统状态 + 健康检查
├── memory_router.py    # P2 记忆系统
├── knowledge_router.py # P3 知识库
├── soul_router.py      # P4 灵魂配置
├── agent_router.py     # Agent Chat + LOD
└── mcp_router.py       # MCP 协议
```
"""
    
    question = """
1. 这个拆分方案合理吗？有没有更好的组织方式？
2. 全局状态（kernel 实例、GPU 状态）应该怎么处理？
3. 有哪些模块之间有强依赖，不适合拆分？
4. 拆分后如何保持向后兼容（不破坏现有 API）？
"""
    
    print("正在咨询 Gemini...")
    result = consult_gemini(
        "/home/xinyue/vulcan-brain/api_server.py",
        analysis,
        question
    )
    print("\n" + "="*60)
    print("Gemini 架构建议")
    print("="*60 + "\n")
    print(result)
