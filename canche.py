
from flask import Flask, request, redirect, url_for, session, render_template_string, make_response
import os
import time

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "CLAVE_DE_LABORATORIO_2026")

USUARIO_PRUEBA = "demo"
CLAVE_PRUEBA = "demo123"

# Caché simulada insegura para fines educativos
CACHE = {}
CACHE_TTL = 60  # segundos

EXTENSIONES_CACHEABLES = (".css", ".js", ".ico", ".png", ".jpg")

HTML_HOME = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Laboratorio WCD</title>
</head>
<body>
    <h1>Laboratorio de Seguridad: Web Cache Deception</h1>

    <p>Este entorno es solo para fines educativos.</p>

    {% if "usuario" in session %}
        <p>Sesión iniciada como: <b>{{ session["usuario"] }}</b></p>
        <ul>
            <li><a href="{{ url_for('perfil') }}">Ver perfil privado</a></li>
            <li><a href="{{ url_for('logout') }}">Cerrar sesión</a></li>
        </ul>
    {% else %}
        <p>No has iniciado sesión.</p>
        <a href="{{ url_for('login') }}">Ir a login</a>
    {% endif %}

    <hr>
    <h3>Rutas del laboratorio</h3>
    <ul>
        <li><code>/login</code></li>
        <li><code>/perfil</code></li>
        <li><code>/perfil/archivo.css</code> ← ruta vulnerable de demostración</li>
        <li><code>/cache/ver</code> ← ver caché simulada</li>
        <li><code>/cache/limpiar</code> ← limpiar caché</li>
    </ul>
</body>
</html>
"""

HTML_LOGIN = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Login</title>
</head>
<body>
    <h1>Iniciar sesión</h1>

    {% if error %}
        <p style="color:red;">{{ error }}</p>
    {% endif %}

    <form method="post">
        <label>Usuario:</label><br>
        <input type="text" name="username" required><br><br>

        <label>Contraseña:</label><br>
        <input type="password" name="password" required><br><br>

        <button type="submit">Entrar</button>
    </form>

    <br>
    <a href="{{ url_for('home') }}">Volver</a>
</body>
</html>
"""

HTML_PERFIL = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Perfil privado</title>
</head>
<body>
    <h1>Perfil privado del usuario</h1>
    <p><b>Usuario:</b> {{ usuario }}</p>
    <p><b>Email:</b> demo@laboratorio.local</p>
    <p><b>Rol:</b> estudiante</p>
    <p><b>Token interno:</b> TOKEN-PRIVADO-XYZ-2026</p>
    <p><b>Hora de generación:</b> {{ ts }}</p>

    <hr>
    <p>Este contenido no debería ser cacheado públicamente.</p>

    <a href="{{ url_for('home') }}">Volver</a>
</body>
</html>
"""

def cache_key():
    # Solo usamos la ruta, simulando una caché mal diseñada
    return request.path

def es_recurso_estatico_por_extension(path: str) -> bool:
    path = path.lower()
    return path.endswith(EXTENSIONES_CACHEABLES)

def get_cached_response(key):
    item = CACHE.get(key)
    if not item:
        return None

    if time.time() - item["time"] > CACHE_TTL:
        del CACHE[key]
        return None

    return item["body"]

def store_in_cache(key, body):
    CACHE[key] = {
        "body": body,
        "time": time.time()
    }

@app.route("/")
def home():
    return render_template_string(HTML_HOME)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == USUARIO_PRUEBA and password == CLAVE_PRUEBA:
            session["usuario"] = username
            return redirect(url_for("perfil"))
        else:
            error = "Usuario o contraseña incorrectos"

    return render_template_string(HTML_LOGIN, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/perfil")
def perfil():
    if "usuario" not in session:
        return redirect(url_for("login"))

    html = render_template_string(
        HTML_PERFIL,
        usuario=session["usuario"],
        ts=time.strftime("%Y-%m-%d %H:%M:%S")
    )

    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store, private"
    resp.headers["X-Demo-Cache"] = "BYPASS"
    return resp

@app.route("/perfil/<path:extra>")
def perfil_vulnerable(extra):
    """
    Ruta intencionalmente vulnerable para la práctica de Web Cache Deception.
    Ejemplo:
      /perfil/archivo.css
      /perfil/cualquier/cosa.js
    """
    key = cache_key()

    cached = get_cached_response(key)
    if cached is not None:
        resp = make_response(cached)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        resp.headers["X-Demo-Cache"] = "HIT"
        resp.headers["Cache-Control"] = "public, max-age=60"
        return resp

    if "usuario" not in session:
        return redirect(url_for("login"))

    # El origen ignora el segmento extra y devuelve el perfil igual
    html = render_template_string(
        HTML_PERFIL,
        usuario=session["usuario"],
        ts=time.strftime("%Y-%m-%d %H:%M:%S")
    )

    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"

    # Fallo deliberado del laboratorio:
    # si la URL parece recurso estático, se cachea públicamente
    if es_recurso_estatico_por_extension(request.path):
        store_in_cache(key, html)
        resp.headers["X-Demo-Cache"] = "MISS-STORED"
        resp.headers["Cache-Control"] = "public, max-age=60"
    else:
        resp.headers["X-Demo-Cache"] = "MISS-NOT-STORED"
        resp.headers["Cache-Control"] = "no-store, private"

    return resp

@app.route("/cache/ver")
def ver_cache():
    contenido = "<h1>Caché simulada</h1><ul>"
    for k, v in CACHE.items():
        contenido += f"<li><b>{k}</b> - guardado hace {int(time.time() - v['time'])} segundos</li>"
    contenido += "</ul><p><a href='/'>Volver</a></p>"
    return contenido

@app.route("/cache/limpiar")
def limpiar_cache():
    CACHE.clear()
    return "<h1>Caché limpiada</h1><p><a href='/'>Volver</a></p>"

if __name__ == "__main__":
    puerto = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto, debug=False)
