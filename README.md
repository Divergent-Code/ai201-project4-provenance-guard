# Provenance Guard

A Flask REST API that classifies submitted text as AI-generated or human-written using three independent detection signals, issues transparency labels, enforces rate limiting, and maintains a structured audit log with an appeals workflow.

---

## Setup

**Requirements:** Python 3.10+

```bash
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Add your Groq API key
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_key_here

# Run the server
python app.py
```

The server starts at `http://localhost:5000`.

---

## Detection Signals

Provenance Guard combines three independent signals into a single confidence score. Each signal returns a value in `[0.0, 1.0]` where `1.0 = likely AI-generated`. The final score is their equal-weighted average.

### Signal 1 — Groq LLM (Semantic)
Sends the text to `llama-3.3-70b-versatile` with a structured prompt asking it to score how AI-like the text reads. Focuses on semantic coherence uniformity, formulaic phrasing, absence of personal voice, and structural repetition. `temperature=0.1` for consistent scoring.

### Signal 2 — Stylometric Heuristics (Structural)
Two sub-signals averaged together:
- **Sentence length variance** — AI text has unnaturally uniform sentence lengths (low standard deviation). Normalized so `std=0 → 1.0`, `std≥20 → 0.0`.
- **Type-token ratio (TTR)** — AI text reuses vocabulary more predictably. Score = `1.0 - (unique_tokens / total_tokens)`.

### Signal 3 — Punctuation & Transition Patterns (Ensemble)
Two sub-signals averaged together:
- **Transition phrase density** — AI text overuses discourse connectives ("however", "therefore", "furthermore", etc.). Normalized so ≥0.5 connectives per sentence → `1.0`.
- **Comma consistency** — AI text places commas with metronomic regularity. Measured as `1.0 - coefficient_of_variation` of comma counts across sentences.

### Confidence Score → Transparency Label

| Score | Attribution | Label |
|-------|-------------|-------|
| > 0.70 | AI-generated | "This content shows strong indicators of AI generation based on its style and structure." |
| 0.30 – 0.70 | Uncertain | "This content's origin is unclear — it has mixed signals of both human and AI writing." |
| < 0.30 | Human-written | "This content shows strong indicators of human authorship." |

---

## API Endpoints

### `POST /submit`

Classifies a piece of text. Rate limited to **10 requests per minute / 100 per day** per IP.  
**Reasoning:** 10 requests per minute allows a creator to submit a batch of chapters sequentially, but stops aggressive automated flooding. 100 per day comfortably covers a high-volume platform user while capping API cost exposure.

**Request:**
```json
{
  "creator_id": "user-123",
  "text": "Your content here.",
  "content_type": "text" 
}
```
*Note on Multi-Modal Support:* `content_type` defaults to `"text"`. If set to `"image_description"`, the system bypasses structural stylometric heuristics (which require paragraph-length prose) and scores the image caption using semantic and punctuation signals.

**Response `200`:**
```json
{
  "content_id": "e7b26fcd-351d-473d-a33f-71ebeab09dc2",
  "attribution": "AI-generated",
  "confidence_score": 0.7785,
  "transparency_label": "This content shows strong indicators of AI generation based on its style and structure.",
  "signals": {
    "groq_llm": 0.9,
    "stylometrics": 0.4355,
    "stylometrics_detail": {
      "sentence_variance_score": 0.3333,
      "type_token_ratio_score": 0.5377
    },
    "punctuation": 1.0,
    "punctuation_detail": {
      "transition_density_score": 1.0,
      "comma_consistency_score": 1.0
    }
  }
}
```

**Response `429` (rate limit exceeded):**
```json
{
  "error": "Rate limit exceeded. You may submit up to 10 pieces of content per minute and 100 per day.",
  "retry_after": "..."
}
```

---

### `POST /appeal`

Contest a classification. Updates the submission's status to `under_review` and logs the creator's reasoning.

**Request:**
```json
{
  "content_id": "e7b26fcd-351d-473d-a33f-71ebeab09dc2",
  "creator_reasoning": "I wrote this myself. My formal style may read as AI-generated.",
  "appeal_type": "false_positive",
  "contact_email": "writer@example.com"
}
```

- `appeal_type`: `"false_positive"` or `"technical_error"`
- `contact_email`: optional — allows a human reviewer to follow up

**Response `200`:**
```json
{
  "message": "Appeal received. Your content has been flagged for human review.",
  "content_id": "e7b26fcd-351d-473d-a33f-71ebeab09dc2",
  "status": "under_review",
  "appeal_type": "false_positive"
}
```

**Response `404`:** Content ID not found.  
**Response `409`:** Appeal already under review.

---

### `POST /verify`

Allows a creator to submit drafting evidence (e.g., a time-lapse hash) to earn a "Verified Human" credential, changing their transparency label on the provenance certificate.

**Request:**
```json
{
  "content_id": "e7b26fcd-351d-473d-a33f-71ebeab09dc2",
  "draft_history_hash": "a1b2c3d4e5f6..."
}
```

**Response `200`:**
```json
{
  "message": "Content successfully verified via drafting evidence.",
  "content_id": "e7b26fcd-351d-473d-a33f-71ebeab09dc2",
  "is_verified": true
}
```

---

### `GET /log`

Returns the full audit log, newest first.

**Query params:** `?limit=N` (default 50)

