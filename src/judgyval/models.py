from pydantic import BaseModel, Field

class Mutation(BaseModel):
    mutated_text: str = Field(description="The complete mutated text")
    mutation_description: str = Field(description="A description of the induced mutation")


import mlflow.genai


mlflow.genai.evaluate()