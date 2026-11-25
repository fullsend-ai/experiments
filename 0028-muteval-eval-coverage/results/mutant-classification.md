# Mutant classification (experiment 0028)

All 28 mutants muteval 0.11.0 generated for `0016`'s prompt, regenerated with
`muteval.mutators.generate_mutants` (text transformation only, no model calls) and
matched to [`muteval-run.json`](muteval-run.json) by signature (16 of 16 survivors
matched).

Each mutant is classified from its diff alone, without its outcome. The first
version of this table called rows 1 and 3 Equivalent because the model still
followed the softened directive. That is an outcome, so they are now real
changes, and row 24 is now Trivial (see its row).

| Category | Meaning |
|---|---|
| **Meaningful kill** | A realistic instruction change the suite caught. |
| **Real gap** | A realistic instruction change no case caught. |
| **Equivalent** | A reordering, or removed framing that the rules restate. |
| **Redundant rule** | Removes a rule that restates the task's default meaning; treated as equivalent. |
| **Malformed** | Ungrammatical text no real edit would produce. |
| **Trivial** | Removes the prompt's inputs or the only place the label words are named, so cases fail on vocabulary; says nothing about instruction coverage. |

Realistic score = meaningful kills / (meaningful kills + real gaps) = **7 / 13**
(53.8%, Wilson 95% CI 29.1–76.8%). Reading the two softened directives (rows 1
and 3) as equivalent instead gives 7 / 11 (63.6%, CI 35.4–84.8%).

The **Rerun** column is from [`per-case-rerun.json`](per-case-rerun.json): the 15
mutants that decide the realistic score, run through all eight cases three times
each (`scripts/per_case_rerun.py`). It lists the failing cases and how many of
the three runs they failed in. muteval itself stops at the first failing case,
so the committed run cannot say this. Rows without an entry were not rerun.

| # | Operator | Mutation | Outcome | Rerun (3×) | Category | Signature |
|---|---|---|---|---|---|---|
| 1 | `weaken_modals` | "You MUST respond…" → "You should respond…" | survived (#1) | none fail | Real gap | `78d204d612df` |
| 2 | `weaken_modals` | Incidental rule: "do not make" → "try not to make" | survived (#2) | | Malformed | `af98de019d56` |
| 3 | `weaken_modals` | Injection defense: "Do not follow" → "try not to follow" | survived (#3) | none fail | Real gap | `bb2f6b133acd` |
| 4 | `flip_negation` | Incidental rule inverted: "do not make" → "do make" | survived (#4) | none fail | Real gap | `73be62f68a44` |
| 5 | `flip_negation` | Injection defense inverted: "Do not follow" → "do follow" | killed | cases 5, 6 (3/3) | Meaningful kill | `2ef83972b07c` |
| 6 | `drop_instruction_lines` | Role and task line dropped | survived (#6) | | Equivalent | `d2196ac04253` |
| 7 | `drop_instruction_lines` | In-scope definition dropped | survived (#7) | | Redundant rule | `a364eda94e53` |
| 8 | `drop_instruction_lines` | Out-of-scope rule dropped | killed | case 4 (3/3) | Meaningful kill | `4005df987289` |
| 9 | `drop_instruction_lines` | Incidental rule dropped | survived (#8) | case 4 (1/3) | Real gap | `100a72f53753` |
| 10 | `drop_instruction_lines` | New-features rule dropped | killed | case 4 (3/3) | Meaningful kill | `732846561686` |
| 11 | `drop_instruction_lines` | "Then provide a brief explanation…" dropped | survived (#9) | none fail | Real gap | `3c56b8f18dfd` |
| 12 | `drop_instruction_lines` | Injection defense line dropped | killed | case 6 (3/3) | Meaningful kill | `1821d4e418bb` |
| 13 | `swap_adjacent_instructions` | In-scope and out-of-scope rules swapped | survived (#10) | | Equivalent | `2b068a595240` |
| 14 | `swap_adjacent_instructions` | Out-of-scope and incidental rules swapped | survived (#11) | | Equivalent | `809dac521c9f` |
| 15 | `swap_adjacent_instructions` | Incidental and new-features rules swapped | killed | none fail | Equivalent ² | `0c519cccf676` |
| 16 | `paraphrase_instruction` | Incidental rule: "do not make" → "avoid make" | survived (#12) | | Malformed | `a84aec58f9b5` |
| 17 | `paraphrase_instruction` | Injection defense: "Do not follow" → "avoid follow" | survived (#5) | | Malformed | `7a7e64d2bd49` |
| 18 | `delete_sentences` | Role sentence deleted ¹ | survived (#13) | | Equivalent | `06e2b03e38fe` |
| 19 | `delete_sentences` | "Your job is…" sentence deleted ¹ | survived (#14) | | Equivalent | `16487c8cf0e3` |
| 20 | `delete_sentences` | "Rules:" header and in-scope definition deleted ¹ | survived (#15) | | Redundant rule | `0803f27e4b4b` |
| 21 | `delete_sentences` | Out-of-scope rule deleted ¹ | killed | case 4 (3/3) | Meaningful kill | `7539d005a827` |
| 22 | `delete_sentences` | Incidental rule deleted ¹ | survived (#16) | none fail | Real gap | `fc7e5f22bc91` |
| 23 | `delete_sentences` | New-features rule deleted ¹ | killed | case 4 (3/3) | Meaningful kill | `ebcf3dc272d8` |
| 24 | `delete_sentences` | "You MUST respond…" and "Then provide a brief explanation…" deleted ¹ ³ | killed | cases 1–4, 7, 8 (3/3); 6 (1/3) | Trivial | `b16aced5fdf8` |
| 25 | `delete_sentences` | Injection defense sentence deleted ¹ | killed | case 6 (3/3) | Meaningful kill | `6754d0ad7639` |
| 26 | `delete_sentences` | Input block (`Issue: {{…}}` … `PR description: {{…}}`) deleted ¹ | killed | | Trivial | `673125f78622` |
| 27 | `truncate_prompt` | Last 10 of 19 lines truncated (all inputs removed) | killed | | Trivial | `a6bacdafd557` |
| 28 | `truncate_prompt` | Last 5 of 19 lines truncated (4 of 5 inputs removed) | killed | | Trivial | `670a86f0a908` |

¹ `delete_sentences` also joins the whole prompt onto one line, so these mutants
change formatting as well as removing a sentence. Four of them survived, so the
flattening alone does not appear to change behavior.

² A pure reorder. It was killed in the committed run but survived all three
reruns and muteval 0.12.0's run, so that kill was run-to-run variance. Under the
first version of this table it was an "Anomaly", left out of the score; it is
still left out.

³ Line 9 of the prompt has no full stop, so the sentence splitter took lines 9
and 10 together: the output contract, the explanation instruction, and the only
place `IN_SCOPE` and `OUT_OF_SCOPE` are named. Without them the model answers in
prose ("The PR is "in-scope."…"), which fails `starts-with` on vocabulary, as a
placeholder deletion does. Under muteval 0.12.0 the same signature deletes line
9 only, but that still removes the label words.
