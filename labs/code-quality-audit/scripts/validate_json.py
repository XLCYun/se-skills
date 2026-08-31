#!/usr/bin/env python3
"""Phase 5 安全网：纯校验器。json.loads + 角色 schema 校验 + 已合法文件的规范化重写。

本脚本绝不修改语义（不猜测、不修复）：不合法的文件唯一正确的处理方式是
重派对应的生产者子代理，让它修正自己的 .rec 并重新 emit_json.py——
只有生产者拥有还原原文所需的语义知识。

用法: python3 validate_json.py <path>              # 校验单个文件
      python3 validate_json.py <dir>                # 校验目录下所有 *.json
      python3 validate_json.py <file1> <file2> ...  # 校验多个路径（文件或目录）
退出码: 0 全部通过；1 有文件不合法（输出中列出需要重派的文件）。
"""
import json
import os
import sys

from emit_json import validate_doc


def check_file(path):
    """校验单个 JSON 文件；合法则用 json.dump 规范化重写。返回 True 表示通过。"""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except OSError as e:
        print(f"FAIL {path}: 无法读取（{e}）", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"FAIL {path}: 非法 JSON — {e.msg}（line {e.lineno}, col {e.colno}）。"
              f"重派生产该文件的子代理，修正其 .rec 后重新 emit_json.py，不得手工修补",
              file=sys.stderr)
        return False

    errs = validate_doc(doc)
    if errs:
        for e in errs:
            print(f"FAIL {path}: {e}", file=sys.stderr)
        return False

    # 规范化重写（内容已合法，仅统一格式），保证 aggregate.py 输入一致
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        if os.path.isdir(arg):
            paths.extend(os.path.join(arg, f) for f in sorted(os.listdir(arg)) if f.endswith(".json"))
        else:
            paths.append(arg)
    if not paths:
        print("No JSON files found", file=sys.stderr)
        sys.exit(1)

    failed = [p for p in paths if not check_file(p)]
    print(f"validated {len(paths) - len(failed)}/{len(paths)} files"
          + (f", {len(failed)} failed（需重派对应子代理）" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
