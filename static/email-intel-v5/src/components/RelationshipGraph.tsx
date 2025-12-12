import { useCallback, useRef, useState, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useRelationshipGraph, useRelationships } from '../hooks/useEmailIntel';
import type { GraphNode, GraphLink } from '../types';
import { Search, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

// Color mapping for node types
const nodeColors = {
  internal: '#f97316', // orange
  person: '#3b82f6',   // blue
  company: '#10b981',  // green
};

// Health score to color
function healthToColor(score: number): string {
  if (score >= 80) return '#22c55e'; // green
  if (score >= 60) return '#eab308'; // yellow
  if (score >= 40) return '#f97316'; // orange
  return '#ef4444'; // red
}

export default function RelationshipGraph() {
  const { data: graphData, isLoading: loadingGraph } = useRelationshipGraph();
  const { data: relationships, isLoading: loadingRel } = useRelationships();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null);

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Node click handler
  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    // Center on node
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 1000);
      graphRef.current.zoom(2, 1000);
    }
  }, []);

  // Filter nodes based on search
  const filteredData = graphData ? {
    nodes: graphData.nodes.filter(node =>
      !searchQuery || node.name.toLowerCase().includes(searchQuery.toLowerCase())
    ),
    links: graphData.links.filter(link => {
      if (!searchQuery) return true;
      const sourceId = typeof link.source === 'string' ? link.source : (link.source as GraphNode).id;
      const targetId = typeof link.target === 'string' ? link.target : (link.target as GraphNode).id;
      return graphData.nodes.some(n =>
        (n.id === sourceId || n.id === targetId) &&
        n.name.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }),
  } : { nodes: [], links: [] };

  // Node canvas rendering
  const nodeCanvasObject = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name;
    const fontSize = Math.max(12 / globalScale, 3);
    const nodeSize = Math.sqrt(node.email_count || 10) * 2 + 5;

    const x = node.x ?? 0;
    const y = node.y ?? 0;

    // Draw node circle
    ctx.beginPath();
    ctx.arc(x, y, nodeSize, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.type === 'internal' ? nodeColors.internal :
                    node.type === 'company' ? nodeColors.company : nodeColors.person;
    ctx.fill();

    // Draw health indicator ring
    ctx.beginPath();
    ctx.arc(x, y, nodeSize + 2, 0, 2 * Math.PI, false);
    ctx.strokeStyle = healthToColor(node.health_score || 50);
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw label
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#fff';
    ctx.fillText(label, x, y + nodeSize + fontSize + 2);
  }, []);

  const isLoading = loadingGraph || loadingRel;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" />
      </div>
    );
  }

  const contacts = relationships?.contacts || [];
  const topContacts = [...contacts]
    .sort((a, b) => b.total_emails - a.total_emails)
    .slice(0, 10);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-white">Relationship Graph</h2>
          <p className="text-sm text-zinc-500">
            {filteredData.nodes.length} 节点 / {filteredData.links.length} 连接
          </p>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="搜索联系人..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 pr-4 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500 w-64"
          />
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex gap-4">
        {/* Graph */}
        <div ref={containerRef} className="flex-1 bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden relative">
          {filteredData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={filteredData}
              width={dimensions.width}
              height={dimensions.height}
              nodeCanvasObject={nodeCanvasObject as (node: object, ctx: CanvasRenderingContext2D, globalScale: number) => void}
              nodePointerAreaPaint={(node: object, color: string, ctx: CanvasRenderingContext2D) => {
                const graphNode = node as GraphNode;
                const nodeSize = Math.sqrt(graphNode.email_count || 10) * 2 + 5;
                ctx.beginPath();
                ctx.arc(graphNode.x ?? 0, graphNode.y ?? 0, nodeSize + 5, 0, 2 * Math.PI, false);
                ctx.fillStyle = color;
                ctx.fill();
              }}
              onNodeClick={(node: object) => handleNodeClick(node as GraphNode)}
              linkColor={() => 'rgba(255,255,255,0.1)'}
              linkWidth={(link: object) => Math.sqrt((link as GraphLink).value || 1)}
              backgroundColor="transparent"
              cooldownTicks={100}
              d3AlphaDecay={0.02}
              d3VelocityDecay={0.3}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-zinc-500">暂无图谱数据</p>
            </div>
          )}

          {/* Graph Controls */}
          <div className="absolute bottom-4 right-4 flex gap-2">
            <button
              onClick={() => graphRef.current?.zoom(graphRef.current.zoom() * 1.2, 400)}
              className="p-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors"
            >
              <ZoomIn className="w-4 h-4 text-zinc-400" />
            </button>
            <button
              onClick={() => graphRef.current?.zoom(graphRef.current.zoom() / 1.2, 400)}
              className="p-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors"
            >
              <ZoomOut className="w-4 h-4 text-zinc-400" />
            </button>
            <button
              onClick={() => graphRef.current?.zoomToFit(400)}
              className="p-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors"
            >
              <Maximize2 className="w-4 h-4 text-zinc-400" />
            </button>
          </div>
        </div>

        {/* Side Panel */}
        <div className="w-72 space-y-4">
          {/* Selected Node Info */}
          {selectedNode && (
            <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
              <h3 className="text-sm font-medium text-zinc-400 mb-3">选中联系人</h3>
              <div className="space-y-2">
                <p className="text-white font-medium">{selectedNode.name}</p>
                {selectedNode.email && (
                  <p className="text-sm text-zinc-500">{selectedNode.email}</p>
                )}
                {selectedNode.company && (
                  <p className="text-sm text-zinc-400">{selectedNode.company}</p>
                )}
                <div className="flex items-center gap-2 mt-3">
                  <span className="text-xs text-zinc-500">健康度</span>
                  <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${selectedNode.health_score || 50}%`,
                        backgroundColor: healthToColor(selectedNode.health_score || 50),
                      }}
                    />
                  </div>
                  <span className="text-xs text-zinc-400">{selectedNode.health_score || 50}%</span>
                </div>
              </div>
            </div>
          )}

          {/* Top Contacts */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
            <h3 className="text-sm font-medium text-zinc-400 mb-3">活跃联系人 Top 10</h3>
            <div className="space-y-2">
              {topContacts.map((contact, index) => (
                <div key={contact.id} className="flex items-center gap-3">
                  <span className="text-xs text-zinc-600 w-4">{index + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{contact.name}</p>
                    <p className="text-xs text-zinc-600">{contact.total_emails} 封</p>
                  </div>
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: healthToColor(contact.health_score) }}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Legend */}
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-4">
            <h3 className="text-sm font-medium text-zinc-400 mb-3">图例</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: nodeColors.internal }} />
                <span className="text-xs text-zinc-400">内部员工</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: nodeColors.person }} />
                <span className="text-xs text-zinc-400">外部联系人</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: nodeColors.company }} />
                <span className="text-xs text-zinc-400">公司</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
