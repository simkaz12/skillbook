import base64
import importlib.util
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "build_site"

spec = importlib.util.spec_from_file_location("build_site", HERE.parent / "build-site.py")
bs = importlib.util.module_from_spec(spec)
sys.modules["build_site"] = bs
spec.loader.exec_module(bs)


def build():
    model = bs.build_model(FIXTURE, FIXTURE / "site")
    redactions = bs.load_redactions(FIXTURE / "site" / "redact.json")
    public = bs.redacted_public(model, redactions)
    by_id = {a["id"]: a for a in public["articles"]}
    return model, redactions, public, by_id


class LinkRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.redactions, cls.public, cls.by_id = build()
        cls.alpha = cls.by_id["skill/alpha"]["body"]

    def test_backticked_registry_name_links(self):
        self.assertIn("[`beta`](#/skill/beta)", self.alpha)

    def test_bare_word_stays_plain(self):
        self.assertIn("The word beta alone stays plain text.", self.alpha)

    def test_fenced_block_is_untouched(self):
        self.assertIn("beta and `beta` and /beta stay inside the fence", self.alpha)

    def test_slash_name_links(self):
        self.assertIn("[`/beta`](#/skill/beta)", self.alpha)
        self.assertIn("[/beta](#/skill/beta)", self.alpha)

    def test_subagent_type_links(self):
        self.assertIn("agent/hand-ex", self.model["articles"]["skill/alpha"]["out"])
        self.assertIn("agent/hand-ex", self.model["articles"]["skill/alpha"]["also"])

    def test_claude_path_links(self):
        self.assertIn("[`~/.claude/LANGUAGE.md`](#/doc/LANGUAGE.md)", self.alpha)

    def test_relative_md_link_targets_child_article(self):
        self.assertIn("[notes](#/skill/alpha/NOTES.md)", self.alpha)

    def test_missing_relative_target_stays_plain(self):
        self.assertIn("A missing target gone stays plain.", self.alpha)
        self.assertNotIn("GONE.md", self.alpha)

    def test_self_mention_is_not_a_link(self):
        self.assertIn("Self mention `alpha` is not a link.", self.alpha)

    def test_repo_relative_path_span_is_not_linked(self):
        self.assertIn("See `hooks/run.sh` for the runner.", self.alpha)

    def test_raw_html_text_is_kept_for_the_page_to_escape(self):
        self.assertIn("Raw <placeholder> text stays literal.", self.alpha)

    def test_tier_table_cell_links(self):
        body = self.by_id["doc/GLOBAL-CLAUDE.md"]["body"]
        self.assertIn("**[hand-ex](#/agent/hand-ex)**", body)
        self.assertIn("**main**", body)

    def test_backlinks(self):
        self.assertIn("skill/alpha", self.by_id["skill/beta"]["back"])
        self.assertIn("principle/planning", self.by_id["skill/alpha"]["back"])


class Collection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.redactions, cls.public, cls.by_id = build()

    def test_excluded_paths_are_absent(self):
        ids = set(self.by_id)
        self.assertNotIn("skill/pi", ids)
        self.assertFalse([i for i in ids if "projects" in i])
        self.assertFalse([i for i in ids if "tests" in i or i.endswith("test.sh")])

    def test_skill_children_become_articles(self):
        self.assertIn("skill/alpha/NOTES.md", self.by_id)

    def test_count_tripwire(self):
        with self.assertRaises(bs.BuildError) as ctx:
            bs.build_model(FIXTURE, FIXTURE / "site", bs.EXPECTED_COUNTS)
        self.assertIn("differ from expected", str(ctx.exception))

    def test_calls_and_called_by(self):
        run = self.model["articles"]["hooks/run.sh"]
        self.assertEqual(["hooks/helper.sh", "scripts/tool.sh"], run["calls"])
        labels = {r["label"]: r for r in self.by_id["hooks/helper.sh"]["info"]}
        self.assertEqual("hooks/run.sh", labels["Called by"]["items"][0]["id"])

    def test_wiring_and_command_triggers(self):
        row = self.public["wiring"]["claude"][0]
        self.assertEqual(("SessionStart", "hooks/run.sh"), (row["event"], row["id"]))
        labels = {r["label"]: r for r in self.by_id["command/ping"]["info"]}
        self.assertEqual("hooks/helper.sh", labels["Triggers hook"]["items"][0]["id"])
        self.assertEqual("handled elsewhere", labels["Note"]["items"][0]["text"])

    def test_categories_and_principles_in_infobox(self):
        labels = {r["label"]: r for r in self.by_id["skill/alpha"]["info"]}
        self.assertEqual("Plan & design", labels["Category"]["items"][0]["text"])
        self.assertEqual("principle/planning", labels["Principles"]["items"][0]["id"])

    def test_nothing_uncovered_in_fixture(self):
        self.assertEqual([], self.model["uncovered"])

    def test_no_unresolved_links(self):
        self.assertEqual([], bs.unresolved_links(self.public))


class Redaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.redactions, cls.public, cls.by_id = build()
        cls.alpha = cls.by_id["skill/alpha"]["body"]

    def test_fixture_values_are_replaced(self):
        self.assertIn("Network at x.x.x.x and dyn.example with ~ and work-app-api and TICKET-12 leak.", self.alpha)

    def test_wiring_urls_are_redacted(self):
        self.assertEqual("http://x.x.x.x:8787/mcp", self.public["wiring"]["mcp"][0]["url"])

    def test_scan_fails_on_planted_ip_and_names_pattern(self):
        with self.assertRaises(bs.RedactionLeak) as ctx:
            bs.assert_no_leaks("<p>host 203.0.113.1</p>", self.redactions)
        self.assertIn(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", str(ctx.exception))

    def test_scan_names_the_article(self):
        public = {"articles": [{"id": "skill/x", "body": "ip 10.1.2.3"}], "wiring": {}}
        with self.assertRaises(bs.RedactionLeak) as ctx:
            bs.assert_no_leaks("ip 10.1.2.3", self.redactions, public)
        self.assertIn("skill/x", str(ctx.exception))

    def test_site_config_redacts_single_label_user_at_host(self):
        real = bs.load_redactions(bs.ROOT / "site" / "redact.json")
        self.assertEqual("ssh <user>@<host>", bs.redact_string("ssh alice@homelab", real))
        self.assertEqual("<user>@<host>", bs.redact_string("bob@10.1.2.3", real))
        self.assertTrue(bs.find_leaks("ssh alice@homelab", real))
        self.assertEqual([], bs.find_leaks("ssh <user>@<host> and @playwright/mcp@0.0.82 and \\n@dataclass", real))

    def test_clean_text_passes(self):
        bs.assert_no_leaks("nothing private here", self.redactions)


class Failures(unittest.TestCase):
    def test_missing_redaction_config_fails_the_build(self):
        with self.assertRaises(bs.BuildError):
            bs.load_redactions(HERE / "fixtures" / "no-such-redact.json")

    def test_empty_redaction_config_fails_the_build(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "redact.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(bs.BuildError):
                bs.load_redactions(path)

    def test_unresolved_href_is_reported(self):
        public = {
            "articles": [{"id": "a", "body": "[x](#/nope)", "info": []}],
            "wiring": {"claude": [], "codex": []},
        }
        self.assertEqual([("a", "nope")], bs.unresolved_links(public))

    def test_unknown_covers_id_fails_the_build(self):
        articles = {
            "p": {"id": "p", "kind": "principle", "covers_spec": ["skill/zzz"]},
        }
        with self.assertRaises(bs.BuildError):
            bs.resolve_covers(articles)


class Route(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.redactions, cls.public, cls.by_id = build()

    def test_route_is_passed_through_to_the_page_data(self):
        route = self.public["route"]
        self.assertEqual(
            [("skill/alpha", False), ("agent/hand-ex", True), ("skill/beta", False)],
            [(s["id"], s["gate"]) for s in route["stops"]],
        )
        self.assertEqual("skill/beta", route["branch"])
        self.assertEqual("skill/alpha", route["branch_from"])
        self.assertEqual("skill/alpha", route["coordinator"])

    def test_route_naming_an_unknown_article_fails_the_build(self):
        articles = {"main": {"fm": {"route": "skill/alpha, skill/ghost"}}, "skill/alpha": {}}
        with self.assertRaises(bs.BuildError) as ctx:
            bs.build_route(articles)
        self.assertIn("skill/ghost", str(ctx.exception))


class Fonts(unittest.TestCase):
    def test_inlined_font_decodes_to_the_vendored_bytes(self):
        site_dir = HERE.parents[1] / "site"
        name = "literata-latin-wght-normal.woff2"
        css = bs.inline_fonts("src: url({{font:%s}}) format(\"woff2\");" % name, site_dir)
        encoded = re.search(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", css).group(1)
        self.assertEqual((site_dir / "vendor" / "fonts" / name).read_bytes(), base64.b64decode(encoded))

    def test_every_font_placeholder_in_the_stylesheet_resolves(self):
        site_dir = HERE.parents[1] / "site"
        css = bs.inline_fonts((site_dir / "style.css").read_text(encoding="utf-8"), site_dir)
        self.assertNotIn("{{font:", css)
        self.assertEqual(3, css.count("data:font/woff2;base64,"))


if __name__ == "__main__":
    unittest.main()
