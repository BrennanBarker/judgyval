# 02 — Data generation

## Principle: the code chooses, not the model

If one model gets free choice of which error to inject, it collapses toward the easiest types (entity and number swaps), and you get imbalance. So the library chooses the **(example, type, span, subtlety, mutator model)** for each generation, and the model only carries it out.

## Mutator model pool

**Use varied mutators. Fix the judge.** The two roles want opposite things:
- Mutators and rewriters *generate the data distribution*. Variety makes it harder for the judge to shortcut by recognizing one model's style, and different families make different kinds of errors.
- The judge is *what gets optimized*. GEPA tunes a prompt for a specific model, and optimized prompts don't transfer cleanly between models. See [04](04-scoring-and-optimization.md).

Rules for the pool:

1. **3–4 models of similar tier, from different families.** Tier mostly affects how subtle the errors are. One stronger model can be added as a deliberate source of hard examples, labeled so it can be reported separately.
2. **Use the same model mix for mutations and neutral controls.** This is the most important rule. If model A mostly writes mutations and model B mostly writes controls, the judge learns "A's style means error." The cleanest option is to have the same sampled model produce both the mutation and the control for a given gold item.
3. **Assign models round-robin or stratified by gold item, not i.i.d.** Random draws can come out uneven by chance on small datasets.
4. **Check the balance after filtering.** Models pass validation at different rates. Check per-model counts after step 1a, and resample or reweight if they've drifted.
5. **Record `mutator_model` on every row** and report judge recall per mutator. Low recall on one mutator means either a blind spot or subtler errors.
6. **Include the judge's own model family as one of the mutators, and track it separately.** If the judge misses errors written by its own family, that's a blind spot you want to measure.

## Neutral controls

Neutral controls are meaning-preserving edits labeled `True`. Without them, "the text was changed" and "the text is wrong" are the same signal, and the judge can learn the first.

- **Target the same kind of span as the mutations.** If mutations are single-span edits and controls are whole-text paraphrases, the *shape of the edit* gives the label away. For a number site, rephrase the sentence containing the number while keeping the number the same.
- **Also make controls on the source side** (see below).
- **Add controls with allowed background** too, if your policy permits some background knowledge (see [03](03-faithfulness-taxonomy.md)).

## The staged generation process

### Stage 1: Find candidate sites
For each gold example, list every place each error type *could* be injected. This produces a feasibility matrix: example × type → candidate spans.

- **Deterministic where possible:** a regex for numbers and dates, named-entity recognition for entities, a dependency parse for negatable predicates and modals. These are cheap and unbiased.
- **An LLM for the rest:** causal and discourse links, conditions and exceptions, quantifiers, coreference chains. Ask it to *list candidate spans per type*, not to mutate anything.
- **Record in-source distractors** for each site: other entities, numbers, or dates that appear in the source and could replace the original. These are needed to generate hard examples.

### Stage 2: Assign
The code fills per-type (and per-subtlety) quotas by picking (example, type, span) triples:
- **Handle the scarcest types first.** If only 15% of examples contain a causal claim, reserve those examples for causal errors before entity swaps use them up.
- **Cap the variants per original** (for example, 3–5 mutations and 1–2 controls).
- **Rotate mutator models** round-robin across assignments.
- A greedy quota-filling algorithm is enough.

### Stage 3: Directed mutation
Give the mutator the exact type, span, and subtlety:
- **One prompt template per type,** with a definition, 2–3 examples, and a **"what doesn't count"** list (e.g. "3" → "three" isn't a quantity error, and neither is "approximately 40%" → "about 40%").
- **Allow a `NOT_APPLICABLE` answer** so the model can decline instead of forcing a bad mutation. Track decline rates per type; a high rate means Stage 1 is too loose for that type.
- **Hybrid rule + LLM for mechanical types.** Rules pick the target and replacement (e.g. another date that appears in the source). The LLM only makes the sentence fluent. You get tight control without FactCC-style unnatural text.
- **Output:** the edited text, a `mutation_description` that names the specific claim affected, and the metadata fields in the [schema](01-overview.md#dataset-schema).

### Stage 4: Validate, including the type
See [01 § 1a](01-overview.md#1a-validate-variants). In addition to "is this an error?", ask a classifier "which type is it?" Type drift is common (you ask for a causal error and get a predicate error). Relabel or discard, but never keep a row with the wrong type.

### Stage 5: Top up
After filtering, harder-to-inject types will fall below quota. Run another assignment round only for the types that are short.

## Source-side mutations

Mutating the *source* while keeping the summary gold is valid, and it may be the cleanest way to create unsupported-claim errors.

**Why it works well**
- The summary is original and unedited, so there are no mutator artifacts for the judge to shortcut on. Only the evidence changes.
- It isolates grounding. The claim is plausible and was true in the original document, so the only way to get it right is to check the source.
- It creates a minimal pair: the same summary appears with the original source (`True`) and with the edited source (`False`). Keep both in the same split.

**Caveats**
1. **Support is often redundant.** A fact can be restated elsewhere, implied, or inferable from other sentences. Validation must check entailment of the claim against the *entire* edited source. Expect a meaningful rejection rate.
2. **Tag removal and contradiction separately.** Removing support makes the claim *unsupported* (`support_removed`). Changing the supporting fact makes it *contradicted* (`support_contradicted`). Judges often perform differently on each.
3. **Deletion can leave seams.** Dangling references ("as noted above"), broken coreference, abrupt transitions, and a shorter source are all possible. The fixes are LLM smoothing of the edited source, and **source-side neutral controls**: delete or rephrase sentences that don't support any summary claim, and label those pairs `True`.
4. **The `mutation_description` should name the summary claim that lost support**, not just the deleted sentence. That keeps `rationale_match` easy to judge ("did the judge flag *that claim*?").

## One error per example

Start with exactly one injected error per row. That keeps labels, descriptions, and `rationale_match` unambiguous. Rows with several errors can come later as a harder evaluation tier.
