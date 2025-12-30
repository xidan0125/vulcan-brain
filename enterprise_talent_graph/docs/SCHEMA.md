# 数据模型设计 (MongoDB Schema)

> 企业人才图谱的数据存储结构

## 一、Collection 概览

| Collection | 用途 | 更新频率 |
|------------|------|----------|
| `talent_nodes` | 人才节点（员工） | 每日 |
| `talent_edges` | 关系边（互动） | 每日 |
| `function_domains` | 职能领域 | 每日 |
| `graph_metrics` | 图谱统计指标 | 每日 |
| `risk_alerts` | 风险预警 | 每日 |

---

## 二、talent_nodes (人才节点)

```javascript
{
  // 主键
  "_id": "david.kneale@vulcanshield.com",
  
  // 基本信息
  "profile": {
    "name": "David Kneale",
    "email": "david.kneale@vulcanshield.com",
    "department": "Management",           // 来自 HR 系统 (可选)
    "official_title": "IT Manager",       // 来自 HR 系统 (可选)
    "ai_title": "Strategic Hub & External Liaison"  // AI 生成
  },
  
  // ========== Layer 1: 网络指标 ==========
  "network_metrics": {
    "hub_score": 0.98,                    // Degree Centrality (归一化)
    "bridge_score": 0.85,                 // Betweenness Centrality
    "prestige_score": 0.72,               // Eigenvector Centrality
    "influence_score": 0.92,              // PageRank
    "community_id": "comm_001",           // Louvain 社区 ID
    "cross_community_connections": 12     // 跨社区连接数
  },
  
  // ========== Layer 2: 关系统计 ==========
  "relationship_stats": {
    "total_sent": 7311,                   // 总发件数
    "total_received": 6254,               // 总收件数
    "unique_internal_contacts": 28,       // 内部联系人数
    "unique_external_contacts": 303,      // 外部联系人数
    "top_collaborators": [                // 核心协作者
      {
        "email": "barry.claypool@vulcanshield.com",
        "name": "Barry Claypool",
        "interaction_count": 3487,
        "relationship_type": "peer",      // AI 分类
        "communication_pattern": "collaborative"
      },
      {
        "email": "daniel.hu@vulcanshield.com",
        "name": "Daniel Hu",
        "interaction_count": 1870,
        "relationship_type": "peer",
        "communication_pattern": "collaborative"
      }
      // ... more
    ]
  },
  
  // ========== Layer 3: 职能归属 ==========
  "function_mapping": {
    "primary_function": "external_business",  // 主要职能
    "secondary_functions": ["project_management"],
    "function_contribution": {                 // 各职能贡献度
      "external_business": 0.75,
      "project_management": 0.20,
      "technical": 0.05
    },
    "is_function_owner": true,                 // 是否为职能负责人
    "owned_functions": ["external_business"]
  },
  
  // ========== Layer 4: 外部生态 ==========
  "external_ecosystem": {
    "external_reach": 303,                     // 外部组织数
    "external_reach_rank": 1,                  // 排名
    "top_external_contacts": [
      {
        "domain": "customer-a.com",
        "company_name": "Customer A Corp",
        "entity_type": "customer",
        "interaction_count": 156,
        "is_sole_contact": true               // 是否唯一联系人
      }
      // ... more
    ],
    "external_by_type": {
      "customer": 45,
      "vendor": 28,
      "partner": 12,
      "financial": 8,
      "other": 210
    }
  },
  
  // ========== Risk Layer: 风险指标 ==========
  "risk_metrics": {
    "burnout_index": 0.42,                    // 倦怠指数 (非工作时间邮件占比)
    "burnout_risk": "high",                   // high/medium/low
    "overload_index": 0.86,                   // 过载指数 (收/发比)
    "overload_risk": "low",
    "flight_risk": "low",                     // 离职风险
    "flight_signals": [],
    "single_point_functions": ["external_business"]  // 作为单点的职能
  },
  
  // ========== 工作模式 ==========
  "work_patterns": {
    "active_hours": {
      "peak_hours": ["09:00-12:00", "14:00-17:00"],
      "after_hours_ratio": 0.42               // 非工作时间占比
    },
    "response_time": {
      "avg_minutes": 45,
      "pattern": "responsive"
    },
    "email_volume_trend": {
      "last_30_days": 620,
      "prev_30_days": 580,
      "change_rate": 0.069                    // +6.9%
    }
  },
  
  // ========== AI 生成内容 ==========
  "ai_insights": {
    "one_liner": "公司对外商务的核心枢纽，连接303个外部组织，是信息流的第一出入口",
    "key_strengths": [
      "跨部门协调能力强",
      "外部资源整合能力突出"
    ],
    "attention_flags": [
      "工作时间分布需关注",
      "对外商务职能无备份"
    ],
    "management_suggestions": [
      "培养 Barry 或 Cindy 作为对外商务备份",
      "重要客户关系建立多人对接机制"
    ],
    "generated_at": "2025-12-23T10:00:00Z"
  },
  
  // ========== 元数据 ==========
  "meta": {
    "created_at": "2025-12-23T08:00:00Z",
    "updated_at": "2025-12-23T10:00:00Z",
    "data_range": {
      "from": "2024-12-01",
      "to": "2025-12-22"
    },
    "email_count_analyzed": 13565
  }
}
```

