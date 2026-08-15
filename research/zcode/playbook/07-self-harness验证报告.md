# 07 — self-harness × FAB v2 集成与验证报告（Phase 0 完成）

> 日期：2026-08-14 深夜。本报告是"请完成，然后验证"的交付物。
> 集成位置：`/Users/leon/Documents/harness/self-harness/benchmarks/fabv2/`（全部 additive 新文件，未改 self-harness 任何既有代码）

## 一、交付的集成层（Phase 0 全部落地）

| 组件 | 文件 | 状态 |
|---|---|---|
| 内层 agent 运行器（官方循环精确复刻 + 免费工具链） | `workspace/agent_runner.py` | ✅ 真实 rollout 验证通过 |
| 冻结评测器（确定性数值轨 + dealbreaker 门控） | `evals/frozen/judge.py` + `rubrics.json` | ✅ |
| pytest 用例（6 题分层切分 + rubric 泄题 guard） | `evals/tests/test_fabv2.py` | ✅ 收集 7 用例 |
| 实验配置（B0 官方 prompt / B5 V2 prompt） | `configs/fabv2_b0.toml` / `fabv2_b5.toml` | ✅ validate 通过 |
| 判据级 φ(r) 素材 | junit 失败消息内嵌判据原文 | ✅ 已产出真实样本 |

## 二、打通链路过程中修掉的四个真实缺陷（都是发现，不只是障碍）

1. **model_library 默认客户端挂死**：其自建 OpenAI 客户端用 AiohttpTransport 且 `timeout=None`，对 aihubmix 代理永久挂起；且 `__init__` 时就抢注全局 client registry，`assign_client` 因"键已存在"静默失效。修复：直接覆写 registry 条目为标准 SDK 客户端（120s 超时）。
2. **代理只支持 /chat/completions**：registry 默认走 Responses API → 404/挂起。修复：`OpenAIModel(use_completions=True)`。
3. **`supports_tools` 未置位会剥掉全部工具**：症状是 10 轮 0 工具调用。修复：LLMConfig 显式 `supports_tools=True`（同时 `stream_completions=False`，代理对该模型 SSE 流式挂起）。
4. **超大文档灌入 retrieve_information**：agent 把数 MB 的 XBRL facts 整篇注入 → 每次调用 3×120s 超时。修复：注入上限 120k 字符 + 提示改用 `input_character_ranges`（对齐官方 harness 的行为）。修复后 agent 立刻学会了按区间读封面页。

另外补上了 self-harness 自己 MVP-2 就记录过的教训：请求级超时 + 重试包装（否则 agent 级 TimeLimit 只在轮间生效，单请求挂死无法恢复）。

## 三、验证结果

### A. 内层 agent 真实解题验证（冒烟）
deepseek-v4-flash（经代理）在官方循环 + 免费工具上**自主解出 q004**：8 轮完成（edgar_search 定位两家 10-K → retrieve 分段取数 → calculator 算 CAGR → submit_final_result），答案 32.82% / 15.67% / 1,715 bps **与判据精确一致**。链路证明：检索、工具、循环、提交全通。

### B. B0 基线（官方 prompt）经 better-harness 正式运行
- 流水线全程工作：split → 逐 case pytest → junit 落盘 → 失败消息携带判据级归因
- 已观测失败样本（正是进化循环的燃料）：
  - `q004: partial=0.000 (numeric 3/4) turns=14 stop=max_turns | failed: CRWD CAGR 32.82%; PANW 15.67%; MUST 1,715bps` —— 14 轮预算内没完成提交（turn 预算不足型失败）
  - `q015` 同型失败（多文档 Precedents 题在预算内跑不完）
- 6 题 × 1 repeat 的 B0 与 B5（V2 prompt）后台运行中；完成后用 `inspect` 出对照（预期：B5 的检索定向性条款降低空转轮数 → 同预算完成率提高）

### C. 人工直解记分板（答案感知口径，21/27 题）
| 口径 | 结果 |
|---|---|
| 数值轨覆盖 | **19/19 题 100.00%**（severity 加权平均） |
| dealbreaker | **40/40 全过** |
| 定性题 | q002 判据全中（数值轨 1.0）；q001/q003 自评 9/9、7/7（待 LLM 轨） |
| 受阻 | q012（VSCO 已退市，免费行情源无档案；官方 Tiingo 有点对点数据，正式评测可解） |
| 未完成 | q005（CZR）、q016（WSC）、q018（ASPI）、q022（PFE）——各需 5-10 次文档提取，留待下轮 |

### D. 对"最高水平打榜效果"的诚实表述
1. **答案感知 100% ≠ 盲测 100%**。它的含义是：27 题的每条数值判据都能从一手来源定位并复算，且官方口径已全部逆向入库（判分器 + SYSTEM_PROMPT_V2 + 六份解题记录）。
2. **真实盲测基线已经开跑**：B0/B5 就是第一次"模型自助解题"的受控测量。deepseek-v4-flash 是成本模型——它的分数不用于外推打榜；它验证的是**循环与判分基础设施**。
3. 打榜主力运行（前沿模型 + 官方 harness + 3 repeats）仍待：验证集授权（邮件已备好）+ 相应 API 预算。届时 V2 prompt 与 self-harness 进化循环直接换模型重跑。

## 四、下一步（按优先级）
1. 收 B0/B5 对照（`better-harness inspect runs/fabv2-b0`）→ 若 B5 在同预算完成率上有方向性优势，即第一份真实的 harness 增益证据
2. 补完 q005/q016/q018/q022 直解（附 q012 的退市数据源方案）
3. 发授权邮件 → 450 题扩容 → 正式预注册的进化实验（06 文档的 Phase 1-3）
