# LLM/Agent 架构分析报告

基于提供的代码文件，以下是对 Vulcan Brain LLM/Agent 架构的深度分析报告：

---

### 1. 当前 LLM 选型现状

#### **使用的模型与用途**
系统采用了 **"术业有专攻"** 的多模型策略，主要分为三类：

1.  **CEO (战略决策脑)**:
    *   **模型**: `qwen3:30b-a3b` (注：代码中标识为 Qwen3，可能是内部微调版或 Qwen2.5 的特定 tag)。
    *   **部署方式**: **Ollama** (`http://localhost:11434`)。
    *   **用途**: 负责意图理解、任务拆解、战略规划、最终回复整合。利用 `<think>` 标签进行深度推理。
2.  **CTO (技术执行脑)**:
    *   **模型**: `Qwen/Qwen2.5-Coder-32B-Instruct-AWQ`。
    *   **部署方式**: **SGLang** (`http://localhost:30000`)。
    *   **用途**: 负责代码生成、工具调用、结构化输出。使用 SGLang 进行高并发/低延迟推理。
3.  **预测/辅助模型**:
    *   **模型**: `qwen2.5:7b`。
    *   **用途**: 在 `config.py` 中定义为 `LLM_PREDICTION_MODEL`，可能用于轻量级任务或推测性解码。

#### **模型配置管理现状**
**管理混乱，尚未统一。**
*   **分散的配置源**:
    *   `config.py`: 尝试做统一配置，但存在 "新旧配置系统" (`settings.py` vs `os.getenv`) 的兼容层，增加了复杂性。
    *   `kernel_bicameral_v5.py`: 在 `__init__` 方法中硬编码了默认值（如 `cto_base_url`），虽然可以传参，但默认值分散在代码中。
    *   `vulcan_libs/ai_service.py`: 重新读取了 `config.py`，但自己实现了一套 `httpx` 调用逻辑，绕过了 `kernel` 中的封装。

---

### 2. Agent 编排架构

#### **当前的 Agent 模式**
采用的是 **Bicameral Mind (双脑/二分心智) 架构**，本质上是一种 **垂直分层的 Manager-Worker 模式**。

*   **架构逻辑**:
    1.  **感知层**: 注入时间、系统状态 (`ceo_soul.py`)。
    2.  **决策层 (CEO)**: 接收用户输入 -> 产生 `<think>` 思考 -> 决定是直接回答还是委派。
    3.  **路由机制**:
        *   **基于规则**: `_classify_query` 检测关键词（"代码", "python"）。
        *   **基于 Prompt**: CEO 输出特定的 JSON 结构 `delegate_to_cto({...})`。
    4.  **执行层 (CTO)**: 接收结构化任务 -> 生成代码/调用工具 -> 返回结果。
    5.  **合成层**: CEO 拿到 CTO 的结果 -> 整合并润色给用户。

#### **架构评价**
*   **优点**:
    *   **能力解耦**: 将"思考/规划"与"执行/编码"分离，利用 Coder 模型极强的代码能力和 Thinking 模型极强的逻辑能力。
    *   **性能优化**: CTO 使用 SGLang + AWQ 量化，针对工具调用和代码生成进行了吞吐量优化。
    *   **可控性**: 通过 `ceo_soul.py` 注入宪法和对齐层，增强了安全性。

*   **缺点/风险**:
    *   **通信脆弱**: CEO 委派 CTO 依赖于 **文本/正则匹配** (`delegate_to_cto` 字符串解析)。如果模型输出格式稍有偏差（如多了一个换行），流程就会中断。
    *   **调用栈分裂**: `ai_service.py` 使用 `httpx` 直接调 API，而 `kernel` 使用 `llama_index` 和 `sglang_client`。系统内存在两套完全不同的 LLM 调用代码。
    *   **状态管理**: 虽然提到 PostgreSQL，但代码中主要依赖内存中的 Prompt 拼接 (`_build_ceo_prompt`)，缺乏真正的上下文窗口管理（Window Buffer）。
    *   **流式处理复杂**: 需要处理 `<think>` 标签的过滤和分流，`BicameralStreamFilter` 和 `ThinkTagFilter` 功能重复。

