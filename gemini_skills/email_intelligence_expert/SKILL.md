# Email Intelligence Expert

邮件数据智能架构师，专注于企业邮件信息提取和知识图谱构建。

## 快速使用

```bash
# 使用别名
python ~/vulcan-brain/run_skill.py email "如何设计Identifier的子类型分类?" --search

# 完整名称
python ~/vulcan-brain/run_skill.py email_intelligence_expert "KùzuDB和Neo4j哪个更适合我们的场景?"
```

## 核心能力

### 1. Schema 设计
- V2 → V3 模型演进
- Event-Fact-Provenance 建模
- Identifier/Amount/Date 等类型分类
- 三级置信度 (OCR_Raw/LLM_Reasoned/Human_Verified)

### 2. 图数据库建模
- KùzuDB / Neo4j 选型
- 超图 (Hypergraph) 建模
- 双时态 (Bi-Temporal) 存储
- Cypher / KùzuDB DDL 编写

### 3. 实体消歧 (Entity Resolution)
- 公司名标准化 (去后缀、别名合并)
- 人名匹配 (中英文、昵称)
- 产品SKU统一

### 4. VLM 提取优化
- Prompt 工程
- JSON 输出稳定性
- 多页文档处理策略

## 联网搜索

此技能默认启用 Google Search，适合:
- 图数据库最佳实践查询
- 知识图谱设计模式研究
- 最新的 Entity Resolution 算法
- VLM/LLM 结构化输出技术

## 典型问题

```bash
# Schema 设计
python run_skill.py email "我们的Identifier类型应该如何细分子类型? 发票号、运单号、订单号有什么区别?"

# 图数据库
python run_skill.py email "如何用KùzuDB建模条件性价格? 比如数量>1000时单价是X,否则是Y"

# 实体消歧
python run_skill.py email "同一家公司出现了SpaceX、Space X、SpaceX Inc.三种写法,如何设计合并策略?"

# VLM 提取
python run_skill.py email "VLM总是返回List而不是Dict,有什么prompt技巧能强制输出正确格式?"
```

## 相关文档

- `docs/email-intelligence-v3/README.md` - 项目总览
- `docs/email-intelligence-v3/research/*.md` - 研究文档
- `services/email_intelligence_v2/models/` - V2 模型代码
- `docs/email-intelligence-v3/v3_pipeline/` - V3 测试脚本

## 维护者

此技能由开发团队维护，如有更新请同步修改:
1. `system_prompt.md` - 系统提示词
2. `config.json` - 配置参数
3. `SKILL.md` - 使用文档
