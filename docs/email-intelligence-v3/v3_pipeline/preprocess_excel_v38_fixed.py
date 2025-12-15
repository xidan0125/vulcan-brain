#!/usr/bin/env python3
"""
V3.8 Excel 预处理脚本 (修复版)
将 Excel 文件转换为图片，供 VLM 提取使用
流程: Excel -> LibreOffice -> PDF -> pdf2image -> JPG

关键修复：每个 Excel 文件有独立的图片目录（使用完整文件名）
"""
import os
import subprocess
import tempfile
import hashlib
from pathlib import Path
from pdf2image import convert_from_path
import json
from datetime import datetime

CACHE_DIR = Path.home() / "vulcan_data" / "cache"
RAW_DIR = CACHE_DIR / "raw"
IMAGES_DIR = CACHE_DIR / "images"
PROGRESS_PATH = CACHE_DIR / "download_progress.json"

DPI = 150
MAX_PAGES = 5

def get_image_dir_name(excel_path: Path) -> str:
    """获取 Excel 对应的图片目录名 (使用完整 stem 的 hash)"""
    # 使用文件名的 MD5 前缀 + 原始前缀，保证唯一性
    stem = excel_path.stem
    prefix = stem.split("_")[0] if "_" in stem else stem[:16]
    hash_suffix = hashlib.md5(stem.encode()).hexdigest()[:8]
    return f"{prefix}_excel_{hash_suffix}"

def process_excel(excel_path: Path) -> list:
    """Excel -> 图片列表"""
    dir_name = get_image_dir_name(excel_path)
    out_dir = IMAGES_DIR / dir_name
    out_dir.mkdir(exist_ok=True)

    # 检查是否已处理
    existing_jpgs = list(out_dir.glob("page_*.jpg"))
    if existing_jpgs:
        return existing_jpgs

    try:
        # 1. Excel -> PDF (LibreOffice)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", tmpdir, str(excel_path)
            ], capture_output=True, timeout=120)

            if result.returncode != 0:
                print(f"LibreOffice 转换失败: {result.stderr.decode()[:100]}")
                return []

            # 找到生成的 PDF
            pdf_files = list(Path(tmpdir).glob("*.pdf"))
            if not pdf_files:
                print(f"未生成 PDF")
                return []

            pdf_path = pdf_files[0]

            # 2. PDF -> Images
            images = convert_from_path(str(pdf_path), dpi=DPI)

            # 3. 保存为 JPG
            saved = []
            for i, img in enumerate(images[:MAX_PAGES]):
                jpg_path = out_dir / f"page_{i+1}.jpg"
                img.save(str(jpg_path), "JPEG", quality=85)
                saved.append(jpg_path)

            return saved

    except subprocess.TimeoutExpired:
        print(f"LibreOffice 超时")
        return []
    except Exception as e:
        print(f"处理错误: {e}")
        return []

def main():
    print("=" * 60)
    print("🔧 V3.8 Excel 预处理 (修复版)")
    print("=" * 60)
    print(f"时间: {datetime.now()}")

    IMAGES_DIR.mkdir(exist_ok=True)

    # 找所有 Excel 文件
    excel_files = list(RAW_DIR.glob("*.xlsx")) + list(RAW_DIR.glob("*.xls"))
    print(f"\n📁 找到 {len(excel_files)} 个 Excel 文件")

    # 统计已处理
    already_processed = 0
    for excel_path in excel_files:
        dir_name = get_image_dir_name(excel_path)
        out_dir = IMAGES_DIR / dir_name
        if out_dir.exists() and list(out_dir.glob("page_*.jpg")):
            already_processed += 1

    print(f"✅ 已处理: {already_processed}")
    print(f"🎯 待处理: {len(excel_files) - already_processed}")

    success = 0
    failed = 0
    skipped = 0

    for i, excel_path in enumerate(excel_files):
        filename = excel_path.name
        dir_name = get_image_dir_name(excel_path)
        out_dir = IMAGES_DIR / dir_name

        print(f"[{i+1}/{len(excel_files)}] {filename[:50]}...", end=" ")

        # 检查是否已有图片
        if out_dir.exists() and list(out_dir.glob("page_*.jpg")):
            print("⏭️ 跳过")
            skipped += 1
            continue

        # 处理
        images = process_excel(excel_path)

        if images:
            print(f"✅ {len(images)} 页")
            success += 1
        else:
            print("❌ 失败")
            failed += 1

    print("\n" + "=" * 60)
    print("📊 预处理完成!")
    print("=" * 60)
    print(f"成功: {success}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")

    # 验证总数
    total_excel_dirs = len([d for d in IMAGES_DIR.iterdir() if d.is_dir() and "_excel_" in d.name])
    total_jpgs = sum(1 for _ in IMAGES_DIR.rglob("page_*.jpg"))
    print(f"\n📁 Excel 图片目录: {total_excel_dirs}")
    print(f"📸 总图片数: {total_jpgs}")

if __name__ == "__main__":
    main()
