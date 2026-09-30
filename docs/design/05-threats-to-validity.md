# 05 — Threats to validity

The main risk in this approach is a judge (or an optimized prompt) that scores well by detecting **something other than the error**. This document lists each shortcut and bias discussed, and what prevents or detects it.

## Shortcut table

| Threat | What the judge learns | Prevention | Detection |
|---|---|---|---|
| **Edited-text style** | "This looks LLM-edited, so `False`" | Neutral controls from the same mutator models ([02](02-data-generation.md#neutral-controls)) | False-positive rate on controls |
| **Edit shape** | "A local edit happened, so `False`" | Span-matched controls: the same kind of span, meaning preserved | False-positive rate on span-matched controls |
| **Mutator style** | "Model A's phrasing means error" | Same model mix for mutations and controls; same model for each gold item's pair | Recall and false-positive rate per `mutator_model` |
| **Source seams** | "This source looks edited, so `False`" | LLM smoothing; source-side neutral controls | False-positive rate on source-side controls |
| **Base rate** | "Lean toward `False`" | 40–50% `True` in train and val | Precision and recall reported separately; false-positive rate on gold |
| **Type collapse** | Only catches easy types | Code-assigned types and quotas ([02](02-data-generation.md#stage-2-assign)) | Recall per `mutation_type` |
| **Easy negatives** | Only catches obvious swaps | `in_source_distractor` subtlety, oversampled | Recall per `subtlety` |
| **Pedantry** | Flags allowed background | A written allowed-background policy plus `True` controls ([03](03-faithfulness-taxonomy.md#the-allowed-background-policy)) | False-positive rate on background controls; real outputs |
| **Right for the wrong reason** | The correct label from an unrelated cue | Deterministic rationale in feedback; `RationaleMatch` | `rationale_match` rate on correct negatives |
| **Self-family blind spot** | Misses errors its own model family makes | Include the judge's family as a mutator | Recall on that mutator |
| **Generator overfitting** | Gets good at *your* synthetic errors specifically | Error types chosen from real error analysis | **The natural-error set** (below) |

## Data validity

| Threat | Mitigation |
|---|---|
| A mutation isn't actually an error ("about" vs. "approximately") | Required error check in 1a; "what doesn't count" lists; human spot-checks |
| Source deletion leaves the claim still supported (redundant support) | Entailment check against the *whole* edited source |
| Type drift (you asked for causal, got predicate) | Type classifier in validation; relabel or discard |
| A "neutral" control changes meaning | Meaning-preservation check on controls |
| Gold contains real errors | Review gold rows the judge flagged; treat as an audit signal ([04](04-scoring-and-optimization.md#gold-rows-the-judge-flags-are-an-audit-signal)) |
| The validator is wrong | Human spot-check of validator decisions on the pilot |

## Evaluation validity

| Threat | Mitigation |
|---|---|
| Leakage across splits (variants of one source in train and test) | Split by `gold_id` before generating |
| Too-narrow confidence intervals (variants of one source are correlated) | Bootstrap over `gold_id`, not rows |
| Overfitting to val through repeated design iteration | A reserve set of untouched originals, for fresh val/test later |
| Optimization noise mistaken for improvement | Repeated GEPA runs with different seeds or subsets; check whether prompts converge |
| Synthetic type frequencies differ from real ones | Report both balanced and natural-frequency-weighted metrics |

## The natural-error set

This is the most important single check. It's a small (~200–500) **human-labeled set of real summarizer outputs**, never used in optimization.

If scores on the synthetic test set go up while scores on the natural-error set stay flat or drop, the judge is overfitting to your generator, not getting better at faithfulness. Nothing else in the pipeline can tell you this. Reading prompt diffs certainly can't ([04](04-scoring-and-optimization.md#what-readable-prompts-do-and-dont-tell-you)).

## Sourcing natural errors

Two different properties matter here:

- **Natural** is about where an error came from: a real summarizer, or whoever wrote the gold data, made it.
- **Representative** is about how examples were sampled.

Errors the judge found are natural but **not representative**. The judge decided which errors got into the sample. So a judge-found set can't measure that judge's recall (by construction, recall on it is about 100%), and it skews type frequencies toward what the judge notices. Using it as the test set would be circular.

| Source | Unbiased for | Good for | Not for |
|---|---|---|---|
| **Random sample, human-labeled** blind to the judge's output | Recall, false-positive rate, natural type frequencies | **The natural-error test set** | — (limited only by labeling cost) |
| **Judge-flagged, human-confirmed** (real outputs) | **Precision** on real outputs (the share of flags that are real) | Finding error patterns the taxonomy is missing | Recall, frequencies, the test set |
| **Gold audit**: gold rows the judge flagged, confirmed by a human ([04](04-scoring-and-optimization.md#gold-rows-the-judge-flags-are-an-audit-signal)) | Nothing strictly | Fixing or removing bad gold; taxonomy ideas | Recall, frequencies, the test set |
| **Flagged by a different, stronger finder** (strong model or ensemble) | Nothing strictly | **Training examples**, especially errors the target judge misses | The test set (biased toward what the finder can see) |

Errors the target judge already catches are also weak *training* signal, since there's little to learn from examples it already gets right. A stronger finder turns up the misses, and those are the most useful to optimize on.

### Process rules

1. **Label the random sample blind.** Reviewers must not see the judge's verdict or rationale, or they'll tend to agree with it and the selection bias comes back.
2. **Keep sources in separate pools and tag every row** with `source` (`random_sample`, `judge_flagged`, `finder_flagged`, `gold_audit`). Only `random_sample` rows go into recall, false-positive-rate, and frequency estimates.
3. **Keep the random sample out of optimization.** Mined rows from other sources can go into training, grouped by `gold_id` or source document like everything else.

Only the blind-labeled random sample measures the judge. Mined errors feed the taxonomy, gold fixes, and training.
