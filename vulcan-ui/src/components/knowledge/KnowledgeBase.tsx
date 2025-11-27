"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Upload,
  File,
  FileText,
  Trash2,
  Search,
  Database,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";

interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  upload_time: string;
}

interface ListResponse {
  documents: Document[];
  total_count: number;
}

interface UploadResponse {
  success: boolean;
  document_id: string;
  filename: string;
  file_size: number;
  total_documents: number;
  message: string;
}

const API_BASE = "http://100.79.150.62:8001";

export default function KnowledgeBase() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [uploading, setUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch documents from API
  const fetchDocuments = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/api/knowledge/list`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data: ListResponse = await response.json();
      setDocuments(data.documents);
      setError(null);
    } catch (err: any) {
      console.error("Failed to fetch documents:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setError(null);

    for (const file of Array.from(files)) {
      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(`${API_BASE}/api/knowledge/upload`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || `Upload failed: ${response.status}`);
        }

        const data: UploadResponse = await response.json();
        console.log("Upload success:", data);
      } catch (err: any) {
        console.error("Upload error:", err);
        setError(err.message);
      }
    }

    // Refresh document list
    await fetchDocuments();
    setUploading(false);
    e.target.value = "";
  };

  const handleDelete = async (docId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/knowledge/${docId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `Delete failed: ${response.status}`);
      }

      // Refresh document list
      await fetchDocuments();
    } catch (err: any) {
      console.error("Delete error:", err);
      setError(err.message);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);

    if (diffInHours < 1) return "刚刚";
    if (diffInHours < 24) return `${Math.floor(diffInHours)} 小时前`;
    if (diffInHours < 48) return "昨天";
    return date.toLocaleDateString("zh-CN");
  };

  const getFileIcon = (type: string) => {
    if (type === ".pdf") return <File className="w-5 h-5 text-red-500" />;
    if (type === ".md") return <FileText className="w-5 h-5 text-blue-500" />;
    if (type === ".py") return <FileText className="w-5 h-5 text-yellow-500" />;
    if (type === ".json") return <FileText className="w-5 h-5 text-green-500" />;
    return <FileText className="w-5 h-5 text-muted-foreground" />;
  };

  const filteredDocs = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-primary" />
              <h1 className="text-2xl font-semibold">Knowledge Base</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              上传文档构建 RAG 向量知识库
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Refresh Button */}
            <button
              onClick={fetchDocuments}
              disabled={isLoading}
              className="p-2 hover:bg-accent rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
            </button>

            {/* Upload Button */}
            <label className="px-4 py-2 bg-primary/10 text-primary hover:bg-primary/20 rounded-lg transition-colors flex items-center gap-2 text-sm cursor-pointer">
              <Upload className="w-4 h-4" />
              {uploading ? "Uploading..." : "Upload Files"}
              <input
                type="file"
                multiple
                accept=".txt,.md,.py,.json,.yaml,.yml"
                onChange={handleFileUpload}
                className="hidden"
                disabled={uploading}
              />
            </label>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3 text-sm text-destructive">
            Error: {error}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="text-2xl font-bold text-primary">
              {documents.length}
            </div>
            <div className="text-xs text-muted-foreground mt-1">Total Documents</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="text-2xl font-bold text-secondary">
              {formatFileSize(documents.reduce((sum, d) => sum + d.file_size, 0))}
            </div>
            <div className="text-xs text-muted-foreground mt-1">Total Size</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="text-2xl font-bold text-foreground">
              {documents.filter(d => d.file_type === ".md" || d.file_type === ".txt").length}
            </div>
            <div className="text-xs text-muted-foreground mt-1">Text Documents</div>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索文档..."
            className="w-full pl-10 pr-4 py-2 bg-card border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="text-center py-8 text-muted-foreground">
            <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin" />
            <p>Loading documents...</p>
          </div>
        )}

        {/* Documents List */}
        {!isLoading && (
          <div className="space-y-2">
            {filteredDocs.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>没有找到文档</p>
                <p className="text-xs mt-1">上传 .txt, .md, .py, .json 文件开始构建知识库</p>
              </div>
            ) : (
              filteredDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="bg-card border border-border rounded-lg p-4 hover:border-primary/50 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    {/* Icon */}
                    <div className="mt-0.5">{getFileIcon(doc.file_type)}</div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-semibold truncate">
                          {doc.filename}
                        </h3>
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                      </div>

                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>{formatFileSize(doc.file_size)}</span>
                        <span>·</span>
                        <span>{formatDate(doc.upload_time)}</span>
                        <span>·</span>
                        <span className="text-primary">{doc.file_type}</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="p-2 hover:bg-red-500/10 text-muted-foreground hover:text-red-500 rounded transition-colors"
                      title="Delete document"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Info Box */}
        <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <span className="text-primary">ℹ️</span>
            RAG Integration
          </h3>
          <p className="text-xs text-muted-foreground">
            文档上传后将自动进行 Chunking 和 Embedding。支持的格式: TXT, MD, PY, JSON, YAML。
            API 端点: <code className="px-1.5 py-0.5 bg-background rounded">POST /api/knowledge/upload</code>
          </p>
        </div>
      </div>
    </div>
  );
}
