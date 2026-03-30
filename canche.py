from flask import Flask, request, redirect, url_for, session, render_template_string, make_response
import os
import time
import secrets

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "LAB_SECRET_2026_CHANGE_ME")

USERS = {
    "demo": {
        "password": "demo123",
        "email": "demo@corp-internal.local",
        "role": "analyst",
        "customer_id": "CUST-44821",
        "invoice_id": "INV-2026-00991",
        "balance": "$4,870.25",
    }
}

# Simulación de caché insegura estilo edge/CDN
EDGE_CACHE = {}
EDGE_TTL = 90
STATIC_EXTENSIONS = (".css", ".js", ".ico", ".png", ".jpg", ".svg", ".woff", ".woff2")

HTML_INDEX = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Customer Portal</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background:#111; color:#eee; }
        a { color:#61dafb; }
        .card { background:#1b1b1b; padding:20px; border-radius:10px; margin-top:20px; }
        code { background:#222; padding:2px 6px; border-radius:6px; }
    </style>
</head>
<body>
    <h1>ACME Customer Portal</h1>
    <p>Área de autoservicio para clientes autenticados.</p>

    <div class="card">
    {% if "user" in session %}
        <p>Sesión activa: <b>{{ session["user"] }}</b></p>
        <ul>
            <li><a href="{{ url_for('dashboard') }}">Dashboard</a></li>
            <li><a href="{{ url_for('billing') }}">Billing</a></li>
            <li><a href="{{ url_for('logout') }}">Cerrar sesión</a></li>
        </ul>
    {% else %}
        <p>No autenticado.</p>
        <a href="{{ url_for('login') }}">Sign in</a>
    {% endif %}
    </div>

    <div class="card">
        <h3>Rutas del laboratorio</h3>
        <ul>
            <li><code>/login</code></li>
            <li><code>/dashboard</code></li>
            <li><code>/billing</code></li>
            <li><code>/billing/download.css</code> ← laboratorio</li>
            <li><code>/admin/cache</code></li>
            <li><code>/admin/purge</code></li>
        </ul>
    </div>
</body>
</html>
"""

HTML_LOGIN = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Sign in</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background:#111; color:#eee; }
        input, button { padding:10px; margin-top:8px; width:280px; }
        a { color:#61dafb; }
        .error { color:#ff6b6b; }
        .card { background:#1b1b1b; padding:20px; border-radius:10px; width:360px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Sign in</h1>
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        <form method="post">
            <label>Username</label><br>
            <input type="text" name="username" required><br>
            <label>Password</label><br>
            <input type="password" name="password" required><br><br>
            <button type="submit">Login</button>
        </form>
        <br>
        <a href="{{ url_for('index') }}">Back</a>
    </div>
</body>
</html>
"""

HTML_DASHBOARD = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background:#111; color:#eee; }
        .card { background:#1b1b1b; padding:20px; border-radius:10px; margin-top:20px; }
        a { color:#61dafb; }
    </style>
</head>
<body>
    <h1>Dashboard</h1>
    <div class="card">
        <p><b>User:</b> {{ user }}</p>
        <p><b>Role:</b> {{ profile["role"] }}</p>
        <p><b>Customer ID:</b> {{ profile["customer_id"] }}</p>
        <p><b>Session ID:</b> {{ sid }}</p>
    </div>

    <div class="card">
        <a href="{{ url_for('billing') }}">Go to billing</a><br><br>
        <a href="{{ url_for('logout') }}">Logout</a>
    </div>
</body>
</html>
"""

HTML_BILLING = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Billing</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background:#111; color:#eee; }
        .card { background:#1b1b1b; padding:20px; border-radius:10px; margin-top:20px; }
        a { color:#61dafb; }
        code { background:#222; padding:2px 6px; border-radius:6px; }
    </style>
</head>
<body>
    <h1>Billing Center</h1>
    <div class="card">
        <p><b>Customer:</b> {{ user }}</p>
        <p><b>Email:</b> {{ profile["email"] }}</p>
        <p><b>Invoice:</b> {{ profile["invoice_id"] }}</p>
        <p><b>Balance:</b> {{ profile["balance"] }}</p>
        <p><b>Generated:</b> {{ ts }}</p>
        <p><b>Internal note:</b> Payment review pending by finance queue.</p>
    </div>

    <div class="card">
        <p>Private endpoint. Should never be cached publicly.</p>
        <p>Download alias (lab): <code>/billing/download.css</code></p>
        <a href="{{ url_for('dashboard') }}">Back to dashboard</a>
    </div>
</body>
</html>
"""

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def edge_key():
    # Clave deliberadamente insegura: solo usa path
    return request.path

def is_static_like(path: str) -> bool:
    return path.lower().endswith(STATIC_EXTENSIONS)

def get_cached(key):
    item = EDGE_CACHE.get(key)
    if not item:
        return None
    if time.time() - item["stored_at"] > EDGE_TTL:
        del EDGE_CACHE[key]
        return None
    return item

def put_cached(key, body, headers=None):
    EDGE_CACHE[key] = {
        "body": body,
        "headers": headers or {},
        "stored_at": time.time()
    }

def build_response(body, cache_state, cache_control, extra_headers=None, status=200):
    resp = make_response(body, status)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = cache_control
    resp.headers["X-Cache"] = cache_state
    resp.headers["X-Cache-Key"] = edge_key()
    resp.headers["X-Served-By"] = "edge-lab-bogota-01"
    resp.headers["X-Request-ID"] = secrets.token_hex(8)
    if extra_headers:
        for k, v in extra_headers.items():
            resp.headers[k] = v
    return resp

@app.route("/")
def index():
    return render_template_string(HTML_INDEX)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = USERS.get(username)
        if user and user["password"] == password:
            session["user"] = username
            session["sid"] = secrets.token_hex(12)
            return redirect(url_for("dashboard"))
        error = "Invalid credentials"

    return render_template_string(HTML_LOGIN, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template_string(
        HTML_DASHBOARD,
        user=session["user"],
        profile=USERS[session["user"]],
        sid=session.get("sid")
    )

@app.route("/billing")
def billing():
    if "user" not in session:
        return redirect(url_for("login"))
    body = render_template_string(
        HTML_BILLING,
        user=session["user"],
        profile=USERS[session["user"]],
        ts=now()
    )
    return build_response(
        body=body,
        cache_state="BYPASS",
        cache_control="private, no-store, no-cache, max-age=0",
        extra_headers={"Pragma": "no-cache"}
    )

@app.route("/billing/<path:alias>")
def billing_alias(alias):
    key = edge_key()

    # 1) Si está en caché, se entrega incluso sin sesión (fallo del laboratorio)
    cached = get_cached(key)
    if cached is not None:
        return build_response(
            body=cached["body"],
            cache_state="HIT",
            cache_control="public, max-age=90",
        )

    # 2) Si no hay sesión y no hay caché, se redirige
    if "user" not in session:
        return redirect(url_for("login"))

    # 3) El origen ignora el alias y devuelve el mismo billing privado
    body = render_template_string(
        HTML_BILLING,
        user=session["user"],
        profile=USERS[session["user"]],
        ts=now()
    )

    # 4) Falla deliberada: si parece estático, el edge lo cachea públicamente
    if is_static_like(request.path):
        put_cached(key, body)
        return build_response(
            body=body,
            cache_state="MISS",
            cache_control="public, max-age=90",
            extra_headers={"X-Lab-Note": "stored-as-static"}
        )

    return build_response(
        body=body,
        cache_state="MISS",
        cache_control="private, no-store",
        extra_headers={"X-Lab-Note": "not-stored"}
    )

@app.route("/admin/cache")
def admin_cache():
    rows = []
    for k, v in EDGE_CACHE.items():
        age = int(time.time() - v["stored_at"])
        rows.append(f"<li><b>{k}</b> - age={age}s</li>")
    html = "<h1>Edge cache</h1><ul>" + "".join(rows) + "</ul><a href='/'>Back</a>"
    return html

@app.route("/admin/purge")
def admin_purge():
    EDGE_CACHE.clear()
    return "<h1>Cache purged</h1><a href='/'>Back</a>"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
