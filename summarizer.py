import os
import dspy
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


lm = dspy.LM(
    model="openrouter/qwen/qwen3.5-9b",
    api_key=st.secrets["OPENROUTER_API_KEY"],
    api_base="https://openrouter.ai/api/v1",
    temperature=0.3,
    cache=False,
)

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

    with dspy.context(lm=lm):

        st.write("DSPy LM:", dspy.settings.lm)
        st.write("LM correctly loaded:", dspy.settings.lm is lm)

        result = SUMMARIZER(
            normalized_entity=normalized_entity,
            statements=statements,
        )

    return result.summary