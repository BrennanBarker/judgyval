# judgyval design notes

These notes expand on the sketch in the top-level [README](../../README.md). Each document covers one concern:

| Doc | Covers |
|---|---|
| [01-overview.md](01-overview.md) | Scope (which judges the approach fits), the revised pipeline, dataset schema, MLflow mapping, library abstractions, open decisions |
| [02-data-generation.md](02-data-generation.md) | Mutator model pool, neutral controls, the staged generation process, source-side mutations, validation |
| [03-faithfulness-taxonomy.md](03-faithfulness-taxonomy.md) | Error types and subtlety levels for a faithfulness judge, domain packs, the allowed-background policy |
| [04-scoring-and-optimization.md](04-scoring-and-optimization.md) | Model roles, the `JudgeEvaluation` scorer, `rationale_match`, GEPA via MLflow, what readable prompts do and don't tell you |
| [05-threats-to-validity.md](05-threats-to-validity.md) | Every shortcut and bias discussed, what it looks like, and the control or metric that catches it; sourcing natural errors |
| [06-dataset-sizing.md](06-dataset-sizing.md) | How many examples to generate versus optimize on, split allocation, confidence intervals |

The main principle across all of them: **the judge should be able to succeed only by detecting the error.** Every design choice below either removes a signal other than the error or measures whether the judge is using one.
