---
title: "28. Code agent on feature-scale epics, graded without reference solutions"
status: Active
topics:
  - evaluation
  - code-agent
---

# 28. Code agent on feature-scale epics, graded without reference solutions

Date: 2026-09-26 (first results); 2026-10-15 (rerun with the review step as
deployed and sandboxed tests; experiment continues)
Authors: Bill Murdock, with Claude Code
Tracks Jira AISDLC-5. Builds on [0006](../0006-code-agent-evaluation/) (the
first code-agent evaluation, 20 synthetic bug-fix scenarios) and
[0026](../0026-eval-statistical-significance/) (how many trials a comparison
needs). The runnable eval lives in `fullsend-ai/agents` under
`eval/local/code-rhai/` (proposed in a pull request from this work; see Related).

## Hypothesis

The production code agent can be measured on real, feature-scale work, the
epics an engineering organisation actually hands it, without anyone writing
reference solutions or hidden tests. The measurement should be grounded in
what the repository itself can confirm (an outcome class, the repository's
own tests on the result, the review agent's findings) and in a judged quality
score that different judges agree on, so that a later comparison between
agent configurations has something trustworthy to stand on.

Secondary questions: how the unmodified agent compares with a cheaper model
on the same work, and whether the agent's own review step is useful evidence
for a model judge.

## What we learned

Five cases, one run per arm, so every observation after the first is a
direction the data is consistent with, not a conclusion. Details and tables
are in Current results.

1. **The measurement works.** Real epics, no reference solutions, no hidden
   tests, and every run still yields an outcome class, a test result, a
   review and a score. The October rerun completed ten runs across two arms
   without an infrastructure failure.
2. **The data so far does not separate strong models on quality.** Opus 4.6,
   Opus 5, GLM 5.3 and Luna all score 3 to 4 out of 5 on nearly every case:
   the work is done, with issues a maintainer would fix in review, and rarely
   mergeable as is. Arm means differ by at most 0.6, and GLM 5.3 sits within
   0.2 of Opus 5 under two judges. The sample is far too small to call them
   equal; it is large enough to say the quality score is not where these
   models differ on this work.
3. **Where they differ is behaviour.** Luna declined two epics every time
   because the repository's rules asked for an assignee first, where the
   Claude models implemented them. GLM wrote ten times the code Opus did on
   the largest case and took four times as long. Opus 4.6 twice shipped a
   monorepo PR that did not install because of a lockfile convention. These
   show up only because the eval classifies declines separately from failures
   and keeps every artifact; whether they generalise needs more cases.
4. **Judges agree closely, and cheaper judges look usable.** Across five judge
   models, PR scores never differ by more than a point, and the one two-point
   split was an ambiguous prompt. GLM 5.3 as a judge matched Opus 5 exactly on
   six of ten verdicts here and twenty of twenty-six across both datasets.
   Consistent with cheap judging at scale; not yet proof of it.
5. **Cost has two shapes.** Today, with GLM free on early access, a GLM-arm
   case costs $5 to $10 for review and judging and nothing for the coder,
   against $12 to $30 for an Opus 5 case. If GLM is later billed at roughly
   GPT-6.1 Sol's rate ($2 per million input, $0.20 cached, $10 output), the
   five coder runs would have cost about $18, $11 of it on the largest case,
   against $42 for Opus 5. The review step, $3 to $10 per case with the
   deployed persona set, is the floor of the per-case cost either way.
6. **Not learned.** Whether the deployed agent on Opus 5.5 differs from the
   Opus 5 stand-in. Whether the review evidence improves the judge. Anything
   about run-to-run variance.

One lesson is about the method rather than the agents: the judge could reach
live GitHub, the review's sub-agents failed silently, and the repository tests
ran on the laptop until each was checked. Every component that runs an agent
needs its behaviour verified against what actually ran, not what the config
says. Limitations has the details.

## Approach

**Cases are recipe cards, not bundles.** A case is an epic from a public
Red Hat AI repository, given to the agent verbatim as a GitHub issue carrying
the `ready-to-code` label, against the repository as it was just before the
humans' first accepted PR for that epic (or the default-branch tip if none
has merged). The card records the upstream repository, the snapshot commit
and the rule that chose it, the human PRs (used only to pick the snapshot,
never shown to the agent or the judge), and the repository's own test
command. The repository tree is rebuilt from the card at run time and never
committed. Five cases were built from the September 2026 epic sample:

