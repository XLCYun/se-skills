# 输出 Schema

本文件定义落盘 `.json` 的最终结构。**子代理不手写这些 JSON**：先按 [rec-format.md](rec-format.md) 写 `.rec` 中间格式，由 `scripts/emit_json.py` 组装、校验并序列化成本文件定义的结构。字段名、枚举值严格按本文件，`validate_json.py` / `aggregate.py` 会再次校验，不合法的文件整体拒收（重派生产者，不做启发式修复）。

## 1. 分片审查输出（Phase 2，每分片一个文件）

路径：`<工作区>/findings/shard-<id>.json`

```json
{
  "shard_id": "shard-03",
  "agent_role": "shard-review",
  "findings": [
    {
      "item_id": "STR-03",
      "item_name": "过大的类",
      "file": "src/main/java/com/x/service/FileService.java",
      "lines": [40, 620],
      "unit": "FileService",
      "unit_type": "class",
      "severity": "high",
      "confidence": "high",
      "evidence": "580 NLOC、31 个方法；同时承担上传分片、配额计算、回收站策略与缩略图生成四类职责（观察事实）。lizard 报告其 upload() 圈复杂度 34。",
      "impact": "四类无关变更都汇聚于此，改动互相冲突风险高。",
      "refactoring": "按职责抽取 QuotaService、TrashPolicy、ThumbnailService。",
      "metric": {"nloc": 580, "methods": 31, "fields": 18, "max_ccn": 34}
    }
  ],
  "summary": [
    {
      "unit": "FileService",
      "unit_type": "class",
      "file": "src/main/java/com/x/service/FileService.java",
      "nloc": 580,
      "fields": [{"name": "quotaCache", "type": "Map<Long,Long>", "static": false, "mutable": true}],
      "methods": [{"name": "upload", "params": ["userId:Long", "file:MultipartFile", "isPublic:boolean"], "returns": "FileVO", "visibility": "public"}],
      "param_clusters": [["userId", "fileId", "versionId"]],
      "dispatch_points": [{"variable": "file.getType()", "kind": "switch", "branches": 5, "line": 210}],
      "dependencies": ["UserRepository", "StorageClient", "QuotaUtil"]
    }
  ],
  "coverage": {
    "assigned": ["FileService", "FileController", "FileVO"],
    "reviewed": ["FileService", "FileController", "FileVO"],
    "skipped": [],
    "drilldown": []
  }
}
```

要点：

- `findings` 只含判定为"存在"的项；`coverage.reviewed` 必须等于 `assigned` 减 `skipped`——这是普查协议的凭证
- `severity` ∈ `high|medium|low`；`confidence` ∈ `high|medium`（低置信发现直接省略，不输出）
- `evidence` 必须区分观察事实与推断；A 档确认项在 `metric` 中带工具数字
- `unit_type` ∈ `class|function|module|file`
- `summary` 覆盖分片内**每个类**（含未报 finding 的），Phase 3 依赖其完整性
- `skipped` 每项 `{"unit": "...", "reason": "..."}`

## 2. 跨文件审查输出（Phase 3，每检查项一个文件）

路径：`<工作区>/findings/cross-<item_id>.json`

结构同上，另加约束：

- `agent_role`: `"cross-file-review"`
- finding 中 `related[]` 字段必填：列出构成该跨文件模式的所有位置 `[{"file": "...", "unit": "...", "lines": [..]}]`
- `coverage.drilldown` 记录每次源码/文档精读：`{"path": "...", "reason": "摘要中 OrderDTO 与 OrderVO 字段重合度 90%，需确认是否分层约定"}`，上限 10 条

## 3. 整体评级输出（Phase 4）

路径：`<工作区>/ratings.json`

```json
{
  "agent_role": "holistic-rating",
  "ratings": [
    {
      "item_id": "CHG-03",
      "item_name": "结构混乱度",
      "score": 3,
      "anchor": "个别模块跨层调用，部分业务逻辑无明确归属",
      "evidence": "FileController 直接注入 FileMapper 绕过 Service（file/FileController.java:35）；配额校验逻辑同时出现在 Controller 与 Interceptor。",
      "walkthrough": "追踪『上传一个文件』路径：Controller→Util→静态工具→Mapper，跨 4 文件且两次绕过 Service 层。"
    }
  ],
  "coverage": {"files_read": ["..."], "drilldown": [], "sampled_files": ["..."]}
}
```

- `score` 为 0–5 整数；`anchor` 必须摘抄 checklist 该项锚点原文（证明对表打分）
- 6 项必须全部出现：CHG-01、CHG-02、CHG-03、OVR-01、ENG-01、CPL-06

## 4. 汇总输出（Phase 5，脚本产出）

`<工作区>/report.json`（供横向对比拼接）：

```json
{
  "target": "group4_backend-master",
  "kloc": {"source": 12.4, "test": 3.1},
  "coverage_audit": {"assigned": 182, "reviewed": 182, "skipped": 0, "pass": true},
  "findings_total": {"high": 6, "medium": 21, "low": 9},
  "density_by_dimension": {"结构": 2.1, "重复": 1.4},
  "scores_by_dimension": {"结构": 74, "重复": 83, "变更边界": 60},
  "ratings": {"CHG-01": 3, "CHG-02": 4, "CHG-03": 3, "OVR-01": 4, "ENG-01": 5, "CPL-06": 3},
  "total_score": 71.6,
  "top_findings": ["..."]
}
```

同时产出人读的 `report.md`：总分与维度表 → 按严重级别排序的发现（含证据）→ C 档评分与走查记录 → 覆盖审计与工具可用性说明 → 按执行顺序排列的整改待办。
