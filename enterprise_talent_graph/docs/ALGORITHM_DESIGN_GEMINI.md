# **企业人才图谱系统算法体系设计咨询报告：基于网络科学与大语言模型的深度洞察**

**摘要**

在数字化转型的深水区，企业组织形态正从静态的科层制向动态的网络化结构演变。传统的组织架构图（Org Chart）已无法捕捉真实的工作流向与权力结构。本报告响应贵公司构建“企业人才图谱系统”的战略需求，提出了一套融合**复杂网络理论（Complex Network Theory）**、**自然语言处理（NLP/LLM）与预测性行为分析**的综合算法体系。

本方案不仅仅是一个数据可视化项目，更是一个基于 Python 生态的、模块化可插拔的**组织智能（Organizational Intelligence）引擎**。针对职能覆盖、关键依赖、协作健康、外部关系及风险预警五大核心命题，我们设计了从底层图构建到顶层风险预测的全链路算法。特别地，本报告引入了 Google 与 Enron 数据集验证过的交互加权模型，结合罗纳德·伯特（Ronald Burt）的结构洞理论与最新的大语言模型（LLM）语义推理能力，旨在从海量邮件数据中提炼出关于人才分布、隐形权力与组织熵增的深层洞察。

本报告共分八章，详细阐述了数据工程架构、网络拓扑算法、语义职能映射、生态风险量化及动态预警模型的数学原理与工程实现，力求为贵公司打造一个具备自我感知与进化能力的组织数字孪生系统。

## ---

**第一章 项目背景与技术哲学**

### **1.1 从静态管理到动态图谱**

在传统的企业管理中，人力资源部门依赖于职位描述（JD）和汇报关系来理解组织。然而，\*\*组织网络分析（Organizational Network Analysis, ONA）\*\*的研究表明，实际完成工作的网络（Informal Network）往往与设计好的组织架构大相径庭 1。邮件作为企业最核心的沟通载体，其元数据（Metadata）与内容（Content）蕴含了组织运行的真实基因。

本项目的核心目标是构建一个**动态图谱（Dynamic Graph）**。这要求我们的算法体系不能仅处理静态快照，而必须具备处理时序数据流的能力，捕捉关系强度的衰减与转移。

### **1.2 系统设计哲学：可插拔与模块化**

针对“可插拔算法体系”的需求，我们在设计上遵循**管道（Pipeline）模式**与**策略（Strategy）模式**。系统被解耦为三个核心层次：

1. **图构建层（Graph Construction Layer）**：负责将原始日志转化为加权有向图，处理节点实体对齐与边权重计算。  
2. **算法分析层（Analytical Core Layer）**：包含拓扑、语义、社群、风险等独立的分析器（Analyzer），每个分析器均可独立插拔、升级或替换。  
3. **应用交付层（Delivery Layer）**：负责将高维向量与图指标转化为业务可读的仪表盘与预警信号。

技术栈选型上，我们以 **Python** 为核心，利用 **NetworkX** 处理中等规模图计算（或 igraph 处理大规模图），**Hugging Face Transformers / OpenAI API** 处理语义理解，**Pandas** 处理时序特征，形成了一套工业级的分析闭环。

## ---

**第二章 数据基石：图模型构建与加权策略**

在进入高阶分析之前，构建一个能够精确反映现实交互强度的图模型是至关重要的。简单地将一次邮件发送视为一条边（Edge）会丢失大量信息。我们需要一个精细化的加权模型来量化“关注力”的稀缺性。

### **2.1 节点（Vertex）与边（Edge）的定义**

#### **2.1.1 节点实体解析**

在图 $G=(V, E)$ 中，节点 $V$ 代表员工。

* **挑战**：同一员工可能拥有多个别名（如 jdoe@company.com, john.doe@company.com）。  
* **解决方案**：在数据摄取阶段实施**实体解析（Entity Resolution）**。建立全局映射表（Global Mapping Table），将所有变体归一化为唯一的 Employee\_UUID。此外，考虑到隐私合规（GDPR/PII），建议在算法层使用 Hash ID 进行计算，仅在最终报告层通过权限控制还原为实名 3。

#### **2.1.2 有向边的构建**

邮件本质上是有向的。$E\_{ij}$ 表示员工 $i$ 向员工 $j$ 发送信息。有向图（Directed Graph）是必须的，因为“请求”与“响应”代表了不同的权力动态。

