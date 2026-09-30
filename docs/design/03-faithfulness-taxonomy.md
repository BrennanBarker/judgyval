# 03 — Faithfulness error taxonomy

This taxonomy is for a judge that decides whether a summary (or answer) is faithful to its source. Each error has two axes: **type** and **subtlety**. It starts from FRANK-style categories (Pagnoni et al., 2021) and adds the types that tend to matter in practice.

Implement each type as a registered `ErrorType` with a definition, examples, a site finder, a mutation template, and a "what doesn't count" list (see [02](02-data-generation.md)).

## Error types

### A. Semantic frame errors: misstating what the source says

| Type | Example | Site finder |
|---|---|---|
| `entity` | Wrong person, organization, product, or drug | Named-entity recognition |
| `quantity` | Wrong number, unit, percentage, date, or time period | Regex |
| `predicate` | Wrong action or relation ("acquired" → "partnered with") | Dependency parse or LLM |
| `role_swap` | Who did what to whom, or who said what, reversed | Dependency parse or LLM |
| `circumstance` | Wrong time, place, or manner | Named-entity recognition or LLM |

### B. Logical and discourse errors

| Type | Example | Site finder |
|---|---|---|
| `polarity` | A claim negated, or a negation removed | Dependency parse |
| `modality` | "may" → "will"; a hedge dropped; "preliminary" → "confirmed" | Modal-verb lexicon or LLM |
| `quantifier_scope` | "some" → "most"; generalizing from one case | Quantifier lexicon or LLM |
| `causal_discourse` | Correlation stated as causation; wrong temporal order; invented contrast | LLM |
| `coreference` | A pronoun or reference points to the wrong entity | Coreference model or LLM |
| `conflation` | Two distinct entities or events merged into one | LLM |

### C. Extrinsic content: not supported by the source

| Type | Example | How to generate |
|---|---|---|
| `fabricated_detail` | A plausible but false added detail | Summary-side insertion |
| `support_removed` | A summary claim whose support was deleted from the source | Source-side deletion ([02](02-data-generation.md#source-side-mutations)) |
| `unsupported_world_knowledge` | A claim that's *true in the world* but absent from the source | Summary-side insertion of true, widely known facts, or source-side deletion targeting widely known facts |

`support_removed` covers most extrinsic cases. It doesn't fully cover the dangerous case: claims the *judge already knows are true* from pretraining (a company's headquarters, a well-known date, what an acronym stands for). Judges let these through because they recognize them as true. So keep `unsupported_world_knowledge` as its own type, and choose sites deliberately for it.

Source-side edits that change (rather than delete) the supporting fact produce `support_contradicted`. That's an intrinsic error; tag it separately from `support_removed`.

### D. Meaning-changing omission

| Type | Example |
|---|---|
| `dropped_condition` | "if X, then Y" → "Y"; an exception or qualifier removed |

Only include omissions that make what remains **false**. Plain incompleteness belongs to a separate completeness judge. Deciding where that boundary falls is an [open decision](01-overview.md#open-decisions).

### E. Domain-specific types

This is where "domain-optimized" comes in. **Derive these from error analysis of real model outputs in your domain**, not from brainstorming. Examples:

- **Medical:** dose, frequency, patient population, contraindication.
- **Legal:** obligation vs. permission (shall/may), party swaps, jurisdiction.
- **Finance:** reporting period (Q3 vs. FY), GAAP vs. non-GAAP, direction of change vs. level.

Package these as a domain pack that extends the base faithfulness pack.

## Subtlety axis

| Level | Description |
|---|---|
| `out_of_source` (easier) | The replacement entity or number never appears in the source |
| `in_source_distractor` (harder) | The replacement is a *different* entity or number that does appear in the source. These are the most valuable hard negatives |
| `edit_size` | Single token vs. a restructured clause (record it; it's useful for breakdowns) |

Tag every mutation with its subtlety. Report results by subtlety, and oversample the hard levels for optimization.

## The allowed-background policy

In most domains some common knowledge is fine in a summary, like expanding "FDA" or writing "Paris, France". If every such addition is labeled an error, optimization pushes the judge toward pedantry and false positives on real outputs.

- **Write the policy down**, e.g. "definitional or trivial background is allowed; substantive claims need support."
- **Include `True`-labeled controls** that add allowed background, so the judge learns where the line is.
- Put the policy text in the judge's seed prompt and in the validator's prompt, so they apply the same standard.

## Type frequencies: natural vs. balanced

The biggest risk with a synthetic taxonomy is that its distribution won't match the errors real summarizers make.
- **Training and optimization:** balance across types for coverage, and oversample hard subtlety levels.
- **Reporting:** also report a version weighted by natural frequency, and compare the two. Estimate frequencies only from the blind-labeled random sample, not from judge-flagged errors (see [05 § Sourcing natural errors](05-threats-to-validity.md#sourcing-natural-errors)).
- **Early on:** use a round of real error analysis to decide which types to include at all.
