import unittest

from test_baseline import junit, spec
from test_baseline.errors import Fault
from .support import FIXTURES, SAMPLE


class ParseJunit(unittest.TestCase):
    def test_phpunit(self):
        tests, messages = junit.parse_junit(FIXTURES / "phpunit.xml")

        self.assertEqual(tests["Tests.Feature.FooTest::test_ok"], "pass")
        self.assertEqual(tests["Tests.Feature.FooTest::test_bad"], "fail")
        self.assertEqual(tests["Tests.Feature.BazTest::test_err"], "fail")
        self.assertEqual(tests["Tests.Feature.BazTest::test_skip"], "skip")
        self.assertIn("Failed asserting", messages["Tests.Feature.FooTest::test_bad"][0])

    def test_pytest(self):
        tests, _ = junit.parse_junit(FIXTURES / "pytest.xml")

        self.assertEqual(tests, {"tests.test_a::test_one": "pass", "tests.test_a::test_two": "fail"})

    def test_vitest(self):
        tests, _ = junit.parse_junit(FIXTURES / "vitest.xml")

        self.assertEqual(tests["src/utils/duration.spec.ts::formats hours"], "fail")
        self.assertEqual(tests["src/utils/duration.spec.ts::skipped case"], "skip")
        self.assertEqual(len(tests), 3)

    def test_nextest(self):
        tests, _ = junit.parse_junit(FIXTURES / "nextest.xml")

        self.assertEqual(tests, {"herdr::unit::tests::ok": "pass", "herdr::unit::tests::bad": "fail"})

    def test_empty_classname_uses_file(self):
        tests, _ = junit.parse_junit(FIXTURES / "no-classname.xml")

        self.assertEqual(tests, {"tests/a.py::lonely": "pass"})


class Classify(unittest.TestCase):
    def setUp(self):
        self.base = {"a": "pass", "b": "fail", "c": "fail", "d": "pass", "e": "skip"}

    def run_classify(self, current, base_units=None, cur_units=None):
        return junit.classify(self.base, base_units or {}, current, cur_units or {})

    def test_pass_to_fail_blocks(self):
        classes = self.run_classify({"a": "fail"})

        self.assertEqual(classes["new"], ["a"])

    def test_absent_from_baseline_and_failing_blocks(self):
        classes = self.run_classify({"z": "fail"})

        self.assertEqual(classes["new"], ["z"])

    def test_skip_to_fail_blocks(self):
        classes = self.run_classify({"e": "fail"})

        self.assertEqual(classes["new"], ["e"])

    def test_fail_to_fail_is_pre_existing(self):
        classes = self.run_classify({"b": "fail"})

        self.assertEqual(classes["pre"], ["b"])
        self.assertEqual(classes["new"], [])

    def test_fail_to_pass_is_fixed(self):
        classes = self.run_classify({"b": "pass", "c": "skip"})

        self.assertEqual(classes["fixed"], ["b", "c"])
        self.assertFalse(junit.blocking(classes))

    def test_fail_to_absent_is_not_fixed(self):
        classes = self.run_classify({})

        self.assertEqual(classes["fixed"], [])

    def test_unit_states(self):
        classes = self.run_classify(
            {},
            base_units={"build": "pass", "lint": "fail"},
            cur_units={"build": "fail", "lint": "fail", "types": "fail", "ok": "pass"},
        )

        self.assertEqual(
            classes["units"],
            {"build": "new-failure", "lint": "pre-existing", "types": "new-failure", "ok": "ok"},
        )
        self.assertTrue(junit.blocking(classes))

    def test_unit_fail_to_pass_is_fixed_and_does_not_block(self):
        classes = self.run_classify({}, base_units={"lint": "fail", "build": "pass"}, cur_units={"lint": "pass", "build": "pass"})

        self.assertEqual(classes["units"], {"lint": "fixed", "build": "ok"})
        self.assertFalse(junit.blocking(classes))

    def test_pre_existing_unit_does_not_block(self):
        classes = self.run_classify({}, base_units={"lint": "fail"}, cur_units={"lint": "fail"})

        self.assertFalse(junit.blocking(classes))


class Tripwire(unittest.TestCase):
    def test_more_than_half_failing_raises(self):
        result = junit.Result(tests={"a": "fail", "b": "fail", "c": "pass"}, first_failure="boom")

        with self.assertRaises(Fault) as ctx:
            junit.check_tripwire(result)
        self.assertIn("boom", str(ctx.exception))

    def test_half_failing_passes(self):
        junit.check_tripwire(junit.Result(tests={"a": "fail", "b": "pass"}))

    def test_empty_raises(self):
        with self.assertRaises(Fault):
            junit.check_tripwire(junit.Result())


class Report(unittest.TestCase):
    def test_report_shape(self):
        info = {
            "repo": "crm-api",
            "tree_head": "3fa9c1e",
            "base": "dev",
            "merge_base": "4f5e6d2aaaa",
        }
        classes = {"new": ["A::b"], "pre": ["C::d"], "fixed": [], "units": {"npm run build": "ok"}}

        text = junit.build_report(info, classes)

        self.assertIn("baseline dev@4f5e6d2  merge-base 4f5e6d2", text)
        self.assertNotIn("old)", text)
        self.assertIn("NEW FAILURES (1), blocking", text)
        self.assertIn("UNITS  npm run build ok", text)
        self.assertTrue(text.endswith("RESULT new-failures"))


class JunitProblem(unittest.TestCase):
    def test_nonzero_exit_without_failing_test_is_a_problem(self):
        self.assertIn("exit 2", junit.junit_problem(2, {"a": "pass"}))

    def test_empty_junit_is_a_problem(self):
        self.assertIsNotNone(junit.junit_problem(0, {}))

    def test_nonzero_exit_with_reported_failure_is_fine(self):
        self.assertIsNone(junit.junit_problem(1, {"a": "pass", "b": "fail"}))

    def test_signal_exit_is_a_problem_even_with_a_reported_failure(self):
        self.assertIn("137", junit.junit_problem(137, {"a": "fail"}))

    def test_clean_run_is_fine(self):
        self.assertIsNone(junit.junit_problem(0, {"a": "pass"}))


class JunitPattern(unittest.TestCase):
    def test_junit_path_found(self):
        parsed = spec.parse_testing(SAMPLE)

        found = junit.JUNIT_RE.search(parsed.repos["crm-web"].full[0])
        self.assertEqual(found.group(0), ".test-results/vitest.xml")
        self.assertIsNone(junit.JUNIT_RE.search("npm run build"))
