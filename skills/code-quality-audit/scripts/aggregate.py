#!/usr/bin/env python3
"""Phase 5：校验、去重、覆盖审计、算分、出报告。

用法: python3 aggregate.py <workspace> [--weights weights.json] [--target-name NAME]
输入:  <workspace>/manifest.json, findings/*.json, ratings.json, tools/tools_report.json(可选)
输出:  <workspace>/report.json, <workspace>/report.md
退出码: 0 成功；1 输入非法；2 覆盖审计不通过（重派缺口后重跑）。
"""
import argparse
import glob
import hashlib
import json
import os
import sys

SEVERITY_W = {"high": 5, "medium": 2, "low": 1}
CONFIDENCES = {"high", "medium"}
DIM_BY_PREFIX = {
    "STR": "结构", "DUP": "重复", "CPL": "耦合", "NAM": "命名与领域建模",
    "CHG": "变更边界", "OVR": "过度设计", "DED": "死代码", "CFG": "配置卫生",
    "ENG": "工程判断", "TST": "测试质量",
}
RATING_ITEMS = {"CHG-01", "CHG-02", "CHG-03", "OVR-01", "ENG-01", "CPL-06"}
REQUIRED_CROSS_ITEMS = {"CPL-03", "CPL-05", "DUP-02", "DUP-03", "NAM-03"}
DEFAULT_WEIGHTS = {
    "结构": 18, "耦合": 14, "测试质量": 15, "重复": 10, "命名与领域建模": 10,
    "变更边界": 10, "配置卫生": 10, "过度设计": 5, "死代码": 4, "工程判断": 4,
}
DEFAULT_DMAX = 8.0
REQUIRED_FINDING_FIELDS = ["item_id", "file", "unit", "severity", "confidence", "evidence"]


