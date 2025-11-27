export interface GenesisQuestion {
  id: number;
  category: string;
  scenario: string;
  optionA: { label: string; value: string };
  optionB: { label: string; value: string };
}

export const GENESIS_QUESTIONS: GenesisQuestion[] = [
  // 第一章：战略野心与风险 (Strategy & Risk)
  {
    id: 1,
    category: "Strategy",
    scenario: "公司账上现金够活 12 个月。现在有一个新业务机会，投入后有 50% 概率让公司翻 10 倍，也有 50% 概率让现金流断裂直接倒闭。",
    optionA: { label: "赌！(Bet)", value: "risk_seeking" },
    optionB: { label: "不赌 (Safe)", value: "risk_averse" }
  },
  {
    id: 2,
    category: "Strategy",
    scenario: "竞品下周就要发布同类产品了。我们的产品核心功能好了，但 UI 还有瑕疵，Bug 率 5%。",
    optionA: { label: "带病抢先上线", value: "speed_first" },
    optionB: { label: "延迟打磨完美", value: "quality_first" }
  },
  {
    id: 3,
    category: "Strategy",
    scenario: "一个大客户占了我们 60% 的营收，但他要求极度苛刻的定制化，会拖慢我们要做的标准化 SaaS 平台。",
    optionA: { label: "跪舔大客户", value: "short_term_survival" },
    optionB: { label: "拒绝为平台梦", value: "long_term_vision" }
  },
  {
    id: 4,
    category: "Strategy",
    scenario: "发现现在的核心业务 3 年后会死。转型需要把现在赚利润的销售团队裁掉一半，换成研发。",
    optionA: { label: "现在就动刀", value: "proactive_change" },
    optionB: { label: "再榨两年利润", value: "delayed_change" }
  },
  {
    id: 5,
    category: "Strategy",
    scenario: "投资人给了一笔巨款，要求 3 年上市，签了苛刻的对赌协议（输了赔身家）。",
    optionA: { label: "拿钱加速", value: "aggressive_growth" },
    optionB: { label: "不拿慢慢发展", value: "organic_growth" }
  },
  // 第二章：人才与管理 (People & Management)
  {
    id: 6,
    category: "People",
    scenario: "公司的技术大拿（Top 1%），一个人顶半个团队，但性格极差，经常霸凌同事，破坏团队氛围。",
    optionA: { label: "容忍特权", value: "talent_over_culture" },
    optionB: { label: "为文化开除", value: "culture_over_talent" }
  },
  {
    id: 7,
    category: "People",
    scenario: "跟你创业 5 年的老兄弟，能力已经跟不上公司现在的 B 轮阶段了，成了瓶颈。",
    optionA: { label: "养着给闲职", value: "loyalty_first" },
    optionB: { label: "让他走人", value: "performance_first" }
  },
  {
    id: 8,
    category: "People",
    scenario: "公司规定严禁远程办公。你极其想挖的一个大神只接受远程。",
    optionA: { label: "为他破例", value: "flexible_rules" },
    optionB: { label: "坚守制度", value: "strict_rules" }
  },
  {
    id: 9,
    category: "People",
    scenario: "现在的团队氛围有点温吞。你倾向于引入每年强制淘汰 10%的机制来激活狼性吗？",
    optionA: { label: "引入淘汰制", value: "wolf_culture" },
    optionB: { label: "温和辅导", value: "nurturing_culture" }
  },
  {
    id: 10,
    category: "People",
    scenario: "基层员工绕过总监直接向你汇报了一个好点子，同时也告了总监一状。",
    optionA: { label: "鼓励直达天听", value: "flat_hierarchy" },
    optionB: { label: "维护管理层级", value: "strict_hierarchy" }
  },
  // 第三章：底线与灰度 (Ethics & Gray Areas)
  {
    id: 11,
    category: "Ethics",
    scenario: "我们的销售搞到了竞品未发布的内部核心数据（非法途径）。",
    optionA: { label: "看并用它", value: "pragmatic" },
    optionB: { label: "销毁严查", value: "principled" }
  },
  {
    id: 12,
    category: "Ethics",
    scenario: "夸大一点产品功能（吹牛）就能拿下这个救命的单子，如果不吹就大概率丢单。客户很难验证。",
    optionA: { label: "撒这句谎", value: "result_oriented" },
    optionB: { label: "坚持诚实", value: "integrity_first" }
  },
  {
    id: 13,
    category: "Ethics",
    scenario: "有个机会能把用户隐私数据卖给第三方（脱敏后），能换回巨大的现金流，且法律界定模糊。",
    optionA: { label: "做", value: "profit_driven" },
    optionB: { label: "不做", value: "privacy_first" }
  },
  {
    id: 14,
    category: "Ethics",
    scenario: "公司出了负面新闻，但其实是被冤枉的。公关建议买水军刷好评压下去，成本低见效快。",
    optionA: { label: "用黑公关反击", value: "aggressive_pr" },
    optionB: { label: "清者自清", value: "transparent_pr" }
  },
  {
    id: 15,
    category: "Ethics",
    scenario: "有个业务在海外很火，在国内处于监管灰色地带（没说准也没说不准）。",
    optionA: { label: "先干了再说", value: "move_fast" },
    optionB: { label: "等政策明朗", value: "wait_and_see" }
  },
  // 第四章：沟通与控制 (Communication & Control)
  {
    id: 16,
    category: "Control",
    scenario: "项目搞砸了。你希望下属向你汇报时...",
    optionA: { label: "先讲原因和补救", value: "soft_report" },
    optionB: { label: "直接说亏了多少", value: "data_first_report" }
  },
  {
    id: 17,
    category: "Control",
    scenario: "你交给副手一个重要项目。你的管理风格是...",
    optionA: { label: "每天早会纠正细节", value: "micromanagement" },
    optionB: { label: "两周后看结果", value: "result_management" }
  },
  {
    id: 18,
    category: "Control",
    scenario: "公司现金流只够 2 个月了。",
    optionA: { label: "实话实说告诉全员", value: "full_transparency" },
    optionB: { label: "报喜不报忧自己扛", value: "selective_transparency" }
  },
  {
    id: 19,
    category: "Control",
    scenario: "在会上，你刚拍板一个决定，下属当众激烈反对你，且有点不给面子。",
    optionA: { label: "有种敢说真话", value: "welcome_dissent" },
    optionB: { label: "不懂规矩挑战权威", value: "respect_authority" }
  },
  {
    id: 20,
    category: "Control",
    scenario: "你希望这个 AI 助手在给建议时...",
    optionA: { label: "给上中下三策让我选", value: "options_style" },
    optionB: { label: "直接给最优解", value: "directive_style" }
  }
];
