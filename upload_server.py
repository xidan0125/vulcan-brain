# upload_server.py - 文件/文件夹上传服务
"""
支持拖拽文件夹上传，保留目录结构
URL: https://upload.vsg-brain.com
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vulcan Upload Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "/data/storage/uploads"
UPLOAD_KEY = "vulcan2025"
MAX_SIZE = 500 * 1024 * 1024  # 单文件 500MB

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Vulcan Upload</title>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #ff6b35; margin-bottom: 5px; }
        .subtitle { color: #888; margin-bottom: 30px; }
        .upload-zone {
            border: 2px dashed #444; border-radius: 10px; padding: 60px 20px;
            text-align: center; margin: 20px 0; transition: all 0.3s;
            background: #16213e;
        }
        .upload-zone.dragover { border-color: #ff6b35; background: #1e2a4a; }
        .upload-zone p { margin: 10px 0; color: #888; }
        .upload-zone .icon { font-size: 48px; margin-bottom: 10px; }
        input[type=password] { padding: 12px 15px; font-size: 16px; width: 200px; border: 1px solid #333; background: #0f0f23; color: #eee; border-radius: 5px; }
        button { padding: 12px 25px; font-size: 16px; background: #ff6b35; color: white; border: none; cursor: pointer; border-radius: 5px; margin-left: 10px; }
        button:hover { background: #ff8c5a; }
        button:disabled { background: #555; cursor: not-allowed; }
        .auth-row { margin-bottom: 20px; }
        #fileList { margin: 20px 0; max-height: 300px; overflow-y: auto; }
        .file-item { display: flex; align-items: center; padding: 8px 12px; background: #16213e; margin: 5px 0; border-radius: 5px; font-size: 14px; }
        .file-item .path { flex: 1; color: #aaa; margin-right: 10px; word-break: break-all; }
        .file-item .size { color: #666; min-width: 80px; text-align: right; }
        .file-item .status { min-width: 30px; text-align: center; }
        .progress-bar { height: 4px; background: #333; border-radius: 2px; margin: 15px 0; overflow: hidden; }
        .progress-bar .fill { height: 100%; background: #4ade80; width: 0%; transition: width 0.3s; }
        #result { padding: 15px; background: #16213e; border-radius: 5px; margin-top: 20px; display: none; }
        .success { color: #4ade80; }
        .error { color: #f87171; }
        .server-files { margin-top: 40px; padding-top: 20px; border-top: 1px solid #333; }
        .server-files h3 { color: #888; }
        .folder { color: #60a5fa; }
        .tree-item { padding: 4px 0; font-family: monospace; font-size: 13px; }
        .tree-item:hover { background: #1e2a4a; }
        .refresh-btn { font-size: 12px; padding: 5px 10px; background: #333; margin-left: 10px; }
    </style>
</head>
<body>
    <h1>📁 Vulcan Upload</h1>
    <p class="subtitle">拖拽文件或文件夹上传，保留目录结构</p>
    
    <div class="auth-row">
        <input type="password" id="key" placeholder="上传密码">
        <button onclick="loadServerFiles()">查看已上传文件</button>
    </div>
    
    <div class="upload-zone" id="dropZone">
        <div class="icon">📂</div>
        <p><strong>拖拽文件或文件夹到这里</strong></p>
        <p>或 <label style="color:#ff6b35;cursor:pointer;"><input type="file" id="fileInput" multiple webkitdirectory style="display:none"> 点击选择文件夹</label></p>
        <p style="font-size:12px;">单文件最大 500MB</p>
    </div>
    
    <div id="fileList"></div>
    <div class="progress-bar"><div class="fill" id="progressFill"></div></div>
    <div id="uploadInfo" style="text-align:center;color:#888;font-size:14px;"></div>
    <div id="result"></div>
    
    <div class="server-files">
        <h3>📦 服务器文件 <button class="refresh-btn" onclick="loadServerFiles()">刷新</button></h3>
        <div id="serverFiles" style="color:#666;">输入密码后点击查看</div>
    </div>

<script>
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const result = document.getElementById('result');
const progressFill = document.getElementById('progressFill');
const uploadInfo = document.getElementById('uploadInfo');

let filesToUpload = [];

// 拖拽事件
dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('dragover'); };
dropZone.ondragleave = () => dropZone.classList.remove('dragover');
dropZone.ondrop = async (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const items = e.dataTransfer.items;
    filesToUpload = [];
    for (let item of items) {
        const entry = item.webkitGetAsEntry();
        if (entry) await traverseEntry(entry, '');
    }
    renderFileList();
    if (filesToUpload.length > 0) uploadFiles();
};

// 遍历文件夹
async function traverseEntry(entry, path) {
    if (entry.isFile) {
        const file = await new Promise(resolve => entry.file(resolve));
        file.relativePath = path + entry.name;
        filesToUpload.push(file);
    } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const entries = await new Promise(resolve => reader.readEntries(resolve));
        for (let e of entries) {
            await traverseEntry(e, path + entry.name + '/');
        }
    }
}

// 文件选择
fileInput.onchange = () => {
    filesToUpload = Array.from(fileInput.files).map(f => {
        f.relativePath = f.webkitRelativePath || f.name;
        return f;
    });
    renderFileList();
    if (filesToUpload.length > 0) uploadFiles();
};

function renderFileList() {
    fileList.innerHTML = filesToUpload.map((f, i) => `
        <div class="file-item" id="file-${i}">
            <span class="status">⏳</span>
            <span class="path">${f.relativePath}</span>
            <span class="size">${formatSize(f.size)}</span>
        </div>
    `).join('');
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
    return (bytes/1024/1024).toFixed(1) + ' MB';
}

async function uploadFiles() {
    const key = document.getElementById('key').value;
    if (!key) { alert('请输入密码'); return; }
    
    let success = 0, failed = 0;
    const total = filesToUpload.length;
    
    for (let i = 0; i < filesToUpload.length; i++) {
        const file = filesToUpload[i];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('path', file.relativePath);
        
        uploadInfo.textContent = `上传中 ${i+1}/${total}: ${file.relativePath}`;
        progressFill.style.width = ((i+1)/total*100) + '%';
        
        try {
            const resp = await fetch('/upload?key=' + key, { method: 'POST', body: formData });
            const item = document.getElementById('file-' + i);
            if (resp.ok) {
                success++;
                item.querySelector('.status').textContent = '✅';
            } else {
                failed++;
                item.querySelector('.status').textContent = '❌';
            }
        } catch (e) {
            failed++;
            document.getElementById('file-' + i).querySelector('.status').textContent = '❌';
        }
    }
    
    result.style.display = 'block';
    result.innerHTML = `<span class="success">✅ 上传完成: ${success} 成功</span>` + 
        (failed > 0 ? `, <span class="error">${failed} 失败</span>` : '');
    uploadInfo.textContent = '';
    loadServerFiles();
}

async function loadServerFiles() {
    const key = document.getElementById('key').value;
    if (!key) { alert('请输入密码'); return; }
    
    const container = document.getElementById('serverFiles');
    container.innerHTML = '加载中...';
    
    try {
        const resp = await fetch('/files?key=' + key);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail);
        
        if (data.tree.length === 0) {
            container.innerHTML = '<div style="color:#666;">暂无文件</div>';
            return;
        }
        
        container.innerHTML = data.tree.map(item => {
            const icon = item.type === 'dir' ? '📁' : '📄';
            const cls = item.type === 'dir' ? 'folder' : '';
            const size = item.size ? ` (${formatSize(item.size)})` : '';
            return `<div class="tree-item"><span class="${cls}">${'  '.repeat(item.depth)}${icon} ${item.name}${size}</span></div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = `<span class="error">加载失败: ${e.message}</span>`;
    }
}
</script>
</body>
</html>
"""

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form(""),
    key: str = Query(..., description="上传密码")
):
    if key != UPLOAD_KEY:
        raise HTTPException(status_code=403, detail="密码错误")
    
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=413, detail=f"文件太大，最大 {MAX_SIZE//1024//1024}MB")
    
    # 使用相对路径或原始文件名
    relative_path = path if path else file.filename
    # 安全处理路径
    safe_path = relative_path.replace("\\", "/").lstrip("/")
    # 防止路径遍历攻击
    if ".." in safe_path:
        raise HTTPException(status_code=400, detail="非法路径")
    
    # 按日期创建根文件夹
    date_folder = datetime.now().strftime("%Y%m%d")
    full_path = os.path.join(UPLOAD_DIR, date_folder, safe_path)
    
    # 创建目录
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    # 保存文件
    with open(full_path, "wb") as f:
        f.write(contents)
    
    return {"success": True, "path": full_path, "size": len(contents)}

@app.get("/files")
async def list_files(key: str = Query(...)):
    if key != UPLOAD_KEY:
        raise HTTPException(status_code=403, detail="密码错误")
    
    tree = []
    for root, dirs, files in os.walk(UPLOAD_DIR):
        depth = root.replace(UPLOAD_DIR, '').count(os.sep)
        rel_root = os.path.relpath(root, UPLOAD_DIR)
        if rel_root != '.':
            tree.append({"name": os.path.basename(root), "type": "dir", "depth": depth})
        for f in sorted(files):
            filepath = os.path.join(root, f)
            tree.append({
                "name": f, 
                "type": "file", 
                "depth": depth + 1,
                "size": os.path.getsize(filepath)
            })
    
    return {"tree": tree}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8800)
