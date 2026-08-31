#!/usr/bin/env bash
# Phase 1：按可用性运行静态工具，结果写入 <workspace>/tools/。
# 用法: bash run_tools.sh <repo> <workspace>
# 缺失的工具跳过并记录在 tools_report.json（对应 A 档项降级人工核对）。
set -u

REPO="${1:?usage: run_tools.sh <repo> <workspace>}"
WS="${2:?usage: run_tools.sh <repo> <workspace>}"
TOOLS_DIR="$WS/tools"
mkdir -p "$TOOLS_DIR"
rm -f "$TOOLS_DIR/READY.json"

declare -a AVAILABLE=() MISSING=()

run_tool() {
  local name="$1"; shift
  if command -v "$name" >/dev/null 2>&1; then
    echo "running $name ..."
    "$@" && AVAILABLE+=("$name") || { echo "warn: $name failed" >&2; MISSING+=("$name(failed)"); }
  else
    echo "skip: $name not installed" >&2
    MISSING+=("$name")
  fi
}

# 规模与语言构成
run_tool cloc cloc --json --quiet \
  --exclude-dir=node_modules,target,build,dist,out,venv,.venv,vendor,coverage \
  --report-file="$TOOLS_DIR/cloc.json" "$REPO"

# 复杂度（STR-01/02/03 的 A 档数据源）
run_tool lizard lizard "$REPO" --csv -o "$TOOLS_DIR/lizard.csv" \
  -x "*/node_modules/*" -x "*/target/*" -x "*/build/*" -x "*/dist/*" -x "*/venv/*"

# 重复代码（DUP-01 的 A 档数据源）
run_tool jscpd jscpd "$REPO" --silent --reporters json --output "$TOOLS_DIR/jscpd" \
  --ignore "**/node_modules/**,**/target/**,**/build/**,**/dist/**,**/*.min.js" \
  --min-tokens 100

# 硬编码/安全（CFG-01 的 A 档数据源）
run_tool semgrep semgrep scan "$REPO" --config auto --json --quiet \
  -o "$TOOLS_DIR/semgrep.json" \
  --exclude node_modules --exclude target --exclude build --exclude dist

# 凭据扫描（CFG-01 高严重子项）。gitleaks ≥8.19 用 dir 子命令，旧版用 detect --no-git
if gitleaks dir --help >/dev/null 2>&1; then
  run_tool gitleaks gitleaks dir "$REPO" -r "$TOOLS_DIR/gitleaks.json" -f json --exit-code 0
else
  run_tool gitleaks gitleaks detect --no-git -s "$REPO" -r "$TOOLS_DIR/gitleaks.json" -f json --exit-code 0
fi

# 工具可用性报告
json_array() {
  local out="" x
  for x in "$@"; do out+="\"$x\","; done
  printf '[%s]' "${out%,}"
}
{
  printf '{\n  "available": %s,\n' "$(json_array "${AVAILABLE[@]+"${AVAILABLE[@]}"}")"
  printf '  "missing": %s,\n' "$(json_array "${MISSING[@]+"${MISSING[@]}"}")"
  printf '  "degraded_items": "missing 中的工具对应的 A 档项转由分片代理人工核对，confidence 上限 medium"\n}\n'
} > "$TOOLS_DIR/tools_report.json"

echo "tools report -> $TOOLS_DIR/tools_report.json"
echo "available: ${AVAILABLE[*]:-none} | missing: ${MISSING[*]:-none}"

# 默认严格门禁；显式 CQA_TOOL_MODE=degraded 才允许降级继续。
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/validate_tools.py" "$WS" --mode "${CQA_TOOL_MODE:-strict}"
