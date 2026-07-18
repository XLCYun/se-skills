#!/usr/bin/env python3
"""修复 Agent 写入的 JSON 文件：校验 → 修复常见引号问题 → json.dump 重写。
Agent 是文本生成器而非 JSON 序列化器，输出的文件中可能含有未转义的内部引号。
本脚本用真正的 json.dump 重写，确保所有字符串值中的特殊字符被正确转义。

用法: python3 repair_json.py <path>              # 修复单个文件
      python3 repair_json.py <dir>                # 修复目录下所有 *.json
      python3 repair_json.py <file1> <file2> ...  # 修复多个文件
退出码: 0 全部通过；1 有文件无法修复。
"""
import json
import os
import re
import sys


def _fix_inner_quotes(text: str) -> str:
    """修复 JSON 字符串值内部的未转义双引号。

    两阶段：
    1. 还原可能被过度使用的「」→ "
    2. 移除代码上下文中不该存在的 "（如 ="word"、{"key"}）
    3. 将中文上下文中的 " 替换为「」
    4. 对 JSON 结构位置的 " 不做任何处理
    """
    # 还原 Agent 可能过度使用的「」
    text = text.replace('「', '"').replace('」', '"')

    # 移除 Python 代码风格的字面量引号
    text = re.sub(r'(\w+)=(")(\w+)(")', r'\1=\3', text)
    text = re.sub(r'"(\w+)"(\s*/\s*)"(\w+)"(\s*/\s*)"(\w+)"', r'\1/\3/\5', text)
    text = re.sub(r'"(\w+)"(\s*/\s*)"(\w+)"', r'\1/\3', text)

    # 判断是否为 JSON 结构引号（不可动）
    def _is_json_delim(s, pos):
        if s[pos] != '"':
            return False
        # 前驱：{, [, ,, : → 开启引号
        i = pos - 1
        while i >= 0 and s[i] in ' \t':
            i -= 1
        if i >= 0 and s[i] in '{[,:':
            return True
        # 后继：}, ], , → 闭合引号
        i = pos + 1
        while i < len(s) and s[i] in ' \t':
            i += 1
        if i < len(s) and s[i] in '},]':
            return True
        if i < len(s) and s[i] == '\n':
            j = i + 1
            while j < len(s) and s[j] in ' \t':
                j += 1
            if j < len(s) and s[j] in '}"':
                return True
        return False

    result = []
    for i, ch in enumerate(text):
        if ch == '"':
            if _is_json_delim(text, i):
                result.append('"')
            elif 0 < i < len(text) - 1:
                prev_cjk = ord(text[i - 1]) > 127
                next_cjk = ord(text[i + 1]) > 127
                if prev_cjk and next_cjk:
                    result.append('「')  # 「
                elif prev_cjk:
                    result.append('」')  # 」
                elif next_cjk:
                    result.append('「')
                else:
                    result.append('"')
            else:
                result.append('"')
        else:
            result.append(ch)
    return ''.join(result)


def repair_file(path: str) -> bool:
    """修复单个 JSON 文件。返回 True 表示成功。"""
    try:
        with open(path, encoding='utf-8') as f:
            raw = f.read()
    except OSError as e:
        print(f"FAIL {path}: cannot read ({e})", file=sys.stderr)
        return False

    # 先尝试直接解析
    try:
        json.loads(raw)
    except json.JSONDecodeError:
        # 尝试修复后解析
        fixed = _fix_inner_quotes(raw)
        try:
            json.loads(fixed)
        except json.JSONDecodeError as e:
            print(f"FAIL {path}: unrepairable — {e.msg} at line {e.lineno}", file=sys.stderr)
            return False
        raw = fixed

    # 用真正序列化器重写（消除任何残留格式问题）
    data = json.loads(raw)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        if os.path.isdir(arg):
            for f in sorted(os.listdir(arg)):
                if f.endswith('.json'):
                    paths.append(os.path.join(arg, f))
        else:
            paths.append(arg)

    if not paths:
        print("No JSON files found", file=sys.stderr)
        sys.exit(1)

    ok, fail = 0, 0
    for p in paths:
        if repair_file(p):
            ok += 1
        else:
            fail += 1

    print(f"Repaired {ok}/{ok + fail} files" + (f", {fail} failed" if fail else ""))
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
