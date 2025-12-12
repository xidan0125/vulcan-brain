"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { useAuth } from "@/contexts/AuthContext";
import {
  Brain,
  Network,
  Users,
  Building2,
  Mail,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Search,
  Filter,
  RefreshCw,
  ChevronRight,
  Clock,
  Send,
  Inbox,
  Zap,
  Activity,
  BarChart3,
  PieChart,
  Eye,
  X,
  Maximize2,
  ZoomIn,
  ZoomOut,
  Move,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ============ Types ============
interface Contact {
  email: string;
  name: string;
  domain: string;
  company_name?: string;
  job_title?: string;
  department?: string;
  sent_count: number;
  received_count: number;
  total_interactions: number;
  health_score: number;
  health_trend: "active" | "stable" | "cooling" | "inactive" | "unknown";
  first_contact?: string;
  last_sent?: string;
  last_received?: string;
}

interface Company {
  domain: string;
  name: string;
  relation_type: string;
  confidence: string;
  email_count: number;
  contact_count: number;
  health_score: number;
  health_trend: string;
  first_contact?: string;
  last_contact?: string;
  contacts?: Contact[];
}

interface GraphNode {
  id: string;
  type: "company" | "contact" | "internal";
  name: string;
  health: number;
  emails: number;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
  type: "sent" | "received" | "both";
}

interface DashboardStats {
  total_contacts: number;
  active_contacts: number;
  total_companies: number;
  needs_attention: number;
  avg_health_score: number;
  total_emails: number;
  health_distribution: {
    active: number;
    stable: number;
    cooling: number;
    inactive: number;
  };
  relation_distribution: Record<string, number>;
}

// ============ Utility Components ============
const HealthRing = ({ score, size = 40 }: { score: number; size?: number }) => {
  const radius = size / 2 - 3;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  let color = "text-red-500";
  if (score > 80) color = "text-emerald-500";
  else if (score > 60) color = "text-yellow-500";
  else if (score > 40) color = "text-orange-500";

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg className="transform -rotate-90 w-full h-full">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#222"
          strokeWidth="4"
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth="4"
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={`${color} transition-all duration-500`}
        />
      </svg>
      <span className="absolute text-xs font-bold text-zinc-200">{score}</span>
    </div>
  );
};

const TrendIcon = ({ type, size = 14 }: { type: string; size?: number }) => {
  switch (type) {
    case "active":
      return <TrendingUp size={size} className="text-emerald-500" />;
    case "stable":
      return <Minus size={size} className="text-blue-500" />;
    case "cooling":
      return <TrendingDown size={size} className="text-yellow-500" />;
    case "inactive":
      return <AlertTriangle size={size} className="text-red-500" />;
    default:
      return <Clock size={size} className="text-zinc-500" />;
  }
};

const RelationBadge = ({ type }: { type: string }) => {
  const colors: Record<string, string> = {
    client: "border-purple-500/30 text-purple-400 bg-purple-500/10",
    vendor: "border-blue-500/30 text-blue-400 bg-blue-500/10",
    partner: "border-emerald-500/30 text-emerald-400 bg-emerald-500/10",
    internal: "border-orange-500/30 text-orange-400 bg-orange-500/10",
    unknown: "border-zinc-500/30 text-zinc-400 bg-zinc-500/10",
  };

  const labels: Record<string, string> = {
    client: "客户",
    vendor: "供应商",
    partner: "合作伙伴",
    internal: "内部",
    unknown: "未分类",
  };

  return (
    <span
      className={`text-[10px] px-2 py-0.5 rounded border font-medium ${
        colors[type] || colors.unknown
      }`}
    >
      {labels[type] || type}
    </span>
  );
};

