#!/usr/bin/env python3
"""Phase 0：枚举审查单元，生成 manifest.json（普查的分母）。

用法: python3 build_manifest.py <repo> --out <workspace>/manifest.json [--max-shard-loc 2000]
仅依赖标准库。单元提取基于正则，是近似值——它决定分派粒度与覆盖分母，不用于计数指标。
"""
import argparse
import json
import os
import re
import sys

EXCLUDE_DIRS = {
    ".git", ".svn", ".hg", ".idea", ".vscode", "__pycache__", ".pytest_cache",
    "node_modules", "bower_components", "vendor",
    "target", "build", "dist", "out", "bin", "obj",
    "venv", ".venv", "env", ".tox", ".pnpm-store",
    "coverage", ".nyc_output", ".gradle", ".mvn",
}
LANG_BY_EXT = {
    ".java": "java", ".kt": "kotlin", ".scala": "scala", ".groovy": "groovy",
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".rb": "ruby", ".php": "php", ".cs": "csharp",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".rs": "rust", ".swift": "swift", ".vue": "vue",
}
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|testing|it)(/|$)"
    r"|(^|/)src/test(/|$)"
)
TEST_FILE = re.compile(
    r"(Test\w*|\w*Tests?|\w*IT)\.(java|kt|scala|groovy)$"
    r"|(_test\.(go|py)|test_\w+\.py)$"
    r"|\.(test|spec)\.(js|jsx|ts|tsx|mjs)$"
)
DOC_FILE = re.compile(r"\.(md|rst|adoc|txt)$", re.IGNORECASE)
ENTRYPOINT_PATTERNS = [
    ("java-main", re.compile(r"public\s+static\s+void\s+main\s*\(")),
    ("spring-boot", re.compile(r"@SpringBootApplication")),
    ("python-main", re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']')),
    ("fastapi", re.compile(r"FastAPI\s*\(")),
    ("flask", re.compile(r"Flask\s*\(__name__\)")),
    ("express", re.compile(r"\.listen\s*\(")),
    ("nest", re.compile(r"NestFactory\.create")),
]

UNIT_PATTERNS = {
    "java": [("class", re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:public|protected|private|abstract|final|static|sealed|\s)*\s*(?:class|interface|enum|record)\s+(\w+)", re.M))],
    "kotlin": [("class", re.compile(r"^\s*(?:open|data|sealed|abstract|internal|private|public|\s)*\s*(?:class|interface|object|enum class)\s+(\w+)", re.M))],
    "scala": [("class", re.compile(r"^\s*(?:case\s+)?(?:class|object|trait)\s+(\w+)", re.M))],
    "python": [
        ("class", re.compile(r"^class\s+(\w+)", re.M)),
        ("function", re.compile(r"^def\s+(\w+)", re.M)),
    ],
    "javascript": [
        ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)", re.M)),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)", re.M)),
        ("function", re.compile(r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(", re.M)),
    ],
    "go": [
        ("struct", re.compile(r"^type\s+(\w+)\s+struct", re.M)),
        ("function", re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(", re.M)),
    ],
    "csharp": [("class", re.compile(r"^\s*(?:public|internal|private|protected|abstract|sealed|static|partial|\s)*\s*(?:class|interface|enum|record|struct)\s+(\w+)", re.M))],
}
UNIT_PATTERNS["typescript"] = UNIT_PATTERNS["javascript"]


def count_loc(text):
    return sum(1 for line in text.splitlines() if line.strip())


def extract_units(lang, text, rel_path):
    patterns = UNIT_PATTERNS.get(lang)
    units = []
    if patterns:
        seen = set()
        for unit_type, pat in patterns:
            for m in pat.finditer(text):
                name = m.group(1)
                line = text.count("\n", 0, m.start()) + 1
                identity = (unit_type, name, line)
                if identity in seen:
                    continue
                seen.add(identity)
                units.append({
                    "id": f"{rel_path}::{unit_type}::{name}@{line}",
                    "type": unit_type,
                    "name": name,
                    "line": line,
                })
    if not units:
        name = os.path.basename(rel_path)
        units.append({
            "id": f"{rel_path}::file::{name}@1",
            "type": "file",
            "name": name,
            "line": 1,
        })
    return units


def detect_entrypoints(text):
    return [name for name, pat in ENTRYPOINT_PATTERNS if pat.search(text)]


def scan(repo):
    files, docs = [], []
    for root, dirs, names in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith("."))
        for name in sorted(names):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, repo)
            ext = os.path.splitext(name)[1].lower()
            if DOC_FILE.search(name):
                docs.append(rel)
                continue
            lang = LANG_BY_EXT.get(ext)
            if not lang:
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError as e:
                print(f"warn: cannot read {rel}: {e}", file=sys.stderr)
                continue
            loc = count_loc(text)
            if loc == 0:
                continue
            files.append({
                "path": rel,
                "lang": lang,
                "loc": loc,
                "is_test": bool(TEST_PATH.search(rel.replace(os.sep, "/")) or TEST_FILE.search(name)),
                "units": extract_units(lang, text, rel),
                "entrypoints": detect_entrypoints(text),
            })
    return files, docs


def build_shards(files, max_loc):
    """按目录聚合后贪心装箱；测试文件独立分片。超大单文件独占一片。"""
    def pack(group_files, kind, start_idx):
        by_dir = {}
        for f in sorted(group_files, key=lambda x: x["path"]):
            by_dir.setdefault(os.path.dirname(f["path"]), []).append(f)
        shards, cur, cur_loc = [], [], 0
        for d in sorted(by_dir):
            for f in by_dir[d]:
                if cur and cur_loc + f["loc"] > max_loc:
                    shards.append(cur)
                    cur, cur_loc = [], 0
                cur.append(f)
                cur_loc += f["loc"]
        if cur:
            shards.append(cur)
        return [
            {
                "id": f"{kind}-{start_idx + i:02d}",
                "kind": kind,
                "files": [f["path"] for f in s],
                "assigned_units": [u["id"] for f in s for u in f["units"]],
                "summary_files": [f["path"] for f in s] if kind == "src" else [],
                "loc": sum(f["loc"] for f in s),
                "units": sum(len(f["units"]) for f in s),
            }
            for i, s in enumerate(shards)
        ]

    src = [f for f in files if not f["is_test"]]
    tst = [f for f in files if f["is_test"]]
    return pack(src, "src", 0) + pack(tst, "test", 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-shard-loc", type=int, default=2000)
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        sys.exit(f"error: not a directory: {repo}")

    files, docs = scan(repo)
    if not files:
        sys.exit("error: no source files found")
    shards = build_shards(files, args.max_shard_loc)
    entrypoints = [
        {"path": f["path"], "kinds": f["entrypoints"]}
        for f in files if f["entrypoints"] and not f["is_test"]
    ]
    manifest = {
        "root": repo,
        "generated_by": "build_manifest.py",
        "totals": {
            "files": len(files),
            "source_loc": sum(f["loc"] for f in files if not f["is_test"]),
            "test_loc": sum(f["loc"] for f in files if f["is_test"]),
            "units": sum(len(f["units"]) for f in files),
            "shards": len(shards),
            "langs": sorted({f["lang"] for f in files}),
        },
        "files": files,
        "shards": shards,
        "entrypoints": entrypoints,
        "docs": docs,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    t = manifest["totals"]
    print(f"manifest: {t['files']} files, {t['source_loc']} src loc + {t['test_loc']} test loc, "
          f"{t['units']} units, {t['shards']} shards -> {args.out}")


if __name__ == "__main__":
    main()
