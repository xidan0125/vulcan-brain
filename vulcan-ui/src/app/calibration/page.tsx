'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { motion, AnimatePresence } from 'framer-motion';
import { Fingerprint, Lock, Brain, Hexagon, ChevronRight, LogOut, SkipForward } from 'lucide-react';
import { useRouter } from 'next/navigation';

// --- Types ---
type Dimension = 'risk_appetite' | 'time_horizon' | 'strategic_drive' | 'people_philosophy' | 'control_style' | 'ethical_boundary';

interface GenomeScores {
  risk_appetite: number;
  time_horizon: number;
  strategic_drive: number;
  people_philosophy: number;
  control_style: number;
  ethical_boundary: number;
}

interface Question {
  id: number;
  dimension: Dimension;
  text: string;
  options: { label: string; value: number; impact_desc: string }[];
}

// --- Data: 6 Dimensions, 3 Questions each ---
const DIMENSIONS: { key: Dimension; label: string; desc: string }[] = [
  { key: 'risk_appetite', label: '风险阈值', desc: '面对未知的勇气与赌性' },
  { key: 'time_horizon', label: '时间视界', desc: '即时满足 vs 延迟享受' },
  { key: 'strategic_drive', label: '战略驱动', desc: '直觉行动 vs 深度谋划' },
  { key: 'people_philosophy', label: '人际哲学', desc: '独狼领袖 vs 群体共生' },
  { key: 'control_style', label: '控制风格', desc: '混沌适应 vs 秩序建立' },
  { key: 'ethical_boundary', label: '伦理边界', desc: '绝对原则 vs 灰度决策' },
];

