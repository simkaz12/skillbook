#!/usr/bin/env python3

import argparse
import base64
import fnmatch
import importlib.util
import json
import posixpath
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

TEXT_SUFFIXES = (".md", ".sh", ".py", ".json", ".yaml", ".yml", ".txt")
EXPECTED_COUNTS = {"skills": 25, "agents": 5, "commands": 3}
DOCUMENTS = ("GLOBAL-CORE.md", "GLOBAL-CLAUDE.md", "LANGUAGE.md")
SKIPPED_DIRS = ("tests", "fixtures", "__pycache__", "synced")
ENTRY_KINDS = ("skill", "agent", "command", "hook", "script", "document")
UNCATEGORIZED = "Other"

RE_CODE_OR_LINK = re.compile(r"\[[^\]]*\]\([^)\s]*\)|`[^`\n]+`")
RE_MD_LINK = re.compile(r"^\[([^\]]*)\]\(([^)\s]*)\)$")
RE_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
RE_BARE_PATH = re.compile(r"(?:~|\$HOME)/\.claude/[A-Za-z0-9_./-]*[A-Za-z0-9_]")
RE_BARE_SLASH = re.compile(r"(?<![\w/~.$:-])/([a-z][a-z0-9-]*)(?![\w/-]|\.\w)")
RE_CLAUDE_PREFIX = re.compile(r"^(?:~|\$HOME)/\.claude/")
RE_TIER_CELL = re.compile(r"^(\|\s*)\*\*([A-Za-z][A-Za-z0-9._-]*)\*\*")
RE_SOURCE_PATH = re.compile(
    r"\b(?:hooks|scripts|skills|agents|commands)/[A-Za-z0-9_./-]*[A-Za-z0-9_]"
)
RE_HERE_PATH = re.compile(r"\$\{?(?:HERE|SCRIPT_DIR)\}?/([A-Za-z0-9_./-]*[A-Za-z0-9_])")
RE_HOME_CLAUDE = re.compile(r"\$HOME/\.claude/([A-Za-z0-9_./-]*[A-Za-z0-9_])")
RE_CATEGORY = re.compile(r"^##\s+(.+?)\s*$")
RE_CATEGORY_ITEM = re.compile(r"^-\s+\*\*/?([A-Za-z0-9-]+)\*\*")
RE_TITLE_HEADING = re.compile(r"\A\s*# [^\n]*\n+")
RE_HREF = re.compile(r"\]\(#/([^)\s]*)\)")


class BuildError(Exception):
    pass


class RedactionLeak(BuildError):
    pass


