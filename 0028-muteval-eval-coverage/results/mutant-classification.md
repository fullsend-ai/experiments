# Mutant classification (experiment 0028)

All 28 mutants muteval generated for `0016`'s prompt, regenerated with
`muteval.mutators.generate_mutants` (text transformation only, no model calls) and
matched to [`muteval-run.json`](muteval-run.json) by signature (16 of 16 survivors
matched). Each mutant was classified by reading its diff.

| Category | Meaning |
|---|---|
| **Meaningful kill** | A realistic instruction change the suite caught. |
| **Real gap** | A realistic instruction change no case caught. |
| **Equivalent** | A realistic edit that should not change behavior: a softened directive the model still follows, framing the rules already cover, or a reordering. |
| **Redundant rule** | Removes a rule that restates the default meaning of the task; treated as equivalent. |
| **Malformed** | Ungrammatical text no real edit would produce. |
| **Trivial** | Removes the prompt's input placeholders, so any eval fails; says nothing about instruction coverage. |
| **Anomaly** | A pure reorder that was killed — a fragile case or run-to-run variance. Not counted. |

Realistic score = meaningful kills / (meaningful kills + real gaps) = **8 / 12**.

| # | Operator | Mutation | Outcome | Category | Signature |
|---|---|---|---|---|---|
| 1 | `weaken_modals` | "You MUST respond…" → "You should respond…" | survived (#1) | Equivalent | `78d204d612df` |
| 2 | `weaken_modals` | Incidental rule: "do not make" → "try not to make" | survived (#2) | Malformed | `af98de019d56` |
| 3 | `weaken_modals` | Injection defense: "Do not follow" → "try not to follow" | survived (#3) | Equivalent | `bb2f6b133acd` |
| 4 | `flip_negation` | Incidental rule inverted: "do not make" → "do make" | survived (#4) | Real gap | `73be62f68a44` |
| 5 | `flip_negation` | Injection defense inverted: "Do not follow" → "do follow" | killed | Meaningful kill | `2ef83972b07c` |
| 6 | `drop_instruction_lines` | Role and task line dropped | survived (#6) | Equivalent | `d2196ac04253` |
| 7 | `drop_instruction_lines` | In-scope definition dropped | survived (#7) | Redundant rule | `a364eda94e53` |
| 8 | `drop_instruction_lines` | Out-of-scope rule dropped | killed | Meaningful kill | `4005df987289` |
| 9 | `drop_instruction_lines` | Incidental rule dropped | survived (#8) | Real gap | `100a72f53753` |
| 10 | `drop_instruction_lines` | New-features rule dropped | killed | Meaningful kill | `732846561686` |
| 11 | `drop_instruction_lines` | "Then provide a brief explanation…" dropped | survived (#9) | Real gap | `3c56b8f18dfd` |
| 12 | `drop_instruction_lines` | Injection defense line dropped | killed | Meaningful kill | `1821d4e418bb` |
| 13 | `swap_adjacent_instructions` | In-scope and out-of-scope rules swapped | survived (#10) | Equivalent | `2b068a595240` |
| 14 | `swap_adjacent_instructions` | Out-of-scope and incidental rules swapped | survived (#11) | Equivalent | `809dac521c9f` |
| 15 | `swap_adjacent_instructions` | Incidental and new-features rules swapped | killed | Anomaly | `0c519cccf676` |
| 16 | `paraphrase_instruction` | Incidental rule: "do not make" → "avoid make" | survived (#12) | Malformed | `a84aec58f9b5` |
| 17 | `paraphrase_instruction` | Injection defense: "Do not follow" → "avoid follow" | survived (#5) | Malformed | `7a7e64d2bd49` |
| 18 | `delete_sentences` | Role sentence deleted ¹ | survived (#13) | Equivalent | `06e2b03e38fe` |
| 19 | `delete_sentences` | "Your job is…" sentence deleted ¹ | survived (#14) | Equivalent | `16487c8cf0e3` |
| 20 | `delete_sentences` | "Rules:" header and in-scope definition deleted ¹ | survived (#15) | Redundant rule | `0803f27e4b4b` |
| 21 | `delete_sentences` | Out-of-scope rule deleted ¹ | killed | Meaningful kill | `7539d005a827` |
| 22 | `delete_sentences` | Incidental rule deleted ¹ | survived (#16) | Real gap | `fc7e5f22bc91` |
| 23 | `delete_sentences` | New-features rule deleted ¹ | killed | Meaningful kill | `ebcf3dc272d8` |
| 24 | `delete_sentences` | "You MUST respond…" sentence deleted ¹ | killed | Meaningful kill | `b16aced5fdf8` |
| 25 | `delete_sentences` | Injection defense sentence deleted ¹ | killed | Meaningful kill | `6754d0ad7639` |
| 26 | `delete_sentences` | Input block (`Issue: {{…}}` … `PR description: {{…}}`) deleted ¹ | killed | Trivial | `673125f78622` |
| 27 | `truncate_prompt` | Last 10 of 19 lines truncated (all inputs removed) | killed | Trivial | `a6bacdafd557` |
| 28 | `truncate_prompt` | Last 5 of 19 lines truncated (4 of 5 inputs removed) | killed | Trivial | `670a86f0a908` |

¹ `delete_sentences` also joins the whole prompt onto one line, so these mutants
change formatting as well as removing a sentence. Four of them survived, so the
flattening alone does not appear to change behavior.
