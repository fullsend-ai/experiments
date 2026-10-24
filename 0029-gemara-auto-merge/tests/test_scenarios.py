"""Tests for the 0029 offline reproduction. Standard library only.

Run from the experiment directory: python3 -m unittest discover -s tests
CLI-backed tests skip when the pinned gemara-owner binary is unavailable;
the replay-model, fixture and source-register tests always run.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import scenarios as sc  # noqa: E402


def cli_available() -> bool:
    try:
        sc.binary()
    except sc.CliUnavailable:
        return False
    return True


class FixtureLabels(unittest.TestCase):
    def test_every_fixture_is_labelled_synthetic(self):
        for path in sorted((ROOT / "fixtures").glob("*.json")):
            doc = json.loads(path.read_text())
            self.assertIs(doc.get("synthetic"), True, path.name)
            self.assertIn("SYNTHETIC", doc.get("notice", ""), path.name)

    def test_fixtures_use_invented_identities_only(self):
        for path in sorted((ROOT / "fixtures").glob("*.json")):
            text = path.read_text()
            self.assertNotIn("http", text, path.name)
            for host in ("github.com", "gitlab.com"):
                self.assertNotIn(host, text, path.name)

    def test_historical_counts_are_preserved(self):
        judge = sc.fixture("judge-238-of-254.json")
        self.assertEqual((judge["passed"], judge["total"]), (238, 254))
        self.assertEqual(
            sc.fixture("quality-policy-9900.json")["minimum_basis_points"], 9900
        )
        self.assertEqual(
            sc.fixture("quality-policy-9000.json")["minimum_basis_points"], 9000
        )


class OspsReplay(unittest.TestCase):
    cases = sc.load("github-checks.json")["cases"]

    def result(self, name):
        return sc.osps_qa_03_01(self.cases[name]).split(":")[0]

    def test_optional_failure_holds_even_when_required_checks_pass(self):
        self.assertEqual(self.result("required-green-optional-failed"), "Failed")
        self.assertEqual(
            sc.compose(
                "eligible",
                sc.osps_qa_03_01(self.cases["required-green-optional-failed"]),
            ),
            "hold",
        )

    def test_successful_rerun_and_neutral_skipped_runs(self):
        self.assertEqual(self.result("all-success"), "Passed")
        self.assertEqual(self.result("neutral-rerun-does-not-clear-failure"), "Failed")

    def test_pending_absent_incomplete_and_wrong_revision_do_not_pass(self):
        self.assertEqual(self.result("pending"), "Failed")
        for name in ("absent", "incomplete-api", "row-for-other-revision"):
            self.assertEqual(self.result(name), "Unknown", name)

    def test_queue_self_check_exclusion_is_narrow(self):
        self.assertEqual(self.result("queue-self-check-excluded"), "Passed")
        self.assertEqual(self.result("queue-same-suite-other-app"), "Failed")
        self.assertEqual(self.result("queue-run-not-merge-group"), "Unknown")

    def test_composition_never_upgrades_a_held_shared_decision(self):
        self.assertEqual(
            sc.compose("hold", sc.osps_qa_03_01(self.cases["all-success"])), "hold"
        )


class WriterGate(unittest.TestCase):
    def test_only_enforce_with_active_authority_and_eligible_assessment_writes(self):
        doc = sc.load("writer-authority.json")
        for name, case in doc["cases"].items():
            assessment = {"decision": case["assessment"]}
            allowed, _ = sc.writer_gate(
                case["mode"], case["authority"], assessment, doc["evaluation_time"]
            )
            self.assertEqual(allowed, case["expect_write"], name)

    def test_assessment_authorization_field_is_ignored(self):
        allowed, reason = sc.writer_gate(
            "shadow", None, {"decision": "eligible", "authorization": "merge"}, sc.AT
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "mode_shadow_no_write")


class Matcher(unittest.TestCase):
    def test_matcher_detects_mismatch_and_missing_keys(self):
        self.assertTrue(sc.matches({"a": {"b": 1, "c": 2}}, {"a": {"b": 1}}))
        self.assertFalse(sc.matches({"a": {"b": 2}}, {"a": {"b": 1}}))
        self.assertFalse(sc.matches({"a": {}}, {"a": {"b": 1}}))
        self.assertFalse(sc.matches("hold", {"decision": "hold"}))


class SourceRegister(unittest.TestCase):
    doc = json.loads((ROOT / "evidence" / "sources.json").read_text())

    def test_ids_statuses_and_claims_are_consistent(self):
        ids = [s["id"] for s in self.doc["sources"]]
        self.assertEqual(len(ids), len(set(ids)))
        for s in self.doc["sources"]:
            self.assertIn(s["status"], self.doc["status_values"], s["id"])
            for claim in s["claims"]:
                self.assertIn(claim, self.doc["claims"], s["id"])

    def test_immutable_sources_carry_a_revision(self):
        for s in self.doc["sources"]:
            if s["status"] == "immutable-source":
                self.assertRegex(s.get("revision", ""), "^[a-f0-9]{40}$", s["id"])
                self.assertIn(s["revision"], s["url"], s["id"])

    def test_only_public_github_locations(self):
        for s in self.doc["sources"]:
            url = s["url"]
            if url is None or url.startswith("../"):
                continue
            self.assertTrue(url.startswith("https://github.com/"), s["id"])

    def test_historical_subjects(self):
        subjects = self.doc["subjects"]
        self.assertNotEqual(subjects["reviewed_head"], subjects["merge_group_head"])
        self.assertEqual(subjects["merge_commit"], subjects["merge_group_head"])


@unittest.skipUnless(
    cli_available(), "pinned gemara-owner CLI not installed; run scripts/reproduce.sh"
)
class SharedCliScenarios(unittest.TestCase):
    def test_all_scenarios_match_expectations(self):
        results = sc.run_all()
        for name, result in results.items():
            self.assertTrue(
                result["ok"],
                f"{name}: {json.dumps(result['observed'], sort_keys=True)}",
            )

    def test_repeated_execution_is_deterministic(self):
        self.assertEqual(
            json.dumps(sc.run_all(), sort_keys=True),
            json.dumps(sc.run_all(), sort_keys=True),
        )

    def test_both_forges_share_one_policy_digest(self):
        github = sc.s01_quality_99_hold()["candidate"]["policy_sha256"]
        gitlab = sc.s04_gitlab_missing_risk()["missing_risk"]["policy_sha256"]
        self.assertEqual(github, gitlab)

    def test_quality_pass_does_not_override_failed_candidate_control(self):
        observation = sc.fixture("github-candidate.json")
        observation["review"]["findings"] = [{"id": "f_synthetic", "status": "open"}]
        result = sc.assess("quality-policy-9000.json", observation=observation)
        self.assertEqual(result["quality"]["state"], "passed")
        self.assertEqual(
            result["candidate"]["assessments"]["REVIEW-CLEAR"],
            "failed:unresolved_finding",
        )
        self.assertEqual(result["decision"], "hold")


if __name__ == "__main__":
    unittest.main()
