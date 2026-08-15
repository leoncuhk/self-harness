# 06 — self-harness × FAB v2：可行性评估与融合构建方案

> 评估对象：`/Users/leon/Documents/harness/self-harness`（deepagents better-harness 的 fork + 严谨性层，L3 harness 自编辑，预注册制，MVP-1/2 均按停机规则终止、无疗效结论）
> 结论：**逻辑成立，且成立方式非常具体——两个项目恰好互为对方最大短板的解药。** 但有三条承重条件必须先满足。

## 一、为什么逻辑讲得通（三条链）

### 链 1：FAB v2 恰好治好 self-harness 的两个死因
| self-harness 的死因 | FAB v2 的对应性质 |
|---|---|
| MVP-1 死于测试床饱和（baseline 0.917，超出 [0.20,0.85] headroom 窗口） | 榜首才 60.6%，headroom 巨大，天然在窗口内 |
| MVP-2 死于诊断信号贫瘠（φ(r) 靠 pytest 断言文本正则，47% 失败指向不可编辑面，分类器还把列宽错误判成超时循环） | 本地判分器给出**判据级** pass/fail（239 条、73% 确定性数值轨、dealbreaker 显式标记）——box② 第一次拿到真诊断材料，比断言文本富集一个量级 |

他们的 roadmap B 项（经验可观测性——把执行轨迹喂给 proposer，"本文档中杠杆最大的改动"）在 FAB v2 上**几乎免费**：`model_library` 的 Agent 本来就把每个 turn 的 query、工具调用、state 快照全量落盘。他们缺的正好是我们有的。

### 链 2：打榜规则恰好废掉最强的否定先验
文献最大的负面结果（2607.12227）：等预算下 evolution 输给 best-of-N / sequential refinement。但 **FAB v2 官方协议 = 固定 harness、每题一个答案、3 次运行取均值**——best-of-N、自一致性、多采样选优全是违规操作。合法杠杆只剩：模型选择、推理参数、harness 质量（未来 custom-scaffold 通道开放后含编排）。**pass@1 的 harness 质量被协议放大为几乎唯一可操作的杠杆**——这正是 self-harness 优化 的东西。（内部诚实声明仍要跑 sequential-refinement 对照臂。）

### 链 3：正面先验的要求 FAB v2 全部满足
2026 文献的共识：正面结果 = **trace-grounded 诊断 × 结构面编辑**（AHE 的增益定位于 tools/middleware/memory 而非 prompt；SE-Agent 轨迹优化 +55% 相对提升；Strands Harness Optimizer 自动优化 prompt/工具文档/skills）。我们的 Wave 1 已实证：36% 的数值类 dealbreaker 挂在**口径约定**上，人工编码（V2 prompt）即巨大杠杆。self-harness 要自动化的正是"发现新口径 → 编码 → 防回归"这个我们手动做过一轮的循环——**不是赌未证实机制，是把已证实的杠杆系统化收割**。

## 二、断裂点与对策（诚实清单）

| # | 断裂点 | 对策 | 何时解决 |
|---|---|---|---|
| 1 | **27 题养不起统计功效**（±3.7pp/题波动，切分后 CI 更宽） | 授权 450 题：类别分层切 250 train / 100 holdout / 100 scorecard；授权前 27 题只做 smoke 级验证（15/6/6），不做疗效声明 | Phase 1（授权后） |
| 2 | **27% 定性判据需 LLM 裁判**，违反其"裁判零 LLM"铁律 | 裁判=冻结的 LLM（模型+prompt+温度固定即 frozen evaluator）；**晋升决策门只用 73% 确定性数值轨**，LLM 轨只做参考报告 | Phase 0 设计即定 |
| 3 | **成本爆炸**（他们 320 次 rollout×17k token 的预算在 FAB v2 只够跑 2-3 题） | 工具结果缓存（已建 .cache/）＋分层子采样迭代（每轮只跑失败簇相关题）＋他们 A2 的 checkpoint/resume ＋ cost veto 限 token/题 | Phase 0-2 |
| 4 | **他们自己的负面记录**：唯一一个已评分预测 precision 0.200 < base rate 0.286；proposer 上下文膨胀到 78k token 拖死传输 | bounded proposer context（每失败簇 1 条代表轨迹，他们已注册为 MVP-3 修复项）；ledger 持续读数，precision 连续 ≤ base rate 即停 | Phase 2 |
| 5 | **判据泄题**（prompt 学到 rubric 原文 = 对基准作弊） | guard 升级：`case_id_leak` 的语义版——扫描候选 prompt 与全部判据文本的 n-gram 重叠，超阈值即拒（把我们"不硬编码判据"的纪律代码化） | Phase 0 |

