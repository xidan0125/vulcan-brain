#!/usr/bin/env python3
"""
V3.6 收割机 (The Harvester) - 带限流保护的稳健下载
改进:
  1. JSON Batching - 每批4个请求 (Outlook保守值)
  2. 指数退避 - 429时自动等待
  3. 进度持久化 - 可断点续传
  4. 请求间隔 - 避免触发限流
"""
import os
import sys
import json
import time
import hashlib
import subprocess
import tempfile
import base64
import pymongo
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict, field
import re

# ============ 配置 ============
CACHE_DIR = Path.home() / "vulcan_data" / "cache"
RAW_DIR = CACHE_DIR / "raw"
IMAGES_DIR = CACHE_DIR / "images"
MANIFEST_PATH = CACHE_DIR / "manifest.json"
PROGRESS_PATH = CACHE_DIR / "download_progress.json"

# 高价值附件过滤
HIGH_VALUE_EXTENSIONS = {'.pdf', '.xlsx', '.xls', '.png', '.jpg', '.jpeg'}
MIN_IMAGE_SIZE = 50 * 1024

# ⚠️ 保守的限流配置
BATCH_SIZE = 4              # Outlook批处理保守值
REQUEST_INTERVAL = 0.5      # 请求间隔(秒)
INITIAL_BACKOFF = 10        # 初始退避时间(秒)
MAX_BACKOFF = 300           # 最大退避时间(秒)
MAX_RETRIES = 3             # 单个请求最大重试次数

# MS365 API
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# ============ 数据结构 ============
@dataclass
class AttachmentRecord:
    email_id: str
    attachment_id: str
    filename: str
    size: int
    content_type: str
    user_email: str
    graph_message_id: str
    email_subject: str
    email_intent: str
    local_path: Optional[str] = None
    image_paths: Optional[List[str]] = None
    status: str = "pending"
    error: Optional[str] = None
    retries: int = 0

