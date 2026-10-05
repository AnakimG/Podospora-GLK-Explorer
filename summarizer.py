import os
import dspy

api_key=os.getenv("OPENROUTER_API_KEY")

lm = dspy.LM(
    model="openrouter/qwen/qwen3.5-9b",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
    temperature=0.3,
    cache=False,
)

dspy.configure(lm=lm)


class Summarize(dspy.Signature):
    """Summarize Statements linked to a specific Normalized Entity."""

    normalized_entity: str = dspy.InputField(
        desc="The selected Normalized Entity."
    )

    statements: list[str] = dspy.InputField(
        desc="The statements list linked to the Normalized Entity."
    )

    summary: str = dspy.OutputField(
        desc="The summary containing all the information from the statements."
    )


SUMMARIZER = dspy.ChainOfThought(Summarize)


def generate_summary(normalized_entity, statements):
    result = SUMMARIZER(
        normalized_entity=normalized_entity,
        statements=statements,
    )

    return result.summary