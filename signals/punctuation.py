"""
Signal 3 — Punctuation & transition-phrase patterns.

Measures two surface patterns that AI models produce with high regularity:

  1. Transition phrase density — AI text overuses discourse connectives
     (however, therefore, furthermore, ...). High density → high AI score.

  2. Comma consistency — AI text places commas with metronomic regularity.
     Low coefficient of variation across sentences → high AI score.

Both sub-signals are normalized to [0.0, 1.0] where 1.0 = likely AI-generated.
The final score is their average.
"""

import math
import re

_TRANSITION_PHRASES = {
    "however", "therefore", "furthermore", "moreover", "consequently",
    "nevertheless", "subsequently", "notably", "importantly", "specifically",
    "additionally", "overall", "ultimately", "in conclusion", "in summary",
    "it is important", "it should be noted", "as a result", "for instance",
    "for example", "in contrast", "on the other hand",
}


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p.strip()]


def _transition_density_score(text: str, sentences: list[str]) -> float:
    """
    Normalize: 0 transitions per sentence → 0.0; ≥0.5 per sentence → 1.0.
    """
    lowered = text.lower()
    count = sum(1 for phrase in _TRANSITION_PHRASES if phrase in lowered)
    n = max(1, len(sentences))
    score = min(1.0, (count / n) * 2.0)
    return score


def _comma_consistency_score(sentences: list[str]) -> float:
    """
    Low coefficient of variation in comma counts → high AI score.
    CV = std / mean; score = max(0, 1 - CV).
    Returns 0.5 when fewer than 2 sentences or mean comma count is 0.
    """
    if len(sentences) < 2:
        return 0.5

    counts = [s.count(",") for s in sentences]
    mean = sum(counts) / len(counts)
    if mean == 0:
        return 0.5

    variance = sum((c - mean) ** 2 for c in counts) / len(counts)
    std = math.sqrt(variance)
    cv = std / mean
    return max(0.0, 1.0 - cv)


def classify(text: str) -> dict:
    """
    Returns {"score": float, "details": dict}.
    Score is in [0.0, 1.0] where 1.0 = likely AI-generated.
    """
    sentences = _split_sentences(text)

    transition_score = _transition_density_score(text, sentences)
    comma_score = _comma_consistency_score(sentences)

    combined = (transition_score + comma_score) / 2.0
    combined = max(0.0, min(1.0, combined))

    return {
        "score": round(combined, 4),
        "details": {
            "transition_density_score": round(transition_score, 4),
            "comma_consistency_score": round(comma_score, 4),
        },
    }
