// monitor.js - V4 GPU Monitor Dashboard
/*
Vulcan Brain V4 - GPU 实时监控面板

功能：
1. 轮询 /api/monitor 获取 GPU 数据
2. 动态渲染 GPU 卡片
3. 显示利用率、显存、温度、功耗
4. 自动更新，刷新间隔 2 秒
*/

(function() {
    'use strict';
    
    // 配置
    const CONFIG = {
        apiEndpoint: '/api/monitor',
        refreshInterval: 2000,  // 2 秒刷新一次
        retryDelay: 5000        // 失败后 5 秒重试
    };
    
    // 创建监控面板 DOM
    function createMonitorPanel() {
        // 检查是否已存在
        if (document.getElementById('gpu-monitor-panel')) {
            return;
        }
        
        const panel = document.createElement('div');
        panel.id = 'gpu-monitor-panel';
        panel.innerHTML = `
            <div class="panel-header">
                ⚡ GPU STATUS
            </div>
            <div id="gpu-cards-container">
                <div style="color: #b0b0b0; text-align: center; padding: 20px;">
                    Loading...
                </div>
            </div>
        `;
        
        document.body.appendChild(panel);
    }
    
    // 渲染 GPU 卡片
    function renderGPUCards(data) {
        const container = document.getElementById('gpu-cards-container');
        
        if (!container) {
            console.error('[Monitor] Container not found');
            return;
        }
        
        if (!data || !data.gpus || data.gpus.length === 0) {
            container.innerHTML = `
                <div style="color: #ff0000; text-align: center;">
                    ❌ No GPU data available
                </div>
            `;
            return;
        }
        
        // 渲染每个 GPU
        container.innerHTML = data.gpus.map((gpu, index) => {
            const memPercent = gpu.memory_percent || 0;
            const tempColor = getTemperatureColor(gpu.temperature);
            const powerPercent = ((gpu.power_draw / gpu.power_limit) * 100).toFixed(1);
            
            return `
                <div class="gpu-card">
                    <div class="gpu-name">GPU ${gpu.gpu_id}: ${gpu.name}</div>
                    
                    <div class="stat-row">
                        <span class="stat-label">Load:</span>
                        <span class="stat-value">${gpu.utilization}%</span>
                    </div>
                    
                    <div class="stat-row">
                        <span class="stat-label">VRAM:</span>
                        <span class="stat-value">${formatMemory(gpu.memory_used)} / ${formatMemory(gpu.memory_total)}</span>
                    </div>
                    
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${memPercent}%"></div>
                    </div>
                    
                    <div class="stat-row">
                        <span class="stat-label">Temp:</span>
                        <span class="stat-value" style="color: ${tempColor}">${gpu.temperature}°C</span>
                    </div>
                    
                    <div class="stat-row">
                        <span class="stat-label">Power:</span>
                        <span class="stat-value">${gpu.power_draw}W / ${gpu.power_limit}W (${powerPercent}%)</span>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    // 格式化内存（MB → GB）
    function formatMemory(mb) {
        if (mb >= 1024) {
            return (mb / 1024).toFixed(1) + ' GB';
        }
        return mb + ' MB';
    }
    
    // 根据温度返回颜色
    function getTemperatureColor(temp) {
        if (temp < 50) return '#00ff00';      // 绿色：正常
        if (temp < 70) return '#ffff00';      // 黄色：温暖
        if (temp < 85) return '#ff8000';      // 橙色：偏热
        return '#ff0000';                     // 红色：过热
    }
    
    // 获取 GPU 数据
    async function fetchGPUData() {
        try {
            const response = await fetch(CONFIG.apiEndpoint);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            renderGPUCards(data);
            
            // 继续轮询
            setTimeout(fetchGPUData, CONFIG.refreshInterval);
        } catch (error) {
            console.error('[Monitor] Fetch failed:', error);
            
            // 显示错误状态
            const container = document.getElementById('gpu-cards-container');
            if (container) {
                container.innerHTML = `
                    <div style="color: #ff8000; text-align: center; padding: 20px;">
                        ⚠️ Connection lost<br>
                        Retrying in ${CONFIG.retryDelay / 1000}s...
                    </div>
                `;
            }
            
            // 重试
            setTimeout(fetchGPUData, CONFIG.retryDelay);
        }
    }
    
    // 初始化
    function init() {
        console.log('[Monitor] Initializing GPU dashboard');
        
        // 等待 DOM 加载完成
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                createMonitorPanel();
                fetchGPUData();
            });
        } else {
            createMonitorPanel();
            fetchGPUData();
        }
    }
    
    // 启动
    init();
})();
