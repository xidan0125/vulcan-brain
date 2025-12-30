"""
AttachmentPreprocessor - 批量预处理附件为图片

功能:
- PDF → PNG (fitz)
- Excel → PDF → PNG (libreoffice + fitz)
- 图片 → 压缩优化
- 结果写入 MongoDB processed_assets
"""
import io
import base64
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import asyncio

import fitz  # PyMuPDF
from docx import Document  # python-docx
from PIL import Image
import pymongo

# ============ 配置 ============
ATTACHMENT_ROOT = Path("/home/xinyue/vulcan-brain/data/attachments")
PROCESSED_ROOT = Path("/home/xinyue/vulcan-brain/data/processed_assets")
MAX_IMAGE_SIZE = 1024  # 最长边像素
JPEG_QUALITY = 80
MAX_PAGES = 5  # 每个文档最多处理页数
PDF_DPI = 150


@dataclass
class ProcessedAsset:
    """处理后的资产"""
    source_attachment: str      # 原始文件名
    asset_type: str             # image 或 text
    asset_path: str             # 相对路径 (图片) 或空 (文本)
    page_number: int            # 页码 (从1开始)
    width: int                  # 图片宽度 (文本为0)
    height: int                 # 图片高度 (文本为0)
    size_bytes: int             # 文件大小
    created_at: datetime
    text_content: str = ""      # 文本内容 (仅 asset_type=text 时使用)


