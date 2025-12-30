"""
Knowledge Agent Prompts
系统提示词 + 动态Prompt构建
"""

# 文件夹结构分析提示词
FOLDER_ANALYSIS_PROMPT = """你是VSG公司的企业文档分析助手。请分析文件夹结构，理解业务含义，生成专业摘要。

## 分析策略
- **根目录(深度0)**: 宏观视角，描述整体架构和主要业务模块
- **一级目录(深度1)**: 模块视角，分析该业务领域的文档构成
- **二级及以下(深度2+)**: 微观视角，具体分析文件内容和用途

## 业务关键词
- Admin/行政 → 行政管理
- Corporate → 公司法人
- Finance → 财务税务
- HR → 人力资源
- Production → 生产制造
- Sales → 销售市场
- Invoice → 发票账单
- Contract → 合同协议
- PO → 采购订单

## 输出格式
返回JSON:
```json
{
  "summary": "2-3句话的业务价值分析",
  "key_points": ["发现1", "发现2", "发现3"],
  "sources": [{"name": "名称", "path": "路径", "reason": "重要性说明"}]
}
```

直接返回JSON，不要其他文字。"""


# 文档内容VLM提取提示词 - 智能结构化
DOCUMENT_VLM_PROMPT = """你是顶尖的商业文档分析专家，服务于VSG集团（一家跨国制造业企业）。

## 你的任务
分析这份商业文档，提取关键信息并以最适合该文档的结构化方式呈现。

## 分析原则
1. **先理解，后结构化**：先理解文档的类型、目的和核心内容，再决定用什么结构来呈现
2. **信息完整性**：提取所有对商业决策有价值的信息
3. **层次分明**：用清晰的层级结构组织信息
4. **智能分类**：根据文档特点选择最合适的信息分类方式

## 输出格式
返回JSON，包含以下字段：

```json
{
  "document_type": "文档类型（如：会议纪要、合同、发票、订单、报告、邮件等）",
  "summary": "一句话概括文档核心内容",
  "structured_content": [
    {
      "section": "章节/类别名称（根据文档内容自行决定最佳分类）",
      "items": ["要点1", "要点2", "..."]
    }
  ],
  "entities": {
    "companies": ["涉及的公司/机构"],
    "people": ["涉及的人员"],
    "amounts": ["金额数字"],
    "dates": ["日期时间"],
    "locations": ["地点"]
  }
}
```

## structured_content 设计指南
根据文档类型智能选择分类方式，例如：
- 会议纪要 → "讨论议题"、"决议事项"、"行动计划"
- 合同 → "合同双方"、"核心条款"、"权利义务"、"重要日期"
- 发票/订单 → "商品明细"、"金额汇总"、"付款信息"
- 报告 → "主要发现"、"数据亮点"、"建议措施"
- 邮件 → "请求事项"、"关键信息"、"待回复问题"

你应该根据实际文档内容灵活决定最佳的结构化方式，不必拘泥于以上示例。

只返回JSON，不要其他解释。"""


# 多页文档汇总提示词
DOCUMENT_SUMMARY_PROMPT = """你是企业文档分析专家。以下是一份多页文档的逐页分析结果，请汇总成完整的文档摘要。

## 逐页分析
{page_analyses}

## 输出格式
返回JSON，合并所有页面的信息，去重整合：
```json
{{
  "document_type": "文档类型",
  "summary": "完整文档概述",
  "structured_content": [
    {{"section": "分类名", "items": ["要点"]}}
  ],
  "entities": {{
    "companies": [],
    "people": [],
    "amounts": [],
    "dates": [],
    "locations": []
  }},
  "page_count": {page_count}
}}
```

只返回JSON。"""


def build_folder_analysis_prompt(analysis_result: dict) -> str:
    """构建文件夹分析Prompt"""
    depth = analysis_result.get("depth", 0)
    folder_path = analysis_result.get("folder_path", "根目录")
    folder_count = analysis_result.get("folder_count", 0)
    file_count = analysis_result.get("file_count", 0)
    vlm_count = analysis_result.get("vlm_file_count", 0)
    total_size = analysis_result.get("total_size_str", "0KB")

    if depth == 0:
        focus = "整体架构分析"
        detail = "分析文档库的整体组织结构，识别主要业务模块"
    elif depth == 1:
        focus = "业务模块分析"
        detail = "分析该模块的业务职能，文档类型构成"
    else:
        focus = "具体内容分析"
        detail = "根据文件名推断每个文件的具体内容和业务价值"

    folders_section = ""
    if analysis_result.get("folders"):
        folders_section = "【子文件夹】\n"
        for f in analysis_result["folders"]:
            hint = f" [{f['business_hint']}]" if f.get('business_hint') else ""
            folders_section += f"  • {f['name']}{hint} - {f['file_count']}个文件\n"

    files_section = ""
    if analysis_result.get("files"):
        files_section = "【文件列表】\n"
        for f in analysis_result["files"][:20]:
            vlm_tag = " [可分析]" if f.get("vlm_supported") else ""
            files_section += f"  • {f['name']} ({f['size_str']}){vlm_tag}\n"
        if analysis_result.get("has_more_files"):
            files_section += f"  ... 还有更多文件\n"

    types_section = ""
    if analysis_result.get("categorized"):
        types_parts = [f"{cat}: {count}个" for cat, count in analysis_result["categorized"].items()]
        types_section = "【文件类型】 " + " | ".join(types_parts)

    prompt = f"""## 任务: {focus}

## 文件夹信息
- 路径: {folder_path}
- 层级: 第{depth}层
- 包含: {folder_count}个子文件夹, {file_count}个文件 (其中{vlm_count}个可深度分析)
- 总大小: {total_size}

{folders_section}
{files_section}
{types_section}

## 分析要求
{detail}

请输出JSON格式的分析结果:
- summary: 有实际业务洞察的摘要
- key_points: 3-4个具体发现
- sources: 最重要的3-5项

直接返回JSON:"""

    return prompt


def build_document_vlm_prompt(file_name: str, page_num: int = 1) -> str:
    """构建文档VLM分析Prompt"""
    return f"""分析文件 "{file_name}" 第 {page_num} 页。

{DOCUMENT_VLM_PROMPT}"""


def build_summary_prompt(page_analyses: list, page_count: int) -> str:
    """构建多页汇总Prompt"""
    analyses_text = ""
    for i, analysis in enumerate(page_analyses):
        analyses_text += f"\n### 第{i+1}页\n{analysis}\n"

    return DOCUMENT_SUMMARY_PROMPT.format(
        page_analyses=analyses_text,
        page_count=page_count
    )
