# V2 现状与数据资产

## 已完成工作

### Phase 0-2 完成
- ✅ MS365邮件同步 (Microsoft Graph API)
- ✅ MongoDB存储 (vulcan_brain.emails)
- ✅ 向量化 + Qdrant语义搜索
- ✅ GLiNER NER实体提取
- ✅ 邮件意图分类

### Phase 3-5 未启动
- ❌ 知识图谱构建
- ❌ GraphRAG问答
- ❌ Agent自动化

## 数据规模

| 指标 | 数值 |
|------|------|
| 原始邮件总数 | 56,868 封 |
| V2处理业务邮件 | 17,402 封 |
| 有附件邮件 | 4,882 封 |
| 附件总数 | 28,724 个 |
| PDF文档 | 3,823 个 |
| Excel表格 | 481 个 |
| NER实体总数 | 250,000+ |

## MongoDB emails集合结构

```javascript
{
  _id: ObjectId,
  message_id: String,
  subject: String,
  from: { name, address },
  to: [{ name, address }],
  received_datetime: Date,
  body: { content, content_type },
  has_attachments: Boolean,
  attachments: [{
    name: String,
    size: Number,
    content_type: String
    // 附件内容未下载!
  }],
  processing_status: {
    v2_extracted: Boolean
  },
  ai_extracted: {
    intent: String,
    entities: [...],
    classification: String
  }
}
```

## V2局限性

1. **只处理正文**: 完全忽略附件内容
2. **扁平实体**: 无关系建模
3. **无时态**: 不能追踪历史变化
4. **无溯源**: 不知道数据从哪来

## 可复用资产

- 17,402封业务邮件筛选结果
- V2意图分类 → 可作为Event.type初始值
- V2 NER实体 → 可作为Event.entities候选
- Qdrant向量索引 → 可用于检索增强

## 需要全新构建

- 附件内容提取 (PDF/Excel/图片)
- Event-Fact数据模型
- 置信度体系
- Provenance溯源链
- 时态链和状态机
