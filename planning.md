# Provenance Guard — Planning Doc

Use this file to record your design decisions as you work through the project.
There are no wrong answers — write enough that you could explain your reasoning to another group.

---

## Detection Signals

**Signal 1: Groq LLM (`llama-3.3-70b-versatile`):**
This signal captures semantic and stylistic coherence holistically by asking the model to assess whether the text reads as human or AI-generated. Output is a score between 0.0 and 1.0.

Exact system prompt used:
```
You are an expert at distinguishing human-written text from AI-generated text.

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
Do not include any text outside the JSON object.
```

`temperature=0.1` is used for scoring consistency. If the Groq API is unavailable, this signal **fails closed** to `0.5` (neutral/uncertain) so the submission can still be processed using Signals 2 and 3. A `"warning"` field is added to the response when this fallback is active.

**Signal 2: Stylometric Heuristics:**
This signal measures structural and statistical properties of the text. We compute sentence length variance and type-token ratio (vocabulary diversity). Output is a normalized score between 0.0 and 1.0.

**Signal 3: Punctuation & Transition Patterns (Stretch — Ensemble Detection):**
This signal measures two surface-level patterns that AI models produce reliably:

1. **Transition phrase density** — AI text frequently uses discourse connectives ("however", "therefore", "furthermore", "moreover", "consequently", "notably", etc.) at higher rates than human writing. Measured as transition words per sentence, normalized to [0, 1] (capped at 0.5 per sentence = score 1.0).

2. **Comma consistency** — AI text applies commas with metronomic regularity. We compute the coefficient of variation (std / mean) of comma counts across sentences; low variation → high AI score. Returns 0.5 when fewer than 2 sentences or mean comma count is 0.

Both sub-signals are normalized to [0.0, 1.0] and averaged into Signal 3's final score.

**Combination Logic:**
All three signal scores are averaged (equal weight) to produce a single, unified confidence score between 0.0 and 1.0.

**Why three independent signals?**
Each signal operates on a different dimension of the text:
- Signal 1 reads *meaning and voice* (semantic layer)
- Signal 2 reads *word and sentence statistics* (structural layer)
- Signal 3 reads *punctuation and discourse patterns* (surface layer)

Because they measure different properties, they are unlikely to fail in the same direction at the same time. A text that fools the LLM with natural-sounding phrasing will still show low sentence-length variance and high transition-word density if it was AI-generated. Equal weighting reflects the absence of evidence that any one signal is more reliable than the others.

**Boundary rules and known failure modes:**

| Input type | Likely failure | Why |
|---|---|---|
| Formal academic human writing | False positive (scored AI) | High transition density + uniform sentence structure matches AI patterns |
| Lightly edited AI output | Uncertain (mid-range) | LLM detects AI traces; stylometrics sees human edits → signals disagree |
| Short text (< 2 sentences) | Signal 2 returns 0.5 | Cannot compute sentence variance; defaults to neutral |
| Highly repetitive poetry | False positive | Low vocabulary diversity + uniform line length |

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
When a piece of text is submitted via `POST /submit`, it is processed through all three signals in sequence. Signals 2 and 3 are pure Python and never fail. Signal 1 (Groq) fails closed to a neutral score of 0.5 if the API is unavailable, so the system always produces a result. The three scores are averaged into a single confidence score, mapped to a transparency label, and saved to the SQLite audit log. If a creator contests the label via `POST /appeal`, the system updates the record's status to "under_review" and appends the reasoning for human review.

