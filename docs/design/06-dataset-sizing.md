# 06 — Dataset sizing

**In short: generate thousands, optimize on hundreds, and measure on thousands.**

How many examples to *generate* and how many to *optimize against* are different questions, with very different answers.

## Several mutations per original

Several different mutations from the same original are allowed and useful. These minimal pairs hold source and topic constant, so the only thing that varies is the error.

- **Group everything by `gold_id`.** The gold row, its controls, and all its mutations go into the same split.
- **Cap the variants per original** (for example, 3–5 mutations and 1–2 controls), so sources with many candidate sites don't dominate.
- **Account for clustering.** Results on variants of one original are correlated, so bootstrap confidence intervals over `gold_id`, not over rows.

## Optimization needs far less than you might expect

GEPA is designed to be sample-efficient; published results use sets of a few hundred examples. The cost is roughly:

```
judge calls ≈ (# candidate prompts evaluated) × (val set size) + reflection minibatches
```

For example, 50 candidates × 300 val rows ≈ 15k judge calls per run. Set `max_metric_calls` with this in mind; the MLflow default of 100 is far too low for a real run.

Val set size dominates the cost, and a larger train set mostly doesn't help. **Variety** helps: many distinct originals, balanced across types. For train and val, prefer many originals with 1–2 variants each over a few originals with many variants.

## The test set is where volume pays off

Test set size should come from what you want to *measure*. The 95% confidence interval for one reporting cell (such as recall on one error type) is approximately:

| n per cell | ±CI at 80% recall |
|---|---|
| 50 | ±11% |
| 100 | ±8% |
| 200 | ±5.5% |
| 400 | ±4% |

With ~15 types at ~100–200 each, plus gold rows and controls for the false-positive rate, the test set comes to a few thousand rows. Clustering by `gold_id` makes the true intervals somewhat wider than this table.

## Allocation for ~3,000 originals

Split by `gold_id` **before** generating anything:

| Split | Originals | Variants each | Rows (approx.) | Purpose |
|---|---|---|---|---|
| Pilot | ~50 | all types | ~300 | Tune mutation prompts, measure rejection rates, human spot-check |
| Train | ~300 | 1–2 + gold + control | ~1,000 | GEPA reflection minibatches |
| Val | ~200 | 1 + gold + control | ~600 | GEPA candidate selection |
| Test | ~1,500 | 2–4 + gold + control | ~6,000+ | Per-type, per-subtlety, per-mutator reporting |
| Reserve | ~900 | — | — | Fresh val/test later |

Plus a separate **human-labeled natural-error set** of ~200–500 real outputs ([05](05-threats-to-validity.md#the-natural-error-set)).

**Label mix:** aim for 40–50% `True` (gold plus controls) in train and val, so a judge that just leans toward `False` doesn't score well.

## Why keep a reserve

- **Design iterations overfit val too.** Every time you look at val scores and adjust mutation prompts, the taxonomy, or scorers, val becomes a little less independent.
- **Stability checks** need fresh subsets: run GEPA 2–3 times with different seeds or train subsets.
- **Re-optimizing later**, when you add error types or change judge models.

## Order of operations

1. **Pilot.** Run all types on ~50 originals. Check rejection rates, type drift, and decline rates, and review a sample by hand. Don't scale up until rejection rates per type are stable.
2. **Generate the full pool in one pass.** Oversample by the measured rejection rate for each type. Generation is a one-time cost, and the pool is reusable.
3. **Draw stratified train and val subsets** from the pool. Grow them only if val scores are still noisy between runs.
4. **Baseline** the seed prompt on test, **optimize**, then **report** on test and on the natural-error set.
