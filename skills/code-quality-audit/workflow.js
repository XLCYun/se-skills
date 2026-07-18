// code-quality-audit 的 Workflow 参考实现（Phase 2/3/4）。
// 前置：主循环已完成 Phase 0/1（build_manifest.py + run_tools.sh），并通过 args 传入：
//   args = {
//     workspace: "<工作区绝对路径>",          // 含 manifest.json、tools/
//     skillDir:  "<skill 目录绝对路径>",       // 含 references/、scripts/
//     shards:    [{id, kind, files: [...], loc, units}, ...]   // 取自 manifest.shards
//   }
// 后置：主循环运行 aggregate.py 完成 Phase 5；若退出码 2（覆盖缺口），
// 用 resumeFromRunId 重跑本 workflow——未变更的 agent 调用会命中缓存，只有缺口分片重跑。

export const meta = {
  name: 'code-quality-audit',
  description: '可量化代码质量审计：分片普查 -> 跨文件审查 -> 整体评级',
  phases: [
    { title: '分片审查', detail: 'B 档逐单元普查 + 结构摘要' },
    { title: '跨文件审查', detail: '基于结构摘要判定跨文件项' },
    { title: '整体评级', detail: 'C 档 6 项锚定评分' },
  ],
}

const { workspace, skillDir, repoRoot, shards } = args
if (!workspace || !skillDir || !repoRoot || !Array.isArray(shards) || shards.length === 0) {
  throw new Error('args 必须包含 workspace、skillDir、repoRoot、shards（来自 manifest.shards）')
}
// 可选：按阶段覆盖模型（额度受限时用小模型跑机械性强的阶段），如
// args.models = { shard: 'haiku', cross: 'sonnet', rating: 'sonnet' }；未指定则继承会话模型。
// 额度中断恢复：已落盘的 shard-*.json 无需重跑，重新调用时从 args.shards 中剔除即可。
const models = args.models || {}

const CHECKLIST = `${skillDir}/references/checklist.md`
const SCHEMA_DOC = `${skillDir}/references/output-schema.md`
const REC_DOC = `${skillDir}/references/rec-format.md`
const EMIT = `${skillDir}/scripts/emit_json.py`

const RESULT_SCHEMA = {
  type: 'object',
  required: ['output_path', 'findings_count', 'reviewed_count', 'skipped_count'],
  properties: {
    output_path: { type: 'string' },
    findings_count: { type: 'number' },
    reviewed_count: { type: 'number' },
    skipped_count: { type: 'number' },
  },
}

const commonRules = `
通用纪律：
- 先读 ${CHECKLIST}（判定标准与边界规则）、${SCHEMA_DOC}（最终输出结构）和 ${REC_DOC}（.rec 落盘格式），再开始审查。
- 只报告有证据的"存在"；证据不足直接省略，不输出 confidence 低的发现。
- evidence 必须区分观察事实与推断；不把 lint 级样式问题当发现。
- 同一现象按 checklist 边界规则归入最特异的一项，不重复计分。
- 不写叙述性总结；也不要手写 JSON 文件——序列化由脚本完成：
  先把结果写成 <目标json路径去掉.json>.rec（rec-format.md 的格式：prose 字段放 <<< >>> 原文块，引号/反斜杠原样书写不转义），
  再运行 python3 ${EMIT} <该.rec路径> 生成合法 .json；非 0 退出时按报错行号修正 .rec 重跑，直到通过才允许返回。`

// ---------- Phase 2 分片审查 ----------
phase('分片审查')
log(`分派 ${shards.length} 个分片`)

const shardResults = await parallel(shards.map(s => () => agent(
  `你是代码质量审计的分片审查代理，执行 B 档逐单元普查。

工作区：${workspace}（tools/ 下有 lizard.csv、jscpd/、semgrep.json 等工具输出，先摘取与本分片文件相关的行作为线索与 A 档确认依据）。
目标仓库根目录：${repoRoot}（下方清单中的路径都相对于它）。

本分片（${s.id}，${s.kind === 'test' ? '测试分片：只执行 TST-01/02/03 三项，判定前先读 manifest.json 的 units 索引了解被测 API 面' : '源码分片：执行 checklist 中所有 B 档单元级项 + A 档确认'}）的必读文件清单（封闭，禁止跳过；确实读不了的记入 coverage.skipped 并给原因）：
${s.files.map(f => `- ${f}`).join('\n')}

对每个文件中的每个类/顶层单元，逐项核对适用的检查项（存在/不存在/不适用）。同时为每个类产出结构摘要（字段表、方法签名、参数组合、条件分发点、出向依赖）——下游跨文件审查完全依赖摘要的完整性，未报 finding 的类也必须有摘要。
${commonRules}

经 ${workspace}/findings/shard-${s.id}.rec + emit_json.py 产出 ${workspace}/findings/shard-${s.id}.json（结构见 output-schema.md 第 1 节，agent_role 填 "shard-review"，shard_id 填 "${s.id}"，coverage.assigned 填本清单全部单元）。返回 output_path（最终 .json 路径）与三个计数。`,
  { label: `shard:${s.id}`, phase: '分片审查', schema: RESULT_SCHEMA, model: models.shard },
)))

