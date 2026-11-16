import os
import signal
import subprocess
from pathlib import Path
from unittest import mock

from test_baseline import SCRIPTS, runs, state
from .support import FakePopen, RunCase


class Start(RunCase):
    def test_writes_the_record_spawns_detached_and_prints_the_id(self):
        key = self.key()

        code, out = self.invoke(runs.start)

        record = runs.load_run(key.path)
        argv, kwargs = FakePopen.calls[0]
        self.assertEqual(code, 0)
        self.assertEqual(out, f"started run {key.id}  crm-api  merge-base {key.merge_base[:7]}\n")
        self.assertEqual((record.status, record.pid, record.merge_base), ("running", 4242, key.merge_base))
        self.assertEqual(
            argv[1:],
            [str(SCRIPTS / "test-baseline.py"), "compare", str(self.repo), "--record", str(key.path)],
        )
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(len(key.id), 7)
        self.killpg.assert_not_called()

    def test_second_call_reports_the_run_already_running(self):
        self.invoke(runs.start)

        code, out = self.invoke(runs.start)

        self.assertEqual((code, out), (0, f"run {self.key().id} already running\n"))
        self.assertEqual(len(FakePopen.calls), 1)
        self.killpg.assert_not_called()

    def test_dead_pid_starts_anew(self):
        self.invoke(runs.start)
        self.alive = False

        _, out = self.invoke(runs.start)

        self.assertTrue(out.startswith("started run"))
        self.assertEqual(len(FakePopen.calls), 2)

    def test_dead_pid_signals_the_old_group_before_launching(self):
        self.write_run(self.key(), pid=4242)
        self.alive = False
        order = []

        def gone_group(pid, sig):
            order.append(("killpg", pid, sig))
            raise ProcessLookupError

        self.killpg.side_effect = gone_group
        launch = runs.launch

        def recording_launch(target, run):
            order.append(("launch",))
            launch(target, run)

        with mock.patch.object(runs, "launch", recording_launch):
            self.invoke(runs.start)

        self.assertEqual(order, [("killpg", 4242, signal.SIGTERM), ("launch",)])

    def test_finished_run_is_not_restarted(self):
        key = self.key()
        self.write_run(key, status="done", exit=0, report="R")

        code, out = self.invoke(runs.start)

        self.assertEqual((code, out), (0, f"run {key.id} already finished; use wait\n"))
        self.assertEqual(FakePopen.calls, [])
        self.killpg.assert_not_called()

    def test_blocking_run_is_not_restarted(self):
        key = self.key()
        self.write_run(key, status="done", exit=1, report="R")

        _, out = self.invoke(runs.start)

        self.assertEqual(out, f"run {key.id} already finished; use wait\n")
        self.assertEqual(FakePopen.calls, [])
        self.killpg.assert_not_called()

    def test_failed_run_starts_again(self):
        key = self.key()
        self.write_run(key, status="done", exit=2, report="ERROR cargo busy")

        code, out = self.invoke(runs.start)

        self.assertEqual(code, 0)
        self.assertEqual(
            out,
            f"run {key.id} failed last time (ERROR cargo busy); starting again\n"
            f"started run {key.id}  crm-api  merge-base {key.merge_base[:7]}\n",
        )
        self.assertEqual(len(FakePopen.calls), 1)
        self.assertEqual(runs.load_run(key.path).status, "running")
        self.killpg.assert_not_called()

    def rerun(self):
        return self.invoke(lambda tree: runs.start(tree, True))

    def test_rerun_launches_over_a_finished_run_and_drops_the_last_compare(self):
        key = self.key()
        self.write_run(key, status="done", exit=0, report="R")
        state.write_json(state.last_compare_path("crm-api"), {"fingerprint": key.fingerprint})

        code, out = self.rerun()

        self.assertEqual(code, 0)
        self.assertEqual(out, f"started run {key.id}  crm-api  merge-base {key.merge_base[:7]}\n")
        self.assertEqual(len(FakePopen.calls), 1)
        self.assertEqual(runs.load_run(key.path).status, "running")
        self.assertFalse(state.last_compare_path("crm-api").exists())

    def test_rerun_launches_over_a_failed_run(self):
        key = self.key()
        self.write_run(key, status="done", exit=2, report="ERROR cargo busy")

        code, _ = self.rerun()

        self.assertEqual(code, 0)
        self.assertEqual(len(FakePopen.calls), 1)

    def test_rerun_leaves_a_live_run_alone(self):
        key = self.key()
        self.write_run(key)
        state.write_json(state.last_compare_path("crm-api"), {"fingerprint": key.fingerprint})

        code, out = self.rerun()

        self.assertEqual((code, out), (0, f"run {key.id} already running\n"))
        self.assertEqual(FakePopen.calls, [])
        self.assertTrue(state.last_compare_path("crm-api").exists())