# ============ Graph API 客户端 ============
class GraphAPIClient:
    def __init__(self):
        self.token = None
        self.token_expires = None
        self.backoff_until = None  # 限流退避时间点
        self.current_backoff = INITIAL_BACKOFF
        self._load_credentials()

    def _load_credentials(self):
        config_path = Path.home() / "vulcan-brain" / "ecosystem.config.js"
        if not config_path.exists():
            raise FileNotFoundError("找不到ecosystem.config.js")
        content = config_path.read_text()
        self.tenant_id = self._extract_config(content, "MS365_TENANT_ID")
        self.client_id = self._extract_config(content, "MS365_CLIENT_ID")
        self.client_secret = self._extract_config(content, "MS365_CLIENT_SECRET")
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError("MS365凭据不完整")

    def _extract_config(self, content: str, key: str) -> str:
        match = re.search(rf'{key}["\s:]+["\']([^"\']+)["\']', content)
        return match.group(1) if match else ""

    def get_token(self) -> str:
        if self.token and self.token_expires and datetime.now() < self.token_expires:
            return self.token
        resp = requests.post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            },
            timeout=30
        )
        data = resp.json()
        if "access_token" not in data:
            raise Exception(f"获取token失败: {data}")
        self.token = data["access_token"]
        self.token_expires = datetime.now() + timedelta(seconds=data.get("expires_in", 3600) - 60)
        return self.token

    def wait_if_throttled(self):
        """如果在限流退避期,等待"""
        if self.backoff_until and datetime.now() < self.backoff_until:
            wait_secs = (self.backoff_until - datetime.now()).total_seconds()
            print(f"    ⏳ 限流退避中,等待 {wait_secs:.0f}s...")
            time.sleep(wait_secs)

    def handle_throttle(self, retry_after: int = None):
        """处理限流,设置退避时间"""
        wait_time = retry_after if retry_after else self.current_backoff
        self.backoff_until = datetime.now() + timedelta(seconds=wait_time)
        print(f"    🚦 触发限流! 退避 {wait_time}s (until {self.backoff_until.strftime('%H:%M:%S')})")
        # 指数退避
        self.current_backoff = min(self.current_backoff * 2, MAX_BACKOFF)

    def reset_backoff(self):
        """成功后重置退避时间"""
        self.current_backoff = INITIAL_BACKOFF

    def download_attachment(self, user_email: str, message_id: str, attachment_id: str, save_path: Path) -> Tuple[bool, str]:
        """下载单个附件,带重试"""
        self.wait_if_throttled()

        url = f"{GRAPH_API_BASE}/users/{user_email}/messages/{message_id}/attachments/{attachment_id}/$value"
        headers = {"Authorization": f"Bearer {self.get_token()}"}

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url, headers=headers, timeout=120)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", INITIAL_BACKOFF))
                    self.handle_throttle(retry_after)
                    time.sleep(retry_after)
                    continue

                if resp.status_code == 404:
                    return False, "附件不存在(404)"

                resp.raise_for_status()
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(resp.content)
                self.reset_backoff()
                return True, "success"

            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5)
                    continue
                return False, "超时"
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                    continue
                return False, str(e)[:100]

        return False, "重试次数用尽"

    def batch_download(self, records: List[AttachmentRecord]) -> List[Tuple[AttachmentRecord, bool, str]]:
        """批量下载 (使用 $batch API)"""
        self.wait_if_throttled()

        # 构建批量请求
        batch_requests = []
        for i, r in enumerate(records):
            batch_requests.append({
                "id": str(i),
                "method": "GET",
                "url": f"/users/{r.user_email}/messages/{r.graph_message_id}/attachments/{r.attachment_id}/$value"
            })

        payload = {"requests": batch_requests}
        headers = {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(
                f"{GRAPH_API_BASE}/$batch",
                headers=headers,
                json=payload,
                timeout=180
            )

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", INITIAL_BACKOFF))
                self.handle_throttle(retry_after)
                # 返回全部失败,让调用者重试
                return [(r, False, "批量请求被限流") for r in records]

            resp.raise_for_status()
            batch_resp = resp.json()

        except Exception as e:
            return [(r, False, f"批量请求失败: {str(e)[:50]}") for r in records]

        # 解析批量响应
        results = []
        responses = {r["id"]: r for r in batch_resp.get("responses", [])}

        for i, record in enumerate(records):
            resp_data = responses.get(str(i), {})
            status = resp_data.get("status", 500)

            if status == 200:
                # 成功 - 保存文件
                body = resp_data.get("body", "")
                try:
                    # 批量响应中的二进制数据是base64编码的
                    content = base64.b64decode(body) if body else b""
                    if content:
                        save_path = Path(record.local_path)
                        save_path.parent.mkdir(parents=True, exist_ok=True)
                        save_path.write_bytes(content)
                        results.append((record, True, "success"))
                    else:
                        results.append((record, False, "响应体为空"))
                except Exception as e:
                    results.append((record, False, f"保存失败: {str(e)[:30]}"))
            elif status == 429:
                results.append((record, False, "单个请求被限流"))
            elif status == 404:
                results.append((record, False, "附件不存在"))
            else:
                error = resp_data.get("body", {}).get("error", {}).get("message", f"HTTP {status}")
                results.append((record, False, error[:50]))

        self.reset_backoff()
        return results

# ============ Step 1: 生成清单 ============
def generate_manifest() -> List[AttachmentRecord]:
    """从MongoDB生成高价值附件清单"""
    print("\n📋 Step 1: 生成高价值附件清单...")

    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client.vulcan_brain

    query = {
        "processing_status.v2_extracted": True,
        "has_attachments": True
    }

    manifest = []
    skipped = {"small_image": 0, "no_ext": 0, "low_value_ext": 0, "no_id": 0}

    total = db.emails.count_documents(query)
    print(f"   扫描 {total} 封邮件...")

    for i, email in enumerate(db.emails.find(query)):
        if (i + 1) % 1000 == 0:
            print(f"   进度: {i+1}/{total}")

        user_email = email.get("user_id") or ""
        if not user_email:
            tos = email.get("to", [])
            if tos and isinstance(tos[0], dict):
                user_email = tos[0].get("address", "")

        graph_message_id = email.get("email_id") or email.get("graph_id") or ""
        if not graph_message_id or not user_email:
            continue

        ai_extracted = email.get("ai_extracted", {})
        intent = "UNKNOWN"
        if isinstance(ai_extracted, dict):
            intent_data = ai_extracted.get("intent", "UNKNOWN")
            if isinstance(intent_data, dict):
                intent = intent_data.get("type", "UNKNOWN")
            else:
                intent = str(intent_data)

        for att in email.get("attachments", []):
            att_id = att.get("id", "")
            filename = att.get("name", "")
            size = att.get("size", 0)
            content_type = att.get("content_type", "")

            if not att_id:
                skipped["no_id"] += 1
                continue

            ext = ""
            if "." in filename:
                ext = "." + filename.rsplit(".", 1)[-1].lower()

            if not ext:
                skipped["no_ext"] += 1
                continue

            if ext not in HIGH_VALUE_EXTENSIONS:
                skipped["low_value_ext"] += 1
                continue

            if ext in {'.png', '.jpg', '.jpeg'} and size < MIN_IMAGE_SIZE:
                skipped["small_image"] += 1
                continue

            # 生成本地路径
            safe_name = f"{att_id[:16]}_{filename}"
            safe_name = re.sub(r'[^\w\-_\.]', '_', safe_name)
            local_path = str(RAW_DIR / safe_name)

            record = AttachmentRecord(
                email_id=str(email["_id"]),
                attachment_id=att_id,
                filename=filename,
                size=size,
                content_type=content_type,
                user_email=user_email,
                graph_message_id=graph_message_id,
                email_subject=email.get("subject", "")[:100],
                email_intent=intent,
                local_path=local_path
            )
            manifest.append(record)

    ext_counts = {}
    for r in manifest:
        ext = r.filename.rsplit(".", 1)[-1].lower() if "." in r.filename else "unknown"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    print(f"\n   ✅ 清单生成完成!")
    print(f"   高价值附件: {len(manifest)} 个")
    print(f"   格式分布: {ext_counts}")
    print(f"   跳过: {skipped}")

    return manifest

# ============ Step 2: 下载附件 (单个模式,更稳健) ============
def download_sequential(manifest: List[AttachmentRecord], api: GraphAPIClient) -> List[AttachmentRecord]:
    """顺序下载,带限流保护"""
    print(f"\n⬇️  Step 2: 顺序下载 ({len(manifest)} 个)...")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 检查已下载
    to_download = []
    already_done = 0
    for r in manifest:
        local_path = Path(r.local_path)
        if local_path.exists() and local_path.stat().st_size > 0:
            r.status = "downloaded"
            already_done += 1
        else:
            to_download.append(r)

    print(f"   已缓存: {already_done}, 待下载: {len(to_download)}")

    if not to_download:
        return manifest

    success = 0
    failed = 0
    start_time = datetime.now()

    for i, record in enumerate(to_download):
        # 进度报告
        if (i + 1) % 50 == 0 or i == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(to_download) - i - 1) / rate / 60 if rate > 0 else 0
            print(f"   进度: {i+1}/{len(to_download)} | 成功:{success} 失败:{failed} | {rate:.1f}/s | ETA:{eta:.0f}min")

        ok, error = api.download_attachment(
            record.user_email,
            record.graph_message_id,
            record.attachment_id,
            Path(record.local_path)
        )

        if ok:
            record.status = "downloaded"
            success += 1
        else:
            record.status = "failed"
            record.error = error
            failed += 1

        # 请求间隔
        time.sleep(REQUEST_INTERVAL)

        # 每100个保存进度
        if (i + 1) % 100 == 0:
            save_progress(manifest)

    print(f"   ✅ 下载完成! 成功:{success}, 失败:{failed}")
    return manifest