### **2.2 交互强度加权模型 (Interaction Weighting Model)**

如何量化一封邮件的权重？基于 Google 的 Friend Suggest 算法研究 4 以及 Enron 数据集的学术成果 6，我们提出一套**注意力稀释模型（Attention Dilution Model）**。

#### **2.2.1 接收类型权重 ($w\_{type}$)**

人类的注意力是有限资源。当一封邮件发送给的人越多，单个人感受到的“社交压力”与“关注度”就越低。

* To（直接接收）：代表明确的沟通意图与行动期望。  
  设定基础权重 $W\_{to} \= 1.0$。若收件栏有 $N\_{to}$ 人，考虑到旁观者效应（Bystander Effect），单边的权重可轻微衰减，但通常为了简化计算，在 $N\_{to}$ 较小时（如\<5）可保持为 1。  
* Cc（抄送）：代表信息同步，属于弱连接。  
  根据 Enron 数据集的研究 6，抄送关系的强度显著低于直发，且随着抄送人数呈平方根级衰减。我们建议采用以下公式：

  $$w\_{cc} \= \\frac{\\alpha}{\\sqrt{1 \+ N\_{cc}}}$$

  其中 $\\alpha$ 为降权系数（建议取 0.5），$N\_{cc}$ 为抄送总人数。这反映了“抄送全员”的邮件对个体而言，社交连接意义极弱。  
* Bcc（密送）：代表隐形监控或单向获取。  
  在常规协作分析中，建议剔除 Bcc 数据（权重=0），因为其不代表显性的双向协作关系，且涉及极高的隐私敏感度 7。仅在特定的“合规风险审计”模式下，才激活 Bcc 边的计算。

#### **2.2.2 互惠性增益 (Reciprocity Boost)**

单向的邮件轰炸不是协作，双向的往来才是。在构建图时，如果 $E\_{ij}$ 和 $E\_{ji}$ 同时存在且频率均高于阈值，我们应对双方的边权重给予 **1.5倍** 的互惠增益。这符合社会交换理论，即互惠关系包含更强的信任与依赖 9。

### **2.3 时间动力学：指数衰减与记忆半衰期**

组织结构是流动的。三个月前的频繁交互如果现在停止了，其对当前业务的影响力应当微乎其微。静态累加的图谱会形成“僵尸连接”。

#### **2.3.1 指数衰减函数 (Exponential Decay)**

我们引入物理学中的半衰期概念 10。设当前时间为 $t\_{now}$，邮件发送时间为 $t\_{msg}$。该邮件贡献的瞬时权重 $w(t)$ 为：

$$w(t) \= w\_{type} \\cdot e^{-\\lambda (t\_{now} \- t\_{msg})}$$  
其中 $\\lambda$ 是衰减常数，由半衰期（Half-Life, $T\_{1/2}$） 决定：

$$\\lambda \= \\frac{\\ln(2)}{T\_{1/2}}$$

#### **2.3.2 业务参数建议**

* **敏捷型项目组织**：建议 $T\_{1/2} \= 30$ 天。意味着一个月前的交互，其权重在当前仅剩 50%。这能快速反映项目组的切换。  
* **稳定型科层组织**：建议 $T\_{1/2} \= 90$ 天。反映长期稳定的汇报关系。

通过 NetworkX 的 MultiDiGraph 结构存储每封邮件的时间戳，在分析时动态计算 snapshot（快照）的聚合权重，是实现这一机制的最佳工程实践。

## ---

**第三章 网络拓扑分析：关键依赖与权力结构**

本章旨在解决“关键依赖”与“识别核心人物”的问题。利用复杂网络算法，我们不再依赖头衔，而是依赖数据来识别谁在真正掌控信息流。

### **3.1 隐形领袖识别：PageRank 与特征向量中心性**

#### **3.1.1 算法原理**

度中心性（Degree Centrality）仅仅统计了谁发的邮件多，这容易被群发通知的行政人员混淆。我们需要知道\*\*“谁被重要的人关注”\*\*。  
PageRank 算法最初用于网页排名，同样适用于人才图谱。如果一个员工收到来自 CEO、CTO 或其他核心骨干的邮件，他的 PageRank 值会显著提升。

#### **3.1.2 业务洞察：非正式权力**

