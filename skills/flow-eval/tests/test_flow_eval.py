import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "flow_eval.py"


def run(*arguments, check=True):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, arguments)],
        text=True,
        capture_output=True,
        check=check,
    )


def read(path):
    return json.loads(Path(path).read_text())


class FlowEvalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.case = self.root / "case"
        run("init", self.case)
        manifest = read(self.case / "manifest.json")
        manifest.update(
            {
                "case_id": "case-one",
                "limits": {"run_cap": 2, "timeout_seconds": 1},
                "variants": {
                    "baseline": {"model": "same", "environment": {"tool": "same"}, "planned_phases": ["recon", "grill", "to-spec", "runner", "reviewer"]},
                    "candidate": {"model": "same", "environment": {"tool": "same"}, "planned_phases": ["recon", "grill", "to-spec", "runner", "reviewer"]},
                },
            }
        )
        (self.case / "manifest.json").write_text(json.dumps(manifest))
        (self.case / "public" / "owner-answers.md").write_text("fixed owner answer\n")
        (self.case / "private" / "expected.md").write_text("DO NOT LEAK EXPECTED ANSWER\n")
        self.worker = self.root / "worker.py"
        self.worker.write_text(
            "import json, pathlib, sys, time\n"
            "out = pathlib.Path(sys.argv[1]); mode = sys.argv[2]; out.mkdir(parents=True, exist_ok=True)\n"
            "if mode == 'sleep': time.sleep(5)\n"
            "(out / 'result.md').write_text('result ' + mode)\n"
            "main = [\n"
            " {'message': {'id': 'm1', 'usage': {'input_tokens': 10, 'cache_read_input_tokens': 1, 'cache_creation_input_tokens': 2, 'output_tokens': 3}}},\n"
            " {'message': {'id': 'm1', 'usage': {'input_tokens': 10, 'cache_read_input_tokens': 1, 'cache_creation_input_tokens': 2, 'output_tokens': 5}}},\n"
            " {'message': {'id': 'm2', 'usage': {'input_tokens': 6, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0, 'output_tokens': 2}}}\n"
            "]\n"
            "(out / 'main.jsonl').write_text('\\n'.join(json.dumps(x) for x in main) + '\\n')\n"
            "child = {'message': {'id': 'c1', 'usage': {'input_tokens': 4, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0, 'output_tokens': 1}}}\n"
            "(out / 'child.jsonl').write_text(json.dumps(child) + '\\n')\n"
            "if mode != 'no-inventory':\n"
            " phases = json.loads(__import__('os').environ['FLOW_EVAL_PLANNED_PHASES'])\n"
            " sessions = [{'id': 'coordinator', 'phases': phases, 'usage': 'main.jsonl'}]\n"
            " if mode != 'one-hand': sessions.append({'id': 'child', 'phases': ['recon'], 'usage': 'child.jsonl'})\n"
            " inventory = {'profile_sha256': __import__('os').environ['FLOW_EVAL_PROFILE_SHA256'], 'sessions': sessions}\n"
            " (out / 'sessions.json').write_text(json.dumps(inventory))\n"
            "if mode == 'nonzero': raise SystemExit(7)\n"
        )

    def tearDown(self):
        self.directory.cleanup()

    def command(self, variant, name, mode="ok", inventory=True):
        result = ["run", self.case, "--variant", variant, "--out", self.root / name]
        if inventory:
            result.extend(["--session-inventory", "{output}/sessions.json"])
        result.extend(["--artifact", "{output}/result.md"])
        result.extend(["--", sys.executable, self.worker, "{output}", mode])
        return run(*result)

    def shorten_inventory(self):
        manifest = read(self.case / "manifest.json")
        for variant in manifest["variants"].values():
            variant["planned_phases"] = ["recon"]
        (self.case / "manifest.json").write_text(json.dumps(manifest))

    def test_blind_bundle_dedupes_usage_and_excludes_private_inputs(self):
        self.command("baseline", "one")
        self.command("candidate", "two", "one-hand")
        workspace = self.root / "one" / "workspace"
        self.assertFalse((workspace / "private").exists())
        visible = "\n".join(path.read_text() for path in workspace.rglob("*") if path.is_file())
        self.assertNotIn("DO NOT LEAK", visible)
        self.assertNotIn("baseline", visible)
        self.assertNotIn("candidate", visible)
        self.assertEqual(read(self.root / "one" / "control.json")["public_fixture_sha256"], read(self.root / "two" / "control.json")["public_fixture_sha256"])
        review = self.root / "review"
        run("review-pack", self.case, "--run", self.root / "one", "--run", self.root / "two", "--out", review)
        self.assertFalse((review / "blind-report.json").read_text().find("baseline") >= 0)
        self.assertFalse((review / "blind-report.json").read_text().find("candidate") >= 0)
        self.assertFalse((review / "blind-report.json").read_text().find("input_tokens") >= 0)
        quality = read(review / "quality-template.json")
        quality["review_complete"] = True
        for entry in quality["entries"]:
            entry["quality"] = "pass"
        (review / "quality.json").write_text(json.dumps(quality))
        cost = self.root / "cost.json"
        run("cost-report", self.case, "--review", review, "--quality", review / "quality.json", "--run", self.root / "one", "--run", self.root / "two", "--out", cost)
        totals = read(cost)["runs"][0]["token_totals"]
        self.assertEqual(totals, {"input_tokens": 20, "cache_read_input_tokens": 1, "cache_creation_input_tokens": 2, "output_tokens": 8})
        self.assertEqual(read(cost)["runs"][0]["profile_activation"], "attested")
        self.assertEqual(len(read(cost)["runs"][0]["sessions"]), 2)
        self.assertEqual(len(read(cost)["runs"][1]["sessions"]), 1)
        self.assertTrue((review / "entry-01" / "artifacts" / "result.md").exists())
        self.assertFalse((review / "entry-01" / "stdout.log").exists())
        self.assertFalse(any(path.name.endswith(".jsonl") for path in review.rglob("*")))
        self.assertTrue((workspace / ".claude" / "skills").is_dir())
        self.assertTrue((workspace / ".claude" / "agents").is_dir())

    def test_missing_inventory_stays_unknown_instead_of_zero(self):
        self.shorten_inventory()
        self.command("baseline", "one")
        self.command("candidate", "two", "no-inventory", inventory=False)
        review = self.root / "review"
        run("review-pack", self.case, "--run", self.root / "one", "--run", self.root / "two", "--out", review)
        quality = {"review_complete": True, "entries": [{"entry": "entry-01"}, {"entry": "entry-02"}]}
        (review / "quality.json").write_text(json.dumps(quality))
        cost = self.root / "cost.json"
        run("cost-report", self.case, "--review", review, "--quality", review / "quality.json", "--run", self.root / "one", "--run", self.root / "two", "--out", cost)
        candidate = next(row for row in read(cost)["runs"] if row["variant"] == "candidate")
        self.assertEqual(candidate["usage_status"], "incomplete")
        self.assertIsNone(candidate["token_totals"])
        self.assertEqual(candidate["sessions"], {})

    def test_blind_bundle_rejects_a_changed_public_fixture(self):
        self.command("baseline", "one")
        (self.case / "public" / "ticket.md").write_text("changed after the first run\n")
        self.command("candidate", "two")
        result = run("review-pack", self.case, "--run", self.root / "one", "--run", self.root / "two", "--out", self.root / "review", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("public fixture changed", result.stderr)

    def test_timeout_and_nonzero_exit_are_recorded(self):
        self.shorten_inventory()
        self.command("baseline", "timeout", "sleep", inventory=False)
        self.command("candidate", "nonzero", "nonzero")
        timeout = read(self.root / "timeout" / "control.json")
        nonzero = read(self.root / "nonzero" / "control.json")
        self.assertTrue(timeout["timed_out"])
        self.assertEqual(nonzero["exit_code"], 7)
        self.assertTrue((self.root / "timeout" / "stdout.log").exists())
        self.assertTrue((self.root / "nonzero" / "stderr.log").exists())

    def test_run_cap_persists_and_variant_metadata_must_match(self):
        self.shorten_inventory()
        self.command("baseline", "one")
        self.command("candidate", "two")
        capped = self.command_result("baseline", "three")
        self.assertNotEqual(capped.returncode, 0)
        self.assertIn("run cap reached", capped.stderr)
        self.case = self.root / "other-case"
        run("init", self.case)
        manifest = read(self.case / "manifest.json")
        manifest["variants"]["candidate"]["model"] = "different"
        (self.case / "manifest.json").write_text(json.dumps(manifest))
        mismatch = self.command_result("baseline", "mismatch")
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("metadata differ", mismatch.stderr)

    def command_result(self, variant, name):
        return run("run", self.case, "--variant", variant, "--out", self.root / name, "--artifact", "{output}/result.md", "--", sys.executable, self.worker, "{output}", "ok", check=False)


if __name__ == "__main__":
    unittest.main()
