---
name: code-quality-audit
description: 可量化的代码质量审计。合并重构坏味道与软件反模式视角（31 项检查项，去重后统一分类），通过"确定性分派 + 多子代理普查 + 结构摘要 map-reduce"对整个仓库做可审计覆盖的深度审查，输出机器可读的 findings.json、覆盖回执、维度分数向量与加权总分。适用于审查仓库、子系统、多项目横向对比（如多个团队的作业评估），需要可比较、可复现的量化结论时优先使用本 skill 而不是纯叙述式审查。
---

# 代码质量审计（可量化）

## 设计原则

1. **探索变分派**：不让 LLM 自由探索仓库。由脚本枚举出完整的审查单元清单（分母），切片后以封闭必读清单分派给子代理。覆盖率 = 已核对单元 / 分派单元，是可审计的数字。
2. **计数交给工具，判断交给 LLM**：A 档检查项由静态工具计数，LLM 只确认与解释；B 档由 LLM 按操作化判据逐单元核对；C 档由 LLM 按锚定量表做整体评分。
3. **不确定性只允许存在于 LLM 单次判定本身**：分派、覆盖核对、去重、评分公式全部固化在脚本中。

## 前置阅读

- [references/checklist.md](references/checklist.md) — 31 项检查项：定义、档位、判定标准/评分锚点、边界规则
- [references/output-schema.md](references/output-schema.md) — findings、结构摘要、覆盖回执、评分的 JSON schema
- [references/rec-format.md](references/rec-format.md) — 子代理落盘用的 `.rec` 中间格式：LLM 不手写 JSON，写 `.rec` 后由 `emit_json.py` 序列化
- [references/scoring.md](references/scoring.md) — 归一化公式与默认权重

## 五阶段流程

```
Phase 0  清单构建（脚本，主循环执行）
Phase 1  工具层（脚本，主循环执行）
Phase 2  分片审查（N 个并行子代理：B 档单元级普查 + 结构摘要）
Phase 3  跨文件审查（专项子代理：基于结构摘要判定跨文件项）
Phase 4  整体评级（1 个子代理：C 档 6 项锚定评分）
Phase 5  汇总（脚本，主循环执行：去重、覆盖审计、算分、出报告）
```

### Phase 0 — 清单构建

```bash
python3 scripts/build_manifest.py <目标仓库路径> --out <工作区>/manifest.json
```

产出 `manifest.json`：源文件清单（路径、语言、LOC、是否测试）、审查单元索引（类/函数）、分片方案（默认每片 ≤ 2000 LOC，测试文件独立分片）、入口点与文档清单。

### Phase 1 — 工具层

```bash
bash scripts/run_tools.sh <目标仓库路径> <工作区>
```

按可用性运行 cloc / lizard / jscpd / semgrep，结果写入 `<工作区>/tools/`。缺失的工具记录在 `tools_report.json` 中并降级（对应 A 档项转由分片代理人工核对，置信度上限为"中"）。

### Phase 2 — 分片审查（map）

对 manifest 中每个分片派发一个子代理。**每个分片代理的输入**：

- 该分片的必读文件清单（封闭，禁止跳过）
- 该分片文件的工具指标摘录（lizard 复杂度、jscpd 重复块）
- checklist.md 中的 B 档单元级项 + A 档确认协议

**每个分片代理的输出**（先写 `<工作区>/findings/shard-<id>.rec`，再运行 `emit_json.py` 生成同名 `.json`；`.rec` 格式见 rec-format.md，最终 schema 见 output-schema.md）：

1. `findings[]` — 逐单元核对结果，只含"存在"的项，但 `coverage.reviewed` 必须列出所有已核对单元（普查协议：对每个单元每个适用项做出 存在/不存在/不适用 判断）
2. `summary[]` — 该分片每个类的结构摘要（字段表、方法签名、参数组合、条件分发点、出向依赖），供 Phase 3 使用
3. `coverage` — 覆盖回执：assigned / reviewed / skipped（含原因）

测试分片代理改用 TST-01/02/03 三项协议，输入额外包含源码 API 摘要（若 Phase 2 源码分片已完成）或 manifest 的单元索引。

### Phase 3 — 跨文件审查（reduce）

对以下跨文件项各派发一个专项子代理：**DUP-02 重复的条件分发、DUP-03 平行类、NAM-03 数据泥团、CPL-05 中间人、CPL-03 依恋情结（跨模块部分）**。

输入：全部分片的 `summary[]` + manifest 的目录树。

**下钻规则**：摘要有歧义或需要意图佐证时，允许精读源码文件与项目文档（README、设计文档、API 文档），但：

- 每个专项代理精读上限 10 个文件；超限时对应 finding 标 `confidence: 中` 并在 evidence 中说明证据缺口
- 所有下钻读取记录在 `coverage.drilldown[]`（路径 + 原因），保证证据链可审计