* **高 PageRank 但低职级**：这类员工是组织的\*\*“隐形领袖（Informal Leaders）”**或**“技术大拿”\*\*。他们没有管理头衔，但对业务决策拥有实质性的影响力 12。  
* **应用**：在识别“高潜人才（HiPo）”或进行“继任者计划”时，这些指标比绩效打分更具前瞻性。

#### **3.1.3 NetworkX 实现**

Python

\# 使用时间衰减后的权重计算 PageRank  
pr\_scores \= nx.pagerank(G, alpha=0.85, weight='decayed\_weight')

### **3.2 跨界桥梁与守门人：介数中心性 (Betweenness Centrality)**

#### **3.2.1 算法原理**

介数中心性衡量一个节点出现在网络中所有最短路径上的频率。

$$C\_B(v) \= \\sum\_{s \\neq v \\neq t} \\frac{\\sigma\_{st}(v)}{\\sigma\_{st}}$$

其中 $\\sigma\_{st}$ 是节点 $s$ 到 $t$ 的最短路径总数，$\\sigma\_{st}(v)$ 是经过 $v$ 的路径数。

#### **3.2.2 业务洞察：桥梁与瓶颈**

* **桥梁（Bridges）**：高介数者通常连接了两个互不统属的部门（如连接研发部与市场部）。他们是**信息经纪人（Information Brokers）**，能够促进跨部门协作 1。  
* **守门人（Gatekeepers）与瓶颈**：如果某人的介数过高，意味着信息流必须经过他才能到达另一端。一旦该员工离职或休假，跨部门协作将瘫痪。这直接对应了“关键依赖”的识别需求。  
* **算法优化**：对于大规模图，标准算法复杂度 $O(VE)$ 过高。建议使用 Brandes 算法的近似实现 betweenness\_centrality\_subset，选取部分核心节点作为锚点进行计算 13。

### **3.3 结构洞 (Structural Holes) 与创新预测**

罗纳德·伯特（Ronald Burt）的结构洞理论是识别人才稀缺性的核心工具 14。

#### **3.3.1 核心指标：网络约束系数 (Constraint)**

Burt 的约束系数 $C\_i$ 衡量一个个体的网络是开放的还是封闭的。

$$C\_i \= \\sum\_{j} (p\_{ij} \+ \\sum\_{q} p\_{iq} p\_{qj})^2$$

* **高约束（High Constraint）**：员工的朋友圈都是熟人（Clique），信息高度冗余。  
* **低约束（Low Constraint）**：员工连接了多个互不认识的群组（占据了结构洞）。

#### **3.3.2 业务价值：创新预测**

研究表明，**占据结构洞（低约束系数）的员工更有可能提出创新想法**，因为他们能接触到异质性的信息流 15。在组建创新突击队时，应优先筛选此类人才。

## ---

**第四章 语义映射与职能覆盖：LLM 的深度解析**

仅靠网络拓扑无法回答“谁负责什么”以及“是否存在技能缺口”。本章引入 **NLP** 和 **LLM** 技术，对邮件元数据及（合规允许下的）主题摘要进行语义分析。

### **4.1 基于 BERTopic 的动态话题建模**

为了识别“核心职能”，我们需要从邮件流中自动涌现业务话题，而不是预设关键词。

#### **4.1.1 算法流程**

17

这是一个典型的无监督学习 Pipeline：

1. **嵌入（Embeddings）**：使用预训练模型（如 paraphrase-multilingual-MiniLM-L12-v2）将邮件主题（Subject）转化为高维向量。  
2. **降维（Dimensionality Reduction）**：使用 **UMAP** 算法将向量降维，保留局部流形结构。  
3. **聚类（Clustering）**：使用 **HDBSCAN** 进行密度聚类，自动识别话题簇（Cluster），并能有效处理噪音数据。  
4. **表示（Representation）**：利用 **c-TF-IDF** 算法提取每个簇的关键词（如“API 迁移”、“Q3 财报”、“供应链审计”）。

#### **4.1.2 职能-人员映射矩阵**

通过计算员工 $u$ 发出的邮件在各个话题簇 $C\_k$ 中的分布概率 $P(C\_k|u)$，我们可以构建**员工-话题矩阵**。

