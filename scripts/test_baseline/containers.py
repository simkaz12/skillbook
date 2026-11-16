import json
import re
import subprocess
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .errors import Fault


CONTAINER_RE = re.compile(r"-w \S+ (\S+)")
HOST_KEY_RE = re.compile(r"(^|_)(HOST|HOSTNAME|URL|ENDPOINT|SERVER|ADDR|ADDRESS)(_|$)|^(REDIS|DB)_")
NON_HOST_KEY_RE = re.compile(
    r"_(CONNECTION|DATABASE|DRIVER|CLIENT|USERNAME|USER|PASSWORD|PORT|PREFIX|SCHEME|NAME|CLUSTER|SOCKET|"
    r"CHARSET|COLLATION|FOREIGN_KEYS|TIMEOUT|SSLMODE|OPTIONS)$"
)
DOTENV_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", re.M)
HOST_FILES = ("phpunit.xml", "phpunit.xml.dist", ".env.testing", ".env")
LABEL_PROJECT = "com.docker.compose.project"
LABEL_DIR = "com.docker.compose.project.working_dir"
LABEL_FILES = "com.docker.compose.project.config_files"
LABEL_SERVICE = "com.docker.compose.service"
UP_TIMEOUT = 180
HEALTH_WAIT = 90
HEALTH_POLL = 2
LOG_TAIL = 5
STARTED = []


def is_docker(section):
    return any("docker exec" in cmd for cmd in section.full + section.focused)


def containers_of(section):
    names = []
    for cmd in section.full:
        found = CONTAINER_RE.search(cmd)
        if found and "docker exec" in cmd and found.group(1) not in names:
            names.append(found.group(1))

    return names


def container_of(section):
    names = containers_of(section)

    return names[0] if names else None


@dataclass
class Compose:
    args: list
    cwd: Path
    service: str = ""


def docker(args, cwd=None, log=None):
    try:
        proc = subprocess.run(["docker", *args], cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        raise Fault("docker is not installed or not on PATH")

    if log:
        with open(log, "a") as handle:
            handle.write(f"\n$ docker {' '.join(args)}\n{proc.stdout}{proc.stderr}")

    return proc


def compose(target, *args, log=None):
    return docker(["compose", *target.args, *args], cwd=target.cwd, log=log)


def require_daemon():
    proc = docker(["info"])
    if proc.returncode != 0:
        detail = (proc.stderr.strip().splitlines() or ["no output"])[-1]
        raise Fault(f"the Docker daemon is not running ({detail}); start it and re-run")


def unsafe_project_dir(workdir):
    path = Path(workdir)

    return ".baseline" in path.parts or (path / ".git").is_file() or not path.is_dir()


def compose_from_labels(labels):
    workdir = labels.get(LABEL_DIR, "")
    files = [f for f in labels.get(LABEL_FILES, "").split(",") if f]
    project = labels.get(LABEL_PROJECT, "")

    if not (workdir and files and project) or unsafe_project_dir(workdir):
        return None

    args = ["-p", project]
    for file in files:
        args += ["-f", file]
    args += ["--project-directory", workdir]

    return Compose(args, Path(workdir), labels.get(LABEL_SERVICE, ""))


def compose_config(target):
    proc = compose(target, "config", "--format", "json")
    if proc.returncode != 0:
        raise Fault(f"docker compose config failed in {target.cwd}: {proc.stderr.strip()[-300:]}")

    return json.loads(proc.stdout)


def service_named(config, container):
    for service, body in config.get("services", {}).items():
        if body.get("container_name") == container:
            return service

    return ""


def resolve_compose(container, main):
    proc = docker(["inspect", container])
    target = None

    if proc.returncode == 0:
        try:
            target = compose_from_labels(json.loads(proc.stdout)[0]["Config"]["Labels"] or {})
        except (ValueError, KeyError, IndexError):
            target = None

    if target is None:
        target = Compose(["--project-directory", str(main)], Path(main))

    config = compose_config(target)
    if target.service not in config.get("services", {}):
        target.service = service_named(config, container)
    if not target.service:
        raise Fault(f"no compose service has container_name {container} in {target.cwd}")

    return target, config


def host_of(value):
    value = value.strip()
    if value[:1] in ("'", '"'):
        value = value[1:].split(value[0])[0]
    else:
        value = value.split(" #")[0].strip()

    if "://" in value:
        return urllib.parse.urlsplit(value).hostname or ""

    return value.split(":")[0].split("/")[0]


def phpunit_pairs(file):
    try:
        root = ET.parse(file).getroot()
    except ET.ParseError:
        return []

    return [(node.get("name", ""), node.get("value", "")) for tag in ("env", "server") for node in root.iter(tag)]


def referenced_hosts(main):
    hosts = set()

    for name in HOST_FILES:
        file = Path(main) / name
        if not file.is_file():
            continue
        if name.startswith("phpunit"):
            pairs = phpunit_pairs(file)
        else:
            pairs = DOTENV_RE.findall(file.read_text(errors="replace"))
        for key, value in pairs:
            if HOST_KEY_RE.search(key) and not NON_HOST_KEY_RE.search(key) and host_of(value):
                hosts.add(host_of(value))

    return hosts


def with_dependencies(config, wanted):
    services = config.get("services", {})
    pending = [name for name in wanted if name in services]
    closure = []

    while pending:
        name = pending.pop(0)
        if name in closure:
            continue
        closure.append(name)
        pending += list(services[name].get("depends_on") or {})

    return closure


def services_needed(config, service, main):
    services = config.get("services", {})
    hosted = sorted(host for host in referenced_hosts(main) if host in services and host != service)

    return with_dependencies(config, [service, *hosted])


def parse_ps(text):
    text = text.strip()
    if not text:
        return {}

    try:
        loaded = json.loads(text)
        rows = loaded if isinstance(loaded, list) else [loaded]
    except ValueError:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]

    return {row.get("Service", ""): row for row in rows}


