# 04 — Scoring and optimization

## Model roles

| Role | What you want |
|---|---|
| Mutator / rewriter | Varied (3–4 families), balanced, recorded on each row |
| Validator (step 1a) | Strong, fixed, ideally not one of the mutators |
| Judge under optimization | One fixed, cheap model |
| GEPA reflection model | Strong, fixed, different from the judge |
| `rationale_match` scorer | Can be cheap; spot-check it against hand labels |

**Choosing the judge model:** optimized prompts are tuned to one model and don't transfer cleanly. If you're choosing between judge models, compare 2–3 candidates with the *seed* prompt on val, pick one, and then optimize only that one.

## `JudgeEvaluation` scorer

- **Value:** whether the judge's label matches `expectations.label`.
- **Rationale:** synthesized deterministically, with no LLM call:
  - Mutated row: *"The injected error was: `<mutation_description>`. The judge's rationale was: `<judge rationale>`."*
  - Gold row the judge flagged: *"This example is gold (no injected error). The judge claimed: `<judge rationale>`."*
  - Neutral control the judge flagged: *"This was a meaning-preserving edit: `<description>`. The judge claimed: `<judge rationale>`."*

The wording is deliberately neutral, and the reflection model decides what it means. A strong reflection model can see when the judge was right for the wrong reason and discount that example. (MLflow also puts `expectations` in the reflection model's dataset, so it sees `mutation_description` directly too.)

### Gold rows the judge flags are an audit signal
When a judge flags a gold example, some of those flags will be *real errors in the gold data*. Log them separately and review them. This makes the library a gold-data auditing tool as a side effect.

## `RationaleMatch` scorer

This scorer checks whether the judge's rationale identifies the injected error.

**Why add it**
- **It's a metric.** Without it, "right for the wrong reason" exists only inside the reflection model's reasoning. You can't report it, compare it between prompt versions, or catch it getting worse.
- **It gives the optimizer a direct signal.** Via `aggregation`, you can optimize a composite (label correct *and* rationale matches) instead of hoping the reflection model notices the mismatch.

**What it costs**
- LLM calls on every example, for every candidate prompt GEPA evaluates.
- Another judge that needs validating.
- A noisier optimization signal if the scorer itself is unreliable.

**Keeping it cheap**
1. **Only run it on negatives the judge labeled correctly.** Gold rows have no injected error to compare against, and a wrong label already scores 0.
2. **A cheap model is probably enough.** Comparing a rationale against a known description is much easier than judging from scratch. Spot-check it against a small hand-labeled sample anyway.
3. **Cache results** by (rationale, mutation_description). Different candidate prompts often produce near-identical rationales.
4. **Start with reporting only.** Run it on val and test, outside the optimization loop. Move it into the loop via `aggregation` only if the numbers show GEPA is rewarding wrong-reason wins.

**Recommended start:** option 4 plus the gating in option 1.

**Edge case:** if the judge flags a real *pre-existing* error in the gold text instead of the injected one, `rationale_match` says "no" even though the judge isn't wrong. Tag those rows for gold audit instead of counting them purely as failures.

## Optimization with MLflow and GEPA

```python
from mlflow.genai import optimize_prompts
from mlflow.genai.optimize import GepaPromptOptimizer

result = optimize_prompts(
    predict_fn=judge_predict_fn,           # receives **inputs (source, summary)
    train_data=train_dataset,
    prompt_uris=[judge_prompt_uri],
    optimizer=GepaPromptOptimizer(
        reflection_model="<provider>:/<strong-model>",
        max_metric_calls=...,              # default is 100; far too low, see 06
        gepa_kwargs={"valset": val_dataset},  # verify once gepa is installed
    ),
    scorers=[JudgeEvaluation()],           # + RationaleMatch() once it's in the loop
    aggregation=...,                       # optional composite
)
```

See [01 § MLflow API notes](01-overview.md#mlflow-api-notes-checked-against-the-installed-mlflow-3161) for the details this depends on.

## What readable prompts do and don't tell you

Prompt optimization has two real advantages over fine-tuning weights:

- **You can read the changes.** Some overfitting is obvious when you read the diff: rules tied to specific examples ("if the summary mentions Q3 revenue…"), domain trivia, or few-shot examples copied from training data. GEPA also records the reflection model's reasoning for each change.
- **Less capacity means less memorization.** A prompt carries far fewer adjustable parameters than a weight update, so it can't memorize much of the dataset. That's a regularizer, separate from being readable.

But reading the prompt has limits:

1. **The shortcut can live in the model, not in the prompt.** The base model may already respond a little to edit artifacts, and GEPA selects whichever prompt amplifies that. The winning prompt can read perfectly reasonably ("scrutinize phrasing carefully for subtle alterations"). Reading tells you what the prompt *asks for*, not what the model *does* with it.
2. **Harmless-sounding wording can shift the base rate.** "Err toward flagging unsupported content" sounds sensible, but it also improves scores for a trivial reason if negatives outnumber positives.
3. **Selected few-shot examples can carry shortcuts quietly** through their surface features (length, domain, where the edit sits).
4. **Wording effects aren't semantic.** Rephrasings with the same meaning can change behavior noticeably.

**Treat reading prompt diffs as a first screen.** The real checks are behavioral; see [05](05-threats-to-validity.md). In short, prompt optimization is less prone to overfitting and easier to audit, but reading isn't a substitute for testing on controls and natural errors.

## Practices for each optimization run

- **Baseline first:** score the seed prompt on test before optimizing, so gains can be measured.
- **Stability:** run GEPA 2–3 times with different seeds or train subsets. If the winning prompts differ a lot but score about the same, you're fitting noise. If they converge, the signal is real.
- **Ablations:** remove one section of the optimized prompt at a time and measure the change on val. That shows which parts actually drive the score.
- **Track the error-rate split**, not just accuracy: the false-positive rate on gold and controls, and recall on mutations, across iterations.
