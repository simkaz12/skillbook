import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from test_baseline import gitops, spec, state
from .support import UpstreamCase, commit_file, git_in


class Matches(unittest.TestCase):
    def test_config_change_makes_snapshot_unusable(self):
        snapshot = {"created_at": time.time(), "config": "a"}

        self.assertTrue(state.matches(snapshot, "a"))
        self.assertFalse(state.matches(snapshot, "b"))
        self.assertFalse(state.matches(None, "a"))

    def test_old_snapshot_is_still_used(self):
        self.assertTrue(state.matches({"created_at": 0, "config": "a"}, "a"))

    def test_config_hash_tracks_base_and_full_commands(self):
        one = spec.parse_testing("base: dev\n\n[r]\nfocused: f\nfull: x\n")
        two = spec.parse_testing("base: dev\n\n[r]\nfocused: f\nfull: y\n")
        three = spec.parse_testing("base: main\n\n[r]\nfocused: f\nfull: x\n")
        same = spec.parse_testing("base: dev\n\n[r]\nfocused: other\nfull: x\n")

        hashes = [state.config_hash(s, s.repos["r"]) for s in (one, two, three, same)]

        self.assertEqual(len(set(hashes)), 3)
        self.assertEqual(hashes[0], hashes[3])


class Locking(unittest.TestCase):
    def test_second_caller_waits_for_the_first(self):
        with tempfile.TemporaryDirectory() as scratch:
            patch = mock.patch.object(state, "STATE", Path(scratch))
            patch.start()
            self.addCleanup(patch.stop)
            order = []

            def second():
                with state.RepoLock("r") as lock:
                    order.append(("second", lock.waited))

            with state.RepoLock("r") as first:
                worker = threading.Thread(target=second)
                worker.start()
                time.sleep(0.3)
                order.append(("first", first.waited))

            worker.join(5)

            self.assertEqual(order, [("first", False), ("second", True)])


class SnapshotPath(UpstreamCase):
    def test_two_trees_sharing_a_merge_base_map_to_one_file(self):
        other = self.root / "other"
        git_in(self.repo, "worktree", "add", "-q", "-b", "one", str(other))
        git_in(self.repo, "checkout", "-q", "-b", "two")
        commit_file(self.repo, "b.txt")
        commit_file(other, "c.txt")

        first = state.snapshot_path("r", gitops.merge_base(self.repo, "dev"))
        second = state.snapshot_path("r", gitops.merge_base(other, "dev"))

        self.assertEqual(first, second)
        self.assertEqual(first.parent, state.STATE / "r" / "baselines")
        self.assertEqual(first.name, f"{self.fork}.json")


class LegacyState(unittest.TestCase):
    def test_old_files_are_removed_once_on_first_touch(self):
        with tempfile.TemporaryDirectory() as scratch, mock.patch.object(state, "STATE", Path(scratch)):
            store = Path(scratch) / "r"
            store.mkdir()
            for name in ("baseline.json", "last-compare.json"):
                (store / name).write_text("{}")

            state.state_dir("r")
            self.assertFalse((store / "baseline.json").exists())
            self.assertFalse((store / "last-compare.json").exists())

            (store / "last-compare.json").write_text("{}")
            state.state_dir("r")
            self.assertTrue((store / "last-compare.json").exists())


class AtomicWrite(unittest.TestCase):
    def test_write_json_round_trips(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "state.json"
            state.write_json(path, {"a": 1})

            self.assertEqual(state.load_json(path), {"a": 1})
            self.assertEqual([p.name for p in Path(scratch).iterdir()], ["state.json"])
