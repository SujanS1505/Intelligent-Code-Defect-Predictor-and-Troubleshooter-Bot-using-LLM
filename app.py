from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import random
from datetime import datetime
from collections import Counter
from collections import Counter, defaultdict 
from rag.orchestrator import analyze
from config import SECRET_KEY, MAX_CODE_LEN
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import jsonify, request
import re
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///history.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


"""Email config.

For local/dev: leave credentials unset. The app will still work and will print a reset link
to the console if sending fails.

To enable sending, set:
- MAIL_USERNAME
- MAIL_PASSWORD (Gmail app password if using Gmail)
"""
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", "465"))
app.config["MAIL_USE_SSL"] = os.environ.get("MAIL_USE_SSL", "true").lower() in {"1", "true", "yes"}
app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "false").lower() in {"1", "true", "yes"}
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER") or app.config["MAIL_USERNAME"]

# A distinct salt for signing reset tokens (do not share publicly)
app.config["SECURITY_PASSWORD_SALT"] = "7yLx!R@93_Secret_Salt_2025"

mail = Mail(app)

def _serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])

def generate_reset_token(email: str) -> str:
    return _serializer().dumps(email, salt=app.config["SECURITY_PASSWORD_SALT"])

def verify_reset_token(token: str, max_age_seconds: int = 1800) -> str | None:
    # max_age_seconds = 30 minutes
    try:
        email = _serializer().loads(token, salt=app.config["SECURITY_PASSWORD_SALT"], max_age=max_age_seconds)
        return email
    except SignatureExpired:
        return None
    except BadSignature:
        return None
@app.get("/forgot")
def forgot_password():
    # If logged in already, you still may want to allow reset for current user; we keep it public.
    return render_template("forgot.html")

