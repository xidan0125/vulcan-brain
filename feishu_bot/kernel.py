"""
飞书机器人 Kernel - 员工传感器版
- 收集员工汇报的项目信息
- 提取关键事件存入 ProjectStore
- 作为 Vulcan Brain 的信息收集触手
"""

import json
from typing import Dict, Any, Optional, Literal
from datetime import datetime
import uuid

from feishu_bot.llm_client import get_llm_client
from services.project_store import get_project_store, SensorEvent

EventType = Literal[
    "progress_update",   # 进度更新
    "task_complete",     # 任务完成
    "risk_report",       # 风险上报
    "blocker",           # 阻塞问题
    "milestone",         # 里程碑
    "general_update",    # 一般更新
    "question",          # 问题咨询
    "small_talk",        # 闲聊
]


class FeishuBotKernel:
    """飞书传感器 Kernel - 收集员工汇报"""
    
    def __init__(self):
        self.llm = get_llm_client()
        self.store = get_project_store()
        print("[FeishuBotKernel] 传感器模式初始化完成")
    
    async def process_message(self, text: str, user_id: str, chat_id: str) -> Dict[str, Any]:
        """
        处理员工消息
        - 识别是否是项目汇报
        - 提取关键信息存入系统
        - 回复确认
        """
        # Step 1: 分析消息类型
        analysis = await self._analyze_message(text, user_id)
        print(f"[Kernel] 消息分析: {analysis}")
        
        event_type = analysis.get("event_type", "small_talk")
        
        # Step 2: 如果是项目相关，存入传感器事件
        if event_type not in ("small_talk", "question"):
            event = await self._create_sensor_event(analysis, user_id, chat_id)
            if event:
                await self.store.add_event(event)
                print(f"[Kernel] 已记录事件: {event.event_type} - {event.title}")
        
        # Step 3: 生成回复
        reply = await self._generate_reply(text, analysis)
        
        return {"type": "text", "text": reply}
    
    async def _analyze_message(self, text: str, user_id: str) -> Dict[str, Any]:
        """用 LLM 分析员工消息，提取项目信息"""
        system_prompt = """你是一个项目管理助手，分析员工的工作汇报消息。

从消息中提取以下信息（JSON格式）：
- event_type: 事件类型
  - "progress_update": 进度更新（如"完成了xx"、"做了xx"）
  - "task_complete": 任务完成（明确说完成某个功能/模块）
  - "risk_report": 风险上报（如"可能延期"、"有问题"）
  - "blocker": 阻塞问题（如"卡住了"、"被xx阻塞"）
  - "milestone": 里程碑（如"上线了"、"发布了"）
  - "general_update": 一般更新
  - "question": 问题咨询（问工作相关问题）
  - "small_talk": 闲聊/无关工作
- project_name: 项目名称（如果提到）
- summary: 一句话总结（10-20字）
- details: 具体内容
- severity: 严重程度（info/warning/error，仅风险/阻塞时填）

只输出 JSON，不要其他文字。

示例：
用户: "StoryFi的合约今天部署好了"
输出: {"event_type": "task_complete", "project_name": "StoryFi", "summary": "合约部署完成", "details": "StoryFi合约今天部署完成", "severity": "info"}

用户: "Vulcan Brain可能要延期，GPU内存不够"
输出: {"event_type": "risk_report", "project_name": "Vulcan Brain", "summary": "GPU内存不足可能延期", "details": "GPU内存不够导致可能延期", "severity": "warning"}

用户: "今天天气真好"
输出: {"event_type": "small_talk", "summary": "闲聊"}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        
        try:
            raw = await self.llm.chat(messages)
            if "{" in raw:
                json_str = raw[raw.find("{"):raw.rfind("}")+1]
                return json.loads(json_str)
        except Exception as e:
            print(f"[Kernel] 消息分析失败: {e}")
        
        return {"event_type": "small_talk", "summary": "无法解析"}
    
    async def _create_sensor_event(self, analysis: Dict[str, Any], user_id: str, chat_id: str) -> Optional[SensorEvent]:
        """创建传感器事件"""
        project_name = analysis.get("project_name")
        
        # 尝试匹配项目
        project_id = "unknown"
        if project_name:
            project = await self.store.get_project_by_name(project_name)
            if project:
                project_id = project.id
        
        return SensorEvent(
            id=str(uuid.uuid4())[:8],
            project_id=project_id,
            event_type=analysis.get("event_type", "general_update"),
            title=analysis.get("summary", "更新"),
            description=analysis.get("details", ""),
            severity=analysis.get("severity", "info"),
            metadata={
                "user_id": user_id,
                "chat_id": chat_id,
                "raw_message": analysis.get("details", ""),
            }
        )
    
    async def _generate_reply(self, user_text: str, analysis: Dict[str, Any]) -> str:
        """生成回复"""
        event_type = analysis.get("event_type", "small_talk")
        
        # 闲聊直接对话
        if event_type == "small_talk":
            messages = [
                {"role": "system", "content": "你是友好的项目助手，简短回复。"},
                {"role": "user", "content": user_text},
            ]
            return await self.llm.chat(messages)
        
        # 问题咨询
        if event_type == "question":
            messages = [
                {"role": "system", "content": "你是项目管理助手，简洁回答工作相关问题。"},
                {"role": "user", "content": user_text},
            ]
            return await self.llm.chat(messages)
        
        # 项目汇报 - 确认收到
        project_name = analysis.get("project_name", "项目")
        summary = analysis.get("summary", "更新")
        
        confirmations = {
            "progress_update": f"✅ 收到！已记录 {project_name} 进度更新：{summary}",
            "task_complete": f"🎉 太棒了！{project_name} - {summary}，已同步到管理端",
            "risk_report": f"⚠️ 收到风险上报：{summary}，已标记到 {project_name}",
            "blocker": f"🚨 收到阻塞问题！{summary}，已紧急标记",
            "milestone": f"🏆 里程碑达成！{project_name} - {summary}，已记录",
            "general_update": f"📝 已记录：{summary}",
        }
        
        return confirmations.get(event_type, f"收到：{summary}")


# 单例
_kernel = None

def get_feishu_kernel() -> FeishuBotKernel:
    global _kernel
    if _kernel is None:
        _kernel = FeishuBotKernel()
    return _kernel
