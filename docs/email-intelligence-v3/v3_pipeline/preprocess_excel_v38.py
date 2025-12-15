#!/usr/bin/env python3
"""
V3.8 Excel 预处理脚本
将 Excel 文件转换为图片，供 VLM 提取使用
流程: Excel -> LibreOffice -> PDF -> pdf2image -> JPG
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
PROGRESS_PATH = CACHE_DIR / "download_progress.json"

DPI = 150
MAX_PAGES = 5

def process_excel(excel_path: Path) -> list:
    """Excel -> 图片列表"""
    stem = excel_path.stem
    out_dir = IMAGES_DIR / stem.split("_")[0]  # 使用 email_id 前缀作为目录名
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
            ], capture_output=True, timeout=60)

            if result.returncode != 0:
                print(f"    LibreOffice 转换失败: {result.stderr.decode()[:100]}")
                return []

            # 找到生成的 PDF
            pdf_files = list(Path(tmpdir).glob("*.pdf"))
            if not pdf_files:
                print(f"    未生成 PDF")
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
        print(f"    LibreOffice 超时")
        return []
    except Exception as e:
        print(f"    处理错误: {e}")
        return []

def main():
    print("=" * 60)
    print("🔧 V3.8 Excel 预处理")
    print("=" * 60)
    print(f"时间: {datetime.now()}")

    IMAGES_DIR.mkdir(exist_ok=True)

    # 找所有 Excel 文件
    excel_files = list(RAW_DIR.glob("*.xlsx")) + list(RAW_DIR.glob("*.xls"))
    print(f"\n📁 找到 {len(excel_files)} 个 Excel 文件")

    # 加载进度文件
    progress_data = []
    if PROGRESS_PATH.exists():
        progress_data = json.loads(PROGRESS_PATH.read_text())

    # 创建查找映射
    progress_map = {r["local_path"]: r for r in progress_data}

    success = 0
    failed = 0
    skipped = 0

    for i, excel_path in enumerate(excel_files):
        filename = excel_path.name
        print(f"[{i+1}/{len(excel_files)}] {filename[:60]}...", end=" ")

        # 检查是否已有图片
        stem = excel_path.stem
        out_dir = IMAGES_DIR / stem.split("_")[0]
        if out_dir.exists() and list(out_dir.glob("page_*.jpg")):
            print("⏭️ 已存在")
            skipped += 1
            continue

        # 处理
        images = process_excel(excel_path)

        if images:
            print(f"✅ {len(images)} 页")
            success += 1

            # 更新进度状态
            local_path = str(excel_path)
            if local_path in progress_map:
                progress_map[local_path]["status"] = "processed"
        else:
            print("❌ 失败")
            failed += 1

        # 每 50 个保存一次进度
        if (i + 1) % 50 == 0:
            updated_progress = list(progress_map.values())
            PROGRESS_PATH.write_text(json.dumps(updated_progress, ensure_ascii=False, indent=2))
            print(f"    💾 进度已保存")

    # 最终保存
    updated_progress = list(progress_map.values())
    PROGRESS_PATH.write_text(json.dumps(updated_progress, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("📊 预处理完成!")
    print("=" * 60)
    print(f"成功: {success}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")

    # 验证
    total_jpgs = len(list(IMAGES_DIR.rglob("page_*.jpg")))
    print(f"\n📸 总图片数: {total_jpgs}")

if __name__ == "__main__":
    main()
