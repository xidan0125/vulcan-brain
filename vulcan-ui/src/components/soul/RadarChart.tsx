'use client';

import React from 'react';

interface RadarChartProps {
  dimensions: {
    risk_appetite: number;      // 风险偏好
    time_preference: number;    // 时间偏好
    social_tendency: number;    // 社交倾向
    decision_style: number;     // 决策风格
    value_priority: number;     // 价值优先级
    stress_response: number;    // 压力响应
  };
  size?: number;
}

const DIMENSION_LABELS: Record<string, string> = {
  risk_appetite: '风险偏好',
  time_preference: '时间偏好',
  social_tendency: '社交倾向',
  decision_style: '决策风格',
  value_priority: '价值优先级',
  stress_response: '压力响应'
};

export default function RadarChart({ dimensions, size = 280 }: RadarChartProps) {
  const center = size / 2;
  const radius = size * 0.35;
  const labelRadius = size * 0.48;

  const dimKeys = Object.keys(DIMENSION_LABELS);
  const angleStep = (2 * Math.PI) / dimKeys.length;

  // 计算多边形顶点
  const getPoint = (index: number, value: number) => {
    const angle = angleStep * index - Math.PI / 2; // 从顶部开始
    const r = radius * value;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle)
    };
  };

  // 背景网格线
  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  // 数据多边形路径
  const dataPoints = dimKeys.map((key, i) => {
    const value = dimensions[key as keyof typeof dimensions] || 0.5;
    return getPoint(i, value);
  });
  const dataPath = dataPoints.map((p, i) =>
    `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
  ).join(' ') + ' Z';

  // 标签位置
  const labelPoints = dimKeys.map((_, i) => {
    const angle = angleStep * i - Math.PI / 2;
    return {
      x: center + labelRadius * Math.cos(angle),
      y: center + labelRadius * Math.sin(angle)
    };
  });

  return (
    <div className="relative">
      <svg width={size} height={size} className="mx-auto">
        {/* 背景网格 */}
        {gridLevels.map((level, levelIdx) => {
          const gridPoints = dimKeys.map((_, i) => getPoint(i, level));
          const gridPath = gridPoints.map((p, i) =>
            `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
          ).join(' ') + ' Z';
          return (
            <path
              key={levelIdx}
              d={gridPath}
              fill="none"
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="1"
            />
          );
        })}

        {/* 轴线 */}
        {dimKeys.map((_, i) => {
          const endPoint = getPoint(i, 1);
          return (
            <line
              key={i}
              x1={center}
              y1={center}
              x2={endPoint.x}
              y2={endPoint.y}
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="1"
            />
          );
        })}

        {/* 数据区域 */}
        <path
          d={dataPath}
          fill="rgba(239, 68, 68, 0.2)"
          stroke="#ef4444"
          strokeWidth="2"
        />

        {/* 数据点 */}
        {dataPoints.map((point, i) => (
          <circle
            key={i}
            cx={point.x}
            cy={point.y}
            r="4"
            fill="#ef4444"
            stroke="#1a1a1a"
            strokeWidth="2"
          />
        ))}

        {/* 中心点 */}
        <circle
          cx={center}
          cy={center}
          r="3"
          fill="rgba(255,255,255,0.3)"
        />
      </svg>

      {/* 标签 */}
      {dimKeys.map((key, i) => {
        const pos = labelPoints[i];
        const value = dimensions[key as keyof typeof dimensions] || 0.5;
        const valuePercent = Math.round(value * 100);

        // 调整文本对齐
        let textAnchor = 'middle';
        let dx = 0;
        if (pos.x < center - 20) {
          textAnchor = 'end';
          dx = -5;
        } else if (pos.x > center + 20) {
          textAnchor = 'start';
          dx = 5;
        }

        return (
          <div
            key={key}
            className="absolute text-xs"
            style={{
              left: pos.x,
              top: pos.y,
              transform: `translate(${textAnchor === 'end' ? '-100%' : textAnchor === 'start' ? '0' : '-50%'}, -50%)`,
            }}
          >
            <span className="text-gray-400">{DIMENSION_LABELS[key]}</span>
            <span className="ml-1 text-red-400 font-mono">{valuePercent}%</span>
          </div>
        );
      })}
    </div>
  );
}