class AttachmentPreprocessor:
    """批量预处理附件为图片"""

    def __init__(self, mongo_uri: str = "mongodb://localhost:27017"):
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client.vulcan_brain
        self.emails = self.db.wecom_emails
        
        # 确保输出目录存在
        PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)

    async def process_emails(self, email_ids: List[str]) -> Dict[str, List[str]]:
        """
        处理多封邮件的附件
        
        Returns:
            {email_id: [image_path_1, image_path_2, ...]}
        """
        results = {}
        
        for email_id in email_ids:
            try:
                paths = await self.process_single_email(email_id)
                results[email_id] = paths
            except Exception as e:
                print(f"处理邮件 {email_id} 失败: {e}")
                results[email_id] = []
        
        return results

    async def process_single_email(self, email_id: str) -> List[str]:
        """处理单封邮件的所有附件"""
        email = self.emails.find_one({"email_id": email_id})
        if not email:
            raise ValueError(f"邮件不存在: {email_id}")
        
        attachments = email.get("attachments", [])
        if not attachments:
            return []
        
        processed_assets = []
        image_paths = []
        
        for att in attachments:
            filename = att.get("filename", "")
            file_path_rel = att.get("file_path", "")
            
            if not file_path_rel:
                continue
            
            file_path = ATTACHMENT_ROOT / file_path_rel
            if not file_path.exists():
                print(f"  文件不存在: {file_path}")
                continue
            
            # 处理附件
            assets = self._process_attachment(file_path, filename, email_id)
            
            for asset in assets:
                asset_dict = {
                    "source_attachment": asset.source_attachment,
                    "asset_type": asset.asset_type,
                    "asset_path": asset.asset_path,
                    "page_number": asset.page_number,
                    "width": asset.width,
                    "height": asset.height,
                    "size_bytes": asset.size_bytes,
                    "created_at": asset.created_at
                }
                if asset.asset_type == "text" and asset.text_content:
                    asset_dict["text_content"] = asset.text_content
                processed_assets.append(asset_dict)
                if asset.asset_path:
                    image_paths.append(asset.asset_path)
        
        # 写入 MongoDB
        if processed_assets:
            self.emails.update_one(
                {"email_id": email_id},
                {"$set": {
                    "processed_assets": processed_assets,
                    "processed_at": datetime.now()
                }}
            )
        
        return image_paths

    def _process_attachment(
        self, 
        file_path: Path, 
        filename: str, 
        email_id: str
    ) -> List[ProcessedAsset]:
        """处理单个附件，返回生成的资产列表"""
        suffix = file_path.suffix.lower()
        
        # 创建输出目录
        output_dir = PROCESSED_ROOT / email_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        assets = []
        
        try:
            if suffix == ".pdf":
                assets = self._convert_pdf_to_images(file_path, filename, output_dir)
            elif suffix in (".xlsx", ".xls", ".xlsm"):
                assets = self._convert_excel_to_images(file_path, filename, output_dir)
            elif suffix in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                assets = self._process_image(file_path, filename, output_dir)
            elif suffix in (".docx", ".doc"):
                assets = self._extract_docx_text(file_path, filename)
            else:
                print(f"  跳过不支持的格式: {suffix}")
        except Exception as e:
            print(f"  处理失败 {filename}: {e}")
        
        return assets

    def _convert_pdf_to_images(
        self, 
        pdf_path: Path, 
        filename: str, 
        output_dir: Path
    ) -> List[ProcessedAsset]:
        """PDF → PNG (使用 fitz)"""
        assets = []
        stem = pdf_path.stem
        
        try:
            doc = fitz.open(str(pdf_path))
            page_count = min(len(doc), MAX_PAGES)
            
            for page_num in range(page_count):
                page = doc[page_num]
                mat = fitz.Matrix(PDF_DPI / 72, PDF_DPI / 72)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # 压缩优化
                optimized, width, height = self._optimize_image(img_data)
                
                # 保存
                output_name = f"{stem}_page{page_num + 1}.jpg"
                output_path = output_dir / output_name
                output_path.write_bytes(optimized)
                
                # 相对路径
                rel_path = str(output_path.relative_to(PROCESSED_ROOT))
                
                assets.append(ProcessedAsset(
                    source_attachment=filename,
                    asset_type="image",
                    asset_path=rel_path,
                    page_number=page_num + 1,
                    width=width,
                    height=height,
                    size_bytes=len(optimized),
                    created_at=datetime.now()
                ))
            
            doc.close()
            print(f"  ✅ PDF转换: {filename} → {page_count} 页")
            
        except Exception as e:
            print(f"  ❌ PDF转换失败: {e}")
        
        return assets

    def _convert_excel_to_images(
        self, 
        excel_path: Path, 
        filename: str, 
        output_dir: Path
    ) -> List[ProcessedAsset]:
        """Excel → PDF → PNG (libreoffice + fitz)"""
        assets = []
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)
                
                # Step 1: Excel → PDF (LibreOffice)
                result = subprocess.run([
                    "libreoffice", "--headless", "--convert-to", "pdf",
                    "--outdir", str(tmpdir), str(excel_path)
                ], capture_output=True, timeout=60)
                
                # 找到生成的 PDF
                pdf_files = list(tmpdir.glob("*.pdf"))
                if not pdf_files:
                    print(f"  ❌ LibreOffice 未生成 PDF")
                    return assets
                
                pdf_path = pdf_files[0]
                
                # Step 2: PDF → PNG (复用 PDF 转换方法)
                assets = self._convert_pdf_to_images(pdf_path, filename, output_dir)
                
                if assets:
                    print(f"  ✅ Excel转换: {filename} → {len(assets)} 页")
                
        except subprocess.TimeoutExpired:
            print(f"  ❌ LibreOffice 超时")
        except Exception as e:
            print(f"  ❌ Excel转换失败: {e}")
        
        return assets

    def _process_image(
        self, 
        img_path: Path, 
        filename: str, 
        output_dir: Path
    ) -> List[ProcessedAsset]:
        """处理图片文件 - 压缩优化"""
        assets = []
        
        try:
            with open(img_path, "rb") as f:
                img_data = f.read()
            
            # 跳过小图片 (可能是签名/logo)
            if len(img_data) < 10000:  # < 10KB
                print(f"  ⏭️ 跳过小图片: {filename}")
                return assets
            
            # 压缩优化
            optimized, width, height = self._optimize_image(img_data)
            
            # 保存
            stem = img_path.stem
            output_name = f"{stem}.jpg"
            output_path = output_dir / output_name
            output_path.write_bytes(optimized)
            
            rel_path = str(output_path.relative_to(PROCESSED_ROOT))
            
            assets.append(ProcessedAsset(
                source_attachment=filename,
                asset_type="image",
                asset_path=rel_path,
                page_number=1,
                width=width,
                height=height,
                size_bytes=len(optimized),
                created_at=datetime.now()
            ))
            
            print(f"  ✅ 图片优化: {filename}")
            
        except Exception as e:
            print(f"  ❌ 图片处理失败: {e}")
        
        return assets


    def _extract_docx_text(
        self,
        docx_path: Path,
        filename: str
    ) -> List[ProcessedAsset]:
        """提取 Word 文档文本内容"""
        assets = []

        try:
            doc = Document(str(docx_path))

            # 提取所有段落文本
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)

            # 提取表格内容
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            row_text.append(cell_text)
                    if row_text:
                        paragraphs.append(" | ".join(row_text))

            full_text = "\n".join(paragraphs)

            if not full_text:
                print(f"  skip empty doc: {filename}")
                return assets

            # 截断过长文本
            max_chars = 8000
            if len(full_text) > max_chars:
                full_text = full_text[:max_chars] + "\n... [truncated]"

            assets.append(ProcessedAsset(
                source_attachment=filename,
                asset_type="text",
                asset_path="",
                page_number=1,
                width=0,
                height=0,
                size_bytes=len(full_text.encode('utf-8')),
                created_at=datetime.now(),
                text_content=full_text
            ))

            print(f"  Word: {filename} -> {len(full_text)} chars")

        except Exception as e:
            print(f"  Word failed: {e}")

        return assets

    def _optimize_image(self, img_data: bytes) -> Tuple[bytes, int, int]:
        """
        优化图片: Resize + JPEG 压缩
        
        Returns:
            (optimized_bytes, width, height)
        """
        img = Image.open(io.BytesIO(img_data))
        
        # 转 RGB (处理 RGBA/P 模式)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Resize
        w, h = img.size
        if max(w, h) > MAX_IMAGE_SIZE:
            if w > h:
                new_w = MAX_IMAGE_SIZE
                new_h = int(h * MAX_IMAGE_SIZE / w)
            else:
                new_h = MAX_IMAGE_SIZE
                new_w = int(w * MAX_IMAGE_SIZE / h)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            w, h = new_w, new_h
        
        # JPEG 压缩
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        
        return buffer.getvalue(), w, h

    def get_image_base64(self, asset_path: str) -> Optional[str]:
        """读取处理后的图片为 base64"""
        full_path = PROCESSED_ROOT / asset_path
        if not full_path.exists():
            return None
        
        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


# ============ 便捷函数 ============

_processor: Optional[AttachmentPreprocessor] = None


def get_processor() -> AttachmentPreprocessor:
    global _processor
    if _processor is None:
        _processor = AttachmentPreprocessor()
    return _processor


async def process_emails(email_ids: List[str]) -> Dict[str, List[str]]:
    """便捷函数: 处理多封邮件"""
    return await get_processor().process_emails(email_ids)


# ============ 测试 ============

async def _test():
    """测试附件处理"""
    processor = AttachmentPreprocessor()
    
    # 找一封有附件的邮件
    email = processor.emails.find_one({
        "attachments": {"$set": True, "": []}
    })
    
    if not email:
        print("未找到有附件的邮件")
        return
    
    email_id = email["email_id"]
    print(f"测试邮件: {email.get('subject', '')[:50]}")
    print(f"Email ID: {email_id}")
    print(f"附件数: {len(email.get('attachments', []))}")
    print()
    
    # 处理
    paths = await processor.process_single_email(email_id)
    
    print()
    print(f"生成资产: {len(paths)} 个")
    for p in paths:
        print(f"  - {p}")


if __name__ == "__main__":
    asyncio.run(_test())
