"""
Signal 2 — Stylometric heuristics.

Measures two structural properties that differ between human and AI writing:

  1. Sentence length variance — AI text tends to have uniform sentence lengths
     (low standard deviation). Human writing is more erratic.

  2. Type-token ratio (TTR) — vocabulary diversity. AI text reuses words more
     predictably, lowering the ratio of unique tokens to total tokens.

Both sub-signals are normalized to [0.0, 1.0] where 1.0 = likely AI-generated.
The final score is their average.
"""

import math
import re


def _split_sentences(text: str) -> list[str]:
    """Split on sentence-ending punctuation; discard empty fragments."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p.strip()]


def _sentence_variance_score(sentences: list[str]) -> float:
    """
    Low standard deviation in sentence lengths → high AI score.

    Normalization: std of 0 → 1.0 (perfectly uniform = AI-like).
                   std >= 20 → 0.0 (highly variable = human-like).
    Returns 0.5 when there are fewer than 2 sentences (can't compute variance).
    """
    if len(sentences) < 2:
        return 0.5

    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    std = math.sqrt(variance)

    score = max(0.0, 1.0 - std / 20.0)
    return score


def _type_token_ratio_score(text: str) -> float:
    """
    Low vocabulary diversity → high AI score.

    TTR = unique_tokens / total_tokens.
    AI score = 1.0 - TTR  (low diversity → high AI score).
    Returns 0.5 for texts shorter than 5 tokens (too short to be meaningful).
    """
    tokens = re.findall(r"\b\w+\b", text.lower())
    if len(tokens) < 5:
        return 0.5

    ttr = len(set(tokens)) / len(tokens)
    return 1.0 - ttr


def classify(text: str) -> dict:
    """
    Returns {"score": float, "details": dict}.
    Score is in [0.0, 1.0] where 1.0 = likely AI-generated.
    """
    sentences = _split_sentences(text)

    variance_score = _sentence_variance_score(sentences)
    ttr_score = _type_token_ratio_score(text)

    combined = (variance_score + ttr_score) / 2.0
    combined = max(0.0, min(1.0, combined))

    return {
        "score": round(combined, 4),
        "details": {
            "sentence_variance_score": round(variance_score, 4),
            "type_token_ratio_score": round(ttr_score, 4),
        },
    }
