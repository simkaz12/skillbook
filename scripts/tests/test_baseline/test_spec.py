import unittest

from test_baseline import spec
from .support import SAMPLE


class ParseTesting(unittest.TestCase):
    def test_base_sections_and_order(self):
        parsed = spec.parse_testing(SAMPLE)

        self.assertEqual(parsed.base, "dev")
        self.assertEqual(list(parsed.repos), ["crm-api", "crm-web"])
        self.assertEqual(len(parsed.repos["crm-api"].full), 1)
        self.assertEqual(
            parsed.repos["crm-web"].full,
            ["npx vitest run --reporter=junit --outputFile=.test-results/vitest.xml", "npm run build"],
        )

    def test_dir_placeholder_is_kept(self):
        parsed = spec.parse_testing(SAMPLE)

        self.assertIn("{dir}", parsed.repos["crm-api"].focused[0])

    def test_shipped_files_parse(self):
        for file in (spec.SKILLBOOK / "agent-projects").glob("*/testing.md"):
            parsed = spec.parse_testing(file.read_text())
            self.assertTrue(parsed.base, file)
            self.assertTrue(any(s.focused for s in parsed.repos.values()), file)
