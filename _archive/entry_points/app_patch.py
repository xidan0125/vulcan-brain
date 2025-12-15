# 优化1: 简化欢迎消息（第8-12行）
OLD_WELCOME = '''    await cl.Message(
        content="**Vulcan Brain Online.**\n\n系统就绪。\n- 内核: CodeAct Native (Streaming)\n- 架构: LOD V4\n- 工具包: " + registry.get_registry_summary() + "\n\n请指示。",
        author="Vulcan"
    ).send()'''

NEW_WELCOME = '''    await cl.Message(
        content="就绪。有什么可以帮您？",
        author="Vulcan"
    ).send()'''

# 优化2: 隐藏思考块（完全不显示 <think> 内容）
# 在 main() 函数中的 token 处理部分，跳过思考块的内容
