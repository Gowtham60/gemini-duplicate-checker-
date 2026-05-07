from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import re
import requests

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("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", "")

issue_store = []

def check_duplicate_with_ai(new_title, new_desc, existing_issues):
    existing_text = "\n".join([
        f"#{iss['issueNumber']}: title='{iss['title']}' description='{iss['description']}'"
        for iss in existing_issues
    ])

    prompt = f"""Check if NEW ISSUE is duplicate of any EXISTING ISSUE by meaning.

EXISTING:
{existing_text}

NEW: title='{new_title}' description='{new_desc}'

Same/similar description meaning = duplicate. Different description = not duplicate.

Respond with ONLY JSON:
{{"isDuplicate": true, "matchedIssueNumber": 1, "matchedIssueTitle": "title"}}
or
{{"isDuplicate": false, "matchedIssueNumber": null, "matchedIssueTitle": null}}"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "You only output valid JSON. No markdown, no explanation, just JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
        "max_tokens": 100
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )

    print(f"Groq status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Groq error: {response.text}")
        return {"isDuplicate": False, "matchedIssueNumber": None, "matchedIssueTitle": None}

    raw = response.json()["choices"][0]["message"]["content"].strip()
    print(f"AI response: {raw}")

    # Clean and parse JSON
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except:
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
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

        if not issue_store:
            issue_store.append({"id": "1", "issueNumber": 1,
                                "title": title, "description": description})
            return jsonify({"isDuplicate": False, "similarityScore": 0,
                            "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

        try:
            result = check_duplicate_with_ai(title, description, issue_store)
        except Exception as ai_err:
            print(f"AI ERROR: {ai_err}")
            issue_store.append({
                "id": str(len(issue_store) + 1),
                "issueNumber": len(issue_store) + 1,
                "title": title, "description": description
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

        issue_store.append({
            "id": str(len(issue_store) + 1),
            "issueNumber": len(issue_store) + 1,
            "title": title, "description": description
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