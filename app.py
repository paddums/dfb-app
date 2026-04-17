"""
DFB Training Assistant - Backend API
=====================================
A simple RAG (Retrieval-Augmented Generation) server for Dublin Fire Brigade
training content. Reads from the /knowledge folder and answers questions
using the Claude AI API.

To run:  python3 app.py
"""

import os
import json
import re
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import anthropic

# ── Setup ─────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)  # Allow the HTML frontend to talk to this server

BASE_DIR   = Path(__file__).parent
# Support both local layout (knowledge/ subfolder) and flat GitHub upload (files at root)
_knowledge_sub = BASE_DIR / "knowledge"
KNOWLEDGE  = _knowledge_sub if _knowledge_sub.exists() else BASE_DIR
MANIFEST   = KNOWLEDGE / "manifest.json"

# Load the API key from the .env file
def load_api_key():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key and key != "paste-your-key-here":
                    return key
    return os.environ.get("ANTHROPIC_API_KEY")

# ── Knowledge retrieval ────────────────────────────────────────────────────────

def load_manifest():
    with open(MANIFEST, "r", encoding="utf-8") as f:
        return json.load(f)

def find_relevant_chunks(query: str, manifest: dict, max_chunks: int = 2) -> list:
    """
    Simple keyword-based routing: score each chunk by how many query words
    appear in its summary. Returns the top-scoring chunks.
    No vector database needed for a 14-chunk knowledge base.
    """
    # Include short abbreviations (EV, BA, HGV etc) as well as normal words
    query_words = set(re.findall(r'\b\w{2,}\b', query.lower()))

    # Keywords that strongly indicate a particular topic
    TOPIC_HINTS = {
        # ── Breathing Apparatus ──────────────────────────────────────
        "ba":            ["01","02","03","04","05","06"],
        "breathing":     ["01","02","03","04","05","06"],
        "scba":          ["01","02"],
        "propak":        ["01"],
        "bodyguard":     ["02"],
        "pdsu":          ["02"],
        "radio":         ["02"],
        "tetra":         ["02"],
        "torch":         ["02"],
        "cylinder":      ["03"],
        "duration":      ["03"],
        "turnaround":    ["03"],
        "search":        ["04"],
        "casualty":      ["04","26"],
        "lost":          ["04"],
        "withdrawal":    ["04"],
        "flashover":     ["05"],
        "backdraught":   ["05"],
        "combustion":    ["05"],
        "ventilation":   ["06"],
        "ppv":           ["06"],
        # ── Road Traffic Collisions ──────────────────────────────────
        "rtc":           ["07","08","09","10","11","12","13","14"],
        "collision":     ["07","13"],
        "holmatro":      ["08"],
        "winch":         ["08"],
        "tirfor":        ["08"],
        "airbag":        ["09"],
        "srs":           ["09"],
        "electric":      ["10"],
        "ev":            ["10"],
        "hybrid":        ["10"],
        "hydrogen":      ["10"],
        "lpg":           ["10"],
        "hgv":           ["11"],
        "truck":         ["11"],
        "bus":           ["11"],
        "articulated":   ["11"],
        "tractor":       ["12"],
        "forklift":      ["12"],
        "agricultural":  ["12"],
        "tyre":          ["12"],
        "motorway":      ["13"],
        "extrication":   ["14"],
        "stabilise":     ["14"],
        "stabilisation": ["14"],
        "stabilization": ["14"],
        "dash":          ["14"],
        "rip":           ["14"],
        # ── LUKAS battery tools ──────────────────────────────────────
        "lukas":         ["08","15"],
        "ewxt":          ["15"],
        "spreader":      ["08","15"],
        "cutter":        ["08","15"],
        "ram":           ["15"],
        # ── CAFS / Foam ──────────────────────────────────────────────
        "cafs":          ["16","17","18","19","24"],
        "foam":          ["16","17","18","19","23","24"],
        "compressed":    ["16"],
        "dn14a1":        ["17"],
        "dn14a5":        ["18","19"],
        "smartcafs":     ["17","18","19"],
        "lance":         ["19"],
        # ── Pump operations ──────────────────────────────────────────
        "pump":          ["20","21","22","23","24"],
        "hydraulics":    ["20"],
        "friction":      ["20"],
        "centrifugal":   ["21"],
        "priming":       ["21"],
        "relay":         ["23"],
        "hydrant":       ["24"],
        "portable":      ["24"],
        "gauge":         ["22"],
        "flowmeter":     ["22"],
        "branch":        ["22"],
        "monitor":       ["22"],
        # ── Water & Flood Rescue ─────────────────────────────────────
        "water":         ["25","26","27","28","29"],
        "flood":         ["25","28"],
        "swiftwater":    ["27"],
        "swift":         ["27"],
        "drowning":      ["26"],
        "hypothermia":   ["26"],
        "boat":          ["28"],
        "strainer":      ["27"],
        "belay":         ["27"],
        "weir":          ["29"],
        "rope":          ["26","27"],
        "knot":          ["26"],
        "hydrology":     ["25"],
        "river":         ["25","27"],
        "ice":           ["29"],
        "mud":           ["29"],
        "helicopter":    ["29"],
        "rescue":        ["08","14","25","26","27","28","29"],
        # ── Shared ───────────────────────────────────────────────────
        "fire":          ["05","06","16","17","18","19"],
        "battery":       ["09","10","15"],
        "pressure":      ["03","20"],
        "construction":  ["09"],
        "roof":          ["14"],
        "scene":         ["13"],
        "arrival":       ["13"],
        "appraisal":     ["13"],
        "post":          ["14"],
    }

    scores = {}
    for chunk in manifest["chunks"]:
        chunk_id = chunk["file"]
        summary_words = set(re.findall(r'\b\w{3,}\b', chunk["summary"].lower()))

        # Base score: keyword overlap with summary
        summary_words = set(re.findall(r'\b\w{2,}\b', chunk["summary"].lower()))
        score = len(query_words & summary_words)

        # Boost score using topic hints
        for hint_word, relevant_ids in TOPIC_HINTS.items():
            if hint_word in query_words:
                for rel_id in relevant_ids:
                    if chunk_id.startswith(rel_id):
                        score += 5

        scores[chunk_id] = score

    # Sort by score, pick top chunks
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = [file for file, score in ranked[:max_chunks] if score > 0]

    # Fallback: if nothing scored, return the two most relevant by position
    if not top:
        top = [ranked[0][0], ranked[1][0]]

    return top

