from pydantic import BaseModel, Field

class Edit(BaseModel):
    original: str = Field(
        description="Text to replace, copied verbatim from the input, with enough surrounding context to appear exactly once"
    )
    replacement: str = Field(description="The text to put in its place")


class Mutation(BaseModel):
    edits: list[Edit] = Field(
        description="Non-overlapping edits that together induce the mutation"
    )
    mutation_description: str = Field(description="A description of the induced mutation")


import mlflow.genai


mlflow.genai.evaluate()