// ============ Force-directed Graph Component ============
const RelationshipGraph = ({
  companies,
  contacts,
  onNodeClick,
}: {
  companies: Company[];
  contacts: Contact[];
  onNodeClick: (node: GraphNode) => void;
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);

  // Build graph data
  useEffect(() => {
    if (!companies.length && !contacts.length) return;

    const newNodes: GraphNode[] = [];
    const newEdges: GraphEdge[] = [];
    const nodeMap = new Map<string, GraphNode>();

    // Add Vulcan as center node
    const vulcanNode: GraphNode = {
      id: "vulcan",
      type: "internal",
      name: "Vulcan Shield",
      health: 100,
      emails: contacts.reduce((sum, c) => sum + c.total_interactions, 0),
      x: dimensions.width / 2,
      y: dimensions.height / 2,
    };
    newNodes.push(vulcanNode);
    nodeMap.set("vulcan", vulcanNode);

    // Add company nodes in a circle around center
    companies.slice(0, 20).forEach((company, i) => {
      const angle = (2 * Math.PI * i) / Math.min(companies.length, 20);
      const radius = 200;
      const node: GraphNode = {
        id: company.domain,
        type: "company",
        name: company.name,
        health: company.health_score,
        emails: company.email_count,
        x: dimensions.width / 2 + Math.cos(angle) * radius,
        y: dimensions.height / 2 + Math.sin(angle) * radius,
      };
      newNodes.push(node);
      nodeMap.set(company.domain, node);

      // Edge from Vulcan to company
      newEdges.push({
        source: "vulcan",
        target: company.domain,
        weight: Math.log(company.email_count + 1) * 2,
        type: "both",
      });
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [companies, contacts, dimensions]);

  // Handle resize
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
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  // Simple force simulation
  useEffect(() => {
    if (nodes.length < 2) return;

    const interval = setInterval(() => {
      setNodes((prevNodes) => {
        const newNodes = [...prevNodes];
        const centerX = dimensions.width / 2;
        const centerY = dimensions.height / 2;

        newNodes.forEach((node, i) => {
          if (node.id === "vulcan") return;

          // Repulsion from other nodes
          let fx = 0,
            fy = 0;
          newNodes.forEach((other, j) => {
            if (i === j) return;
            const dx = (node.x || 0) - (other.x || 0);
            const dy = (node.y || 0) - (other.y || 0);
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = 5000 / (dist * dist);
            fx += (dx / dist) * force;
            fy += (dy / dist) * force;
          });

          // Attraction to center
          const dx = centerX - (node.x || 0);
          const dy = centerY - (node.y || 0);
          fx += dx * 0.01;
          fy += dy * 0.01;

          // Apply forces
          node.x = (node.x || 0) + fx * 0.1;
          node.y = (node.y || 0) + fy * 0.1;

          // Boundary constraints
          node.x = Math.max(50, Math.min(dimensions.width - 50, node.x || 0));
          node.y = Math.max(50, Math.min(dimensions.height - 50, node.y || 0));
        });

        return newNodes;
      });
    }, 50);

    // Stop after a few seconds
    setTimeout(() => clearInterval(interval), 3000);

    return () => clearInterval(interval);
  }, [nodes.length, dimensions]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.max(0.3, Math.min(3, z * delta)));
  };

  const getNodeColor = (node: GraphNode) => {
    if (node.type === "internal") return "#f97316"; // orange
    if (node.health > 80) return "#10b981"; // emerald
    if (node.health > 60) return "#eab308"; // yellow
    if (node.health > 40) return "#f97316"; // orange
    return "#ef4444"; // red
  };

  const getNodeSize = (node: GraphNode) => {
    if (node.type === "internal") return 30;
    return 10 + Math.log(node.emails + 1) * 5;
  };

  return (
    <div
      ref={containerRef}
      className="w-full h-full bg-zinc-950 rounded-xl border border-zinc-800 relative overflow-hidden"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
    >
      {/* Controls */}
      <div className="absolute top-4 right-4 flex gap-2 z-10">
        <button
          onClick={() => setZoom((z) => Math.min(3, z * 1.2))}
          className="p-2 bg-zinc-900/80 border border-zinc-700 rounded-lg hover:bg-zinc-800 text-zinc-400"
        >
          <ZoomIn size={16} />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(0.3, z * 0.8))}
          className="p-2 bg-zinc-900/80 border border-zinc-700 rounded-lg hover:bg-zinc-800 text-zinc-400"
        >
          <ZoomOut size={16} />
        </button>
        <button
          onClick={() => {
            setZoom(1);
            setPan({ x: 0, y: 0 });
          }}
          className="p-2 bg-zinc-900/80 border border-zinc-700 rounded-lg hover:bg-zinc-800 text-zinc-400"
        >
          <Maximize2 size={16} />
        </button>
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-zinc-900/90 border border-zinc-700 rounded-lg p-3 z-10">
        <div className="text-[10px] text-zinc-500 mb-2 font-mono">LEGEND</div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-orange-500" />
            <span className="text-[10px] text-zinc-400">Vulcan (内部)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500" />
            <span className="text-[10px] text-zinc-400">健康 (80+)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <span className="text-[10px] text-zinc-400">稳定 (60-80)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-[10px] text-zinc-400">需关注 (&lt;60)</span>
          </div>
        </div>
      </div>

      {/* Graph SVG */}
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="cursor-move"
      >
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Edges */}
          {edges.map((edge, i) => {
            const sourceNode = nodes.find((n) => n.id === edge.source);
            const targetNode = nodes.find((n) => n.id === edge.target);
            if (!sourceNode || !targetNode) return null;

            return (
              <line
                key={i}
                x1={sourceNode.x}
                y1={sourceNode.y}
                x2={targetNode.x}
                y2={targetNode.y}
                stroke={hoveredNode === edge.source || hoveredNode === edge.target ? "#f97316" : "#333"}
                strokeWidth={edge.weight}
                strokeOpacity={hoveredNode === edge.source || hoveredNode === edge.target ? 0.8 : 0.3}
                className="transition-all duration-200"
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onNodeClick(node)}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              className="cursor-pointer"
            >
              {/* Glow effect */}
              {hoveredNode === node.id && (
                <circle
                  r={getNodeSize(node) + 8}
                  fill={getNodeColor(node)}
                  fillOpacity={0.2}
                  className="animate-pulse"
                />
              )}

              {/* Node circle */}
              <circle
                r={getNodeSize(node)}
                fill={getNodeColor(node)}
                stroke={hoveredNode === node.id ? "#fff" : "transparent"}
                strokeWidth={2}
                className="transition-all duration-200"
              />

              {/* Label */}
              {(hoveredNode === node.id || node.type === "internal") && (
                <text
                  y={getNodeSize(node) + 14}
                  textAnchor="middle"
                  className="text-[10px] fill-zinc-300 font-medium"
                  style={{ pointerEvents: "none" }}
                >
                  {node.name.length > 15 ? node.name.slice(0, 15) + "..." : node.name}
                </text>
              )}
            </g>
          ))}
        </g>
      </svg>

      {/* Stats overlay */}
      <div className="absolute top-4 left-4 bg-zinc-900/90 border border-zinc-700 rounded-lg p-3">
        <div className="text-[10px] text-zinc-500 font-mono mb-1">NETWORK STATS</div>
        <div className="text-lg font-bold text-white">{nodes.length}</div>
        <div className="text-[10px] text-zinc-500">节点</div>
        <div className="text-sm font-medium text-zinc-300 mt-1">{edges.length}</div>
        <div className="text-[10px] text-zinc-500">连接</div>
      </div>
    </div>
  );
};

