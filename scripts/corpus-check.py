#!/usr/bin/env python3

import argparse
import fnmatch
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCAN_DIRS = ("skills", "agents", "commands", "hooks")
SKIP_DIRS = ("skills/synced",)
SCAN_ROOT_FILES = ("CONTEXT-LOAD.md",)
TEXT_SUFFIXES = frozenset({".md", ".sh", ".py", ".yaml", ".yml", ".txt"})

CHECKS = ("skill-ref", "retired-tool", "fork-tools", "agent-ref")

RETIRED_TOOLS = frozenset({
    "evidence_browse", "evidence_capture", "evidence_fetch", "evidence_resolve",
    "ledger_compact", "ledger_context", "ledger_feedback", "ledger_recall",
    "ledger_save", "ledger_session_history", "ledger_shift_recall",
    "session_digest",
})

FS_ROOTS = frozenset({
    "bin", "boot", "dev", "etc", "home", "lib", "lib64", "media", "mnt", "opt",
    "proc", "root", "run", "sbin", "srv", "sys", "tmp", "usr", "var",
})

LOCATIVE_WORDS = frozenset({
    "at", "in", "under", "inside", "into", "contains", "containing", "contain",
    "path", "paths", "url", "urls", "route", "routes", "endpoint", "endpoints",
    "mount", "mounted", "serves", "serving", "directory", "dir", "folder",
})

AGENT_NOUNS = frozenset({"agent", "agents", "subagent", "subagents"})

INVOKE_WORDS = frozenset({
    "invoke", "invokes", "invoking", "run", "runs", "use", "uses", "using",
    "via", "through", "per", "trigger", "triggers",
})

INVOKE_STOPWORDS = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "its", "your", "our",
    "their", "each", "every", "same", "whole", "full", "entire", "new",
    "other", "existing", "current", "actual", "usual", "relevant",
})

TRAILING_NONSKILL = frozenset({
    "hook", "hooks", "tool", "tools", "command", "commands", "binary",
    "binaries", "flag", "flags", "option", "options", "event", "events",
    "file", "files", "script", "scripts", "payload", "field", "fields",
    "key", "keys", "directory", "folder", "endpoint", "table", "column",
    "env", "var", "variable", "setting", "settings", "config", "package",
    "server", "profile", "mode", "block",
})

COMMON_BINARIES = frozenset({
    "awk", "bash", "cat", "chmod", "claude", "codex", "composer", "cp", "curl",
    "diff", "docker", "find", "gh", "git", "grep", "head", "jq", "journalctl",
    "ls", "mv", "node", "npm", "npx", "php", "pnpm", "pytest", "python",
    "python3", "rg", "rm", "scp", "sed", "sh", "ssh", "systemctl", "tail",
    "tinker", "wget", "yarn",
})

CORE_TOOLS = frozenset({
    "Agent", "Bash", "BashOutput", "Edit", "Glob", "Grep", "KillShell",
    "NotebookEdit", "Read", "Skill", "Task", "TodoWrite", "WebFetch",
    "WebSearch", "Write",
})

THIRD_PARTY_TOOLS = frozenset({
    "lint-staged",
})

TOOL_ALIASES = {"Task": "Agent"}

NAME = r"[A-Za-z][A-Za-z0-9._-]*"
KEBAB = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+"

RE_BACKTICK = re.compile(r"`([^`\n]+)`")
RE_SKILL_CALL = re.compile(r"Skill\(\s*(?:skill\s*[:=]\s*)?[\"']?(" + NAME + r")")
RE_SKILL_KEY = re.compile(r"[\"']?\bskill[\"']?\s*[:=]\s*[\"']?(" + NAME + r")")
RE_SKILL_WORD = re.compile(r"`(" + NAME + r")`\s+skill\b(?!s)")
RE_SKILL_PATH = re.compile(
    r"(?:~|/home/[^/\s]+)/(?:\.claude|Projects/skillbook)/skills/(" + NAME + r")/"
)
RE_SLASH = re.compile(r"^/(" + NAME + r")$")
RE_PLAIN_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")

