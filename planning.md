# Provenance Guard — Planning Doc

Use this file to record your design decisions as you work through the project.
There are no wrong answers — write enough that you could explain your reasoning to another group.

---

## Detection Signals

**Signal 1: Groq LLM (`llama-3.3-70b-versatile`):**
This signal captures semantic and stylistic coherence holistically by asking the model to assess whether the text reads as human or AI-generated. Output is a score between 0.0 and 1.0.

**Signal 2: Stylometric Heuristics:**
This signal measures structural and statistical properties of the text. We compute sentence length variance and type-token ratio (vocabulary diversity). Output is a normalized score between 0.0 and 1.0.

**Signal 3: Punctuation & Transition Patterns (Stretch — Ensemble Detection):**
This signal measures two surface-level patterns that AI models produce reliably:

1. **Transition phrase density** — AI text frequently uses discourse connectives ("however", "therefore", "furthermore", "moreover", "consequently", "notably", etc.) at higher rates than human writing. Measured as transition words per sentence, normalized to [0, 1] (capped at 0.5 per sentence = score 1.0).

2. **Comma consistency** — AI text applies commas with metronomic regularity. We compute the coefficient of variation (std / mean) of comma counts across sentences; low variation → high AI score. Returns 0.5 when fewer than 2 sentences or mean comma count is 0.

Both sub-signals are normalized to [0.0, 1.0] and averaged into Signal 3's final score.

**Combination Logic:**
All three signal scores are averaged (equal weight) to produce a single, unified confidence score between 0.0 and 1.0.

**What do these signals miss?**
The LLM signal may incorrectly flag highly formal or formulaic human writing (e.g., legal texts) as AI. The stylometric signal may incorrectly flag human writing that has been heavily edited for uniformity or brevity. The punctuation signal may over-flag academic human writing that also uses many transition words.

---

## Uncertainty Representation & Labels

A confidence score of 0.6 means the system detects some AI-like characteristics but lacks the definitive markers of either pure AI generation or completely natural human writing. It represents genuine uncertainty.

| Confidence Score Range | Transparency Label Text | What it means |
|-------|----------------|---------------------|
| > 0.70 | "Likely AI-generated" | Strong semantic and structural indicators of AI origin. |
| 0.30 - 0.70 | "Uncertain origin" | Conflicting signals or mild indicators, leaning ambiguous. |
| < 0.30 | "Likely human-written" | High vocabulary diversity and natural structural variance. |

**How do we handle false positives?**
Because falsely accusing a human writer is a worse outcome than missing an AI-generated text, we reserve the definitive "Likely AI-generated" label for only high-confidence scores (> 0.70) and provide a clear appeals workflow.

---

## Appeals Workflow

**Who can submit?**
Any creator who receives a classification they believe is inaccurate.

**What information is provided?**
The `content_id` and a `creator_reasoning` text field explaining why the classification is incorrect.

**System Action:**
The system updates the content's status to `"under_review"` and logs the appeal alongside the original classification decision in the audit log.

**What does the human reviewer see?**
The original text, the individual signal scores, the combined confidence score, the issued label, and the creator's written reasoning.

---

## Anticipated Edge Cases

| Scenario | Anticipated Score | Why it handles it poorly |
|-------|-----------------|-------------------|
| Highly repetitive, stylized poetry | High (AI) | Scores very high on stylometric heuristics due to low sentence length variance and low vocabulary diversity. |
| Lightly edited AI output | Mid (Uncertain) | The LLM detects semantic AI traces, while the stylometric signal sees human edits, causing conflicting scores. |

---

## Architecture

**Narrative:**
When a piece of text is submitted via `POST /submit`, it is processed through the Groq LLM and Stylometric Heuristics signals. Both return independent scores, averaged into a single confidence score. This score maps to a transparency label ("Likely AI-generated", "Uncertain origin", or "Likely human-written"). The decision is saved to an SQLite Audit Log before returning the response. If a creator contests the label via `POST /appeal`, the system locates the submission in the Audit Log, updates its status to "under_review", and appends the reasoning.

**Diagram:**
```text
[Submission Flow]
POST /submit → Groq LLM & Stylometrics → Confidence Scoring → Label Mapping → Audit Log → JSON Response

[Appeal Flow]
POST /appeal → Status Update ("under_review") → Audit Log → JSON Response
```

---

## AI Tool Plan

**M3 (Submission Endpoint + First Signal):**
I provided the Detection Signals section and Architecture diagram to an AI tool to generate a Flask app skeleton containing the `POST /submit` route and the Groq LLM signal function. Verified by running two test submissions:
- AI-sounding text → `confidence_score: 0.8`, attribution: `"AI-generated"` ✓
- Casual human text → `confidence_score: 0.2`, attribution: `"Human-written"` ✓

**M4 (Second Signal + Confidence Scoring):**
I will provide the Uncertainty Representation section to generate the stylometric heuristic function (sentence length variance + type-token ratio) and the averaging logic. I will verify it by testing a clearly AI-generated paragraph and a clearly human-written paragraph to ensure meaningful score variation across both signals.

**M5 (Production Layer):**
I will provide the Appeals Workflow and Transparency Labels to generate the label mapping, `POST /appeal` endpoint, and Flask-Limiter integration. I will verify by running PowerShell `Invoke-RestMethod` commands to reach all label variants and confirm the rate limit 429 response.

---

## Appeals Workflow — Additional Fields

Beyond the required `content_id` and `creator_reasoning`, the `/appeal` endpoint also captures:
- `appeal_type`: categorizes the appeal as `false_positive` or `technical_error`
- `contact_email`: allows a human reviewer to follow up with the creator directly
