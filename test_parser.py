# test_parser.py
import json
from llama_index.core.llms import ChatResponse, ChatMessage, MessageRole
# 导入你刚刚写的解析器
from parser import qwen_xml_to_tool_calls_parser

def run_test(name, input_content, should_have_tool=False, expected_tool_name=None):
    """
    辅助测试函数：模拟一次 LLM 响应并检查解析结果
    """
    print(f"--------------------------------------------------")
    print(f"🧪 测试场景: {name}")
    print(f"📥 模拟输入: {input_content[:60]}..." if input_content else "None")

    # 1. 构建模拟的 ChatResponse
    mock_response = ChatResponse(
        message=ChatMessage(
            role=MessageRole.ASSISTANT,
            content=input_content,
            additional_kwargs={} # 初始状态为空
        )
    )

    # 2. 运行你的解析器
    try:
        processed_response = qwen_xml_to_tool_calls_parser(mock_response)
    except Exception as e:
        print(f"❌ 崩溃: 解析器抛出了异常 - {e}")
        return

    # 3. 验证结果
    tool_calls = processed_response.message.additional_kwargs.get("tool_calls", [])
    
    if should_have_tool:
        if tool_calls:
            tool_data = tool_calls[0]['function']
            parsed_name = tool_data['name']
            parsed_args = tool_data['arguments']
            
            print(f"✅ 解析成功! 发现工具调用.")
            print(f"   🛠️ 工具名: {parsed_name}")
            print(f"   📋 参数: {parsed_args}")
            
            # 验证工具名是否匹配
            if expected_tool_name and parsed_name == expected_tool_name:
                print(f"✅ 工具名匹配预期 ({expected_tool_name})")
            elif expected_tool_name:
                print(f"❌ 工具名不匹配! 预期 {expected_tool_name}, 实际 {parsed_name}")
            
            # 验证内容是否被清洗 (防止模型自言自语)
            if processed_response.message.content is None or processed_response.message.content == "":
                 print(f"✅ Content 已被清洗 (Cleaned)")
            else:
                 print(f"⚠️ 警告: Content 未被清洗: {processed_response.message.content}")

        else:
            print(f"❌ 失败: 预期有工具调用，但解析结果为空.")
    else:
        if not tool_calls:
            print(f"✅ 通过: 正确地忽略了非工具消息.")
        else:
            print(f"❌ 失败: 预期无工具，却解析出了工具: {tool_calls}")
    print("\n")

if __name__ == "__main__":
    print("🚀 开始 T1.3 解析器单元测试...\n")

    # --- 场景 1: 标准的 Qwen XML 工具调用 ---
    xml_input_1 = """<tool_call>{"name": "get_current_time", "arguments": {"timezone": "Asia/Shanghai"}}</tool_call>"""
    run_test("标准 XML", xml_input_1, should_have_tool=True, expected_tool_name="get_current_time")

    # --- 场景 2: 包含 <think> 标签的复杂调用 (Thinking 模型的典型输出) ---
    xml_input_2 = """<think>
用户想知道现在的时间。我应该使用 get_current_time 工具。
时区是上海。
</think>
<tool_call>{"name": "get_current_time", "arguments": {"timezone": "Asia/Shanghai"}}</tool_call>"""
    run_test("带 Thinking 过程", xml_input_2, should_have_tool=True, expected_tool_name="get_current_time")

    # --- 场景 3: 普通闲聊 (无工具) ---
    text_input = "你好！我是 Qwen，很高兴为你服务。"
    run_test("普通闲聊", text_input, should_have_tool=False)

    # --- 场景 4: XML 格式损坏/JSON 错误 (健壮性测试) ---
    broken_input = """<tool_call>{name: "broken_json", args: ...}</tool_call>"""
    run_test("损坏的 JSON", broken_input, should_have_tool=False)

    print("🏁 测试结束。如果看到全绿 ✅，则 Phase 1 通过。")
