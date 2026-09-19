"""Shared Nebius Token Factory client, so connection details live in one place."""
import os

from openai import OpenAI

DEFAULT_MODEL = os.environ.get("TERRAWEAVER_MODEL", "nvidia/Nemotron-3_5-Lightning")


def client() -> OpenAI:
    return OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=os.environ["NEBIUS_API_KEY"],
    )
