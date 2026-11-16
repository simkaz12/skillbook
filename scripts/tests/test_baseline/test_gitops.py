import subprocess
import tempfile
import unittest
from pathlib import Path

from test_baseline import gitops
from test_baseline.errors import Fault
from .support import UpstreamCase, commit_file, git_in


class Fingerprint(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name)
        subprocess.run(["git", "-C", str(self.path), "init", "-q"], check=True)
        (self.path / "a.txt").write_text("one")

    def tearDown(self):
        self.dir.cleanup()

    def test_stable(self):
        self.assertEqual(gitops.fingerprint(self.path, "abc"), gitops.fingerprint(self.path, "abc"))

    def test_untracked_file_changes_it(self):
        before = gitops.fingerprint(self.path, "abc")
        (self.path / "new.txt").write_text("x")

        self.assertNotEqual(before, gitops.fingerprint(self.path, "abc"))

    def test_env_file_and_commit_change_it(self):
        before = gitops.fingerprint(self.path, "abc")

        self.assertNotEqual(before, gitops.fingerprint(self.path, "def"))

        (self.path / ".env").write_text("A=1")
        with_env = gitops.fingerprint(self.path, "abc")
        self.assertNotEqual(before, with_env)

        (self.path / ".env").write_text("A=2")
        self.assertNotEqual(with_env, gitops.fingerprint(self.path, "abc"))

    def test_tracked_file_matching_ignore_rule_still_counts(self):
        base = ["git", "-C", str(self.path), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*base, "add", "a.txt"], check=True)
        subprocess.run([*base, "commit", "-q", "-m", "init"], check=True)
        (self.path / ".gitignore").write_text("a.txt\n")
        before = gitops.fingerprint(self.path, "abc")

        (self.path / "a.txt").write_text("changed")

        self.assertNotEqual(before, gitops.fingerprint(self.path, "abc"))

    def test_real_index_untouched(self):
        gitops.fingerprint(self.path, "abc")
        staged = subprocess.run(
            ["git", "-C", str(self.path), "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
        ).stdout

        self.assertEqual(staged, "")


class RunSetup(unittest.TestCase):
    def test_failing_setup_command_raises(self):
        with tempfile.TemporaryDirectory() as scratch:
            log = Path(scratch) / "setup.log"

            with self.assertRaises(Fault) as ctx:
                gitops.run_setup("exit 3", scratch, {}, log)
            self.assertIn("exit 3", str(ctx.exception))

    def test_passing_setup_command_returns(self):
        with tempfile.TemporaryDirectory() as scratch:
            gitops.run_setup("true", scratch, {}, Path(scratch) / "setup.log")

    def test_failed_install_during_link_or_install_raises(self):
        with tempfile.TemporaryDirectory() as scratch:
            main = Path(scratch) / "main"
            tree = Path(scratch) / "tree"
            for path in (main, tree):
                path.mkdir()
            (main / "composer.lock").write_text("a")
            (tree / "composer.lock").write_text("b")

            with self.assertRaises(Fault):
                gitops.link_or_install(main, tree, "vendor", "composer.lock", "false", {}, tree / "log")


class LinkOrInstall(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.main = root / "main"
        self.tree = root / "tree"
        for path in (self.main, self.tree):
            path.mkdir()
            (path / "composer.lock").write_text("lock")
        (self.main / "vendor" / "composer").mkdir(parents=True)
        (self.main / "vendor" / "composer" / "autoload_psr4.php").write_text("main")
        (self.main / "vendor" / "autoload.php").write_text("loader")
        (self.main / "vendor" / "laravel").mkdir()
        (self.tree / "vendor").mkdir()
        (self.tree / "vendor" / "stale").write_text("x")

    def tearDown(self):
        self.dir.cleanup()

    def link(self):
        log = self.tree / "log"
        gitops.link_or_install(self.main, self.tree, "vendor", "composer.lock", "true", {}, log)

    def test_installed_directory_is_replaced_by_a_copy_when_locks_match(self):
        self.link()

        vendor = self.tree / "vendor"
        self.assertFalse(vendor.is_symlink())
        self.assertFalse((vendor / "stale").exists())
        self.assertEqual((vendor / "composer" / "autoload_psr4.php").read_text(), "main")

    def test_copy_does_not_write_through_to_the_main_checkout(self):
        self.link()

        (self.tree / "vendor" / "composer" / "autoload_psr4.php").write_text("tree")

        self.assertEqual((self.main / "vendor" / "composer" / "autoload_psr4.php").read_text(), "main")

    def test_relinking_over_an_existing_copy_works(self):
        self.link()
        self.link()

        self.assertTrue((self.tree / "vendor" / "laravel").is_dir())

    def test_node_modules_is_linked(self):
        for path in (self.main, self.tree):
            (path / "package-lock.json").write_text("lock")
        (self.main / "node_modules").mkdir()

        log = self.tree / "log"
        gitops.link_or_install(self.main, self.tree, "node_modules", "package-lock.json", "true", {}, log)

        self.assertTrue((self.tree / "node_modules").is_symlink())

    def test_laravel_dirs_created_only_for_laravel_trees(self):
        gitops.make_laravel_dirs(self.tree)
        self.assertFalse((self.tree / "storage").exists())

        (self.tree / "artisan").write_text("")
        gitops.make_laravel_dirs(self.tree)
        self.assertTrue((self.tree / "storage" / "framework" / "views").is_dir())


class MergeBase(UpstreamCase):
    def test_branch_ahead_of_origin_resolves_to_the_fork_point(self):
        git_in(self.repo, "checkout", "-q", "-b", "feature")
        commit_file(self.repo, "b.txt")
        commit_file(self.repo, "c.txt")
        commit_file(self.upstream, "d.txt")

        self.assertEqual(gitops.merge_base(self.repo, "dev"), self.fork)

    def test_tree_on_the_base_resolves_to_head(self):
        self.assertEqual(gitops.merge_base(self.repo, "dev"), git_in(self.repo, "rev-parse", "HEAD"))

    def test_fetch_runs_once_per_invocation(self):
        commit_file(self.upstream, "d.txt")
        gitops.merge_base(self.repo, "dev")
        after_first = git_in(self.repo, "rev-parse", "origin/dev")
        commit_file(self.upstream, "e.txt")

        gitops.merge_base(self.repo, "dev")

        self.assertEqual(git_in(self.repo, "rev-parse", "origin/dev"), after_first)

    def test_missing_remote_ref_faults(self):
        with self.assertRaises(Fault) as ctx:
            gitops.local_merge_base(self.repo, "nope")

        self.assertIn("cannot compute merge-base with origin/nope", str(ctx.exception))


class RunFingerprint(UpstreamCase):
    def test_ticket_artifacts_do_not_change_it_but_source_does(self):
        before = gitops.run_fingerprint(self.repo, "id")

        for name in ("docs/verification/x.md", "docs/specs/y.md", "docs/qa/z.md", ".claude/s.json"):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text("artifact")
        self.assertEqual(before, gitops.run_fingerprint(self.repo, "id"))
        self.assertNotEqual(before, gitops.fingerprint(self.repo, "id"))

        (self.repo / "src").mkdir()
        (self.repo / "src" / "a.py").write_text("code")
        self.assertNotEqual(before, gitops.run_fingerprint(self.repo, "id"))

    def test_identity_still_counts(self):
        self.assertNotEqual(gitops.run_fingerprint(self.repo, "one"), gitops.run_fingerprint(self.repo, "two"))
