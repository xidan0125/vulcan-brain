"""
Stage 2: VLM 附件提取器
- PNG/JPG: VLM 直接读取
- Excel: 转截图 -> VLM
- PDF: 提取文本 -> LLM 摘要
"""
import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests

# 配置
VLLM_BASE = "http://localhost:8000/v1"
VLLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Thinking-FP8"
ATTACHMENT_ROOT = Path("/home/xinyue/vulcan-brain/data/attachments")


def call_vlm(prompt: str, image_base64: Optional[str] = None, max_tokens: int = 2000) -> str:
    """调用 vLLM (Qwen3-VL)"""
    content = [{"type": "text", "text": prompt}]
    
    if image_base64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })
    
    try:
        response = requests.post(
            f"{VLLM_BASE}/chat/completions",
            json={
                "model": VLLM_MODEL,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": max_tokens,
                "temperature": 0.1
            },
            timeout=120
        )
        result = response.json()
        text = result["choices"][0]["message"]["content"]
        
        # 去除 thinking 部分
        if "</think>" in text:
            text = text.split("</think>")[-1].strip()
        
        return text
    except Exception as e:
        return f"VLM调用失败: {e}"


def read_image_base64(file_path: Path) -> Optional[str]:
    """读取图片为 base64"""
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"读取图片失败: {e}")
        return None


def excel_to_screenshot(excel_path: Path) -> Optional[str]:
    """将 Excel 转为截图 (使用 LibreOffice)"""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # LibreOffice 导出为 PDF
            pdf_path = Path(tmpdir) / "output.pdf"
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", tmpdir, str(excel_path)
            ], capture_output=True, timeout=30)
            
            # 找到生成的 PDF
            pdf_files = list(Path(tmpdir).glob("*.pdf"))
            if not pdf_files:
                return None
            
            # PDF 转 PNG (使用 pdftoppm)
            png_path = Path(tmpdir) / "page"
            subprocess.run([
                "pdftoppm", "-png", "-f", "1", "-l", "1",
                str(pdf_files[0]), str(png_path)
            ], capture_output=True, timeout=30)
            
            # 读取生成的 PNG
            png_files = list(Path(tmpdir).glob("*.png"))
            if png_files:
                return read_image_base64(png_files[0])
    except Exception as e:
        print(f"Excel转截图失败: {e}")
    
    return None


def extract_pdf_text(pdf_path: Path) -> str:
    """提取 PDF 文本"""
    try:
        # 尝试 pdftotext
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout[:5000]  # 限制长度
    except Exception as e:
        print(f"PDF提取失败: {e}")
    
    return ""


def process_attachment(attachment: Dict, company: str) -> Dict[str, Any]:
    """处理单个附件，返回提取的结构化信息"""
    filename = attachment.get("filename", "")
    file_path_rel = attachment.get("file_path", "")
    
    if not file_path_rel:
        return {"filename": filename, "extracted": None, "error": "无文件路径"}
    
    file_path = ATTACHMENT_ROOT / file_path_rel
    
    if not file_path.exists():
        return {"filename": filename, "extracted": None, "error": "文件不存在"}
    
    suffix = file_path.suffix.lower()
    result = {"filename": filename, "file_path": str(file_path), "type": suffix}
    
    # 图片: 直接 VLM
    if suffix in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
        # 跳过小图片（可能是签名/logo）
        if file_path.stat().st_size < 10000:  # < 10KB
            result["extracted"] = None
            result["skip_reason"] = "小图片(可能是签名)"
            return result
        
        image_b64 = read_image_base64(file_path)
        if image_b64:
            prompt = """分析这张图片，提取所有业务相关信息。
如果是表格/表单，输出结构化JSON: {document_type, key_data: {...}}
如果是其他内容，简要描述关键信息。"""
            extracted = call_vlm(prompt, image_b64)
            result["extracted"] = extracted
        else:
            result["error"] = "图片读取失败"
    
    # Excel: 转截图 -> VLM
    elif suffix in [".xlsx", ".xls", ".xlsm"]:
        image_b64 = excel_to_screenshot(file_path)
        if image_b64:
            prompt = """这是一份Excel表格的截图。请提取关键业务数据：
- 表格类型（订单/报价/托书/其他）
- 关键字段和数值
- 日期/截止时间
- 联系人信息
输出JSON格式。"""
            extracted = call_vlm(prompt, image_b64)
            result["extracted"] = extracted
        else:
            result["error"] = "Excel转图失败"
            # 备选：直接用文件名推断
            result["inferred"] = f"Excel文件: {filename}"
    
    # PDF: 提取文本
    elif suffix == ".pdf":
        text = extract_pdf_text(file_path)
        if text:
            # 用 LLM 摘要
            prompt = f"""以下是PDF文档内容，请提取关键业务信息（JSON格式）：

{text[:3000]}

提取：document_type, key_points, dates, amounts（如有）"""
            extracted = call_vlm(prompt)
            result["extracted"] = extracted
        else:
            result["extracted"] = None
            result["note"] = "PDF无文本(可能是扫描件)"
    
    # 其他文件类型
    else:
        result["extracted"] = None
        result["note"] = f"不支持的文件类型: {suffix}"
    
    return result


def process_thread_attachments(attachments: List[Dict], company: str) -> List[Dict]:
    """处理一个 thread 的所有附件"""
    results = []
    
    for att in attachments:
        # 跳过内嵌图片（通常是邮件签名）
        filename = att.get("filename", "")
        if "@" in filename or filename.startswith("image00"):
            continue
        
        result = process_attachment(att, company)
        if result.get("extracted") or result.get("error"):
            results.append(result)
    
    return results


# 测试
if __name__ == "__main__":
    # 测试客户需求表图片
    test_att = {
        "filename": "客户需求信息确认表-北京石墨烯1225.png",
        "file_path": "shanghai/2025-12/15b42a52457c5c0b729cb3c77b49fe4c/客户需求信息确认表-北京石墨烯1225.png"
    }
    result = process_attachment(test_att, "shanghai")
    print("=== 测试结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
