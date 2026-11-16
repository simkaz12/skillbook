import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import containers, gitops
from .errors import Fault


SKILLBOOK = Path(__file__).resolve().parents[2]
PROJECTS = Path(os.environ.get("PROJECTS_ROOT", str(Path.home() / "Projects")))


@dataclass
class Section:
    focused: list = field(default_factory=list)
    full: list = field(default_factory=list)


@dataclass
class Spec:
    base: str = ""
    repos: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Target:
    top: Path
    main: Path
    repo: str
    rel: str
    spec: Spec
    section: Section


def parse_testing(text):
    spec = Spec()
    section = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        header = re.fullmatch(r"\[([^\]]+)\]", line)
        if header:
            section = spec.repos.setdefault(header.group(1), Section())
            continue

        key, _, value = line.partition(":")
        value = value.strip()
        if key == "base" and section is None:
            spec.base = value
        elif key == "focused" and section is not None:
            section.focused.append(value)
        elif key == "full" and section is not None:
            section.full.append(value)

    return spec


def project_keys(main):
    script = f'source "{SKILLBOOK}/hooks/scope-map.sh" && project_keys "{main}"'
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    return [key for key in proc.stdout.split() if key]


def load_specs():
    specs = {}
    for file in sorted((SKILLBOOK / "agent-projects").glob("*/testing.md")):
        specs[file.parent.name] = parse_testing(file.read_text())

    return specs


def lookup(repo):
    specs = load_specs()
    keys = project_keys(PROJECTS / repo)

    for key in keys + [k for k in specs if k not in keys]:
        spec = specs.get(key)
        if spec and repo in spec.repos:
            return spec, full_section(spec.repos[repo], repo)

    raise Fault(f"no testing.md section for repo {repo}")


def full_section(section, repo):
    if not section.full:
        raise Fault(f"no full suite configured for repo {repo}")

    return section


def is_cargo(repo):
    return (PROJECTS / repo / "Cargo.toml").exists()


def cwd_repo(cwd=None):
    cwd = Path(cwd or os.getcwd())
    hint = "name repos explicitly: baseline <repo>..."
    probe = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise Fault(f"{cwd} is not inside a git repo; {hint}")

    main = gitops.main_checkout(cwd).resolve()
    if main.parent != PROJECTS.resolve():
        raise Fault(f"{main} is not a repo directly under {PROJECTS}; {hint}")

    if not any(main.name in spec.repos for spec in load_specs().values()):
        raise Fault(f"{main.name} has no [repo] section in any testing.md; {hint}")

    return main.name


def resolve_target(tree_arg):
    top = Path(gitops.git(tree_arg, "rev-parse", "--show-toplevel"))
    main = gitops.main_checkout(top)
    spec, section = lookup(main.name)
    rel = os.path.relpath(top, main)

    if containers.is_docker(section) and rel.startswith(".."):
        raise Fault(f"{top} is outside the container mount {main}; cannot compare")

    return Target(top, main, main.name, rel, spec, section)
