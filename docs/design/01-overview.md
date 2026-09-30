# 01 — Overview

## What judgyval does

judgyval evaluates and optimizes LLM judges using **controlled error injection**. It starts from gold examples, injects known errors (each with a natural-language description of what was changed), and uses the result as labeled contrastive data for three purposes:

1. Measuring a judge: does it catch each kind of error, and does it leave correct examples alone?
2. Giving the prompt optimizer feedback that knows *what the error actually was*, so the optimizer can tell "right for the right reason" from "right by luck."
3. Auditing the gold data as a side effect, because a judge flagging a gold example is sometimes correct.

## Which judges the approach fits

It works for any judge that meets two conditions:

1. **There's a known-good artifact** (gold output, reference, or compliant response).
2. **Failures are local, describable, and injectable.** You can say "here is what's wrong" in a sentence.

| Fits well | Fits poorly |
|---|---|
| Faithfulness / groundedness (summaries, RAG answers) | Holistic quality ("helpfulness", "engagingness") |
| Instruction following (inject constraint violations) | Pairwise preference judges |
| Structured extraction (wrong field, wrong value) | Tasks with no gold, or many equally-good golds |
| Citation / attribution correctness | Creativity, tone, "vibes" |
| Policy / style-guide compliance (inject a violation) | |
| Translation adequacy | |
| Code correctness (this is mutation testing) | |

Graded (Likert) judges can also fit if mutations carry a severity level.

**Where the generality lives:** the pipeline (mutate → validate → assemble contrastive data → optimize with error-aware feedback) is task-agnostic. What's task-specific is the **error taxonomy, the mutation prompts, and the field mapping** (which field gets mutated). Those should be plugins stored as data, not code.

**Build order:** build faithfulness end-to-end first. Then build a second, contrasting task (instruction following is a good one) *before* freezing the abstractions. The second task shows which parts of the first design were secretly faithfulness-specific.

**Prior art:** FactCC (rule-based synthetic negatives for factual consistency); FRANK (Pagnoni et al., 2021), a typology of summarization factuality errors; mutation testing in software engineering.

## Revised pipeline

### 0. Prep data
Gold data is registered as an MLflow dataset. Before generating anything, **split by `gold_id`** into pilot / train / val / test / reserve (see [06](06-dataset-sizing.md)). Everything generated from one original stays in that original's split.

### 1. Generate variants
For each gold example, generate:
- **Mutations**: one injected error each, with the type, span, and subtlety assigned by the library, not chosen by the model. See [02](02-data-generation.md).
- **Neutral controls**: edits that preserve meaning and touch the same kind of span, labeled `True`.

Mutator models are drawn from a balanced pool of 3–4 model families. The prompt and model config for each generation are logged to the prompt registry.

`mlflow.genai.evaluate(data=gold_dataset, predict_fn=mutate, scorers=[...])` provides tracing and parallelism. The step 1a scorers can go in the same call. Keep them separate only if you want to re-score without regenerating, and if so, say so.

### 1a. Validate variants
Validation is a **required filter**, not an optional one:
- `ChangedTextScorer`: the text actually changed. Necessary but far from enough.
- **Error check** (strong LLM, fixed, ideally not one of the mutators): is this actually an error relative to the pair? For source-side mutations, check entailment against the *whole* edited source.
- **Type check**: is it the assigned error type? Relabel or discard if the type drifted.
- **Control check**: for neutral controls, is the meaning actually preserved?
- A human spot-check on a sample, since the validator also needs validating.

### 2. Assemble the augmented dataset
You need a helper that converts traces into a dataset. It's core library code and should be a named component. Register the result as a new MLflow dataset.

### 3. Evaluate and optimize the judge
One fixed, cheap judge model. The judge's prompt is optimized with `mlflow.genai.optimize_prompts(...)` and `GepaPromptOptimizer`, using error-aware scorers. See [04](04-scoring-and-optimization.md).

## Dataset schema

For the *judge's* `predict_fn`, the text being judged is an **input**. `optimize_prompts` calls `predict_fn(**inputs)` and scores the result against `expectations`. So both source and summary go in `inputs`, even though the summary is the mutation target:

```python
{
    "inputs": {"source": ..., "summary": ...},
    "expectations": {
        "label": False,                    # True for gold and neutral controls
        "mutation_description": ...,       # None for gold; describes the edit for controls
        "mutation_type": "quantity",       # or "gold", "neutral_control"
        "mutation_target": "summary",      # or "source"
        "subtlety": "in_source_distractor",
        "mutator_model": ...,
        "mutator_prompt_uri": ...,         # provenance
        "gold_id": ...,                    # for grouped splits and clustered CIs
    },
}
```

The step 0 example in the top-level README puts `summary` under `inputs` for gold data but under `outputs` in step 2. Use the layout above everywhere.

## MLflow API notes (checked against the installed mlflow 3.16.1)

- The entry point is `mlflow.genai.optimize_prompts(*, predict_fn, train_data, prompt_uris, optimizer, scorers, aggregation, enable_tracking)`. The README's `mlflow.genai.optimize.optimize(...)` isn't the name to use.
- The optimizer class is `mlflow.genai.optimize.GepaPromptOptimizer(reflection_model, max_metric_calls=100, display_progress_bar=False, gepa_kwargs=None)`.
- `aggregation` combines per-scorer results into one number. That's where a composite score goes (label correct *and* rationale matches).
- `max_metric_calls` defaults to **100**, which is far too low for a real run; see [06](06-dataset-sizing.md).
- MLflow passes only `trainset` to GEPA. A separate validation set would have to go through `gepa_kwargs` (`valset`). Verify this once `gepa` is installed; it isn't in the environment yet.
- The reflection model's dataset includes each row's `expectations` and the scorer `rationales`. So the reflection model sees `mutation_description` directly, as well as your synthesized rationale.
- Use one name for the scorer; the README uses both `JudgeEvaluator` and `JudgeEvaluation`.

## Library abstractions (proposed)

- **`ErrorType`**: a registered object with a definition, examples, a site-finding function (rule-based or LLM), a mutation prompt template, and a "what doesn't count" list. Types are grouped into **packs**: a faithfulness pack ships with the library, and domain packs extend it.
- **`MutatorPool`**: a set of model configs plus an assignment strategy (`round_robin`, `uniform`, `stratified`). Each config is logged to the prompt registry.
- **`SiteFinder` → `Assigner` → `Mutator` → `Validator`**: the staged generation process in [02](02-data-generation.md).
- **Trace → dataset helper**: turns generation runs into registered datasets with the schema above.
- **Scorers**: `JudgeEvaluation` (label plus deterministic rationale) and `RationaleMatch` (an LLM check, gated).
- **Reporting**: breakdowns by type, subtlety, mutator, and label; a report of gold rows the judge flagged, for audit.

## Open decisions

- Task-agnostic from day one, or faithfulness-first with a later refactor? (Recommended: faithfulness-first, with the taxonomy stored as data.)
- The policy on allowed background knowledge (see [03](03-faithfulness-taxonomy.md)).
- Whether `rationale_match` goes into the optimization loop or is used only for reporting (recommended: reporting only at first).
- Whether meaning-changing omission is in scope for this judge or belongs to a separate completeness judge.
