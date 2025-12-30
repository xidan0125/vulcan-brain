"use client";

import { useEffect, useRef } from "react";
import type { EChartsOption, ECharts } from "echarts";

interface BaseChartProps {
  option: EChartsOption | null;
  style?: React.CSSProperties;
  loading?: boolean;
}

export default function BaseChart({ 
  option, 
  style = { height: "300px", width: "100%" }, 
  loading = false,
}: BaseChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ECharts | null>(null);

  useEffect(() => {
    // 防止 React 19 Strict Mode 竞态条件
    let isDisposed = false;

    const initChart = async () => {
      if (!chartRef.current || !option) return;

      // 动态导入 echarts
      const echarts = await import("echarts");
      
      // 如果在加载过程中组件已卸载，直接返回
      if (isDisposed) return;

      // 确保销毁旧实例
      if (chartInstance.current) {
        chartInstance.current.dispose();
      }

      // 初始化
      const chart = echarts.init(chartRef.current);
      chartInstance.current = chart;

      // 设置配置
      chart.setOption(option);

      // 响应式
      const handleResize = () => chart.resize();
      window.addEventListener("resize", handleResize);

      // 返回清理函数
      return () => {
        window.removeEventListener("resize", handleResize);
      };
    };

    initChart();

    // 清理函数
    return () => {
      isDisposed = true;
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, [option]);

  // Loading 状态
  useEffect(() => {
    if (!chartInstance.current) return;
    if (loading) {
      chartInstance.current.showLoading();
    } else {
      chartInstance.current.hideLoading();
    }
  }, [loading]);

  if (!option) {
    return (
      <div style={style} className="flex items-center justify-center">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-500" />
      </div>
    );
  }

  return <div ref={chartRef} style={style} />;
}
