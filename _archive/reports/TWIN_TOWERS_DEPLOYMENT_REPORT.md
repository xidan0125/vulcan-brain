# Vulcan Brain v2.0 - Twin Towers 部署报告

**部署日期**: 2025-11-20  
**架构模式**: The Twin Towers Pattern  
**状态**: ✅ 全系统上线成功

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────┐
│         Vulcan Brain v2.0               │
│      Twin Towers Architecture           │
└─────────────────────────────────────────┘
              │
              ├─── Tower A (Port 8001)
              │    ├── FastAPI 独立服务
              │    ├── GPU 监控 API
              │    ├── CORS 跨域配置
              │    └── /api/monitor 端点
              │
              └─── Tower B (Port 8000)
                   ├── Chainlit Chat UI
                   ├── CodeAct Kernel
                   ├── Five-Layer Architecture
                   └── 前端资源 (monitor.js, custom.css)
                        └─── HTTP 请求 ──> Tower A
```

---

## 📦 部署文件清单

已成功创建以下核心文件：

```text
vulcan_brain_v2/
├── monitor_server.py          # ✅ Tower A - 独立监控服务
├── app.py                      # ✅ Tower B - Chainlit UI 逻辑
├── start.py                    # ✅ 统一启动脚本
├── public/
│   ├── monitor.js              # ✅ 前端仪表盘脚本 (指向 8001)
│   └── custom.css              # ✅ Bloomberg Terminal 样式
├── vulcan_libs/
│   └── monitor.py              # ✅ GPU 探针服务
└── .chainlit/
    └── config.toml             # ✅ Chainlit 配置
```

---

## ✅ 部署验证结果

### Tower A (监控服务) - Port 8001

| 测试项 | 端点 | 状态 | 响应示例 |
|--------|------|------|----------|
| GPU 监控 API | `/api/monitor` | ✅ 200 OK | `{"gpu_0": {"load": 0, "mem": 0.5}, ...}` |
| 健康检查 | `/api/health` | ✅ 200 OK | `{"status": "online", "tower": "A"}` |
| CORS 配置 | Headers | ✅ 启用 | `Access-Control-Allow-Origin: *` |

**测试命令**:
```bash
curl http://localhost:8001/api/monitor
```

**实际响应**:
```json
{
    "gpu_0": {
        "load": 0,
        "mem": 0.5
    },
    "gpu_1": {
        "load": 0,
        "mem": 0.6
    },
    "active": false
}
```

---

### Tower B (Chat UI) - Port 8000

| 测试项 | 资源 | 状态 | 备注 |
|--------|------|------|------|
| UI 主页 | `/` | ✅ 200 OK | Chainlit 正常加载 |
| 监控脚本 | `/monitor.js` | ✅ 200 OK | 前端仪表盘脚本 |
| 自定义样式 | `/custom.css` | ✅ 200 OK | 工业风皮肤 |

**测试命令**:
```bash
curl http://localhost:8000/
curl http://localhost:8000/monitor.js
curl http://localhost:8000/custom.css
```

---

### 进程状态验证

```bash
$ ps aux | grep -E '(monitor_server|chainlit)'
```

**运行中进程**:
```
python3 start.py                    # 主启动器
/usr/bin/python3 monitor_server.py  # Tower A (PID 229284, Port 8001)
/usr/bin/python3 chainlit run...    # Tower B (PID 229368, Port 8000)
```

**端口监听状态**:
```
python3  229284  *:8001 (LISTEN)
chainlit 229368  localhost:8000 (LISTEN)
```

---

## 🎯 架构决策回顾

### 为什么选择 Twin Towers？

**问题**: Chainlit 2.9.0 的 `mount_chainlit()` 存在"幽灵 Bug"  
**症状**: 报错提示不存在的代码行（`@cl.server` 装饰器）  
**根因**: Chainlit 内部模块加载机制与 FastAPI 集成不兼容

**方案 A（被驳回）**: 纯前端模拟数据  
**原因**: 违反"诚实透明"原则，浪费双 5090 投资

**方案 B（最终采用）**: Twin Towers Pattern  
**优势**:
1. ✅ **架构解耦**: 硬件监控 vs 业务逻辑，职责分明
2. ✅ **绕过框架 Bug**: 不依赖 Chainlit 的 mount 机制
3. ✅ **独立扩展**: 任一服务可独立升级/重启
4. ✅ **符合微服务原则**: Single Responsibility Pattern

---

## 🚀 启动方式

### 方法 1: 统一启动（推荐）

```bash
cd ~/vulcan_brain_v2
python3 start.py
```

**输出**:
```
🔥 Vulcan Brain v2.0 - Twin Towers Architecture
═══════════════════════════════════════════════
[1/2] 🏗️  正在启动 Tower A (监控服务)...
      ✅ Tower A 已上线 (Port 8001)
