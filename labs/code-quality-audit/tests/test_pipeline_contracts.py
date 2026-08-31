import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


aggregate = load_module("aggregate", SCRIPTS / "aggregate.py")
build_manifest = load_module("build_manifest", SCRIPTS / "build_manifest.py")


class ManifestTests(unittest.TestCase):
    def test_unit_ids_are_file_qualified_and_shards_carry_closed_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "a.py").write_text("def main():\n    pass\n", encoding="utf-8")
            (repo / "b.py").write_text("def main():\n    pass\n", encoding="utf-8")
            files, _ = build_manifest.scan(str(repo))
            shards = build_manifest.build_shards(files, 2000)

        ids = [unit["id"] for file in files for unit in file["units"]]
        self.assertEqual(2, len(ids))
        self.assertEqual(2, len(set(ids)))
        self.assertIn("a.py::function::main@1", ids)
        self.assertIn("b.py::function::main@1", ids)
        self.assertEqual(set(ids), set(shards[0]["assigned_units"]))
        self.assertEqual(["a.py", "b.py"], shards[0]["summary_files"])


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.source = "src/a.py"
        self.unit = "src/a.py::function::main@1"
        self.manifest = {
            "files": [{"path": self.source, "is_test": False}],
            "shards": [{
                "id": "src-00",
                "kind": "src",
                "assigned_units": [self.unit],
                "summary_files": [self.source],
            }],
        }
        self.shard = {
            "shard_id": "src-00",
            "coverage": {"assigned": [self.unit], "reviewed": [self.unit], "skipped": []},
            "summary": [{"file": self.source}],
        }
        self.cross = [
            (f"cross-{item}.json", {
                "coverage": {"assigned": [self.source], "reviewed": [self.source]}
            })
            for item in aggregate.REQUIRED_CROSS_ITEMS
        ]

    def test_exact_manifest_coverage_passes(self):
        result = aggregate.coverage_audit(
            self.manifest, [("shard-src-00.json", self.shard)], self.cross)
        self.assertTrue(result["pass"])
        self.assertEqual(1, result["assigned"])

    def test_extra_review_and_missing_summary_fail_with_retry_target(self):
        self.shard["coverage"]["reviewed"].append("src/b.py::function::main@1")
        self.shard["summary"] = []
        result = aggregate.coverage_audit(
            self.manifest, [("shard-src-00.json", self.shard)], self.cross)
        self.assertFalse(result["pass"])
        gap = next(g for g in result["gaps"] if g.get("shard") == "src-00")
        self.assertEqual(["src/b.py::function::main@1"], gap["extra_reviewed"])
        self.assertEqual([self.source], gap["missing_summaries"])
        self.assertEqual(["src-00"], aggregate.gap_report(result)["retry_shards"])

    def test_missing_shard_is_retryable(self):
        result = aggregate.coverage_audit(self.manifest, [], self.cross)
        self.assertFalse(result["pass"])
        self.assertEqual(["src-00"], aggregate.gap_report(result)["retry_shards"])


class ToolGateTests(unittest.TestCase):
    def test_strict_gate_requires_every_parseable_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            tools = ws / "tools"
            (tools / "jscpd").mkdir(parents=True)
            (ws / "manifest.json").write_text(
                json.dumps({"totals": {"langs": ["python"]}}), encoding="utf-8")
            (tools / "tools_report.json").write_text(json.dumps({
                "available": ["cloc", "lizard", "jscpd", "semgrep", "gitleaks"],
                "missing": [],
            }), encoding="utf-8")
            (tools / "cloc.json").write_text('{"SUM": {}}', encoding="utf-8")
            (tools / "semgrep.json").write_text(
                '{"results": [], "errors": []}', encoding="utf-8")
            (tools / "gitleaks.json").write_text("[]", encoding="utf-8")
            (tools / "jscpd" / "jscpd-report.json").write_text(
                '{"statistics": {}}', encoding="utf-8")
            (tools / "lizard.csv").write_text("name,nloc\nmain,2\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_tools.py"), str(ws)],
                capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            ready = json.loads((tools / "READY.json").read_text(encoding="utf-8"))
            self.assertTrue(ready["strict"])

            (tools / "semgrep.json").unlink()
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_tools.py"), str(ws)],
                capture_output=True, text=True, check=False)
            self.assertEqual(1, result.returncode)
            self.assertFalse((tools / "READY.json").exists())


if __name__ == "__main__":
    unittest.main()