| Case | Epic | Repository | Language |
|---|---|---|---|
| 001 | RHAI-517 capability manifest endpoint | trustyai-explainability/nemo-guardrails | Python |
| 002 | RHAI-331 deprecate legacy checks | trustyai-explainability/nemo-guardrails | Python |
| 003 | RHAI-284 pod- and model-level dashboard panels | opendatahub-io/kserve | YAML/Go |
| 004 | RHAI-369 Konflux onboarding for a component | opendatahub-io/odh-dashboard | TypeScript/Dockerfile |
| 005 | RHAI-503 Data Connect Hub views | opendatahub-io/odh-dashboard | TypeScript |

**Grading has no reference.** Each run is classified first: `pr` (the agent
opened a PR), `declined` (it stopped and said why), or `failed`. Deterministic
judges then check that the repository's own tests still pass on the PR head
and that fullsend's review agent ran. A tool-using model judge reads the task,
the diff, the PR write-up, the test result, the review agent's findings and a
checkout of the PR head, and scores 1 to 5 against the task's acceptance
criteria. A decline is scored separately on whether its stated reason holds
up against the task and the repository. Every artifact is kept so a different
judge can re-score later without re-running agents.

**Two arms, same pipeline.** In the September and early-October runs, arm 1
was the code agent as the fleet then ran it (Claude Code runtime, Opus 4.6,
effort high) and arm 2 swapped only the model and runtime (pi runtime, GPT-6
Luna, effort high). In the October 14/15 rerun the arms are GLM 5.3 at effort
high on pi, served by Red Hat's EnMaaS gateway, and Opus 5 on Claude Code,
the closest stand-in for the Opus 5.5 the fleet moved to on October 2 that a
developer's Vertex project can serve. The review step is fullsend's review
agent, held constant across arms (see "The review step" below). The judge is
the same model for both arms.

**The review step.** The review agent is a parent plus nine persona
sub-agents, and what it runs on is decided by the fullsend configuration the
eval runs under, not by the eval. In the September and early-October runs it
ran in its Claude Code form: an Opus 4.6 parent dispatching Claude sub-agents
(Opus 4.6 and Sonnet 4.6). That is the review harness's default, what a
repository with no review entry in its own fullsend config gets; the agents
repository's own deployed review was by then already on the pi runtime with a
GPT-6.1 Sol parent and GPT and Gemini personas. On October 6 it moved to a
Sonnet 5.5 parent, an Opus 5.5 challenger, GPT-6.1 Sol for correctness and
security and Gemini 3.8 Flash for docs and style, and that is the
configuration the rerun uses, with one deviation: the Claude aliases are
pinned to Sonnet 5 and Opus 5, because the Vertex project the runs use does
not serve the 5.5 generation. Each run's `review-metrics.json` records the
models that actually answered, per persona.

**Repository tests run in a sandbox.** From the rerun on, the repository's
own test command runs on the PR head inside a throwaway OpenShell sandbox
built from the coder's image, with only the package registries reachable,
rather than on the host that runs the eval. Earlier runs ran it on the host.

## Current results

### GLM 5.3 vs Opus 5 with the review as deployed and sandboxed tests (2026-10-14/15)

Both arms ran overnight on the same five cards, back to back, with the review
step configured as the agents repository configures it (above) and the repo
tests in the sandbox. Judge: Opus 5, confined, one sample per case, then GLM
5.3 (codex runner via EnMaaS) over the same artifacts.

| Case | GLM 5.3 high (pi) | Opus 5 high (Claude Code) |
|---|---|---|
| 001 | PR, 80 turns, 23 min, +603, tests pass, quality 4 / 4 | PR, 99 turns, 18 min, +961/-1, tests pass, quality 4 / 3 |
| 002 | PR, 100 turns, 20 min, +332/-1106, tests pass, quality 3 / 3 | PR, 74 turns, 13 min, +355/-1028, tests pass, quality 3 / 4 |
| 003 | PR, 58 turns, 14 min, +508/-102, checks pass, quality 3 / 3 | PR, 57 turns, 13 min, +491/-95, checks pass, quality 4 / 4 |
| 004 | PR, 64 turns, 13 min, +180, tests pass, quality 4 / 3 | PR, 44 turns, 7 min, +177, tests pass, quality 4 / 3 |
| 005 | PR, 309 turns, 82 min, +24541 in 90 files, tests pass, quality 3 / 3 | PR, 153 turns, 20 min, +2234 in 44 files, tests pass, quality 3 / 3 |

