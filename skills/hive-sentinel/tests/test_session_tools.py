import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "session_tools.py"
SPEC = importlib.util.spec_from_file_location("session_tools", SCRIPT)
session_tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session_tools)


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


class CodexSessionTests(unittest.TestCase):
    def test_identity_timeline_and_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-root.jsonl"
            write_jsonl(path, [
                {"timestamp": "2026-01-01T00:00:00Z", "type": "session_meta", "payload": {
                    "id": "root", "session_id": "root", "cwd": "/repo",
                    "source": {"subagent": {"thread_spawn": {
                        "parent_thread_id": "queen", "agent_path": "/root/api", "agent_nickname": "Ada"
                    }}}
                }},
                {"timestamp": "2026-01-01T00:00:01Z", "type": "response_item", "payload": {
                    "type": "custom_tool_call", "name": "exec_command", "call_id": "call-1",
                    "status": "in_progress", "input": {"cmd": "pytest -q"}
                }},
                {"timestamp": "2026-01-01T00:00:03Z", "type": "response_item", "payload": {
                    "type": "custom_tool_call_output", "call_id": "call-1", "output": "ok"
                }},
                {"timestamp": "2026-01-01T00:00:04Z", "type": "event_msg", "payload": {
                    "type": "token_count", "info": {"last_token_usage": {
                        "input_tokens": 12, "output_tokens": 3, "reasoning_output_tokens": 4, "total_tokens": 19
                    }}
                }},
            ])

            identity, events = session_tools.normalized_events(path)
            stats = session_tools.summarize(identity, events)

        self.assertEqual("codex", identity["runtime"])
        self.assertEqual("queen", identity["parent_session_id"])
        self.assertEqual("/root/api", identity["agent_path"])
        self.assertEqual(4000, stats["session_duration_ms"])
        self.assertEqual(1, stats["tool_call_counts"]["exec_command"])
        self.assertEqual(2000, stats["tool_duration_ms"]["exec_command"]["total"])
        self.assertEqual(
            {"input_tokens": 12, "output_tokens": 3, "reasoning_tokens": 4, "total_tokens": 19},
            stats["token_usage"],
        )
        self.assertEqual(2000, stats["observed_activity_duration_ms"]["test"])


class ClaudeSessionTests(unittest.TestCase):
    def test_tool_events_and_usage_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claude-session.jsonl"
            write_jsonl(path, [
                {"timestamp": "2026-01-01T00:00:00Z", "type": "assistant", "sessionId": "claude-1", "cwd": "/repo",
                 "message": {"role": "assistant", "usage": {"input_tokens": 7, "output_tokens": 2},
                             "content": [{"type": "tool_use", "id": "tool-1", "name": "Bash", "input": {}}]}},
                {"timestamp": "2026-01-01T00:00:05Z", "type": "user", "sessionId": "claude-1",
                 "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tool-1", "content": "ok"}]}},
            ])

            identity, events = session_tools.normalized_events(path)
            stats = session_tools.summarize(identity, events)

        self.assertEqual("claude", identity["runtime"])
        self.assertEqual("claude-1", identity["session_id"])
        self.assertEqual(["assistant", "tool_use", "tool_result"], [event["event_type"] for event in events])
        self.assertEqual(5000, stats["tool_duration_ms"]["Bash"]["total"])
        self.assertEqual({"input_tokens": 7, "output_tokens": 2}, stats["token_usage"])

    def test_subagent_path_distinguishes_agent_from_parent_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "session-1" / "subagents"
            directory.mkdir(parents=True)
            path = directory / "agent-worker.jsonl"
            write_jsonl(path, [{
                "timestamp": "2026-01-01T00:00:00Z", "type": "assistant",
                "sessionId": "session-1", "cwd": "/repo", "message": {"content": []},
            }])

            identity = session_tools.session_identity(path, "claude")

        self.assertEqual("session-1", identity["parent_session_id"])
        self.assertEqual("agent-worker", identity["agent_name"])


class DiscoveryAndComparisonTests(unittest.TestCase):
    def test_discovery_finds_exact_session_and_comparison_counts_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "one.jsonl"
            second = root / "two.jsonl"
            write_jsonl(first, [
                {"timestamp": "2026-01-01T00:00:00Z", "type": "session_meta", "payload": {"id": "one"}},
                {"timestamp": "2026-01-01T00:00:10Z", "type": "event_msg", "payload": {"type": "task_complete"}},
            ])
            write_jsonl(second, [
                {"timestamp": "2026-01-01T00:00:05Z", "type": "session_meta", "payload": {"id": "two"}},
                {"timestamp": "2026-01-01T00:00:15Z", "type": "event_msg", "payload": {"type": "task_complete"}},
            ])

            matches = session_tools.discover("codex", "one", [root])
            loaded = [session_tools.normalized_events(first), session_tools.normalized_events(second)]
            intervals = []
            for identity, events in loaded:
                times = [session_tools.parse_timestamp(event["timestamp"]) for event in events]
                intervals.extend([(min(times), 1), (max(times), -1)])
            active = maximum = 0
            for _, delta in sorted(intervals, key=lambda item: (item[0], -item[1])):
                active += delta
                maximum = max(maximum, active)

        self.assertEqual(1, len(matches))
        self.assertEqual("one", matches[0]["session_id"])
        self.assertEqual(2, maximum)

    def test_raw_query_is_explicit_and_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            write_jsonl(path, [
                {"type": "message", "content": "needle one"},
                {"type": "message", "content": "needle two"},
            ])
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "query", "--raw-pattern", "needle", "--limit", "1", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            output = json.loads(result.stdout)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(output["records"]))
        self.assertTrue(output["truncated"])


if __name__ == "__main__":
    unittest.main()
