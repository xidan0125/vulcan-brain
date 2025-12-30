"""
Knowledge Agent Core
智能文档分析Agent - 支持VLM深度分析
"""

import os
import json
import httpx
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .tools import (
    analyze_folder_structure,
    file_to_images,
    get_vlm_type,
    extract_word_text,
)
from .prompts import (
    FOLDER_ANALYSIS_PROMPT,
    DOCUMENT_VLM_PROMPT,
    build_folder_analysis_prompt,
    build_document_vlm_prompt,
    build_summary_prompt,
)

# vLLM 配置
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000/v1/chat/completions")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8")

# 深度阈值 - 超过此深度启用VLM分析
VLM_DEPTH_THRESHOLD = 2


@dataclass
class AnalysisResult:
    """分析结果"""
    summary: str
    key_points: List[str]
    sources: List[Dict]
    folder_path: str
    depth: int
    file_count: int
    folder_count: int
    from_cache: bool = False
    vlm_analyzed: bool = False
    error: Optional[str] = None


class KnowledgeAgent:
    """
    知识库智能分析Agent

    分析策略:
    - 浅层(0-1): 基于文件夹结构分析
    - 深层(2+): 启用VLM分析文件内容
    """

    def __init__(self, base_path: str):
        self.base_path = base_path
        self._summary_cache: Dict[str, Dict] = {}
        self._file_cache: Dict[str, Dict] = {}

    async def summarize(self, folder_path: str = "", force_refresh: bool = False) -> Dict:
        """
        生成文件夹智能摘要

        Args:
            folder_path: 相对路径
            force_refresh: 强制刷新缓存

        Returns:
            分析结果字典
        """
        cache_key = folder_path or "_root_"

        # 检查缓存
        if not force_refresh and cache_key in self._summary_cache:
            cached = self._summary_cache[cache_key].copy()
            cached["from_cache"] = True
            return cached

        # Step 1: 分析文件夹结构
        analysis = analyze_folder_structure(self.base_path, folder_path)

        if "error" in analysis:
            return {
                "error": analysis["error"],
                "folder_path": folder_path,
                "from_cache": False
            }

        # 空文件夹
        if analysis["folder_count"] == 0 and analysis["file_count"] == 0:
            return {
                "summary": "这是一个空文件夹，暂无内容。",
                "key_points": [],
                "sources": [],
                "folder_path": folder_path,
                "depth": analysis["depth"],
                "file_count": 0,
                "folder_count": 0,
                "vlm_analyzed": False,
                "from_cache": False
            }

        # Step 2: 始终使用结构分析 (VLM分析仅在点击文件时触发)
        depth = analysis["depth"]
        vlm_analyzed = False
        
        # 文件夹摘要始终用快速结构分析
        # VLM深度分析仅在用户点击具体文件时触发 (analyze_file endpoint)
        result = await self._structure_analysis(analysis)

        # 验证和修复结果
        result = self._validate_result(result, analysis)

        # 添加元信息
        result["folder_path"] = folder_path
        result["depth"] = analysis["depth"]
        result["file_count"] = analysis["file_count"]
        result["folder_count"] = analysis["folder_count"]
        result["vlm_analyzed"] = vlm_analyzed
        result["from_cache"] = False

        # 只缓存有内容的结果
        self._summary_cache[cache_key] = result.copy()

        return result

    async def analyze_file(self, file_path: str, force_refresh: bool = False) -> Dict:
        """
        分析单个文件内容
        - Word文档: 提取文本 + LLM分析（快速）
        - PDF/图片: VLM视觉分析
        """
        cache_key = file_path

        if not force_refresh and cache_key in self._file_cache:
            cached = self._file_cache[cache_key].copy()
            cached["from_cache"] = True
            return cached

        full_path = os.path.join(self.base_path, file_path)

        if not os.path.exists(full_path):
            return {"error": "文件不存在", "file_path": file_path}

        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()

        # Word文档：直接提取文本，用LLM分析（快速）
        if ext in ['.docx', '.doc']:
            result = await self._analyze_word_file(full_path, file_name)
        else:
            # PDF/图片：VLM视觉分析
            result = await self._analyze_with_vlm(full_path, file_name)

        result["file_path"] = file_path
        result["file_name"] = file_name
        result["from_cache"] = False

        # 只缓存有内容的结果
        if result.get("summary") and not result.get("error"):
            self._file_cache[cache_key] = result.copy()

        return result

    async def _analyze_word_file(self, full_path: str, file_name: str) -> Dict:
        """Word文档分析 - 提取文本后用LLM"""
        text = extract_word_text(full_path)

        if not text or len(text.strip()) < 10:
            return {"error": "无法提取Word文档内容"}

        # 截断过长文本
        if len(text) > 15000:
            text = text[:15000] + "\n... (内容过长，已截断)"

        prompt = f"""分析以下Word文档内容，文件名: {file_name}

{DOCUMENT_VLM_PROMPT}

文档内容:
{text}
"""

        try:
            result = await self._call_llm(prompt)
            return result
        except Exception as e:
            return {"error": f"分析失败: {str(e)}"}

    async def _analyze_with_vlm(self, full_path: str, file_name: str) -> Dict:
        """PDF/图片分析 - VLM视觉分析"""
        images = file_to_images(full_path, max_pages=10, dpi=200)

        if not images or "error" in images[0]:
            error = images[0].get("error", "转换失败") if images else "未知错误"
            return {"error": error}

        page_results = []

        for img_data in images:
            if "error" in img_data or "info" in img_data:
                continue

            page_num = img_data.get("page", 1)
            prompt = build_document_vlm_prompt(file_name, page_num)

            try:
                page_result = await self._call_vlm_with_image(
                    img_data["base64"],
                    img_data["mime"],
                    prompt
                )
                page_result["page"] = page_num
                page_results.append(page_result)
            except Exception as e:
                page_results.append({"page": page_num, "error": str(e)})

        if len(page_results) > 1:
            return await self._summarize_pages(page_results, len(images))
        elif page_results:
            return page_results[0]
        else:
            return {"error": "无法分析文件内容"}

    async def _structure_analysis(self, analysis: Dict) -> Dict:
        """基于结构的分析（浅层）"""
        prompt = build_folder_analysis_prompt(analysis)

        try:
            result = await self._call_llm(prompt, FOLDER_ANALYSIS_PROMPT)
            return result
        except Exception as e:
            return self._generate_fallback(analysis, str(e))

    async def _vlm_deep_analysis(self, analysis: Dict) -> Dict:
        """VLM深度分析（深层）"""
        # 选择可分析的文件（优先PDF和Excel）
        vlm_files = [
            f for f in analysis.get("files", [])
            if f.get("vlm_supported")
        ]

        # 按重要性排序：PDF > Excel > 图片
        priority = {"pdf": 0, "excel": 1, "direct_image": 2}
        vlm_files.sort(key=lambda f: priority.get(f.get("vlm_type"), 3))

        # 最多分析3个文件
        files_to_analyze = vlm_files[:3]

        if not files_to_analyze:
            # 没有可分析的文件，回退到结构分析
            return await self._structure_analysis(analysis)

        # 分析文件
        file_summaries = []
        for f in files_to_analyze:
            file_result = await self.analyze_file(f["path"])
            if "error" not in file_result:
                file_summaries.append({
                    "file": f["name"],
                    "type": file_result.get("document_type", "未知"),
                    "summary": file_result.get("summary", ""),
                    "entities": file_result.get("entities", {})
                })

        # 生成摘要
        if file_summaries:
            summary_parts = []
            key_points = []
            sources = []

            for fs in file_summaries:
                if fs.get("summary"):
                    summary_parts.append(f"{fs['file']}: {fs['summary']}")
                if fs.get("type"):
                    key_points.append(f"【{fs['file']}】{fs['type']}文档")
                sources.append({
                    "name": fs["file"],
                    "path": fs.get("path", ""),
                    "reason": fs.get("type", "可分析文档")
                })

            return {
                "summary": "；".join(summary_parts) if summary_parts else "已分析文件内容",
                "key_points": key_points[:4],
                "sources": sources[:5],
                "file_analyses": file_summaries
            }

        # 回退
        return await self._structure_analysis(analysis)

    async def _call_llm(self, prompt: str, system_prompt: str = "") -> Dict:
        """调用LLM（纯文本）"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": VLLM_MODEL,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.3
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(VLLM_URL, json=payload)
            resp.raise_for_status()

        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        return self._parse_json_response(content)

    async def _call_vlm_with_image(self, image_base64: str, mime_type: str, prompt: str) -> Dict:
        """调用VLM（带图片）"""
        payload = {
            "model": VLLM_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(VLLM_URL, json=payload)
            resp.raise_for_status()

        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        return self._parse_json_response(content)

    async def _summarize_pages(self, page_results: List[Dict], page_count: int) -> Dict:
        """汇总多页分析结果"""
        # 构建汇总prompt
        analyses_text = json.dumps(page_results, ensure_ascii=False, indent=2)
        prompt = build_summary_prompt(page_results, page_count)

        try:
            return await self._call_llm(prompt)
        except:
            # 简单合并
            all_facts = []
            all_entities = {"companies": [], "products": [], "amounts": [], "dates": []}

            for pr in page_results:
                if "key_facts" in pr:
                    all_facts.extend(pr["key_facts"])
                if "entities" in pr:
                    for k, v in pr["entities"].items():
                        if k in all_entities and isinstance(v, list):
                            all_entities[k].extend(v)

            # 去重
            for k in all_entities:
                all_entities[k] = list(set(all_entities[k]))

            return {
                "summary": page_results[0].get("summary", "") if page_results else "",
                "document_type": page_results[0].get("document_type", "未知") if page_results else "未知",
                "key_facts": all_facts[:10],
                "entities": all_entities,
                "page_count": page_count
            }

    def _parse_json_response(self, content: str) -> Dict:
        print(f"[VLM RAW] {content[:500]}...")  # Debug
        """解析LLM返回的JSON"""
        # 处理thinking模式
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()

        # 处理markdown代码块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {"raw_response": content, "parse_error": True}

    def _validate_result(self, result: Dict, analysis: Dict) -> Dict:
        """验证并修复结果"""
        bad_patterns = ["2-3句", "核心摘要", "业务价值", "描述这个文件夹", "发现1", "发现2"]

        summary = result.get("summary", "")
        if not summary or any(p in summary for p in bad_patterns) or result.get("parse_error"):
            result["summary"] = self._generate_smart_summary(analysis)

        key_points = result.get("key_points", [])
        if not key_points or not isinstance(key_points, list):
            result["key_points"] = self._generate_smart_key_points(analysis)

        sources = result.get("sources", [])
        if not sources or not isinstance(sources, list):
            result["sources"] = self._generate_smart_sources(analysis)

        return result

    def _generate_fallback(self, analysis: Dict, error: str = "") -> Dict:
        """生成备用结果"""
        return {
            "summary": self._generate_smart_summary(analysis),
            "key_points": self._generate_smart_key_points(analysis),
            "sources": self._generate_smart_sources(analysis),
            "error": error if error else None
        }

    def _generate_smart_summary(self, analysis: Dict) -> str:
        """生成智能摘要"""
        parts = []
        depth = analysis.get("depth", 0)

        if analysis.get("folders"):
            hints = [f["business_hint"] for f in analysis["folders"] if f.get("business_hint")]
            if hints:
                unique_hints = list(dict.fromkeys(hints))[:3]
                parts.append(f"涵盖{', '.join(unique_hints)}等业务领域")
            else:
                folder_names = [f["name"] for f in analysis["folders"][:3]]
                parts.append(f"包含{', '.join(folder_names)}等{len(analysis['folders'])}个模块")

        if analysis.get("categorized"):
            cats = list(analysis["categorized"].keys())
            parts.append(f"主要为{cats[0]}类型文件")

        if analysis.get("total_size", 0) > 0:
            parts.append(f"总容量{analysis['total_size_str']}")

        return "，".join(parts) + "。" if parts else f"包含{analysis['file_count']}个文件"

    def _generate_smart_key_points(self, analysis: Dict) -> List[str]:
        """生成智能要点"""
        points = []

        for f in analysis.get("folders", [])[:2]:
            if f.get("business_hint"):
                points.append(f"【{f['name']}】{f['business_hint']}文档，{f['file_count']}个文件")

        for cat, count in list(analysis.get("categorized", {}).items())[:2]:
            if count > 3:
                points.append(f"包含{count}个{cat}文件")

        return points[:4] if points else ["文件夹内容待整理"]

    def _generate_smart_sources(self, analysis: Dict) -> List[Dict]:
        """生成智能来源"""
        sources = []

        for f in analysis.get("folders", [])[:3]:
            reason = f.get("business_hint") or f"包含{f['file_count']}个文件"
            sources.append({"name": f["name"], "path": f["path"], "reason": reason})

        for f in analysis.get("files", [])[:2]:
            if f.get("vlm_supported"):
                sources.append({
                    "name": f["name"],
                    "path": f["path"],
                    "reason": f"可深度分析的{f['ext'][1:].upper()}文件"
                })

        return sources[:5]

    def clear_cache(self, folder_path: Optional[str] = None) -> int:
        """清除缓存"""
        if folder_path is None:
            count = len(self._summary_cache) + len(self._file_cache)
            self._summary_cache.clear()
            self._file_cache.clear()
            return count
        else:
            count = 0
            cache_key = folder_path or "_root_"
            if cache_key in self._summary_cache:
                del self._summary_cache[cache_key]
                count += 1
            if folder_path in self._file_cache:
                del self._file_cache[folder_path]
                count += 1
            return count


# 模块级共享
_agent_instance: Optional[KnowledgeAgent] = None
_summary_cache: Dict[str, Dict] = {}


def get_agent(base_path: str) -> KnowledgeAgent:
    """获取Agent实例"""
    global _agent_instance
    if _agent_instance is None or _agent_instance.base_path != base_path:
        _agent_instance = KnowledgeAgent(base_path)
        _agent_instance._summary_cache = _summary_cache
    return _agent_instance


async def smart_summarize(base_path: str, folder_path: str) -> Dict:
    """便捷函数：智能摘要"""
    agent = get_agent(base_path)
    return await agent.summarize(folder_path)
