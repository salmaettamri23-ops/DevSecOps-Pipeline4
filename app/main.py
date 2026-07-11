from flask import Flask, request, render_template_string, redirect, url_for, jsonify
from flask_wtf import CSRFProtect
from flask_talisman import Talisman
import sqlite3
import os

app = Flask(__name__)

# =========================================================================
# CORRECTION SonarQube (L4) : "Make sure disabling CSRF protection is safe"
# Flask ne protège pas les formulaires contre le CSRF par défaut.
# On active Flask-WTF pour générer et vérifier un token CSRF unique
# sur chaque formulaire POST. Ceci corrige aussi l'alerte ZAP
# "Absence of Anti-CSRF Tokens".
# =========================================================================
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-moi-avant-la-production')
csrf = CSRFProtect(app)

# =========================================================================
# CORRECTION ZAP : en-têtes de sécurité HTTP manquants
# Flask-Talisman ajoute automatiquement :
#   - Content-Security-Policy (CSP)      -> corrige "CSP Header Not Set"
#   - X-Frame-Options: SAMEORIGIN        -> corrige "Missing Anti-clickjacking Header"
#   - X-Content-Type-Options: nosniff    -> corrige "X-Content-Type-Options Header Missing"
# force_https=False car l'app tourne en HTTP en environnement de staging/démo.
# A mettre à True en production réelle avec un certificat TLS.
# =========================================================================
Talisman(
    app,
    force_https=False,
    frame_options='SAMEORIGIN',
    x_content_type_options=True,
    content_security_policy={
        'default-src': "'self'",
        'style-src': "'self' 'unsafe-inline'",
    },
)

# =========================================================================
# CORRECTION SonarQube (L10) : "Define a constant instead of duplicating
# this literal 'tasks.db' 5 times."
# =========================================================================
DB_NAME = 'tasks.db'


def init_db():
    """Crée la table des tâches avec une colonne pour le statut (0 = En cours, 1 = Fait)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


# --- DESIGN DE L'INTERFACE (HTML/CSS) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PFE - Gestionnaire de Tâches SecOps</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; margin: 40px; }
        .container { max-width: 600px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0px 0px 10px rgba(0,0,0,0.1); margin: auto; }
        .header-student { background-color: #007bff; color: white; padding: 10px; border-radius: 4px; text-align: center; margin-bottom: 20px; font-weight: bold; }
        h2, h3 { color: #333; }
        input[type="text"] { width: 70%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
        input[type="submit"] { padding: 10px 15px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; }
        ul { list-style-type: none; padding: 0; }
        li { padding: 10px; background: #eee; margin-bottom: 5px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
        .btn-done { background: #007bff; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; text-decoration: none; font-size: 12px; }
        .btn-undone { background: #dc3545; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; text-decoration: none; font-size: 12px; }
        .done-task { background: #d4edda; color: #155724; }
        .tables-container { display: flex; gap: 20px; margin-top: 20px; }
        .table-column { flex: 1; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-student">
            PFE Licence Cybersécurité | Réalisé par : SALMA ETTAMRI
        </div>
        <h2>Mon Gestionnaire de Tâches</h2>
        <form action="/add" method="POST">
            <!-- CORRECTION : token CSRF injecté automatiquement par Flask-WTF -->
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <input type="text" name="task_title" placeholder="Nouvelle tâche..." required>
            <input type="submit" value="Ajouter">
        </form>
        <div class="tables-container">
            <div class="table-column">
                <h3>Tâches en cours</h3>
                <ul>
                    {% for task in tasks_todo %}
                        <li>
                            {{ task[1] }}
                            <a href="/done/{{ task[0] }}" class="btn-done">Done</a>
                        </li>
                    {% endfor %}
                </ul>
            </div>
            <div class="table-column">
                <h3>Tâches effectuées</h3>
                <ul>
                    {% for task in tasks_done %}
                        <li class="done-task">
                            <span>{{ task[1] }} ✅</span>
                            <a href="/undone/{{ task[0] }}" class="btn-undone">Undone</a>
                        </li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </div>
</body>
</html>
"""


# --- ROUTES DE L'APPLICATION ---
# CORRECTION SonarQube (L87, L93) : "Specify the HTTP methods this route
# should accept." -> ajout explicite de methods=['GET'] sur chaque route
# qui n'accepte que des lectures.

@app.route('/health', methods=['GET'])
def health():
    """Route indispensable pour l'étape DAST (OWASP ZAP) du Jenkinsfile."""
    return jsonify({"status": "UP", "message": "Application saine"}), 200


@app.route('/', methods=['GET'])
def index():
    """Sépare les tâches en deux listes selon leur statut (0 ou 1)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM tasks WHERE status = 0")
    tasks_todo = cursor.fetchall()
    cursor.execute("SELECT id, title FROM tasks WHERE status = 1")
    tasks_done = cursor.fetchall()
    conn.close()
    return render_template_string(HTML_TEMPLATE, tasks_todo=tasks_todo, tasks_done=tasks_done)


@app.route('/add', methods=['POST'])
def add_task():
    title = request.form.get('task_title')
    if title:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (title, status) VALUES (?, 0)", (title,))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))


@app.route('/done/<int:task_id>', methods=['GET'])
def complete_task(task_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 1 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/undone/<int:task_id>', methods=['GET'])
def undo_task(task_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 0 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


# =========================================================================
# CORRECTION ZAP : "Server Leaks Version Information via Server Header"
# et en-têtes Cross-Origin manquants (COOP / COEP / CORP / Permissions-Policy).
# Talisman ne couvre pas ces en-têtes, on les ajoute donc manuellement ici.
# =========================================================================
@app.after_request
def add_security_headers(response):
    response.headers['Server'] = 'WebServer'  # masque "Werkzeug/x.x Python/x.x"
    response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    return response


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=3000)
