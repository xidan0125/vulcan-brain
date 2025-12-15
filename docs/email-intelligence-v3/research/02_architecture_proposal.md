全息数据底座架构设计方案
A. 数据模型设计 (Data Modeling)
采用知识图谱融合事件溯源： 针对复杂的高端制造 B2B 交互数据，当前业界最佳实践是构建知识图谱作为统一的数据表示[1][2]。简单的实体-关系三元组模型不足以表达多实体、多上下文的关系[3]。为此，我们设计一个事件驱动的知识图谱，结合超图(Hypergraph)结构，来存储“原子事实”和其上下文。知识图谱以节点和边表示实体及其关系，并支持高阶关系 (n元关系) 作为超边来涵盖业务中的多实体关联（如合同版本关联多方、多条件参数）[4]。同时，引入事件(Event)节点记录每封邮件或合同修订动作，实现事件溯源：每个事件节点连接相关实体/事实节点，保留发生时间和顺序。这样的事件型知识图谱可将分散的高价值数据实时抽取、去重链接，汇聚成企业知识网[5]。
模式与Schema设计： 我们采用分层模式，包括元数据层(MetaKG)、布局层(LayoutKG)和语义层(SemanticKG)[6]。MetaKG存储文档/邮件的元信息（发件人、日期等）；LayoutKG捕获文档结构（章节、页码、表格位置等）用于定位来源；SemanticKG存储领域实体、属性及关系（技术参数、价格、条款等）[7]。通过这种Schema，系统可兼容非结构化文本（邮件正文节点）、半结构化表格（Excel单元格节点）、多模态图纸（图片节点及其OCR提取的文字节点）。例如，邮件正文解析为段落/句子节点，PDF附件解析为页和内容块节点，Excel解析为表格/单元格节点，然后在知识图谱中将它们与抽取的业务实体和事实节点关联[8][9]。这种统一Schema确保不同来源的信息通过关系连接：正文说明节点“解释(explain)”某PDF段落，Excel单元格节点与对应PDF数据节点“相同时间(same-time)”等关系相连，从而整合上下文[10][11]。
JSON Schema 示例： 我们推荐使用NoSQL图数据库（如Neo4j或TypeDB）存储上述模式下的数据，以JSON形式定义实体/事件记录。下面给出核心“原子事实”和“事件”的JSON示例：
// 原子事实示例： {   "fact_id": "FACT_1001",   "type": "MaterialProperty",   "entity": "Alloy_X",               // 实体名称   "attribute": "heat_resistance",    // 属性名称   "value": 1200,   "unit": "℃",   "conditions": { "environment": "A" },  // 条件性上下文   "state": "draft",                 // 所处业务状态（此处为草案值）   "confidence": "LLM_Reasoned",     // 置信等级：LLM推理提取   "evidence": [                     // 证据链，可包含多个来源     {       "source_id": "EMAIL_2023_05_01_007",       "source_type": "email_attachment",       "file_name": "Spec_v1.pdf",       "page": 5,       "bbox": [100, 230, 400, 260]   // 在源文件中的坐标区域     }   ],   "event_id": "EVT_20230501_1"      // 来源事件（邮件）的ID，关联到事件节点 }
// 事件示例（如一次合同修订）： {   "event_id": "EVT_20230501_1",   "type": "ContractRevision",   "timestamp": "2023-05-01T10:15:30Z",   "actors": ["Alice (Sales)", "Bob (Client)"],  // 涉及主体   "entities": ["Contract_99"],      // 涉及的业务实体（如合同编号）   "changes": [                      // 变更的事实列表     {       "fact": "price",       "old_value": 1000000,       "new_value": 950000     }   ],   "state_after": "negotiation",     // 事件导致的业务状态（如进入谈判中）   "source": {     "source_id": "EMAIL_2023_05_01_007",     "source_type": "email",        // 指明事件来源是某封邮件     "sequence_in_thread": 45       // 邮件线程中的序号   } }
上述JSON结构展示了事件-事实-证据链的物理存储模型：事实记录存储具体属性值及条件，关联到相应事件ID，并带有证据数组指向原始附件的位置（包括文件标识、页码及区域坐标，实现数据血缘追溯到源头）。事件记录描述一次业务交互（如合同版本更新），列出影响的事实变更和演进后的状态。这样的Schema能直观表示“在某次邮件事件EVT_20230501_1中，Alloy_X材料的heat_resistance在环境A下由1000℃变为1200℃，该新值来自附件Spec_v1.pdf第5页某区域”，满足多源异构数据的统一表示和溯源需求[12][13]。
超图与推理扩展： 为增强对复杂关系的查询支持，我们在知识图谱中引入超边或关联节点表示多元组关系。例如，对于“材料耐热度在环境A为X，在环境B为Y”这样的条件性事实，可以建模为一个耐热度属性节点，通过两条关联边分别连接环境A和环境B的取值节点，或者引入一个中间超节点将Material_X、Environment_A、Environment_B、HeatResistance_X、HeatResistance_Y关联在一起，从而完整表达事实的条件依赖。类似地，长链路依赖（跨2年50封邮件的决策）可通过事件链表征：每个事件节点有next_event指针指向后续事件，使我们沿事件时间线遍历；也可以利用图数据库的路径查询来追踪某项决策涉及的整个事件子图。
知识图谱的优势： 该建模符合业界趋势：知识图谱擅长处理高度关联的企业核心数据，可自然表示信息流转并集成多源数据[14][15]。相比仅用向量索引的文本处理，图结构保留了丰富的上下位和顺序关系，使系统可以回答复杂业务问题并支持上层推理。例如，通过图查询可以找到“某技术参数从首次提议到最终确定经过哪些版本修改”，这是传统关系库或纯文本搜索难以实现的。GraphRAG 等研究也表明，将知识图谱用于生成式AI检索可大幅提高准确性和可解释性[16][17]——这意味着我们的数据底座既能服务直接查询，也能作为检索增强生成 (RAG) 的知识来源。
B. 多模态信息融合策略 (Multimodal Fusion)
分路径提取，语义后融合： 鉴于邮件正文与附件经常互为上下文且格式差异巨大，我们采用“分而治之”的多模态信息处理流水线，再进行融合。这一策略与Docs2KG框架相一致：先将邮件按照正文和附件拆分，正文文本走文本解析通道，附件根据类型走相应解析通道，然后将提取的信息汇合构建知识图谱[8][18]。具体而言，邮件正文经过NLP管道提取关键句子、实体和意图（例如识别“倾向接受”这类模糊表态，可用正则结合LLM分类判断其状态语气）；PDF附件通过OCR和版面分析获取文字块、表格和图注等（利用开源LayoutLMv3或PyMuPDF解析，再辅以LLM抽取表述的事实）；扫描件/图纸先高分辨率OCR提取文字及标注，再使用视觉模型识别关键图形符号或参数位置；Excel附件则用数据解析库（如Pandas）读表，将表格转换为结构化JSON，或渲染成图像走OCR路径以保留表格布局[19][20]。在此双路径处理阶段，每种格式由专门模块处理，最大程度保留各自信息（表格数值精度、图纸中的注释等）[21][22]。
上下文融合与冲突对齐： 提取完成后，系统执行语义级融合：将正文和附件信息合并，同步对比正文与附件提及的关键数据。如检测到正文声明“修改了附件中的某参数”，则在知识图谱融合时生成一条“修正”关系，连接正文中的陈述节点和附件对应的事实节点，标记附件原值已被正文覆写。这种Inter-modal关系（模态间关系）用例如“overrides”或Docs2KG中的“supported_by/解释(explain)”关系表示[23]。融合过程由一个全息解析器（可由大模型实现）辅助完成：我们构建邮件正文与附件内容的统一上下文，例如Prompt模板提示LLM： “附件X显示的参数A=5，正文声称参数A=6，请给出最终有效的参数A值并解释来源”。利用本地强大的LLM推理，可以产出带有依据的融合结果，然后据此更新知识图谱中的事实节点。此后融合方法确保正文和附件的信息冲突被显式处理，而非简单地各存各的。研究表明，在RAG应用中引入图结构关联文本片段可以更准确地回答复杂查询[24][17]，我们的融合策略正是通过图谱连接正文-附件实现对复杂上下文的保留。
多模态大模型端到端方案： 作为对比，我们也评估多模态大模型 (LMM) 端到端提取。最新开源模型如 Qwen-2.5-VL 或 Llama-3-Vision 据称可同时接受图像和文本输入，对图文进行统一编码理解。这意味着我们可以将邮件正文和附件页面图像一起输入模型，让模型直接输出结构化的事实。然而在工程上，我们需权衡这种方法的挑战：超长上下文窗口和高分辨率图像细节。附件常为多页文档，直接拼接正文和所有附件文本会超出大模型的Token窗口限制；而将高清设计图等整图输入，会产生数千以上的视觉Token，严重挤占上下文长度。为缓解此问题，模型通常会下采样图像或切块输入，但这可能导致细小文字或单位丢失。因此，尽管多模态LLM如Qwen-VL-Chat在图文问答上表现优异，但对于我们80,000封邮件的大体量、多页附件场景，分段处理+检索仍是更可行的方案。我们推荐：优先使用分模块提取+后融合的流水线，在关键融合步骤借助多模态LLM进行局部推理。例如，当正文与附件某段存在冲突时，调用视觉问答模型对附件相关部分进行再理解，比让模型一次吃下全量数据更稳健。
Token窗口与细节保留策略： 针对Token长度限制，我们利用Chunking + RAG策略：将长附件分割成语义段落或表格单元作为文档块，使用向量索引检索与查询相关的块供LLM处理。这种分块检索确保即使模型上下文有限，也能通过检索挑选相关片段进行分析，提高效率和细节保留度[25]。对于高分辨率图纸，我们采取多尺度处理：先提取矢量形式的数据（如CAD图的标注文本和数值），再针对关键区域截取图像片段放大后给视觉模型分析，从而避免整图缩放带来的信息漏失。总的来说，分步提取 + 智能检索融合代表了当前业界在多模态企业数据处理上的SOTA流程[21][8]——既发挥各模态专长，又通过知识图谱和LLM将信息重新整合成“全息”的业务知识。
C. 确定性与数据治理 (Certainty & Governance)
置信度量化与存储： 面对关键信息零差错的要求，我们为每条提取的“原子事实”打上可信度等级标签，并在Schema中存储。这套置信度分级可分为三档：【OCR_Raw】表示仅由OCR直接提取，未经模型理解（低信度）；【LLM_Reasoned】表示经大模型上下文推理佐证（中信度）；【Human_Verified】表示经人工校对确认（高信度）。例如，上述JSON示例中的"confidence": "LLM_Reasoned"即表示该耐热度是模型综合多源得到的结果。系统在知识图谱中可将置信度作为属性或边权重储存，供查询和决策参考。当存在多来源冲突时，也可利用置信度赋值驱动自动仲裁（见下文冲突解决策略）[26]。此外，我们引入置信度评分机制：对大模型输出引入一致性检查或embedding匹配来评估其可靠度[27][28]。研究发现LLM往往对自身输出过于自信，而embedding语义相似度等方法能更好地区分不准确结果[28]。因此系统在录入LLM提取的事实时，会将模型的回答与原文片段计算相似度，若低于阈值则降低其置信等级或标记人工复核。通过这些手段，我们为每条数据提供量化的可信度指标并持续校准，确保管理层可据此判断信息可靠性。
业务状态机设计： 为表示业务流程中的状态演进，我们在数据模型中加入状态字段和状态机规则。例如合同实体有status属性，可取{Quotation(报价中), Negotiation(谈判中), Signed(已签约), Voided(已作废)}等值。每条事实也带有state（如示例中的 "state": "draft" 表示草案值）。更关键的是，我们设计状态与事件的联动：事件节点（如EVT合同修订）会触发相关实体状态改变，同时旧版本事实被标记为过期。比如一次“合同签署”事件会将合同.status从“谈判中”更新为“已签约”，并将此前所有标记为草案的价格参数事实更新为“最终确认”状态。在知识图谱中，这可以通过时间戳和版本号实现：例如价格节点附有valid_until属性或连到一个“被取代(superseded_by)”关系指向新价格节点，表明旧价格已失效。通过引入状态机，我们的数据底座能够区分同一参数在不同业务阶段的取值，避免混淆草稿和定稿。例如，查询“当前有效报价”时，系统会沿着superseded_by关系找到最新状态为Signed的价格节点返回，而不会错用过期数据。
冲突检测与仲裁策略： 当邮件正文、PDF、Excel三方数据不一致时，我们采用“检测-仲裁-追踪”三步流程保证数据一致性：
	•	冲突检测： 知识图谱汇融合并新插入一条事实时，触发冲突检查。系统在同一实体-属性上下文下检索是否存在不同取值的事实节点。若发现冲突，例如合同99在“price”属性上同时存在100万和95万两个值，则进入仲裁流程。
	•	自动仲裁： 系统根据预定义优先级规则选择可信值[26]。仲裁逻辑如下：首先比较冲突事实的confidence等级，优先采用高置信度（例如Human_Verified > LLM_Reasoned > OCR_Raw）[26]；如置信等级相同，则比较来源的权威级（例如已签署合同文本 > 邮件报价 > 非正式沟通）；如仍无法区分，则以时间戳新者为准（最新邮件/附件的值覆盖旧值）[26]。在上例中，若95万来自已签合同扫描件(Human_Verified)而100万来自谈判邮件(LLM_Reasoned)，系统会选择95万作为合同99.price的有效值，同时将100万的节点标记为superseded状态以保留其历史记录。此外，如果仲裁规则仍无法自动决断（例如两个来源级别相同且新旧难辨），系统会将冲突标记为人工审核，推送给管理员在前端界面确认。整个仲裁过程有详细的算法流程图支撑：(a) 计算每候选值的信任评分；(b) 基于阈值和规则判定胜出值；(c) 更新图谱中事实节点状态（胜出者标记为“active”，败者标记为“conflict_resolved”并指向胜出者）[26]。
	•	结果追踪： 冲突解决后，系统在知识图谱中建立证据链记录仲裁过程。例如在合同99.price的95万节点附加属性derived_from: [fact_100万]，并记录决策依据（来源文件ID、判定时间、执行人/算法ID）。这相当于一个数据血缘记录，方便日后审计时追溯为何某值被取代。知识图谱天生适合存储此类数据血缘，因为它可以将仲裁决策也表示为一种关系网络[29][14]。每条原子事实都能追溯到原始证据节点（附件页面坐标等），以及其被更可信事实替换的链条。这种全链路可追溯设计确保即使出现错误决策，我们也能迅速定位根源纠正，增强整体可信度。
