"""Offline scenario runner for experiment 0029 (Gemara-assessed auto-merge).

Policy semantics come from the pinned shared ``gemara-owner`` CLI
(github.com/ascerra/fullsend-gemara-integration at SHARED_REVISION). This file
only feeds it synthetic fixtures and compares the results with expectations.

Two parts are local replay models, not imports, because the lab repository
(fullsend-ai/auto-merge) publishes no license and its code is not copied here:

* ``osps_qa_03_01`` replays the documented check-run/status semantics of the
  lab's OSPS-QA-03.01 GitHub adapter (configured_policy.py, checks_value).
* ``writer_gate`` models the separation between assessment eligibility and
  owner-authorized mutation. It drives a recording mock, never a real writer.

No network, credentials, model or forge write is used. Exit status is 0 only
when every scenario matches its expectation.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
SHARED_MODULE = "github.com/ascerra/fullsend-gemara-integration"
SHARED_REVISION = "61a01465478e50d8e9b3e21dd056fdef90baff30"
AT = "2026-10-20T00:10:00Z"
GITHUB_ACTIONS_APP_ID = 15368
QUEUE_WORKFLOW = ".github/workflows/gemara-merge-queue.yml"
MERGE_GROUP_HEAD = "c3" * 20


class CliUnavailable(RuntimeError):
    pass


def binary() -> str:
    path = os.environ.get("GEMARA_OWNER") or str(
        ROOT / ".cache" / "bin" / "gemara-owner"
    )
    if not Path(path).is_file():
        raise CliUnavailable(
            f"gemara-owner not found at {path}; run scripts/reproduce.sh (setup) or set GEMARA_OWNER"
        )
    return path


def load(name: str) -> dict:
    doc = json.loads((FIXTURES / name).read_text())
    if doc.get("synthetic") is not True:
        raise ValueError(f"{name} is not labelled synthetic")
    return doc


def fixture(name: str) -> dict:
    return copy.deepcopy(load(name)["cli_input"])


def cli(command: str, inputs: dict[str, object]) -> dict:
    """Run the shared CLI. A str input is written verbatim; None means a missing file."""
    with tempfile.TemporaryDirectory() as tmp:
        args = [binary(), command]
        for flag, value in inputs.items():
            path = Path(tmp) / f"{flag}.json"
            if value is not None:
                path.write_text(value if isinstance(value, str) else json.dumps(value))
            args += [f"--{flag}", str(path)]
        args += ["--at", AT]
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=60, env={}, cwd=tmp
        )
    out = {"exit": proc.returncode}
    if proc.stdout.strip():
        out["report"] = json.loads(proc.stdout)
    else:
        out["rejected"] = proc.stderr.strip()
    return out


def summarize_candidate(report: dict) -> dict:
    return {
        "decision": report["decision"],
        "authorization": report["authorization"],
        "mutation_permitted": report["mutation_permitted"],
        "policy_sha256": report["policy_sha256"],
        "binding_sha256": report["binding_sha256"],
        "subject_head": report["subject"]["head_sha"],
        "assessments": {
            a["id"]: f"{a['state']}:{a['reason']}" for a in report["assessments"]
        },
    }


def summarize_quality(report: dict) -> dict:
    return {
        "decision": report["decision"],
        "state": report["state"],
        "reason": report["reason"],
        "passed": report["passed"],
        "total": report["total"],
        "minimum_basis_points": report["minimum_basis_points"],
        "authorization": report["authorization"],
        "mutation_permitted": report["mutation_permitted"],
    }


def summarize(result: dict) -> dict:
    if "report" not in result:
        return {
            "decision": "hold",
            "rejected": result["rejected"],
            "exit": result["exit"],
        }
    r = result["report"]
    if r["schema_version"] == "candidate-assessment/v1":
        out = {
            "decision": r["decision"],
            "authorization": r["authorization"],
            "mutation_permitted": r["mutation_permitted"],
            "candidate": summarize_candidate(r["candidate"]),
            "quality": summarize_quality(r["quality"]),
        }
    elif r["schema_version"] == "judge-check/v1":
        out = summarize_quality(r)
    else:
        out = summarize_candidate(r)
    out["exit"] = result["exit"]
    return out


def assess(
    policy: str = "quality-policy-9000.json",
    observation: dict | None = None,
    judge: object = "default",
) -> dict:
    return summarize(
        cli(
            "assess-candidate",
            {
                "binding": fixture("github-binding.json"),
                "observation": observation
                if observation is not None
                else fixture("github-candidate.json"),
                "judge-policy": fixture(policy),
                "judge-observation": fixture("judge-238-of-254.json")
                if judge == "default"
                else judge,
            },
        )
    )


def check_judge(policy: dict, observation: object) -> dict:
    return summarize(cli("check-judge", {"policy": policy, "observation": observation}))


def judge_with(**changes: object) -> dict:
    value = fixture("judge-238-of-254.json")
    value.update(changes)
    return value


def policy_with(bp: int) -> dict:
    value = fixture("quality-policy-9000.json")
    value["minimum_basis_points"] = bp
    return value


# --- Local replay: OSPS-QA-03.01 GitHub evidence adapter ---------------------


def osps_checks_value(case: dict) -> tuple[bool | None, list[dict]]:
    """Replay of the lab adapter: every observed automated check must succeed.

    Latest run per (app, name) counts, so a successful rerun supersedes a
    failure. Completed neutral/skipped runs are not pass/fail evidence. Pending
    runs are not successful. Latest status per context counts. Incomplete API
    data, rows for another revision, or no evidence at all yield None. In the
    queue phase only the evaluator's own in-flight check (same check suite,
    GitHub Actions app) is excluded, and only for a validated merge_group run.
    There is no manual-bypass exception.
    """
    head = case["head_sha"]
    checks, statuses = case["check_runs"], case["statuses"]
    if (
        not re.fullmatch("[a-f0-9]{40}", head)
        or checks is None
        or statuses is None
        or case["api_errors"]
    ):
        return None, []
    excluded_suite = None
    if case["phase"] == "queue":
        run = case.get("queue_run") or {}
        if (
            run.get("path") != QUEUE_WORKFLOW
            or run.get("event") != "merge_group"
            or run.get("head_sha") != head
            or type(run.get("check_suite_id")) is not int
        ):
            return None, []
        excluded_suite = run["check_suite_id"]
    latest: dict[tuple, dict] = {}
    for row in checks:
        if (
            excluded_suite is not None
            and (row.get("check_suite") or {}).get("id") == excluded_suite
            and (row.get("app") or {}).get("id") == GITHUB_ACTIONS_APP_ID
        ):
            continue
        if row.get("head_sha") != head or type(row.get("id")) is not int:
            return None, []
        if row.get("status") == "completed" and row.get("conclusion") in {
            "neutral",
            "skipped",
        }:
            continue
        key = ((row.get("app") or {}).get("id"), row.get("name"))
        if row["id"] > latest.get(key, {}).get("id", -1):
            latest[key] = row
    evidence = [
        {
            "kind": "check",
            "name": r["name"],
            "passed": r.get("status") == "completed"
            and r.get("conclusion") == "success",
        }
        for r in latest.values()
    ]
    latest_status: dict[str, dict] = {}
    for row in statuses:
        if type(row.get("id")) is not int or not isinstance(row.get("context"), str):
            return None, []
        if row["id"] > latest_status.get(row["context"], {}).get("id", -1):
            latest_status[row["context"]] = row
    evidence += [
        {"kind": "status", "name": r["context"], "passed": r.get("state") == "success"}
        for r in latest_status.values()
    ]
    return (all(e["passed"] for e in evidence) if evidence else None), evidence


def osps_qa_03_01(case: dict) -> str:
    value, _ = osps_checks_value(case)
    if value is None:
        return "Unknown:check_evidence_absent_or_incomplete"
    return (
        "Passed:observed_checks_successful"
        if value
        else "Failed:observed_check_not_successful"
    )


def compose(shared_decision: str, osps: str) -> str:
    """Our AND-composition: shared candidate+quality decision and the selected requirement."""
    return (
        "eligible"
        if shared_decision == "eligible" and osps.startswith("Passed:")
        else "hold"
    )


# --- Mock writer gate ----------------------------------------------------------


class RecordingWriter:
    """Stands in for the lab's separate App writer. It only records calls."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def request_queue_enrollment(self, subject: str) -> None:
        self.calls.append(subject)