**Diagram:**
```text
[Submission Flow]
POST /submit
  ├─ Signal 1: Groq LLM          (fails closed → 0.5 if API unavailable)
  ├─ Signal 2: Stylometrics      (pure Python, always returns)
  └─ Signal 3: Punctuation       (pure Python, always returns)
        ↓
  Equal-weighted average → confidence score
        ↓
  Label mapping → transparency label
        ↓
  SQLite audit log → JSON response

[Appeal Flow]
POST /appeal → Lookup → Status: "under_review" → Audit Log → JSON response

[Read-only]
GET /log         → full audit log (newest first)
GET /analytics   → aggregate statistics
GET /certificate → single-submission provenance document
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

## Provenance Certificate (Stretch Goal)

**Endpoint:** `GET /certificate/<content_id>`

**Purpose:**
Returns a self-contained, shareable document that summarizes the full classification record for a single submission. A creator can present this as evidence of the system's decision — including the signals used, the confidence score, and the issued label — or a reviewer can use it to audit the decision.

**What it contains:**

| Field | Description |
|-------|-------------|
| `certificate_id` | Same as `content_id` — globally unique identifier for this record |
| `issued_at` | Timestamp from the original submission (`created_at`) |
| `creator_id` | Submitted creator identifier |
| `status` | Current review status (`reviewed` or `under_review`) |
| `verdict.attribution` | Final attribution label |
| `verdict.confidence_score` | Combined score across all signals |
| `verdict.transparency_label` | Human-readable label text |
| `signals` | Individual scores for groq_llm, stylometrics, and punctuation |
| `appeal` | Appeal fields if the record has been contested, otherwise `null` |

**Design note:**
No new database tables or columns are required. The certificate is assembled at request time from the existing `submissions` row.

---

## Analytics Dashboard (Stretch Goal)

**Endpoint:** `GET /analytics`

**What it returns:**
Aggregate statistics computed live from the audit log — no separate store needed.

| Field | Description |
|-------|-------------|
| `total_submissions` | Count of all records in the audit log |
| `label_distribution` | Count + percentage for each attribution label |
| `average_confidence_score` | Mean `combined_score` across all submissions |
| `signal_averages` | Mean score for each of the three signals |
| `appeal_count` | Number of submissions currently under review |
| `appeal_rate_pct` | `appeal_count / total_submissions * 100` |

All values computed with SQLite aggregate functions — no additional dependency.

---

## Appeals Workflow — Additional Fields

Beyond the required `content_id` and `creator_reasoning`, the `/appeal` endpoint also captures:
- `appeal_type`: categorizes the appeal as `false_positive` or `technical_error`
- `contact_email`: allows a human reviewer to follow up with the creator directly

---

## Implementation Notes

**Signal disagreement examples (observed during testing):**

| Input | groq_llm | stylometrics | punctuation | combined | Label |
|---|---|---|---|---|---|
| Dense transition-word AI paragraph | 0.90 | 0.44 | 1.00 | 0.78 | AI-generated |
| Casual sourdough story | 0.20 | 0.51 | 0.25 | 0.32 | Uncertain |
| Formal human writing (non-native speaker) | 0.80 | 0.42 | — | 0.61 | Uncertain |
| Short casual human text | 0.20 | 0.40 | — | 0.20 | Human-written |

**What surprised us during testing:**

1. *Signal independence confirmed by disagreement.* The AI-sounding governance paragraph scored `groq_llm=0.9` but only `stylometrics=0.44`. This is the correct behavior — stylometrics correctly detected vocabulary diversity in the long passage that pulled the score down. The combined score of 0.78 is more conservative than the LLM alone would produce.

2. *Short texts default to Uncertain.* A casual 4-sentence human text scored `stylometrics=0.51` because too-few sentences prevent meaningful variance computation (returns 0.5). The fallback is intentionally neutral — it avoids confident misclassification on thin evidence.

3. *False positives on formal writing.* A submission from a non-native English speaker writing in formal style scored `groq_llm=0.8` despite being human-written. This is the documented limitation of Signal 1 and the primary motivation for having an appeals workflow. The confidence score (0.61) correctly landed in "Uncertain" rather than "AI-generated", demonstrating the asymmetric threshold design (>0.70 required for the stronger label).

4. *Rate limit fires correctly.* With 10 requests per minute enforced, the 10th in-window request triggers 429. Earlier requests in the same minute count toward the limit, which is the expected behavior — the window is sliding, not per-batch.

**Why asymmetric thresholds?**
Falsely accusing a human writer is a worse outcome than failing to detect AI-generated text. We therefore require a score above 0.70 (not just above 0.50) before issuing the "AI-generated" label. The 0.30–0.70 "Uncertain" band is intentionally wide — the system communicates genuine ambiguity rather than forcing a binary verdict when evidence is mixed.
