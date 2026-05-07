from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import json
import re

app = Flask(__name__)
CORS(app)

# Groq setup — replace with your key
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

issue_store = []

def check_duplicate_with_ai(new_title, new_desc, existing_issues):
    existing_text = "\n".join([
        f"#{iss['issueNumber']}: title='{iss['title']}' description='{iss['description']}'"
        for iss in existing_issues
    ])

    prompt = f"""You are a duplicate issue detector. Check if the NEW ISSUE is a duplicate of any EXISTING ISSUE.

EXISTING ISSUES:
{existing_text}

NEW ISSUE:
title='{new_title}'
description='{new_desc}'

Rules:
- Compare BOTH title AND description MEANING together
- "blade broken" and "blade has an issue" = SAME MEANING = duplicate
- "fan" + "blade broken" vs "fan" + "wire issue" = DIFFERENT = not duplicate
- Focus on meaning not exact words
- Same problem described differently = duplicate

Reply ONLY valid JSON no markdown:
{{"isDuplicate": true, "matchedIssueNumber": 1, "matchedIssueTitle": "title", "reason": "reason"}}"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=200
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    return json.loads(raw.strip())


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
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