离线数据质量监控： 在完全离线环境下，我们搭建自动化的数据质量监控体系以持续保障知识底座的准确性和新鲜度。首先，利用规则校验(Rule-based Validation)：基于业务逻辑编写数据完整性约束，例如“一个采购请求必须在90天内转变为合同或关闭”，通过定期查询图谱找出不满足条件的异常实例。我们采用SHACL等图约束语言来形式化这些规则，在每次数据更新后运行校验，自动报告违规情况[30][31]。其次，引入开源数据质量框架，如 Great Expectations 或 Soda，定制期望(Expectations)来监测关键数据分布[32]——例如期望“报价金额应为正值”“同一合同的多版本价格应逐步收敛而非剧烈波动”等等。一旦检出超出期望的异常，记录日志并通知工程人员修正。再次，我们部署异常检测算法：利用时间序列和图网络模型，对持续积累的数据进行趋势分析，发现异常模式（如某参数频繁在几个固定值之间来回变动可能暗示提取错误或业务异常）。所有质量监控过程均可在本地算力上运行，无需外部依赖。此外，我们提供管理看板展示数据质量指标：例如置信度分布、人工校验率、冲突发生率、每种解析模型的提取准确率等。结合这些指标的可视化，数据团队可以对整体数据健康度做到心中有数，并不断迭代改进解析策略。值得一提的是，我们的知识图谱设计本身就助力数据治理：通过将Provenance(数据出处)存入图谱，我们确保每条知识都有据可依[29]；通过事件和版本的关联，我们提供了内建的审计线索来快速定位问题来源[33][14]。这使我们的数据底座在严苛的质量要求下依然保持高可信、可监管、可追责。
D. 技术栈推荐 (Tech Stack Recommendation)
模型选择 (大型本地模型): 基于完全离线和充裕GPU算力的前提，我们优先选用业界最新最强的开源大模型组合，以最大化推理效果。对于文本理解与生成，推荐使用最新的 Llama-3 70B (假设已发布) 或 Qwen-14B/34B 等中文-英语混 domains 强模型。它们在通用知识和推理方面表现优异，可通过Prompt工程和Few-Shot提示实现我们需要的NLP任务，而无需微调。同时，为了处理图像和PDF，我们引入 多模态视觉语言模型：如 Qwen-VL 系列[34]或 IDEFICS 80B 等，它们在开源领域接近GPT-4V水准。Qwen-VL-Chat 被证明可以准确理解图像内容并结合文本提问[35]。我们可利用Qwen-VL对附件中的图表、扫描件直接提问（例如“这张图纸中材料X的耐热度数值是多少？”），获取模型解析结果，再与正文内容结合。另一前沿选择是 DeepSeek-V3（MoE架构，总参数671B，激活37B/Token[36]）：它号称开源领域最强推理模型，在复杂推理和多轮分析上有优势[37]。虽然体量巨大，但在MoE架构下实际每次推理只用到一部分专家网络，因此在双5090上经过优化部署或许可行[38]。DeepSeek-V3可用于关键决策邮件的深度分析，发挥“逐步思考”(Chain-of-thought)优势，从50封邮件的长链路中抽丝剥茧找出因果关联。综上，文本大模型建议：Llama系列(如Llama-2 70B或Llama-3)用于日常查询和基础抽取，Qwen系列擅长中英混杂和专业语料，可作为辅助；DeepSeek这类超大模型在需要极高推理深度时按需调用。
多模态解析框架: 在模型周边，我们选取成熟的开源工具链来搭建多模态管道。针对PDF/扫描件解析，可使用 PyMuPDF 提取文本层，结合 Tesseract OCR 或 EasyOCR 处理扫描图像，然后利用 LayoutLM 或 DocTR 等预训练模型获取版面结构。对于Excel和半结构化表格，Pandas 和 openpyxl 提供可靠的解析手段，将数据直接转为DataFrame/JSON结构[20]。在图像理解方面，Detectron2 或 MMDetection 可用来识别技术图纸中的图形符号，如焊接符号、公差标记等；Donut OCR 或 TrOCR 等模型可以端到端读取文档图像中的关键信息。如果需要更高层语义理解，再调用视觉LLM对OCR结果结合图像进行说明。所有这些组件都可以集成在本地流程中，无需外部API，符合保密要求。
知识存储与检索: 我们推荐采用 Neo4j 或 NebulaGraph 作为知识图谱数据库，在本地部署用于存储实体关系。Neo4j对高价值主数据管理和查询非常成熟，支持ACID事务保证一致性，并提供Cypher查询方便复杂路径和模式匹配[39][40]。若需要更灵活的超边表示，可以考虑 TypeDB (Grakn) 这类本体驱动的数据库，它原生支持超关系和推理规则，适合我们的超图模型表达复杂n元关系。无论哪种图数据库，我们都会将其与向量数据库相结合，实现RAG检索：例如使用 FAISS 或 Milvus 建立文档嵌入索引库，将邮件正文段落、附件段落向量化存储，供LLM生成回答时语义检索[25]。Graph + Vector的混合检索可以由我们自行构建，也可参考 Lettria 提出的 GraphRAG 实践：在检索时同时利用图关系精准筛选以及向量相似召回，使得生成答案的准确率提升显著[16][41]。离线部署Milvus非常方便，其能处理上百万级别向量数据，查询延迟毫秒级，完全胜任80k邮件规模的向量检索需求。
软件2.0策略 (模型推理 vs 规则代码): 我们在架构中贯彻“能学习则学习，需规则则规则”的理念，把大模型与传统代码各自的优势领域加以界定。对于非结构化信息解析、模糊推断这类复杂度高且规则难穷举的任务，我们倾向使用大模型（Software 2.0）取代繁琐的硬编码逻辑。例如，材料耐热度的描述可能千变万化，与其编写一长串正则，不如让经过训练的LLM去抓取句子中的温度值并判断条件，这是大模型擅长的领域。然而，模型推理也有局限，特别在确定性计算和关键校验方面：我们不会完全依赖模型给出数值就直接采用，而是在模型提取后加上传统校验。例如对于价格等关键数值，编写验证函数确保提取值为数字且单位正确，对比多份来源是否一致，从而双重保障。再如业务规则（付款期限不得超过90天等）也通过编码实现强校验，而不依赖模型的常识判断。实践经验表明，模型+规则的混合方案最稳健：模型负责“读懂”人类语言和视觉内容，规则负责最后的守门。[26]提到也可用简单优先级和时间规则解决数据冲突，这其实就是在模型产生候选后用规则拍板的思路。我们将这种机制贯穿系统，确保模型的每次重要决策都有可解释的规则依据或人工复核。随着数据量增加，我们会持续评估Software 2.0的边界：凡是模型易出错或关系重大处，一律纳入可控的规则或人审流程，把灾难性错误风险降到最低。
硬件与性能优化: 双路RTX 5090为本地部署大模型提供了充裕的GPU算力（推测每卡配备48GB以上显存）。我们将充分利用技术栈中的并行和优化方案：首先，使用 DeepSpeed 或 Colossal-AI 对大模型进行推理并行或MoE专家并行，加速推理速度并突破单卡显存限制，使70B+模型分布在两卡上运行顺畅。其次，启用 FP16/INT8量化 或最新的 GPTQ 4bit量化技术，将模型体积缩减一半以上，在几乎无精度损失的情况下提升显存利用率，从而可能加载例如DeepSeek这样超大规模的模型。第三，对于长文档处理，引入 长上下文优化：一些Llama变体已经支持4K甚至16K以上上下文，我们会跟进使用；若需128K以上长度，可考虑 recurrence scheme 或 RAG 替代直接长上下文。双5090也为并发推理提供了可能，我们能将多模态解析流水线各阶段分摊至不同GPU：如GPU0运行OCR和图像模型，GPU1运行LLM文本生成，并使用异步队列流水线处理批量邮件，以提高吞吐。最后，在存储和查询层面，我们借助 缓存 和 预计算 提升性能——例如对常见问题预生成答案片段缓存，对图谱的复杂关系计算离线预跑定期更新。这一切都基于我们不牺牲推理深度的前提：宁可通过硬件和软件优化来换取速度，也不降模型规模或精度标准。毕竟，管理层决策所依赖的是高度可靠和智能的分析结果，我们提供的技术栈正是为了在离线环境中逼近云端最强AI的水准，同时保持对数据的绝对掌控。不仅在理论上可行，我们给出的方案在组件上均已有成功实践的开源参考，实现起来有据可依[21][15]。这套全栈架构将最终产出一个本地最强、全面且鲁棒的“全息数据底座”，能够经受住工程落地的检验，真正为高层决策赋能。 (架构图：高价值离线B2B业务“全息数据底座”多模态数据流转及知识存储设计)
参考文献：
	•	Sun et al. Docs2KG: Unified Knowledge Graph Construction from Heterogeneous Documents Assisted by LLMs. arXiv, 2024[1][2][8][9]等
	•	Peng et al. Graph Retrieval-Augmented Generation: A Survey. arXiv, 2024[16][17].
	•	Luo et al. HyperGraphRAG: Hypergraph-Structured Knowledge for RAG. NeurIPS, 2025[3][42].
	•	AWS Blog. Improving RAG accuracy with GraphRAG. 2024[24][41].
	•	Telicent Blog. Event-Driven Knowledge Graphs. 2024[15][5].
	•	Neo4j Blog. Data Lineage: Storing & Analyzing with Knowledge Graphs. 2025[14].
	•	Milvus Q&A. Ensure Data Consistency in a Knowledge Graph. 2023[26].
	•	Amazon Science. Confidence scoring for LLM-generated SQL. 2025[27][28].
	•	Bruno Gonzalez. Open-Source Data Quality Tools (2023)[32]. (其余文献略)

