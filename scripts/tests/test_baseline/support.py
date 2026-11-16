import contextlib
import io
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from test_baseline import gitops, runs, spec, state


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

SAMPLE = """base: dev

[crm-api]
focused: docker exec -w /var/www/html/{dir} crm_web php artisan test <paths>
full: docker exec -w /var/www/html/{dir} crm_web php artisan test --log-junit .test-results/phpunit.xml

[crm-web]
focused: npx vitest run <paths>
full: npx vitest run --reporter=junit --outputFile=.test-results/vitest.xml
full: npm run build
"""


def git_in(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit_file(path, name, text="x"):
    (Path(path) / name).parent.mkdir(parents=True, exist_ok=True)
    (Path(path) / name).write_text(text)
    git_in(path, "add", name)
    git_in(path, "commit", "-q", "-m", name)

    return git_in(path, "rev-parse", "HEAD")


class UpstreamCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name).resolve()
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        git_in(self.upstream, "init", "-q", "-b", "dev")
        self.fork = commit_file(self.upstream, "a.txt")
        git_in(self.root, "clone", "-q", str(self.upstream), str(self.root / "crm-api"))
        self.repo = self.root / "crm-api"
        for patch in (
            mock.patch.object(gitops, "FETCHED", set()),
            mock.patch.object(state, "STATE", self.root / "state"),
        ):
            patch.start()
            self.addCleanup(patch.stop)


REAL_POPEN = subprocess.Popen


class FakePopen:
    pid = 4242
    calls = []

    def __new__(cls, argv, **kwargs):
        if argv[0] != sys.executable:
            return REAL_POPEN(argv, **kwargs)

        cls.calls.append((argv, kwargs))

        return super().__new__(cls)

    def __init__(self, argv, **kwargs):
        pass


class RunCase(UpstreamCase):
    def setUp(self):
        super().setUp()
        FakePopen.calls = []
        specs = {"crm": spec.parse_testing(SAMPLE)}
        self.alive = True
        self.killpg = mock.Mock(side_effect=ProcessLookupError)
        for patch in (
            mock.patch.object(spec, "PROJECTS", self.root),
            mock.patch.object(spec, "load_specs", return_value=specs),
            mock.patch.object(spec, "project_keys", return_value=[]),
            mock.patch.object(runs.subprocess, "Popen", FakePopen),
            mock.patch.object(runs, "pid_alive", lambda pid: self.alive and pid > 0),
            mock.patch.object(runs.os, "killpg", self.killpg),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def invoke(self, func, tree=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = func(str(tree or self.repo))

        return code, out.getvalue()

    def key(self):
        target = spec.resolve_target(self.repo)

        return runs.run_key(target, gitops.merge_base(target.top, target.spec.base))

    def write_run(self, key, **fields):
        base = {
            "fingerprint": key.fingerprint,
            "tree": str(self.repo),
            "repo": "crm-api",
            "merge_base": key.merge_base,
            "config": "c",
            "started_at": time.time() - 120,
            "pid": 4242,
            "status": "running",
        }
        runs.save_run(key.path, state.RunRecord(**{**base, **fields}))

    def finish_on_sleep(self, key, after=1, **fields):
        seen = []

        def fake_sleep(_):
            seen.append(1)
            if len(seen) >= after:
                self.write_run(key, status="done", exit=1, report="REPORT\nRESULT new-failures", **fields)

        return mock.patch.object(runs.time, "sleep", fake_sleep)
