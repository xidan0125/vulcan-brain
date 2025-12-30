"""
Vulcan Brain API - Agent 路由
Agent Chat API + LOD Agent
"""
import json
import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import LLM_MODEL_NAME
from agent_prompts import AGENT_PROMPTS, AGENT_METADATA, get_agent_prompt, list_agents
from agent_session_store import get_agent_session, save_agent_session, delete_agent_session, list_user_sessions
from api.dependencies import get_kernel
from api.routers.auth_router import get_current_user

router = APIRouter(tags=["Agents"])


# === Pydantic Models ===
class AgentChatRequest(BaseModel):
    """Agent聊天请求"""
    message: str
    session_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    """Agent聊天响应"""
    reply: str
    agent: str
    agent_name: str
    session_id: str


# === API Endpoints ===
@router.get('/api/agents/list')
async def api_list_agents():
    """列出所有可用的Agent"""
    return {'agents': list_agents(), 'count': len(AGENT_METADATA)}


@router.get('/api/agents/{agent_type}/info')
async def api_get_agent_info(agent_type: str):
    """获取指定Agent的信息"""
    if agent_type not in AGENT_METADATA:
        raise HTTPException(status_code=404, detail=f'Agent {agent_type} not found')
    return {'id': agent_type, **AGENT_METADATA[agent_type], 'has_prompt': agent_type in AGENT_PROMPTS}


@router.post('/api/agents/{agent_type}/chat')
async def api_agent_chat(agent_type: str, request: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """与指定Agent进行对话"""
    if agent_type not in AGENT_PROMPTS:
        raise HTTPException(status_code=404, detail=f'Agent {agent_type} not found')

    user_id = current_user["user_id"]
    session_id = request.session_id or str(uuid.uuid4())

    history = await get_agent_session(user_id, session_id)
    history.append({'role': 'user', 'content': request.message})

    if len(history) > 20:
        history = history[-20:]

    try:
        system_prompt = get_agent_prompt(agent_type)
        agent_name = AGENT_METADATA[agent_type]['name']

        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append(msg)

        completion = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=2048
        )
        response_text = completion.choices[0].message.content

        history.append({'role': 'assistant', 'content': response_text})
        await save_agent_session(user_id, session_id, history, agent_type)

        return AgentChatResponse(
            reply=response_text,
            agent=agent_type,
            agent_name=agent_name,
            session_id=session_id
        )

    except Exception as e:
        print(f'[ERROR] Agent chat error: {e}')
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/api/agents/{agent_type}/chat/stream')
async def api_agent_chat_stream(agent_type: str, request: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """流式对话 - 返回 SSE 流"""
    if agent_type not in AGENT_PROMPTS:
        raise HTTPException(status_code=404, detail=f'Agent {agent_type} not found')

    system_prompt = get_agent_prompt(agent_type)
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        try:
            from openai import OpenAI
            client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

            history = await get_agent_session(current_user['user_id'], session_id)
            history.append({'role': 'user', 'content': request.message})

            messages = [{"role": "system", "content": system_prompt}]
            for msg in history[-20:]:
                messages.append(msg)

            stream = client.chat.completions.create(
                model=LLM_MODEL_NAME,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True
            )

            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"

            history.append({'role': 'assistant', 'content': full_response})
            await save_agent_session(current_user['user_id'], session_id, history, agent_type)

            yield f"data: {json.dumps({'content': '', 'done': True, 'session_id': session_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@router.delete('/api/agents/sessions/{session_id}')
async def api_clear_agent_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """清除指定会话的历史"""
    user_id = current_user["user_id"]
    if await delete_agent_session(user_id, session_id):
        return {'success': True, 'message': f'Session {session_id} cleared'}
    return {'success': False, 'message': 'Session not found or not owned by user'}


@router.get('/api/agents/sessions')
async def api_list_agent_sessions(agent_type: str = None, current_user: dict = Depends(get_current_user)):
    """列出用户的Agent会话"""
    user_id = current_user["user_id"]
    sessions = await list_user_sessions(user_id, agent_type)
    return {"sessions": sessions, "count": len(sessions)}


# === LOD Agent Endpoints ===
@router.post("/api/agents/{agent_type}/chat/lod")
async def api_agent_chat_lod(agent_type: str, request: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """
    使用 LOD Kernel 的 Agent 对话端点
    特点：动态工具加载、CodeAct 执行、三层记忆
    """
    if agent_type not in AGENT_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")

    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        agent_prompt = get_agent_prompt(agent_type)
        kernel = get_kernel()
        
        enhanced_query = f"""【当前角色】{AGENT_METADATA[agent_type]["name"]}
{agent_prompt}

【用户问题】
{request.message}"""
        
        full_response = ""
        async for event in kernel.run_stream(enhanced_query):
            if event.get("type") == "token":
                full_response += event.get("content", "")
        
        return AgentChatResponse(
            reply=full_response,
            agent=agent_type,
            agent_name=AGENT_METADATA[agent_type]["name"],
            session_id=session_id
        )
        
    except Exception as e:
        print(f"[ERROR] LOD Agent chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/agents/{agent_type}/chat/lod/stream")
async def api_agent_chat_lod_stream(agent_type: str, request: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """使用 LOD Kernel 的流式 Agent 对话"""
    if agent_type not in AGENT_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")

    async def generate():
        try:
            agent_prompt = get_agent_prompt(agent_type)
            kernel = get_kernel()
            
            enhanced_query = f"""【当前角色】{AGENT_METADATA[agent_type]["name"]}
{agent_prompt}

【用户问题】
{request.message}"""
            
            async for event in kernel.run_stream(enhanced_query):
                evt_type = event.get("type")
                content = event.get("content", "")

                if evt_type == "token":
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                elif evt_type == "code":
                    yield f"data: {json.dumps({'type': 'code', 'content': content})}\n\n"
                elif evt_type == "tool_output":
                    yield f"data: {json.dumps({'type': 'tool_output', 'content': content})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
