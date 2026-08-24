"""Local integration tests against real Codex and Claude Code JSONL records.

These tests never copy transcript content into the repository. They skip only when the
corresponding runtime has no local persisted session of the requested kind.
"""

import importlib.util
import os
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "session_tools.py"
SPEC = importlib.util.spec_from_file_location("real_session_tools", SCRIPT)
session_tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session_tools)
REQUIRE_REAL_SESSIONS = os.environ.get("HIVE_SENTINEL_REQUIRE_REAL_SESSIONS") == "1"


def require_or_skip(test_case, path, message):
    if path is not None:
        return
    if REQUIRE_REAL_SESSIONS:
        test_case.fail(message)
    test_case.skipTest(message)


def codex_files():
    root = Path.home() / ".codex" / "sessions"
    return root.rglob("*.jsonl") if root.is_dir() else []


def claude_files():
    root = Path.home() / ".claude" / "projects"
    return root.rglob("*.jsonl") if root.is_dir() else []


def select_session(runtime, want_subagent):
    paths = codex_files() if runtime == "codex" else claude_files()
    existing = [path for path in paths if path.is_file()]
    for path in sorted(existing, key=lambda item: item.stat().st_mtime, reverse=True):
        is_subagent_path = path.parent.name == "subagents"
        if runtime == "claude" and is_subagent_path != want_subagent:
            continue
        try:
            identity = session_tools.session_identity(path, runtime)
        except OSError:
            continue
        is_subagent = bool(identity["parent_session_id"])
        if is_subagent == want_subagent and identity["session_id"]:
            return path
    return None


class RealCodexSessionTests(unittest.TestCase):
    def test_real_main_session_normalizes_and_summarizes(self):
        path = select_session("codex", want_subagent=False)
        require_or_skip(self, path, "no persisted Codex main session found")

        identity, events = session_tools.normalized_events(path, "codex")
        stats = session_tools.summarize(identity, events)

        self.assertEqual("codex", identity["runtime"])
        self.assertTrue(identity["session_id"])
        self.assertGreater(identity["record_count"], 0)
        self.assertGreater(len(events), 0)
        self.assertGreater(stats["event_count"], 0)

    def test_real_subagent_preserves_parent_relationship(self):
        path = select_session("codex", want_subagent=True)
        require_or_skip(self, path, "no persisted Codex subagent session found")

        identity, events = session_tools.normalized_events(path, "codex")

        self.assertTrue(identity["parent_session_id"])
        self.assertTrue(identity["agent_path"] or identity["agent_name"])
        self.assertGreater(len(events), 0)


class RealClaudeSessionTests(unittest.TestCase):
    def test_real_main_session_normalizes_and_summarizes(self):
        path = select_session("claude", want_subagent=False)
        require_or_skip(self, path, "no persisted Claude Code main session found")

        identity, events = session_tools.normalized_events(path, "claude")
        stats = session_tools.summarize(identity, events)

        self.assertEqual("claude", identity["runtime"])
        self.assertTrue(identity["session_id"])
        self.assertGreater(identity["record_count"], 0)
        self.assertGreater(len(events), 0)
        self.assertGreater(stats["event_count"], 0)

    def test_real_subagent_uses_transcript_path_as_agent_identity(self):
        path = select_session("claude", want_subagent=True)
        require_or_skip(self, path, "no persisted Claude Code subagent session found")

        identity, events = session_tools.normalized_events(path, "claude")

        self.assertEqual(identity["session_id"], identity["parent_session_id"])
        self.assertTrue(identity["agent_name"].startswith("agent-"))
        self.assertTrue(identity["agent_path"].startswith("subagents/"))
        self.assertGreater(len(events), 0)


if __name__ == "__main__":
    unittest.main()