const QUESTIONS: Question[] = [
  {
    id: 1,
    dimension: "risk_appetite",
    text: "公司现有业务增长稳定但缓慢，您发现一个新兴市场潜力巨大，但进入壁垒高，竞争激烈，且技术尚不成熟。您会选择：",
    options: [
      { label: "谨慎评估，小规模试水，逐步投入，控制风险", value: 40, impact_desc: "稳健保守" },
      { label: "大胆投入，快速抢占市场份额，即使承担短期亏损也在所不惜", value: 80, impact_desc: "激进冒险" }
    ]
  },
  {
    id: 2,
    dimension: "risk_appetite",
    text: "竞争对手推出一款颠覆性产品，对您的核心业务造成威胁。您会选择：",
    options: [
      { label: "加强现有产品的优化和改进，稳固市场份额，密切关注对手动向", value: 30, impact_desc: "防守型" },
      { label: "积极研发类似产品，甚至尝试更激进的创新，直接与对手展开竞争", value: 75, impact_desc: "进攻型" }
    ]
  },
  {
    id: 3,
    dimension: "risk_appetite",
    text: "公司账面有充足现金，但近期市场波动较大。您会选择：",
    options: [
      { label: "保留大部分现金，应对不确定性，等待更明确的投资机会", value: 20, impact_desc: "风险规避" },
      { label: "积极寻找高回报的投资项目，包括并购、新业务拓展等", value: 85, impact_desc: "积极投资" }
    ]
  },
  {
    id: 4,
    dimension: "time_horizon",
    text: "在制定公司未来发展战略时，您更倾向于：",
    options: [
      { label: "关注未来3-5年的发展趋势，制定相对具体的目标和计划", value: 40, impact_desc: "中期规划" },
      { label: "着眼于未来10-20年的长期愿景，即使短期内难以实现", value: 90, impact_desc: "长期愿景" }
    ]
  },
  {
    id: 5,
    dimension: "time_horizon",
    text: "面对一项需要长期投入才能见效的研发项目，您会：",
    options: [
      { label: "设定明确的阶段性目标，定期评估项目进展，确保短期内能看到成果", value: 35, impact_desc: "短期回报" },
      { label: "给予研发团队充分的自由和支持，允许他们进行长期探索", value: 80, impact_desc: "长期探索" }
    ]
  },
  {
    id: 6,
    dimension: "time_horizon",
    text: "在考虑投资回报时，您更看重：",
    options: [
      { label: "短期内的快速回报，尽快收回投资成本", value: 25, impact_desc: "速效主义" },
      { label: "长期稳定的回报，即使短期内收益较低，但未来增长潜力巨大", value: 70, impact_desc: "复利思维" }
    ]
  },
  {
    id: 7,
    dimension: "strategic_drive",
    text: "面对竞争激烈的市场环境，您认为企业最重要的是：",
    options: [
      { label: "保持敏锐的市场洞察力，快速响应客户需求，不断优化产品和服务", value: 45, impact_desc: "市场导向" },
      { label: "拥有独特的竞争优势，建立强大的品牌影响力，引领行业发展趋势", value: 90, impact_desc: "引领行业" }
    ]
  },
  {
    id: 8,
    dimension: "strategic_drive",
    text: "在制定企业发展战略时，您更倾向于：",
    options: [
      { label: "基于现有业务和优势，进行稳健的扩张和延伸", value: 35, impact_desc: "稳健扩张" },
      { label: "积极探索新的业务领域，即使与现有业务关联不大，也要寻求突破", value: 85, impact_desc: "多元化" }
    ]
  },
  {
    id: 9,
    dimension: "strategic_drive",
    text: "您认为企业成功的关键在于：",
    options: [
      { label: "不断提升运营效率，降低成本，提高盈利能力", value: 40, impact_desc: "效率至上" },
      { label: "持续创新，开发新产品和新服务，满足客户不断变化的需求", value: 80, impact_desc: "创新驱动" }
    ]
  },
  {
    id: 10,
    dimension: "people_philosophy",
    text: "在团队管理中，您更注重：",
    options: [
      { label: "建立明确的规章制度，严格执行，确保团队高效运作", value: 30, impact_desc: "制度管理" },
      { label: "营造积极的团队氛围，鼓励员工自主性和创造性", value: 75, impact_desc: "人性管理" }
    ]
  },
  {
    id: 11,
    dimension: "people_philosophy",
    text: "面对员工的错误，您更倾向于：",
    options: [
      { label: "严肃批评，指出错误，并要求其承担责任", value: 25, impact_desc: "严厉追责" },
      { label: "了解错误原因，帮助员工分析问题，使其从中学习和成长", value: 80, impact_desc: "积极引导" }
    ]
  },
  {
    id: 12,
    dimension: "people_philosophy",
    text: "在人才选拔方面，您更看重：",
    options: [
      { label: "候选人的专业技能和经验，确保其能胜任工作", value: 40, impact_desc: "能力导向" },
      { label: "候选人的价值观和潜力，确保其与企业文化相符", value: 85, impact_desc: "潜力导向" }
    ]
  },
  {
    id: 13,
    dimension: "control_style",
    text: "在项目管理中，您更倾向于：",
    options: [
      { label: "制定详细的项目计划，严格监控项目进度，确保项目按计划完成", value: 80, impact_desc: "强管控" },
      { label: "给予项目团队充分的自主权，鼓励他们灵活应对变化", value: 30, impact_desc: "弱管控" }
    ]
  },
  {
    id: 14,
    dimension: "control_style",
    text: "在决策过程中，您更喜欢：",
    options: [
      { label: "收集尽可能多的信息，进行详细的分析和评估", value: 75, impact_desc: "数据驱动" },
      { label: "依靠直觉和经验，快速做出决策，抓住市场机会", value: 35, impact_desc: "直觉驱动" }
    ]
  },
  {
    id: 15,
    dimension: "control_style",
    text: "对于员工的日常工作，您更倾向于：",
    options: [
      { label: "设定明确的目标和指标，定期评估员工的工作表现", value: 80, impact_desc: "绩效管理" },
      { label: "给予员工充分的信任和自主权，让他们自由安排工作", value: 35, impact_desc: "信任授权" }
    ]
  },
  {
    id: 16,
    dimension: "ethical_boundary",
    text: "为了获得一个重要的商业合同，您得知竞争对手存在一些违规行为，您会：",
    options: [
      { label: "坚守商业道德，不利用竞争对手的违规行为，通过自身实力赢得合同", value: 15, impact_desc: "坚守道德" },
      { label: "权衡利弊，如果利用对手的违规行为能确保获得合同，可能会考虑", value: 75, impact_desc: "利益优先" }
    ]
  },
  {
    id: 17,
    dimension: "ethical_boundary",
    text: "在公司经营过程中，您发现一个潜在的漏洞可以帮助公司规避一些税收，您会：",
    options: [
      { label: "严格遵守法律法规，依法纳税，维护企业良好的社会形象", value: 10, impact_desc: "严守法规" },
      { label: "咨询专业人士，在法律允许的范围内，尽可能降低税收负担", value: 60, impact_desc: "合理避税" }
    ]
  },
  {
    id: 18,
    dimension: "ethical_boundary",
    text: "如果您的个人利益与公司利益发生冲突，您会：",
    options: [
      { label: "优先考虑公司利益，维护公司的整体利益", value: 20, impact_desc: "公司优先" },
      { label: "在不损害公司利益的前提下，尽可能维护自己的合法权益", value: 55, impact_desc: "平衡利益" }
    ]
  },
  {
    id: 19,
    dimension: "ethical_boundary",
    text: "您发现一位核心员工存在一些道德问题，但其能力非常突出，对公司贡献巨大，您会：",
    options: [
      { label: "严肃处理，即使可能损失这位员工，也要维护公司的道德底线", value: 15, impact_desc: "道德至上" },
      { label: "给予警告，并进行引导和教育，希望其能改正错误", value: 70, impact_desc: "给予机会" }
    ]
  },
  {
    id: 20,
    dimension: "strategic_drive",
    text: "在制定长期战略时，您更看重：",
    options: [
      { label: "确保公司在现有市场中的领导地位，并不断提升市场份额", value: 40, impact_desc: "深耕市场" },
      { label: "探索全新的商业模式和市场机会，即使面临较高的风险和不确定性", value: 85, impact_desc: "探索突破" }
    ]
  }
];

