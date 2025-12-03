# 维度1: 聊天记录收集系统 - 实现文档

> 状态: ✅ 已完成基础实现  
> 日期: 2025-12-02

## 1. 概述

实现了飞书群聊消息的收集、存储和查询功能，作为五纬度信息收集系统的第一个维度。

## 2. 收集方式

根据需求确认，采用以下收集策略：

| 方式 | 说明 |
|------|------|
| 定时收集 | 日报生成前自动收集（需配置定时任务） |
| 手动触发 | 通过 API 手动触发收集 |
| 实时保存 | Brain Bot 收到的消息自动保存 |

### 去重机制
- 使用 `message_id` 作为唯一索引
- 插入前检查，已存在则跳过

### 收集通知
- 收集完成后自动发送群消息通知
- 显示扫描数、新增数、跳过数

## 3. 文件结构

```
vulcan-brain/
├── services/
│   └── message_store.py       # 消息存储模块 (新增)
├── message_api.py             # 消息收集 API (新增)
├── feishu_api.py              # 飞书机器人 (修改: 添加自动保存)
└── api_server.py              # 主服务 (修改: 添加路由)
```

## 4. MongoDB 数据结构

### Collection: `feishu_messages`

```javascript
{
  message_id: "om_xxx",           // 唯一标识
  chat_id: "oc_xxx",              // 群聊ID
  chat_type: "group",             // group/p2p
  sender: {
    open_id: "ou_xxx"             // 发送者ID
  },
  content: "消息内容",
  content_type: "text",
  timestamp: ISODate(),           // 消息时间
  created_at: ISODate(),          // 入库时间
  extracted: {                    // AI 提取字段 (待实现)
    processed: false,
    is_business: null,
    topics: [],
    entities: [],
    intent: null,
    action_items: []
  }
}
```

### 索引
- `message_id`: 唯一索引 (去重)
- `chat_id + timestamp`: 联合索引 (按群按时间查询)
- `created_at`: TTL 索引 (1年自动删除)

## 5. API 端点

### 手动收集
```http
POST /api/messages/collect
Content-Type: application/json

{
  "chat_ids": ["oc_xxx", "oc_yyy"],
  "since_hours": 24,
  "send_notice": true
}
```

### 获取历史
```http
GET /api/messages/history?chat_id=oc_xxx&limit=50
```

### 获取今日消息
```http
GET /api/messages/today?chat_id=oc_xxx
```

### 搜索消息
```http
GET /api/messages/search?keyword=项目&chat_id=oc_xxx
```

### 消息统计
```http
GET /api/messages/stats?chat_id=oc_xxx
```

### 定时收集任务
```http
POST /api/messages/scheduled-collect?chat_ids=oc_xxx&chat_ids=oc_yyy
```

## 6. 使用说明

### 6.1 获取群聊 ID

在飞书群聊中，发送一条消息给 Brain Bot，查看后端日志可获得 `chat_id`。

### 6.2 配置定时任务

建议在日报生成前调用收集接口：

```bash
# crontab 示例 (每天早上 8:55 收集)
55 8 * * * curl -X POST "http://localhost:8001/api/messages/scheduled-collect?chat_ids=oc_xxx"
```

### 6.3 查看收集结果

1. 群内会收到通知消息
2. 通过 API 查询已存储的消息

## 7. 待完成功能

- [ ] AI 结构化提取 (topics, entities, intent)
- [ ] 与日报系统集成
- [ ] 前端管理界面
- [ ] 定时任务自动配置

## 8. 下一步

继续实现维度2: 项目管理（飞书任务）