def writer_gate(
    mode: str, authority: dict | None, assessment: dict, now: str
) -> tuple[bool, str]:
    """Eligibility is necessary, never sufficient. Authority is separate owner input."""
    if mode != "enforce":
        return False, f"mode_{mode}_no_write"
    if authority is None:
        return False, "owner_authority_absent"
    if not authority["enabled"] or datetime.fromisoformat(
        now
    ) >= datetime.fromisoformat(authority["expires_at"]):
        return False, "owner_authority_inactive"
    if assessment.get("decision") != "eligible":
        return False, "assessment_hold"
    return True, "mock_enrollment_requested"


# --- Scenarios ------------------------------------------------------------------


def s01_quality_99_hold() -> dict:
    return assess("quality-policy-9900.json")


def s02_quality_90_eligible() -> dict:
    result = assess("quality-policy-9000.json")
    writer = RecordingWriter()
    # The lab configuration defaulted to shadow and holds no authority in this replay.
    allowed, reason = writer_gate("shadow", None, result, AT)
    if allowed:
        writer.request_queue_enrollment(result["candidate"]["subject_head"])
    result["writer"] = {"gate": reason, "calls": len(writer.calls)}
    return result


def s03_integer_boundary() -> dict:
    return {
        "225/250 at 9000": check_judge(
            policy_with(9000), judge_with(passed=225, total=250)
        )["state"],
        "224/250 at 9000": check_judge(
            policy_with(9000), judge_with(passed=224, total=250)
        )["state"],
        "99/100 at 9900": check_judge(
            policy_with(9900), judge_with(passed=99, total=100)
        )["state"],
        "98/100 at 9900": check_judge(
            policy_with(9900), judge_with(passed=98, total=100)
        )["state"],
        "238/254 at 9370": check_judge(policy_with(9370), judge_with())["state"],
        "238/254 at 9371": check_judge(policy_with(9371), judge_with())["state"],
    }


