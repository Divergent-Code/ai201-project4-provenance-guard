"""
Signal 1 — Groq LLM semantic classifier.

Asks llama-3.3-70b-versatile to assess whether the text reads as
human-written or AI-generated and return a structured score.

Returns a float in [0.0, 1.0] where 1.0 = highly likely AI-generated.
"""

import json
import os

from groq import Groq

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


SYSTEM_PROMPT = """You are an expert at distinguishing human-written text from AI-generated text.

Analyze the provided text and return ONLY a JSON object with this exact structure:
{
  "score": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence>"
}

Where score means:
- 0.0 = definitely human-written
- 1.0 = definitely AI-generated
- 0.5 = completely ambiguous

Focus on: semantic coherence uniformity, formulaic phrasing, unnatural consistency,
absence of personal voice, hedging language patterns, and structural repetition.
Do not include any text outside the JSON object."""


def classify(text: str) -> dict:
    """
    Returns {"score": float, "reasoning": str}.
    Raises on API failure — caller handles fallback.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this text:\n\n{text}"},
        ],
        temperature=0.1,
        max_tokens=150,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model wraps the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    result = json.loads(raw)
    score = float(result["score"])
    score = max(0.0, min(1.0, score))  # clamp to [0, 1]
    return {"score": score, "reasoning": result.get("reasoning", "")}