// --- Audio Manager ---
const useAudio = () => {
  const audioRef = useRef<{ [key: string]: HTMLAudioElement }>({});
  const bgmRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      audioRef.current = {
        hover: new Audio('/sounds/hover.mp3'),
        select: new Audio('/sounds/select.mp3'),
        lock: new Audio('/sounds/lock.mp3'),
        boot: new Audio('/sounds/boot.mp3'),
        birth: new Audio('/sounds/birth.mp3'),
      };
      bgmRef.current = new Audio('/sounds/bgm.mp3');
      if (bgmRef.current) {
        bgmRef.current.loop = true;
        bgmRef.current.volume = 0.3;
      }
    }
  }, []);

  const playSfx = (type: 'hover' | 'select' | 'lock' | 'boot' | 'birth') => {
    const audio = audioRef.current[type];
    if (audio) {
      audio.currentTime = 0;
      audio.play().catch(() => {});
    }
  };

  const playBgm = () => { bgmRef.current?.play().catch(() => {}); };
  const stopBgm = () => { if (bgmRef.current) { bgmRef.current.pause(); bgmRef.current.currentTime = 0; } };

  return { playSfx, playBgm, stopBgm };
};

// --- Background ---
const Background = () => (
  <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none bg-zinc-950">
    <div className="absolute inset-0 opacity-20 brightness-100 contrast-150 mix-blend-overlay" style={{backgroundImage: "url('data:image/svg+xml,%3Csvg viewBox=\"0 0 400 400\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cfilter id=\"noiseFilter\"%3E%3CfeTurbulence type=\"fractalNoise\" baseFrequency=\"0.9\" numOctaves=\"3\" stitchTiles=\"stitch\"/%3E%3C/filter%3E%3Crect width=\"100%25\" height=\"100%25\" filter=\"url(%23noiseFilter)\"/%3E%3C/svg%3E')"}}></div>
    <div className="absolute top-[-50%] left-[-50%] w-[200%] h-[200%] bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-orange-900/20 via-zinc-950/50 to-zinc-950 animate-pulse"></div>
    <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:50px_50px]" />
  </div>
);

