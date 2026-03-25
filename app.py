import sqlite3
import string
import random
from pathlib import Path

from flask import Flask, request, redirect, render_template_string, abort

app = Flask(__name__)

# Path to the SQLite database file (created automatically if missing)
DB_PATH = Path("urls.db")

# Simple HTML form template rendered directly from a string
HTML_FORM = """
<!doctype html>
<title>URL Shortener</title>
<h1>Shorten a URL</h1>
<form method="post">
  <input type="url" name="url" placeholder="https://example.com" required style="width:300px">
  <button type="submit">Shorten</button>
</form>
{% if short_url %}
  <p>Short URL: <a href="{{ short_url }}">{{ short_url }}</a></p>
{% endif %}
"""


# ---------- Database setup ----------

def init_db():
    """
    Create the SQLite database file and the 'urls' table if they do not exist.

    The 'urls' table stores:
      - id:         integer primary key (auto-increment)
      - original_url: the full, original URL submitted by the user
      - short_code:   the generated short code used in the shortened URL
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def get_db():
    """
    Open and return a new connection to the SQLite database.

    Each call returns a fresh connection; callers are responsible for closing it.
    """
    return sqlite3.connect(DB_PATH)


# ---------- Short code generation ----------

def generate_code(length: int = 6) -> str:
    """
    Generate a random short code using letters and digits.

    The default length is 6 characters.
    """
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def generate_unique_short_code(cur, length: int = 6) -> str:
    """
    Generate a random short code that is guaranteed to be unique in the database.

    Uses the given cursor to query the 'urls' table until it finds a code
    that does not already exist.
    """
    while True:
        code = generate_code(length)
        cur.execute("SELECT 1 FROM urls WHERE short_code = ?", (code,))
        if cur.fetchone() is None:
            return code


# ---------- URL storage helpers ----------

def store_url(original_url: str) -> str:
    """
    Store the given original URL in the database with a unique short code.

    Returns the generated short code so it can be shown to the user.
    """
    conn = get_db()
    cur = conn.cursor()

    # Generate a short code that is not already used
    short_code = generate_unique_short_code(cur)

    # Insert the (original_url, short_code) pair into the 'urls' table
    cur.execute(
        "INSERT INTO urls (original_url, short_code) VALUES (?, ?)",
        (original_url, short_code),
    )
    conn.commit()
    conn.close()
    return short_code


def resolve_url(short_code: str) -> str | None:
    """
    Look up the original URL for a given short code.

    Returns the original URL if found, or None if the code does not exist.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT original_url FROM urls WHERE short_code = ?",
        (short_code,),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Home page:

    - On GET:  display a simple HTML form to submit a long URL.
    - On POST: read the submitted URL, store it in the database with a
      generated short code, and display the resulting shortened URL.
    """
    short_url = None
    if request.method == "POST":
        long_url = request.form.get("url")
        if long_url:
            # Store the original URL and get back a unique short code
            code = store_url(long_url)
            # Build the full shortened URL (e.g., http://host/<code>)
            short_url = request.host_url + code
    return render_template_string(HTML_FORM, short_url=short_url)


@app.route("/<short_code>")
def redirect_short_code(short_code):
    """
    Redirection route:

    - Receives a short code in the URL path.
    - Looks up the corresponding original URL in the database.
    - If found, redirects the user to that URL.
    - If not found, shows a simple error message.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT original_url FROM urls WHERE short_code = ?",
        (short_code,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        # Simple error message for unknown/invalid codes
        return "Invalid or unknown short code.", 404

    # Redirect to the stored original URL
    return redirect(row[0])


if __name__ == "__main__":
    # Ensure the database and 'urls' table exist before handling any requests
    init_db()
    # Start the Flask development server
    app.run(debug=True)