# ============ 进度保存/恢复 ============
def save_progress(manifest: List[AttachmentRecord]):
    """保存下载进度"""
    data = [asdict(r) for r in manifest]
    PROGRESS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def load_progress() -> Optional[List[AttachmentRecord]]:
    """加载之前的进度"""
    if not PROGRESS_PATH.exists():
        return None
    try:
        data = json.loads(PROGRESS_PATH.read_text())
        return [AttachmentRecord(**d) for d in data]
    except:
        return None

# ============ Step 3: Excel预处理 ============
def preprocess_excel(manifest: List[AttachmentRecord]) -> List[AttachmentRecord]:
    """将Excel转为图片"""
    print(f"\n🔄 Step 3: Excel预处理...")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    excel_files = [r for r in manifest if r.status == "downloaded" and r.filename.lower().endswith(('.xlsx', '.xls'))]
    print(f"   Excel文件: {len(excel_files)} 个")

    if not excel_files:
        return manifest

    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("   ⚠️  pdf2image未安装,跳过Excel处理")
        return manifest

    success = 0
    failed = 0

    for r in excel_files:
        try:
            excel_path = Path(r.local_path)
            output_dir = IMAGES_DIR / r.attachment_id[:16]
            output_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, str(excel_path)]
                result = subprocess.run(cmd, capture_output=True, timeout=60)

                if result.returncode != 0:
                    raise RuntimeError(f"LibreOffice失败")

                pdf_files = list(Path(tmpdir).glob("*.pdf"))
                if not pdf_files:
                    raise RuntimeError("PDF未生成")

                images = convert_from_path(str(pdf_files[0]), dpi=200)
                image_paths = []

                for i, img in enumerate(images[:5]):
                    img_path = output_dir / f"page_{i+1}.jpg"
                    img.save(str(img_path), "JPEG", quality=85)
                    image_paths.append(str(img_path))

                r.image_paths = image_paths
                r.status = "processed"
                success += 1

        except Exception as e:
            r.error = f"Excel处理失败: {str(e)[:50]}"
            failed += 1

        if (success + failed) % 50 == 0:
            print(f"   进度: {success + failed}/{len(excel_files)}")

    print(f"   ✅ Excel处理完成! 成功:{success}, 失败:{failed}")
    return manifest

