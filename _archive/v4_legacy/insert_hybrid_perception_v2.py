#!/usr/bin/env python3
"""
脚本 V2：修复 f-string 语法问题
关键修复：直接读取文件行，手动定位插入点，避免 regex 破坏 f-string
"""

# 读取原文件
with open("kernel_codeact.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# ========== 找到插入点 ==========
insert_line_perception = None
insert_line_build_base = None
build_base_end = None

for i, line in enumerate(lines):
    if "def _build_base_prompt(self)" in line:
        insert_line_perception = i  # 在这行之前插入 perception 方法
        insert_line_build_base = i
    if insert_line_build_base is not None and build_base_end is None:
        # 找到 _build_base_prompt 方法的结束（下一个方法或类结束）
        if i > insert_line_build_base + 5:  # 至少过几行
            if (line.strip().startswith("def ") or
                line.strip().startswith("async def ") or
                (not line.strip() and lines[i+1].strip().startswith("def "))):
                build_base_end = i
                break

if insert_line_perception is None:
    print("❌ 错误：找不到 _build_base_prompt 方法")
    exit(1)

# ========== 1. 插入 _get_perception_context() 方法 ==========
perception_method = '''    def _get_perception_context(self):
        """
        [感知层] 获取当前物理世界的快照
        这是架构修正：把'查时间'从工具层提升到感知层
        """
        tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(tz)

        return f"""【环境感知 - 实时更新】
- 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
- 星期: {now.strftime('%A')}
- 时区: Asia/Shanghai
- 系统状态: 在线 (Dual RTX 5090 Ready)
"""

'''

# 在 _build_base_prompt 之前插入
lines.insert(insert_line_perception, perception_method)

# 更新后续行号
insert_line_build_base += perception_method.count('\n')
build_base_end += perception_method.count('\n')

# ========== 2. 替换 _build_base_prompt() 方法 ==========
new_build_base_prompt = '''    def _build_base_prompt(self) -> str:
        """构建基础 Prompt（灵魂层 + 指令 + 环境感知，不含工具描述）"""
        # [混合感知架构] 动态注入当前时间
        perception = self._get_perception_context()

        return f"""你是 Vulcan Brain - 一个有原则、有记忆、有灵魂的 AI 助手。

{perception}

{self.constitution}

{self.alignment_lessons}

【用户长期记忆】
{self.user_memories}

【工作流程】
1. **感知优先**：对于时间、日期等基础问题，直接利用【环境感知】中的信息回答，**不要**写代码调用工具。
2. **复杂计算**：对于数据分析、逻辑推演、或【环境感知】未包含的信息，必须编写 Python 代码 (```python ... ```) 来解决。
3. 我会执行代码，并将 print() 输出返回给你。
4. 你根据输出，给出最终答案。

【核心原则】
- 遇到问题直接上报，不擅自创建简化版
- 代码优于文字：Show, don't tell
- 简洁胜于复杂：100 行优于 1000 行
- 必须使用 print() 输出关键结果
- 当用户让你"记住"某事时，调用 remember_info()
- 当 Boss 纠正你时，调用 record_boss_feedback()
"""

'''

# 删除旧的 _build_base_prompt 方法（从定义行到结束行）
del lines[insert_line_build_base:build_base_end]

# 插入新方法
lines.insert(insert_line_build_base, new_build_base_prompt)

# ========== 3. 添加 run_stream() 方法到文件末尾 ==========
# 检查是否已存在
has_run_stream = any("async def run_stream(self" in line for line in lines)

if has_run_stream:
    print("⚠️  检测到已存在 run_stream 方法，将删除旧版本")
    # 找到并删除旧的 run_stream
    start_idx = None
    for i, line in enumerate(lines):
        if "async def run_stream(self" in line:
            start_idx = i
            break

    if start_idx is not None:
        # 找到方法结束（下一个同级方法或类结束）
        indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
        end_idx = None
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if line.strip() and not line.startswith(' ' * (indent + 4)):
                # 找到同级或更外层的定义
                end_idx = i
                break

        if end_idx is None:
            end_idx = len(lines)

        # 删除旧方法
        del lines[start_idx:end_idx]

# 添加新的 run_stream 到文件末尾
run_stream_method = '''
    async def run_stream(self, user_query: str):
        """
        V-Final 真流式内核（混合感知架构）
        特性：
        1. 使用 astream_chat 实现毫秒级 TTFT
        2. 动态刷新时间感知（每次查询都是最新时间）
        3. 实时缓冲输出以进行 CodeAct 匹配
        4. 协议严格对齐 app.py
        """
        print(f"\\n🚀 [Vulcan] 启动流式任务: {user_query}")

        # [混合感知] 刷新System Prompt（确保时间是最新的）
        self.base_system_prompt = self._build_base_prompt()

        # LOD 动态加载工具（保留原有逻辑）
        if hasattr(self, "_update_context"):
            self._update_context(user_query)
        else:
            # 如果没有LOD，至少要确保system_prompt是最新的
            self.system_prompt = self._build_full_prompt()

        # 初始化历史
        history = [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(role="user", content=user_query)
        ]

        step = 0
        MAX_STEPS = 5  # 防止死循环

        while step < MAX_STEPS:
            step += 1
            print(f"🔄 [Step {step}] 生成中...")

            # --- 1. 真流式调用 LLM ---
            response_gen = await self.llm.astream_chat(history)

            full_content = ""
            is_thinking_block = False

            async for chunk in response_gen:
                delta = chunk.message.content
                full_content += delta

                # 状态机判断是否在思考
                if "<think>" in full_content and "</think>" not in full_content:
                    is_thinking_block = True
                elif "</think>" in full_content:
                    is_thinking_block = False

                # ✅ 协议对齐：发送 'token' 事件
                yield {
                    "type": "token",
                    "content": delta,
                    "is_thinking": is_thinking_block
                }

            # 流式结束，将完整回复加入历史
            history.append(ChatMessage(role="assistant", content=full_content))

            # --- 2. CodeAct 解析与执行 ---
            code_match = CODE_BLOCK_REGEX.search(full_content)

            if code_match:
                code = code_match.group(1).strip()
                print(f"💻 [Code Detected] 长度: {len(code)}")

                # 执行代码
                output = self._execute_code(code)
                print(f"✅ [Execution] {output[:50]}...")

                # ✅ 协议对齐：发送 'tool_output' 事件
                yield {
                    "type": "tool_output",
                    "content": output
                }

                # 喂回历史
                history.append(ChatMessage(
                    role="user",
                    content=f"Execution Output:\\n{output}"
                ))

                # 循环继续
                continue

            else:
                # --- 3. 结束条件 ---
                print("🏁 [Finish] 任务完成")
                return

        yield {"type": "error", "content": "Error: Maximum steps reached."}
'''

lines.append(run_stream_method)

# ========== 写回文件 ==========
with open("kernel_codeact.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("✅ 混合感知架构代码已成功插入到 kernel_codeact.py")
print("📝 修改内容：")
print("   1. 添加 _get_perception_context() 方法（感知层）")
print("   2. 更新 _build_base_prompt() 方法（注入环境数据）")
print("   3. 添加 run_stream() 方法（真流式 + 协议对齐）")
