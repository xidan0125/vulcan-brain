"""
Vulcan Brain API - 知识库路由
P3 Knowledge Base API - 文档上传、RAG 索引
"""
import os
import json
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from llama_index.core import Document

from auth_api import get_current_user

router = APIRouter(tags=["Knowledge Base"])


# === 存储配置 ===
KB_STORAGE_DIR = './kb_storage'
KB_METADATA_FILE = os.path.join(KB_STORAGE_DIR, 'metadata.json')
KB_RAG_DIR = os.path.join(KB_STORAGE_DIR, 'rag_index')

# 确保目录存在
os.makedirs(KB_STORAGE_DIR, exist_ok=True)

# 加载/初始化 metadata
if os.path.exists(KB_METADATA_FILE):
    with open(KB_METADATA_FILE, 'r', encoding='utf-8') as f:
        _kb_metadata = json.load(f)
else:
    _kb_metadata = {}


def _save_metadata():
    """保存 metadata 到磁盘"""
    with open(KB_METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(_kb_metadata, f, ensure_ascii=False, indent=2)


def _rebuild_rag_index():
    """重建 RAG 索引"""
    from vulcan_libs.rag import VulcanRAG

    documents = []
    for doc_id, doc_info in _kb_metadata.items():
        file_path = doc_info['file_path']
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                documents.append(Document(
                    text=content,
                    doc_id=doc_id,
                    metadata={
                        'filename': doc_info['filename'],
                        'upload_time': doc_info['upload_time']
                    }
                ))

    if documents:
        rag = VulcanRAG(persist_dir=KB_RAG_DIR)
        rag.build_knowledge_base(documents)
        return len(documents)
    return 0


# === API Endpoints ===
@router.post('/api/knowledge/upload')
async def upload_document(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """
    P3 - 上传文档到知识库
    支持的文件类型: .txt, .md, .py, .json, .yaml, .yml
    """
    allowed_extensions = ['.txt', '.md', '.py', '.json', '.yaml', '.yml']
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f'不支持的文件类型: {file_ext}。支持的类型: {allowed_extensions}'
        )

    content = await file.read()
    text_content = content.decode('utf-8')
    doc_id = hashlib.md5(text_content.encode()).hexdigest()[:16]

    file_path = os.path.join(KB_STORAGE_DIR, f'{doc_id}_{file.filename}')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text_content)

    _kb_metadata[doc_id] = {
        'id': doc_id,
        'filename': file.filename,
        'file_path': file_path,
        'file_size': len(content),
        'upload_time': datetime.now().isoformat(),
        'file_type': file_ext,
        'user_id': current_user["user_id"]
    }
    _save_metadata()

    doc_count = _rebuild_rag_index()

    return {
        'success': True,
        'document_id': doc_id,
        'filename': file.filename,
        'file_size': len(content),
        'total_documents': doc_count,
        'message': '文档上传成功并已加入知识库'
    }


@router.get('/api/knowledge/list')
async def list_documents(current_user: dict = Depends(get_current_user)):
    """P3 - 列出所有知识库文档"""
    documents = []
    for doc_id, doc_info in _kb_metadata.items():
        documents.append({
            'id': doc_info['id'],
            'filename': doc_info['filename'],
            'file_size': doc_info['file_size'],
            'upload_time': doc_info['upload_time'],
            'file_type': doc_info['file_type']
        })

    documents.sort(key=lambda x: x['upload_time'], reverse=True)

    return {
        'documents': documents,
        'total_count': len(documents)
    }


@router.delete('/api/knowledge/{document_id}')
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user)):
    """P3 - 删除指定文档"""
    if document_id not in _kb_metadata:
        raise HTTPException(status_code=404, detail='文档不存在')

    doc_info = _kb_metadata[document_id]

    if os.path.exists(doc_info['file_path']):
        os.remove(doc_info['file_path'])

    del _kb_metadata[document_id]
    _save_metadata()

    doc_count = _rebuild_rag_index()

    return {
        'success': True,
        'deleted_document_id': document_id,
        'deleted_filename': doc_info['filename'],
        'remaining_documents': doc_count,
        'message': '文档已删除并更新知识库索引'
    }
