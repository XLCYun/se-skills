#!/usr/bin/env python3
"""验证 Phase 1 工具产物；严格模式通过后生成 tools/READY.json。

用法: python3 validate_tools.py <workspace> [--mode strict|degraded]
退出码: 0 门禁通过；1 工具缺失、失败、输出无效或与 manifest 不匹配。
"""
import argparse
import csv
import hashlib
import json
import os
import sys


REQUIRED = {
    "cloc": ("cloc.json", "json"),
    "lizard": ("lizard.csv", "csv"),
    "jscpd": (os.path.join("jscpd", "jscpd-report.json"), "json"),
    "semgrep": ("semgrep.json", "json"),
    "gitleaks": ("gitleaks.json", "json"),
}
LANGUAGE_SUPPORT = {
    # 只列需要语法解析的工具；cloc/gitleaks 按文本工作，jscpd 可处理本 manifest 的代码扩展名。
    "lizard": {
        "c", "cpp", "csharp", "java", "javascript", "typescript", "python",
        "go", "ruby", "swift", "kotlin", "scala",
    },
    "semgrep": {
        "c", "cpp", "csharp", "java", "javascript", "typescript", "python",
        "go", "ruby", "php", "rust", "kotlin",
    },
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def validate_output(tool, path, kind):
    if not os.path.isfile(path):
        return "missing"
    if os.path.getsize(path) == 0:
        return "empty"
    try:
        if kind == "json":
            data = load_json(path)
            if tool == "cloc" and not (isinstance(data, dict) and "SUM" in data):
                return "invalid: cloc.json 缺少 SUM"
            if tool == "jscpd" and not (isinstance(data, dict) and
                                         ("statistics" in data or "duplicates" in data)):
                return "invalid: jscpd report 缺少 statistics/duplicates"
            if tool == "semgrep":
                if not (isinstance(data, dict) and isinstance(data.get("results"), list)):
                    return "invalid: semgrep.json 缺少 results[]"
                if data.get("errors"):
                    return f"invalid: semgrep 报告 {len(data['errors'])} 个错误"
            if tool == "gitleaks" and not isinstance(data, list):
                return "invalid: gitleaks.json 必须是数组"
        else:
            with open(path, newline="", encoding="utf-8", errors="replace") as f:
                rows = csv.reader(f)
                if next(rows, None) is None or next(rows, None) is None:
                    return "empty"
    except (OSError, ValueError, json.JSONDecodeError, csv.Error) as e:
        return f"invalid: {e}"
    return "success"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--mode", choices=("strict", "degraded"), default="strict")
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    tools_dir = os.path.join(ws, "tools")
    ready_path = os.path.join(tools_dir, "READY.json")
    if os.path.exists(ready_path):
        os.unlink(ready_path)

    try:
        manifest = load_json(os.path.join(ws, "manifest.json"))
        report = load_json(os.path.join(tools_dir, "tools_report.json"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: 工具门禁输入无效: {e}", file=sys.stderr)
        return 1

    declared_available = set(report.get("available", []))
    declared_missing = set(report.get("missing", []))
    languages = set(manifest.get("totals", {}).get("langs", []))
    statuses, failures = {}, []
    for tool, (rel, kind) in REQUIRED.items():
        path = os.path.join(tools_dir, rel)
        status = validate_output(tool, path, kind)
        unsupported = sorted(languages - LANGUAGE_SUPPORT.get(tool, languages))
        statuses[tool] = {
            "status": status,
            "output": rel,
            "sha256": sha256(path) if status == "success" else None,
            "unsupported_languages": unsupported,
        }
        if status != "success":
            failures.append(f"{tool}: {status}")
        if tool not in declared_available:
            failures.append(f"{tool}: tools_report 未声明 available")
        if unsupported:
            failures.append(f"{tool}: 不支持语言 {', '.join(unsupported)}")
    if declared_missing:
        failures.append("tools_report missing: " + ", ".join(sorted(declared_missing)))

    strict_ready = not failures
    ready = {
        "ready": strict_ready or args.mode == "degraded",
        "strict": strict_ready,
        "mode": args.mode,
        "manifest_sha256": sha256(os.path.join(ws, "manifest.json")),
        "languages": sorted(languages),
        "tools": statuses,
        "failures": failures,
    }
    if ready["ready"]:
        with open(ready_path, "w", encoding="utf-8") as f:
            json.dump(ready, f, ensure_ascii=False, indent=2)
        print(ready_path)
        if failures:
            print("warning: degraded tool gate: " + "; ".join(failures), file=sys.stderr)
        return 0

    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)
    print("error: strict 工具门禁失败，不得启动 Phase 2", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
