# .rec 中间格式

**为什么存在**：LLM 是文本生成器，不是 JSON 序列化器——手写 JSON 时 evidence 里的引号、反斜杠、换行迟早会产生非法文件。因此子代理**不直接写 JSON**：先把结果写成 `.rec`（本格式没有转义概念，所有文本原样书写），再运行 `emit_json.py` 由真正的序列化器生成合法 JSON。

## 工作流

```bash
# 1. 用 Write 工具写 <输出路径>.rec（如 findings/shard-03.rec）
# 2. 转换（默认输出同名 .json）：
python3 <skill目录>/scripts/emit_json.py <输出路径>.rec
# 3. 非 0 退出 = 解析/校验失败，按报错行号修正 .rec 后重跑，直到通过
```

## 语法（就 3 条规则）

1. **Section 头**：`=== NAME ===` 独占一行。可用：`DOC`、`FINDING`、`SUMMARY`、`RATING`、`SKIPPED`、`DRILLDOWN`、`COVERAGE`，文件最后必须以 `=== END ===` 结尾（用于检测截断）。同名 section 可重复出现（每个 FINDING/SUMMARY/RATING/SKIPPED/DRILLDOWN 一段）。
2. **单行字段**：`key: value`。value 先按 JSON 解析（数字、数组、对象、布尔都写 JSON 字面量，如 `lines: [40, 620]`、`metric: {"nloc": 580}`），解析失败则按原样字符串处理（如 `severity: high`、`file: src/a/B.java`）。
3. **多行原文块**：`key <<<` 起、独占一行的 `>>>` 止，块内内容**完全原样**——任何引号、反斜杠、代码片段都不需要转义。prose 字段（`evidence`、`impact`、`refactoring`、`anchor`、`walkthrough`、`reason`）必须用块或单行原文，永远不会被当作 JSON 解析。唯一的边界情况：块内某行恰好是 `>>>` 时，写成 ` >>>`（前置一个空格），转换器会还原。

同一 section 内字段不得重复。空行随意。

## 分片 / 跨文件审查文档（agent_role: shard-review | cross-file-review）

```
=== DOC ===
shard_id: shard-03
agent_role: shard-review

=== FINDING ===
item_id: STR-03
item_name: 过大的类
file: src/main/java/com/x/service/FileService.java
lines: [40, 620]
unit: FileService
unit_type: class
severity: high
confidence: high
metric: {"nloc": 580, "methods": 31, "fields": 18, "max_ccn": 34}
evidence <<<
580 NLOC、31 个方法；同时承担上传分片、配额计算、回收站策略与缩略图生成
四类职责（观察事实）。代码中有 type="chunk" 与 "$.data.items" 这类引号，
原样写即可。lizard 报告其 upload() 圈复杂度 34。
>>>
impact <<<
四类无关变更都汇聚于此，改动互相冲突风险高。
>>>
refactoring <<<
按职责抽取 QuotaService、TrashPolicy、ThumbnailService。
>>>

=== SUMMARY ===
file: src/main/java/com/x/service/FileService.java
language: java
classes: [{"name": "FileService", "methods": ["upload"]}]
functions: [{"name": "upload", "params": ["userId", "file"], "returns": "FileVO"}]
param_clusters: [["userId", "fileId", "versionId"]]
dispatch_points: [{"variable": "file.getType()", "kind": "switch", "branches": 5, "line": 210}]
dependencies: ["UserRepository", "StorageClient", "QuotaUtil"]
delegations: [{"from": "upload", "to": "StorageClient.put"}]

=== SKIPPED ===
unit_id: src/main/java/com/x/LegacyUtil.java::class::LegacyUtil@10
reason <<<
文件编码损坏，无法读取
>>>

=== DRILLDOWN ===
path: src/main/java/com/x/dto/OrderDTO.java
reason <<<
摘要中 OrderDTO 与 OrderVO 字段重合度 90%，需确认是否分层约定
>>>

=== COVERAGE ===
assigned: ["src/main/java/com/x/service/FileService.java::class::FileService@40", "src/main/java/com/x/LegacyUtil.java::class::LegacyUtil@10"]
reviewed: ["src/main/java/com/x/service/FileService.java::class::FileService@40"]

=== END ===
```

要点：

- 结构化子对象（`metric`、`fields`、`methods`、`related` 等，内容是标识符和数字，无引号碰撞风险）用单行 JSON 字面量；prose 用原文块——引号风险被隔离在原文块里
- 每个 SKIPPED / DRILLDOWN 各占一个 section；无跳过/无下钻则不写
- `COVERAGE` 的 `assigned` / `reviewed` 必须原样使用 manifest 的完整 unit_id；源码分片每个文件一条 SUMMARY，测试分片不写 SUMMARY
- 跨文件文档（cross-file-review）：无 `shard_id`；FINDING 内必须有 `related: [{"file": "...", "unit": "...", "lines": [10, 20]}]`
- 转换器会校验必填字段与枚举值（severity ∈ high|medium|low 等），报错逐条列出

## 整体评级文档（agent_role: holistic-rating）

```
=== DOC ===
agent_role: holistic-rating

=== RATING ===
item_id: CHG-03
item_name: 结构混乱度
score: 3
anchor <<<
个别模块跨层调用，部分业务逻辑无明确归属
>>>
evidence <<<
FileController 直接注入 FileMapper 绕过 Service（file/FileController.java:35）。
>>>
walkthrough <<<
追踪『上传一个文件』路径：Controller→Util→静态工具→Mapper，跨 4 文件且两次绕过 Service 层。
>>>

=== COVERAGE ===
files_read: ["src/main/java/com/x/Main.java"]
sampled_files: ["src/main/java/com/x/config/CacheConfig.java"]

=== END ===
```

6 个 RATING section 缺一不可（CHG-01/02/03、OVR-01、ENG-01、CPL-06），`score` 为 0–5 整数。下钻仍用 DRILLDOWN section。

最终 `.json` 的完整结构定义见 [output-schema.md](output-schema.md)——`.rec` 只是书写载体，`emit_json.py` 负责组装成该 schema。
