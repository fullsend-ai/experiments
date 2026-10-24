# Results: Gemara-assessed auto-merge

Two kinds of results appear here and are kept apart:

- **Historical hosted observations** from the `fullsend-ai/auto-merge` lab, 2026-10-19 to 2026-10-23. Links were checked on 2026-10-24. Issue, PR and run pages can change, and Actions artifacts can expire or require a GitHub login. An artifact link is a locator, not an archive. Every source is listed in [evidence/sources.json](evidence/sources.json).
- **New local results** from the offline replay in this directory (2026-10-24, scenarios S01–S10). The replay uses invented fixtures and never claims to be a hosted or authenticated observation.

## A. Review evidence baseline

To be consumable by policy, ordinary Fullsend Review output needed four things: a *completed* review with an approval, the state of every finding, a risk assessment, and a binding to the exact head revision and trusted configuration the review used. [PR #50](https://github.com/fullsend-ai/auto-merge/pull/50) (merged 2026-10-19) and [PR #52](https://github.com/fullsend-ai/auto-merge/pull/52) (merged 2026-10-21) were preparatory changes that built this evidence path. They were not functional merge demonstrations.

Current-head CI and a completed AI review are separate evidence sources. They can refer to different revisions or arrive at different times. A green check does not imply a review of that head, and a review does not imply the checks ran on it. The shared `CHECKS-PASS` and `EVIDENCE-CURRENT` controls test them independently.

## B. Shared policy and the missing-risk hold

Shared candidate controls ([catalog](https://github.com/ascerra/fullsend-gemara-integration/blob/61a01465478e50d8e9b3e21dd056fdef90baff30/policy/catalog.json), [policy](https://github.com/ascerra/fullsend-gemara-integration/blob/61a01465478e50d8e9b3e21dd056fdef90baff30/policy/common.json)):

| Control | Requires |
| --- | --- |
| OWNER-SCOPE | Owner-approved paths and change kinds, open and ready, active owner grant |
| REVIEW-CLEAR | Completed approval, configured risk evidence present and acceptable, no unresolved findings |
| CHECKS-PASS | Each configured required check succeeded for this head |
| EVIDENCE-CURRENT | Project, head, target, policy, binding and publication agree; observations are fresh |
| PROTECTIONS-ACTIVE | Protected target, required gate, resolved discussions, no bypass, forge merge queue/train |

A review that looks clear but has no required risk assessment does not pass. The shared check returns Unknown with reason `risk_assessment_missing`, and the composed decision holds.

The [GitHub](https://github.com/ascerra/fullsend-gemara-integration/blob/61a01465478e50d8e9b3e21dd056fdef90baff30/examples/github/binding.json) and [GitLab](https://github.com/ascerra/fullsend-gemara-integration/blob/61a01465478e50d8e9b3e21dd056fdef90baff30/examples/gitlab/binding.json) binding examples use the same catalog and policy digests. Their evidence adapters are forge-specific: GitLab's target revision comes from a current target-branch lookup, and its protected mechanism is a merge train instead of a merge queue. The examples alone do not prove a live deployment.

Historically, the original GitLab consumer was expected to hold because its Review output lacked the required risk assessment. That deployment is private and is described here only generically. **The only public evidence for this case is the synthetic fixture.** No public live GitLab merge happened, and the GitHub and GitLab enforcement infrastructure was not identical.

Runner restrictions complicated running the pinned shared code in isolation. Controls around a pinned dependency, and keeping reader and writer credentials away from shared code, are consumer integration concerns. Controlling the shared repository does not make it safe to run its code beside credentials.

**Local replay S04:** a synthetic GitLab consumer with approval, no findings and a green required check, but `risk_score: null`, gives `REVIEW-CLEAR = unknown:risk_assessment_missing` and **hold**. The other four controls pass. The same fixture with `risk_score: 1` is eligible. Its policy digest equals the GitHub candidate's.

## C. Additional quality requirement: 99% holds

The external MLflow scorer is `review_correctly_approved`. The historical observation was **238 passing judgments out of 254 scored approvals = 93.7008…%**. At the owner's **99%** threshold (9900 basis points), the quality condition failed while all five candidate controls passed. Our composed decision (`AssessCandidate`: five controls AND quality) held, and the writer skipped protected-queue enrollment. Sources: [PR #53](https://github.com/fullsend-ai/auto-merge/pull/53) (still open, an unmerged hold demonstration), [evaluation run 39594830599](https://github.com/fullsend-ai/auto-merge/actions/runs/39594830599), [`shared-gate-assessment-1` artifact 12344096345](https://github.com/fullsend-ai/auto-merge/actions/runs/39594830599/artifacts/12344096345).

How the [public collector implementation](https://github.com/ascerra/fullsend-gemara-integration/blob/61a01465478e50d8e9b3e21dd056fdef90baff30/scripts/collect_mlflow_judge.py) works:

- It aggregates read-only metadata only. It never fetches trace artifacts, runs a model or writes feedback.
- The scorer, source, experiment and window are fixed by trusted configuration.
- Pagination is bounded. Population checks run two scans that must agree, and duplicate traces abort collection.
- It counts exactly one valid binary assessment per completed trace from the configured source.
- Freshness and minimum-sample requirements are enforced downstream by `check-judge`.
- Only counts, timestamps and a records digest leave memory.

Neither Gemara nor this reproduction invokes a model. The fixture [judge-238-of-254.json](fixtures/judge-238-of-254.json) reuses the historical counts with the invented source `synthetic.not-an-mlflow-export`. It is **not** an authenticated export of the private MLflow service.

**Local replay S01:** clean candidate + 238/254 at 9900 bp → quality `failed:judge_approval_rate_below_threshold`, candidate eligible, composed **hold**.

## D. Owner changes the threshold to 90%

A separate policy file, [quality-policy-9000.json](fixtures/quality-policy-9000.json), sets 9000 bp. The 9900 file remains for comparison. With the same 238/254 observation, quality passes. The lower threshold does not improve review quality, and it cannot override any other failing requirement.

[PR #56](https://github.com/fullsend-ai/auto-merge/pull/56) (merged 2026-10-21 17:16:46 UTC) was the earlier 90% case. [PR #54](https://github.com/fullsend-ai/auto-merge/pull/54) is still open. **PR #54 is not the successful merged example.** The complete later trial is issue #57 → PR #58 (section F).

**Local replay S02:** quality `passed`, decision **eligible**, `authorization: "none"`, `mutation_permitted: false`. The mock writer gate in shadow mode makes **0** calls.
**S03 (integer boundary):** 225/250 at 9000 passes and 224/250 fails. 99/100 at 9900 passes and 98/100 fails. 238/254 passes at 9370 but fails at 9371, even though a dashboard rounding 93.70% to one decimal would show "93.7%" for both. The comparison is `passed × 10000 ≥ total × bp` in integers.

## E. Adding one maintained OpenSSF requirement

The mapping, step by step:

1. Select `OSPS-QA-03.01` from pinned OpenSSF [`OSPS-QA.yaml`](https://github.com/ossf/security-baseline/blob/a26a7963f6fd098c1e82829322ec9e1196a4f294/baseline/OSPS-QA.yaml#L84-L101) (release v2026.08.28, parent control `OSPS-QA-03`). The lab [pinned](https://github.com/fullsend-ai/auto-merge/blob/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71/gemara-auto-merge/upstream/osps-baseline/source.json) the original YAML and license unchanged, with SHA-256 digests.
2. Our [catalog wrapper](https://github.com/fullsend-ai/auto-merge/blob/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71/gemara-auto-merge/upstream/osps-baseline/catalog.json) selects the parent control and requirement without rewriting their text. Our [policy](https://github.com/fullsend-ai/auto-merge/blob/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71/gemara-auto-merge/upstream/osps-baseline/policy.json) maps it to the required evaluation method `all-checks-passed`.
3. Our [GitHub adapter](https://github.com/fullsend-ai/auto-merge/blob/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71/gemara-auto-merge/configured_policy.py#L51-L123) reads exact-revision check runs and commit statuses, including optional ones. Required-check enforcement continues independently.
4. Our [native step](https://github.com/fullsend-ai/auto-merge/blob/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71/gemara-auto-merge/native-evaluator/policy_assessment.go) passes the observation to the Gemara SDK. The native evaluation log names the upstream requirement and its result.
5. Our composed decision and the existing writer require that result together with all other conditions.

Adapter semantics, from the implementation:

- The latest run per (app, name) counts, so a successful rerun supersedes a failure.
- A completed `neutral` or `skipped` run is not pass/fail evidence. It does **not** clear an earlier failure.
- A pending run is not a success.
- The latest status per context counts.
- Incomplete API reads, rows for another revision, or no evidence at all → no pass.
- At queue time, only the evaluator's own in-flight check suite (GitHub Actions app, validated `merge_group` run on the same revision) is excluded. GitHub still requires that gate to finish before merging.

The lab supports no automatic manual-bypass exception, which is stricter than the upstream allowance for explicit manual bypass. It is not "every GitHub check must say success". Passing this one requirement does not mean meeting the whole baseline or any full maturity level.

**Local replay S05:** with shared required checks and quality eligible, the replay gives:

| Case | Requirement | Composed |
| --- | --- | --- |
| Required green, optional failed | Failed | hold |
| All relevant succeeded (rerun, neutral and skipped included) | Passed | eligible |
| Pending optional check | Failed | hold |
| Neutral rerun after a failure | Failed | hold |
| No evidence / incomplete API / row for other revision | Unknown | hold |
| Queue: own check suite excluded | Passed | eligible |
| Queue: same suite but other app | Failed | hold |
| Queue: run is not a `merge_group` run | Unknown | hold |

This is a replay model of the adapter. The code was not imported, because the lab repository publishes no license.

## F. Complete protected merge and post-trial cleanup

User-visible evidence, in order:

1. [Issue #57](https://github.com/fullsend-ai/auto-merge/issues/57) asks for the documentation behavior, and [PR #58](https://github.com/fullsend-ai/auto-merge/pull/58) implements it. (Issue #57 was still open when observed on 2026-10-24.)
2. [Fullsend Review run 39955761534](https://github.com/fullsend-ai/auto-merge/actions/runs/39955761534) completed for head `14499514434b02c4b2563cd0e50aec225b77fa86` against trusted configuration `5f4f8f39ff196d815866396e6f05ebe6aff6e7a9`: approval, no unresolved findings, low risk. Artifact: [`fullsend-review-evidence-1` 12502054995](https://github.com/fullsend-ai/auto-merge/actions/runs/39955761534/artifacts/12502054995).
3. [Enrollment run 39956959534](https://github.com/fullsend-ai/auto-merge/actions/runs/39956959534) found the five shared conditions, 90% quality and OSPS-QA-03.01 all passed. Artifacts: [`shared-gate-assessment-1` 12502977284](https://github.com/fullsend-ai/auto-merge/actions/runs/39956959534/artifacts/12502977284) and native enrollment/OpenSSF [`gemara-evaluation-evaluate-1` 12503645276](https://github.com/fullsend-ai/auto-merge/actions/runs/39956959534/artifacts/12503645276).
4. The separate trusted App writer revalidated, then requested protected-queue enrollment: [job 120426280311](https://github.com/fullsend-ai/auto-merge/actions/runs/39956959534/job/120426280311) `enqueue / writer`, artifact [`gemara-evaluation-writer-1` 12503242005](https://github.com/fullsend-ai/auto-merge/actions/runs/39956959534/artifacts/12503242005). The PR timeline records `gemara-auto-merge-pilot-lab[bot]` adding the PR to the merge queue at **12:58:50 UTC**. The lab observed token revocation afterward; the public timeline does not show it.
5. [Merge-group evaluation run 39957499141](https://github.com/fullsend-ai/auto-merge/actions/runs/39957499141) (artifact [`gemara-evaluation-gate-1` 12503845545](https://github.com/fullsend-ai/auto-merge/actions/runs/39957499141/artifacts/12503845545)) and [CI 39957499387](https://github.com/fullsend-ai/auto-merge/actions/runs/39957499387) ran on the combined revision `fee00797…`. The reviewed PR head was not treated as equivalent to the merged result. OSPS-QA-03.01 passed at both enrollment and queue validation.
6. GitHub's merge queue performed the merge on **2026-10-23 at 13:03:51 UTC**, commit [`fee00797c19a07a2e3bdd83ce7fd1dbc917087f1`](https://github.com/fullsend-ai/auto-merge/commit/fee00797c19a07a2e3bdd83ce7fd1dbc917087f1). The timeline attributes the `merged` event to the App account that enqueued the PR, and records `github-merge-queue[bot]` removing it from the queue at the same second. Gemara did not merge anything. The bounded lab authority allowed this one trial; the broader production-readiness assessment still held.
7. Cleanup commit [`4c86073e…`](https://github.com/fullsend-ai/auto-merge/commit/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71) returned the configuration to shadow mode and disabled grants. [Final CI 39958588002](https://github.com/fullsend-ai/auto-merge/actions/runs/39958588002) passed. The lab's historical protection comparison recorded an exact restoration. Today's rules page cannot prove that historical state.

Earlier setup deployments used separately approved, temporary admin bypasses, each followed by restoration. The demonstration PR itself went through the protected queue. Reproduction requires no bypass, and none is described here.

**Local replay S08 (mock):** a writer gate makes 0 calls in these cases: shadow mode, off mode, enforce with no authority, enforce with expired or disabled authority, and enforce with a held assessment. A positive control (enforce + active authority + eligible) records exactly one mock call, so the test is not vacuous. **S09:** this is an internal-consistency check. Moving only the subject to the merge-group head, while the publication and checks still name the candidate head, holds (CHECKS-PASS: check for wrong revision; EVIDENCE-CURRENT: publication binding invalid). Relabelling the candidate evidence consistently (subject, publication and checks) is **eligible**: the shared CLI cannot tell relabelled evidence from a fresh merge-group observation, so keeping the subjects distinct depends on the collector observing the merge-group revision itself. The historical reviewed head differs from the merge-group head, which equals the merge commit. **S07:** each case asserts exit code 2 and the specific reason. A head mismatch holds on CHECKS-PASS and EVIDENCE-CURRENT. Evidence bound to another binding holds every control as wrong subject or policy. A stale observation holds every control as stale or future evidence. A non-collector `source_kind` is rejected as input. **S06:** missing, malformed, stale, under-sampled, empty, incomplete, other-source or authorization-claiming judge data → Unknown or rejected input. An empty population never counts as 100%.

## Failures and lessons

- **An unsigned contribution drew a DCO finding.** The branch was corrected, then fresh checks and a new review ran. The rejected revision was never treated as approved.
- **Pin and provenance mismatch.** The vendored runtime pin and the dispatcher's provenance disagreed, and each needed its own identity and pin. Success came from correcting provenance, not from weakening evidence validation.
- **Mixed concerns cause review friction.** Too much experiment authorization and history in a demo PR made it hard to review. Keep setup, owner scope and the demonstration issue distinct and readable.
- **A green job is not a pass.** A workflow job can succeed because *the observation completed* while the policy inside its artifact reports **hold**. Inspect the decision, not the icon.
- **Distinct outcomes.** These are all different things: schema-valid output, successful collection, candidate eligibility, owner authorization, queue enrollment, merge-group success, actual merge, and production qualification.

## Limits and unanswered questions

- **Threshold and scorer.** Neither the threshold's statistical validity nor the scorer's correctness was established, and nothing was compared with independent human labels.
- **Scored population.** Coverage of the scored population is unmeasured. The aggregate is experiment-wide and is not isolated by agent or rubric version.
- **93.70%** is a pass rate among scored approvals. It is not overall review accuracy, and it is not the probability that the next PR is safe.
- **One live merge.** One protected merge was observed, on GitHub only. Production rollout safety and long-term availability are untested.
- **No comparison.** Whether this beats simpler native policy structures (rulesets, required checks, CODEOWNERS) was not compared.
- **Not a released feature.** The owner configuration surface is a local patch. `repos.yaml` handling was tested locally only; no live managed GitLab installation exercised it.
- **Replay models.** The offline OSPS and writer-gate parts replay documented behavior. They are not the lab's code, which is unlicensed.