Quality is "Opus 5 judge / GLM judge". Means: GLM arm 3.40 / 3.20, Opus 5
arm 3.60 / 3.40. The two judges agree exactly on six of the ten PRs and are
one point apart on the rest, and both rank the arms the same way. Every PR
passed the repository's own tests in the sandbox, and the review ran with the
full persona set on all ten PRs: one Opus 5 challenger call, three or four
Sonnet 5 persona calls, two GPT-6.1 Sol calls and two or three Gemini calls
each.

Wall clock: the GLM arm took 5 h 5 min for the five cases, the Opus 5 arm
3 h 25 min, each including review and judging. On the coder alone Opus 5 was
about twice as fast overall, and the gap is almost entirely case 005, where
GLM spent 82 minutes writing a 24,500-line scaffold across 90 files and Opus
20 minutes on 2,200 lines across 44; on the other four cases the coders were
within seven minutes of each other. Spend: the GLM arm $37 (coder free on
EnMaaS; reviews $27, judging $10), the Opus 5 arm $74 (coders $42, reviews
$24, judging $8); the GLM judge was free. The review step with the deployed
persona set costs $3 to $10 per case on PRs of this size.

Against the earlier Opus 4.6 arm (mean 3.0 from the confined judge) both arms
score higher, but the comparison is not clean: the review evidence and the
test environment both changed between the runs, and one run per cell cannot
separate model from noise. Within the rerun, where everything else is held
constant, the two arms are close: under the Opus 5 judge the free coder ties
on four of five cases and is one point lower on the fifth.

### What the judge comparisons established

These findings come from re-scoring the artifacts of the earlier runs (the
runs themselves are superseded; their scores are in the appendix). The
findings about the judges stand, and the rerun above adds a fifth judge, GLM
5.3, to the comparison.

**PRs.** Every judge is within one point of every other on every PR. The
disagreements lean one way: the stronger judges rate Luna's PRs higher
(Luna mean 3.67 to 4.0 against 2.8 to 3.0 for Opus 4.6) and never disagree
by more than a point. Judge choice changes the gap between arms, not the
ranking of individual artifacts. Sonnet 5 matches Opus 5.5 exactly on six
of eight PRs and is a viable cheaper judge for `pr_quality`.

**Declines, and the prompt.** The two Luna declines produced the only
two-point split of the exercise: Opus 5 and 5.5 gave 2, docking for the
proposal or plan the repository's rule itself asks for; Sonnet 5 gave 4,
reading the question as "was the stated reason legitimate" and stopping
there. That is a disagreement about what the question is, not about the
facts, so the prompt was rewritten to ask only two things: are the
decline's claims accurate, and is the verified reason a real blocker the
agent could not resolve (repository rules that forbid proceeding count).
What the agent did after stopping, the message's polish, and what another
agent would have done are declared out of scope. Under the new wording Opus
5 and Sonnet 5 agreed exactly on both declines (4 and 4 on 001; 3 and 3 on
002, before confinement). The two-point split was the prompt's ambiguity,
not the models.

**The judge was not confined.** While checking the Sonnet 5 verdicts, one
rationale quoted the title of the upstream repository's issue #1 and the
diff of an upstream pull request, neither of which was in the staged inputs.
The judge had run `gh issue view` and read GitHub. Probing the Claude Code
CLI showed why: a permissions allow list only pre-approves the listed tools,
and in headless mode the unlisted ones (Bash, WebFetch, WebSearch, Agent)
stay callable with no prompt. The harness built the judge's permissions
from the allow list alone, although its runner already knew how to pass a
deny list. So every Claude Code judge verdict in this experiment before the
confined re-judge could have consulted live GitHub, including the human PRs the
cards deliberately withhold; one visibly did, and the others cannot be
checked because judge transcripts are not kept. The issue lookup was also
wrong in context: Luna's "issue #1" was the private fixture issue, so the
judge penalised a mismatch it had created by looking in the wrong place.