def s04_gitlab_missing_risk() -> dict:
    held = summarize(
        cli(
            "evaluate-fixture",
            {
                "binding": fixture("gitlab-binding.json"),
                "fixture": fixture("gitlab-missing-risk.json"),
            },
        )
    )
    control = fixture("gitlab-missing-risk.json")
    control["observation"]["review"]["risk_score"] = 1
    with_risk = summarize(
        cli(
            "evaluate-fixture",
            {"binding": fixture("gitlab-binding.json"), "fixture": control},
        )
    )
    return {
        "missing_risk": held,
        "control_with_risk": {
            "decision": with_risk["decision"],
            "policy_sha256": with_risk["policy_sha256"],
        },
    }


def s05_osps_requirement() -> dict:
    cases = load("github-checks.json")["cases"]
    shared = assess("quality-policy-9000.json")["decision"]
    out = {"shared_required_checks_and_quality": shared, "cases": {}}
    for name, case in cases.items():
        result = osps_qa_03_01(case)
        out["cases"][name] = {
            "requirement": result,
            "composed": compose(shared, result),
        }
    return out


def s06_judge_evidence_unknown() -> dict:
    policy = fixture("quality-policy-9000.json")
    malformed = json.dumps(fixture("judge-238-of-254.json"))[:-1] + ', "passed": 254}'
    cases = {
        "missing": None,
        "malformed-duplicate-key": malformed,
        "stale-snapshot": judge_with(
            window_start="2025-10-19T00:00:00Z",
            window_end="2026-10-19T00:00:00Z",
            collected_at="2026-10-19T00:00:00Z",
            latest_score_at="2026-10-18T12:00:00Z",
        ),
        "stale-scores": judge_with(latest_score_at="2026-10-01T00:00:00Z"),
        "insufficient-samples": judge_with(passed=99, total=99),
        "empty-population": judge_with(passed=0, total=0),
        "incomplete-population": judge_with(complete=False),
        "invalid-scores-present": judge_with(invalid=3),
        "other-source": judge_with(source_id="synthetic.other-source"),
        "claims-authorization": judge_with(authorization="merge"),
    }
    out = {}
    for name, observation in cases.items():
        r = check_judge(policy, observation)
        out[name] = r.get("rejected") or f"{r['state']}:{r['reason']}"
    return out


def s07_subject_and_trust() -> dict:
    base = fixture("github-candidate.json")
    head_mismatch = copy.deepcopy(base)
    head_mismatch["subject"]["head_sha"] = "d4" * 20
    other_binding = copy.deepcopy(base)
    other_binding["subject"]["binding_sha256"] = fixture("gitlab-missing-risk.json")[
        "observation"
    ]["subject"]["binding_sha256"]
    other_binding["publication"]["subject"] = other_binding["subject"]
    untrusted = copy.deepcopy(base)
    untrusted["source_kind"] = "synthetic-fixture"
    stale = copy.deepcopy(base)
    stale["collected_at"] = "2026-10-19T23:50:00Z"
    out = {}
    for name, value in {
        "head-mismatch": head_mismatch,
        "bound-to-other-binding": other_binding,
        "untrusted-source-kind": untrusted,
        "stale-observation": stale,
    }.items():
        r = assess("quality-policy-9000.json", observation=value)
        out[name] = {
            "decision": r["decision"],
            "detail": r.get("rejected")
            or {
                k: v
                for k, v in r["candidate"]["assessments"].items()
                if not v.startswith("passed:")
            },
        }
    return out