* **应用**：识别“挂羊头卖狗肉”的现象。例如，一名头衔为“销售”的员工，其邮件内容 80% 聚集在“产品测试”话题中，说明他实际承担了 QA 或产品经理的职能。

### **4.2 专家识别与技能缺口分析 (Expertise & Gap Analysis)**

#### **4.2.1 专家网络构建**

结合 HITS (Hyperlink-Induced Topic Search) 算法与语义分析 12。  
对于特定技能话题（如“Python 开发”）：

* 构建该话题下的子图。  
* 计算节点的 **Authority Score**。如果很多人就该话题向某人发送咨询邮件（In-degree 高且来源于 Hubs），则该人是该领域的**隐形专家**。

#### **4.2.2 人员缺口识别**

计算关键战略话题（如“AI 转型”）的参与度分布基尼系数（Gini Coefficient）。

* **高风险**：如果关于“AI 转型”的讨论高度集中在 1-2 个节点（Gini \> 0.8），且这两个节点已处于高负荷状态，则系统判定存在严重的\*\*“技能单点风险”**和**“人员缺口”\*\*。

### **4.3 LLM 增强的角色推理 (TnT-LLM)**

对于难以分类的复杂职能，利用 LLM 的零样本推理能力 19。

* **Prompt 策略**：输入员工的网络特征（如连接部门数）和高频词云。"Employee A connects primarily with Finance and Engineering. Top email keywords are 'budget approval', 'server cost', 'license renewal'. Deduce their functional role."  
* **输出**：LLM 可能推断出“IT 采购经理”或“FinOps 工程师”，这比 HR 系统的标准岗位名称更精准。

## ---

**第五章 协作健康与信息孤岛分析**

本章解决“协作健康”与“信息孤岛”问题。核心在于对比“行政组织”与“实际交互社群”的差异。

### **5.1 社群检测算法 (Community Detection)**

我们不依据 Org Chart，而是依据交互密度来划分圈子。

#### **5.1.1 算法选择：Leiden 算法**

相比经典的 Louvain 算法，**Leiden 算法**在优化模块度（Modularity）的同时，保证了社群的连通性，且运算速度更快，更适合大规模网络 17。

#### **5.1.2 孤岛指数 (Silo Index)**

将 Leiden 算法检测出的\*\*自然社群（Community）**与公司的**行政部门（Department）\*\*进行重叠度分析。

* **NMI (归一化互信息)**：衡量两个划分的相似度。  
* 部门内聚度：计算 $E-I$ 指数（External-Internal Index）。

  $$E-I \= \\frac{E \- I}{E \+ I}$$

  其中 $E$ 为跨部门连接数，$I$ 为部门内连接数。  
  * **值接近 \-1**：极度封闭，**信息孤岛**严重。  
  * **值接近 \+1**：极度松散，缺乏团队凝聚力。  
  * **健康区间**：通常在 \-0.5 到 \+0.5 之间，保持内部凝聚与外部协作的平衡 22。

### **5.2 组织熵 (Organizational Entropy)**

引入热力学熵的概念来衡量协作的混乱程度 23。

* 结构熵 (Structural Entropy)：

  $$H\_{struct} \= \- \\sum\_{i} \\frac{d\_i}{2m} \\log (\\frac{d\_i}{2m})$$

  其中 $d\_i$ 是节点度，$m$ 是总边数。  
* **业务含义**：  
  * **熵过低**：层级森严，信息流动受阻，可能导致反应迟钝。  
  * **熵过高**：扁平化过度，沟通路径混乱，可能导致决策效率低下。  
  * **动态监控**：在组织架构调整（Reorg）期间，监控熵值的变化曲线，判断新秩序是否建立。

## ---

**第六章 外部生态与供应链风险量化**

企业的生存依赖于外部生态。通过分析邮件域（Domain），我们可以量化客户与供应商关系的健康度。

### **6.1 外部关系集中度：HHI 指数应用**

**赫芬达尔-赫希曼指数（HHI）通常用于反垄断分析，但在本系统中，我们创新性地将其用于供应链风险评估** 25。

#### **6.1.1 算法逻辑**

构建“员工-外部域”的二部图。设公司与 $N$ 个外部供应商域（如 @vendorA.com, @vendorB.com）有交互。计算交互量的份额 $s\_i$。

$$HHI \= \\sum\_{i=1}^{N} s\_i^2$$