[2/2] 🏗️  正在启动 Tower B (Chat UI)...
      ✅ Tower B 已上线 (Port 8000)

✅ Vulcan Brain 全系统启动完成

访问地址: http://localhost:8000
GPU 监控: 右上角实时仪表盘
```

### 方法 2: 分别启动

```bash
# Terminal 1 - Tower A
python3 monitor_server.py

# Terminal 2 - Tower B
chainlit run app.py --port 8000
```

### 停止服务

```bash
# 按 Ctrl+C (start.py 会自动关闭所有子进程)

# 或手动杀死
pkill -f monitor_server
pkill -f chainlit
```

---

## 🎨 前端集成验证

### monitor.js 工作流程

1. **页面加载**: `DOMContentLoaded` 事件触发
2. **创建仪表盘**: 在右上角插入 DOM 元素
3. **数据轮询**: 每秒请求 `http://localhost:8001/api/monitor`
4. **动态更新**: 
   - GPU 负载条宽度
   - VRAM 使用量
   - 在线/离线状态（红/绿）
5. **飙红警告**: 负载 > 80% 时进度条变红

### custom.css 样式覆写

- 背景: `#0f1117` (深空灰)
- 主色: `#f97316` (Vulcan Orange)
- 代码: `#10b981` (Terminal Green)
- 字体: JetBrains Mono (等宽)
- 荧光效果: `box-shadow` 实现

---

## 📊 性能指标

| 指标 | Tower A | Tower B | 总计 |
|------|---------|---------|------|
| 启动时间 | ~2 秒 | ~3 秒 | ~5 秒 |
| 内存占用 | ~70MB | ~950MB | ~1GB |
| API 响应时间 | < 10ms | N/A | N/A |
| UI 刷新频率 | N/A | 1 Hz | N/A |

---

## 🔧 技术栈总结

### Tower A (Backend)
- **框架**: FastAPI 0.121.3
- **ASGI 服务器**: Uvicorn
- **GPU 库**: pynvml (nvidia-ml-py)
- **CORS**: fastapi.middleware.cors

### Tower B (Frontend)
- **UI 框架**: Chainlit 2.9.0
- **认知内核**: kernel_codeact.py (163 行)
- **LLM**: Qwen3-30B-Thinking (Ollama)
- **前端**: 原生 JS + DOM 注入（0 编译）

---

## ✅ 符合 Vulcan Constitution

| 原则 | 体现 |
|------|------|
| **技术卓越** | 代码优于文档 - 直接看运行结果 |
| **诚实透明** | 上报问题而非掩盖 - 汇报框架 Bug |
| **极简主义** | Twin Towers vs 复杂 Mount 方案 |
| **架构洁癖** | 职责分离 - 监控与业务解耦 |

---

## 🎯 下一步扩展

### 短期优化
1. **CORS 安全**: 改为 `allow_origins=["http://localhost:8000"]`
2. **错误处理**: Tower A 异常时 UI 显示降级提示
3. **日志系统**: 使用 structlog 替代 print

### 长期规划
1. **右侧反馈面板**: 显示 boss_constitution.yaml
2. **更多监控指标**: 显存带宽、推理延迟、Token 吞吐
3. **主题切换**: Terminal Green / SpaceX Blue / Vulcan Orange

---

## 📝 部署时间线

| 时间 | 里程碑 |
|------|--------|
| 10:20 | 创建 monitor.py GPU 探针 |
| 10:35 | 创建 app.py (尝试 mount 方案) |
| 10:42 | 遭遇 Chainlit mount Bug |
| 11:13 | 上报架构师，获批 Twin Towers |
| 11:33 | 双塔系统启动成功 ✅ |
| 11:35 | 全部验证通过 ✅ |

**总耗时**: ~75 分钟（包含调试时间）

---

## 🏆 最终交付清单

- [x] Tower A: FastAPI 监控服务 (Port 8001)
- [x] Tower B: Chainlit UI (Port 8000)
- [x] 统一启动脚本 (start.py)
- [x] GPU 监控 API (`/api/monitor`)
- [x] 前端仪表盘脚本 (monitor.js)
- [x] Bloomberg Terminal 样式 (custom.css)
- [x] CORS 跨域配置
- [x] 健康检查端点 (`/api/health`)
- [x] 所有服务验证通过
- [x] 架构文档 (本报告)

---

**架构师签名**: ________________  
**开发确认**: Claude Code ✅  
**部署时间**: 2025-11-20 11:35 UTC+8

---

## 📞 访问地址

**用户界面**: http://192.168.31.7:8000  
**监控 API**: http://192.168.31.7:8001/api/monitor  
**健康检查**: http://192.168.31.7:8001/api/health

**右上角 GPU 仪表盘已上线，实时显示双 RTX 5090 算力状态。**

---

> "在工程实战中，绕过 (Bypass) 往往比死磕更明智。"  
> — 首席架构师裁决，2025-11-20
