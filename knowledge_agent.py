"""
Knowledge Base Agent - 智能文档分析助手
基于文件结构和内容提供智能摘要

设计思路:
1. 预处理: 收集文件夹结构、文件名、文件大小等元数据
2. 工具层: 提供 list_files, read_file_names, analyze_structure 等工具
3. LLM层: 基于元数据生成智能摘要
4. 缓存层: 缓存结果避免重复分析
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import Form, Depends, HTTPException
from vulcan_libs.ai_service import generate_json, get_ai_service

# 摘要缓存
_summary_cache: dict = {}

# 文件类型分类
FILE_CATEGORIES = {
    "合同文档": [".pdf", ".doc", ".docx"],
    "财务数据": [".xlsx", ".xls", ".csv"],
    "技术图纸": [".dwg", ".dxf", ".cad"],
    "图片资料": [".png", ".jpg", ".jpeg", ".gif"],
    "压缩包": [".zip", ".rar", ".7z"],
    "演示文稿": [".ppt", ".pptx"],
}

# 业务关键词映射
BUSINESS_KEYWORDS = {
    "Admin": "行政管理与治理",
    "Corporate": "公司法人与股权结构",
    "Finance": "财务与税务",
    "HR": "人力资源",
    "Production": "生产制造",
    "Sales": "销售与市场",
    "Logistics": "物流与供应链",
    "Quality": "质量管理",
    "R&D": "研发与技术",
    "Legal": "法务合规",
    "IT": "信息技术",
    "Hungary": "匈牙利项目",
    "HU": "匈牙利项目",
}


def analyze_folder_structure(base_path: str, folder_path: str) -> Dict:
    """
    深度分析文件夹结构,提取关键信息
    这是给 AI 的"工具输出"
    """
    target_dir = os.path.join(base_path, folder_path) if folder_path else base_path

    if not os.path.exists(target_dir):
        return {"error": "文件夹不存在"}

    # 收集数据
    folders = []
    files = []
    file_types = {}
    total_size = 0
    keywords_found = []

    for entry in os.listdir(target_dir):
        entry_path = os.path.join(target_dir, entry)
        rel_path = os.path.join(folder_path, entry) if folder_path else entry

        if os.path.isdir(entry_path):
            # 分析子文件夹
            file_count = sum(1 for _, _, fs in os.walk(entry_path) for f in fs)

            # 提取业务关键词
            matched_keywords = []
            for kw, desc in BUSINESS_KEYWORDS.items():
                if kw.lower() in entry.lower():
                    matched_keywords.append(desc)

            folders.append({
                "name": entry,
                "path": rel_path,
                "file_count": file_count,
                "business_hint": matched_keywords[0] if matched_keywords else None
            })
        else:
            ext = os.path.splitext(entry)[1].lower()
            stat = os.stat(entry_path)
            size = stat.st_size
            total_size += size

            # 统计文件类型
            file_types[ext] = file_types.get(ext, 0) + 1

            files.append({
                "name": entry,
                "path": rel_path,
                "ext": ext,
                "size": size,
                "size_str": f"{size//1024}KB" if size < 1024*1024 else f"{size//(1024*1024)}MB"
            })

    # 识别文件类别
    categorized = {}
    for cat, exts in FILE_CATEGORIES.items():
        count = sum(file_types.get(e, 0) for e in exts)
        if count > 0:
            categorized[cat] = count

    # 深度判断
    depth = len(folder_path.split('/')) if folder_path else 0

    return {
        "folder_path": folder_path or "根目录",
        "depth": depth,
        "folder_count": len(folders),
        "file_count": len(files),
        "total_size": total_size,
        "total_size_str": f"{total_size//(1024*1024)}MB" if total_size > 1024*1024 else f"{total_size//1024}KB",
        "folders": folders,
        "files": files[:30],  # 限制文件数量避免 prompt 过长
        "file_types": file_types,
        "categorized": categorized,
        "has_more_files": len(files) > 30
    }


def build_smart_prompt(analysis: Dict) -> str:
    """
    构建智能 Prompt - 根据分析结果动态调整
    """
    depth = analysis["depth"]
    folder_count = analysis["folder_count"]
    file_count = analysis["file_count"]

    # 根据深度选择分析角度
    if depth == 0:
        focus = "整体架构和分类逻辑"
        detail = "描述文档库的整体组织结构,各模块的作用"
    elif depth == 1:
        focus = "该模块的业务职能"
        detail = "分析该分类下文档的业务价值和使用场景"
    else:
        focus = "具体文件的内容推断"
        detail = "根据文件名推断每个文件的具体内容和用途"

    # 构建文件夹描述
    folders_desc = ""
    if analysis["folders"]:
        folders_desc = "【子文件夹】\n"
        for f in analysis["folders"]:
            hint = f" ({f['business_hint']})" if f.get('business_hint') else ""
            folders_desc += f"  - {f['name']}{hint} 包含{f['file_count']}个文件\n"

    # 构建文件描述
    files_desc = ""
    if analysis["files"]:
        files_desc = "【文件列表】\n"
        for f in analysis["files"][:15]:
            files_desc += f"  - {f['name']} ({f['size_str']})\n"
        if analysis["has_more_files"]:
            files_desc += f"  - ... 还有更多文件\n"

    # 文件类型统计
    types_desc = ""
    if analysis["categorized"]:
        types_desc = "【文件类型】 " + ", ".join([f"{k}{v}个" for k, v in analysis["categorized"].items()])

    prompt = f"""你是企业文档管理专家。根据下面的文件夹信息,用中文写一段专业分析。