#### **6.1.2 风险判读**

* **高 HHI (\> 0.25)**：说明公司的外部交互极度集中在少数几个供应商或客户身上。这是一种**生态脆弱性**的表现。一旦该大客户流失，或该核心供应商断供，企业将面临巨大冲击。  
* **建议**：对于高 HHI 的领域（如“芯片采购”），算法应提示引入多元化供应商。

### **6.2 外部关系的单点故障 (Boundary Spanning Risks)**

分析对接关键外部域（如 @vip-client.com）的内部员工结构。

* **结构性漏洞检测**：如果与某关键客户的 90% 交互都通过单一员工（Boundary Spanner）进行，该员工即为**关系瓶颈**。  
* **风险**：一旦该员工离职，客户关系可能随之流失。  
* **行动建议**：系统自动识别此类高危节点，建议增加“B角”或副手进入相关邮件抄送列表，稀释关系独占性。

## ---

**第七章 动态风险预警：从倦怠到离职**

本章利用时序数据，构建预测性模型，解决“风险预警”需求。

### **7.1 职业倦怠 (Burnout) 的数字化表征**

基于 Job Demands-Resources (JD-R) 模型与邮件行为研究 27，我们提取以下核心特征：

| 风险维度 | 指标定义 | 风险阈值建议 |
| :---- | :---- | :---- |
| **下班后负荷 (After-hours)** | 晚 8 点至早 8 点及周末发件占比 | **\> 30%** 28 |
| **响应压力 (Response Pressure)** | 收件到回复的时间差（Latency） | 均值持续缩短且方差增大（焦虑特征） |
| **周末侵占 (Weekend Activity)** | 周末活跃天数占比 | **\> 20%** 28 |
| **网络退缩 (Withdrawal)** | Out-degree（主动发件）显著下降 | 环比下降 \> 20% |

**综合评分算法**：使用逻辑回归或随机森林模型，将上述指标加权，输出 0-100 的**倦怠风险指数**。注意需结合员工所在时区进行归一化，避免跨国协作的误判。

### **7.2 离职预测：传染与侵蚀模型**

“离职是会传染的”。本系统采用两种机制预测离职倾向。

#### **7.2.1 离职传染模型 (Turnover Contagion)**

基于社会传染理论 29，构建邻居状态影响模型。

$$P\_{churn}(u) \= \\alpha \\cdot P\_{self}(u) \+ \\beta \\sum\_{v \\in N(u)} w\_{uv} \\cdot I\_{churn}(v)$$

* 如果员工 $u$ 的强连接邻居（Top 5 互动者）中有人在过去 3 个月内离职（$I\_{churn}=1$），则 $u$ 的离职概率显著增加。这被称为**滚雪球效应（Snowball Effect）**。

#### **7.2.2 K-shell 结构侵蚀 (Structural Erosion)**

监测员工在网络核心层级中的位置变化 31。

* **K-shell Decomposition**：将网络剥洋葱般分层。核心层（High k-shell）通常是组织骨干。  
* **预警信号**：如果一名核心员工的 k-shell 值在两个季度内连续下降，说明他正在被边缘化，或者他的核心盟友正在流失。这往往是离职意向产生的早期静默信号，比显性的抱怨更早出现。

### **7.3 组织鲁棒性测试：渗透分析 (Percolation Analysis)**

为了量化“单点故障”对整体的影响，我们引入物理学中的渗透理论。

* **模拟攻击**：按 PageRank 排名移除 Top 5 节点（模拟核心骨干集体离职）。  
* **最大连通分量 (Giant Component) 变化**：计算移除后网络最大连通子图的大小变化。  
* **判定**：如果移除 5 人导致网络破碎度超过 20%，说明组织极其脆弱，过度依赖“超级节点”。

## ---

**第八章 系统实施架构与伦理合规**

### **8.1 基于 Python 的可插拔 Pipeline 设计**

为了实现算法的可插拔性，我们建议采用面向对象的**策略模式**。

#### **8.1.1 架构代码示例**

Python

from abc import ABC, abstractmethod  
import networkx as nx

\# 抽象基类：分析器策略  
class GraphAnalyzer(ABC):  
    @abstractmethod  
    def analyze(self, G: nx.DiGraph, metadata: dict) \-\> dict:  
        pass

