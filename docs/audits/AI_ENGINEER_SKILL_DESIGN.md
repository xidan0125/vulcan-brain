# AI Engineer Skill 设计方案

Generated: 2025-12-13T00:11:28.132629

---

你好！作为资深 AI 基础设施工程师，我非常理解你在 Vulcan Brain 系统中引入 `ai_engineer_v1` 的战略意义。在一个双 LLM（CEO + CTO）的架构中，你需要一个懂“行话”且能弥合高层决策与底层代码实现的中间层。

特别是你提到的**脆弱的文本解析通信**和**Soul 系统集成**，是这次设计的关键破局点。

以下是针对 `ai_engineer_v1` 的详细设计建议：

---

### 1. Skill 结构设计 (File Structure)

不要仅仅把 Skill 当作一个 Prompt，它应该是一个**可执行的软件模块**。建议采用如下目录结构：

```text
ai_engineer_v1/
├── manifest.json          # 元数据：版本、依赖、适用场景
├── system_prompt.md       # 核心人设：强调架构思维、SOTA 追踪、工程化落地
├── knowledge/             # 静态知识库 (RAG索引源)
│   ├── inference_engines/ # SGLang, vLLM, Ollama 对比数据
│   ├── prompt_patterns/   # CoT, ReAct, Tot 最佳实践
│   └── model_zoo/         # 各模型 VRAM 需求表、上下文窗口限制
├── tools/                 # 该 Skill 专用的工具定义 (Function Definitions)
│   ├── huggingface_api.py # 查询模型榜单、论文
│   ├── vram_calc.py       # 显存估算器
│   └── mcp_generator.py   # 生成 MCP Server 配置模板
├── examples/              # Few-shot 样本 (这对提升指令遵循至关重要)
│   ├── arch_design_shot.json
│   └── tool_selection_shot.json
└── tests/                 # 评估该 Skill 输出质量的测试用例
```

**核心差异点：**
*   **system_prompt.md**: 必须包含当前的系统约束（Current System Constraints），例如“当前环境只有 A100*2，不支持 GPT-4，首选 Qwen 系列”。
*   **manifest.json**: 用于 Soul 系统加载 Skill 时的注册。

### 2. 知识更新机制 (Knowledge Freshness)

AI 领域发展太快，静态 Prompt 一周就过时。建议采用 **"Hot-Swap Context" + "Active Search"** 策略：

1.  **分层知识注入**:
    *   **L1 (静态)**: 基础原理 (Transformer, Attention, RAG)。
    *   **L2 (周期性更新)**: 这是一个自动化 Job。每周自动爬取 HuggingFace Trending, Reddit LocalLLaMA, arXiv Sanity，生成摘要存入 `knowledge/weekly_digest.md`，并在运行时注入 Context。
    *   **L3 (实时)**: 赋予 Skill 联网搜索能力（Tavily API / Serper Dev），当被问及 "DeepSeek-V3 性能如何" 时，强制触发搜索。

2.  **版本控制**:
    *   维护一个 `model_registry.yaml`，记录当前支持的模型及其特性（GGUF 支持情况、AWQ/GPTQ 兼容性）。

### 3. 与 Soul 系统的集成方案

Soul 系统是“状态”和“记忆”的载体。AI Engineer 不仅要读取 Soul，还要维护 Soul 的健康。

*   **通信协议升级 (解决文本解析脆弱问题)**:
    *   **放弃纯文本**: 即使是 Ollama，现在也较好地支持 JSON Mode。
    *   **采用结构化输出 (Structured Outputs)**: 定义严格的 Pydantic 模型或 JSON Schema。
    *   **Soul 接口**: Soul 应暴露 API 供 Skill 调用，例如 `soul.update_tech_stack(state)` 或 `soul.get_project_constraints()`。