def load_chunk_content(filename: str) -> str:
    path = KNOWLEDGE / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """Serve the frontend."""
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/topics", methods=["GET"])
def topics():
    """Return one starter question per knowledge source for the welcome screen."""
    STARTER_QUESTIONS = {
        "Breathing Apparatus":       "What is turn-around pressure?",
        "Road Traffic Collisions":   "What are EV hazards at an RTC?",
        "LUKAS Battery Rescue Tools":"How do I operate the LUKAS spreader?",
        "Compressed Air Foam Systems":"How does CAFS extinguish fire?",
        "Fire Pump Operations":      "How do I calculate friction loss?",
        "Water and Flood Rescue":    "What is the technique for a strainer rescue?",
    }
    manifest = load_manifest()
    chips = []
    for source in manifest.get("sources", []):
        topic    = source.get("topic", "")
        question = STARTER_QUESTIONS.get(topic)
        if question:
            chips.append({"topic": topic, "question": question})
    return jsonify({"chips": chips})


@app.route("/health", methods=["GET"])
def health():
    """Simple check that the server is running."""
    return jsonify({"status": "ok", "message": "DFB Training Assistant is running"})

@app.route("/ask", methods=["POST"])
def ask():
    """
    Main endpoint. Receives a question, finds the relevant training content,
    and returns an answer from Claude.
    """
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "Please provide a question."}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400

    # Load API key
    api_key = load_api_key()
    if not api_key:
        return jsonify({"error": "API key not configured. Please check your .env file."}), 500

    # Find and load relevant knowledge chunks
    manifest = load_manifest()
    relevant_files = find_relevant_chunks(question, manifest)
    context_parts = []
    sources_used = []

    for filename in relevant_files:
        content = load_chunk_content(filename)
        if content:
            # Find this chunk's title from the manifest
            chunk_info = next((c for c in manifest["chunks"] if c["file"] == filename), {})
            title = chunk_info.get("file", filename).replace("_", " ").replace(".md", "")
            context_parts.append(f"--- SOURCE: {title} ---\n{content}")
            sources_used.append(filename)

    context = "\n\n".join(context_parts)

    # Build the prompt for Claude
    system_prompt = """You are a training assistant for Dublin Fire Brigade (DFB).
Firefighters check this in the field — answers must be scannable in under 15 seconds.

Always respond with valid JSON using this exact structure:
{
  "answer": "your answer here (markdown supported)",
  "suggestions": ["follow-up question 1", "follow-up question 2", "follow-up question 3"]
}

Answer rules:
- Lead with the key fact — no preamble, no "Great question"
- Use bullet points over prose
- Max 3–4 bullets per section; no long paragraphs
- ⚠️ Safety-critical info always leads if relevant
- Answer based ONLY on the provided training material — do not invent information
- If the answer isn't in the material: one line only — "Not covered here. Check [section]."
- Never pad or summarise at the end

Suggestions: 3 short follow-up questions that can be answered using ONLY the training material provided above — not general firefighting knowledge. Each under 8 words. If fewer than 3 questions are answerable from the material, only include those that are."""

    user_message = f"""Here is the relevant DFB training material:

{context}

---

Question from a DFB member: {question}

Respond with JSON only."""

    # Call Claude API
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        raw = response.content[0].text

        # Strip markdown code fences if Claude wrapped the JSON
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r'^```[a-z]*\n?', '', clean).rstrip('`').strip()

        # Parse structured JSON response
        try:
            parsed      = json.loads(clean)
            answer      = parsed.get("answer", raw)
            suggestions = parsed.get("suggestions", [])
        except (json.JSONDecodeError, AttributeError):
            answer      = raw
            suggestions = []

        return jsonify({
            "answer": answer,
            "sources": sources_used,
            "suggestions": suggestions,
            "question": question
        })

    except anthropic.AuthenticationError:
        return jsonify({"error": "Invalid API key. Please check your .env file."}), 401
    except Exception as e:
        return jsonify({"error": f"Something went wrong: {str(e)}"}), 500


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    api_key = load_api_key()
    if not api_key:
        print("\n⚠️  WARNING: No API key found in .env file.")
        print("   Open the .env file and replace 'paste-your-key-here' with your key.\n")
    else:
        print("\n✅ API key loaded successfully.")

    print("🚒 DFB Training Assistant starting...")
    print("   Open your browser and go to: http://localhost:5001")
    print("   Press CTRL+C to stop the server.\n")
    app.run(debug=False, host="0.0.0.0", port=5001)
