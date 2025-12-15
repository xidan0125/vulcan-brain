# Architecture Analysis Context

## 1. Project Metadata

- **Project Name**: {{ project_name }}
- **Analysis Date**: {{ analysis_date }}
- **Development Phase**: {{ dev_phase }}
- **User Query**: {{ user_query }}

---

## 2. Project Directory Structure

以下是项目的完整目录结构：

```
{{ directory_tree }}
```

---

## 3. Key Files Content

以下是核心代码文件的内容（按重要性排序）：

{% for file in files %}
### File: `{{ file.path }}`
- **Size**: {{ file.size }} bytes
- **Lines**: {{ file.lines }}
- **Type**: {{ file.type }}

```{{ file.language }}
{{ file.content }}
```

---
{% endfor %}

## 4. Additional Context

### 已知的技术栈
{{ tech_stack }}

### 团队规模
{{ team_size }}

### 业务背景
{{ business_context }}

---

## 5. Analysis Request

请基于以上代码和上下文，回答核心问题框架中的 6 个问题，并输出结构化的架构分析报告。

重点关注：
1. 一级模块的边界划分是否合理
2. 模块间的依赖关系是否健康
3. 最需要立即修复的架构问题
4. 可落地的演进路径建议

