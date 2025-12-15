# Vulcan Brain 硬件配置

## GPU
- **型号**: NVIDIA GeForce RTX 5090 × 2（双卡）
- **显存**: 32GB × 2 = 64GB 总显存
- **驱动**: 580.95.05
- **NVLink**: 待确认

## CPU
- **型号**: AMD Ryzen Threadripper PRO 7975WX
- **核心**: 32 核 64 线程
- **架构**: Zen 4

## 内存
- **总量**: 256GB DDR5

## 存储
- 待补充

## 关键约束
1. 双卡部署 MoE 模型有兼容性问题
2. 单卡 32GB 可以跑大部分 70B 量化模型
3. 双卡 64GB 理论上可以跑 Qwen3 72B FP16

## 当前部署
- Ollama: qwen3:30b-a3b (CEO)
- SGLang: Qwen2.5-Coder-32B-AWQ (CTO) - 效果一般
