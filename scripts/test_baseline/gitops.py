import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import containers, state
from .errors import Fault


PREFIX_RE = re.compile(r"^(mise exec \S+ --) ")
COPIED_DEPENDENCIES = ("vendor",)
FETCHED = set()
RUN_EXCLUDES = ("docs/verification", "docs/specs", "docs/qa", ".claude")


def git(path, *args, env=None, check=True):
    proc = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if check and proc.returncode != 0:
        raise Fault(f"git {' '.join(args)} failed in {path}: {proc.stderr.strip()}")

    return proc.stdout.strip()


def main_checkout(path):
    common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")

    return Path(common).parent


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}


def cargo_running():
    for name in ("cargo", "rustc"):
        if subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0:
            return True

    return False


def ensure_excludes(main):
    common = Path(git(main, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    exclude = common / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    current = exclude.read_text().splitlines() if exclude.exists() else []
    missing = [line for line in (".baseline/", ".test-results/") if line not in current]

    if missing:
        with exclude.open("a") as handle:
            handle.write("\n".join(missing) + "\n")


def link_or_install(main, tree, name, lockfile, install_cmd, env, log):
    if not (main / lockfile).exists():
        return

    target = tree / name
    source = main / name
    tree_lock = tree / lockfile
    same = tree_lock.exists() and (main / lockfile).read_bytes() == tree_lock.read_bytes()

    if target.is_symlink():
        target.unlink()

    if source.exists() and same:
        link_dependencies(source, target, name in COPIED_DEPENDENCIES)
        return

    run_setup(install_cmd, tree, env, log)


def link_dependencies(source, target, copy):
    if target.is_symlink():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)

    if copy:
        proc = subprocess.run(["cp", "-a", "--reflink=auto", str(source), str(target)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise Fault(f"copying {source} failed: {proc.stderr.strip()}")
        return

    target.symlink_to(os.path.relpath(source, target.parent))


def make_laravel_dirs(tree):
    if not (tree / "artisan").exists():
        return

    for sub in (
        "framework/cache/data",
        "framework/sessions",
        "framework/views",
        "framework/testing",
        "logs",
        "app/public",
    ):
        (tree / "storage" / sub).mkdir(parents=True, exist_ok=True)

    (tree / "bootstrap" / "cache").mkdir(parents=True, exist_ok=True)


def has_postinstall(tree):
    package = state.load_json(tree / "package.json") or {}

    return "postinstall" in package.get("scripts", {})


def run_logged(cmd, cwd, env, log):
    with open(log, "ab") as handle:
        handle.write(f"\n$ {cmd}\n".encode())
        proc = subprocess.run(["bash", "-c", cmd], cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT)

    return proc.returncode


def fetch_base(path, base):
    key = (str(main_checkout(path)), base)
    if key in FETCHED:
        return

    git(path, "fetch", "origin", base)
    FETCHED.add(key)


def local_merge_base(tree, base):
    sha = git(tree, "merge-base", "HEAD", f"origin/{base}", check=False)
    if not sha:
        raise Fault(f"{tree}: cannot compute merge-base with origin/{base}")

    return sha


def merge_base(tree, base):
    fetch_base(tree, base)

    return local_merge_base(tree, base)


def prepare_tree(section, main, tree, log, commit):
    if (tree / ".git").exists():
        git(tree, "checkout", "--detach", "--force", commit)
    else:
        tree.parent.mkdir(parents=True, exist_ok=True)
        git(main, "worktree", "add", "--detach", str(tree), commit)

    tracked = set(git(tree, "ls-files").splitlines())
    for env_file in main.glob(".env*"):
        if env_file.is_file() and env_file.name not in tracked:
            shutil.copy2(env_file, tree / env_file.name)

    env = clean_env()
    prefix = ""
    for cmd in section.full:
        found = PREFIX_RE.match(cmd)
        if found:
            prefix = found.group(1) + " "

    container = containers.container_of(section)
    rel = os.path.relpath(tree, main)
    composer = (
        f'docker exec -u "$(id -u):$(id -g)" -w /var/www/html/{rel} {container} composer install --no-interaction'
        if container
        else "composer install --no-interaction"
    )
    make_laravel_dirs(tree)
    link_or_install(main, tree, "vendor", "composer.lock", composer, env, log)
    npm = "npm ci"
    if prefix:
        npm = (
            f"{prefix}npx --yes npm@11.6.2 ci --ignore-scripts"
            f" || {prefix}npx --yes npm@11.6.2 install --ignore-scripts"
        )
    link_or_install(main, tree, "node_modules", "package-lock.json", npm, env, log)

    if (main / "uv.lock").exists():
        run_setup(f"{prefix}uv sync", tree, env, log)

    if has_postinstall(tree):
        run_setup(f"{prefix}npm run postinstall", tree, env, log)


def run_setup(cmd, cwd, env, log):
    rc = run_logged(cmd, cwd, env, log)
    if rc != 0:
        raise Fault(f"setup command failed (exit {rc}): {cmd[:80]} (log {log})")


def fingerprint(tree, identity, excluded=()):
    pathspec = [".", *(f":!{path}" for path in excluded)]

    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(scratch, "index")}
        git(tree, "read-tree", "HEAD", env=env, check=False)
        git(tree, "add", "-A", "--", *pathspec, env=env)
        written = git(tree, "write-tree", env=env)

    digest = hashlib.sha256()
    for env_file in sorted(Path(tree).glob(".env*")):
        if env_file.is_file():
            digest.update(env_file.name.encode() + env_file.read_bytes())

    return hashlib.sha256(f"{written}\n{digest.hexdigest()}\n{identity}".encode()).hexdigest()


def run_fingerprint(tree, identity):
    return fingerprint(tree, identity, RUN_EXCLUDES)


def tree_key(target, sha):
    return run_fingerprint(target.top, f"{sha}@{state.config_hash(target.spec, target.section)}")