---

### 3. 建议的标准化方案

#### **A. LLM 调用统一化 (The LLM Gateway)**
废弃 `ai_service.py` 中的 `httpx` 实现和 `kernel` 中的直接实例化，建立统一的 **Model Gateway**。

```python
# 伪代码示例
class LLMFactory:
    @staticmethod
    def get_ceo_model() -> BaseLLM:
        # 统一返回 LlamaIndex 或 LangChain 的接口对象
        return Ollama(model=config.CEO_MODEL, base_url=config.OLLAMA_URL)

    @staticmethod
    def get_cto_client() -> SGLangClient:
        return SGLangClient(base_url=config.SGLANG_URL)
```

#### **B. Agent 编排优化 (Graph-based State Machine)**
目前的 "Prompt 触发委派" 比较脆弱，建议迁移到 **状态机 (State Machine)** 或 **图编排 (Graph)** 模式（如 LangGraph）。

*   **当前**: CEO 输出文本 -> 正则检测 -> 触发 CTO。
*   **建议**: 定义明确的节点 (Node) 和边 (Edge)。
    *   `Router Node`: 分析意图，决定流向 `Chat Node` 还是 `Tool Node`。
    *   `Tool Node (CTO)`: 专门执行工具。
    *   使用 **Function Calling / Tool Use API** 替代文本生成的 `delegate_to_cto({...})`，提高稳定性。

#### **C. 需要创建的新模块**
1.  **`vulcan_libs.model_gateway`**: 统一所有的 LLM 接口实例化，屏蔽 Ollama/SGLang/vLLM 的差异。
2.  **`vulcan_libs.prompt_registry`**: 将 `ceo_soul.py` 和 `kernel` 中的长 Prompt 提取到 YAML 或单独的 py 文件中管理，支持版本控制。
3.  **`vulcan_libs.context_manager`**: 统一管理短期记忆（Window）和长期记忆（Vector DB/Postgres），替代目前散落在各处的 `user_memories` 字符串拼接。

---

### 4. 优先级排序 (Top 5)

根据代码现状，以下是改进任务的优先级排序：

1.  **🔴 [Critical] 统一 LLM 调用层 (Refactor AI Service)**
    *   **任务**: 合并 `vulcan_libs/ai_service.py` 和 `kernel_bicameral_v5.py` 中的 LLM 调用逻辑。
    *   **原因**: 存在两套 HTTP 调用代码是维护噩梦，且 `ai_service` 缺乏对 SGLang 的支持。

2.  **🟠 [High] 强化 CEO->CTO 协议 (Structured Output)**
    *   **任务**: 将 `delegate_to_cto` 从 "文本生成+正则匹配" 改为标准的 **Function Calling** (如果模型支持) 或使用 **Pydantic 约束的结构化输出** (SGLang 支持 regex 约束)。
    *   **原因**: 当前的字符串匹配方式极易出错，是系统稳定性的最大短板。

3.  **🟠 [High] 统一配置管理 (Fix Config)**
    *   **任务**: 清理 `config.py`，移除 "向后兼容层"，强制使用单一配置源（推荐 Pydantic Settings）。
    *   **原因**: `try...except` 加载配置会导致生产环境和开发环境行为不一致的隐患。

4.  **🟡 [Medium] 提取 Prompt 模板 (Prompt Engineering)**
    *   **任务**: 将 `ceo_soul.py` 和 `kernel` 中的 f-string Prompt 剥离，建立 Prompt 模板库。
    *   **原因**: 代码与 Prompt 耦合过紧，修改 Prompt 需要改动核心代码逻辑。

5.  **🟢 [Low] 统一流式过滤器 (Stream Unification)**
    *   **任务**: 合并 `BicameralStreamFilter` 和 `ThinkTagFilter`。
    *   **原因**: 两者都在做 `<think>` 标签过滤，逻辑重复。