def service_states(target, services):
    proc = compose(target, "ps", "-a", "--format", "json", *services)

    return parse_ps(proc.stdout) if proc.returncode == 0 else {}


def is_ready(row):
    return bool(row) and row.get("State") == "running" and row.get("Health", "") in ("", "healthy")


def not_ready(states, services):
    return [name for name in services if not is_ready(states.get(name))]


def container_logs(name):
    proc = docker(["logs", "--tail", str(LOG_TAIL), name])
    lines = (proc.stdout + proc.stderr).strip().splitlines()[-LOG_TAIL:]

    return "\n".join(lines) or "(no log output)"


def wait_ready(target, services):
    deadline = time.time() + HEALTH_WAIT
    states = service_states(target, services)

    while not_ready(states, services) and time.time() < deadline:
        time.sleep(HEALTH_POLL)
        states = service_states(target, services)

    return states


def restart_once(target, services, states, log):
    names = [states[name]["Name"] for name in not_ready(states, services) if name in states]
    if names:
        docker(["restart", *names], log=log)

    return wait_ready(target, services)


def fail_not_ready(states, services):
    parts = []
    for name in not_ready(states, services):
        container = (states.get(name) or {}).get("Name") or name
        tail = container_logs(container)
        parts.append(f"container {container} is not running after restart; last {LOG_TAIL} log lines:\n{tail}")

    raise Fault("\n".join(parts))


def bring_up(container, main, log):
    target, config = resolve_compose(container, main)
    services = services_needed(config, target.service, main)
    before = service_states(target, services)

    if not not_ready(before, services):
        return

    compose(target, "up", "-d", "--wait", "--no-recreate", "--wait-timeout", str(UP_TIMEOUT), *services, log=log)
    states = service_states(target, services)

    if not_ready(states, services):
        states = restart_once(target, services, states, log)
    if not_ready(states, services):
        fail_not_ready(states, services)

    for name in not_ready(before, services):
        if states[name]["Name"] not in STARTED:
            STARTED.append(states[name]["Name"])


def ensure_containers(section, main, log):
    names = containers_of(section)
    if not names:
        return

    require_daemon()
    for name in names:
        bring_up(name, main, log)


def containers_line():
    return f"CONTAINERS started {', '.join(STARTED)}" if STARTED else ""


def with_containers(report):
    line = containers_line()
    if not line:
        return report

    head, _, rest = report.partition("\n")

    return f"{head}\n{line}\n{rest}" if rest else f"{head}\n{line}"