def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def load_json(path, required=True):
    if not os.path.exists(path):
        if required:
            die(f"missing input: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            die(f"invalid JSON in {path}: {e}")


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def validate_finding(f, src):
    for field in REQUIRED_FINDING_FIELDS:
        if field not in f or f[field] in (None, ""):
            die(f"{src}: finding missing field '{field}': {json.dumps(f, ensure_ascii=False)[:200]}")
    if f["severity"] not in SEVERITY_W:
        die(f"{src}: bad severity '{f['severity']}' (expect high|medium|low)")
    if f["confidence"] not in CONFIDENCES:
        die(f"{src}: bad confidence '{f['confidence']}' (expect high|medium; 低置信发现应省略)")
    prefix = f["item_id"].split("-")[0]
    if prefix not in DIM_BY_PREFIX:
        die(f"{src}: unknown item_id '{f['item_id']}'")
    if f["item_id"] in RATING_ITEMS:
        die(f"{src}: '{f['item_id']}' 是 C 档评级项，不应出现在 findings 中（应在 ratings.json）")


def duplicates(values):
    seen, repeated = set(), set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return sorted(repeated)


def coverage_audit(manifest, shard_files, cross_files, check_cross=True):
    """以 manifest 为唯一分母，双向核对 shard/cross coverage 与文件级 summary。"""
    shard_by_id = {s["id"]: s for s in manifest["shards"]}
    gaps, skipped_total, reviewed_total, assigned_total = [], 0, 0, 0
    seen_shards = set()
    all_expected = [unit_id for s in manifest["shards"] for unit_id in s.get("assigned_units", [])]
    duplicate_manifest_units = duplicates(all_expected)
    if duplicate_manifest_units:
        gaps.append({"kind": "duplicate_manifest_units", "unit_ids": duplicate_manifest_units})
    for path, data in shard_files:
        sid = data.get("shard_id", "?")
        if sid in seen_shards:
            gaps.append({"kind": "duplicate_shard_result", "shard": sid, "file": path})
            continue
        seen_shards.add(sid)
        cov = data.get("coverage") or {}
        if sid not in shard_by_id:
            gaps.append({"kind": "unknown_shard", "shard": sid, "file": path})
            continue
        expected_list = shard_by_id[sid].get("assigned_units", [])
        assigned_list = cov.get("assigned", [])
        reviewed_list = cov.get("reviewed", [])
        skipped_list = cov.get("skipped", [])
        skipped_ids = [s.get("unit_id") if isinstance(s, dict) else s for s in skipped_list]
        expected, assigned, reviewed, skipped = map(set, (
            expected_list, assigned_list, reviewed_list, skipped_ids))

        detail = {
            "kind": "shard_coverage_mismatch",
            "shard": sid,
            "missing_assigned": sorted(expected - assigned),
            "extra_assigned": sorted(assigned - expected),
            "missing_review": sorted(assigned - reviewed - skipped),
            "extra_reviewed": sorted(reviewed - assigned),
            "extra_skipped": sorted(skipped - assigned),
            "reviewed_and_skipped": sorted(reviewed & skipped),
            "duplicate_expected": duplicates(expected_list),
            "duplicate_assigned": duplicates(assigned_list),
            "duplicate_reviewed": duplicates(reviewed_list),
            "duplicate_skipped": duplicates(skipped_ids),
        }

        expected_summary = set(shard_by_id[sid].get("summary_files", []))
        summary_list = [s.get("file") for s in data.get("summary", []) if isinstance(s, dict)]
        actual_summary = set(summary_list)
        detail.update({
            "missing_summaries": sorted(expected_summary - actual_summary),
            "extra_summaries": sorted(actual_summary - expected_summary),
            "duplicate_summaries": duplicates(summary_list),
        })
        if any(value for key, value in detail.items() if key not in {"kind", "shard"}):
            gaps.append(detail)

        assigned_total += len(expected_list)
        reviewed_total += len(reviewed)
        skipped_total += len(skipped)
    missing_shards = sorted(set(shard_by_id) - seen_shards)
    if missing_shards:
        gaps.append({"kind": "missing_shards", "shards": missing_shards})

    if check_cross:
        all_source_files = {
            f["path"] for f in manifest.get("files", []) if not f.get("is_test")
        }
        cross_by_item = {}
        for path, data in cross_files:
            item = os.path.basename(path).removeprefix("cross-").removesuffix(".json")
            if item in cross_by_item:
                gaps.append({"kind": "duplicate_cross_result", "item": item, "file": path})
                continue
            cross_by_item[item] = data
            cov = data.get("coverage") or {}
            assigned_list = cov.get("assigned", [])
            reviewed_list = cov.get("reviewed", [])
            assigned, reviewed = set(assigned_list), set(reviewed_list)
            detail = {
                "kind": "cross_coverage_mismatch",
                "item": item,
                "missing_assigned": sorted(all_source_files - assigned),
                "extra_assigned": sorted(assigned - all_source_files),
                "missing_review": sorted(assigned - reviewed),
                "extra_reviewed": sorted(reviewed - assigned),
                "duplicate_assigned": duplicates(assigned_list),
                "duplicate_reviewed": duplicates(reviewed_list),
            }
            if any(value for key, value in detail.items() if key not in {"kind", "item"}):
                gaps.append(detail)
        missing_cross = sorted(REQUIRED_CROSS_ITEMS - set(cross_by_item))
        extra_cross = sorted(set(cross_by_item) - REQUIRED_CROSS_ITEMS)
        if missing_cross or extra_cross:
            gaps.append({"kind": "cross_files_mismatch", "missing": missing_cross, "extra": extra_cross})
    return {
        "assigned": assigned_total,
        "reviewed": reviewed_total,
        "skipped": skipped_total,
        "gaps": gaps,
        "pass": not gaps,
    }


def gap_report(coverage):
    retry_shards, retry_cross = set(), set()
    for gap in coverage["gaps"]:
        if gap.get("shard") and gap.get("kind") != "unknown_shard":
            retry_shards.add(gap["shard"])
        retry_shards.update(gap.get("shards", []))
        if gap.get("item"):
            retry_cross.add(gap["item"])
        if gap.get("kind") == "cross_files_mismatch":
            retry_cross.update(gap.get("missing", []))
    return {
        "status": "failed",
        "retryable": True,
        "retry_shards": sorted(retry_shards),
        "retry_cross": sorted(retry_cross),
        "gaps": coverage["gaps"],
    }


def dedupe(findings):
    seen, out, dropped = set(), [], 0
    for f in findings:
        key = (f["item_id"], f["file"], f["unit"])
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(f)
    return out, dropped


def compute(findings, ratings, manifest, weights, dmax):
    src_kloc = max(manifest["totals"]["source_loc"] / 1000.0, 0.001)
    test_kloc = manifest["totals"]["test_loc"] / 1000.0
    tst_kloc = test_kloc if test_kloc > 0 else src_kloc

    density, counts = {}, {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        dim = DIM_BY_PREFIX[f["item_id"].split("-")[0]]
        kloc = tst_kloc if dim == "测试质量" else src_kloc
        density[dim] = density.get(dim, 0.0) + SEVERITY_W[f["severity"]] / kloc
        counts[f["severity"]] += 1

    rating_by_item = {r["item_id"]: r["score"] for r in ratings}
    missing = sorted(RATING_ITEMS - set(rating_by_item))
    if missing:
        die(f"ratings.json 缺少 C 档评级项: {missing}")
    for item, score in rating_by_item.items():
        if not (isinstance(score, int) and 0 <= score <= 5):
            die(f"ratings: {item} 的 score 必须是 0-5 整数，得到 {score!r}")

    def s_density(dim):
        d = density.get(dim, 0.0)
        return 100.0 * max(0.0, 1.0 - d / dmax.get(dim, DEFAULT_DMAX))

    scores = {}
    for dim in ("结构", "重复", "命名与领域建模", "死代码", "配置卫生", "测试质量"):
        scores[dim] = s_density(dim)
    scores["变更边界"] = sum(rating_by_item[i] * 20 for i in ("CHG-01", "CHG-02", "CHG-03")) / 3.0
    scores["过度设计"] = rating_by_item["OVR-01"] * 20.0
    scores["工程判断"] = rating_by_item["ENG-01"] * 20.0
    scores["耦合"] = (s_density("耦合") + rating_by_item["CPL-06"] * 20.0) / 2.0

    total = sum(scores[d] * weights[d] for d in weights) / 100.0
    return {
        "kloc": {"source": round(src_kloc, 2), "test": round(test_kloc, 2)},
        "findings_total": counts,
        "density_by_dimension": {k: round(v, 2) for k, v in sorted(density.items())},
        "scores_by_dimension": {k: round(v, 1) for k, v in scores.items()},
        "ratings": {k: rating_by_item[k] for k in sorted(RATING_ITEMS)},
        "total_score": round(total, 1),
    }


def render_md(target, result, findings, ratings_data, coverage, tools_report, weights):
    sev_order = {"high": 0, "medium": 1, "low": 2}
    findings = sorted(findings, key=lambda f: (sev_order[f["severity"]], f["item_id"]))
    zh_sev = {"high": "高", "medium": "中", "low": "低"}
    lines = [f"# 代码质量审计报告：{target}", ""]
    lines += [f"**加权总分：{result['total_score']} / 100**",
              f"（源码 {result['kloc']['source']} KLOC，测试 {result['kloc']['test']} KLOC；"
              f"发现 高 {result['findings_total']['high']} / 中 {result['findings_total']['medium']}"
              f" / 低 {result['findings_total']['low']}）", ""]
    lines += ["## 维度分数", "", "| 维度 | 分数 | 权重 | 加权密度 |", "|---|---|---|---|"]
    for dim, w in sorted(weights.items(), key=lambda x: -x[1]):
        d = result["density_by_dimension"].get(dim, "-")
        lines.append(f"| {dim} | {result['scores_by_dimension'][dim]} | {w} | {d} |")
    lines += ["", "## C 档整体评级", ""]
    for r in sorted(ratings_data, key=lambda x: x["item_id"]):
        lines.append(f"- **{r['item_id']} {r.get('item_name','')}：{r['score']}/5** — {r.get('anchor','')}")
        if r.get("evidence"):
            lines.append(f"  - 证据：{r['evidence']}")
    lines += ["", "## 发现（按严重级别）", ""]
    for i, f in enumerate(findings, 1):
        lines.append(f"### {i}. [{zh_sev[f['severity']]}] {f['item_id']} @ {f['unit']}")
        loc = f.get("lines") or []
        loc_str = f" L{loc[0]}-{loc[1]}" if len(loc) >= 2 else (f" L{loc[0]}" if loc else "")
        lines.append(f"- 位置：`{f['file']}`{loc_str}")
        lines.append(f"- 置信度：{zh_sev.get(f['confidence'], f['confidence'])}")
        lines.append(f"- 证据：{f['evidence']}")
        if f.get("impact"):
            lines.append(f"- 影响：{f['impact']}")
        if f.get("refactoring"):
            lines.append(f"- 重构方向：{f['refactoring']}")
        lines.append("")
    lines += ["## 覆盖审计", "",
              f"- 分派单元 {coverage['assigned']}，已核对 {coverage['reviewed']}，"
              f"跳过 {coverage['skipped']}，缺口 {len(coverage['gaps'])} —— "
              f"{'通过' if coverage['pass'] else '不通过'}"]
    if tools_report:
        lines.append(f"- 工具可用：{', '.join(tools_report.get('available', [])) or '无'}；"
                     f"缺失（对应 A 档降级 *）：{', '.join(tools_report.get('missing', [])) or '无'}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--weights", help="权重/DMAX 覆盖文件")
    ap.add_argument("--target-name", help="报告中的项目名，默认取 manifest.root 目录名")
    ap.add_argument("--allow-degraded-tools", action="store_true",
                    help="允许缺失工具，仅用于非正式降级审计")
    args = ap.parse_args()
    ws = args.workspace

    manifest = load_json(os.path.join(ws, "manifest.json"))
    ratings_file = load_json(os.path.join(ws, "ratings.json"))
    ratings = ratings_file.get("ratings", [])
    tools_report = load_json(os.path.join(ws, "tools", "tools_report.json"), required=False)
    ready_path = os.path.join(ws, "tools", "READY.json")
    if not args.allow_degraded_tools:
        ready = load_json(ready_path, required=False)
        manifest_path = os.path.join(ws, "manifest.json")
        if not ready or not ready.get("ready") or not ready.get("strict"):
            die("工具门禁未通过：缺少有效 tools/READY.json；先运行 validate_tools.py")
        if ready.get("manifest_sha256") != file_sha256(manifest_path):
            die("工具门禁已过期：manifest.json 在 READY 生成后发生变化；重新运行工具门禁")

    weights, dmax = dict(DEFAULT_WEIGHTS), {}
    weights_raw = ""
    if args.weights:
        with open(args.weights, encoding="utf-8") as f:
            weights_raw = f.read()
        override = json.loads(weights_raw)
        weights.update(override.get("weights", {}))
        dmax.update(override.get("dmax", {}))
    if round(sum(weights.values()), 6) != 100:
        die(f"权重合计必须为 100，当前 {sum(weights.values())}")

    all_findings, shard_files, cross_files = [], [], []
    paths = sorted(glob.glob(os.path.join(ws, "findings", "*.json")))
    if not paths:
        die(f"no findings files in {ws}/findings/")
    for path in paths:
        data = load_json(path)
        for f in data.get("findings", []):
            validate_finding(f, os.path.basename(path))
            all_findings.append(f)
        if data.get("agent_role") == "shard-review":
            shard_files.append((path, data))
        elif data.get("agent_role") == "cross-file-review":
            cross_files.append((path, data))

    coverage = coverage_audit(manifest, shard_files, cross_files)
    if not coverage["pass"]:
        report_data = gap_report(coverage)
        gap_path = os.path.join(ws, "gap-report.json")
        with open(gap_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(json.dumps(report_data, ensure_ascii=False, indent=1))
        die("覆盖审计不通过：以上单元未被核对，重派缺口分片后重跑", code=2)

    findings, dropped = dedupe(all_findings)
    if dropped:
        print(f"dedupe: dropped {dropped} duplicate finding(s)")

    result = compute(findings, ratings, manifest, weights, dmax)
    target = args.target_name or os.path.basename(manifest["root"].rstrip("/"))
    checklist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "references", "checklist.md")
    checklist_hash = ""
    if os.path.exists(checklist_path):
        with open(checklist_path, "rb") as f:
            checklist_hash = hashlib.sha256(f.read()).hexdigest()[:12]

    report = {
        "target": target,
        **result,
        "coverage_audit": {k: coverage[k] for k in ("assigned", "reviewed", "skipped", "pass")},
        "weights": weights,
        "provenance": {
            "checklist_sha256": checklist_hash,
            "weights_sha256": hashlib.sha256(weights_raw.encode()).hexdigest()[:12] if weights_raw else "default",
            "tools_missing": (tools_report or {}).get("missing", []),
        },
        "top_findings": [
            f"[{f['severity']}] {f['item_id']} {f['unit']} ({f['file']})"
            for f in findings if f["severity"] == "high"
        ][:10],
    }
    with open(os.path.join(ws, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ws, "report.md"), "w", encoding="utf-8") as f:
        f.write(render_md(target, result, findings, ratings, coverage, tools_report, weights))
    print(f"{target}: total={result['total_score']} "
          f"(findings h/m/l = {result['findings_total']['high']}/"
          f"{result['findings_total']['medium']}/{result['findings_total']['low']}) "
          f"-> {ws}/report.json, report.md")


if __name__ == "__main__":
    main()