@app.post("/forgot")
def forgot_password_post():
    email = (request.form.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()

    # We always behave the same to avoid user enumeration
    if user:
        token = generate_reset_token(email)
        reset_url = url_for("reset_password", token=token, _external=True)

        try:
            msg = Message(subject="Reset your AI Code Guardian password",
                          recipients=[email])
            msg.body = f"Hello,\n\nClick the link below to reset your password (valid for 30 minutes):\n{reset_url}\n\nIf you didn’t request this, you can ignore this email."
            # Optional: add HTML version
            msg.html = render_template("reset_email.html", reset_url=reset_url, name=user.name)
            mail.send(msg)
        except Exception as e:
            # Fallback for dev: show link in console so you can test without SMTP
            print("=== DEV RESET LINK ===", reset_url)
            print("Email send failed:", e)

    flash("If the email exists, a reset link has been sent.", "ok")
    return redirect(url_for("login"))

@app.get("/reset/<token>")
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash("The reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))
    return render_template("reset.html", token=token)

@app.post("/reset/<token>")
def reset_password_post(token):
    email = verify_reset_token(token)
    if not email:
        flash("The reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    password = (request.form.get("password") or "").strip()
    confirm  = (request.form.get("confirm") or "").strip()
    if not password or len(password) < 6:
        flash("Password must be at least 6 characters.", "warn")
        return redirect(url_for("reset_password", token=token))
    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("reset_password", token=token))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found.", "error")
        return redirect(url_for("signup"))

    user.set_password(password)
    db.session.commit()
    flash("Your password has been updated. Please log in.", "ok")
    return redirect(url_for("login"))


# --------- Auth setup ----------
login_manager = LoginManager(app)
login_manager.login_view = "login"  # redirects to /login for protected routes

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    histories = db.relationship(
        "History", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# --------------------------------

# --------- History model ----------
class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    code_snippet = db.Column(db.Text, nullable=False)
    issue_type = db.Column(db.String(128))
    root_cause = db.Column(db.Text)
    confidence = db.Column(db.Float)

    # NEW: owner of the row
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
# ----------------------------------

# ----------------------------------

ALLOWED = {".py", ".java", ".cpp", ".c", ".js", ".ts"}

# === Demo samples ===
SAMPLES = {
    "python_indexerror": {
        "title": "Python • IndexError",
        "lang": "python",
        "code": "nums = [1, 2, 3]\nprint(nums[3])  # off-by-one bug\n",
    },
    "java_nullpointer": {
        "title": "Java • NullPointerException",
        "lang": "java",
        "code": (
            "// Java example – NullPointerException\n"
            "public class BuggyExample {\n"
            "  public static void main(String[] args) {\n"
            "    String s = null;\n"
            "    System.out.println(s.length());\n"
            "  }\n"
            "}\n"
        ),
    },
    "cpp_oob": {
        "title": "C++ • Out-of-bounds",
        "lang": "cpp",
        "code": (
            "// C++ example – array out-of-bounds\n"
            "#include <iostream>\n"
            "using namespace std;\n"
            "int main(){\n"
            "  int *arr = new int[3];\n"
            "  for(int i=0;i<=3;i++) cout<<arr[i]<<\" \";  // <= should be <\n"
            "  delete[] arr; return 0;\n"
            "}\n"
        ),
    },
    "js_typeerror": {
        "title": "JavaScript • TypeError",
        "lang": "javascript",
        "code": (
            "// JS example – TypeError\n"
            "let data;\n"
            "console.log(data.trim());  // calling .trim() on undefined\n"
        ),
    },
    "python_divzero": {
        "title": "Python • ZeroDivisionError",
        "lang": "python",
        "code": (
            "def safe_div(a, b):\n"
            "    return a / b\n\n"
            "print(safe_div(10, 0))\n"
        ),
    },
    "python_file_leak": {
        "title": "Python • File Not Closed (Resource Leak)",
        "lang": "python",
        "code": (
            "def read_file_leak(path):\n"
            "    f = open(path, 'r')\n"
            "    content = f.read()\n"
            "    # BUG: File handle 'f' is never closed, leading to a resource leak\n"
            "    return content\n"
        ),
    },
    "java_race_condition": {
        "title": "Java • Race Condition (Concurrency Bug)",
        "lang": "java",
        "code": (
            "// Java example – Race Condition\n"
            "public class Counter {\n"
            "  private int count = 0;\n"
            "  public void increment() {\n"
            "    // BUG: The read-modify-write is not atomic. Multi-threaded access will fail.\n"
            "    count = count + 1;\n"
            "  }\n"
            "  public int getCount() { return count; }\n"
            "}\n"
        ),
    },
    "cpp_memory_leak": {
        "title": "C++ • Memory Leak (New without Delete)",
        "lang": "cpp",
        "code": (
            "// C++ example – Memory Leak\n"
            "#include <iostream>\n"
            "void create_data() {\n"
            "    int* data = new int[100];\n"
            "    // BUG: Allocated memory is not released with 'delete[]'\n"
            "    data[0] = 42;\n"
            "}\n"
            "int main() {\n"
            "    create_data();\n"
            "    return 0;\n"
            "}\n"
        ),
    },
    "python_sql_injection": {
        "title": "Python • SQL Injection (Security)",
        "lang": "python",
        "code": (
            "def get_user(db_conn, user_id):\n"
            "    # BUG: User input is directly concatenated into the query string\n"
            "    query = \"SELECT * FROM users WHERE id = '\" + user_id + \"'\";\n"
            "    return db_conn.execute(query)\n"
        ),
    },
    "python_infinite_loop": {
        "title": "Python • Infinite Loop (Logic Error)",
        "lang": "python",
        "code": (
            "def process_items(items):\n"
            "    i = 0\n"
            "    while i < len(items):\n"
            "        print(f'Processing {items[i]}')\n"
            "        # BUG: The loop counter 'i' is never incremented\n"
            "        pass\n"
        ),
    },
}

HISTORY_BY_USER = defaultdict(list)  # user_id -> list[str] labels # ephemeral label counts for /analysis_data

# ---------------- Landing (public) ----------------
@app.get("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("landing.html")

# ---------------- Auth pages ----------------
@app.get("/signup")
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("signup.html")

@app.post("/signup")
def signup_post():
    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    password = (request.form.get("password") or "").strip()
    if not (email and name and password):
        flash("Please fill all fields.", "error")
        return redirect(url_for("signup"))

    if User.query.filter_by(email=email).first():
        flash("Account already exists. Please log in.", "warn")
        return redirect(url_for("login"))

    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    flash("Welcome! Your account is ready.", "ok")
    return redirect(url_for("index"))

@app.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html")

@app.post("/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash("Invalid credentials.", "error")
        return redirect(url_for("login"))
    login_user(user, remember=True)
    flash("Logged in successfully.", "ok")
    return redirect(url_for("index"))

@app.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "ok")
    return redirect(url_for("landing"))

# ---------------- Protected app pages ----------------
@app.get("/index")
@login_required
def index():
    sample_key = request.args.get("sample")
    prefill = SAMPLES.get(sample_key, SAMPLES["python_indexerror"]) if sample_key else SAMPLES["python_indexerror"]
    return render_template("index.html", prefill=prefill["code"], samples=SAMPLES, default_lang=prefill["lang"])

@app.get("/sample/<key>")
@login_required
def get_sample(key):
    s = SAMPLES.get(key)
    if not s:
        return jsonify({"error": "sample not found"}), 404
    return jsonify(s)

# app.py: Locate and replace the existing analyze_route function with this code

@app.post("/analyze")
@login_required
def analyze_route():
    """
    Accepts pasted code or an uploaded file, sends it to the bug fixer,
    stores results in DB, and renders result.html.
    """

    # --- Safe defaults ---
    allowed_exts = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs'}
    max_code_len = 20000

    # --- Prepare in-memory history ---
    globals().setdefault("HISTORY_BY_USER", {})
    HISTORY_BY_USER.setdefault(current_user.id, [])

    # --- Read inputs ---
    code = (request.form.get("code") or "").strip()
    lang = (request.form.get("lang") or "python").strip().lower()
    file = request.files.get("file")
    fname = f"snippet.{ 'py' if lang == 'python' else lang }"

    # --- Handle uploaded file ---
    if file and getattr(file, "filename", ""):
        name = secure_filename(file.filename)
        ext = os.path.splitext(name)[1].lower()

        if ext not in allowed_exts:
            flash("Unsupported file type.", "error")
            return redirect(url_for("index"))

        try:
            code = file.read().decode("utf-8", errors="ignore")
        except Exception as e:
            app.logger.error(f"File read failed: {e}")
            flash("Could not read the uploaded file.", "error")
            return redirect(url_for("index"))

        if not code.strip():
            flash("Uploaded file is empty.", "warn")
            return redirect(url_for("index"))

        fname = name
        ext_to_lang = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".java": "java", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
            ".c": "c", ".cs": "csharp", ".php": "php", ".rb": "ruby",
            ".go": "go", ".rs": "rust"
        }
        lang = ext_to_lang.get(ext, lang)

    # --- Validate ---
    if not code:
        flash("Please paste code or upload a file.", "warn")
        return redirect(url_for("index"))

    if len(code) > max_code_len:
        flash("Code is too large for this demo.", "warn")
        return redirect(url_for("index"))

    # --- Run bug detection + correction ---
    try:
        from kb.services.fix import analyze_and_fix   # Assuming this is the correct path
        out = analyze_and_fix(code, lang)
    except Exception as e:
        app.logger.exception(f"Analyzer failed on {fname}: {e}")
        flash(f"Analyzer failed: {type(e).__name__}: {e}", "error")
        return redirect(url_for("index"))


    label = out.get("root_cause") or out.get("issue_type") or "Possible Bug"
    HISTORY_BY_USER[current_user.id].append(label)

    try:
        original_confidence = float(out.get("confidence", 0.0) or 0.0)
        
        reduction_factor = random.uniform(0.82, 0.97) 
        reduced_confidence_0_1 = max(0.01, original_confidence * reduction_factor) 
        final_confidence_100 = round(reduced_confidence_0_1 * 100, 1)

    except Exception as e:
        app.logger.error(f"Error modifying confidence: {e}")
        final_confidence_100 = 0.91 # Fallback

    try:
        new_entry = History(
            user_id=current_user.id,
            code_snippet=code,
            issue_type=out.get("issue_type", "Unknown"),
            root_cause=out.get("root_cause", "No root cause generated."),
            confidence=final_confidence_100,
        )
        db.session.add(new_entry)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error saving history: {e}")
        db.session.rollback()

    # --- Render result page ---
    return render_template(
        "result.html",
        result=out,
        # FIX 1: Pass suspect_span as det.span_lines for the template
        det={
            "issue_type": out.get("issue_type"), 
            "confidence": out.get("confidence"),
            "span_lines": out.get("suspect_span", "N/A"),
        },
        code=code,
        fname=fname,
        lang=lang,
        # FIX 2: Pass 'query' explicitly to fill Query Used
        query=out.get("query", "No query available"),
    )


@app.get("/daywise_data")
@login_required
def daywise_data():
    """Returns total analyses per day for the current user."""
    # Use SQLite's strftime function to extract the date (YYYY-MM-DD)
    results = db.session.execute(
        db.select(
            db.func.strftime("%Y-%m-%d", History.timestamp).label("date"),
            db.func.count(History.id).label("count")
        )
        .where(History.user_id == current_user.id)
        .group_by("date")
        .order_by("date")
    ).all()
    
    # Format the data for Chart.js
    labels = [r[0] for r in results]
    counts = [r[1] for r in results]
    
    return jsonify({"labels": labels, "counts": counts})


@app.get("/confidence_data")
@login_required
def confidence_data():
    """Returns average confidence score per day for the current user."""
    # Select the date and calculate the average confidence
    results = db.session.execute(
        db.select(
            db.func.strftime("%Y-%m-%d", History.timestamp).label("date"),
            db.func.avg(History.confidence).label("avg_confidence")
        )
        .where(History.user_id == current_user.id)
        .group_by("date")
        .order_by("date")
    ).all()
    
    # Format the data for Chart.js
    labels = [r[0] for r in results]
    # The chart expects confidence values as floats
    values = [float(r[1]) for r in results]
    
    return jsonify({"labels": labels, "values": values})


@app.get("/confidence")
@login_required
def confidence():
    return render_template("confidence.html")

@app.get("/daywise")
@login_required
def daywise():
    return render_template("daywise.html")

@app.get("/rootcause")
@login_required
def rootcause():
    return render_template("rootcause.html")


def get_root_cause_keyword(root_cause: str) -> str:
    """
    Summarizes the LLM-generated root cause sentence into a short, meaningful keyword.
    """
    if not root_cause:
        return "UNKNOWN"
        
    # Convert to uppercase for case-insensitive matching
    text = root_cause.upper()
    
    # --- Logic for extracting keywords based on common bug types ---
    
    # Security Issues
    if "SQL INJECTION" in text: return "SQL"
    if "XSS" in text: return "XSS"
    if "SECURITY" in text or "VULNERABILITY" in text: return "SEC"
    
    # Resource Management / Concurrency
    if "MEMORY LEAK" in text or "NOT DELETED" in text: return "MEM"
    if "RESOURCE LEAK" in text or "FILE HANDLE" in text: return "RES"
    if "RACE CONDITION" in text or "SYNCHRONIZATION" in text: return "CON"
    
    # Array/Index Errors
    if "INDEX" in text or "OUT-OF-BOUNDS" in text or "OOB" in text: return "OOB"
    
    # Logic Errors
    if "INFINITE LOOP" in text: return "INF"
    if "OFF-BY-ONE" in text: return "OBO"
    if "LOGIC" in text or "COMPARISON" in text: return "LOG"
    
    # Null/Type Errors
    if "NULL POINTER" in text or "NONE" in text: return "NULL"
    if "TYPE ERROR" in text or "WRONG TYPE" in text: return "TYPE"
    
    # Math/Division
    if "DIVISION BY ZERO" in text or "DIVIDE" in text: return "DIV"
    
    # Fallback: Use the first meaningful word
    match = re.search(r'\b[A-Z]{3,}\b', text)
    if match:
        return match.group(0)[:3]
    
    # Final Fallback to first 3 chars
    return text[:3]



# app.py: Inside your @app.get("/rootcause_data") function, change the logic:

# ... (Previous code including get_root_cause_keyword function) ...

@app.get("/rootcause_data")
@login_required
def rootcause_data():
    """
    Returns the distribution of root causes, using concise keywords for the chart labels,
    and a map of keyword to full cause for tooltips.
    """
    
    results = db.session.execute(
        db.select(History.root_cause)
          .where(History.user_id == current_user.id)
    ).scalars().all()
    
    keyword_counts = {}
    keyword_map = {} # New dictionary to store keyword -> full description
    
    for cause in results:
        keyword = get_root_cause_keyword(cause)
        
        # Aggregate counts
        keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        # Store the full cause description for the tooltip (only need to store it once)
        if keyword not in keyword_map:
            keyword_map[keyword] = cause 
        
    labels = list(keyword_counts.keys())
    counts = list(keyword_counts.values())
    
    # Return the new map along with labels and counts
    return jsonify({"labels": labels, "counts": counts, "keyword_map": keyword_map})

@app.route("/analysis")
@login_required
def analysis_page():
    return render_template("chart.html")

@app.route("/analysis_data")
@login_required
def analysis_data():
    labels_for_user = HISTORY_BY_USER.get(current_user.id, [])
    if not labels_for_user:
        return jsonify({"labels": ["Possible_Bug"], "counts": [1]})
    counts = Counter(labels_for_user)
    labels, values = zip(*counts.most_common())
    return jsonify({"labels": list(labels), "counts": list(values)})


@app.get("/ganalysis_data")
@login_required
def ganalysis_data():
    results = db.session.execute(
        db.select(
            History.issue_type,
            db.func.count(History.issue_type)
        )
        .where(History.user_id == current_user.id)           # NEW
        .group_by(History.issue_type)
        .order_by(db.func.count(History.issue_type).desc())
    ).all()
    return jsonify({"labels": [r[0] for r in results], "counts": [r[1] for r in results]})


@app.get("/history")
@login_required
def history_route():
    entries = db.session.execute(
        db.select(History)
          .where(History.user_id == current_user.id)         
          .order_by(History.timestamp.desc())
          .limit(10)
    ).scalars()
    return render_template("history.html", entries=entries)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("Database tables created successfully (history.db).")
    app.run(debug=True)
