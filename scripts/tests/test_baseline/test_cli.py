import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_baseline import cli, containers, gitops, junit, runs, spec, state
from test_baseline.errors import Fault
from .support import FakePopen, RunCase, SAMPLE


class NoArgumentRepo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name).resolve()
        self.repo = self.root / "crm-api"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("one")
        self.git(self.repo, "add", "a.txt")
        self.git(self.repo, "commit", "-q", "-m", "init")
        specs = {"crm": spec.parse_testing(SAMPLE)}
        for patch in (
            mock.patch.object(spec, "PROJECTS", self.root),
            mock.patch.object(spec, "load_specs", return_value=specs),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.dir.cleanup()

    def git(self, path, *args):
        subprocess.run(
            ["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t", *args],
            check=True,
            capture_output=True,
        )

    def run_main(self, cwd, argv):
        err = io.StringIO()
        recorded = []
        with (
            mock.patch("os.getcwd", return_value=str(cwd)),
            mock.patch.object(cli, "record_baseline", side_effect=lambda repo: recorded.append(repo) or repo),
            mock.patch.object(cli, "baseline_row", side_effect=lambda repo: [repo, "x", "1", "0", "1s"]),
            mock.patch.object(sys, "argv", ["test-baseline.py", "baseline", *argv]),
            mock.patch.object(sys, "stderr", err),
            mock.patch.object(sys, "stdout", io.StringIO()),
        ):
            code = cli.main()

        return code, recorded, err.getvalue()

    def test_no_args_in_repo_baselines_that_repo_only(self):
        sub = self.repo / "nested"
        sub.mkdir()

        self.assertEqual(self.run_main(self.repo, []), (0, ["crm-api"], ""))
        self.assertEqual(self.run_main(sub, [])[1], ["crm-api"])

    def test_no_args_in_linked_worktree_uses_main_checkout_name(self):
        tree = self.root / "elsewhere" / "ticket-1"
        self.git(self.repo, "worktree", "add", "-q", "--detach", str(tree))

        self.assertEqual(self.run_main(tree, [])[1], ["crm-api"])

    def test_no_args_outside_a_repo_exits_2(self):
        code, recorded, err = self.run_main(self.root, [])

        self.assertEqual((code, recorded), (2, []))
        self.assertIn("not inside a git repo", err)
        self.assertIn("name repos explicitly", err)

    def test_no_args_in_unknown_repo_exits_2(self):
        other = self.root / "other"
        other.mkdir()
        self.git(other, "init", "-q")

        code, recorded, err = self.run_main(other, [])

        self.assertEqual((code, recorded), (2, []))
        self.assertIn("no [repo] section", err)

    def test_no_args_in_repo_outside_projects_exits_2(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "crm-api"
            path.mkdir()
            self.git(path, "init", "-q")

            code, recorded, err = self.run_main(path, [])

        self.assertEqual((code, recorded), (2, []))
        self.assertIn("is not a repo directly under", err)

    def test_explicit_args_are_unchanged(self):
        code, recorded, err = self.run_main(self.root, ["crm-web", "crm-api"])

        self.assertEqual((code, recorded, err), (0, ["crm-web", "crm-api"], ""))


class RecordedCompare(RunCase):
    def test_fault_leaves_a_done_record_with_exit_2(self):
        key = self.key()
        self.write_run(key)

        with mock.patch.object(cli, "compare", side_effect=Fault("boom")):
            outcome = cli.compare_recorded(str(self.repo), key.path)

        record = runs.load_run(key.path)
        self.assertEqual(outcome, cli.Outcome("ERROR boom", 2))
        self.assertEqual((record.status, record.exit, record.report), ("done", 2, "ERROR boom"))
        self.assertGreater(record.finished_at, 0)

    def test_result_is_stored_on_the_record(self):
        key = self.key()
        self.write_run(key)

        with mock.patch.object(cli, "compare", return_value=cli.Outcome("R\nRESULT clean", 0)):
            cli.compare_recorded(str(self.repo), key.path)

        record = runs.load_run(key.path)
        self.assertEqual((record.status, record.exit, record.report), ("done", 0, "R\nRESULT clean"))

    def compare_with_stubs(self, key):
        snapshot = {"tests": {}, "units": {}}
        stubs = (
            mock.patch.object(containers, "ensure_containers"),
            mock.patch.object(cli, "baseline_locked", return_value=snapshot),
            mock.patch.object(junit, "execute", return_value=junit.Result()),
            mock.patch.object(cli, "guard_cargo"),
        )
        with contextlib.ExitStack() as stack:
            mocks = [stack.enter_context(stub) for stub in stubs]
            cli.compare_recorded(str(self.repo), key.path)

        return mocks[2]

    def test_record_keyed_by_another_tree_runs_nothing(self):
        key = self.key()
        self.write_run(key, fingerprint="0" * 64)

        execute = self.compare_with_stubs(key)

        record = runs.load_run(key.path)
        execute.assert_not_called()
        self.assertEqual(
            (record.status, record.exit, record.report),
            ("done", 2, "ERROR tree changed before the run started"),
        )

    def test_record_keyed_by_another_merge_base_runs_nothing(self):
        key = self.key()
        self.write_run(key, merge_base="f" * 40)

        execute = self.compare_with_stubs(key)

        execute.assert_not_called()
        self.assertEqual(runs.load_run(key.path).exit, 2)

    def test_merge_base_moved_before_the_lock_runs_nothing(self):
        key = self.key()
        self.write_run(key)
        real = gitops.local_merge_base
        calls = []

        def moving(tree, base):
            calls.append(1)

            return real(tree, base) if len(calls) == 1 else "e" * 40

        with mock.patch.object(cli.gitops, "local_merge_base", moving):
            execute = self.compare_with_stubs(key)

        record = runs.load_run(key.path)
        execute.assert_not_called()
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            (record.status, record.exit, record.report),
            ("done", 2, "ERROR tree changed before the run started"),
        )

    def test_matching_record_runs_as_before(self):
        key = self.key()
        self.write_run(key)

        execute = self.compare_with_stubs(key)

        record = runs.load_run(key.path)
        execute.assert_called_once()
        self.assertEqual((record.status, record.exit), ("done", 0))
        self.assertTrue(record.report.endswith("RESULT clean"))


    def test_rerun_start_computes_again_instead_of_reusing_the_last_compare(self):
        key = self.key()
        self.write_run(key, status="done", exit=0, report="OLD\nRESULT clean")
        state.write_json(
            state.last_compare_path("crm-api"),
            {"fingerprint": key.fingerprint, "report": "OLD\nRESULT clean", "exit": 0},
        )

        code, out = self.invoke(lambda tree: runs.start(tree, True))
        execute = self.compare_with_stubs(key)

        record = runs.load_run(key.path)
        self.assertEqual(code, 0)
        self.assertIn("started run", out)
        execute.assert_called_once()
        self.assertEqual((record.status, record.exit), ("done", 0))
        self.assertNotIn("REUSED", record.report)
        self.assertNotIn("OLD", record.report)

    def test_without_rerun_the_last_compare_is_reused(self):
        key = self.key()
        self.write_run(key)
        state.write_json(
            state.last_compare_path("crm-api"),
            {"fingerprint": key.fingerprint, "report": "OLD\nRESULT clean", "exit": 0},
        )

        execute = self.compare_with_stubs(key)

        execute.assert_not_called()
        self.assertIn("REUSED", runs.load_run(key.path).report)


class EmptyFullSuite(RunCase):
    def setUp(self):
        super().setUp()
        text = "\n".join(line for line in SAMPLE.splitlines() if not line.startswith("full:"))
        specs = {"crm": spec.parse_testing(text)}
        patch = mock.patch.object(spec, "load_specs", return_value=specs)
        patch.start()
        self.addCleanup(patch.stop)

    def run_main(self, *argv):
        err = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["test-baseline.py", *argv]),
            mock.patch.object(sys, "stderr", err),
            mock.patch.object(sys, "stdout", io.StringIO()),
        ):
            code = cli.main()

        return code, err.getvalue()

    def test_focused_lines_still_parse(self):
        parsed = spec.parse_testing(SAMPLE.replace("full: npm run build\n", ""))

        self.assertEqual(len(parsed.repos["crm-web"].focused), 1)

    def test_every_subcommand_exits_2_with_the_same_message(self):
        message = "no full suite configured for repo crm-api"
        for argv in (
            ("start", str(self.repo)),
            ("wait", str(self.repo)),
            ("status", str(self.repo)),
            ("compare", str(self.repo)),
            ("baseline", "crm-api"),
        ):
            with self.subTest(argv=argv):
                code, err = self.run_main(*argv)

                self.assertEqual(code, 2)
                self.assertIn(message, err)
        self.assertEqual(FakePopen.calls, [])
