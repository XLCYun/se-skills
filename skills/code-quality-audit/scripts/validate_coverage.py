#!/usr/bin/env python3
"""在 Agent 阶段之间执行 manifest/coverage 强校验并生成定向重试清单。"""
import argparse
import glob
import json
import os
import sys

from aggregate import coverage_audit, gap_report, load_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--phase", choices=("shard", "all"), default="shard")
    args = ap.parse_args()
    ws = os.path.abspath(args.workspace)
    manifest = load_json(os.path.join(ws, "manifest.json"))
    shard_files, cross_files = [], []
    for path in sorted(glob.glob(os.path.join(ws, "findings", "*.json"))):
        data = load_json(path)
        if data.get("agent_role") == "shard-review":
            shard_files.append((path, data))
        elif data.get("agent_role") == "cross-file-review":
            cross_files.append((path, data))

    coverage = coverage_audit(
        manifest, shard_files, cross_files, check_cross=args.phase == "all")
    gap_path = os.path.join(ws, "gap-report.json")
    if not coverage["pass"]:
        report = gap_report(coverage)
        with open(gap_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    if os.path.exists(gap_path):
        os.unlink(gap_path)
    print(json.dumps({"status": "passed", "phase": args.phase,
                      "assigned": coverage["assigned"],
                      "reviewed": coverage["reviewed"],
                      "skipped": coverage["skipped"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
