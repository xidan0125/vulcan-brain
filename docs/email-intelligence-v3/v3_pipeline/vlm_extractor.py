#!/usr/bin/env python3
"""
V3 VLM提取器
使用 Qwen3-VL 视觉模型直接从文档图片中提取结构化信息
"""
import base64
import fitz  # PyMuPDF - 仅用于PDF转图片
import requests
from pathlib import Path
from typing import Dict, List, Optional
import json

# vLLM 服务配置
VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL_NAME = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"

# 提取 Prompt
EXTRACTION_PROMPT = """你是一个B2B商业文档分析专家。请仔细查看这份文档图片，提取所有关键商业信息。

请以JSON格式返回，包含以下字段（如有）：

{
  "document_type": "发票/订单/报价单/合同/装箱单/图纸/其他",
  "facts": [
    {
      "type": "金额/数量/日期/产品/公司/人员/地址/联系方式/其他",
      "value": "具体值",
      "context": "上下文说明",
      "confidence": 0.9
    }
  ],
  "entities": {
    "companies": ["公司名1", "公司名2"],
    "products": ["产品1", "产品2"],
    "amounts": ["金额1", "金额2"],
    "dates": ["日期1", "日期2"]
  },
  "summary": "一句话概述这份文档的内容"
}

只返回JSON，不要其他解释。"""


class VLMExtractor:
    """VLM视觉提取器"""

    def __init__(self, vllm_url: str = VLLM_URL):
        self.vllm_url = vllm_url

    def _file_to_base64(self, file_path: Path) -> str:
        """文件转base64"""
        return base64.b64encode(file_path.read_bytes()).decode()

    def _pdf_page_to_base64(self, pdf_path: Path, page_num: int = 0, dpi: int = 150) -> str:
        """PDF单页转base64图片"""
        doc = fitz.open(str(pdf_path))
        page = doc[page_num]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()
        return base64.b64encode(img_bytes).decode()

    def _get_mime_type(self, file_path: Path) -> str:
        """获取MIME类型"""
        suffix = file_path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
        }
        return mime_map.get(suffix, "application/octet-stream")

    def extract_from_image(self, image_base64: str,
                          mime_type: str = "image/png",
                          prompt: str = EXTRACTION_PROMPT) -> Dict:
        """从图片提取信息"""

        payload = {
            "model": MODEL_NAME,
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

        resp = requests.post(self.vllm_url, json=payload, timeout=120)
        resp.raise_for_status()

        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        # 尝试解析JSON
        try:
            # 处理thinking模式的输出 (</think>标签)
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()

            # 处理可能的markdown代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {"raw_response": content, "parse_error": True}

    def extract_from_file(self, file_path: Path) -> Dict:
        """从文件提取信息（自动处理PDF和图片）"""
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            # PDF: 获取页数，逐页处理
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            doc.close()

            all_results = []
            for page_num in range(min(page_count, 10)):  # 最多处理10页
                img_b64 = self._pdf_page_to_base64(file_path, page_num)
                result = self.extract_from_image(img_b64, "image/png")
                result["page"] = page_num + 1
                all_results.append(result)

            return {
                "file": file_path.name,
                "type": "pdf",
                "page_count": page_count,
                "extractions": all_results
            }

        elif suffix in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"]:
            img_b64 = self._file_to_base64(file_path)
            mime = self._get_mime_type(file_path)
            result = self.extract_from_image(img_b64, mime)
            return {
                "file": file_path.name,
                "type": "image",
                "extraction": result
            }

        else:
            return {
                "file": file_path.name,
                "type": "unsupported",
                "error": f"Unsupported file type: {suffix}"
            }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python vlm_extractor.py <file_path>")
        print("       python vlm_extractor.py --test-connection")
        sys.exit(1)

    if sys.argv[1] == "--test-connection":
        # 测试VLM服务连接
        try:
            resp = requests.get("http://localhost:8000/v1/models", timeout=5)
            print(f"VLM Service: OK")
            print(f"Models: {resp.json()}")
        except Exception as e:
            print(f"VLM Service: FAILED - {e}")
        sys.exit(0)

    extractor = VLMExtractor()
    result = extractor.extract_from_file(Path(sys.argv[1]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