---

## 三、talent_edges (关系边)

```javascript
{
  "_id": ObjectId("..."),
  
  // 关系双方 (按字母序存储，保证唯一性)
  "source": "barry.claypool@vulcanshield.com",
  "target": "david.kneale@vulcanshield.com",
  
  // 互动统计
  "interaction": {
    "total_count": 3487,                      // 总互动量
    "source_to_target": 1680,                 // A → B
    "target_to_source": 1807,                 // B → A
    "symmetry_ratio": 0.93,                   // 对称度
    "first_interaction": "2024-01-15",
    "last_interaction": "2025-12-22"
  },
  
  // 关系属性 (AI 分析)
  "relationship": {
    "type": "peer",                           // hierarchy/peer/external
    "communication_pattern": "collaborative", // directive/collaborative/reporting
    "health_score": 0.85,                     // 关系健康度
    "dominant_topics": [
      "Project Coordination",
      "Budget Approval",
      "Customer Follow-up"
    ]
  },
  
  // 是否跨社区
  "cross_community": false,
  "communities": ["comm_001"],                // 如果跨社区，列出两个社区
  
  // 元数据
  "meta": {
    "updated_at": "2025-12-23T10:00:00Z"
  }
}

// 索引
db.talent_edges.createIndex({ "source": 1, "target": 1 }, { unique: true })
db.talent_edges.createIndex({ "interaction.total_count": -1 })
db.talent_edges.createIndex({ "cross_community": 1 })
```

---

## 四、function_domains (职能领域)

```javascript
{
  "_id": "external_business",
  
  // 基本信息
  "name": "对外商务",
  "name_en": "External Business",
  "description": "客户关系、销售、商务谈判、对外协调",
  
  // 人员配置
  "personnel": {
    "primary_owner": {
      "email": "david.kneale@vulcanshield.com",
      "name": "David Kneale",
      "contribution": 0.75
    },
    "backup_owners": [],                      // 空 = 无备份 = 高风险
    "contributors": [
      {
        "email": "barry.claypool@vulcanshield.com",
        "name": "Barry Claypool",
        "contribution": 0.15
      },
      {
        "email": "cindy.wang@vulcanshield.com",
        "name": "Cindy Wang",
        "contribution": 0.10
      }
    ]
  },
  
  // 健康度评估
  "health": {
    "coverage_score": 65,                     // 人员覆盖充足度 (0-100)
    "single_point_risk": true,                // 单点故障风险
    "knowledge_concentration": 0.75,          // 知识集中度 (越高越危险)
    "risk_level": "high"                      // high/medium/low
  },
  
  // 主题关键词
  "topics": {
    "keywords": ["customer", "quote", "order", "contract", "negotiation"],
    "sample_subjects": [
      "RE: Quote for Project ABC",
      "Customer Visit Schedule",
      "Contract Amendment"
    ]
  },
  
  // 外部关系 (如适用)
  "external_relations": {
    "total_external_orgs": 303,
    "external_by_type": {
      "customer": 180,
      "partner": 45,
      "vendor": 78
    }
  },
  
  // 与其他职能的连接
  "connections": [
    {
      "target_function": "technical",
      "bridge_persons": [
        "david.kneale@vulcanshield.com",
        "barry.claypool@vulcanshield.com"
      ],
      "interaction_strength": "strong"
    }
  ],
  
  // 元数据
  "meta": {
    "detected_by": "topic_clustering",        // 如何识别的
    "confidence": 0.85,
    "updated_at": "2025-12-23T10:00:00Z"
  }
}
```

