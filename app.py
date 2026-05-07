from flask import Flask, request, jsonify
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

issue_store = []

# ── Similarity helpers ──────────────────────────────────────────────

def normalize(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\s]', '', (text or '').lower())).strip()

def tokenize(text):
    stopwords = {'the','a','an','is','are','was','were','has','have','been','be',
                 'to','of','and','in','on','at','it','this','that','for','with',
                 'not','do','does','did','i','my','we','our','there'}
    return [w for w in normalize(text).split() if len(w) > 1 and w not in stopwords]

def jaccard(a, b):
    sa, sb = set(tokenize(a)), set(tokenize(b))
    if not sa and not sb: return 1.0
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)

def bigram(a, b):
    def bigrams(s):
        n = normalize(s)
        return set(n[i:i+2] for i in range(len(n)-1))
    ba, bb = bigrams(a), bigrams(b)
    if not ba and not bb: return 1.0
    if not ba or not bb: return 0.0
    return 2 * len(ba & bb) / (len(ba) + len(bb))

def similarity(a, b):
    return max(jaccard(a, b), bigram(a, b))

def is_duplicate(new_title, new_desc, existing):
    """
    Duplicate = description similar (>=50%) 
    If no description → title similarity check
    """
    title_sim = similarity(new_title, existing['title'])
    
    has_new_desc = bool(new_desc and new_desc.strip())
    has_old_desc = bool(existing['description'] and existing['description'].strip())

    if has_new_desc and has_old_desc:
        desc_sim = similarity(new_desc, existing['description'])
        # Both have description → description must be similar
        score = title_sim * 0.3 + desc_sim * 0.7
        return score >= 0.50, score
    elif not has_new_desc and not has_old_desc:
        # Neither has description → title alone decide
        return title_sim >= 0.70, title_sim
    else:
        # One has desc, other doesn't → not duplicate
        return False, 0.0

# ── Routes ──────────────────────────────────────────────────────────

@app.route("/raise-issue", methods=["POST"])
def raise_issue():
    try:
        data = request.get_json(force=True)
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()

        if not title:
            return jsonify({"isDuplicate": False, "similarityScore": 0,
                            "matchedIssueId": None, "matchedIssueTitle": None, "message": None})

        # Check against all existing issues
        best_match = None
        best_score = 0.0

        for issue in issue_store:
            dup, score = is_duplicate(title, description, issue)
            if dup and score > best_score:
                best_score = score
                best_match = issue

        if best_match:
            return jsonify({
                "isDuplicate": True,
                "similarityScore": round(best_score, 2),
                "matchedIssueId": best_match['id'],
                "matchedIssueTitle": best_match['title'],
                "message": f"This issue has already been raised (#{best_match['issueNumber']}: {best_match['title']})"
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
        print(f"ERROR: {e}")
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