**Response `200`:**
```json
{
  "count": 18,
  "entries": [
    {
      "id": "e7b26fcd-...",
      "creator_id": "test-s3-ai",
      "attribution": "AI-generated",
      "combined_score": 0.7785,
      "signal1_score": 0.9,
      "signal2_score": 0.4355,
      "signal3_score": 1.0,
      "label": "This content shows strong indicators of AI generation...",
      "status": "reviewed",
      "appeal_reasoning": null,
      "appeal_type": null,
      "contact_email": null,
      "created_at": "2026-06-25 01:15:00"
    }
  ]
}
```

---

### `GET /analytics`

Aggregate statistics over the full audit log.

**Response `200`:**
```json
{
  "total_submissions": 18,
  "average_confidence_score": 0.5629,
  "signal_averages": {
    "groq_llm": 0.6333,
    "stylometrics": 0.482,
    "punctuation": 0.625
  },
  "label_distribution": {
    "AI-generated":  { "count": 2,  "pct": 11.1 },
    "Uncertain":     { "count": 14, "pct": 77.8 },
    "Human-written": { "count": 2,  "pct": 11.1 }
  },
  "appeal_count": 1,
  "appeal_rate_pct": 5.6
}
```

---

### `GET /certificate/<content_id>`

Returns a self-contained provenance certificate for a single submission — suitable for sharing as evidence of the system's classification decision.

**Response `200`:**
```json
{
  "certificate_id": "bd526b20-6eeb-46bf-8cf1-665c0926453c",
  "issued_at": "2026-06-24 23:51:53",
  "creator_id": "test-ai-1",
  "status": "under_review",
  "is_verified": true,
  "verdict": {
    "attribution": "Uncertain",
    "confidence_score": 0.6111,
    "transparency_label": "✓ Verified Human-written"
  },
  "signals": {
    "groq_llm": 0.8,
    "stylometrics": 0.4222,
    "punctuation": 0.4111
  },
  "appeal": {
    "appeal_type": "false_positive",
    "creator_reasoning": "I wrote this myself. I am a non-native English speaker...",
    "contact_email": "writer@example.com"
  }
}
```

`"appeal"` is `null` when no appeal has been filed.

**Response `404`:** Content ID not found.

---

## Known Limitations

**Highly Stylized Poetry / Prose:** Repetitive poetry or highly stylized prose with unnatural, short sentences and low vocabulary diversity may trigger a false positive. This is because the stylometric signal expects natural variance; highly structured writing mimics the statistical uniformity of AI text.

---

## Architecture

```
POST /submit
  └─ Signal 1: Groq LLM (groq_classifier.py)
  └─ Signal 2: Stylometrics (stylometrics.py)
  └─ Signal 3: Punctuation patterns (punctuation.py)
  └─ Equal-weighted average → confidence score
  └─ Label mapping → transparency label
  └─ SQLite audit log (database.py)
  └─ JSON response

POST /appeal
  └─ Lookup submission by content_id
  └─ Update status → "under_review"
  └─ Append reasoning, appeal_type, contact_email
  └─ JSON response

GET /log         → full audit log (newest first)
GET /analytics   → aggregate statistics over all submissions
GET /certificate/<id> → single-submission provenance document
```

**Storage:** SQLite (`audit.db`) via Python's built-in `sqlite3`. Single `submissions` table with schema migration on startup for backward compatibility.

---

## AI Tool Plan

**M3 — Submission Endpoint + Signal 1:**
I provided the Detection Signals section and Architecture diagram to an AI tool to generate a Flask app skeleton with `POST /submit` and the Groq LLM classifier. Verified by submitting AI-sounding text (`confidence_score: 0.8`, attribution: `AI-generated`) and casual human text (`confidence_score: 0.2`, attribution: `Human-written`).

**M4 — Signal 2 + Confidence Scoring:**
I provided the Uncertainty Representation table to generate the stylometric heuristic function (sentence length variance + type-token ratio) and the score-averaging logic. I manually revised the stylometric heuristic function to explicitly cap the normalized scores between 0.0 and 1.0, because the AI-generated code originally allowed scores > 1.0 on extremely long sentences. Verified by testing four inputs spanning all three label variants and confirming the two signals disagree on ambiguous cases — demonstrating genuine independence.

**M5 — Production Layer:**
I provided the Appeals Workflow and Transparency Labels sections to generate the label mapping function, `POST /appeal` endpoint, and Flask-Limiter integration. I had to manually override the Flask-Limiter configuration to use `storage_uri="memory://"` to prevent startup warnings. Verified all label variants, confirmed 429 response at the rate limit, and completed an end-to-end appeal test showing the audit log entry updating to `status: "under_review"`.

**Stretch — Ensemble Detection (Signal 3):**
I designed the punctuation/transition-pattern signal independently (two sub-signals: transition phrase density and comma coefficient of variation) and had the AI tool implement it following the same interface contract as Signals 1 and 2. Verified by contrasting a transition-word-heavy AI paragraph (`punctuation: 1.0`) against casual human text (`punctuation: 0.25`).

**Stretch — Analytics + Provenance Certificate:**
I specified the exact aggregate fields for `GET /analytics` and the certificate schema for `GET /certificate/<id>`, then had the AI tool implement the SQLite aggregate query and route handlers. Both were verified against the live audit log.

---

## Spec Reflection

- **How the spec helped:** Designing the specific thresholds and label variants upfront in `planning.md` made the implementation of the transparency labels trivial and prevented UX guesswork.
- **Where we diverged:** The original architecture only specified two signals (LLM and Stylometrics). During implementation, we added a third independent signal (Punctuation/Transition Patterns) to fulfill the Ensemble Detection stretch goal. We also added an `is_verified` state to the database and a `POST /verify` endpoint to support the Provenance Certificate verification stretch goal.