---

## 五、graph_metrics (图谱统计)

```javascript
{
  "_id": "latest",                            // 或日期 "2025-12-23"
  
  // 基本统计
  "basic_stats": {
    "total_nodes": 32,                        // 员工数
    "total_edges": 156,                       // 关系数
    "total_emails_analyzed": 59661,
    "date_range": {
      "from": "2024-12-01",
      "to": "2025-12-22"
    }
  },
  
  // 网络特征
  "network_stats": {
    "density": 0.31,                          // 网络密度
    "avg_clustering": 0.45,                   // 平均聚类系数
    "num_communities": 5,                     // 社区数
    "largest_community_size": 12
  },
  
  // 排行榜
  "rankings": {
    "by_hub_score": [
      {"email": "david.kneale@...", "name": "David", "score": 0.98},
      {"email": "barry.claypool@...", "name": "Barry", "score": 0.85},
      // top 10
    ],
    "by_bridge_score": [...],
    "by_external_reach": [...],
    "by_influence": [...]
  },
  
  // 职能统计
  "function_stats": {
    "total_functions": 5,
    "functions_at_risk": 1,
    "coverage_by_function": {
      "external_business": 65,
      "technical": 85,
      "operations": 75,
      "finance": 80,
      "hr_admin": 70
    }
  },
  
  // 风险统计
  "risk_stats": {
    "high_burnout_count": 1,
    "medium_burnout_count": 2,
    "single_point_functions": 1,
    "concentration_risks": 3
  },
  
  // 组织健康分数
  "health_score": {
    "overall": 78,
    "breakdown": {
      "network_health": 85,
      "function_coverage": 70,
      "risk_level": 65,
      "collaboration": 88
    }
  },
  
  "meta": {
    "computed_at": "2025-12-23T10:00:00Z",
    "computation_time_seconds": 45
  }
}
```

---

## 六、risk_alerts (风险预警)

```javascript
{
  "_id": ObjectId("..."),
  
  "risk_type": "single_point_failure",        // burnout/flight/single_point/concentration
  "severity": "high",                         // high/medium/low
  "status": "active",                         // active/acknowledged/resolved
  
  // 风险主体
  "subject": {
    "type": "function",                       // person/function/external_relation
    "id": "external_business",
    "name": "对外商务"
  },
  
  // 相关人员
  "related_persons": [
    {
      "email": "david.kneale@vulcanshield.com",
      "name": "David Kneale",
      "role": "sole_owner"
    }
  ],
  
  // 风险描述
  "description": "对外商务职能只有 David 一人核心负责，无备份",
  "impact": "David 离职将导致 303 个外部组织关系断裂",
  
  // 建议
  "recommendations": [
    "培养 Barry 或 Cindy 作为对外商务备份",
    "重要客户关系建立多人对接机制",
    "制定知识转移计划"
  ],
  
  // 元数据
  "meta": {
    "detected_at": "2025-12-23T10:00:00Z",
    "last_checked": "2025-12-23T10:00:00Z"
  }
}

// 索引
db.risk_alerts.createIndex({ "risk_type": 1, "severity": 1 })
db.risk_alerts.createIndex({ "status": 1 })
db.risk_alerts.createIndex({ "subject.type": 1, "subject.id": 1 })
```

---

## 七、索引策略

```javascript
// talent_nodes
db.talent_nodes.createIndex({ "network_metrics.hub_score": -1 })
db.talent_nodes.createIndex({ "network_metrics.bridge_score": -1 })
db.talent_nodes.createIndex({ "external_ecosystem.external_reach": -1 })
db.talent_nodes.createIndex({ "function_mapping.primary_function": 1 })
db.talent_nodes.createIndex({ "risk_metrics.burnout_risk": 1 })
db.talent_nodes.createIndex({ "network_metrics.community_id": 1 })

// talent_edges
db.talent_edges.createIndex({ "source": 1, "target": 1 }, { unique: true })
db.talent_edges.createIndex({ "interaction.total_count": -1 })

// function_domains
db.function_domains.createIndex({ "health.risk_level": 1 })

// risk_alerts
db.risk_alerts.createIndex({ "status": 1, "severity": -1 })
```

---

*最后更新: 2025-12-23*