Fix: a default deny list for Claude Code judges (Bash, WebFetch, WebSearch,
Agent), filed and proposed upstream (opendatahub-io/agent-eval-harness#239,
#240) and set explicitly in the eval. Re-judging all ten artifacts with Opus
5 under the deny list and the new decline prompt (about $15) flipped no
conclusion: PR scores within one point of every earlier judge, arm means
3.0 and 3.67, declines 4 and 4. One instructive shift: the 002 decline had
scored 3 from an unconfined Opus 5 an hour earlier under the same prompt,
because that judge fetched the upstream PR diff and could call Luna's claim
about it false; the confined judge, limited to the snapshot, could only call
it unsupported. Confinement changes what a judge can know, by design. The
judge keeps the full repository snapshot at the PR head, so it can check
claims against code and the project's own rules; any outside fact it must
verify now has to be on the card.

### Observations

- **Judges agree on PRs, and the stronger ones separate more.** The all-3s
  of the first Sol run were partly the work and partly the judge: on
  identical artifacts Opus 5, Opus 5.5 and Sonnet 5 found 4s that Sol did
  not, always in Luna's favour, while never disagreeing by more than a point
  across four judges and a confined re-judge. Judge choice changes the gap
  between arms, not the ranking of individual artifacts. The one two-point
  split, on declines, was the prompt's ambiguity and went away when the
  prompt said what to score.
- **A "read-only" judge was not.** The judge's allow list did not stop it
  reaching live GitHub, and one verdict shows it did. The eval now denies
  shell, network and sub-agent tools to its judges and the harness fix is
  proposed upstream; the reference verdicts are from the confined judge.
  Any judge that runs as an agent needs its isolation verified, not assumed.
- **One repo convention decided every early test failure.** In the
  September and October 6 runs both Claude models, on different days, added a
  workspace package to the odh-dashboard monorepo without regenerating
  `package-lock.json`, so `npm ci` refused to install. Luna did not. In the
  rerun both GLM 5.3 and Opus 5 got the lockfile right and all five PRs
  installed and passed. Repository-specific conventions of this kind are
  where "agent readiness" of a repo shows up in the numbers.
- **The review's sub-agents must be checked, not assumed.** Before the rerun
  the eval forced the review step onto a fixed model, and on a machine whose
  Vertex project lacked the models the persona files name, the persona
  sub-agents failed silently with zero tokens while the parent reviewed
  alone. That happened in a sister eval on this pipeline, not in the runs
  reported here, but it is why every run now records the models each
  persona actually answered on, and why the rerun's review is described
  above in terms of what ran rather than what was configured.
- **Reported costs can be wrong.** The pi runtime priced GPT-6 Luna at a
  Claude-tier rate, about 50 times its published price. Costs above were
  recomputed from token counts.
- **The review step is expensive relative to the coder** on these cases ($4
  to $6 per review in the early runs, $3 to $10 with the deployed persona
  set in the rerun, against $2 to $4.50 per Opus 4.6 implementation and $4
  to $19 per Opus 5 one). Whether the judge needs it is an open question
  worth a controlled test.
- **GLM 5.3 through EnMaaS is a usable arm.** Free to run, within 0.2 of
  Opus 5 under both judges, and all five PRs installed and passed tests. Its
  cost is time on the largest case, where it produced ten times the code.

## Limitations

One sample per case, one run per arm, five cases, one sample per judge.
Runs were made from a laptop against a personal cloud budget; nothing here
is a fleet measurement yet. Two of the five cases are from the same
repository. The September and October 6 baseline is the agents repository's
harness default of late August 2026 (Opus 4.6); the rerun's Opus 5 arm
stands in for the Opus 5.5 the fleet deploys since October 2, and the rerun's
review pins the Claude aliases one generation back for the same reason, so
neither arm is the deployed agent exactly. The review evidence differs
between the early runs (Claude Code form, Opus 4.6 parent) and the rerun (pi
persona ensemble, cross-vendor), and the repository tests moved from the host
to a sandbox, so scores across the two periods are not directly comparable. All judge
verdicts before the confined re-judge were produced by a judge that could
reach live GitHub; they are kept for the agreement comparison, but only the
confined column is treated as a measurement. Every verdict so far also saw
per-case author notes that have since been removed from the eval: on review
they restated the epic, described the human change, or were wrong in places.
The judge now gets the task text alone; the stored verdicts have not been
re-run without the notes.

## Conclusion

The pipeline measures the code agent on real, feature-scale work without
reference solutions, and the first results are summarised under What we
learned: the quality score does not yet separate strong models, behaviour
does, judges agree, and the cost of a case is set by the review step. What
the experiment lacks is sample size; the next steps are repeated runs per
0026 on the stored artifacts and cards, a second case set from 0006's twenty
scenarios, a controlled test of whether the review evidence helps the judge,
and then one treatment at a time (a minimal platform-contract-only agent as a
floor, and practices from epic-code-gen).

## Related

- fullsend-ai/agents#1622: `eval/local/code-rhai/` (pipeline, scripts, cards),
  including the sandboxed regression check and the review-step configuration
  described above.
- A separate experiment (forthcoming) covers the production-PR dataset built on
  the same pipeline: real fullsend PRs judged at first push and final state,
  the agent on the same issues, an effort-level sweep on GLM, and the Opus
  comparison on those cases.
- opendatahub-io/agent-eval-harness#239 and #240: the judge-confinement
  finding and its fix.
- fullsend-ai/fullsend#7748, a hardening note filed from this work.

## Appendix: outdated results

Kept for the record and for the judge-agreement comparison. None of these is
a current measurement of the agent.

### First look, 2026-09-25/26: Sonnet 4.6 vs Luna, five cases, different judges

**Why outdated:** a pipeline shake-down. The two arms were scored by different
judges (Opus 5 and GPT-6 Sol), the host slept for most of the night, the
review ran in its Claude Code default form, and the repository tests ran on
the host. Kept because it produced the Luna refusal and the first PR-quality
scores.

| Case | Sonnet 4.6 | Luna |
|---|---|---|
| 001 | PR, tests pass, quality 4/5 | declined (repo AGENTS.md), decline 4/5 |
| 002 | PR, tests pass (19 tests deleted), quality 3/5 | declined (unspecified sunset date), decline 4/5 |
| 003 | PR, checks pass, quality 3/5 | PR, checks pass, quality 3/5 |
| 004 | PR, tests pass, quality 3/5 | PR, tests pass, quality 3/5 |
| 005 | PR, tests fail (lockfile not regenerated), quality 2/5 | did not finish (infrastructure) |

### Opus 4.6 (fleet as-is) vs Luna, 2026-09-26 and 2026-10-06, five cases, one judge

**Why outdated:** three things changed after these runs. The fleet moved its
code agent from Opus 4.6 to Opus 5.5 on October 2, so this arm is no longer
the deployed agent. The review step ran in the harness's Claude Code default
form (Opus 4.6 parent, Claude sub-agents), not the pi persona ensemble the
agents repository deploys, so the review evidence the judge saw differs from
the rerun's. And the repository tests ran on the eval host rather than in a
sandbox. The GPT-6 Sol verdicts here were also made before the judge was
confined to its inputs and while per-case author notes were still shown to
it. The Luna arm was dropped in favour of GLM 5.3, which is free to run on
Red Hat's gateway.

Cases 001, 003, 004 on 09-26 and 002, 005 on 10-06, same configuration and
the same agent checkout throughout. Judge: GPT-6 Sol on the codex runner, one
sample per case. Reviewer: the production review agent on Claude Code, Opus
4.6 orchestrator, sub-agents on their configured tiers. "Fleet as-is" means
the agents repository's harness defaults; the fleet's own deployed
configuration has since moved to newer models, so this baseline is dated.

| Case | Opus 4.6 | Luna |
|---|---|---|
| 001 | PR, 95 turns, tests pass, 12 review findings, quality 3/5 | declined (same reason as before), 13 turns, decline 3/5 |
| 002 | PR, 62 turns, tests pass (21 test functions removed, 11 added), 22 findings, quality 3/5 | declined, 9 turns, decline 3/5 |
| 003 | PR, 54 turns, checks pass, 7 findings, quality 3/5 | PR, 53 turns, checks pass, 6 findings, quality 3/5 |
| 004 | PR, 76 turns, tests pass, 5 findings, quality 3/5 | PR, 29 turns, tests pass, 6 findings, quality 3/5 |
| 005 | PR, 248 turns, tests fail (lockfile not regenerated), 16 findings, quality 1/5 | PR, 172 turns, tests pass, 16 findings, quality 3/5 |

Totals under this judge: Opus 4.6 five PRs, quality 3, 3, 3, 3, 1 (mean
2.6), repo tests pass on 4 of 5; Luna three PRs at 3, 3, 3 (mean 3.0) with
tests passing on all three, plus two declines at 3. Cost at published rates:
Opus coder $29 for five cases; Luna coder about $0.50; the eight production
reviews $4 to $11 each ($55 total; the two largest PRs each drew a review
over $10); judging about $1 per verdict.

The reference verdicts for this experiment are not Sol's but the confined
Opus 5 judge's (last column of the four-judge table below): Opus 4.6 PRs
3, 3, 3, 4, 2 (mean 3.0); Luna PRs 4, 4, 3 (mean 3.67) and declines 4, 4.
Same ranking, slightly wider gap.

### Four judges on the ten artifacts of the Opus 4.6 vs Luna runs

**Why outdated:** the artifacts are those of the superseded runs above. The
table is kept as the evidence for the judge findings in Current results.

The stored artifacts were re-scored without re-running any agent, one sample
each: Opus 5 on the first six (Vertex, 10-06), Opus 5.5 on all ten (10-07,
via a gateway on the harness side), Sonnet 5 on all ten (Vertex, 10-07), and
finally Opus 5 again on all ten with the judge confined to its inputs and a
revised decline prompt (both explained under "What the judge comparisons
established" in Current results). The last column is the reference set.

| Artifact | GPT-6 Sol | Opus 5 | Opus 5.5 | Sonnet 5 | Opus 5, confined |
|---|---|---|---|---|---|
| Opus 4.6, 001 PR | 3 | 3 | 3 | 3 | 3 |
| Opus 4.6, 002 PR | 3 | - | 3 | 3 | 3 |
| Opus 4.6, 003 PR | 3 | 3 | 3 | 3 | 3 |
| Opus 4.6, 004 PR | 3 | 3 | 4 | 4 | 4 |
| Opus 4.6, 005 PR | 1 | - | 1 | 2 | 2 |
| Luna, 001 decline | 3 | 2 | 2 | 4 | 4* |
| Luna, 002 decline | 3 | - | 2 | 4 | 4* |
| Luna, 003 PR | 3 | 3 | 4 | 4 | 4 |
| Luna, 004 PR | 3 | 4 | 4 | 4 | 4 |
| Luna, 005 PR | 3 | - | 4 | 3 | 3 |

\* under the revised decline prompt; the first four columns use the original.

### Observations that no longer apply

- **Reproducible refusals, on both sides.** Luna declined RHAI-517 in every
  run (five of five) and RHAI-331 in every run (three of three), each time
  because the repository's `AGENTS.md` and `CONTRIBUTING.md` require an
  assignee and an agreed approach before non-trivial work, and for RHAI-331
  also because the epic leaves the deprecation sunset date to a pending
  product decision. Sonnet and Opus implemented both. On RHAI-331 Opus chose
  a sunset date itself, which the judge flagged as "asserted without
  evidence of the required PM decision". Under the final decline prompt the
  judges rate both declines 4: the stated reasons check out against the
  repository's rules, docked one point where a claim cannot be verified from
  the snapshot (RHAI-517's assignment state) or is unsupported (RHAI-331's
  description of an upstream PR). Under the original prompt the Opus judges
  also docked for leaving no proposal or plan behind, which the eval now
  treats as a separate question. Obedience versus initiative, visible from
  both sides because the outcome classification does not hide a decline as a
  failure.
- **Luna is cheap, and not worse here.** Roughly 60 times cheaper than Opus
  4.6 per case, with equal or better judge scores on the three cases both
  completed. Opus's extra turns did not buy quality on the largest case: 248
  turns produced a bigger scaffold that does not install, where Luna's 172
  turns passed the repo's tests. The sample is far too small to conclude
  anything; it sets the stake for the question.

The Luna observations describe an arm that is no longer run. The refusal
behaviour it showed (declining when the repository's contribution rules ask
for an assignee or an agreed approach) remains a real phenomenon the outcome
classification is designed to surface; GLM 5.3 and Opus 5 did not decline on
any of the five cases in the rerun.