输出同样经 `.rec` → `emit_json.py` 落盘为 `<工作区>/findings/cross-<item>.json`。

### Phase 4 — 整体评级

单个子代理对 C 档 6 项评分：**CHG-01 发散式变化、CHG-02 霰弹式修改、CHG-03 结构混乱度、OVR-01 推测性泛化、ENG-01 重复造轮子、CPL-06 内幕交易**。

输入配方（全局视野 + 有代表性细读）：

1. 目录树与 manifest（全局骨架）
2. 全部分片结构摘要（全局语义地图）
3. 工具指标（复杂度分布、重复率）
4. 精读：入口点、最大的 3 个类、复杂度 top-5 文件、随机抽 2 个普通文件（按文件路径字母序取第 1 和中位那个，保证可复现）

同样适用下钻规则（上限 10 个额外文件）。输出经 `.rec` → `emit_json.py` 落盘为 `<工作区>/ratings.json`：每项 0–5 整数分 + 锚点引用 + 证据。

### Phase 5 — 汇总

```bash
# 安全网：纯校验（不修复）。不合法的文件 = 重派对应子代理重写其 .rec 并重新 emit，不得手工/脚本修补
python3 scripts/validate_json.py <工作区>/findings/ <工作区>/ratings.json
python3 scripts/aggregate.py <工作区> [--weights <权重覆盖.json>]
```

`validate_json.py` 对每个文件做 `json.loads` + 角色 schema 校验，合法文件规范化重写（`json.dump`），**不合法的文件只报错绝不猜测式修复**——只有生产者子代理拥有还原原文所需的语义知识，校验失败必须重派该子代理。aggregate.py 执行：schema 校验 → 按 `(item_id, file, unit)` 去重 → 覆盖审计（有缺口则退出码 2 并列出缺口单元，需重派后重跑）→ 计算加权发现密度 → 维度分数 → 加权总分 → 产出 `report.json` 与 `report.md`。

## 编排方式

**优先**：使用 Workflow 工具执行 [workflow.js](workflow.js)（参考实现）。主循环先跑完 Phase 0/1，把 manifest、分片清单、工作区路径通过 `args` 传入；workflow 内部完成 Phase 2/3/4 并把 findings 文件落盘；主循环最后跑 Phase 5。

**退化路径**：环境无 Workflow 时，主代理用 Agent 工具按同一协议派发——分片清单仍来自 `build_manifest.py` 输出，每个子代理的 prompt 必须包含：封闭必读清单、对应检查项协议全文或路径、输出 schema、落盘路径。汇总仍必须经过 `aggregate.py` 的覆盖率校验，校验不过必须重派缺口，不得手工放行。

**子代理 prompt 纪律**（两种编排方式通用）：

- 必读清单是封闭的：不读完不允许返回；确实无法读取的文件记入 `coverage.skipped` 并给原因
- **不要手写 JSON 文件**（LLM 手写 JSON 迟早在引号/反斜杠/换行上产生非法文件）。先把结果写成 `<输出路径>.rec`（格式见 references/rec-format.md：prose 字段放 `<<< >>>` 原文块，任何引号原样书写，无需转义），然后运行 `python3 scripts/emit_json.py <输出路径>.rec` 生成合法 `.json`；非 0 退出时按报错行号修正 `.rec` 重跑，直到通过。序列化永远由脚本完成
- 输出内容必须符合 output-schema.md（emit_json.py 会校验必填字段与枚举值），不写叙述性总结
- 只报告有证据的"存在"，禁止推测性发现；证据不足时用 confidence 表达而不是省略字段

## 评分与权重

见 [references/scoring.md](references/scoring.md)。默认维度权重（调用方可通过 `--weights` 覆盖）：

结构 18 / 重复 10 / 耦合 14 / 命名与领域建模 10 / 变更边界 10 / 过度设计 5 / 死代码 4 / 配置卫生 10 / 工程判断 4 / 测试质量 15（合计 100，分数越高质量越好）。

## 多项目横向对比

对每个项目独立跑完五阶段后，将各项目 `report.json` 中的指标向量（总分、维度分、加权发现密度、C 档评分）拼接成对比矩阵。因为分母（审查单元）由同一脚本枚举、判据与公式相同，横向比较是公平的。

## 不要做什么

- 不要让子代理"自行探索仓库"替代封闭必读清单
- 不要让子代理手写 JSON，也不要用启发式脚本"猜修"不合法的 JSON——校验失败只能重派生产者
- 不要把工具可计数的 A 档项交给 LLM 数数
- 不要在覆盖审计不通过时手工放行
- 不要把 lint 级样式问题报告为发现
- 不要对同一现象在多个检查项下重复计分（边界规则见 checklist.md 每项的"边界"字段）
- 无高置信度发现时直接说明，并报告覆盖范围
