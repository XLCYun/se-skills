#!/usr/bin/env python3
"""把子代理写的 .rec 中间格式确定性地转换为合法 JSON（格式规范见 references/rec-format.md）。

设计原则：LLM 只产出原始文本，序列化永远由本脚本的 json.dump 完成。
.rec 是行式格式，prose 字段放在 <<< >>> 原文块里，没有转义概念，
因此 JSON 合法性按构造保证，而不是事后修复。

用法: python3 emit_json.py <file.rec> [--out <file.json>]
      默认输出路径 = 输入路径把 .rec 换成 .json。
退出码: 0 成功（打印输出路径）；1 解析或校验失败（打印带行号的错误，修正 .rec 后重跑）。
"""
import argparse
import json
import os
import re
import sys

SECTION_RE = re.compile(r'^===\s*([A-Z]+)\s*===\s*$')
KV_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):\s?(.*)$')
BLOCK_OPEN_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*<<<\s*$')

# prose 字段永远按原文字符串处理，绝不尝试 JSON 解析
PROSE_FIELDS = {"evidence", "impact", "refactoring", "anchor", "walkthrough", "reason"}
KNOWN_SECTIONS = {"DOC", "FINDING", "SUMMARY", "RATING", "SKIPPED", "DRILLDOWN", "COVERAGE", "END"}
ROLES = {"shard-review", "cross-file-review", "holistic-rating"}
SEVERITIES = {"high", "medium", "low"}
CONFIDENCES = {"high", "medium"}
UNIT_TYPES = {"class", "function", "module", "file"}
RATING_ITEMS = {"CHG-01", "CHG-02", "CHG-03", "OVR-01", "ENG-01", "CPL-06"}


class RecError(Exception):
    def __init__(self, lineno, msg):
        super().__init__(f"line {lineno}: {msg}")
        self.lineno = lineno


def coerce(key, raw):
    """单行值：prose 字段永远原文；其他先按 JSON 解析，失败则按原文字符串。"""
    raw = raw.strip()
    if key in PROSE_FIELDS:
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_rec(text):
    """解析 .rec 文本 → [(section_name, fields_dict, start_lineno), ...]。"""
    lines = text.split("\n")
    sections = []
    current = None       # (name, dict, start_lineno)
    saw_end = False
    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        m = SECTION_RE.match(line)
        if m:
            name = m.group(1)
            if name not in KNOWN_SECTIONS:
                raise RecError(lineno, f"未知 section '=== {name} ==='（可用：{', '.join(sorted(KNOWN_SECTIONS))}）")
            if saw_end:
                raise RecError(lineno, "=== END === 之后不允许再有内容")
            if name == "END":
                saw_end = True
                current = None
            else:
                current = (name, {}, lineno)
                sections.append(current)
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if saw_end:
            raise RecError(lineno, "=== END === 之后不允许再有内容")
        if current is None:
            raise RecError(lineno, f"内容出现在任何 section 之前：{line[:60]!r}")

        m = BLOCK_OPEN_RE.match(line)
        if m:
            key = m.group(1)
            body = []
            j = i + 1
            while j < len(lines):
                bl = lines[j]
                if bl == ">>>":
                    break
                # 转义规则：内容里恰好为 ">>>" 的行写成 " >>>"（前置一个空格），这里还原
                body.append(bl[1:] if bl == " >>>" else bl)
                j += 1
            else:
                raise RecError(lineno, f"字段 '{key}' 的 <<< 块直到文件末尾都没有 >>> 闭合行")
            if key in current[1]:
                raise RecError(lineno, f"section 内字段 '{key}' 重复")
            current[1][key] = "\n".join(body).strip("\n")
            i = j + 1
            continue

        m = KV_RE.match(line)
        if m:
            key, raw = m.group(1), m.group(2)
            if key in current[1]:
                raise RecError(lineno, f"section 内字段 '{key}' 重复")
            current[1][key] = coerce(key, raw)
            i += 1
            continue

        raise RecError(lineno, f"无法解析的行（既不是 'key: value' 也不是 'key <<<'）：{line[:60]!r}")

    if not saw_end:
        raise RecError(len(lines), "缺少结尾的 === END ===（用于检测输出被截断）")
    return sections


def assemble(sections):
    """按 agent_role 把 sections 组装成 output-schema.md 定义的文档结构。"""
    doc_fields, coverage = {}, {}
    findings, summaries, ratings, skipped, drilldown = [], [], [], [], []
    for name, data, lineno in sections:
        if name == "DOC":
            doc_fields.update(data)
        elif name == "FINDING":
            findings.append(data)
        elif name == "SUMMARY":
            summaries.append(data)
        elif name == "RATING":
            ratings.append(data)
        elif name == "SKIPPED":
            skipped.append(data)
        elif name == "DRILLDOWN":
            drilldown.append(data)
        elif name == "COVERAGE":
            coverage.update(data)

    role = doc_fields.get("agent_role")
    if role == "holistic-rating":
        out = dict(doc_fields)
        out["ratings"] = ratings
        out["coverage"] = {
            "files_read": coverage.get("files_read", []),
            "drilldown": drilldown + list(coverage.get("drilldown", [])),
            "sampled_files": coverage.get("sampled_files", []),
        }
    else:
        out = dict(doc_fields)
        out["findings"] = findings
        out["summary"] = summaries
        out["coverage"] = {
            "assigned": coverage.get("assigned", []),
            "reviewed": coverage.get("reviewed", []),
            "skipped": skipped + list(coverage.get("skipped", [])),
            "drilldown": drilldown + list(coverage.get("drilldown", [])),
        }
    return out


