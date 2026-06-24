import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from database import fetch_log, init_db, insert_submission
from signals.groq_classifier import classify as groq_classify

load_dotenv()

app = Flask(__name__)
init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attribution_label(score: float) -> tuple[str, str]:
    """Return (attribution, label_text) for a combined confidence score."""
    if score > 0.70:
        return (
            "AI-generated",
            "This content shows strong indicators of AI generation based on its style and structure.",
        )
    elif score >= 0.30:
        return (
            "Uncertain",
            "This content's origin is unclear — it has mixed signals of both human and AI writing.",
        )
    else:
        return (
            "Human-written",
            "This content shows strong indicators of human authorship.",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True)
    if not data or "text" not in data or "creator_id" not in data:
        return jsonify({"error": "Request must include 'text' and 'creator_id'."}), 400

    text: str = data["text"].strip()
    creator_id: str = data["creator_id"]

    if not text:
        return jsonify({"error": "'text' must not be empty."}), 400

    # --- Signal 1: Groq LLM ---
    try:
        groq_result = groq_classify(text)
        signal1_score = groq_result["score"]
    except Exception as e:
        return jsonify({"error": f"Signal 1 (Groq) failed: {str(e)}"}), 502

    # Combined score is just Signal 1 for now (Signal 2 added in Phase 3)
    combined_score = signal1_score
    attribution, label_text = _attribution_label(combined_score)

    content_id = str(uuid.uuid4())

    insert_submission({
        "id": content_id,
        "creator_id": creator_id,
        "text": text,
        "signal1_score": signal1_score,
        "combined_score": combined_score,
        "attribution": attribution,
        "label": label_text,
        "status": "reviewed",
    })

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence_score": round(combined_score, 4),
        "transparency_label": label_text,
        "signals": {
            "groq_llm": round(signal1_score, 4),
        },
    }), 200


@app.route("/log", methods=["GET"])
def get_log():
    limit = request.args.get("limit", 50, type=int)
    entries = fetch_log(limit=limit)
    return jsonify({"count": len(entries), "entries": entries}), 200


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