def s08_writer_authority() -> dict:
    doc = load("writer-authority.json")
    eligible = assess("quality-policy-9000.json")
    held = assess("quality-policy-9900.json")
    out = {}
    for name, case in doc["cases"].items():
        writer = RecordingWriter()
        assessment = eligible if case["assessment"] == "eligible" else held
        allowed, reason = writer_gate(
            case["mode"], case["authority"], assessment, doc["evaluation_time"]
        )
        if allowed:
            writer.request_queue_enrollment(assessment["candidate"]["subject_head"])
        out[name] = {
            "gate": reason,
            "mock_calls": len(writer.calls),
            "expected_calls": int(case["expect_write"]),
        }
    return out


def s09_distinct_subjects() -> dict:
    candidate = fixture("github-candidate.json")
    merge_group = copy.deepcopy(candidate)
    merge_group["subject"]["head_sha"] = MERGE_GROUP_HEAD
    reused = assess("quality-policy-9000.json", observation=merge_group)
    sources = json.loads((ROOT / "evidence" / "sources.json").read_text())["subjects"]
    return {
        "synthetic_heads_distinct": candidate["subject"]["head_sha"]
        != MERGE_GROUP_HEAD,
        "candidate_evidence_reused_for_merge_group": reused["decision"],
        "historical_reviewed_head_differs_from_merge_group": sources["reviewed_head"]
        != sources["merge_group_head"],
        "historical_merge_commit_is_merge_group_head": sources["merge_commit"]
        == sources["merge_group_head"],
    }


