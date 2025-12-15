# start.py
"""
Vulcan Brain v2.0 - Twin Towers Unified Launcher
双塔统一启动脚本
"""

import subprocess
import sys
import time
import signal
import os

def run_services():
    processes = []
    
    print("=" * 70)
    print("🔥 Vulcan Brain v2.0 - Twin Towers Architecture")
    print("=" * 70)
    print("")
    print("架构模式: 独立双服务 (The Twin Towers Pattern)")
    print("  Tower A: 硬件监控服务 (FastAPI) - Port 8001")
    print("  Tower B: 神经流 UI (Chainlit) - Port 8000")
    print("")
    print("正在启动系统...")
    print("-" * 70)

    try:
        # 1. 启动监控服务 (Tower A - API)
        print("[1/2] 🏗️  正在启动 Tower A (监控服务)...")
        p1 = subprocess.Popen(
            [sys.executable, "monitor_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(p1)
        
        # 等待 API 服务就绪
        time.sleep(2)
        print("      ✅ Tower A 已上线 (Port 8001)")

        # 2. 启动 Chainlit UI (Tower B)
        print("[2/2] 🏗️  正在启动 Tower B (Chat UI)...")
        
        # 使用 Chainlit 的完整路径
        chainlit_path = os.path.expanduser("~/.local/bin/chainlit")
        
        p2 = subprocess.Popen(
            [chainlit_path, "run", "app.py", "-w", "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(p2)
        
        time.sleep(3)
        print("      ✅ Tower B 已上线 (Port 8000)")
        
        print("")
        print("=" * 70)
        print("✅ Vulcan Brain 全系统启动完成")
        print("=" * 70)
        print("")
        print("访问地址: http://localhost:8000")
        print("GPU 监控: 右上角实时仪表盘")
        print("")
        print("按 Ctrl+C 停止所有服务")
        print("-" * 70)
        print("")
        
        # 保持主进程运行，直到被中断
        try:
            while True:
                # 检查进程是否仍在运行
                if p1.poll() is not None:
                    print("⚠️  Tower A (监控服务) 意外停止")
                    break
                if p2.poll() is not None:
                    print("⚠️  Tower B (UI) 意外停止")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    except KeyboardInterrupt:
        pass
    finally:
        print("\n\n🛑 正在关闭所有服务...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except:
                p.kill()
        print("✅ 所有服务已停止")
        print("\n再见，老板。\n")

if __name__ == "__main__":
    # 确保在项目根目录执行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run_services()
