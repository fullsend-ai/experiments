# Ownership and maintenance

## Who owns what

| Party | Owns | Must not |
| --- | --- | --- |
| **Gemara upstream** ([schema](https://github.com/gemaraproj/gemara/tree/9d36c253484d14922010252bfffe58bdcd49a144), [Go SDK](https://github.com/gemaraproj/go-gemara/tree/5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2)) | Schemas and model (1.5.0); SDK assessment and evaluation-log machinery | Be credited with running judges, authenticating evidence, minting tokens, granting authority or merging |
| **OpenSSF upstream** ([OSPS-QA-03.01](https://github.com/ossf/security-baseline/blob/a26a7963f6fd098c1e82829322ec9e1196a4f294/baseline/OSPS-QA.yaml#L84-L101)) | Requirement content, applicability, release cadence, license | Be treated as a GitHub scanner. It is content |
| **Shared module** ([fullsend-gemara-integration](https://github.com/ascerra/fullsend-gemara-integration/tree/61a01465478e50d8e9b3e21dd056fdef90baff30), Apache-2.0) | Common catalog and policies, deterministic evaluators, judge check, CLI, normalized types, synthetic examples, read-only MLflow collector, SDK/schema pins ([adoption guide](https://github.com/ascerra/fullsend-gemara-integration/blob/61a01465478e50d8e9b3e21dd056fdef90baff30/docs/ADOPTION.md)) | Hold write credentials, publish decisions or merge |
| **Consumer repository** ([auto-merge](https://github.com/fullsend-ai/auto-merge/tree/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71)) | Trusted source pins; forge identity; current PR/base/merge-group subject; evidence publishers and collectors; owner scope; quality threshold, window and freshness; selected optional controls; credential boundary | Load policy or thresholds from the candidate branch; run shared code beside reader or writer credentials |
| **Existing writer and forge** (GitHub App, merge queue, rulesets) | Revalidation, short-lived repository-scoped token, protected enrollment, combined-revision CI and assessment, the merge itself | Accept an eligibility report as authority |

## Version pins

| Item | Pin | Where it is pinned |
| --- | --- | --- |
| Shared module | `61a01465478e50d8e9b3e21dd056fdef90baff30` | Consumer source pin; this experiment's `scripts/reproduce.sh` and `scripts/scenarios.py` |
| Gemara Go SDK | `5e33fda460a80ffa99e9efbe19afb43e7d4c4dd2` (`v0.11.1-0.20261009030221-5e33fda460a8`) | Shared `go.mod` / `go.sum` |
| Gemara schema | `9d36c253484d14922010252bfffe58bdcd49a144` (1.5.0) | Shared `schema-toolchain.json`; consumer [toolchain lock](https://github.com/fullsend-ai/auto-merge/blob/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71/gemara-auto-merge/toolchain-lock.json) |
| OSPS baseline | release `v2026.08.28`, commit `a26a7963f6fd098c1e82829322ec9e1196a4f294` | Consumer [source.json](https://github.com/fullsend-ai/auto-merge/blob/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71/gemara-auto-merge/upstream/osps-baseline/source.json) with SHA-256 of the YAML, wrapper and policy |
| Local Fullsend build | vendored binary, SHA-256 checked | Consumer [local-build.json](https://github.com/fullsend-ai/auto-merge/blob/4c86073ea6e05aff69b22b261eb7e2c74f3a5f71/.fullsend/local-build.json) |

## Update procedure

1. **Upstream release.** For a new Gemara SDK or schema, or a new OSPS release, update the pin in the owning repository (shared module or consumer) in a reviewed PR that touches nothing else. Re-verify digests and licenses. Rerun the shared tests and optional schema validation.
2. **Shared module change.** Merge it in the shared repository, then bump the consumer's source pin in a separate consumer PR. A consumer PR must never be able to change the policy that authorizes it, so pin bumps go through the protected path and are evaluated by the *base* configuration.
3. **Consumer threshold or control change.** This is an owner PR on the consumer, which is a governed path. Keep the old configuration inspectable, as the 9900 and 9000 files are here.
4. **Re-establish authority.** Grants expire, and `enforce` cannot renew them. A new trial needs a fresh, bounded owner grant and must then return to shadow mode.
5. **Updating this experiment.** Change `SHARED_REVISION` in `scripts/scenarios.py` and `revision` in `scripts/reproduce.sh` together, rerun `scripts/reproduce.sh`, and report any changed outcome as a new local result.

## Measured footprint

These line counts are as reported by the lab. They are physical lines of owned files at the referenced revisions and include comments and blank lines. Retained utilities count, and dependencies do not. Historical revisions are excluded. They are **neither a minimum adoption cost nor engineering time saved**.

| Component | Source / tooling | Tests | Policy / config / CI |
| --- | ---: | ---: | ---: |
| Shared module | 1,726 | 960 | 619 |
| auto-merge consumer | 7,215 | 5,157 | 2,649 |
| Local Fullsend patch | +190 / −6 | +170 | — |

**OSPS-specific dedicated files: 454 physical lines.** That is a 165-line adapter, 132 lines of policy and pin, and 157 lines of tests, not counting the generic machinery they reuse. Adding the requirement still meant writing and maintaining a trusted adapter, a mapping and tests.

The consumer is about four times the size of the shared module. Most of the consumer cost sits in evidence collection, authentication, the writer and queue reconciliation. Shared policy did not remove that work.

## This experiment's own maintenance

This directory pins the shared CLI and copies no upstream code. If the pinned module becomes unavailable from the Go module proxy, the offline replay cannot be set up. The historical record in `RESULTS.md` and `evidence/sources.json` stays readable. Hosted links may expire.