[1] [12] Docs2KG: Unified Knowledge Graph Construction from Heterogeneous Documents Assisted by Large Language Models
https://arxiv.org/html/2406.02962v1
[2] [8] [9] [10] [11] [13] [18] [19] [20] [21] [22] [23] [2406.02962] Docs2KG: Unified Knowledge Graph Construction from Heterogeneous Documents Assisted by Large Language Models
https://ar5iv.labs.arxiv.org/html/2406.02962v1
[3] [4] [42] HyperGraphRAG: Retrieval-Augmented Generation via Hypergraph-Structured Knowledge Representation | OpenReview
https://openreview.net/forum?id=ravS5h8MNg
[5] [15] Event-Driven Knowledge Graphs - Telicent
https://telicent.io/news/event-driven-knowledge-graphs/
[6] [7] Docs2KG by AI4WA
https://docs2kg.ai4wa.com
[14] [33] What Is Data Lineage? Tracking Data Through Enterprise Systems
https://neo4j.com/blog/graph-database/what-is-data-lineage/
[16] [17] [24] [25] [41] Improving Retrieval Augmented Generation accuracy with GraphRAG | Artificial Intelligence
https://aws.amazon.com/blogs/machine-learning/improving-retrieval-augmented-generation-accuracy-with-graphrag/
[26] [30] [31] [39] [40] How do you ensure data consistency in a knowledge graph?
https://milvus.io/ai-quick-reference/how-do-you-ensure-data-consistency-in-a-knowledge-graph
[27] [28] Confidence scoring for LLM-generated SQL in supply chain data extraction - Amazon Science
https://www.amazon.science/publications/confidence-scoring-for-llm-generated-sql-in-supply-chain-data-extraction
[29] Why Provenance is the Key to AI Success: Knowledge Graph Ontology Design | by ODSC - Open Data Science | Medium
https://odsc.medium.com/why-provenance-is-the-key-to-ai-success-knowledge-graph-ontology-design-8baa83554ccb
[32] A guide to open-source data quality tools in late 2023 | by Bruno Gonzalez | Medium
https://medium.com/@brunouy/a-guide-to-open-source-data-quality-tools-in-late-2023-f9dbadbc7948
[34] QwenLM/Qwen3-VL - GitHub
https://github.com/QwenLM/Qwen3-VL
[35] Qwen VLo
https://qwen.ai/blog?id=5a32ae43df17771e727c3c30112ae2ab8233e399
[36] deepseek-ai/DeepSeek-V3 - Hugging Face
https://huggingface.co/deepseek-ai/DeepSeek-V3
[37] DeepSeek v3 - Advanced AI & LLM Model Online
https://deepseekv3.org/
[38] Deepseek-v3 vs other LLMs: what's different
https://nebius.com/blog/posts/deepseek-v3-vs-other-llms