def load_corpus_check():
    path = HERE / "corpus-check.py"
    spec = importlib.util.spec_from_file_location("corpus_check", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["corpus_check"] = module
    spec.loader.exec_module(module)
    return module


def is_excluded(rel):
    parts = rel.split("/")
    if any(part in SKIPPED_DIRS for part in parts):
        return True

    name = parts[-1]
    if fnmatch.fnmatch(name, "test*.sh") or fnmatch.fnmatch(name, "test_*.py"):
        return True

    if parts[0] == "skills" and len(parts) > 2 and "projects" in parts[2:]:
        return True

    return False


def is_text_file(path):
    return path.suffix in TEXT_SUFFIXES and path.is_file() and not path.is_symlink()


def new_article(art_id, kind, rel, text, cc):
    fmt = "source" if rel and not rel.endswith(".md") else "md"
    fm, body = cc.split_frontmatter(text) if fmt == "md" else ({}, text)
    if fmt == "md":
        body = RE_TITLE_HEADING.sub("", body, count=1)
    return {
        "id": art_id,
        "kind": kind,
        "path": rel,
        "fmt": fmt,
        "title": rel,
        "fm": fm,
        "raw": body,
        "body": "",
        "source": "",
        "info": [],
        "out": [],
        "back": [],
        "also": [],
        "notes": [],
    }


def read_article(root, rel, art_id, kind, cc):
    text = (root / rel).read_text(encoding="utf-8")
    return new_article(art_id, kind, rel, text, cc)


def collect_skills(root, cc, articles):
    base = root / "skills"
    if not base.is_dir():
        return

    for skill_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        name = skill_dir.name
        if name == "pi" or not (skill_dir / "SKILL.md").is_file():
            continue

        for path in sorted(skill_dir.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if is_excluded(rel) or not is_text_file(path):
                continue

            inner = rel[len(f"skills/{name}/"):]
            if inner == "SKILL.md":
                art = read_article(root, rel, f"skill/{name}", "skill", cc)
                art["title"] = name
                art["name"] = name
            else:
                art = read_article(root, rel, f"skill/{name}/{inner}", "skillfile", cc)
                art["parent"] = f"skill/{name}"
            articles[art["id"]] = art


def collect_flat(root, cc, articles, folder, kind):
    base = root / folder
    if not base.is_dir():
        return

    for path in sorted(base.glob("*.md")):
        rel = path.relative_to(root).as_posix()
        art = read_article(root, rel, f"{kind}/{path.stem}", kind, cc)
        art["title"] = f"/{path.stem}" if kind == "command" else path.stem
        art["name"] = path.stem
        articles[art["id"]] = art


def collect_tree(root, cc, articles, folder, kind):
    base = root / folder
    if not base.is_dir():
        return

    for path in sorted(base.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if is_excluded(rel) or not is_text_file(path):
            continue
        articles[rel] = read_article(root, rel, rel, kind, cc)


def collect_documents(root, cc, articles):
    for name in DOCUMENTS:
        if not (root / name).is_file():
            continue
        art = read_article(root, name, f"doc/{name}", "document", cc)
        art["title"] = name
        articles[art["id"]] = art


def collect(root, cc):
    articles = {}
    collect_skills(root, cc, articles)
    collect_flat(root, cc, articles, "agents", "agent")
    collect_flat(root, cc, articles, "commands", "command")
    collect_tree(root, cc, articles, "hooks", "hook")
    collect_tree(root, cc, articles, "scripts", "script")
    collect_documents(root, cc, articles)
    return articles


def count_kinds(articles):
    counts = {"skills": 0, "agents": 0, "commands": 0}
    for art in articles.values():
        if art["kind"] == "skill":
            counts["skills"] += 1
        if art["kind"] == "agent":
            counts["agents"] += 1
        if art["kind"] == "command":
            counts["commands"] += 1
    return counts


def check_expected_counts(articles, expected):
    if not expected:
        return

    counts = count_kinds(articles)
    if counts == expected:
        return

    lines = [f"collected counts {counts} differ from expected {expected}"]
    for kind in ("skill", "agent", "command"):
        names = sorted(a["name"] for a in articles.values() if a["kind"] == kind)
        lines.append(f"{kind}s ({len(names)}): {', '.join(names)}")
    raise BuildError("\n".join(lines))


def load_json(path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_categories(readme_text, skill_names):
    categories = {}
    current = None

    for line in readme_text.split("\n"):
        heading = RE_CATEGORY.match(line)
        if heading:
            current = heading.group(1)
            continue

        item = RE_CATEGORY_ITEM.match(line)
        if item and current and item.group(1) in skill_names:
            categories.setdefault(item.group(1), current)

    return categories


def leading_comment(text):
    lines = text.split("\n")
    if lines and lines[0].startswith("#!"):
        lines = lines[1:]

    block = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            block.append(stripped.lstrip("#").strip())
            continue
        if not stripped and not block:
            continue
        break

    return " ".join(part for part in block if part).strip()


def first_paragraph(text):
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "|", "```", "-", "@")):
            return stripped
    return ""


def describe(art):
    if art["fm"].get("description"):
        return art["fm"]["description"]
    if art["fmt"] == "source":
        return leading_comment(art["raw"])
    return first_paragraph(art["raw"])


def build_pathmap(articles):
    return {art["path"]: art["id"] for art in articles.values() if art["path"]}


def hook_row(event, matcher, hook, pathmap):
    command = hook.get("command", "")
    found = RE_HOME_CLAUDE.search(command)
    row = {
        "event": event,
        "matcher": matcher,
        "id": None,
        "label": command[:80],
        "args": "",
        "async": bool(hook.get("async")),
        "timeout": hook.get("timeout"),
    }

    if found:
        rel = found.group(1)
        row["label"] = rel
        row["id"] = pathmap.get(rel)
        row["args"] = command[found.end():].strip().lstrip('"').strip()
    elif "bashfilter" in command:
        row["label"] = "bashfilter-chain (optional, not included)"

    return row


def parse_hook_config(path, pathmap):
    data = load_json(path, {})
    rows = []

    for event, groups in data.get("hooks", {}).items():
        for group in groups:
            matcher = group.get("matcher", "")
            for hook in group.get("hooks", []):
                rows.append(hook_row(event, matcher, hook, pathmap))

    return rows


def parse_mcp(path):
    data = load_json(path, {})
    rows = []

    for name, cfg in data.get("user", {}).items():
        rows.append(mcp_row("user", name, cfg))

    for project, servers in data.get("projects", {}).items():
        for name, cfg in servers.items():
            rows.append(mcp_row(project, name, cfg))

    return rows


def mcp_row(scope, name, cfg):
    return {
        "scope": scope,
        "name": name,
        "transport": cfg.get("type", ""),
        "url": cfg.get("url") or cfg.get("command", ""),
    }


def build_wiring(root, pathmap):
    return {
        "claude": parse_hook_config(root / "settings.json", pathmap),
        "codex": parse_hook_config(root / "codex" / "hooks.json", pathmap),
        "mcp": parse_mcp(root / "mcp" / "servers.json"),
    }


def event_label(source, row):
    label = f"{source}: {row['event']}"
    if row["matcher"]:
        label += f" ({row['matcher']})"
    return label


def wiring_by_script(wiring):
    wired = {}
    for source, key in (("Claude Code", "claude"), ("Codex", "codex")):
        for row in wiring[key]:
            if row["id"]:
                wired.setdefault(row["id"], []).append(event_label(source, row))
    return wired


def command_triggers(wiring):
    triggers = {}
    for row in wiring["claude"]:
        if row["event"] != "UserPromptExpansion" or not row["matcher"]:
            continue
        for name in row["matcher"].split("|"):
            triggers.setdefault(name, []).append(row)
    return triggers


class Linker:
    def __init__(self, cc, articles, pathmap, registries):
        self.cc = cc
        self.articles = articles
        self.pathmap = pathmap
        skills, commands, agents = registries
        self.skills = {n for n in skills if f"skill/{n}" in articles}
        self.commands = {n for n in commands if f"command/{n}" in articles}
        self.agents = {n for n in agents if f"agent/{n}" in articles}
        self.excluded = set(agents) | cc.CORE_TOOLS | cc.THIRD_PARTY_TOOLS
        self.current = None
        self.linked = set()

    def current_path(self):
        return self.current["path"] or ""

    def name_target(self, name):
        if name in self.skills:
            return f"skill/{name}"
        if name in self.agents:
            return f"agent/{name}"
        if name in self.commands:
            return f"command/{name}"
        return None

    def slash_target(self, name):
        if name in self.skills:
            return f"skill/{name}"
        if name in self.commands:
            return f"command/{name}"
        return None

    def claude_path_target(self, text):
        if not RE_CLAUDE_PREFIX.match(text):
            return None
        return self.pathmap.get(RE_CLAUDE_PREFIX.sub("", text))

    def span_target(self, span):
        span = span.strip()
        slash = self.cc.RE_SLASH.match(span)
        if slash:
            return self.slash_target(slash.group(1))
        return self.name_target(span) or self.claude_path_target(span)

    def hit(self, target):
        if not target or target == self.current["id"]:
            return None
        self.linked.add(target)
        return target

    def link_code(self, token):
        span = token[1:-1]
        target = self.hit(self.span_target(span))
        if not target:
            return token
        return f"[{token}](#/{target})"

    def link_markdown(self, token):
        match = RE_MD_LINK.match(token)
        text, url = match.group(1), match.group(2)
        if not url or url.startswith("#") or RE_SCHEME.match(url):
            return token

        base = posixpath.dirname(self.current_path())
        target_path = posixpath.normpath(posixpath.join(base, url.split("#")[0]))
        target = self.hit(self.pathmap.get(target_path))
        if target:
            return f"[{text}](#/{target})"
        return text

    def link_token(self, token):
        if token.startswith("["):
            return self.link_markdown(token)
        return self.link_code(token)

    def bare_replace(self, match):
        text = match.group(0)
        if text.startswith("/"):
            target = self.hit(self.slash_target(match.group(1)))
        else:
            target = self.hit(self.claude_path_target(text))
        if not target:
            return text
        return f"[{text}](#/{target})"

    def link_plain(self, text):
        text = RE_BARE_PATH.sub(self.bare_replace, text)
        return RE_BARE_SLASH.sub(self.bare_replace, text)

    def link_line(self, line):
        out = []
        pos = 0

        for match in RE_CODE_OR_LINK.finditer(line):
            out.append(self.link_plain(line[pos:match.start()]))
            out.append(self.link_token(match.group(0)))
            pos = match.end()

        out.append(self.link_plain(line[pos:]))
        return "".join(out)

    def link_tier_cell(self, line):
        match = RE_TIER_CELL.match(line)
        if not match or match.group(2) not in self.agents:
            return line

        target = self.hit(f"agent/{match.group(2)}")
        if not target:
            return line
        name = match.group(2)
        return RE_TIER_CELL.sub(f"{match.group(1)}**[{name}](#/{target})**", line, count=1)

    def fence_flags(self, lines):
        flags = []
        inside = False
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                flags.append(True)
                inside = not inside
                continue
            flags.append(inside)
        return flags

    def detect(self, lines, fenced):
        visible = ["" if fenced[i] else line for i, line in enumerate(lines)]
        found = set()
        tier_lines = set()

        for line in visible:
            for name in self.cc.skill_candidates(line, self.excluded):
                target = self.slash_target(name)
                if target:
                    found.add(target)

        for number, token, source in self.cc.agent_candidates(self.current_path(), visible):
            if token in self.agents:
                found.add(f"agent/{token}")
                if source == "the delegation table":
                    tier_lines.add(number)

        return found, tier_lines

    def process(self, art):
        self.current = art
        self.linked = set()
        lines = art["raw"].split("\n")
        fenced = self.fence_flags(lines)
        detected, tier_lines = self.detect(lines, fenced)

        out = []
        for index, line in enumerate(lines):
            if fenced[index]:
                out.append(line)
                continue
            if index + 1 in tier_lines:
                line = self.link_tier_cell(line)
            out.append(self.link_line(line))

        art["body"] = "\n".join(out)
        detected.discard(art["id"])
        art["also"] = sorted(detected - self.linked)
        return self.linked | detected


def source_calls(art, pathmap):
    found = set()
    base = posixpath.dirname(art["path"])

    for rel in RE_SOURCE_PATH.findall(art["raw"]):
        if rel in pathmap:
            found.add(pathmap[rel])

    for rel in RE_HERE_PATH.findall(art["raw"]):
        joined = posixpath.normpath(posixpath.join(base, rel))
        if joined in pathmap:
            found.add(pathmap[joined])

    found.discard(art["id"])
    return found


def apply_extra_links(extra, articles):
    edges = {}
    notes = {}

    for entry in extra:
        source = entry.get("from")
        if source not in articles:
            raise BuildError(f"links.json: unknown article {source!r}")

        if entry.get("to"):
            if entry["to"] not in articles:
                raise BuildError(f"links.json: unknown target {entry['to']!r}")
            edges.setdefault(source, set()).add(entry["to"])

        if entry.get("note"):
            notes.setdefault(source, []).append(entry["note"])

    return edges, notes


def split_list(value):
    tokens = re.split(r"[,\s]+", value or "")
    return [t for t in tokens if t and t != "-"]


def load_principles(site_dir, cc, articles):
    base = site_dir / "principles"
    if not base.is_dir():
        return

    for path in sorted(base.glob("*.md")):
        fm, body = cc.split_frontmatter(path.read_text(encoding="utf-8"))
        art = new_article(f"principle/{path.stem}", "principle", None, "", cc)
        art.update({"title": fm.get("title") or path.stem, "fm": fm, "raw": body})
        art["covers_spec"] = split_list(fm.get("covers", ""))
        articles[art["id"]] = art


def load_main(site_dir, cc, articles):
    path = site_dir / "main.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Skillbook\n"
    fm, body = cc.split_frontmatter(text)
    art = new_article("main", "main", None, "", cc)
    art.update({"title": fm.get("title") or "Skillbook", "fm": fm, "raw": body})
    articles["main"] = art


def add_pages(root, site_dir, cc, articles):
    readme = root / "skills" / "README.md"
    if readme.is_file():
        art = read_article(root, "skills/README.md", "skills/README.md", "index", cc)
        art["title"] = "Skills index"
        articles[art["id"]] = art

    load_main(site_dir, cc, articles)
    load_principles(site_dir, cc, articles)

    wiring = new_article("wiring", "wiring", None, "", cc)
    wiring["title"] = "Wiring"
    articles["wiring"] = wiring


def resolve_covers(articles):
    covered = {}

    for art in articles.values():
        if art["kind"] != "principle":
            continue

        ids = []
        for spec in art["covers_spec"]:
            matches = [i for i in articles if i != art["id"] and fnmatch.fnmatchcase(i, spec)]
            matches = [i for i in matches if articles[i]["kind"] in ENTRY_KINDS]
            if not matches:
                raise BuildError(f"{art['id']}: covers {spec!r} matches no article")
            ids.extend(matches)

        art["covers"] = sorted(set(ids))
        for entry in art["covers"]:
            covered.setdefault(entry, []).append(art["id"])

    return covered


def principles_for(art, covered):
    ids = set(covered.get(art["id"], []))
    if art["kind"] == "skillfile":
        ids |= set(covered.get(art["parent"], []))
    return sorted(ids)


def find_uncovered(articles, covered):
    return sorted(
        a["id"] for a in articles.values()
        if a["kind"] in ENTRY_KINDS and not principles_for(a, covered)
    )


def item(articles, art_id):
    return {"text": articles[art_id]["title"], "id": art_id}


def text_item(text):
    return {"text": text}


def row(label, items):
    return {"label": label, "items": items}


def ids_row(articles, label, ids):
    if not ids:
        return None
    return row(label, [item(articles, i) for i in ids])


def text_row(label, value):
    if not value:
        return None
    return row(label, [text_item(value)])


def trigger_items(rows):
    items = []
    for hook in rows:
        entry = {"text": hook["label"]}
        if hook["id"]:
            entry["id"] = hook["id"]
        else:
            entry["text"] = f"{hook['label']} (not included)"
        items.append(entry)
    return items


def build_info(art, ctx):
    articles = ctx["articles"]
    kind = art["kind"]
    rows = []

    if kind == "skill":
        rows += skill_rows(art, ctx)
    elif kind == "agent":
        rows += agent_rows(art)
    elif kind == "command":
        rows += command_rows(art, ctx)
    elif kind in ("hook", "script", "skillfile"):
        rows += file_rows(art, ctx)
    elif kind == "document":
        rows.append(text_row("Path", art["path"]))
    elif kind == "principle":
        rows.append(ids_row(articles, "Covers", art.get("covers", [])))

    rows.append(ids_row(articles, "Also references", art["also"]))
    rows.append(ids_row(articles, "Principles", principles_for(art, ctx["covered"])))
    for note in art["notes"]:
        rows.append(text_row("Note", note))

    return [r for r in rows if r]


def skill_rows(art, ctx):
    articles = ctx["articles"]
    fm = art["fm"]
    name = art["name"]
    files = sorted(i for i, a in articles.items() if a.get("parent") == art["id"])
    invocation = "Slash-only" if fm.get("disable-model-invocation", "").lower() == "true" else ""

    return [
        text_row("Description", fm.get("description")),
        text_row("Category", ctx["categories"].get(name, UNCATEGORIZED)),
        text_row("Invocation", invocation),
        text_row("Allowed tools", fm.get("allowed-tools")),
        text_row("Path", art["path"]),
        ids_row(articles, "Files", files),
    ]


def agent_rows(art):
    fm = art["fm"]
    return [
        text_row("Description", fm.get("description")),
        text_row("Model", fm.get("model")),
        text_row("Tools", fm.get("tools")),
        text_row("Capability", fm.get("capability")),
        text_row("Path", art["path"]),
    ]


def command_rows(art, ctx):
    fm = art["fm"]
    triggered = ctx["triggers"].get(art["name"], [])
    trigger = row("Triggers hook", trigger_items(triggered)) if triggered else None
    return [
        text_row("Description", fm.get("description")),
        trigger,
        text_row("Path", art["path"]),
    ]


def file_rows(art, ctx):
    articles = ctx["articles"]
    wired = ctx["wired"].get(art["id"], [])
    called_by = sorted(ctx["called_by"].get(art["id"], []))
    parent = [art["parent"]] if art.get("parent") else []

    return [
        text_row("Description", describe(art)),
        ids_row(articles, "Part of", parent),
        text_row("Path", art["path"]),
        row("Wired to", [text_item(w) for w in wired]) if wired else None,
        ids_row(articles, "Calls", art.get("calls", [])),
        ids_row(articles, "Called by", called_by),
    ]


def compute_edges(articles, linker, pathmap, extra_edges):
    edges = {}

    for art in articles.values():
        if art["fmt"] == "md":
            edges[art["id"]] = set(linker.process(art))
        else:
            art["source"] = art["raw"]
            calls = source_calls(art, pathmap)
            art["calls"] = sorted(calls)
            edges[art["id"]] = set(calls)

        edges[art["id"]] |= extra_edges.get(art["id"], set())
        edges[art["id"]].discard(art["id"])

    return edges


def invert(edges):
    inverted = {}
    for source, targets in edges.items():
        for target in targets:
            inverted.setdefault(target, set()).add(source)
    return inverted


def build_nav(articles, categories):
    def ids_of(kind):
        return sorted(i for i, a in articles.items() if a["kind"] == kind)

    grouped = {}
    for art_id in ids_of("skill"):
        category = categories.get(articles[art_id]["name"], UNCATEGORIZED)
        grouped.setdefault(category, []).append(art_id)

    order = list(dict.fromkeys(categories.values()))
    skill_groups = [{"title": "Index", "ids": ["skills/README.md"]}] if "skills/README.md" in articles else []
    for category in sorted(grouped, key=lambda c: (c == UNCATEGORIZED, order.index(c) if c in order else 0)):
        skill_groups.append({"title": category, "ids": grouped[category]})

    return [
        {"title": "Main page", "groups": [{"title": "", "ids": ["main"]}]},
        {"title": "Principles", "groups": [{"title": "", "ids": ids_of("principle")}]},
        {"title": "Skills", "groups": skill_groups},
        {"title": "Agents", "groups": [{"title": "", "ids": ids_of("agent")}]},
        {"title": "Commands", "groups": [{"title": "", "ids": ids_of("command")}]},
        {"title": "Hooks", "groups": [{"title": "", "ids": ids_of("hook")}]},
        {"title": "Scripts", "groups": [{"title": "", "ids": ids_of("script")}]},
        {"title": "Documents", "groups": [{"title": "", "ids": ids_of("document")}]},
        {"title": "Wiring", "groups": [{"title": "", "ids": ["wiring"]}]},
    ]


def build_route(articles):
    fm = articles["main"]["fm"]
    stops = split_list(fm.get("route", ""))
    gates = set(split_list(fm.get("gates", "")))
    branch = split_list(fm.get("branch", ""))
    coordinator = split_list(fm.get("coordinator", ""))
    branch_from = split_list(fm.get("branch_from", ""))

    referenced = stops + list(gates) + branch + coordinator + branch_from
    missing = [i for i in referenced if i not in articles]
    if missing:
        raise BuildError("route names unknown articles: " + ", ".join(missing))

    return {
        "stops": [{"id": i, "gate": i in gates} for i in stops],
        "branch": branch[0] if branch else None,
        "branch_from": branch_from[0] if branch_from else None,
        "coordinator": coordinator[0] if coordinator else None,
    }


def build_model(root, site_dir, expected=None):
    cc = load_corpus_check()
    articles = collect(root, cc)
    check_expected_counts(articles, expected)
    add_pages(root, site_dir, cc, articles)

    pathmap = build_pathmap(articles)
    registries = cc.build_registries(root)
    skill_names = {a["name"] for a in articles.values() if a["kind"] == "skill"}
    readme = articles.get("skills/README.md")
    categories = parse_categories(readme["raw"], skill_names) if readme else {}
    wiring = build_wiring(root, pathmap)

    linker = Linker(cc, articles, pathmap, registries)
    extra_edges, extra_notes = apply_extra_links(load_json(site_dir / "links.json", []), articles)
    edges = compute_edges(articles, linker, pathmap, extra_edges)
    backs = invert(edges)
    covered = resolve_covers(articles)

    for art_id, notes in extra_notes.items():
        articles[art_id]["notes"] = notes

    ctx = {
        "articles": articles,
        "categories": categories,
        "covered": covered,
        "wired": wiring_by_script(wiring),
        "triggers": command_triggers(wiring),
        "called_by": invert({a["id"]: set(a.get("calls", [])) for a in articles.values()}),
    }

    for art in articles.values():
        art["out"] = sorted(edges[art["id"]])
        art["back"] = sorted(backs.get(art["id"], set()))
        art["info"] = build_info(art, ctx)

    return {
        "articles": articles,
        "nav": build_nav(articles, categories),
        "wiring": wiring,
        "route": build_route(articles),
        "uncovered": find_uncovered(articles, covered),
        "edge_count": sum(len(t) for t in edges.values()),
    }


def load_redactions(path):
    if not path.is_file():
        raise BuildError(f"redaction config missing: {path}")

    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise BuildError(f"redaction config has no rules: {path}")

    return [(re.compile(e["pattern"]), e["replace"], e["pattern"]) for e in entries]


def redact_string(text, redactions):
    for rx, replace, _ in redactions:
        text = rx.sub(replace, text)
    return text


def redact_value(value, redactions):
    if isinstance(value, str):
        return redact_string(value, redactions)
    if isinstance(value, list):
        return [redact_value(v, redactions) for v in value]
    if isinstance(value, dict):
        return {redact_value(k, redactions): redact_value(v, redactions) for k, v in value.items()}
    return value


def public_article(art):
    keys = ("id", "kind", "title", "path", "fmt", "body", "source", "info", "back")
    return {key: art[key] for key in keys}


def public_model(model):
    return {
        "articles": [public_article(a) for a in model["articles"].values()],
        "nav": model["nav"],
        "wiring": model["wiring"],
        "route": model["route"],
    }


def redacted_public(model, redactions):
    return redact_value(public_model(model), redactions)


def find_leaks(text, redactions):
    return [source for rx, _, source in redactions if rx.search(text)]


def leak_locations(public, redactions, source):
    rx = next(r for r, _, s in redactions if s == source)
    where = [a["id"] for a in public["articles"] if rx.search(json.dumps(a, ensure_ascii=False))]
    if rx.search(json.dumps(public["wiring"], ensure_ascii=False)):
        where.append("wiring")
    return where or ["template"]


def assert_no_leaks(text, redactions, public=None):
    leaks = find_leaks(text, redactions)
    if not leaks:
        return

    lines = []
    for source in leaks:
        where = leak_locations(public, redactions, source) if public else ["page"]
        lines.append(f"redaction leak: pattern `{source}` in {', '.join(where[:6])}")
    raise RedactionLeak("\n".join(lines))


def unresolved_links(public):
    known = {a["id"] for a in public["articles"]}
    missing = []

    for art in public["articles"]:
        for target in RE_HREF.findall(art["body"]):
            if target not in known:
                missing.append((art["id"], target))
        for info_row in art["info"]:
            for entry in info_row["items"]:
                if entry.get("id") and entry["id"] not in known:
                    missing.append((art["id"], entry["id"]))

    for wiring_row in public["wiring"]["claude"] + public["wiring"]["codex"]:
        if wiring_row["id"] and wiring_row["id"] not in known:
            missing.append(("wiring", wiring_row["id"]))

    return missing


def inline_asset(text, closing):
    return re.sub(rf"</({closing})", lambda m: f"<\\/{m.group(1)}", text, flags=re.IGNORECASE)


def embed_json(data):
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


RE_FONT = re.compile(r"\{\{font:([A-Za-z0-9._-]+)\}\}")


def inline_fonts(css, site_dir):
    def encode(match):
        data = (site_dir / "vendor" / "fonts" / match.group(1)).read_bytes()
        return "data:font/woff2;base64," + base64.b64encode(data).decode("ascii")

    return RE_FONT.sub(encode, css)


def assemble(public, site_dir):
    template = (site_dir / "template.html").read_text(encoding="utf-8")
    parts = {
        "CSS": inline_asset(inline_fonts((site_dir / "style.css").read_text(encoding="utf-8"), site_dir), "style"),
        "MARKED": inline_asset((site_dir / "vendor" / "marked.min.js").read_text(encoding="utf-8"), "script"),
        "APP": inline_asset((site_dir / "app.js").read_text(encoding="utf-8"), "script"),
        "DATA": embed_json(public),
    }
    return re.sub(r"\{\{(CSS|MARKED|APP|DATA)\}\}", lambda m: parts[m.group(1)], template)


def summary_line(model, unresolved, size_kb):
    kinds = {}
    for art in model["articles"].values():
        kinds[art["kind"]] = kinds.get(art["kind"], 0) + 1

    parts = [
        f"skills {kinds.get('skill', 0)}",
        f"agents {kinds.get('agent', 0)}",
        f"commands {kinds.get('command', 0)}",
        f"hooks {kinds.get('hook', 0)}",
        f"scripts {kinds.get('script', 0)}",
        f"documents {kinds.get('document', 0)}",
        f"principles {kinds.get('principle', 0)}",
        f"links {model['edge_count']}",
        f"unresolved {len(unresolved)}",
        f"uncovered {len(model['uncovered'])}",
        f"{size_kb} KB",
    ]
    return " · ".join(parts)


def run(root, site_dir, out_path, expected):
    model = build_model(root, site_dir, expected)
    redactions = load_redactions(site_dir / "redact.json")
    public = redacted_public(model, redactions)

    unresolved = unresolved_links(public)
    if unresolved:
        lines = [f"broken link: {src} -> #/{dst}" for src, dst in unresolved]
        raise BuildError("\n".join(lines))

    html = assemble(public, site_dir)
    assert_no_leaks(html, redactions, public)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return summary_line(model, unresolved, round(len(html.encode("utf-8")) / 1024))


def main():
    ap = argparse.ArgumentParser(description="Build site/build/index.html, the skillbook intro site.")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    site_dir = root / "site"
    out_path = Path(args.out) if args.out else site_dir / "build" / "index.html"

    try:
        print(run(root, site_dir, out_path, EXPECTED_COUNTS))
    except BuildError as exc:
        print(f"build-site: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