// --- Awakening Stage ---
const Awakening = ({ onComplete, onSkip, onLogout }: { onComplete: () => void; onSkip: () => void; onLogout: () => void }) => {
  const [text, setText] = useState("INITIALIZING...");
  const { playSfx, playBgm } = useAudio();
  const [started, setStarted] = useState(false);

  const startGenesis = () => {
    setStarted(true);
    playSfx('boot');
    playBgm();

    const sequence = ["ESTABLISHING NEURAL LINK...", "CALIBRATING SENSORS...", "SYNCHRONIZING SOUL SIGNATURE...", "GENESIS PROTOCOL READY."];
    let idx = 0;

    const run = () => {
      if (idx >= sequence.length) { setTimeout(onComplete, 800); return; }
      setText(sequence[idx]);
      setTimeout(() => { idx++; run(); }, 1000);
    };
    run();
  };

  if (!started) {
    return (
      <div className="flex flex-col items-center justify-center h-screen z-10 relative">
        {/* 右上角操作按钮 */}
        <div className="absolute top-6 right-6 flex gap-3">
          <motion.button
            onClick={onSkip}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="flex items-center gap-2 px-4 py-2 text-zinc-400 hover:text-white border border-zinc-700 hover:border-zinc-500 rounded-lg transition-all text-sm"
          >
            <SkipForward size={16} />
            稍后再说
          </motion.button>
          <motion.button
            onClick={onLogout}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="flex items-center gap-2 px-4 py-2 text-zinc-400 hover:text-red-400 border border-zinc-700 hover:border-red-500/50 rounded-lg transition-all text-sm"
          >
            <LogOut size={16} />
            退出登录
          </motion.button>
        </div>

        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="text-center">
          <Fingerprint size={80} className="text-orange-500 mx-auto mb-8 animate-pulse" />
          <h1 className="text-4xl font-bold text-white mb-4">PREFERENCE ALIGNMENT</h1>
          <p className="text-zinc-400 mb-8 max-w-md">校准你的决策偏好，训练专属于你的AI大脑</p>
          <motion.button onClick={startGenesis} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            className="px-8 py-4 bg-orange-500 text-white font-bold rounded-lg hover:bg-orange-600 transition-colors shadow-[0_0_30px_rgba(249,115,22,0.5)]">
            开始校准
          </motion.button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen z-10 relative">
      <motion.div key={text} initial={{ opacity: 0, filter: 'blur(10px)' }} animate={{ opacity: 1, filter: 'blur(0px)' }}
        className="text-orange-500 font-mono text-xl tracking-[0.2em]">{text}</motion.div>
      <motion.div initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 4.5, ease: "circOut" }}
        className="h-0.5 w-64 bg-orange-500 mt-4 shadow-[0_0_15px_rgba(249,115,22,0.8)]" />
    </div>
  );
};