*   **集成流程**:
    1.  **CEO (决策)**: "我们需要加一个联网搜索功能。" -> 发送意图给 Soul。
    2.  **Soul**: 路由给 `ai_engineer_v1`，附带当前架构上下文。
    3.  **AI Engineer**:
        *   分析：需要 Search Tool + 总结能力。
        *   选型：Tavily API (工具) + Qwen2.5-7B-Instruct (推理成本低)。
        *   输出：生成 JSON 配置描述架构变更。
    4.  **CTO (代码)**: 读取 JSON 配置，生成具体 Python 代码。

### 4. 输出格式 (Deliverables)

AI Engineer 的输出必须是**机器可读**且**人类可审**的。

1.  **架构决策记录 (ADR - JSON/Markdown)**:
    ```json
    {
      "decision_id": "ADR-005",
      "title": "Switch to SGLang for CTO Node",
      "status": "Proposed",
      "context": "Ollama concurrency is low.",
      "decision": "Use SGLang with Qwen2.5-Coder.",
      "consequences": ["Need NVLink setup", "Throughput increases by 3x"]
    }
    ```
2.  **Mermaid.js 图表**: 描述 Agent 交互流程、数据流向。
3.  **MCP 配置文件**: 直接生成 `mcp_server_config.json`，定义工具接口。
4.  **选型矩阵**: Markdown 表格，对比不同方案的 Cost/Latency/Quality。

### 5. 典型应用场景 (Use Cases)

1.  **新 Agent 接入**:
    *   *User*: "我要加一个负责写 SQL 的 Agent。"
    *   *AI Eng*: 设计 Prompt 模板，推荐 text-to-sql 专用微调模型（如 Defog SQLCoder），计算所需显存，生成与主系统的通信接口定义。

2.  **推理性能调优**:
    *   *User*: "CTO 响应太慢。"
    *   *AI Eng*: 分析 Token/s，建议从 FP16 切换到 AWQ 量化，或者建议开启 SGLang 的 Radix Attention 缓存前缀。

3.  **成本/Token 优化**:
    *   *User*: "上下文超长了。"
    *   *AI Eng*: 设计 RAG 策略（Chunking size），或者引入 Context Compression 算法，或者建议切换到支持 128k context 的模型版本。

4.  **工具链整合**:
    *   *User*: "让系统能读取 GitHub Repo。"
    *   *AI Eng*: 生成基于 MCP 协议的 GitHub Fetcher 工具定义，并指导 CTO 写出实现代码。

### 6. 你遗漏了什么重要领域？ (Gap Analysis)

在你的列表中，以下几个领域对于 AI Engineer 至关重要，但在当前 Skill 定义中缺失：

1.  **Evals (评估与测试)**:
    *   AI Engineer 必须知道如何验证模型效果。
    *   **关键词**: Ragas (RAG评估), DeepEval, LLM-as-a-Judge, 准确率/幻觉率测试数据集构建。

2.  **Observability (可观测性)**:
    *   不仅仅是 Log，而是 Trace。
    *   **关键词**: LangSmith, Arize Phoenix, OpenTelemetry。AI Engineer 需要设计如何追踪一个 Request 穿过多个 Agent 的全链路。

3.  **Security & Guardrails (安全与护栏)**:
    *   防止 Prompt Injection，确保输出合规。
    *   **关键词**: NeMo Guardrails, Llama Guard, PII (隐私数据) 过滤。

4.  **Hardware/Deployment Specifics (硬核部署)**:
    *   不仅是选引擎，还有硬件适配。
    *   **关键词**: CUDA 版本匹配, Docker 容器化优化, Tensor Parallelism (TP) vs Pipeline Parallelism (PP) 设置。

### 总结建议

将 `ai_engineer_v1` 定位为 **Vulcan Brain 的“技术参谋长”**。

*   **输入**: 模糊的业务需求 (来自 CEO/Product Architect)。
*   **处理**: 结合当前硬件约束、SOTA 知识、Soul 状态。
*   **输出**: 精确的 JSON 架构定义、Mermaid 图表、具体的推理引擎参数配置。

建议优先解决 **通信协议 (JSON Schema)** 和 **知识库动态更新 (Web Search/Feeds)** 这两个点，这将极大提升系统的鲁棒性。