const failedShards = shards.filter((s, i) => !shardResults[i])
if (failedShards.length) {
  log(`警告：${failedShards.map(s => s.id).join(', ')} 未返回结果，aggregate.py 将在覆盖审计中报缺口`)
}

// ---------- Phase 3 跨文件审查 ----------
// 屏障是必要的：跨文件判定需要全部分片的结构摘要。
phase('跨文件审查')

const CROSS_ITEMS = [
  { id: 'DUP-02', name: '重复的条件分发' },
  { id: 'DUP-03', name: '接口不一致的平行类' },
  { id: 'NAM-03', name: '数据泥团' },
  { id: 'CPL-05', name: '中间人' },
  { id: 'CPL-03', name: '依恋情结（跨模块聚合复核）' },
]

const crossResults = await parallel(CROSS_ITEMS.map(item => () => agent(
  `你是代码质量审计的跨文件专项代理，只判定一项：${item.id} ${item.name}。

主输入：${workspace}/findings/ 下所有 shard-*.json 的 summary 数组（全仓结构摘要），以及 ${workspace}/manifest.json 的目录树信息。目标仓库根目录：${repoRoot}。先聚合摘要中与本项相关的信号（如 dispatch_points、param_clusters、方法签名重合、纯转发方法比例）。

下钻规则：摘要有歧义或需要意图佐证时，允许精读源码文件与项目文档（README、设计文档），上限 10 个文件；超限时对应 finding 标 confidence: medium 并在 evidence 说明证据缺口。每次下钻记入 coverage.drilldown（路径+原因）。
${commonRules}
- finding 必须带 related[] 字段，列出构成该跨文件模式的全部位置。

经 ${workspace}/findings/cross-${item.id}.rec + emit_json.py 产出 ${workspace}/findings/cross-${item.id}.json（结构见 output-schema.md 第 2 节，agent_role 填 "cross-file-review"）。返回 output_path（最终 .json 路径）与计数（reviewed_count 填聚合分析过的单元数）。`,
  { label: `cross:${item.id}`, phase: '跨文件审查', schema: RESULT_SCHEMA, model: models.cross },
)))

// ---------- Phase 4 整体评级 ----------
phase('整体评级')

const rating = await agent(
  `你是代码质量审计的整体评级代理，对 C 档 6 项做 0–5 锚定评分：CHG-01 发散式变化、CHG-02 霰弹式修改、CHG-03 结构混乱度、OVR-01 推测性泛化、ENG-01 重复造轮子、CPL-06 内幕交易。

目标仓库根目录：${repoRoot}。输入配方（按顺序消化）：
1. ${workspace}/manifest.json —— 目录树骨架、入口点、文档清单
2. ${workspace}/findings/shard-*.json 的 summary —— 全仓语义地图
3. ${workspace}/tools/ —— 复杂度分布与重复率
4. 精读：全部入口点文件、NLOC 最大的 3 个类、lizard 复杂度 top-5 文件、以及按文件路径字母序取第 1 个和中位第 1 个普通源文件（可复现的随机抽样）
5. ENG-01 判定前必须读 README 等文档，寻找自研的正当理由

下钻规则：上限额外 10 个文件，记录在 coverage.drilldown。
评分纪律：每项的 anchor 字段必须摘抄 ${CHECKLIST} 中该项锚点原文；CHG-02 需附一条假想变更的走查记录（walkthrough 字段）；CHG-03 附最难追踪路径的走查。评分基于证据而不是印象——引用具体文件与行为。

经 ${workspace}/ratings.rec + emit_json.py 产出 ${workspace}/ratings.json（结构见 output-schema.md 第 3 节，6 项缺一不可）。返回 output_path（最终 .json 路径）与计数（findings_count 填 0，reviewed_count 填精读文件数）。`,
  { label: 'holistic-rating', phase: '整体评级', schema: RESULT_SCHEMA, model: models.rating },
)

const ok = [...shardResults, ...crossResults, rating].filter(Boolean)
return {
  shards_done: shardResults.filter(Boolean).length,
  shards_total: shards.length,
  cross_done: crossResults.filter(Boolean).length,
  rating_done: !!rating,
  total_findings: ok.reduce((n, r) => n + (r.findings_count || 0), 0),
  next: `先运行 python3 ${skillDir}/scripts/validate_json.py ${workspace}/findings/ ${workspace}/ratings.json 做纯校验（失败 = 重派对应子代理修正其 .rec 重新 emit，不得手工修补）；再运行 python3 ${skillDir}/scripts/aggregate.py ${workspace} 完成 Phase 5（退出码 2 = 覆盖缺口，用 resumeFromRunId 重跑缺口分片）`,
}