RE_SUBAGENT_TYPE = re.compile(r"subagent_type\s*[:=]\s*[\"']?(" + NAME + r")")
RE_DISPATCH = re.compile(
    r"\b(?:dispatch|dispatches|dispatched|dispatching|spawn|spawns|spawned)\s+"
    r"(?:a|an|the)?\s*(?:`(" + NAME + r")`|(" + KEBAB + r"))\b"
)
RE_AGENT_WORD = re.compile(
    r"`(" + NAME + r")`\s+(?:(?:sub)?agents?|explorers?|workers?)\b"
)
RE_AGENT_PATH = re.compile(r"(?<![\w/-])agents/(" + NAME + r")\.md\b")
RE_TABLE_TIER = re.compile(r"^\|\s*\*\*(" + NAME + r")\*\*\s*\|")
RE_CASE_OPEN = re.compile(r"^\s*case\s+\"?\$\{?([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
RE_CASE_ARM = re.compile(r"^\s*([A-Za-z0-9_|*-]+)\)")
RE_CASE_END = re.compile(r"^\s*esac\b")

RE_FM_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$")
RE_MCP_TOOL = re.compile(r"\bmcp__[a-z0-9-]+__[a-z0-9_-]+")
RE_RETIRED_MCP = re.compile(r"\bmcp__pi-memory__([a-z0-9_-]+)")
RE_RETIRED_BARE = re.compile(r"\b(" + "|".join(sorted(RETIRED_TOOLS)) + r")\b")

RE_SKILL_INVOKE = re.compile(
    r"\bSkill\s*\(|`Skill`\s+tool|\bSkill\s+tool\b|Skill-invoke|"
    r"\binvoke\b[^.\n]{0,60}\bskill\b", re.IGNORECASE
)
RE_AGENT_INVOKE = re.compile(r"\bsubagent_type\b|\bAgent\s*\(|`?Agent`?\s+tool\b")
RE_CORE_TOOL_WORD = re.compile(r"`(" + "|".join(sorted(CORE_TOOLS)) + r")`\s+tool\b")


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    line: int
    token: str
    message: str

    def render(self):
        return f"{self.path}:{self.line}: {self.check}: {self.message}"

    def key(self):
        return (CHECKS.index(self.check), self.path, self.line, self.token)


@dataclass
class Waiver:
    check: str
    glob: str
    token: str
    reason: str
    used: bool = field(default=False)

    def matches(self, finding):
        if self.check not in ("*", finding.check):
            return False
        if not fnmatch.fnmatch(finding.path, self.glob):
            return False
        return self.token in ("*", finding.token)


def load_waivers(path):
    waivers = []
    if not path.exists():
        return waivers
    for raw in path.read_text(encoding="utf-8").splitlines():
        split = raw.split("#", 1)
        body = split[0].strip()
        reason = split[1].strip() if len(split) > 1 else ""
        if not body:
            continue
        parts = body.split()
        if len(parts) != 3:
            raise SystemExit(f"{path}: malformed waiver: {raw!r}")
        check, glob, token = parts
        if check not in CHECKS and check != "*":
            raise SystemExit(f"{path}: unknown check {check!r} in {raw!r}")
        if not reason:
            raise SystemExit(f"{path}: waiver needs a '# reason': {raw!r}")
        waivers.append(Waiver(check, glob, token, reason))
    return waivers


def split_frontmatter(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = {}
            key = None
            for entry in lines[1:i]:
                m = RE_FM_KEY.match(entry)
                if m:
                    key = m.group(1)
                    fm[key] = m.group(2).strip()
                elif key and entry.strip():
                    fm[key] = (fm[key] + " " + entry.strip()).strip()
            return fm, "\n".join(lines[i + 1:])
    return {}, text


def collect_files(root, subset):
    files = []
    for name in SCAN_ROOT_FILES:
        p = root / name
        if p.is_file():
            files.append(p)
    for d in SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            rel_dir = p.relative_to(root).as_posix()
            if any(rel_dir == s or rel_dir.startswith(s + "/") for s in SKIP_DIRS):
                continue
            if p.is_file() and p.suffix in TEXT_SUFFIXES:
                files.append(p)
    out = []
    for p in sorted(set(files)):
        rel = p.relative_to(root).as_posix()
        if subset is not None and rel not in subset:
            continue
        try:
            out.append((rel, p.read_text(encoding="utf-8")))
        except (UnicodeDecodeError, OSError) as exc:
            raise SystemExit(f"corpus-check: cannot read {rel}: {exc}")
    return out


def build_registries(root):
    skills = set()
    base = root / "skills"
    if base.is_dir():
        skills = {d.name for d in base.iterdir() if (d / "SKILL.md").is_file()}
    commands = set()
    base = root / "commands"
    if base.is_dir():
        commands = {p.stem for p in base.glob("*.md")}
    agents = set()
    base = root / "agents"
    if base.is_dir():
        agents = {p.stem for p in base.glob("*.md")}
    return skills, commands, agents


def skill_candidates(line, excluded):
    seen = []
    for rx in (RE_SKILL_CALL, RE_SKILL_KEY, RE_SKILL_WORD, RE_SKILL_PATH):
        for m in rx.finditer(line):
            seen.append(m.group(1))
    for m in RE_BACKTICK.finditer(line):
        span = m.group(1).strip()
        before = re.findall(r"[A-Za-z']+", line[:m.start()])
        slash = RE_SLASH.match(span)
        if slash:
            prev = before[-1].lower() if before else ""
            if slash.group(1) not in FS_ROOTS and prev not in LOCATIVE_WORDS:
                seen.append(slash.group(1))
        elif invoke_cued(before) and RE_PLAIN_NAME.match(span) \
                and span.lower() not in COMMON_BINARIES and span not in excluded:
            after = re.findall(r"[A-Za-z']+", line[m.end():m.end() + 24])
            if after and after[0].lower() in TRAILING_NONSKILL:
                continue
            seen.append(span)
    return list(dict.fromkeys(seen))


def invoke_cued(before):
    for word in reversed(before[-4:]):
        low = word.lower()
        if low in INVOKE_STOPWORDS:
            continue
        return low in INVOKE_WORDS
    return False


def agent_candidates(rel, lines):
    found = []
    for n, line in enumerate(lines, 1):
        for m in RE_SUBAGENT_TYPE.finditer(line):
            found.append((n, m.group(1), "subagent_type"))
        for m in RE_DISPATCH.finditer(line):
            token = m.group(1)
            if not token:
                bare = m.group(2)
                if AGENT_NOUNS & set(bare.split("-")):
                    continue
                token = bare
            found.append((n, token, "a dispatch phrase"))
        for m in RE_AGENT_WORD.finditer(line):
            found.append((n, m.group(1), "an agent phrase"))
        for m in RE_AGENT_PATH.finditer(line):
            found.append((n, m.group(1), "an agents/ path"))
    found.extend(tier_table_candidates(lines))
    if rel.endswith(".sh"):
        found.extend(case_router_candidates(lines))
    seen = {}
    for n, token, source in found:
        seen.setdefault((n, token), source)
    return [(n, token, source) for (n, token), source in seen.items()]


def tier_table_candidates(lines):
    found = []
    active = False
    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            active = False
            continue
        cells = [c.strip().lower() for c in stripped.strip("|").split("|")]
        if cells and cells[0] in ("tier", "agent"):
            active = True
            continue
        if active:
            m = RE_TABLE_TIER.match(stripped)
            if m:
                found.append((n, m.group(1), "the delegation table"))
    return found


def case_router_candidates(lines):
    found = []
    in_case = False
    for n, line in enumerate(lines, 1):
        if in_case:
            if RE_CASE_END.match(line):
                in_case = False
                continue
            m = RE_CASE_ARM.match(line)
            if m:
                for tok in m.group(1).split("|"):
                    if tok and tok != "*":
                        found.append((n, tok, "an agent_type router"))
            continue
        m = RE_CASE_OPEN.match(line)
        if m and "agent" in m.group(1).lower():
            in_case = True
    return found


def check_skill_refs(rel, lines, invocable, excluded):
    out = []
    for n, line in enumerate(lines, 1):
        for token in skill_candidates(line, excluded):
            if token in invocable:
                continue
            out.append(Finding(
                "skill-ref", rel, n, token,
                f"references skill `{token}` — no skills/{token}/SKILL.md "
                f"and no commands/{token}.md",
            ))
    return out


def check_retired_tools(rel, lines):
    out = []
    for n, line in enumerate(lines, 1):
        for m in RE_RETIRED_MCP.finditer(line):
            out.append(Finding(
                "retired-tool", rel, n, m.group(1),
                f"calls retired pi-memory tool mcp__pi-memory__{m.group(1)} "
                f"— resolves at runtime, writes into the frozen archive",
            ))
        for m in RE_RETIRED_BARE.finditer(line):
            if f"mcp__pi-memory__{m.group(1)}" in line:
                continue
            out.append(Finding(
                "retired-tool", rel, n, m.group(1),
                f"names retired pi-memory tool {m.group(1)} "
                f"— resolves at runtime, writes into the frozen archive",
            ))
    return out


def parse_tools(value):
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    raw = raw.strip("[]")
    tools = set()
    for part in re.split(r"[,\s]+", raw):
        part = part.strip("\"'- ")
        if part:
            tools.add(TOOL_ALIASES.get(part, part))
    return tools or None


def required_tools(fm, body):
    req = set()
    if RE_SKILL_INVOKE.search(body):
        req.add("Skill")
    if RE_AGENT_INVOKE.search(body):
        req.add("Agent")
    for m in RE_CORE_TOOL_WORD.finditer(body):
        req.add(TOOL_ALIASES.get(m.group(1), m.group(1)))
    for m in RE_MCP_TOOL.finditer(body):
        req.add(m.group(0))
    declared = parse_tools(fm.get("allowed-tools"))
    if declared:
        req |= declared
    return req


def check_fork_tools(root, rel, text, agents):
    fm, body = split_frontmatter(text)
    target = fm.get("agent", "").strip().strip("\"'")
    if not target:
        return []
    line = 1
    for n, entry in enumerate(text.split("\n"), 1):
        if entry.startswith("agent:"):
            line = n
            break
    if target not in agents:
        return [Finding(
            "fork-tools", rel, line, target,
            f"forks into agent `{target}` — no agents/{target}.md",
        )]
    afm, _ = split_frontmatter(
        (root / "agents" / f"{target}.md").read_text(encoding="utf-8")
    )
    allowed = parse_tools(afm.get("tools"))
    if allowed is None:
        return []
    missing = sorted(required_tools(fm, body) - allowed)
    if not missing:
        return []
    return [Finding(
        "fork-tools", rel, line, target,
        f"forks into `{target}` but its tools: allowlist is missing "
        f"{', '.join(missing)} — a hard allowlist, so the fork cannot load it",
    )]


def check_agent_refs(rel, lines, agents):
    out = []
    for n, token, source in agent_candidates(rel, lines):
        if token in agents:
            continue
        out.append(Finding(
            "agent-ref", rel, n, token,
            f"names agent `{token}` in {source} — no agents/{token}.md",
        ))
    return out


def staged_paths(root):
    proc = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only",
         "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    )
    return {p for p in proc.stdout.split("\n") if p}


def run(root, subset, waivers):
    skills, commands, agents = build_registries(root)
    invocable = skills | commands
    excluded = agents | CORE_TOOLS | THIRD_PARTY_TOOLS
    files = collect_files(root, subset)
    findings = []
    for rel, text in files:
        lines = text.split("\n")
        findings.extend(check_skill_refs(rel, lines, invocable, excluded))
        findings.extend(check_retired_tools(rel, lines))
        findings.extend(check_agent_refs(rel, lines, agents))
        if rel.startswith("skills/") and rel.endswith("SKILL.md"):
            findings.extend(check_fork_tools(root, rel, text, agents))
    kept = []
    for f in findings:
        waiver = next((w for w in waivers if w.matches(f)), None)
        if waiver:
            waiver.used = True
            continue
        kept.append(f)
    kept.sort(key=Finding.key)
    return kept, len(files), skills, commands, agents


def self_test(root):
    fixture = root / "scripts" / "fixtures" / "corpus"
    expected_file = root / "scripts" / "fixtures" / "expected.txt"
    if not fixture.is_dir():
        print(f"corpus-check: no fixture at {fixture}", file=sys.stderr)
        return 2
    actual = [f.render() for f in run(fixture, None, [])[0]]
    expected = [
        e for e in expected_file.read_text(encoding="utf-8").split("\n") if e.strip()
    ]
    if actual == expected:
        print(f"corpus-check self-test: {len(actual)} expected findings, all matched")
        return 0
    for line in expected:
        if line not in actual:
            print(f"self-test MISSING: {line}")
    for line in actual:
        if line not in expected:
            print(f"self-test UNEXPECTED: {line}")
    return 1


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def main():
    ap = argparse.ArgumentParser(
        description="Referential-integrity checker for the skill/agent corpus. "
                    "Scans skills/, agents/, commands/, hooks/ and "
                    "CONTEXT-LOAD.md for dangling skill references, retired "
                    "pi-memory tool calls, fork/allowlist mismatches and dangling "
                    "agent references. Exit 1 with findings, 0 with a count "
                    "summary. Waivers: scripts/corpus-check-waivers.txt.",
    )
    ap.add_argument("--root", default=None,
                    help="corpus root to scan (default: the repo this script sits in)")
    ap.add_argument("--staged", action="store_true",
                    help="report only files staged for commit; the corpus is still "
                         "read from the working tree")
    ap.add_argument("--self-test", action="store_true",
                    help="run every check against scripts/fixtures/corpus and diff "
                         "against scripts/fixtures/expected.txt")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root \
        else Path(__file__).resolve().parents[1]

    if args.self_test:
        return self_test(root)

    waivers = load_waivers(root / "scripts" / "corpus-check-waivers.txt")
    subset = staged_paths(root) if args.staged else None
    findings, n_files, skills, commands, agents = run(root, subset, waivers)

    if findings:
        for f in findings:
            print(f.render())
        return 1

    stale = [w for w in waivers if not w.used]
    summary = (
        f"corpus-check: {n_files} files, {len(skills)} skills, "
        f"{len(commands)} commands, {len(agents)} agents, 0 findings"
    )
    if stale:
        summary += f", {plural(len(stale), 'unused waiver')}"
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
