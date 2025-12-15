# app.py (V4.1 - 单例模式优化)
"""
Vulcan Brain V4.1 - Chainlit 入口
修复：使用全局单例避免每会话重复加载 Embedding 模型
"""
import chainlit as cl
from config import LLM_MODEL_NAME
from kernel_codeact import VulcanCodeActKernel
from vulcan_libs.singleton import get_global_objects


@cl.on_chat_start
async def start():
    # 【优化】使用全局单例，Embedding 模型只加载一次
    registry, retriever = get_global_objects()

    # Kernel 每个会话一个实例（维护对话历史）
    kernel = VulcanCodeActKernel(
        model=LLM_MODEL_NAME,
        registry=registry,
        retriever=retriever,
        enable_lod=True
    )

    cl.user_session.set("kernel", kernel)
    cl.user_session.set("registry", registry)


@cl.on_message
async def main(message: cl.Message):
    kernel = cl.user_session.get("kernel")

    main_msg = cl.Message(content="", author="Vulcan")
    await main_msg.send()

    thinking_step = None

    async for event in kernel.run_stream(message.content):
        evt_type = event.get("type")
        content = event.get("content")

        if evt_type == "token":
            if event.get("is_thinking", False):
                if not thinking_step:
                    thinking_step = cl.Step(name="⚡ System 2 深度推理中...", type="process")
                    await thinking_step.send()
            else:
                if thinking_step:
                    await thinking_step.update()
                    thinking_step = None
                await main_msg.stream_token(content)

        elif evt_type == "code":
            code_block = f"\n```python\n{content}\n```\n"
            await main_msg.stream_token(code_block)

        elif evt_type == "tool_output":
            async with cl.Step(name="CodeAct 执行结果", type="tool") as tool_step:
                tool_step.output = content

        elif evt_type == "error":
            await cl.Message(content=f"❌ **Error:** {content}", author="System").send()

    await main_msg.update()

    actions = [
        cl.Action(name="correct", value="correct", payload={"action": "correct"}, label="✏️ 纠错/注入知识"),
        cl.Action(name="good", value="good", payload={"action": "good"}, label="👍 满意")
    ]
    main_msg.actions = actions
    await main_msg.update()


@cl.action_callback("correct")
async def on_action(action: cl.Action):
    res = await cl.AskUserMessage(content="请指示修正意见（将存入长期记忆与 DPO 数据集）：", timeout=60).send()
    if res:
        await cl.Message(content=f"✅ 已记录反馈：'{res.get('output', res)}'。").send()
    await action.remove()