\# 具体实现：拓扑分析器  
class TopologyAnalyzer(GraphAnalyzer):  
    def analyze(self, G, metadata):  
        \# 计算 PageRank  
        pr \= nx.pagerank(G, weight='weight')  
        \# 计算结构洞  
        constraint \= nx.constraint(G, weight='weight')  
        return {"pagerank": pr, "structural\_holes": constraint}

\# 具体实现：风险分析器  
class BurnoutAnalyzer(GraphAnalyzer):  
    def analyze(self, G, metadata):  
        \# 计算下班后邮件比例  
        \# 逻辑：遍历边的时间属性，计算 after\_hours\_ratio  
        return {"burnout\_risk": calculate\_metrics(G)}

\# 统一执行管道  
class AnalysisPipeline:  
    def \_\_init\_\_(self):  
        self.analyzers \=

    def add\_analyzer(self, analyzer: GraphAnalyzer):  
        self.analyzers.append(analyzer)

    def run(self, G, metadata):  
        results \= {}  
        for analyzer in self.analyzers:  
            results.update(analyzer.analyze(G, metadata))  
        return results

这种设计使得未来添加新的算法（如引入新的 LLM 模型）时，只需继承 GraphAnalyzer 即可，无需修改核心代码。

### **8.2 数据隐私与伦理治理 (Governance)**

ONA 分析涉及极高的隐私敏感度。系统必须内置隐私保护机制 3。

1. **最小化原则**：仅分析元数据（Metadata）和主题（Subject），**严禁分析邮件正文（Body）**，除非在特定的合规审计场景下并获得法务授权。  
2. **去标识化 (Hashing)**：在数据摄取层（Ingestion）即对邮箱进行加盐哈希（Salted Hash）。算法层仅处理 User\_A2f39 这样的 ID。  
3. **聚合输出**：对于负面指标（如倦怠、离职预测），系统仅向管理层展示\*\*团队级（Team Level）\*\*的聚合风险热力图，避免针对个人的算法歧视或监视感。

### **8.3 可视化选型**

* **前端渲染**：建议使用 **Cytoscape.js** 32。它比 NetworkX 的 Matplotlib 绘图强大得多，支持数万节点的高性能渲染，且提供丰富的交互（点击节点高亮邻居、力导向布局动态调整）。  
* **后端支持**：通过 Python 生成 JSON 格式的图数据（Nodes/Edges list），前端直接加载渲染。

---

**结论**

本报告所设计的算法体系，通过**加权有向图**捕捉权力结构，通过**BERTopic** 洞察职能分布，通过**Leiden 算法**诊断协作孤岛，并通过**HHI**与**传染模型**预警内外部风险。这是一套从数据到底层逻辑完全闭环的解决方案。实施该系统，将帮助贵公司从凭借经验的模糊管理，进化为基于数据智能的精准治理。

| 维度 | 核心算法/模型 | 解决问题 | 关键 Python 库 |
| :---- | :---- | :---- | :---- |
| **拓扑** | PageRank, Betweenness | 隐形领袖、守门人 | networkx |
| **职能** | BERTopic, c-TF-IDF | 职能画像、错位识别 | bertopic, transformers |
| **协作** | Leiden, E-I Index | 部门墙、社群检测 | cdlib, python-louvain |
| **外部** | HHI, Structural Entropy | 供应链集中度 | scipy, numpy |
| **风险** | Contagion Model, Decay | 离职传染、职业倦怠 | pandas, lifelines |

#### **Works cited**

