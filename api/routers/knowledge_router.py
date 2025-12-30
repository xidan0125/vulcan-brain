"""
Vulcan Brain API - 知识库路由 V2
企业文档管理 - 匈牙利项目文件 + 邮件附件
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Header, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
import hashlib

import motor.motor_asyncio as motor

# MongoDB 配置
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGODB_DB", "vulcan_brain")

# 知识库访问密码 (SHA256 hash)
# 默认密码: vulcan2024
KNOWLEDGE_PASSWORD_HASH = os.getenv(
    "KNOWLEDGE_PASSWORD_HASH",
    hashlib.sha256("vulcan2024".encode()).hexdigest()
)

def verify_knowledge_password(password: str) -> bool:
    """验证知识库访问密码"""
    if not password:
        return False
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return password_hash == KNOWLEDGE_PASSWORD_HASH

async def check_knowledge_auth(x_knowledge_password: str = Header(None, alias="X-Knowledge-Password")):
    """验证知识库访问权限"""
    if not verify_knowledge_password(x_knowledge_password):
        raise HTTPException(status_code=401, detail="需要输入正确的访问密码")

# 创建异步客户端
_client = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        _client = motor.AsyncIOMotorClient(MONGO_URI)
        _db = _client[MONGO_DB]
    return _db

router = APIRouter(tags=["Knowledge Base"])


@router.post('/api/knowledge/verify-password')
async def verify_password(password: str = Query(...)):
    """验证知识库访问密码"""
    if verify_knowledge_password(password):
        return {"success": True, "message": "密码正确"}
    raise HTTPException(status_code=401, detail="密码错误")


# === 存储路径 ===
UPLOAD_DIR = "/data/storage/uploads"
ATTACHMENT_CACHE_DIR = "/home/xinyue/attachment_cache"

# === 业务类型关键词 ===
BUSINESS_KEYWORDS = {
    "INVOICE": ["invoice", "inv", "fapiao", "发票", "bill"],
    "PO_ORDER": ["po", "order", "purchase", "订单"],
    "CONTRACT": ["contract", "agreement", "nda", "合同", "协议"],
    "QUOTE": ["quote", "quotation", "price", "报价"],
    "PACKING": ["packing", "list", "shipping", "waybill", "装箱", "单号"],
    "SPEC_DRAWING": ["spec", "drawing", "dwg", "cad", "图纸", "参数", "sheet"],
    "CERTIFICATE": ["cert", "certificate", "证书", "认证"],
    "REPORT": ["report", "summary", "analysis", "报告"],
}

# 高价值文件扩展名
HIGH_VALUE_EXTENSIONS = {'.pdf', '.xlsx', '.xls', '.docx', '.doc', '.csv', '.pptx', '.ppt'}


def count_files_recursive(dir_path: str) -> int:
    """递归统计目录下所有文件数量"""
    total = 0
    try:
        for entry in os.listdir(dir_path):
            entry_path = os.path.join(dir_path, entry)
            if os.path.isfile(entry_path):
                total += 1
            elif os.path.isdir(entry_path):
                total += count_files_recursive(entry_path)
    except PermissionError:
        pass
    return total


def classify_by_filename(filename: str) -> str:
    """根据文件名关键词分类"""
    fname_lower = filename.lower()
    for btype, keywords in BUSINESS_KEYWORDS.items():
        if any(kw in fname_lower for kw in keywords):
            return btype
    return "OTHER"


def get_file_icon(ext: str) -> str:
    """获取文件类型图标"""
    icons = {
        '.pdf': '📄', '.xlsx': '📊', '.xls': '📊',
        '.docx': '📝', '.doc': '📝', '.pptx': '📽️',
        '.csv': '📋', '.zip': '📦', '.png': '🖼️',
        '.jpg': '🖼️', '.jpeg': '🖼️', '.gif': '🖼️',
    }
    return icons.get(ext.lower(), '📎')


# ==================== 匈牙利项目文件 API ====================

class FolderItem(BaseModel):
    name: str
    path: str
    type: str  # 'folder' or 'file'
    size: Optional[int] = None
    ext: Optional[str] = None
    icon: Optional[str] = None
    modified: Optional[str] = None
    children_count: Optional[int] = None


@router.get('/api/knowledge/hungary/tree')
async def get_hungary_tree(_: None = Depends(check_knowledge_auth)):
    """获取匈牙利项目完整目录树"""
    
    def count_all_files(items) -> int:
        """递归统计所有文件数量（包括子文件夹）"""
        total = 0
        for item in items:
            if item["type"] == "file":
                total += 1
            elif "children" in item:
                total += count_all_files(item["children"])
        return total

    def build_tree(dir_path: str, relative_base: str = "") -> List[dict]:
        items = []
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return items

        # 先文件夹，后文件
        folders = []
        files = []

        for entry in entries:
            full_path = os.path.join(dir_path, entry)
            rel_path = os.path.join(relative_base, entry) if relative_base else entry

            if os.path.isdir(full_path):
                children = build_tree(full_path, rel_path)
                # 递归统计所有文件（包括子文件夹里的）
                total_files = count_all_files(children)
                folders.append({
                    "name": entry,
                    "path": rel_path,
                    "type": "folder",
                    "children": children,
                    "children_count": total_files
                })
            else:
                ext = os.path.splitext(entry)[1].lower()
                stat = os.stat(full_path)
                files.append({
                    "name": entry,
                    "path": rel_path,
                    "type": "file",
                    "size": stat.st_size,
                    "ext": ext,
                    "icon": get_file_icon(ext),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        return folders + files
    
    if not os.path.exists(UPLOAD_DIR):
        return {"tree": [], "total_files": 0, "total_size": 0}
    
    tree = build_tree(UPLOAD_DIR)
    
    # 统计
    def count_files(items):
        total = 0
        size = 0
        for item in items:
            if item["type"] == "file":
                total += 1
                size += item.get("size", 0)
            elif "children" in item:
                t, s = count_files(item["children"])
                total += t
                size += s
        return total, size
    
    total_files, total_size = count_files(tree)
    
    return {
        "tree": tree,
        "total_files": total_files,
        "total_size": total_size
    }


@router.get('/api/knowledge/hungary/folder')
async def get_hungary_folder(
    path: str = Query("", description="相对路径"),
    _: None = Depends(check_knowledge_auth)
):
    """获取指定文件夹内容"""
    full_path = os.path.join(UPLOAD_DIR, path) if path else UPLOAD_DIR
    
    if not os.path.exists(full_path) or not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail="文件夹不存在")
    
    # 安全检查
    if not os.path.abspath(full_path).startswith(os.path.abspath(UPLOAD_DIR)):
        raise HTTPException(status_code=403, detail="访问被拒绝")
    
    items = []
    for entry in sorted(os.listdir(full_path)):
        entry_path = os.path.join(full_path, entry)
        rel_path = os.path.join(path, entry) if path else entry
        
        if os.path.isdir(entry_path):
            # 递归统计所有子文件数
            file_count = count_files_recursive(entry_path)
            items.append({
                "name": entry,
                "path": rel_path,
                "type": "folder",
                "children_count": file_count
            })
        else:
            ext = os.path.splitext(entry)[1].lower()
            stat = os.stat(entry_path)
            items.append({
                "name": entry,
                "path": rel_path,
                "type": "file",
                "size": stat.st_size,
                "ext": ext,
                "icon": get_file_icon(ext),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    # 排序：文件夹在前
    items.sort(key=lambda x: (0 if x["type"] == "folder" else 1, x["name"]))
    
    return {
        "path": path,
        "items": items,
        "breadcrumbs": path.split("/") if path else []
    }


@router.get('/api/knowledge/hungary/download/{file_path:path}')
async def download_hungary_file(
    file_path: str,
    _: None = Depends(check_knowledge_auth)
):
    """下载匈牙利项目文件"""
    full_path = os.path.join(UPLOAD_DIR, file_path)
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    if not os.path.abspath(full_path).startswith(os.path.abspath(UPLOAD_DIR)):
        raise HTTPException(status_code=403, detail="访问被拒绝")
    
    return FileResponse(
        full_path,
        filename=os.path.basename(full_path),
        media_type='application/octet-stream'
    )


# ==================== 邮件附件 API ====================



@router.post('/api/knowledge/upload')
async def upload_file(
    file: UploadFile = File(...),
    folder_path: str = Form(""),
    _: None = Depends(check_knowledge_auth)
):
    """上传文件到指定文件夹"""
    # 确定目标目录
    target_dir = os.path.join(UPLOAD_DIR, folder_path) if folder_path else UPLOAD_DIR
    
    # 安全检查 - 防止路径遍历攻击
    abs_target = os.path.abspath(target_dir)
    abs_upload = os.path.abspath(UPLOAD_DIR)
    if not abs_target.startswith(abs_upload):
        raise HTTPException(status_code=403, detail="非法路径")
    
    # 确保目录存在
    if not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail="目标文件夹不存在")
    
    if not os.path.isdir(target_dir):
        raise HTTPException(status_code=400, detail="目标路径不是文件夹")
    
    # 处理文件名 (避免覆盖)
    filename = file.filename
    target_path = os.path.join(target_dir, filename)
    
    # 如果文件已存在，添加时间戳
    if os.path.exists(target_path):
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}{ext}"
        target_path = os.path.join(target_dir, filename)
    
    # 保存文件
    try:
        contents = await file.read()
        with open(target_path, 'wb') as f:
            f.write(contents)
        
        file_size = os.path.getsize(target_path)
        
        return {
            "success": True,
            "filename": filename,
            "path": os.path.join(folder_path, filename) if folder_path else filename,
            "size": file_size,
            "message": f"文件已上传到 {folder_path or '根目录'}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")




# === AI 文件夹摘要 (使用 Knowledge Agent) ===
import sys
sys.path.insert(0, '/home/xinyue/vulcan-brain')
from agents.knowledge import smart_summarize, get_agent, _summary_cache

@router.post('/api/knowledge/summarize')
async def summarize_folder_endpoint(
    folder_path: str = Form(""),
    _: None = Depends(check_knowledge_auth)
):
    """
    AI 生成文件夹内容摘要

    分析策略:
    - 浅层(0-1): 基于文件夹结构分析
    - 深层(2+): 启用VLM分析文件内容 (PDF/Excel转图片)
    """
    # 安全检查
    target_dir = os.path.join(UPLOAD_DIR, folder_path) if folder_path else UPLOAD_DIR
    if not os.path.abspath(target_dir).startswith(os.path.abspath(UPLOAD_DIR)):
        raise HTTPException(status_code=403, detail="访问被拒绝")

    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        raise HTTPException(status_code=404, detail="文件夹不存在")

    # 调用 Knowledge Agent
    result = await smart_summarize(UPLOAD_DIR, folder_path)

    if "error" in result and result["error"] == "文件夹不存在":
        raise HTTPException(status_code=404, detail="文件夹不存在")

    return result


@router.post('/api/knowledge/summarize/clear-cache')
async def clear_summary_cache(_: None = Depends(check_knowledge_auth)):
    """清除摘要缓存"""
    agent = get_agent(UPLOAD_DIR)
    count = agent.clear_cache()
    return {"success": True, "cleared": count}


@router.post('/api/knowledge/analyze-file')
async def analyze_file_endpoint(
    file_path: str = Form(...),
    _: None = Depends(check_knowledge_auth)
):
    """
    VLM分析单个文件内容

    支持: PDF, Excel, 图片
    将文件转为图片后用 Qwen3-VL 多模态模型分析
    """
    # 安全检查
    full_path = os.path.join(UPLOAD_DIR, file_path)
    if not os.path.abspath(full_path).startswith(os.path.abspath(UPLOAD_DIR)):
        raise HTTPException(status_code=403, detail="访问被拒绝")

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 调用 Knowledge Agent 分析文件
    agent = get_agent(UPLOAD_DIR)
    result = await agent.analyze_file(file_path)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result




@router.get('/api/knowledge/attachments/stats')
async def get_attachment_stats(_: None = Depends(check_knowledge_auth)):
    """获取邮件附件统计"""
    db = get_db()
    
    # 聚合统计
    pipeline = [
        {"$match": {"attachments.0": {"$exists": True}}},
        {"$unwind": "$attachments"},
        {"$match": {
            "$or": [
                {"attachments.name": {"$regex": r"\.(pdf|xlsx|xls|docx|doc|csv|pptx|ppt)$", "$options": "i"}}
            ]
        }},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "total_size": {"$sum": "$attachments.size"}
        }}
    ]
    
    result = await db.emails.aggregate(pipeline).to_list(1)
    stats = result[0] if result else {"total": 0, "total_size": 0}
    
    # 按扩展名统计
    ext_pipeline = [
        {"$match": {"attachments.0": {"$exists": True}}},
        {"$unwind": "$attachments"},
        {"$match": {
            "$or": [
                {"attachments.name": {"$regex": r"\.(pdf|xlsx|xls|docx|doc|csv|pptx|ppt)$", "$options": "i"}}
            ]
        }},
        {"$project": {
            "ext": {"$toLower": {"$arrayElemAt": [{"$split": ["$attachments.name", "."]}, -1]}}
        }},
        {"$group": {"_id": "$ext", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    ext_stats = await db.emails.aggregate(ext_pipeline).to_list(20)
    
    return {
        "total_files": stats.get("total", 0),
        "total_size": stats.get("total_size", 0),
        "by_extension": {item["_id"]: item["count"] for item in ext_stats}
    }




@router.get('/api/knowledge/attachments/list')
async def list_attachments(
    category: Optional[str] = Query(None, description="业务类型筛选"),
    ext: Optional[str] = Query(None, description="扩展名筛选"),
    search: Optional[str] = Query(None, description="搜索文件名"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(check_knowledge_auth)
):
    """列出邮件附件"""
    db = get_db()
    
    # 构建查询
    match_conditions = {"attachments.0": {"$exists": True}}
    
    pipeline = [
        {"$match": match_conditions},
        {"$unwind": "$attachments"},
        # 只要高价值文件
        {"$match": {
            "attachments.name": {"$regex": r"\.(pdf|xlsx|xls|docx|doc|csv|pptx|ppt)$", "$options": "i"}
        }}
    ]
    
    # 扩展名筛选
    if ext:
        pipeline.append({
            "$match": {"attachments.name": {"$regex": f"\\.{ext}$", "$options": "i"}}
        })
    
    # 搜索
    if search:
        pipeline.append({
            "$match": {"attachments.name": {"$regex": search, "$options": "i"}}
        })
    
    # 投影 - 显式排除 _id
    pipeline.append({
        "$project": {
            "_id": 0,
            "email_id": {"$toString": "$_id"},
            "attachment_id": "$attachments.id",
            "name": "$attachments.name",
            "size": "$attachments.size",
            "content_type": "$attachments.content_type",
            "email_subject": "$subject",
            "email_from": "$from.address",
            "email_date": {"$toString": "$received_at"},
            "ext": {"$toLower": {"$arrayElemAt": [{"$split": ["$attachments.name", "."]}, -1]}}
        }
    })
    
    # 添加业务分类
    pipeline.append({
        "$addFields": {
            "category": {
                "$switch": {
                    "branches": [
                        {"case": {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": "invoice|inv|fapiao|发票|bill"}}, "then": "INVOICE"},
                        {"case": {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": "po|order|purchase|订单"}}, "then": "PO_ORDER"},
                        {"case": {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": "contract|agreement|nda|合同|协议"}}, "then": "CONTRACT"},
                        {"case": {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": "quote|quotation|price|报价"}}, "then": "QUOTE"},
                        {"case": {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": "packing|list|shipping|waybill|装箱|单号"}}, "then": "PACKING"},
                        {"case": {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": "spec|drawing|dwg|cad|图纸|参数|sheet"}}, "then": "SPEC_DRAWING"},
                        {"case": {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": "cert|certificate|证书|认证"}}, "then": "CERTIFICATE"},
                        {"case": {"$regexMatch": {"input": {"$toLower": "$name"}, "regex": "report|summary|analysis|报告"}}, "then": "REPORT"},
                    ],
                    "default": "OTHER"
                }
            }
        }
    })
    
    # 业务类型筛选
    if category:
        pipeline.append({"$match": {"category": category}})
    
    # 排序、分页
    pipeline.extend([
        {"$sort": {"email_date": -1}},
        {"$skip": skip},
        {"$limit": limit}
    ])
    
    attachments = await db.emails.aggregate(pipeline).to_list(limit)
    
    # 统计各分类数量
    category_pipeline = [
        {"$match": {"attachments.0": {"$exists": True}}},
        {"$unwind": "$attachments"},
        {"$match": {"attachments.name": {"$regex": r"\.(pdf|xlsx|xls|docx|doc|csv|pptx|ppt)$", "$options": "i"}}},
        {"$project": {"_id": 0, "name": {"$toLower": "$attachments.name"}}},
        {"$addFields": {
            "category": {
                "$switch": {
                    "branches": [
                        {"case": {"$regexMatch": {"input": "$name", "regex": "invoice|inv|fapiao|发票|bill"}}, "then": "INVOICE"},
                        {"case": {"$regexMatch": {"input": "$name", "regex": "po|order|purchase|订单"}}, "then": "PO_ORDER"},
                        {"case": {"$regexMatch": {"input": "$name", "regex": "contract|agreement|nda|合同|协议"}}, "then": "CONTRACT"},
                        {"case": {"$regexMatch": {"input": "$name", "regex": "quote|quotation|price|报价"}}, "then": "QUOTE"},
                        {"case": {"$regexMatch": {"input": "$name", "regex": "packing|list|shipping|waybill|装箱|单号"}}, "then": "PACKING"},
                        {"case": {"$regexMatch": {"input": "$name", "regex": "spec|drawing|dwg|cad|图纸|参数|sheet"}}, "then": "SPEC_DRAWING"},
                        {"case": {"$regexMatch": {"input": "$name", "regex": "cert|certificate|证书|认证"}}, "then": "CERTIFICATE"},
                        {"case": {"$regexMatch": {"input": "$name", "regex": "report|summary|analysis|报告"}}, "then": "REPORT"},
                    ],
                    "default": "OTHER"
                }
            }
        }},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    categories = await db.emails.aggregate(category_pipeline).to_list(20)
    
    return {
        "attachments": attachments,
        "categories": {item["_id"]: item["count"] for item in categories},
        "skip": skip,
        "limit": limit
    }




@router.get('/api/knowledge/attachments/download')
async def download_attachment(
    email_id: str = Query(...),
    attachment_id: str = Query(...),
    _: None = Depends(check_knowledge_auth)
):
    """下载邮件附件（从缓存或实时下载）"""
    db = get_db()
    
    # 先检查缓存
    cached = await db.attachment_cache.find_one({
        "email_id": email_id,
        "attachment_id": attachment_id,
        "status": "downloaded"
    })
    
    if cached and os.path.exists(cached["cache_path"]):
        return FileResponse(
            cached["cache_path"],
            filename=cached["filename"],
            media_type='application/octet-stream'
        )
    
    # TODO: 实时从 Outlook 下载
    raise HTTPException(status_code=404, detail="附件未缓存，暂不支持实时下载")