class Wait(RunCase):
    def test_finished_run_prints_the_report_and_returns_its_exit(self):
        self.write_run(self.key(), status="done", exit=1, report="REPORT\nRESULT new-failures")

        code, out = self.invoke(runs.wait)

        self.assertEqual((code, out), (1, "REPORT\nRESULT new-failures\n"))
        self.assertEqual(FakePopen.calls, [])

    def test_running_run_is_polled_until_done(self):
        key = self.key()
        self.write_run(key)

        with self.finish_on_sleep(key, after=2):
            code, out = self.invoke(runs.wait)

        self.assertEqual(code, 1)
        self.assertTrue(out.startswith(f"waiting for run {key.id} (started 2m ago)\n"))
        self.assertTrue(out.endswith("RESULT new-failures\n"))
        self.assertEqual(FakePopen.calls, [])

    def test_changed_tree_starts_a_new_run(self):
        old = self.key()
        self.write_run(old, status="done", exit=0, report="OLD")
        (self.repo / "new.txt").write_text("changed")
        new = self.key()

        with self.finish_on_sleep(new):
            code, out = self.invoke(runs.wait)

        self.assertNotEqual(old.id, new.id)
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith(f"tree changed since run {old.id}; starting a new run\n"))
        self.assertEqual(len(FakePopen.calls), 1)

    def test_missing_record_starts_a_run(self):
        key = self.key()

        with self.finish_on_sleep(key):
            _, out = self.invoke(runs.wait)

        self.assertTrue(out.startswith("no run for this tree; starting one\n"))

    def test_dead_pid_starts_a_new_run_and_says_so(self):
        key = self.key()
        self.write_run(key)
        self.alive = False

        with self.finish_on_sleep(key):
            _, out = self.invoke(runs.wait)

        self.assertTrue(out.startswith(f"run {key.id} is not running (process gone); starting a new run\n"))
        self.assertEqual(len(FakePopen.calls), 1)

    def test_run_that_dies_while_awaited_is_restarted_and_the_replacement_is_returned(self):
        key = self.key()
        self.write_run(key)
        sleeps = []

        def fake_sleep(_):
            sleeps.append(1)
            if len(sleeps) == 1:
                self.alive = False
            else:
                self.alive = True
                self.write_run(key, status="done", exit=1, report="REPLACEMENT\nRESULT new-failures")

        with mock.patch.object(runs.time, "sleep", fake_sleep):
            code, out = self.invoke(runs.wait)

        self.assertEqual(code, 1)
        self.assertIn(f"run {key.id} is not running (process gone); starting a new run\n", out)
        self.assertTrue(out.endswith("REPLACEMENT\nRESULT new-failures\n"))
        self.assertEqual(len(FakePopen.calls), 1)

    def test_restart_signals_the_old_group_before_launching(self):
        key = self.key()
        self.write_run(key, pid=4242)
        self.alive = False
        order = []

        def gone_group(pid, sig):
            order.append(("killpg", pid, sig))
            raise ProcessLookupError

        self.killpg.side_effect = gone_group
        launch = runs.launch

        def recording_launch(target, run):
            order.append(("launch",))
            launch(target, run)

        with (
            self.finish_on_sleep(key),
            mock.patch.object(runs, "launch", recording_launch),
        ):
            self.invoke(runs.wait)

        self.assertEqual(order, [("killpg", 4242, signal.SIGTERM), ("launch",)])

    def test_restart_waits_for_the_group_to_empty_then_kills_what_is_left(self):
        key = self.key()
        self.write_run(key, pid=4242)
        self.alive = False
        self.killpg.side_effect = None
        clock = iter([0.0, 1.0, 6.0])

        with (
            self.finish_on_sleep(key),
            mock.patch.object(runs.time, "monotonic", lambda: next(clock)),
        ):
            self.invoke(runs.wait)

        sent = [call.args for call in self.killpg.call_args_list]
        self.assertEqual(
            sent,
            [(4242, signal.SIGTERM), (4242, 0), (4242, signal.SIGKILL)],
        )
        self.assertEqual(len(FakePopen.calls), 1)

    def test_restart_never_signals_pid_zero_or_its_own_group(self):
        key = self.key()
        self.alive = False

        for pid in (0, os.getpgid(0)):
            self.write_run(key, pid=pid)
            with self.finish_on_sleep(key):
                self.invoke(runs.wait)

        self.killpg.assert_not_called()
        self.assertEqual(len(FakePopen.calls), 2)

    def test_a_live_healthy_run_is_never_signalled(self):
        key = self.key()
        self.write_run(key)

        with self.finish_on_sleep(key):
            self.invoke(runs.wait)

        self.killpg.assert_not_called()
        self.assertEqual(FakePopen.calls, [])

    def test_failed_run_is_discarded_and_the_replacement_exit_is_returned(self):
        key = self.key()
        self.write_run(key, status="done", exit=2, report="ERROR docker is down\nmore")

        with self.finish_on_sleep(key):
            code, out = self.invoke(runs.wait)

        self.assertEqual(code, 1)
        self.assertTrue(out.startswith(f"run {key.id} failed last time (ERROR docker is down); starting again\n"))
        self.assertTrue(out.endswith("REPORT\nRESULT new-failures\n"))
        self.assertEqual(len(FakePopen.calls), 1)
        self.killpg.assert_not_called()

    def test_clean_and_blocking_records_stay_cached(self):
        key = self.key()

        for exit_code in (0, 1):
            self.write_run(key, status="done", exit=exit_code, report="CACHED")
            code, out = self.invoke(runs.wait)
            self.assertEqual((code, out), (exit_code, "CACHED\n"))

        self.assertEqual(FakePopen.calls, [])


class Status(RunCase):
    def test_no_run_and_no_snapshot(self):
        key = self.key()

        code, out = self.invoke(runs.status)

        self.assertEqual((code, out), (0, f"crm-api  merge-base {key.merge_base[:7]}  snapshot missing  run none\n"))

    def test_running_run_with_a_snapshot(self):
        key = self.key()
        self.write_run(key)
        path = state.snapshot_path("crm-api", key.merge_base)
        path.write_text("{}")

        _, out = self.invoke(runs.status)

        self.assertEqual(out, f"crm-api  merge-base {key.merge_base[:7]}  snapshot present  run {key.id} running 2m\n")

    def test_done_run(self):
        key = self.key()
        self.write_run(key, status="done", exit=1, report="R")

        _, out = self.invoke(runs.status)

        self.assertTrue(out.endswith(f"run {key.id} done exit 1\n"))
        self.assertEqual(FakePopen.calls, [])