def validate_doc(doc):
    """校验组装后的文档（与 aggregate.py 的校验对齐，提前暴露错误）。返回错误列表。"""
    errs = []
    role = doc.get("agent_role")
    if role not in ROLES:
        errs.append(f"agent_role 必须是 {sorted(ROLES)} 之一，得到 {role!r}")
        return errs

    if role == "holistic-rating":
        ratings = doc.get("ratings", [])
        seen = set()
        for i, r in enumerate(ratings):
            where = f"ratings[{i}]({r.get('item_id', '?')})"
            for field in ("item_id", "item_name", "score", "anchor", "evidence"):
                if r.get(field) in (None, ""):
                    errs.append(f"{where}: 缺少字段 '{field}'")
            score = r.get("score")
            if not (isinstance(score, int) and 0 <= score <= 5):
                errs.append(f"{where}: score 必须是 0-5 整数，得到 {score!r}")
            if r.get("item_id"):
                seen.add(r["item_id"])
        missing = sorted(RATING_ITEMS - seen)
        if missing:
            errs.append(f"缺少 C 档评级项: {missing}（6 项缺一不可）")
        return errs

    for i, f in enumerate(doc.get("findings", [])):
        where = f"findings[{i}]({f.get('item_id', '?')} @ {f.get('unit', '?')})"
        for field in ("item_id", "file", "unit", "severity", "confidence", "evidence"):
            if f.get(field) in (None, ""):
                errs.append(f"{where}: 缺少字段 '{field}'")
        if f.get("severity") and f["severity"] not in SEVERITIES:
            errs.append(f"{where}: severity 必须是 high|medium|low，得到 {f['severity']!r}")
        if f.get("confidence") and f["confidence"] not in CONFIDENCES:
            errs.append(f"{where}: confidence 必须是 high|medium（低置信发现应省略），得到 {f['confidence']!r}")
        if f.get("unit_type") and f["unit_type"] not in UNIT_TYPES:
            errs.append(f"{where}: unit_type 必须是 class|function|module|file，得到 {f['unit_type']!r}")
        lines_v = f.get("lines")
        if lines_v is not None and not (isinstance(lines_v, list) and all(isinstance(x, int) for x in lines_v)):
            errs.append(f"{where}: lines 必须是整数数组，如 [40, 620]，得到 {lines_v!r}")
        if role == "cross-file-review" and not f.get("related"):
            errs.append(f"{where}: 跨文件 finding 必须带 related[]（构成该模式的全部位置）")

    for i, s in enumerate(doc.get("summary", [])):
        where = f"summary[{i}]({s.get('unit', '?')})"
        for field in ("unit", "file"):
            if s.get(field) in (None, ""):
                errs.append(f"{where}: 缺少字段 '{field}'")

    cov = doc.get("coverage") or {}
    for key in ("assigned", "reviewed"):
        if not isinstance(cov.get(key), list):
            errs.append(f"coverage.{key} 必须是数组")
    if role == "shard-review":
        if not doc.get("shard_id"):
            errs.append("shard-review 文档必须有 shard_id（写在 === DOC === 里）")
        if not cov.get("assigned"):
            errs.append("coverage.assigned 不能为空（普查协议的凭证）")
    for i, s in enumerate(cov.get("skipped", [])):
        if not (isinstance(s, dict) and s.get("unit") and s.get("reason")):
            errs.append(f"coverage.skipped[{i}] 必须含 unit 与 reason")
    for i, d in enumerate(cov.get("drilldown", [])):
        if not (isinstance(d, dict) and d.get("path") and d.get("reason")):
            errs.append(f"coverage.drilldown[{i}] 必须含 path 与 reason")
    return errs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rec", help=".rec 输入文件")
    ap.add_argument("--out", help="输出 JSON 路径（默认：输入路径 .rec → .json）")
    args = ap.parse_args()

    out_path = args.out or (re.sub(r"\.rec$", "", args.rec) + ".json")
    try:
        with open(args.rec, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"error: 无法读取 {args.rec}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        sections = parse_rec(text)
    except RecError as e:
        print(f"error: {args.rec}: {e}", file=sys.stderr)
        sys.exit(1)

    doc = assemble(sections)
    errs = validate_doc(doc)
    if errs:
        for e in errs:
            print(f"error: {args.rec}: {e}", file=sys.stderr)
        print(f"共 {len(errs)} 个校验错误，修正 .rec 后重跑", file=sys.stderr)
        sys.exit(1)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(out_path)


if __name__ == "__main__":
    main()