SCENARIOS = {
    "S01 clean candidate + 238/254 at 99% -> hold": (
        s01_quality_99_hold,
        {
            "decision": "hold",
            "candidate": {"decision": "eligible"},
            "quality": {
                "state": "failed",
                "reason": "judge_approval_rate_below_threshold",
                "passed": 238,
                "total": 254,
            },
        },
    ),
    "S02 same inputs at 90% -> eligible, no mutation": (
        s02_quality_90_eligible,
        {
            "decision": "eligible",
            "authorization": "none",
            "mutation_permitted": False,
            "quality": {"state": "passed"},
            "writer": {"gate": "mode_shadow_no_write", "calls": 0},
        },
    ),
    "S03 integer threshold boundary": (
        s03_integer_boundary,
        {
            "225/250 at 9000": "passed",
            "224/250 at 9000": "failed",
            "99/100 at 9900": "passed",
            "98/100 at 9900": "failed",
            "238/254 at 9370": "passed",
            "238/254 at 9371": "failed",
        },
    ),
    "S04 GitLab consumer missing risk -> hold": (
        s04_gitlab_missing_risk,
        {
            "missing_risk": {
                "decision": "hold",
                "assessments": {
                    "OWNER-SCOPE": "passed:satisfied_in_synthetic_fixture",
                    "REVIEW-CLEAR": "unknown:risk_assessment_missing",
                    "CHECKS-PASS": "passed:satisfied_in_synthetic_fixture",
                    "EVIDENCE-CURRENT": "passed:satisfied_in_synthetic_fixture",
                    "PROTECTIONS-ACTIVE": "passed:satisfied_in_synthetic_fixture",
                },
            },
            "control_with_risk": {"decision": "eligible"},
        },
    ),
    "S05 OSPS-QA-03.01 observed checks": (
        s05_osps_requirement,
        {
            "shared_required_checks_and_quality": "eligible",
            "cases": {
                "required-green-optional-failed": {
                    "requirement": "Failed:observed_check_not_successful",
                    "composed": "hold",
                },
                "all-success": {
                    "requirement": "Passed:observed_checks_successful",
                    "composed": "eligible",
                },
                "pending": {
                    "requirement": "Failed:observed_check_not_successful",
                    "composed": "hold",
                },
                "neutral-rerun-does-not-clear-failure": {
                    "requirement": "Failed:observed_check_not_successful",
                    "composed": "hold",
                },
                "absent": {
                    "requirement": "Unknown:check_evidence_absent_or_incomplete",
                    "composed": "hold",
                },
                "incomplete-api": {
                    "requirement": "Unknown:check_evidence_absent_or_incomplete",
                    "composed": "hold",
                },
                "row-for-other-revision": {
                    "requirement": "Unknown:check_evidence_absent_or_incomplete",
                    "composed": "hold",
                },
                "queue-self-check-excluded": {
                    "requirement": "Passed:observed_checks_successful",
                    "composed": "eligible",
                },
                "queue-same-suite-other-app": {
                    "requirement": "Failed:observed_check_not_successful",
                    "composed": "hold",
                },
                "queue-run-not-merge-group": {
                    "requirement": "Unknown:check_evidence_absent_or_incomplete",
                    "composed": "hold",
                },
            },
        },
    ),
    "S06 missing/stale/insufficient/malformed judge evidence -> not passed": (
        s06_judge_evidence_unknown,
        {
            "missing": "input_unavailable",
            "malformed-duplicate-key": "invalid_json",
            "stale-snapshot": "unknown:judge_snapshot_stale_or_invalid",
            "stale-scores": "unknown:judge_scores_stale_or_invalid",
            "insufficient-samples": "unknown:judge_sample_insufficient",
            "empty-population": "unknown:judge_sample_insufficient",
            "incomplete-population": "unknown:judge_population_incomplete_or_invalid",
            "invalid-scores-present": "unknown:judge_population_incomplete_or_invalid",
            "other-source": "unknown:judge_source_mismatch",
            "claims-authorization": "unknown:judge_source_mismatch",
        },
    ),
    "S07 head mismatch or untrusted evidence -> hold": (
        s07_subject_and_trust,
        {
            "head-mismatch": {
                "decision": "hold",
                "detail": {
                    "CHECKS-PASS": "unknown:check_for_wrong_revision",
                    "EVIDENCE-CURRENT": "unknown:publication_binding_invalid",
                },
            },
            "bound-to-other-binding": {"decision": "hold"},
            "untrusted-source-kind": {
                "decision": "hold",
                "detail": "collector_observation_required",
            },
            "stale-observation": {"decision": "hold"},
        },
    ),
    "S08 shadow/absent/expired authority -> no writer call (mock)": (
        s08_writer_authority,
        {
            "shadow-with-valid-authority": {"mock_calls": 0},
            "off-with-valid-authority": {"mock_calls": 0},
            "enforce-without-authority": {"mock_calls": 0},
            "enforce-expired-authority": {"mock_calls": 0},
            "enforce-disabled-authority": {"mock_calls": 0},
            "enforce-valid-authority-held-assessment": {"mock_calls": 0},
            "enforce-valid-authority-eligible-positive-control": {"mock_calls": 1},
        },
    ),
    "S09 candidate and merge-group subjects stay distinct": (
        s09_distinct_subjects,
        {
            "synthetic_heads_distinct": True,
            "candidate_evidence_reused_for_merge_group": "hold",
            "historical_reviewed_head_differs_from_merge_group": True,
            "historical_merge_commit_is_merge_group_head": True,
        },
    ),
}


def matches(observed: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            k in observed and matches(observed[k], v) for k, v in expected.items()
        )
    return observed == expected


def run_all() -> dict:
    results = {}
    for name, (scenario, expected) in SCENARIOS.items():
        observed = scenario()
        results[name] = {"ok": matches(observed, expected), "observed": observed}
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--json", action="store_true", help="print full scenario observations as JSON"
    )
    args = parser.parse_args()
    first = run_all()
    second = run_all()
    deterministic = json.dumps(first, sort_keys=True) == json.dumps(
        second, sort_keys=True
    )
    if args.json:
        print(
            json.dumps(
                {
                    "evaluation_time": AT,
                    "shared_module": f"{SHARED_MODULE}@{SHARED_REVISION}",
                    "deterministic": deterministic,
                    "scenarios": first,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for name, result in first.items():
            print(f"{'PASS' if result['ok'] else 'FAIL'}  {name}")
        print(
            f"{'PASS' if deterministic else 'FAIL'}  S10 two runs at fixed time {AT} produce identical summaries"
        )
        print(
            f"Shared CLI: {SHARED_MODULE}@{SHARED_REVISION}. Synthetic inputs only; no network, credentials, model or writer."
        )
    return 0 if deterministic and all(r["ok"] for r in first.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