1. Organizational Network Analysis (ONA): Mapping Informal Power and Influence, accessed December 23, 2025, [https://www.ilms.academy/blog/organizational-network-analysis-ona-mapping-informal-power-and-influence](https://www.ilms.academy/blog/organizational-network-analysis-ona-mapping-informal-power-and-influence)  
2. What is Organizational Network Analysis? A Comprehensive Guide \- Polinode, accessed December 23, 2025, [https://www.polinode.com/guides/what-is-organizational-network-analysis-a-comprehensive-guide](https://www.polinode.com/guides/what-is-organizational-network-analysis-a-comprehensive-guide)  
3. HR teams can (and should) use AI to predict employee burnout \- ESMT Berlin, accessed December 23, 2025, [https://esmt.berlin/knowledge/hr-teams-can-and-should-use-ai-predict-employee-burnout](https://esmt.berlin/knowledge/hr-teams-can-and-should-use-ai-predict-employee-burnout)  
4. Suggesting Friends Using the Implicit Social Graph \- Google Research, accessed December 23, 2025, [https://research.google.com/pubs/archive/36371.pdf](https://research.google.com/pubs/archive/36371.pdf)  
5. Suggesting (More) Friends Using the Implicit Social Graph \- Google Research, accessed December 23, 2025, [https://research.google.com/pubs/archive/37120.pdf](https://research.google.com/pubs/archive/37120.pdf)  
6. Network Analysis with the Enron Email Corpus, accessed December 23, 2025, [https://www.tandfonline.com/doi/pdf/10.1080/10691898.2015.11889734](https://www.tandfonline.com/doi/pdf/10.1080/10691898.2015.11889734)  
7. CC vs BCC: What's the Difference in Email? \- Mailchimp, accessed December 23, 2025, [https://mailchimp.com/resources/what-is-a-bcc-email/](https://mailchimp.com/resources/what-is-a-bcc-email/)  
8. Anatomy of an Email: To vs CC vs BCC, Oh My\! \- LinkedPhone, accessed December 23, 2025, [https://linkedphone.com/anatomy-of-an-email-to-vs-cc-bcc/](https://linkedphone.com/anatomy-of-an-email-to-vs-cc-bcc/)  
9. NetworkX — NetworkX documentation, accessed December 23, 2025, [https://networkx.org/](https://networkx.org/)  
10. Exponential decay \- Wikipedia, accessed December 23, 2025, [https://en.wikipedia.org/wiki/Exponential\_decay](https://en.wikipedia.org/wiki/Exponential_decay)  
11. Exponential decay models | R-bloggers, accessed December 23, 2025, [https://www.r-bloggers.com/2012/05/exponential-decay-models/](https://www.r-bloggers.com/2012/05/exponential-decay-models/)  
12. Classifying Organizational Roles Using Email Social Networks | Request PDF, accessed December 23, 2025, [https://www.researchgate.net/publication/286547506\_Classifying\_Organizational\_Roles\_Using\_Email\_Social\_Networks](https://www.researchgate.net/publication/286547506_Classifying_Organizational_Roles_Using_Email_Social_Networks)  
13. Shortest Paths — NetworkX 3.6.1 documentation, accessed December 23, 2025, [https://networkx.org/documentation/stable/reference/algorithms/shortest\_paths.html](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html)  
14. Appendix B Measuring Access to Structural Holes \- Ronald Burt, accessed December 23, 2025, [http://www.ronaldsburt.com/research/files/NNappB.pdf](http://www.ronaldsburt.com/research/files/NNappB.pdf)  
15. Introduction to Structural Hole Theory | by Carolyn Bentley (Wells) \- Medium, accessed December 23, 2025, [https://medium.com/@agreenmoment/introduction-to-structural-holes-theory-124c51c3ae31](https://medium.com/@agreenmoment/introduction-to-structural-holes-theory-124c51c3ae31)  
16. Structural Holes and Good Ideas1 | American Journal of Sociology: Vol 110, No 2, accessed December 23, 2025, [https://www.journals.uchicago.edu/doi/10.1086/421787](https://www.journals.uchicago.edu/doi/10.1086/421787)  
17. GCD-TM: Graph-Driven Community Detection for Topic Modelling in Psychiatry Texts \- ACL Anthology, accessed December 23, 2025, [https://aclanthology.org/2024.nlp4science-1.6.pdf](https://aclanthology.org/2024.nlp4science-1.6.pdf)  
18. Visualize Topics \- BERTopic \- Maarten Grootendorst, accessed December 23, 2025, [https://maartengr.github.io/BERTopic/getting\_started/visualization/visualize\_topics.html](https://maartengr.github.io/BERTopic/getting_started/visualization/visualize_topics.html)  
19. TnT-LLM: Text Mining at Scale with Large Language Models \- Microsoft Research, accessed December 23, 2025, [https://www.microsoft.com/en-us/research/publication/tnt-llm-text-mining-at-scale-with-large-language-models/](https://www.microsoft.com/en-us/research/publication/tnt-llm-text-mining-at-scale-with-large-language-models/)  
20. LLMs Between the Nodes: Community Discovery Beyond Vectors \- arXiv, accessed December 23, 2025, [https://arxiv.org/html/2507.22955v1](https://arxiv.org/html/2507.22955v1)  
21. A guide for choosing community detection algorithms in social network studies: The Question-Alignment approach \- PubMed Central, accessed December 23, 2025, [https://pmc.ncbi.nlm.nih.gov/articles/PMC7508227/](https://pmc.ncbi.nlm.nih.gov/articles/PMC7508227/)  
22. What is Organizational Network Analysis (ONA)? \- Rob Cross, accessed December 23, 2025, [https://www.robcross.org/what-is-organizational-network-analysis/](https://www.robcross.org/what-is-organizational-network-analysis/)  
23. Quantifying Information Distribution in Social Networks: The Structural Entropy Index of Community (SEIC) for Twitter Communication Analysis \- MDPI, accessed December 23, 2025, [https://www.mdpi.com/1099-4300/27/11/1140](https://www.mdpi.com/1099-4300/27/11/1140)  
24. A Network Structure Entropy Considering Series-Parallel Structures \- MDPI, accessed December 23, 2025, [https://www.mdpi.com/1099-4300/24/7/852](https://www.mdpi.com/1099-4300/24/7/852)  
25. The Herfindahl-Hirschman Index: Story, Primer, Alternatives \- Conversable Economist, accessed December 23, 2025, [https://conversableeconomist.com/2020/02/18/the-herfindahl-hirschman-index-story-primer-alternatives/](https://conversableeconomist.com/2020/02/18/the-herfindahl-hirschman-index-story-primer-alternatives/)  
26. Some dominance indices to determine market concentration \- PMC \- NIH, accessed December 23, 2025, [https://pmc.ncbi.nlm.nih.gov/articles/PMC9041919/](https://pmc.ncbi.nlm.nih.gov/articles/PMC9041919/)  
27. E-mail communication patterns and job burnout \- PMC \- PubMed Central, accessed December 23, 2025, [https://pmc.ncbi.nlm.nih.gov/articles/PMC5843271/](https://pmc.ncbi.nlm.nih.gov/articles/PMC5843271/)  
28. Flagging Burnout Early: Alerting on After-Hours Email Patterns in Google & Microsoft 365, accessed December 23, 2025, [https://www.worklytics.co/resources/flagging-burnout-early-alerting-after-hours-email-patterns-google-microsoft-365](https://www.worklytics.co/resources/flagging-burnout-early-alerting-after-hours-email-patterns-google-microsoft-365)  
29. (PDF) Predicting Employee Turnover From Communication Networks \- ResearchGate, accessed December 23, 2025, [https://www.researchgate.net/publication/249471877\_Predicting\_Employee\_Turnover\_From\_Communication\_Networks](https://www.researchgate.net/publication/249471877_Predicting_Employee_Turnover_From_Communication_Networks)  
30. (PDF) New Network Models for the Analysis of Social Contagion in Organizations: An Introduction to Autologistic Actor Attribute Models \- ResearchGate, accessed December 23, 2025, [https://www.researchgate.net/publication/350062090\_New\_Network\_Models\_for\_the\_Analysis\_of\_Social\_Contagion\_in\_Organizations\_An\_Introduction\_to\_Autologistic\_Actor\_Attribute\_Models](https://www.researchgate.net/publication/350062090_New_Network_Models_for_the_Analysis_of_Social_Contagion_in_Organizations_An_Introduction_to_Autologistic_Actor_Attribute_Models)  
31. (PDF) Predicting Employee Turnover from Network Analysis \- ResearchGate, accessed December 23, 2025, [https://www.researchgate.net/publication/331681337\_Predicting\_Employee\_Turnover\_from\_Network\_Analysis](https://www.researchgate.net/publication/331681337_Predicting_Employee_Turnover_from_Network_Analysis)  
32. Networkx vs cytoscape \- Dash Python \- Plotly Community Forum, accessed December 23, 2025, [https://community.plotly.com/t/networkx-vs-cytoscape/61430](https://community.plotly.com/t/networkx-vs-cytoscape/61430)  
33. Network Visualization with Cytoscape, accessed December 23, 2025, [https://cytoscape.org/cytoscape-tutorials/presentations/network-visualization.html](https://cytoscape.org/cytoscape-tutorials/presentations/network-visualization.html)