# ============ Step 4: 整理图片 ============
def organize_images(manifest: List[AttachmentRecord]) -> List[AttachmentRecord]:
    """整理图片目录"""
    print(f"\n📁 Step 4: 整理图片目录...")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    organized = 0

    for r in manifest:
        if r.status not in ("downloaded", "processed"):
            continue

        ext = r.filename.rsplit(".", 1)[-1].lower() if "." in r.filename else ""

        if ext in ('pdf', 'png', 'jpg', 'jpeg'):
            src = Path(r.local_path)
            if src.exists():
                dest = IMAGES_DIR / f"{r.attachment_id[:16]}_{r.filename}"
                if not dest.exists():
                    try:
                        dest.symlink_to(src)
                    except:
                        pass  # Windows可能不支持symlink
                r.image_paths = [str(dest)]
                r.status = "processed"
                organized += 1

    print(f"   ✅ 整理完成! {organized} 个文件")
    return manifest

# ============ 主流程 ============
def main():
    print("=" * 60)
    print("🚜 V3.6 收割机 - 带限流保护")
    print("=" * 60)
    print(f"时间: {datetime.now()}")
    print(f"配置: BATCH_SIZE={BATCH_SIZE}, INTERVAL={REQUEST_INTERVAL}s")
    print(f"缓存: {CACHE_DIR}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 检查是否有之前的进度
    manifest = load_progress()
    if manifest:
        pending = sum(1 for r in manifest if r.status == "pending")
        downloaded = sum(1 for r in manifest if r.status == "downloaded")
        print(f"\n📂 发现之前的进度: {len(manifest)}个附件")
        print(f"   待下载: {pending}, 已下载: {downloaded}")

        if pending > 0:
            print("   继续下载...")
        else:
            print("   全部已下载,跳过Step 1-2")
    else:
        # Step 1: 生成清单
        manifest = generate_manifest()
        save_progress(manifest)
        print(f"\n💾 清单已保存: {PROGRESS_PATH}")

    # Step 2: 下载
    pending = [r for r in manifest if r.status == "pending"]
    if pending:
        api = GraphAPIClient()
        manifest = download_sequential(manifest, api)
        save_progress(manifest)

    # Step 3: Excel预处理
    manifest = preprocess_excel(manifest)

    # Step 4: 整理
    manifest = organize_images(manifest)

    # 保存最终清单
    final_data = [asdict(r) for r in manifest]
    MANIFEST_PATH.write_text(json.dumps(final_data, indent=2, ensure_ascii=False))

    # 统计
    status_counts = {}
    for r in manifest:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    print("\n" + "=" * 60)
    print("📊 收割完成!")
    print("=" * 60)
    print(f"总附件: {len(manifest)}")
    print(f"状态: {status_counts}")
    print(f"\n产物:")
    print(f"  原始文件: {RAW_DIR}")
    print(f"  处理后: {IMAGES_DIR}")
    print(f"  清单: {MANIFEST_PATH}")

if __name__ == "__main__":
    main()
