import unittest

from benchmark.agent import rule_plan
from benchmark.run import CATALOG, measure


class BenchmarkTests(unittest.TestCase):
    def test_calibration_and_holdout_matrix(self):
        for cohort, split, job, direction in [
            ("A", "calibration", "dict-a-l1", "positive"), ("A", "calibration", "dict-b-l1", "negative"),
            ("B", "calibration", "dict-b-l1", "positive"), ("B", "calibration", "dict-a-l1", "negative"),
            ("A", "holdout", "plain-l1", "negative"), ("A", "holdout", "dict-a-l6", "positive"),
            ("A", "holdout", "dict-b-l6", "negative"),
        ]:
            with self.subTest(cohort=cohort, split=split, job=job):
                r = measure(job, cohort, split)
                self.assertTrue(r["roundtrip_ok"])
                self.assertEqual((r["execution"], r["validity"], r["direction"]), ("completed", "valid", direction))
                self.assertEqual(r["input_bytes"], 928)
                self.assertEqual(r["metric"]["value"], r["output_bytes"]/928)
                self.assertLess(r["elapsed_ms"], 2000)
                self.assertEqual(len(r["reproduce"]["fixture_sha256"]), 64)
                self.assertEqual(r["reproduce"]["dictionary_sha256"] is None, job == "plain-l1")
        crash = measure("dict-c-l1", "A", "calibration")
        self.assertEqual((crash["execution"], crash["validity"], crash["direction"]),
                         ("crashed", "invalid", "undetermined"))
        self.assertIsNone(crash["metric"]["value"])
        self.assertEqual(CATALOG, ("plain-l1", "dict-a-l6", "dict-b-l6"))

    def test_different_applicable_dictionary_can_change_the_plan(self):
        candidate = {"result": {"result_id": "96880441-29cb-490f-93ef-8a2ef82f9dd9", "version": 2,
                                "configuration": {"dictionary_family": "B"}, "direction": "positive"},
                     "applicability": {"status": "applies", "mismatches": []}}
        self.assertEqual(rule_plan([candidate])["job_id"], "dict-b-l6")
        candidate["applicability"] = {"status": "mismatch", "mismatches": [
            {"field": "cohort", "wanted": "A", "found": "B"}]}
        plan = rule_plan([candidate])
        self.assertEqual(plan["job_id"], "plain-l1")
        self.assertEqual(plan["used_refs"], [])
        self.assertEqual(plan["rejected_candidates"][0]["ref"]["version"], 2)


if __name__ == "__main__":
    unittest.main()
