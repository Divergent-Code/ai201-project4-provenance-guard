import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from database import fetch_analytics, fetch_log, fetch_submission, init_db, insert_submission, update_appeal
from signals.groq_classifier import classify as groq_classify
from signals.punctuation import classify as punct_classify
from signals.stylometrics import classify as stylo_classify

load_dotenv()

app = Flask(__name__)
init_db()

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


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
@limiter.limit("10 per minute; 100 per day")
def submit():
    data = request.get_json(silent=True)
    if not data or "text" not in data or "creator_id" not in data:
        return jsonify({"error": "Request must include 'text' and 'creator_id'."}), 400

    text: str = data["text"].strip()
    creator_id: str = data["creator_id"]

    if not text:
        return jsonify({"error": "'text' must not be empty."}), 400

    # --- Signal 1: Groq LLM (semantic) ---
    groq_degraded = False
    try:
        groq_result = groq_classify(text)
        signal1_score = groq_result["score"]
    except Exception:
        signal1_score = 0.5
        groq_degraded = True

    # --- Signal 2: Stylometric heuristics (structural) ---
    stylo_result = stylo_classify(text)
    signal2_score = stylo_result["score"]

    # --- Signal 3: Punctuation & transition patterns ---
    punct_result = punct_classify(text)
    signal3_score = punct_result["score"]

    # Combined score: equal-weighted average of all three signals
    combined_score = round((signal1_score + signal2_score + signal3_score) / 3.0, 4)
    attribution, label_text = _attribution_label(combined_score)

    content_id = str(uuid.uuid4())

    insert_submission({
        "id": content_id,
        "creator_id": creator_id,
        "text": text,
        "signal1_score": signal1_score,
        "signal2_score": signal2_score,
        "signal3_score": signal3_score,
        "combined_score": combined_score,
        "attribution": attribution,
        "label": label_text,
        "status": "reviewed",
    })

    response = {
        "content_id": content_id,
        "attribution": attribution,
        "confidence_score": combined_score,
        "transparency_label": label_text,
        "signals": {
            "groq_llm": round(signal1_score, 4),
            "stylometrics": round(signal2_score, 4),
            "stylometrics_detail": stylo_result["details"],
            "punctuation": round(signal3_score, 4),
            "punctuation_detail": punct_result["details"],
        },
    }
    if groq_degraded:
        response["warning"] = "Signal 1 (Groq) unavailable. Score computed from stylometric and punctuation signals only; groq_llm defaulted to 0.5."
    return jsonify(response), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required."}), 400

    content_id = data.get("content_id", "").strip()
    creator_reasoning = data.get("creator_reasoning", "").strip()

    if not content_id or not creator_reasoning:
        return jsonify({"error": "Both 'content_id' and 'creator_reasoning' are required."}), 400

    appeal_type = data.get("appeal_type", "false_positive").strip()
    contact_email = data.get("contact_email", "").strip()

    if appeal_type not in ("false_positive", "technical_error"):
        return jsonify({"error": "'appeal_type' must be 'false_positive' or 'technical_error'."}), 400

    submission = fetch_submission(content_id)
    if not submission:
        return jsonify({"error": f"No submission found for content_id '{content_id}'."}), 404

    if submission["status"] == "under_review":
        return jsonify({"error": "An appeal for this content is already under review."}), 409

    update_appeal(content_id, creator_reasoning, appeal_type, contact_email)

    return jsonify({
        "message": "Appeal received. Your content has been flagged for human review.",
        "content_id": content_id,
        "status": "under_review",
        "appeal_type": appeal_type,
    }), 200


@app.route("/analytics", methods=["GET"])
def get_analytics():
    return jsonify(fetch_analytics()), 200


@app.route("/certificate/<content_id>", methods=["GET"])
def get_certificate(content_id):
    submission = fetch_submission(content_id)
    if not submission:
        return jsonify({"error": f"No submission found for content_id '{content_id}'."}), 404

    appeal = None
    if submission["status"] == "under_review":
        appeal = {
            "appeal_type": submission["appeal_type"],
            "creator_reasoning": submission["appeal_reasoning"],
            "contact_email": submission["contact_email"],
        }

    certificate = {
        "certificate_id": submission["id"],
        "issued_at": submission["created_at"],
        "creator_id": submission["creator_id"],
        "status": submission["status"],
        "verdict": {
            "attribution": submission["attribution"],
            "confidence_score": submission["combined_score"],
            "transparency_label": submission["label"],
        },
        "signals": {
            "groq_llm": submission["signal1_score"],
            "stylometrics": submission["signal2_score"],
            "punctuation": submission["signal3_score"],
        },
        "appeal": appeal,
    }

    return jsonify(certificate), 200


@app.route("/log", methods=["GET"])
def get_log():
    limit = request.args.get("limit", 50, type=int)
    entries = fetch_log(limit=limit)
    return jsonify({"count": len(entries), "entries": entries}), 200


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({
        "error": "Rate limit exceeded. You may submit up to 10 pieces of content per minute and 100 per day.",
        "retry_after": str(e.description),
    }), 429


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
