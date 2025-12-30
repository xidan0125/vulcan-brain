"""
修复后的 _qwen3_stream 方法
使用启发式方法检测思考/内容分界
"""

NEW_QWEN3_STREAM = """
    async def _qwen3_stream(
        self,
        messages: List[ChatMessage],
        temperature: float,
        max_tokens: int,
        tools: List[Dict] = None,
        enable_thinking: bool = True
    ) -> AsyncGenerator[Union[str, StreamChunk], None]:
        \"\"\"
        Qwen3 流式聊天
        
        Qwen3-Thinking 模型输出格式:
        - 先输出思考内容（自然语言推理）
        - 然后双换行
        - 最后输出正式回答（通常带 markdown 格式）
        
        使用启发式检测: 双换行后跟 markdown/数字/特定词开头
        \"\"\"
        import re as regex
        client = self._get_http_client()

        payload = {
            "model": self.qwen3_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # 状态追踪
        in_thinking = True
        buffer = ""
        
        # 回答开始的启发式模式: 双换行后跟特定格式
        answer_start_pattern = regex.compile(
            r"\\n\\n(\\*\\*|\\d+[.)]|The |This |Here |So,? |In |To |Yes|No |It |I |For |When |My |Your |A |An )",
            regex.IGNORECASE
        )

        async with client.stream(
            "POST",
            f"{self.qwen3_base_url}/v1/chat/completions",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        # 输出剩余缓冲区
                        if buffer:
                            if enable_thinking:
                                chunk_type = "thinking" if in_thinking else "content"
                                yield StreamChunk(type=chunk_type, text=buffer)
                            elif not in_thinking:
                                yield buffer
                        break
                        
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        
                        # 优先使用 reasoning_content (如果 vLLM parser 工作)
                        reasoning = delta.get("reasoning_content", "")
                        text = delta.get("content", "")
                        
                        if reasoning and enable_thinking:
                            yield StreamChunk(type="thinking", text=reasoning)
                            continue
                        
                        if not text:
                            continue
                        
                        # 添加到缓冲区
                        buffer += text
                        
                        if in_thinking:
                            # 检查是否到达回答部分
                            match = answer_start_pattern.search(buffer)
                            if match:
                                # 找到回答开始位置
                                split_pos = match.start()
                                thinking_text = buffer[:split_pos]
                                answer_text = buffer[split_pos + 2:]  # 跳过 \\n\\n
                                buffer = ""
                                in_thinking = False
                                
                                if thinking_text and enable_thinking:
                                    yield StreamChunk(type="thinking", text=thinking_text)
                                if answer_text:
                                    if enable_thinking:
                                        yield StreamChunk(type="content", text=answer_text)
                                    else:
                                        yield answer_text
                            else:
                                # 还在思考阶段，保留最后80字符用于跨chunk检测
                                if len(buffer) > 80:
                                    output = buffer[:-80]
                                    buffer = buffer[-80:]
                                    if enable_thinking:
                                        yield StreamChunk(type="thinking", text=output)
                        else:
                            # 已经在回答阶段，直接输出
                            if enable_thinking:
                                yield StreamChunk(type="content", text=buffer)
                            else:
                                yield buffer
                            buffer = ""
                            
                    except json.JSONDecodeError:
                        continue
"""

print(NEW_QWEN3_STREAM)
