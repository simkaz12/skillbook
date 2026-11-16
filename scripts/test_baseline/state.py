import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from . import spec


STATE = Path(os.environ.get("TEST_BASELINE_HOME", str(Path.home() / ".cache" / "test-baseline")))
LEGACY_STATE = ("baseline.json", "last-compare.json")
RunStatus = Literal["running", "done"]


@dataclass(frozen=True, slots=True)
class RunRecord:
    fingerprint: str
    tree: str
    repo: str
    merge_base: str
    config: str
    started_at: float
    pid: int
    status: RunStatus
    exit: int = 0
    report: str = ""
    finished_at: float = 0.0


@dataclass(frozen=True, slots=True)
class RunKey:
    merge_base: str
    fingerprint: str
    path: Path

    @property
    def id(self):
        return self.fingerprint[:7]


def state_dir(repo):
    path = STATE / repo
    first_touch = not (path / "baselines").exists()

    for sub in ("logs", "baselines", "runs"):
        (path / sub).mkdir(parents=True, exist_ok=True)

    if first_touch:
        for legacy in LEGACY_STATE:
            (path / legacy).unlink(missing_ok=True)

    return path


def last_compare_path(repo):
    return state_dir(repo) / "last-compare.json"


def snapshot_path(repo, sha):
    return state_dir(repo) / "baselines" / f"{sha}.json"


class RepoLock:
    def __init__(self, repo, name="lock"):
        self.path = state_dir(repo) / name
        self.waited = False

    def __enter__(self):
        self.handle = open(self.path, "w")
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.waited = True
            fcntl.flock(self.handle, fcntl.LOCK_EX)

        return self

    def __exit__(self, *exc):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


def write_json(path, data):
    path = Path(path)
    scratch = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    scratch.write_text(json.dumps(data))
    os.replace(scratch, path)


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def matches(snapshot, config):
    return bool(snapshot) and snapshot.get("config") == config


def config_hash(spec, section):
    payload = json.dumps([spec.base, section.full])

    return hashlib.sha256(payload.encode()).hexdigest()
