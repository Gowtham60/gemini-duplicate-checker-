from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
import json
import re
import time

app = Flask(__name__)
CORS(app)

# Gemini setup — update key if needed
GEMINI_API_KEY = "AIzaSyDqhF5cOc2u0olu-i6w8hLBFX1dTV8z5Z4"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-lite")

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
- Same or similar description meaning = duplicate (even if wording differs)
- "blade broken" = "blade has an issue" = duplicate
- Different description = not duplicate even if same title

Reply ONLY valid JSON:
{{"isDuplicate": true, "matchedIssueNumber": 1, "matchedIssueTitle": "title"}}
or
{{"isDuplicate": false, "matchedIssueNumber": null, "matchedIssueTitle": null}}"""

    # Retry up to 3 times on rate limit
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            raw = re.sub(r'```json\s*', '', raw)
            raw = re.sub(r'```\s*', '', raw)
            return json.loads(raw.strip())
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                print(f"Rate limit hit, waiting 15s... attempt {attempt+1}")
                time.sleep(15)
                continue
            raise e

    raise Exception("Rate limit exceeded after 3 retries")


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

        # Ask Gemini AI
        try:
            result = check_duplicate_with_ai(title, description, issue_store)
        except Exception as ai_err:
            print(f"AI ERROR: {ai_err}")
            # AI fail — save anyway
            issue_store.append({
                "id": str(len(issue_store)+1),
                "issueNumber": len(issue_store)+1,
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
            "id": str(len(issue_store)+1),
            "issueNumber": len(issue_store)+1,
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
