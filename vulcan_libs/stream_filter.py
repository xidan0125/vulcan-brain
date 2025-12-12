# vulcan_libs/stream_filter.py
"""
Vulcan Brain - 流式输出过滤器
从 kernel_codeact.py 提取，CEO 和 CTO 共用
"""

class OptimizedStreamingThinkFilter:
    """
    工业级流式过滤器 - 支持分流输出
    
    核心机制：
    1. 实时处理每个chunk（不等待完整响应）
    2. 状态机跟踪是否在think块内
    3. 缓冲区处理跨chunk的标签边界
    4. 分流输出：thinking 和 token 分开
    """
    
    def __init__(self):
        self.buffer = ""
        self.inside_think = False
        
    def process_chunk(self, chunk: str):
        """
        处理单个chunk，返回分流输出
        
        Args:
            chunk: LLM输出的原始chunk
            
        Returns:
            list[tuple[str, str]]: [(type, content), ...] 
                                   type 是 'thinking' 或 'token'
        """
        self.buffer += chunk
        outputs = []
        
        while True:
            if self.inside_think:
                close_idx = self.buffer.find('</think>')
                if close_idx == -1:
                    safe_len = self._find_safe_output_length_think(self.buffer)
                    if safe_len > 0:
                        outputs.append(('thinking', self.buffer[:safe_len]))
                        self.buffer = self.buffer[safe_len:]
                    break
                else:
                    if close_idx > 0:
                        outputs.append(('thinking', self.buffer[:close_idx]))
                    self.buffer = self.buffer[close_idx + 8:]
                    self.inside_think = False
            else:
                open_idx = self.buffer.find('<think>')
                if open_idx == -1:
                    safe_len = self._find_safe_output_length(self.buffer)
                    if safe_len > 0:
                        outputs.append(('token', self.buffer[:safe_len]))
                        self.buffer = self.buffer[safe_len:]
                    break
                else:
                    if open_idx > 0:
                        outputs.append(('token', self.buffer[:open_idx]))
                    self.buffer = self.buffer[open_idx + 7:]
                    self.inside_think = True
        
        return outputs
    
    def _find_safe_output_length(self, text: str) -> int:
        """找到可以安全输出的长度（正文）"""
        if not text:
            return 0
        for i in range(min(8, len(text)), 0, -1):
            suffix = text[-i:]
            if '<think>'.startswith(suffix) or '</think>'.startswith(suffix):
                return len(text) - i
        return len(text)
    
    def _find_safe_output_length_think(self, text: str) -> int:
        """找到可以安全输出的长度（思考内容）"""
        if not text:
            return 0
        for i in range(min(9, len(text)), 0, -1):
            suffix = text[-i:]
            if '</think>'.startswith(suffix):
                return len(text) - i
        return len(text)
    
    def flush(self):
        """流结束时输出剩余buffer"""
        result = []
        if self.buffer:
            if self.inside_think:
                result.append(('thinking', self.buffer))
            else:
                result.append(('token', self.buffer))
            self.buffer = ""
        return result
    
    def reset(self):
        """重置状态"""
        self.buffer = ""
        self.inside_think = False
