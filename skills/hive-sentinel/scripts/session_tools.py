#!/usr/bin/env python3
"""Read-only tools for exploring persisted agent session records."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


RUNTIMES = ("auto", "codex", "claude")


def emit(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def parse_timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000 if number > 10_000_000_000 else number
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def iso_timestamp(value: Any) -> str | None:
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    return datetime.fromtimestamp(parsed).astimezone().isoformat()


def read_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield line_number, record


def infer_runtime(path: Path, records: list[tuple[int, dict[str, Any]]]) -> str:
    for _, record in records[:20]:
        if record.get("type") == "session_meta" and isinstance(record.get("payload"), dict):
            return "codex"
        if "sessionId" in record or "parentUuid" in record or "isSidechain" in record:
            return "claude"
    lowered = str(path).lower()
    if "/.codex/" in lowered:
        return "codex"
    if "/.claude/" in lowered:
        return "claude"
    return "unknown"


def default_roots(runtime: str) -> list[Path]:
    home = Path.home()
    if runtime == "codex":
        codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
        return [codex_home / "sessions", codex_home / "archived_sessions"]
    if runtime == "claude":
        return [home / ".claude" / "projects", home / ".claude" / "sessions"]
    return default_roots("codex") + default_roots("claude")


def candidate_files(runtime: str, roots: list[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = root.rglob("*.jsonl")
        else:
            continue
        for path in candidates:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield resolved


def session_identity(path: Path, runtime: str | None = None) -> dict[str, Any]:
    records = list(read_jsonl(path))
    detected = runtime if runtime and runtime != "auto" else infer_runtime(path, records)
    result: dict[str, Any] = {
        "runtime": detected,
        "path": str(path.resolve()),
        "session_id": None,
        "parent_session_id": None,
        "agent_path": None,
        "agent_name": None,
        "cwd": None,
        "record_count": len(records),
    }
    if detected == "codex":
        for _, record in records:
            if record.get("type") != "session_meta":
                continue
            payload = record.get("payload") or {}
            result["session_id"] = payload.get("session_id") or payload.get("id")
            result["cwd"] = payload.get("cwd")
            source = payload.get("source")
            if isinstance(source, dict):
                spawn = ((source.get("subagent") or {}).get("thread_spawn") or {})
                result["parent_session_id"] = spawn.get("parent_thread_id")
                result["agent_path"] = spawn.get("agent_path")
                result["agent_name"] = spawn.get("agent_nickname")
            break
    elif detected == "claude":
        for _, record in records:
            result["session_id"] = result["session_id"] or record.get("sessionId") or record.get("session_id")
            result["cwd"] = result["cwd"] or record.get("cwd")
            if result["session_id"] and result["cwd"]:
                break
        result["session_id"] = result["session_id"] or path.stem
        if path.parent.name == "subagents":
            result["parent_session_id"] = result["session_id"]
            result["agent_name"] = path.stem
            result["agent_path"] = f"subagents/{path.name}"
    return result


def discover(runtime: str, session_id: str | None, roots: list[Path]) -> list[dict[str, Any]]:
    matches = []
    for path in candidate_files(runtime, roots):
        identity = session_identity(path, runtime)
        if session_id and identity["session_id"] != session_id:
            continue
        if runtime != "auto" and identity["runtime"] != runtime:
            continue
        matches.append(identity)
    return sorted(matches, key=lambda item: item["path"])


def searchable_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def tool_activity(name: str | None, tool_input: Any = None) -> str:
    if not name:
        return "tool"
    lowered = name.lower()
    details = searchable_text(tool_input).lower()
    if re.search(r"\b(pytest|unittest|cargo\s+test|go\s+test|npm\s+test|pnpm\s+test|yarn\s+test)\b", details):
        return "test"
    if re.search(r"\bgit\s+", details):
        return "git"
    if any(part in lowered for part in ("read", "view", "list", "find", "search", "glob")):
        return "read"
    if any(part in lowered for part in ("edit", "write", "patch", "create")):
        return "edit"
    if any(part in lowered for part in ("test", "pytest", "cargo test")):
        return "test"
    if any(part in lowered for part in ("shell", "bash", "exec", "command", "terminal")):
        return "shell"
    if "git" in lowered:
        return "git"
    return "tool"


def usage_from(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    aliases = {
        "input_tokens": ("input_tokens", "input"),
        "output_tokens": ("output_tokens", "output"),
        "cached_input_tokens": ("cached_input_tokens", "cache_read_input_tokens"),
        "cache_creation_tokens": ("cache_creation_input_tokens", "cache_write_input_tokens"),
        "reasoning_tokens": ("reasoning_tokens", "reasoning_output_tokens"),
        "total_tokens": ("total_tokens",),
    }
    result = {}
    for canonical, keys in aliases.items():
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, (int, float)):
                result[canonical] = int(raw)
                break
    return result


def codex_events(path: Path, session_id: str | None) -> list[dict[str, Any]]:
    events = []
    for _, record in read_jsonl(path):
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        outer = record.get("type", "unknown")
        inner = payload.get("type") or outer
        timestamp = record.get("timestamp") or payload.get("started_at")
        event: dict[str, Any] = {
            "runtime": "codex",
            "session_id": session_id,
            "timestamp": iso_timestamp(timestamp),
            "event_type": inner,
            "activity_kind": "other",
        }
        if outer == "response_item" and inner == "custom_tool_call":
            event.update({
                "activity_kind": tool_activity(payload.get("name"), payload.get("input")),
                "tool_name": payload.get("name"),
                "call_id": payload.get("call_id"),
                "status": "started",
            })
        elif outer == "response_item" and inner == "custom_tool_call_output":
            event.update({
                "activity_kind": "tool_result",
                "call_id": payload.get("call_id"),
                "status": "completed",
            })
        elif inner in ("task_started", "task_complete"):
            event["activity_kind"] = "agent"
            event["duration_ms"] = payload.get("duration_ms")
        elif inner == "item_completed":
            item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
            event["activity_kind"] = tool_activity(
                item.get("name") or item.get("type"), item.get("input") or item.get("command")
            )
            event["tool_name"] = item.get("name") or item.get("type")
            start = payload.get("started_at_ms")
            end = payload.get("completed_at_ms")
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                event["duration_ms"] = max(0, int(end - start))
        elif inner == "token_count":
            event["activity_kind"] = "llm"
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
            event["usage"] = usage_from(info.get("last_token_usage") or info.get("total_token_usage") or info)
        elif inner in ("message", "reasoning"):
            event["activity_kind"] = "llm"
        else:
            event["activity_kind"] = "runtime"
        events.append(event)
    return events


def claude_content_events(record: dict[str, Any], base: dict[str, Any]) -> list[dict[str, Any]]:
    message = record.get("message") if isinstance(record.get("message"), dict) else {}
    content = message.get("content")
    blocks = content if isinstance(content, list) else []
    events = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "tool_use":
            event = dict(base)
            event.update({
                "event_type": "tool_use",
                "activity_kind": tool_activity(block.get("name"), block.get("input")),
                "tool_name": block.get("name"),
                "call_id": block.get("id"),
                "status": "started",
            })
            events.append(event)
        elif block_type == "tool_result":
            event = dict(base)
            event.update({
                "event_type": "tool_result",
                "activity_kind": "tool_result",
                "call_id": block.get("tool_use_id"),
                "status": "error" if block.get("is_error") else "completed",
            })
            events.append(event)
    return events


def claude_events(path: Path, session_id: str | None) -> list[dict[str, Any]]:
    events = []
    for _, record in read_jsonl(path):
        event_type = record.get("subtype") or record.get("type", "unknown")
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        base = {
            "runtime": "claude",
            "session_id": record.get("sessionId") or record.get("session_id") or session_id,
            "timestamp": iso_timestamp(record.get("timestamp")),
            "event_type": event_type,
            "activity_kind": "llm" if record.get("type") == "assistant" else "runtime",
        }
        usage = usage_from(message.get("usage"))
        if usage:
            base["usage"] = usage
        content_events = claude_content_events(record, base)
        if record.get("type") == "assistant" or not content_events:
            events.append(base)
        for event in content_events:
            event.pop("usage", None)
        events.extend(content_events)
    return events


def normalized_events(path: Path, runtime: str = "auto") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    identity = session_identity(path, runtime)
    if identity["runtime"] == "codex":
        events = codex_events(path, identity["session_id"])
    elif identity["runtime"] == "claude":
        events = claude_events(path, identity["session_id"])
    else:
        raise ValueError(f"unsupported session format: {path}")
    events.sort(key=lambda item: parse_timestamp(item.get("timestamp")) or float("inf"))
    return identity, events


def summarize(identity: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps = [parse_timestamp(event.get("timestamp")) for event in events]
    timestamps = [value for value in timestamps if value is not None]
    activity_counts = Counter(event["activity_kind"] for event in events)
    tools = Counter(event.get("tool_name") for event in events if event.get("tool_name"))
    usage: defaultdict[str, int] = defaultdict(int)
    activity_durations: defaultdict[str, int] = defaultdict(int)
    usage_available = False
    for event in events:
        if isinstance(event.get("duration_ms"), (int, float)):
            activity_durations[event["activity_kind"]] += int(event["duration_ms"])
        for key, value in (event.get("usage") or {}).items():
            usage[key] += value
            usage_available = True

    calls: dict[str, tuple[float, str | None, str]] = {}
    tool_durations: defaultdict[str, list[int]] = defaultdict(list)
    for event in events:
        call_id = event.get("call_id")
        timestamp = parse_timestamp(event.get("timestamp"))
        if not call_id or timestamp is None:
            continue
        if event.get("status") == "started":
            calls[call_id] = (timestamp, event.get("tool_name"), event["activity_kind"])
        elif call_id in calls:
            started, tool_name, activity_kind = calls.pop(call_id)
            elapsed = max(0, int((timestamp - started) * 1000))
            tool_durations[tool_name or "unknown"].append(elapsed)
            activity_durations[activity_kind] += elapsed

    duration_ms: int | str = "unavailable"
    if len(timestamps) >= 2:
        duration_ms = max(0, int((max(timestamps) - min(timestamps)) * 1000))
    return {
        "identity": identity,
        "session_duration_ms": duration_ms,
        "event_count": len(events),
        "activity_event_counts": dict(sorted(activity_counts.items())),
        "observed_activity_duration_ms": dict(sorted(activity_durations.items())) or "unavailable",
        "duration_note": "Observed spans may overlap and must not be summed as wall-clock time.",
        "tool_call_counts": dict(sorted(tools.items())),
        "tool_duration_ms": {
            name: {"count": len(values), "total": sum(values), "average": round(sum(values) / len(values))}
            for name, values in sorted(tool_durations.items())
        },
        "token_usage": dict(sorted(usage.items())) if usage_available else "unavailable",
    }


def load_paths(paths: list[str], runtime: str) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    loaded = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        loaded.append(normalized_events(path, runtime))
    return loaded


def command_discover(args: argparse.Namespace) -> None:
    roots = [Path(root).expanduser() for root in args.root] if args.root else default_roots(args.runtime)
    emit({"matches": discover(args.runtime, args.session_id, roots)})


def command_describe(args: argparse.Namespace) -> None:
    descriptions = []
    for identity, events in load_paths(args.path, args.runtime):
        descriptions.append({
            **identity,
            "event_types": sorted({event["event_type"] for event in events}),
            "activity_kinds": sorted({event["activity_kind"] for event in events}),
        })
    emit({"sessions": descriptions})


def command_timeline(args: argparse.Namespace) -> None:
    output = []
    for _, events in load_paths(args.path, args.runtime):
        output.extend(events)
    output.sort(key=lambda item: parse_timestamp(item.get("timestamp")) or float("inf"))
    emit({"events": output})


def command_stats(args: argparse.Namespace) -> None:
    emit({"sessions": [summarize(identity, events) for identity, events in load_paths(args.path, args.runtime)]})


def command_query(args: argparse.Namespace) -> None:
    if args.raw_pattern:
        pattern = re.compile(args.raw_pattern, re.IGNORECASE)
        records = []
        for raw in args.path:
            path = Path(raw).expanduser().resolve()
            for _, record in read_jsonl(path):
                if pattern.search(json.dumps(record, ensure_ascii=False)):
                    records.append(record)
                    if len(records) >= args.limit:
                        emit({"records": records, "truncated": True})
                        return
        emit({"records": records, "truncated": False})
        return
    pattern = re.compile(args.pattern, re.IGNORECASE) if args.pattern else None
    output = []
    for _, events in load_paths(args.path, args.runtime):
        for event in events:
            if args.activity and event.get("activity_kind") != args.activity:
                continue
            if args.event_type and event.get("event_type") != args.event_type:
                continue
            if args.tool and event.get("tool_name") != args.tool:
                continue
            if pattern and not pattern.search(json.dumps(event, ensure_ascii=False)):
                continue
            output.append(event)
    emit({"events": output})


def command_compare(args: argparse.Namespace) -> None:
    loaded = load_paths(args.path, args.runtime)
    sessions = [summarize(identity, events) for identity, events in loaded]
    intervals = []
    for identity, events in loaded:
        timestamps = [parse_timestamp(item.get("timestamp")) for item in events]
        timestamps = [item for item in timestamps if item is not None]
        if timestamps:
            intervals.append((min(timestamps), 1, identity["session_id"]))
            intervals.append((max(timestamps), -1, identity["session_id"]))
    active = maximum = 0
    for _, delta, _ in sorted(intervals, key=lambda item: (item[0], -item[1])):
        active += delta
        maximum = max(maximum, active)
    emit({"sessions": sessions, "maximum_concurrency": maximum if intervals else "unavailable"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Find persisted session files")
    discover_parser.add_argument("--runtime", choices=RUNTIMES, default="auto")
    discover_parser.add_argument("--session-id")
    discover_parser.add_argument("--root", action="append", default=[])
    discover_parser.set_defaults(func=command_discover)

    for name, help_text, function in (
        ("describe", "Describe session metadata and available event fields", command_describe),
        ("timeline", "Normalize session records into a chronological timeline", command_timeline),
        ("stats", "Calculate deterministic session and tool statistics", command_stats),
        ("compare", "Compare multiple sessions and their concurrency", command_compare),
    ):
        child = subparsers.add_parser(name, help=help_text)
        child.add_argument("--runtime", choices=RUNTIMES, default="auto")
        child.add_argument("path", nargs="+")
        child.set_defaults(func=function)

    query_parser = subparsers.add_parser("query", help="Filter normalized session events")
    query_parser.add_argument("--runtime", choices=RUNTIMES, default="auto")
    query_parser.add_argument("--activity")
    query_parser.add_argument("--event-type")
    query_parser.add_argument("--tool")
    query_parser.add_argument("--pattern")
    query_parser.add_argument("--raw-pattern", help="Search complete source records and return matching records")
    query_parser.add_argument("--limit", type=int, default=100, help="Maximum raw records to return")
    query_parser.add_argument("path", nargs="+")
    query_parser.set_defaults(func=command_query)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (FileNotFoundError, ValueError, OSError) as exc:
        emit({"error": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
