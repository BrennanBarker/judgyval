# judgyval

`judgyval` is a library around a workflow to evaluate and optimize LLM-based model judges, using controlled error injection.

This library is tightly integrated with the `mlflow` experiment tracking platform, making use of MLFlow's prompt registry, datasets registered to mlflow, mlflow.openai.autolog() to generate traces, mlflow.genai.evaluate() to log generations and scoring, and mlflow.genai.optimize() to optimize judge prompts based on feedback from earlier stages, via the mlflow GEPA optimizer.

Detailed design notes live in [docs/design/](docs/design/README.md).

## Design Outline
0. Prep Data

    Gold data is registered as an mlflow dataset.  (Assume this is already done.)
    
    Example: a gold summarization dataset has been formatted to have a shape of [{"inputs": {"id": str, "source": str, "summary": str}, "outputs": {}, "expectations": {}}]

1. Error Injection (Mutation)

    One or more LLMs are enlisted to augment the gold dataset by injecting an error into each example.  The mutated text, as well as a natural language *description of the mutation* are generated as output from the model(s). the `mutate` prediction function might also pass additional metadata into the expectation, for example a mutation_target (for the part of the input being mutated) or a mutation_type. For provenance reasons, the prompt and model configurations for the mutation models are logged into the MLFlow prompt registry.  `mlflow.genai.evaluate(data=gold_dataset, predict_fn=mutate, scorers=[])` is used to generate data using mlflow's tracing and parallelism facilities.

1.a. Mutation scoring

    After generating mutated data, one or more scorers are applied (`mlflow.genai.evaluate(data=mutation_run_traces, scorers=[ChangedTextScorer, <Some Judge?>])`).  As a minimum, a ChangedTextScorer simply identifies that the mutation_target does not == the original.  A judge might be invoked to, say, evaluate whether the given mutation_description describes the difference between the original and mutated target.  These scores might be used to exclude traces from the augmented dataset in the next step

2. Augment Dataset

    A new dataset is created and registered with mlflow, now placing the original data as well as newly-generated examples into their proper input and output columns ("source" and/or mutations targeting "source" in "inputs" and "summary" or mutations targeting "summary" in "output").  Labels ("expectations") representing the judge's target are determined by whether the data is gold (True) or mutated (False), and the mutation model's mutation description provides a target rationale for the judge.

3. Evaluate/Optimize Judges

    Candidate model judges are proposed to distinguish between the gold examples and the mutated examples and provide a rationale, consistent with MLFlow's Feedback object.  Judges are evaluated with a `JudgeEvaluator(mlflow.Scorer)` based on their ability to recover the expected labels; the value indicates whether the labels match, but importantly we also synthesize a rationale: "the induced error was: <mutation_description>, whereas the model's rationale was: <judge rationale>" -- that ambiguous formulation allows the rationale to be generated deterministically, whereas a strong reflection model can spot cases where the judge was "right for the wrong reason" and discount that example as signal for the prompt optimizer.  In this way `mlflow.genai.optimize.optimize(data=augmented_dataset, predict_fn=judge_predict_fn, scorers=[JudgeEvaluation], optimizer=GepaOptimizer(reflection_model))`.