## 三、构建方案

### Phase 0 — 适配器（现在即可动工，零授权依赖）
1. **Runner 适配**：`Fabv2Runner implements collect_inventory/run`——每 case 一道题，调 `finance-agent --questions ... --log-dir`，产出 `final_answer` + 逐题 turn 目录；失败分类沿用其 apparatus 分区（sec.gov 限流=environment_caused）
2. **Evaluator 适配**：冻结版 `judge.py`（确定性数值轨出 pass/fail + dealbreaker 标记；φ(r)= (类别, 判据, 数值锚点 miss 模式)）
3. **Surface**：`SYSTEM_PROMPT`（Track A）/ + `get_agent` 编排 overlay（Track B，等官方 custom-scaffold 通道）
4. **Guards**：rubric-leak 扫描 + surface_bloat（prompt 字节预算）+ cost veto（token/题上限）
5. **基线族**：B0=官方原 prompt；**B5=我们的 SYSTEM_PROMPT_V2**（"成熟 harness、零进化"的诚实起点——比文献里的基线强得多）；B1=best-of-N（仅内部对照，打榜非法）；SR=顺序自检修正（合法性最好的强臂：教 agent 在提交前用 calculator 自验数值链）
6. 27 题分层切 15/6/6，smoke 级：只验证管线，不做任何疗效声明

### Phase 1 — 授权后扩容
450 题类别分层重切；headroom 复测（应落在窗口内）；正式预注册（主终点=dealbreaker 通过率，停机规则，scorecard 只开封一次）

### Phase 2 — 跑环（他们的 A→B 我们 nearly-free）
proposer 输入 = 编辑面当前值 + 判据级失败签名 + **每簇一条代表轨迹**（bounded）；K 候选按目标分派（去约束/加自验/加检索策略）；保守门（Δ_train≥0 ∧ Δ_hold≥0 ∧ max>0）+ cost veto；ledger 记录每条预测

### Phase 3 — 验证阶梯（照搬其 L0-L5）
1. 进化 harness vs B5（V2）vs B0 在 holdout 上，bootstrap CI
2. SR 等预算对照（诚实臂）
3. scorecard 一次开封
4. 跨模型迁移（在模型 X 上进化，模型 Y/Z 上受益？——updater×beneficiary 矩阵）
5. 增益集中度检查（不许 2-3 题贡献全部增益）

## 四、预注册的疗效判据（建议值）
- 主终点：数值轨 dealbreaker 通过率，进化 vs B5 ≥ +8pp 且 95% CI 不含 0（450 题下 CI 半宽约 ±4pp，+8pp 是可分辨的最小有意义增益）
- 机制证据：ledger precision 持续 > base rate（"工程而非搜索"）
- 红线：任何未预测回归逃过 gate 两次 → 停机复核；rubric-leak guard 触发 → 候选作废

## 五、诚实的收益预期
文献坐标：人工 harness 工程 +13.7pt（LangChain，TB）；自动化 self-harness 公开最好 +2/127 任务（NVIDIA）。我们已有"人工版"（V2 prompt，Wave 1 答案感知证据支撑）。self-harness 的期望增值 = **在 450 题规模上持续人工无法坚持的迭代 + gate/ledger 防回归纪律**，保守预期 +3-8pp（对 60.6% 榜首即进入 65-70% 区间）。若 Phase 2 后 precision 仍 ≤ base rate，按他们自己的话："这是可报告的结果，而不是继续调参的理由"——届时回退到人工迭代轨道，B5（V2）就是交付物。

## 参考链接
- [Self-Harness (2606.09498)](https://arxiv.org/html/2606.09498v1) · [Lil'Log harness engineering](https://lilianweng.github.io/posts/2026-07-04-harness/) · [Meta-Harness](https://yoonholee.com/meta-harness/) · [Strands Harness Optimizer](https://strandsagents.com/blog/introducing-harness-optimizer/) · [LangChain harness engineering](https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering) · [自进化 agent 分类学](https://lsl.zone/blog/2026/a-taxonomy-of-self-evolving-agents/) · [Evo-Memory](https://arxiv.org/html/2511.20857v2)