// ============ Company Card Component ============
const CompanyCard = ({
  company,
  onClick,
  isSelected,
}: {
  company: Company;
  onClick: () => void;
  isSelected: boolean;
}) => (
  <div
    onClick={onClick}
    className={`p-4 rounded-xl border transition-all cursor-pointer ${
      isSelected
        ? "bg-orange-500/10 border-orange-500/30"
        : "bg-zinc-900/50 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900"
    }`}
  >
    <div className="flex items-start justify-between mb-3">
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            company.health_score > 70
              ? "bg-emerald-500/10"
              : company.health_score > 40
              ? "bg-yellow-500/10"
              : "bg-red-500/10"
          }`}
        >
          <Building2
            className={`w-5 h-5 ${
              company.health_score > 70
                ? "text-emerald-400"
                : company.health_score > 40
                ? "text-yellow-400"
                : "text-red-400"
            }`}
          />
        </div>
        <div>
          <div className="font-medium text-zinc-200">{company.name}</div>
          <div className="text-xs text-zinc-600">{company.domain}</div>
        </div>
      </div>
      <HealthRing score={company.health_score} size={36} />
    </div>

    <div className="flex items-center justify-between">
      <div className="flex items-center gap-4 text-xs text-zinc-500">
        <span className="flex items-center gap-1">
          <Mail size={12} />
          {company.email_count.toLocaleString()}
        </span>
        <span className="flex items-center gap-1">
          <Users size={12} />
          {company.contact_count}
        </span>
      </div>
      <RelationBadge type={company.relation_type} />
    </div>
  </div>
);

// ============ Contact Row Component ============
const ContactRow = ({
  contact,
  onClick,
}: {
  contact: Contact;
  onClick: () => void;
}) => (
  <div
    onClick={onClick}
    className="flex items-center justify-between p-3 rounded-lg hover:bg-zinc-900/50 border border-transparent hover:border-zinc-800 transition-all cursor-pointer"
  >
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-zinc-700 to-zinc-800 flex items-center justify-center text-xs font-medium text-zinc-300">
        {contact.name?.[0] || "?"}
      </div>
      <div>
        <div className="text-sm font-medium text-zinc-200">{contact.name}</div>
        <div className="text-xs text-zinc-600">
          {contact.company_name || contact.domain}
          {contact.job_title && ` · ${contact.job_title}`}
        </div>
      </div>
    </div>
    <div className="flex items-center gap-4">
      <div className="text-xs text-zinc-500 flex items-center gap-3">
        <span className="flex items-center gap-1">
          <Send size={10} className="text-blue-400" />
          {contact.sent_count}
        </span>
        <span className="flex items-center gap-1">
          <Inbox size={10} className="text-emerald-400" />
          {contact.received_count}
        </span>
      </div>
      <TrendIcon type={contact.health_trend} />
      <HealthRing score={contact.health_score} size={28} />
    </div>
  </div>
);

// ============ Main Page Component ============
export default function EmailIntelligencePage() {
  const { user, isAuthenticated, loading: authLoading, genesisCompleted } = useAuth();
  const router = useRouter();

  const [activeView, setActiveView] = useState<"graph" | "companies" | "contacts">("graph");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState<string>("all");

  // Auth check
  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!genesisCompleted) {
      router.push("/calibration");
    }
  }, [isAuthenticated, authLoading, genesisCompleted, router]);

  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, companiesRes, contactsRes] = await Promise.all([
        fetch(`${API_BASE}/api/email-intel/command-center`),
        fetch(`${API_BASE}/api/email-intel/companies?limit=100&sort_by=health`),
        fetch(`${API_BASE}/api/email-intel/relationships?limit=200&sort_by=health`),
      ]);

      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data);
      }
      if (companiesRes.ok) {
        const data = await companiesRes.json();
        setCompanies(data.companies || []);
      }
      if (contactsRes.ok) {
        const data = await contactsRes.json();
        setContacts(data.contacts || []);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated && genesisCompleted) {
      fetchData();
    }
  }, [isAuthenticated, genesisCompleted, fetchData]);

  // Filter companies
  const filteredCompanies = useMemo(() => {
    let result = companies;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(term) ||
          c.domain.toLowerCase().includes(term)
      );
    }
    if (filterType !== "all") {
      result = result.filter((c) => c.relation_type === filterType);
    }
    return result;
  }, [companies, searchTerm, filterType]);

  // Filter contacts
  const filteredContacts = useMemo(() => {
    let result = contacts;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(term) ||
          c.email.toLowerCase().includes(term) ||
          c.domain.toLowerCase().includes(term)
      );
    }
    if (selectedCompany) {
      result = result.filter((c) => c.domain === selectedCompany.domain);
    }
    return result;
  }, [contacts, searchTerm, selectedCompany]);

  const handleNodeClick = (node: GraphNode) => {
    if (node.type === "company") {
      const company = companies.find((c) => c.domain === node.id);
      if (company) {
        setSelectedCompany(company);
        setActiveView("companies");
      }
    }
  };

  if (authLoading) {
    return (
      <div className="h-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border border-orange-500/50 border-t-orange-500 rounded-md animate-spin mx-auto mb-4" />
          <p className="text-zinc-600 text-xs font-mono tracking-wider">LOADING...</p>
        </div>
      </div>
    );
  }

  return (
    <DashboardLayout>
      <div className="h-full flex flex-col bg-[#050505]">
        {/* Header */}
        <div className="flex-shrink-0 border-b border-zinc-800 p-4">
          <div className="max-w-[1800px] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <Network className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Email Intelligence</h1>
                <p className="text-sm text-zinc-500">关系网络 · 健康追踪 · 智能洞察</p>
              </div>
            </div>

            <div className="flex items-center gap-6">
              {/* Quick Stats */}
              {stats && (
                <div className="hidden lg:flex items-center gap-6 mr-6">
                  <div className="text-center">
                    <div className="text-2xl font-light text-white">
                      {stats.total_emails?.toLocaleString() || 0}
                    </div>
                    <div className="text-[10px] text-zinc-600 font-mono">EMAILS</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-light text-white">
                      {stats.total_companies}
                    </div>
                    <div className="text-[10px] text-zinc-600 font-mono">COMPANIES</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-light text-white">
                      {stats.total_contacts}
                    </div>
                    <div className="text-[10px] text-zinc-600 font-mono">CONTACTS</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-light text-emerald-400">
                      {stats.avg_health_score?.toFixed(0) || 0}
                    </div>
                    <div className="text-[10px] text-zinc-600 font-mono">AVG HEALTH</div>
                  </div>
                </div>
              )}

              {/* View Toggle */}
              <div className="flex bg-zinc-900 p-1 rounded-lg border border-zinc-800">
                {[
                  { id: "graph", label: "图谱", icon: Network },
                  { id: "companies", label: "公司", icon: Building2 },
                  { id: "contacts", label: "联系人", icon: Users },
                ].map((view) => {
                  const Icon = view.icon;
                  return (
                    <button
                      key={view.id}
                      onClick={() => setActiveView(view.id as typeof activeView)}
                      className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-all ${
                        activeView === view.id
                          ? "bg-indigo-500/20 text-indigo-400"
                          : "text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      <Icon size={16} />
                      <span className="hidden sm:inline">{view.label}</span>
                    </button>
                  );
                })}
              </div>

              <button
                onClick={fetchData}
                disabled={loading}
                className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-hidden">
          {activeView === "graph" ? (
            <div className="h-full p-4">
              <div className="max-w-[1800px] mx-auto h-full">
                <RelationshipGraph
                  companies={filteredCompanies}
                  contacts={filteredContacts}
                  onNodeClick={handleNodeClick}
                />
              </div>
            </div>
          ) : (
            <div className="h-full flex">
              {/* Left Panel - List */}
              <div className="w-1/2 border-r border-zinc-800 flex flex-col">
                {/* Search & Filter */}
                <div className="p-4 border-b border-zinc-800 space-y-3">
                  <div className="relative">
                    <Search size={16} className="absolute left-3 top-3 text-zinc-500" />
                    <input
                      type="text"
                      placeholder={activeView === "companies" ? "搜索公司..." : "搜索联系人..."}
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-lg py-2.5 pl-10 pr-4 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500/50"
                    />
                  </div>

                  {activeView === "companies" && (
                    <div className="flex gap-2 flex-wrap">
                      {["all", "client", "vendor", "partner", "internal", "unknown"].map((type) => (
                        <button
                          key={type}
                          onClick={() => setFilterType(type)}
                          className={`px-3 py-1 text-xs rounded-full border transition-all ${
                            filterType === type
                              ? "bg-indigo-500/20 border-indigo-500/30 text-indigo-400"
                              : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
                          }`}
                        >
                          {type === "all" ? "全部" : type === "client" ? "客户" : type === "vendor" ? "供应商" : type === "partner" ? "合作伙伴" : type === "internal" ? "内部" : "未分类"}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* List */}
                <div className="flex-1 overflow-auto p-4 space-y-3">
                  {loading ? (
                    <div className="space-y-3">
                      {[1, 2, 3, 4, 5].map((i) => (
                        <div
                          key={i}
                          className="h-24 bg-zinc-900/50 rounded-xl border border-zinc-800 animate-pulse"
                        />
                      ))}
                    </div>
                  ) : activeView === "companies" ? (
                    filteredCompanies.map((company) => (
                      <CompanyCard
                        key={company.domain}
                        company={company}
                        onClick={() => setSelectedCompany(company)}
                        isSelected={selectedCompany?.domain === company.domain}
                      />
                    ))
                  ) : (
                    filteredContacts.map((contact) => (
                      <ContactRow
                        key={contact.email}
                        contact={contact}
                        onClick={() => setSelectedContact(contact)}
                      />
                    ))
                  )}
                </div>
              </div>

              {/* Right Panel - Detail */}
              <div className="w-1/2 flex flex-col">
                {activeView === "companies" && selectedCompany ? (
                  <div className="flex-1 overflow-auto p-6">
                    {/* Company Header */}
                    <div className="flex items-start justify-between mb-6">
                      <div className="flex items-center gap-4">
                        <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-zinc-800 to-zinc-900 flex items-center justify-center border border-zinc-700">
                          <Building2 className="w-8 h-8 text-zinc-400" />
                        </div>
                        <div>
                          <h2 className="text-xl font-bold text-white">{selectedCompany.name}</h2>
                          <p className="text-sm text-zinc-500">{selectedCompany.domain}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <RelationBadge type={selectedCompany.relation_type} />
                            <TrendIcon type={selectedCompany.health_trend} size={16} />
                          </div>
                        </div>
                      </div>
                      <HealthRing score={selectedCompany.health_score} size={64} />
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-3 gap-4 mb-6">
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 text-zinc-500 text-xs mb-2">
                          <Mail size={14} />
                          邮件总数
                        </div>
                        <div className="text-2xl font-light text-white">
                          {selectedCompany.email_count.toLocaleString()}
                        </div>
                      </div>
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 text-zinc-500 text-xs mb-2">
                          <Users size={14} />
                          联系人数
                        </div>
                        <div className="text-2xl font-light text-white">
                          {selectedCompany.contact_count}
                        </div>
                      </div>
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 text-zinc-500 text-xs mb-2">
                          <Activity size={14} />
                          置信度
                        </div>
                        <div className="text-2xl font-light text-white capitalize">
                          {selectedCompany.confidence}
                        </div>
                      </div>
                    </div>

                    {/* Company Contacts */}
                    <div>
                      <h3 className="text-sm font-semibold text-zinc-400 mb-3 flex items-center gap-2">
                        <Users size={14} />
                        关联联系人
                      </h3>
                      <div className="space-y-2">
                        {filteredContacts
                          .filter((c) => c.domain === selectedCompany.domain)
                          .slice(0, 10)
                          .map((contact) => (
                            <ContactRow
                              key={contact.email}
                              contact={contact}
                              onClick={() => setSelectedContact(contact)}
                            />
                          ))}
                      </div>
                    </div>
                  </div>
                ) : activeView === "contacts" && selectedContact ? (
                  <div className="flex-1 overflow-auto p-6">
                    {/* Contact Header */}
                    <div className="flex items-start justify-between mb-6">
                      <div className="flex items-center gap-4">
                        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-zinc-700 to-zinc-800 flex items-center justify-center text-2xl font-light text-white">
                          {selectedContact.name?.[0] || "?"}
                        </div>
                        <div>
                          <h2 className="text-xl font-bold text-white">{selectedContact.name}</h2>
                          <p className="text-sm text-indigo-400">{selectedContact.email}</p>
                          <p className="text-sm text-zinc-500 mt-1">
                            {selectedContact.company_name || selectedContact.domain}
                            {selectedContact.job_title && (
                              <span className="text-zinc-400"> · {selectedContact.job_title}</span>
                            )}
                          </p>
                        </div>
                      </div>
                      <HealthRing score={selectedContact.health_score} size={64} />
                    </div>

                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-4 mb-6">
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 text-blue-400 text-xs mb-2">
                          <Send size={14} />
                          发送
                        </div>
                        <div className="text-2xl font-light text-white">
                          {selectedContact.sent_count}
                        </div>
                      </div>
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 text-emerald-400 text-xs mb-2">
                          <Inbox size={14} />
                          接收
                        </div>
                        <div className="text-2xl font-light text-white">
                          {selectedContact.received_count}
                        </div>
                      </div>
                      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                        <div className="flex items-center gap-2 text-zinc-500 text-xs mb-2">
                          <Activity size={14} />
                          总互动
                        </div>
                        <div className="text-2xl font-light text-white">
                          {selectedContact.total_interactions}
                        </div>
                      </div>
                    </div>

                    {/* Timeline */}
                    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
                      <h3 className="text-sm font-semibold text-zinc-400 mb-4 flex items-center gap-2">
                        <Clock size={14} />
                        互动时间线
                      </h3>
                      <div className="space-y-3">
                        {selectedContact.last_sent && (
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center">
                              <Send size={14} className="text-blue-400" />
                            </div>
                            <div>
                              <div className="text-sm text-zinc-300">最后发送</div>
                              <div className="text-xs text-zinc-600">
                                {new Date(selectedContact.last_sent).toLocaleDateString()}
                              </div>
                            </div>
                          </div>
                        )}
                        {selectedContact.last_received && (
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center">
                              <Inbox size={14} className="text-emerald-400" />
                            </div>
                            <div>
                              <div className="text-sm text-zinc-300">最后接收</div>
                              <div className="text-xs text-zinc-600">
                                {new Date(selectedContact.last_received).toLocaleDateString()}
                              </div>
                            </div>
                          </div>
                        )}
                        {selectedContact.first_contact && (
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-zinc-500/10 flex items-center justify-center">
                              <Clock size={14} className="text-zinc-400" />
                            </div>
                            <div>
                              <div className="text-sm text-zinc-300">首次联系</div>
                              <div className="text-xs text-zinc-600">
                                {new Date(selectedContact.first_contact).toLocaleDateString()}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-zinc-600">
                    <div className="text-center">
                      {activeView === "companies" ? (
                        <>
                          <Building2 size={48} className="mx-auto mb-4 opacity-20" />
                          <p>选择公司查看详情</p>
                        </>
                      ) : (
                        <>
                          <Users size={48} className="mx-auto mb-4 opacity-20" />
                          <p>选择联系人查看详情</p>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
