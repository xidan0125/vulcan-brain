# Vulcan Brain 开发知识库

这是给 Claude + Gemini 开发 Vulcan Brain 时参考的前沿知识库。

## 目录结构

```
.knowledge/
├── ai-frontiers/          # AI 前沿实践与认知
│   ├── whitepapers/       # 原始白皮书 (PDF)
│   └── digests/           # 提取的结构化知识 (JSON)
└── README.md
```

## 当前知识来源

### Google/Kaggle AI Agents Intensive (2025)
5篇权威白皮书，涵盖 AI Agent 开发全流程：

| 文件 | 主题 | 核心内容 |
|------|------|----------|
| 01_intro_to_agents | Agent 入门 | 架构、分类、生命周期 |
| 02_tools_and_mcp | 工具与 MCP | 工具设计、MCP 协议、互操作性 |
| 03_context_and_memory | 上下文与记忆 | Context Engineering、Session、Memory |
| 04_agent_quality | 质量评估 | 评估框架、LM Judge、调试 |
| 05_prototype_to_production | 原型到生产 | 部署、扩展、运维 |

## 如何使用

### 快速查看某个概念
```bash
# 查看所有概念列表
cat .knowledge/ai-frontiers/digests/01_intro_to_agents.json | jq '.core_concepts[].name'

# 查看 MCP 相关知识
cat .knowledge/ai-frontiers/digests/02_tools_and_mcp.json | jq '.core_concepts[] | select(.name | contains("MCP"))'
```

### 合并知识库
所有知识已合并到 `digests/_combined_knowledge.json`

## 如何补充新知识

1. 将 PDF 放入 `whitepapers/` 目录
2. 运行提取脚本（需要 Gemini API）
3. 或手动创建 JSON 到 `digests/` 目录

### JSON 格式参考
```json
{
  "title": "文档标题",
  "summary": "一句话总结",
  "core_concepts": [
    {
      "name": "概念名称",
      "definition": "定义",
      "key_points": ["要点1", "要点2"]
    }
  ],
  "best_practices": [...],
  "architecture_patterns": [...],
  "code_snippets": [...],
  "key_takeaways": [...]
}
```

## 更新记录

- 2024-12-13: 初始化，添加 Google/Kaggle AI Agents 5篇白皮书
