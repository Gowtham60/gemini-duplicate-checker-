from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import os
import json
import re

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("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", "")
client = Groq(api_key=GROQ_API_KEY)

issue_store = []

def check_duplicate_with_ai(new_title, new_desc, existing_issues):
    existing_text = "\n".join([
        f"#{iss['issueNumber']}: title='{iss['title']}' description='{iss['description']}'"
        for iss in existing_issues
    ])

    prompt = f"""Duplicate issue detector. Check if NEW ISSUE matches any EXISTING ISSUE by meaning.

EXISTING:
{existing_text}

NEW: title='{new_title}' description='{new_desc}'

Rules:
- Same or similar description meaning = duplicate
- "blade broken" = "blade has an issue" = duplicate  
- Different description = not duplicate even if same title

You MUST respond with ONLY this JSON and nothing else:
{{"isDuplicate": true, "matchedIssueNumber": 1, "matchedIssueTitle": "title"}}
or
{{"isDuplicate": false, "matchedIssueNumber": null, "matchedIssueTitle": null}}"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a JSON-only response bot. You only output valid JSON, nothing else. No explanations, no markdown, no code blocks."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=100
    )

    raw = response.choices[0].message.content.strip()
    print(f"AI RAW RESPONSE: {raw}")

    # Extract JSON from response
    # Try direct parse first
    try:
        return json.loads(raw)
    except:
        pass

    # Try finding JSON in the response
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass

    # If all fails - return not duplicate
    print(f"JSON PARSE FAILED for: {raw}")
    return {"isDuplicate": False, "matchedIssueNumber": None, "matchedIssueTitle": None}


@app.route("/raise-issue", methods=["POST"])
def raise_issue():
    try:
        data = request.get_json(force=True)
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()

        if not title:
            return jsonify({"isDuplicate": False, "similarityScore": 0,
                            "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

        # First issue — save directly
        if not issue_store:
            issue_store.append({"id": "1", "issueNumber": 1,
                                "title": title, "description": description})
            return jsonify({"isDuplicate": False, "similarityScore": 0,
                            "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

        # Ask Groq AI
        try:
            result = check_duplicate_with_ai(title, description, issue_store)
        except Exception as ai_err:
            print(f"AI ERROR: {ai_err}")
            issue_store.append({
                "id": str(len(issue_store) + 1),
                "issueNumber": len(issue_store) + 1,
                "title": title,
                "description": description
            })
            return jsonify({"isDuplicate": False, "similarityScore": 0,
                            "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

        if result.get("isDuplicate"):
            mn = result.get("matchedIssueNumber")
            mt = result.get("matchedIssueTitle", "")
            return jsonify({
                "isDuplicate": True,
                "similarityScore": 1.0,
                "matchedIssueId": str(mn),
                "matchedIssueTitle": mt,
                "message": f"This issue has already been raised (#{mn}: {mt})"
            })

        # Not duplicate — save
        issue_store.append({
            "id": str(len(issue_store) + 1),
            "issueNumber": len(issue_store) + 1,
            "title": title,
            "description": description
        })
        return jsonify({"isDuplicate": False, "similarityScore": 0,
                        "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

    except Exception as e:
        print(f"SERVER ERROR: {e}")
        return jsonify({"isDuplicate": False, "similarityScore": 0,
                        "matchedIssueId": None, "matchedIssueTitle": None, "message": None})


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
