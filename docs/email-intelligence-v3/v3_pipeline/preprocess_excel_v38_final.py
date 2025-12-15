#!/usr/bin/env python3
"""
V3.8 Excel 预处理脚本 (最终版)
目录结构: images/<attachment_stem>/page_<n>.jpg
与 PDF/图片 统一规则，方便 batch_extractor 加载
"""
import os
import subprocess
import tempfile
from pathlib import Path
from pdf2image import convert_from_path
import json
from datetime import datetime

CACHE_DIR = Path.home() / "vulcan_data" / "cache"
RAW_DIR = CACHE_DIR / "raw"
IMAGES_DIR = CACHE_DIR / "images"

DPI = 150
MAX_PAGES = 5

def process_excel(excel_path: Path) -> list:
    """Excel -> 图片列表，目录名 = stem"""
    out_dir = IMAGES_DIR / excel_path.stem
    out_dir.mkdir(exist_ok=True)

    # 检查是否已处理
    existing_jpgs = list(out_dir.glob("page_*.jpg"))
    if existing_jpgs:
        return existing_jpgs

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Excel -> PDF
            result = subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", tmpdir, str(excel_path)
            ], capture_output=True, timeout=120)

            if result.returncode != 0:
                return []

            pdf_files = list(Path(tmpdir).glob("*.pdf"))
            if not pdf_files:
                return []

            # PDF -> Images
            images = convert_from_path(str(pdf_files[0]), dpi=DPI)

            # 保存
            saved = []
            for i, img in enumerate(images[:MAX_PAGES]):
                jpg_path = out_dir / f"page_{i+1}.jpg"
                img.save(str(jpg_path), "JPEG", quality=85)
                saved.append(jpg_path)

            return saved

    except Exception as e:
        print(f"    错误: {e}")
        return []

def main():
    print("=" * 60)
    print("🔧 V3.8 Excel 预处理 (统一目录结构)")
    print("=" * 60)
    print(f"规则: images/<stem>/page_<n>.jpg")
    print(f"时间: {datetime.now()}\n")

    IMAGES_DIR.mkdir(exist_ok=True)

    excel_files = list(RAW_DIR.glob("*.xlsx")) + list(RAW_DIR.glob("*.xls"))
    print(f"📁 Excel 文件: {len(excel_files)}")

    # 统计已处理
    already = sum(1 for f in excel_files if (IMAGES_DIR / f.stem).exists() and list((IMAGES_DIR / f.stem).glob("page_*.jpg")))
    print(f"✅ 已处理: {already}")
    print(f"🎯 待处理: {len(excel_files) - already}\n")

    success, failed, skipped = 0, 0, 0

    for i, excel_path in enumerate(excel_files):
        out_dir = IMAGES_DIR / excel_path.stem
        print(f"[{i+1}/{len(excel_files)}] {excel_path.name[:50]}...", end=" ", flush=True)

        if out_dir.exists() and list(out_dir.glob("page_*.jpg")):
            print("⏭️")
            skipped += 1
            continue

        images = process_excel(excel_path)
        if images:
            print(f"✅ {len(images)}p")
            success += 1
        else:
            print("❌")
            failed += 1

    print(f"\n{'='*60}")
    print(f"📊 完成! 成功:{success} 失败:{failed} 跳过:{skipped}")

if __name__ == "__main__":
    main()