当前文件夹: {analysis['folder_path']}
层级深度: 第{depth}层
统计: {folder_count}个子文件夹, {file_count}个文件, 总大小{analysis['total_size_str']}

{folders_desc}
{files_desc}
{types_desc}

【任务】
从"{focus}"角度分析这个文件夹,{detail}。

【输出JSON格式】
返回一个JSON对象,包含:
1. "summary": 字符串,2-3句话描述这个文件夹的业务价值和主要内容(不要只说数量,要有实质分析)
2. "key_points": 字符串数组,3个关键发现或特点
3. "sources": 对象数组,每个对象有name/path/reason字段,列出3-5个最重要的文件或文件夹

直接返回JSON,不要任何其他文字。"""

    return prompt


async def smart_summarize(base_path: str, folder_path: str) -> Dict:
    """
    智能摘要 - 完整流程
    """
    global _summary_cache

    cache_key = folder_path or "_root_"
    if cache_key in _summary_cache:
        cached = _summary_cache[cache_key]
        cached["from_cache"] = True
        return cached

    # Step 1: 分析文件夹结构
    analysis = analyze_folder_structure(base_path, folder_path)
    if "error" in analysis:
        return {"error": analysis["error"]}

    # 如果没有内容可分析,返回简单结果
    if analysis["folder_count"] == 0 and analysis["file_count"] == 0:
        return {
            "summary": "这是一个空文件夹,暂无内容。",
            "key_points": [],
            "sources": [],
            "folder_path": folder_path,
            "depth": analysis["depth"],
            "file_count": 0,
            "folder_count": 0,
            "from_cache": False
        }

    # Step 2: 构建智能 Prompt
    prompt = build_smart_prompt(analysis)

    # Step 3: 调用 LLM
    try:
        result = await generate_json(prompt, temperature=0.3, max_tokens=1500)

        # 确保必要字段
        if not result.get("summary") or "2-3句" in result.get("summary", "") or "描述这个文件夹" in result.get("summary", ""):
            # 如果模型返回了模板文字,生成备用摘要
            result["summary"] = _generate_fallback_summary(analysis)

        if not result.get("key_points") or not isinstance(result["key_points"], list):
            result["key_points"] = _generate_fallback_key_points(analysis)

        if not result.get("sources") or not isinstance(result["sources"], list):
            result["sources"] = _generate_fallback_sources(analysis)

        # 添加元信息
        result["folder_path"] = folder_path
        result["depth"] = analysis["depth"]
        result["file_count"] = analysis["file_count"]
        result["folder_count"] = analysis["folder_count"]
        result["from_cache"] = False

        # 缓存
        _summary_cache[cache_key] = result

        return result

    except Exception as e:
        # 降级: 返回基于分析的基础摘要
        return {
            "summary": _generate_fallback_summary(analysis),
            "key_points": _generate_fallback_key_points(analysis),
            "sources": _generate_fallback_sources(analysis),
            "folder_path": folder_path,
            "depth": analysis["depth"],
            "file_count": analysis["file_count"],
            "folder_count": analysis["folder_count"],
            "error": str(e),
            "from_cache": False
        }


def _generate_fallback_summary(analysis: Dict) -> str:
    """生成备用摘要"""
    parts = []

    if analysis["folders"]:
        folder_names = [f["name"] for f in analysis["folders"][:3]]
        hints = [f["business_hint"] for f in analysis["folders"] if f.get("business_hint")]

        if hints:
            parts.append(f"主要包含{hints[0]}相关文档")
        else:
            parts.append(f"包含 {', '.join(folder_names)} 等{len(analysis['folders'])}个子目录")

    if analysis["categorized"]:
        cats = list(analysis["categorized"].keys())
        parts.append(f"文件类型以{cats[0]}为主")

    if analysis["total_size"] > 0:
        parts.append(f"总容量{analysis['total_size_str']}")

    return "，".join(parts) if parts else f"该文件夹包含 {analysis['folder_count']} 个子目录和 {analysis['file_count']} 个文件"


def _generate_fallback_key_points(analysis: Dict) -> List[str]:
    """生成备用要点"""
    points = []

    for f in analysis["folders"][:2]:
        if f.get("business_hint"):
            points.append(f"{f['name']}: {f['business_hint']}文档,{f['file_count']}个文件")
        else:
            points.append(f"{f['name']}: 包含{f['file_count']}个文件")

    if analysis["categorized"]:
        for cat, count in list(analysis["categorized"].items())[:1]:
            points.append(f"主要文件类型: {cat} ({count}个)")

    return points[:3]


def _generate_fallback_sources(analysis: Dict) -> List[Dict]:
    """生成备用来源"""
    sources = []

    for f in analysis["folders"][:3]:
        reason = f"包含{f['file_count']}个文件"
        if f.get("business_hint"):
            reason = f"{f['business_hint']}文档"
        sources.append({
            "name": f["name"],
            "path": f["path"],
            "reason": reason
        })

    for f in analysis["files"][:2]:
        sources.append({
            "name": f["name"],
            "path": f["path"],
            "reason": f"文件大小{f['size_str']}"
        })

    return sources[:5]


# 导出函数供 router 使用
__all__ = ['smart_summarize', '_summary_cache']
