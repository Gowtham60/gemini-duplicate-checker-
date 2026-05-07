from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
import json

app = Flask(__name__)
CORS(app)

# Gemini setup
GEMINI_API_KEY = "AIzaSyAJaHYPi4VCd94kjUpM_iCOFbcGLSkzTeA"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# In-memory store — all raised issues
issue_store = []

def check_duplicate_with_ai(new_title, new_desc, existing_issues):
    """Ask Gemini AI if new issue is duplicate of any existing issue."""

    existing_text = "\n".join([
        f"Issue #{i+1}: Title='{iss['title']}', Description='{iss['description']}'"
        for i, iss in enumerate(existing_issues)
    ])

    prompt = f"""You are a duplicate issue detector for a product issue tracker.

Check if the NEW ISSUE is a duplicate or semantically similar to any EXISTING ISSUE.

Rules:
- Compare BOTH title AND description together
- "blade broken" and "blade has an issue" = SAME MEANING = duplicate
- "fan" + "blade broken" vs "fan" + "wire issue" = DIFFERENT = not duplicate
- Minor wording differences don't matter — focus on meaning
- Same product problem described differently = duplicate

EXISTING ISSUES:
{existing_text}

NEW ISSUE:
Title: '{new_title}'
Description: '{new_desc}'

Respond ONLY with valid JSON, no markdown, no explanation:
{{"isDuplicate": true or false, "matchedIssueNumber": null or number, "matchedIssueTitle": null or string, "reason": "one sentence explanation"}}"""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Clean markdown if any
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


@app.route("/raise-issue", methods=["POST"])
def raise_issue():
    data = request.get_json()
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    # No existing issues → not duplicate, just save
    if not issue_store:
        new_issue = {
            "id": str(len(issue_store) + 1),
            "issueNumber": len(issue_store) + 1,
            "title": title,
            "description": description
        }
        issue_store.append(new_issue)
        return jsonify({
            "isDuplicate": False,
            "similarityScore": 0,
            "matchedIssueId": None,
            "matchedIssueTitle": None,
            "message": None
        })

    # Ask Gemini AI
    try:
        result = check_duplicate_with_ai(title, description, issue_store)
    except Exception as e:
        return jsonify({"error": f"AI check failed: {str(e)}"}), 500

    if result.get("isDuplicate"):
        matched_num = result.get("matchedIssueNumber")
        matched_title = result.get("matchedIssueTitle", "")
        return jsonify({
            "isDuplicate": True,
            "similarityScore": 1.0,
            "matchedIssueId": str(matched_num),
            "matchedIssueTitle": matched_title,
            "message": f"This issue has already been raised (#{matched_num}: {matched_title})"
        })

    # Not duplicate — save to memory
    new_issue = {
        "id": str(len(issue_store) + 1),
        "issueNumber": len(issue_store) + 1,
        "title": title,
        "description": description
    }
    issue_store.append(new_issue)

    return jsonify({
        "isDuplicate": False,
        "similarityScore": 0,
        "matchedIssueId": None,
        "matchedIssueTitle": None,
        "message": None
    })


@app.route("/issues", methods=["GET"])
def get_issues():
    return jsonify({"count": len(issue_store), "issues": issue_store})


@app.route("/reset", methods=["DELETE"])
def reset_issues():
    issue_store.clear()
    return jsonify({"message": "All issues cleared"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "issueCount": len(issue_store)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