// --- Radar Chart ---
const RadarChart = ({ scores }: { scores: GenomeScores }) => {
  const size = 300, center = size / 2, radius = size / 2 - 40;

  const points = DIMENSIONS.map((dim, i) => {
    const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2;
    const value = scores[dim.key] || 50;
    const r = (value / 100) * radius;
    return {
      x: center + r * Math.cos(angle), y: center + r * Math.sin(angle),
      labelX: center + (radius + 30) * Math.cos(angle), labelY: center + (radius + 30) * Math.sin(angle),
      label: dim.label
    };
  });

  const pathData = points.map((p, i) => (i === 0 ? `M ${p.x},${p.y}` : `L ${p.x},${p.y}`)).join(' ') + " Z";

  return (
    <div className="relative flex items-center justify-center">
      <svg width={size} height={size} className="overflow-visible">
        {[0.2, 0.4, 0.6, 0.8, 1].map((scale) => (
          <motion.polygon key={scale}
            points={DIMENSIONS.map((_, i) => {
              const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2;
              const r = radius * scale;
              return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`;
            }).join(' ')}
            fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="1"
            initial={{ opacity: 0, scale: 0 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.5 + scale * 0.5 }} />
        ))}
        {DIMENSIONS.map((_, i) => {
          const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2;
          return <line key={i} x1={center} y1={center} x2={center + radius * Math.cos(angle)} y2={center + radius * Math.sin(angle)} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />;
        })}
        <motion.path d={pathData} fill="rgba(249, 115, 22, 0.2)" stroke="#f97316" strokeWidth="2"
          initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 2, ease: "easeInOut", delay: 1 }}
          style={{ filter: "drop-shadow(0 0 10px rgba(249,115,22,0.5))" }} />
        {points.map((p, i) => (
          <motion.circle key={i} cx={p.x} cy={p.y} r="5" fill="#f97316" stroke="#fff" strokeWidth="2"
            initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 2 + i * 0.1 }} />
        ))}
      </svg>
      {points.map((p, i) => (
        <motion.div key={i} className="absolute text-xs text-zinc-400 font-mono tracking-wider whitespace-nowrap"
          style={{ left: p.labelX, top: p.labelY, transform: 'translate(-50%, -50%)' }}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 2.5 }}>
          {p.label}
        </motion.div>
      ))}
    </div>
  );
};

// --- Main Page ---
export default function GenesisPage() {
  const [stage, setStage] = useState<'awakening' | 'questions' | 'birth' | 'interpretation'>('awakening');
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [scores, setScores] = useState<GenomeScores>({
    risk_appetite: 50, time_horizon: 50, strategic_drive: 50,
    people_philosophy: 50, control_style: 50, ethical_boundary: 50
  });
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [isDimensionTransition, setIsDimensionTransition] = useState(false);
  const [analysisText, setAnalysisText] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const { playSfx } = useAudio();
  const { refreshCalibrationStatus, logout } = useAuth();
  const router = useRouter();

  // 跳过校准，直接进入系统（使用默认值）
  const handleSkip = async () => {
    try {
      // 保存默认的校准数据
      const token = localStorage.getItem('vulcan_token');
      await fetch('/api/soul/genesis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          genome: scores,  // 默认值
          questions_answered: 0,
          version: '2.0',
          skipped: true
        })
      });
      localStorage.setItem('vulcan_genesis_complete', 'true');
      await refreshCalibrationStatus();
      router.push('/');
    } catch (e) {
      console.error('Failed to skip calibration:', e);
      // 即使失败也允许进入
      localStorage.setItem('vulcan_genesis_complete', 'true');
      router.push('/');
    }
  };

  // 退出登录
  const handleLogout = () => {
    logout();
  };

  const currentQuestion = QUESTIONS[currentQIndex];
  const currentDimension = DIMENSIONS.find(d => d.key === currentQuestion?.dimension);
  const progress = (currentQIndex / QUESTIONS.length) * 100;

  const handleAnswer = async (value: number) => {
    playSfx('select');
    setScores(prev => ({ ...prev, [currentQuestion.dimension]: Math.round((prev[currentQuestion.dimension] + value) / 2) }));
    setAnswers(prev => ({ ...prev, [currentQuestion.id]: value }));

    const nextQ = QUESTIONS[currentQIndex + 1];
    if (nextQ && nextQ.dimension !== currentQuestion.dimension) {
      playSfx('lock');
      setIsDimensionTransition(true);
      setTimeout(() => { setIsDimensionTransition(false); setCurrentQIndex(prev => prev + 1); }, 2500);
    } else if (nextQ) {
      setTimeout(() => setCurrentQIndex(prev => prev + 1), 400);
    } else {
      finishGenesis();
    }
  };

  const finishGenesis = async () => {
    setStage('birth');
    playSfx('birth');
    try {
      const token = localStorage.getItem('vulcan_token');
      await fetch('/api/soul/genesis', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ genome: scores, questions_answered: Object.keys(answers).length, version: '2.0' })
      });
    localStorage.setItem('vulcan_genesis_complete', 'true');
      await refreshCalibrationStatus();
    } catch (e) { console.error('Failed to save genome:', e); }
    setTimeout(() => generateAIAnalysis(), 3500);
  };

  const generateAIAnalysis = async () => {
    setIsAnalyzing(true);
    const prompt = `你是一个神秘的灵魂分析师。根据以下用户的六维度数据，生成一段精准、有洞察力、带有叙事感的个性化分析。

数据：风险阈值:${scores.risk_appetite}/100, 时间视界:${scores.time_horizon}/100, 战略驱动:${scores.strategic_drive}/100, 人际哲学:${scores.people_philosophy}/100, 控制风格:${scores.control_style}/100, 伦理边界:${scores.ethical_boundary}/100

要求：1.用第二人称"你"描述 2.有洞察和隐喻 3.提到一个相似的历史名人或角色 4.揭示一个用户可能没意识到的深层特质 5.200-300字 6.语气神秘但温暖`;

    try {
      const response = await fetch('/api/ai/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'user', content: prompt }], model: 'deepseek' })
      });
      const data = await response.json();
      const analysis = data.response || data.content || '灵魂解析完成。你的数据独一无二。';
      setStage('interpretation');
      let i = 0;
      const interval = setInterval(() => {
        setAnalysisText(analysis.slice(0, i)); i++;
        if (i > analysis.length) { clearInterval(interval); setIsAnalyzing(false); }
      }, 40);
    } catch (e) {
      console.error('AI analysis failed:', e);
      setStage('interpretation');
      setAnalysisText('灵魂解析完成。你的基因组数据已被永久记录。');
      setIsAnalyzing(false);
    }
  };

  return (
    <main className="min-h-screen w-full bg-zinc-950 text-zinc-100 font-sans selection:bg-orange-500/30 overflow-hidden relative">
      <Background />

      {stage === 'awakening' && <Awakening onComplete={() => setStage('questions')} onSkip={handleSkip} onLogout={handleLogout} />}

      {stage === 'questions' && (
        <div className="relative z-10 w-full h-screen flex flex-col items-center justify-center p-6">
          {/* 右上角退出按钮 */}
          <div className="absolute top-6 right-6 flex gap-3 z-40">
            <motion.button
              onClick={handleSkip}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 px-3 py-1.5 text-zinc-500 hover:text-white border border-zinc-800 hover:border-zinc-600 rounded-lg transition-all text-xs"
            >
              <SkipForward size={14} />
              跳过
            </motion.button>
            <motion.button
              onClick={handleLogout}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 px-3 py-1.5 text-zinc-500 hover:text-red-400 border border-zinc-800 hover:border-red-500/50 rounded-lg transition-all text-xs"
            >
              <LogOut size={14} />
              退出
            </motion.button>
          </div>

          <AnimatePresence>
            {isDimensionTransition && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="absolute inset-0 z-50 bg-zinc-950/90 backdrop-blur-md flex flex-col items-center justify-center">
                <motion.div initial={{ scale: 0, rotate: -180 }} animate={{ scale: 1, rotate: 0 }}
                  transition={{ type: "spring", stiffness: 100 }} className="mb-8 relative">
                  <Hexagon size={80} className="text-orange-500 stroke-1" />
                  <Lock size={30} className="text-white absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                </motion.div>
                <h2 className="text-3xl font-bold tracking-widest text-orange-500 uppercase">{currentDimension?.label} LOCKED</h2>
                <p className="text-zinc-400 mt-2 font-mono">DATA CRYSTALLIZED</p>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="absolute top-10 w-full max-w-2xl px-6">
            <div className="flex justify-between text-xs font-mono text-zinc-500 mb-2">
              <span>SEQUENCE: {currentQIndex + 1} / {QUESTIONS.length}</span>
              <span>DIMENSION: {currentDimension?.label}</span>
            </div>
            <div className="h-1 w-full bg-zinc-900 rounded-full overflow-hidden">
              <motion.div className="h-full bg-orange-600 shadow-[0_0_10px_rgba(234,88,12,0.8)]"
                initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ duration: 0.5 }} />
            </div>
          </div>

          <AnimatePresence mode="wait">
            <motion.div key={currentQuestion.id}
              initial={{ opacity: 0, y: 50, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -50, scale: 1.05 }} transition={{ duration: 0.4, ease: "easeOut" }}
              className="w-full max-w-2xl">
              <div className="mb-12 text-center space-y-4">
                <motion.span className="inline-block px-3 py-1 rounded-full border border-orange-500/30 bg-orange-500/5 text-orange-400 text-xs font-mono tracking-wider"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
                  // {currentDimension?.desc}
                </motion.span>
                <h2 className="text-2xl md:text-3xl font-light leading-relaxed">{currentQuestion.text}</h2>
              </div>

              <div className="grid gap-4">
                {currentQuestion.options.map((opt, idx) => (
                  <motion.button key={idx} onClick={() => handleAnswer(opt.value)}
                    initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 + idx * 0.1 }}
                    whileHover={{ scale: 1.02, backgroundColor: "rgba(249, 115, 22, 0.1)", borderColor: "rgba(249, 115, 22, 0.5)" }}
                    whileTap={{ scale: 0.98 }}
                    className="group relative w-full p-5 text-left border border-zinc-800 bg-zinc-900/50 backdrop-blur-sm rounded-xl transition-all duration-300 hover:shadow-[0_0_20px_rgba(249,115,22,0.15)]">
                    <div className="flex items-center justify-between">
                      <span className="text-base text-zinc-300 group-hover:text-white transition-colors">{opt.label}</span>
                      <ChevronRight className="opacity-0 group-hover:opacity-100 text-orange-500 transition-all -translate-x-4 group-hover:translate-x-0" />
                    </div>
                    <div className="absolute bottom-0 left-0 h-[2px] bg-orange-500 w-0 group-hover:w-full transition-all duration-500 ease-out" />
                  </motion.button>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      )}


      {stage === 'birth' && (
        <div className="flex flex-col items-center justify-center h-screen z-10 relative">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-12 text-center">
            <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-b from-white to-zinc-500 mb-2">GENESIS COMPLETE</h1>
            <p className="text-orange-500 font-mono text-sm tracking-[0.3em] animate-pulse">ANALYZING SOUL MATRIX...</p>
          </motion.div>
          <div className="scale-125 transform"><RadarChart scores={scores} /></div>
        </div>
      )}

      {stage === 'interpretation' && (
        <div className="relative z-10 w-full min-h-screen flex flex-col md:flex-row items-center justify-center p-8 gap-12 max-w-7xl mx-auto">
          <motion.div initial={{ opacity: 0, x: -50 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 1 }}
            className="flex-1 flex flex-col items-center">
            <div className="relative">
              <div className="absolute inset-0 bg-orange-500/20 blur-[50px] rounded-full" />
              <RadarChart scores={scores} />
            </div>
            <div className="mt-8 grid grid-cols-2 gap-3 w-full max-w-sm">
              {DIMENSIONS.map((dim) => (
                <div key={dim.key} className="bg-zinc-900/50 border border-zinc-800 p-3 rounded-lg">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs text-zinc-500">{dim.label}</span>
                    <span className="text-xs text-orange-400 font-mono">{scores[dim.key]}</span>
                  </div>
                  <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
                    <motion.div className="h-full bg-orange-500" initial={{ width: 0 }}
                      animate={{ width: `${scores[dim.key]}%` }} transition={{ duration: 1, delay: 0.5 }} />
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 50 }} animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 1, delay: 0.5 }} className="flex-1 max-w-xl">
            <div className="flex items-center gap-3 mb-6 text-orange-500">
              <Brain size={24} />
              <span className="font-mono text-sm tracking-widest">SOUL INTERPRETATION</span>
            </div>
            <div className="min-h-[200px] text-lg leading-relaxed text-zinc-200 font-light border-l-2 border-orange-500/30 pl-6 relative">
              {analysisText}
              {isAnalyzing && (
                <motion.span animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 0.8 }}
                  className="inline-block w-2 h-5 bg-orange-500 ml-1 align-middle" />
              )}
            </div>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: isAnalyzing ? 0 : 1 }} transition={{ delay: 1 }} className="mt-12 flex gap-4">
              <a href="/" className="px-8 py-3 bg-orange-500 text-white font-bold rounded-lg hover:bg-orange-600 transition-colors flex items-center gap-2 shadow-[0_0_20px_rgba(249,115,22,0.3)]">
                进入系统 <ChevronRight size={18} />
              </a>
            </motion.div>
          </motion.div>
        </div>
      )}
    </main>
  );
}
