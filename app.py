from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
import json
import re

app = Flask(__name__)
CORS(app)

# Gemini setup
GEMINI_API_KEY = "AIzaSyDqhF5cOc2u0olu-i6w8hLBFX1dTV8z5Z4"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

issue_store = []

def check_duplicate_with_ai(new_title, new_desc, existing_issues):
    existing_text = "\n".join([
        f"Issue #{iss['issueNumber']}: Title='{iss['title']}', Description='{iss['description']}'"
        for iss in existing_issues
    ])
    prompt = f"""You are a duplicate issue detector.
Check if the NEW ISSUE is duplicate or semantically similar to any EXISTING ISSUE.
Rules:
- Compare BOTH title AND description meaning together
- "blade broken" and "blade has an issue" = SAME MEANING = duplicate
- "fan" + "blade broken" vs "fan" + "wire issue" = DIFFERENT = not duplicate
- Focus on meaning, not exact words
EXISTING ISSUES:
{existing_text}
NEW ISSUE:
Title: '{new_title}'
Description: '{new_desc}'
Reply ONLY with JSON (no markdown):
{{"isDuplicate": true, "matchedIssueNumber": 1, "matchedIssueTitle": "title", "reason": "reason"}}"""

    response = model.generate_content(prompt)
    raw = response.text.strip()
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
            return jsonify({"isDuplicate": False, "similarityScore": 0, "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

        if not issue_store:
            issue_store.append({"id": "1", "issueNumber": 1, "title": title, "description": description})
            return jsonify({"isDuplicate": False, "similarityScore": 0, "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

        try:
            result = check_duplicate_with_ai(title, description, issue_store)
        except Exception as ai_err:
            print(f"AI ERROR: {ai_err}")
            issue_store.append({"id": str(len(issue_store)+1), "issueNumber": len(issue_store)+1, "title": title, "description": description})
            return jsonify({"isDuplicate": False, "similarityScore": 0, "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

        if result.get("isDuplicate"):
            mn = result.get("matchedIssueNumber")
            mt = result.get("matchedIssueTitle", "")
            return jsonify({"isDuplicate": True, "similarityScore": 1.0, "matchedIssueId": str(mn), "matchedIssueTitle": mt, "message": f"This issue has already been raised (#{mn}: {mt})"})

        issue_store.append({"id": str(len(issue_store)+1), "issueNumber": len(issue_store)+1, "title": title, "description": description})
        return jsonify({"isDuplicate": False, "similarityScore": 0, "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

    except Exception as e:
        print(f"SERVER ERROR: {e}")
        return jsonify({"isDuplicate": False, "similarityScore": 0, "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

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
