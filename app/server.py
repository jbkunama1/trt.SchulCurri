# Schulcurriculum Sport: Flask + SQLite (eine DB-Datei unter $DATA_DIR)
import contextlib
import csv
import datetime
import functools
import io
import os
import re
import secrets
import sqlite3
import time

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from curriculum import CURRICULUM, EVALUATIONS, REFLECTION_QUESTIONS, STAGES, STAGE_KEYS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'data'))
DOCS_DIR = os.environ.get('DOCS_DIR', os.path.join(BASE_DIR, 'docs'))
DB_PATH = os.path.join(DATA_DIR, 'schulcurri.db')
os.makedirs(DATA_DIR, exist_ok=True)

THEMES = ('sporty', 'sunset', 'forest', 'neon', 'dark')
STATUS = ('offen', 'erledigt', 'teilweise', 'entfaellt')
STATUS_ICON = {'offen': '⬜', 'erledigt': '✅', 'teilweise': '🔶', 'entfaellt': '➖'}
DOC_EXT = {'.md': '📝', '.pdf': '📄', '.html': '🌐', '.csv': '📊', '.json': '🧾', '.txt': '📃'}
USERNAME_RE = re.compile(r'^[a-z0-9_.-]{3,32}$')
MAX_TEXT = 5000
MIN_PW = 8


def load_secret():
    env = os.environ.get('SECRET_KEY')
    if env:
        return env
    path = os.path.join(DATA_DIR, '.secret_key')
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(secrets.token_hex(32))
        os.chmod(path, 0o600)
    with open(path) as f:
        return f.read().strip()


app = Flask(__name__)
app.secret_key = load_secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=12),
    MAX_CONTENT_LENGTH=1024 * 1024,
)
if os.environ.get('TRUST_PROXY') == '1':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


@contextlib.contextmanager
def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    finally:
        con.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'teacher',
  theme TEXT NOT NULL DEFAULT 'sporty',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS school_years(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT UNIQUE NOT NULL,
  active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS checklist(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  school_year_id INTEGER NOT NULL REFERENCES school_years(id) ON DELETE CASCADE,
  stage TEXT NOT NULL, item_code TEXT NOT NULL, item_title TEXT NOT NULL,
  item_desc TEXT NOT NULL, hours INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'offen', note TEXT NOT NULL DEFAULT '',
  updated_by TEXT, updated_at TEXT,
  UNIQUE(school_year_id, stage, item_code));
CREATE TABLE IF NOT EXISTS evaluations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  school_year_id INTEGER NOT NULL REFERENCES school_years(id) ON DELETE CASCADE,
  stage TEXT NOT NULL, area TEXT NOT NULL, instrument TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0, result TEXT NOT NULL DEFAULT '',
  UNIQUE(school_year_id, stage, area));
CREATE TABLE IF NOT EXISTS reflections(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  school_year_id INTEGER NOT NULL REFERENCES school_years(id) ON DELETE CASCADE,
  stage TEXT NOT NULL, qkey TEXT NOT NULL, answer TEXT NOT NULL DEFAULT '',
  UNIQUE(school_year_id, stage, qkey));
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT, action TEXT, detail TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
"""


def init_db():
    with db() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript(SCHEMA)
        if not c.execute('SELECT 1 FROM users WHERE role=?', ('admin',)).fetchone():
            pw = os.environ.get('ADMIN_PASSWORD')
            generated = not pw
            if generated:
                pw = secrets.token_urlsafe(12)
            c.execute('INSERT INTO users(username, display_name, password_hash, role) VALUES(?,?,?,?)',
                      ('admin', 'Administrator', generate_password_hash(pw), 'admin'))
            if generated:
                print(f"[schulcurri] Erster Start. Benutzer 'admin', Passwort: {pw} (bitte sofort aendern)", flush=True)


def seed_year(c, year_id):
    for s in STAGES:
        k = s['key']
        c.executemany('INSERT OR IGNORE INTO checklist(school_year_id,stage,item_code,item_title,item_desc,hours) VALUES(?,?,?,?,?,?)',
                      [(year_id, k, code, title, desc, h) for code, title, desc, h in CURRICULUM[k]])
        c.executemany('INSERT OR IGNORE INTO evaluations(school_year_id,stage,area,instrument) VALUES(?,?,?,?)',
                      [(year_id, k, a, i) for a, i in EVALUATIONS[k]])
        c.executemany('INSERT OR IGNORE INTO reflections(school_year_id,stage,qkey) VALUES(?,?,?)',
                      [(year_id, k, q) for q, _ in REFLECTION_QUESTIONS])


def audit(c, action, detail=''):
    who = g.user['username'] if g.user else '-'
    c.execute('INSERT INTO audit_log(username,action,detail) VALUES(?,?,?)', (who, action, str(detail)[:200]))


def current_year(c):
    return (c.execute('SELECT * FROM school_years WHERE active=1 LIMIT 1').fetchone()
            or c.execute('SELECT * FROM school_years ORDER BY id DESC LIMIT 1').fetchone())


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(24)
    return session['csrf']


app.jinja_env.globals['csrf_token'] = csrf_token
app.jinja_env.globals['csrf_field'] = lambda: Markup('<input type="hidden" name="csrf_token" value="%s">' % csrf_token())


@app.before_request
def before():
    g.user = None
    if request.endpoint == 'static':
        return None
    uid = session.get('uid')
    if uid:
        with db() as c:
            g.user = c.execute('SELECT id,username,display_name,role,theme FROM users WHERE id=? AND active=1',
                               (uid,)).fetchone()
        if g.user is None:
            session.clear()
    if request.method == 'POST':
        expected = session.get('csrf')
        sent = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token') or ''
        if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
            abort(400, 'CSRF-Token fehlt oder ist ungueltig')
    return None


@app.after_request
def headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Referrer-Policy'] = 'same-origin'
    resp.headers['Content-Security-Policy'] = ("default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                               "script-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
    return resp


def login_required(f):
    @functools.wraps(f)
    def wrapper(*a, **kw):
        if g.user is None:
            if request.path.startswith('/api/'):
                return jsonify(error='login'), 401
            return redirect(url_for('login'))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @functools.wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if g.user['role'] != 'admin':
            abort(403)
        return f(*a, **kw)
    return wrapper


FAILS = {}


def too_many(ip):
    now = time.time()
    FAILS[ip] = [t for t in FAILS.get(ip, []) if now - t < 300]
    return len(FAILS[ip]) >= 5


def clip(v):
    return str(v or '')[:MAX_TEXT]


@app.route('/health')
def health():
    with db() as c:
        c.execute('SELECT 1')
    return jsonify(status='ok')


@app.route('/login', methods=['GET', 'POST'])
def login():
    err = None
    if request.method == 'POST':
        ip = request.remote_addr or '?'
        if too_many(ip):
            err = 'Zu viele Versuche. Bitte 5 Minuten warten. ⏳'
        else:
            name = request.form.get('username', '').strip().lower()
            with db() as c:
                u = c.execute('SELECT * FROM users WHERE username=? AND active=1', (name,)).fetchone()
            if u and check_password_hash(u['password_hash'], request.form.get('password', '')):
                FAILS.pop(ip, None)
                session.clear()
                session['uid'] = u['id']
                session.permanent = True
                return redirect(url_for('dashboard'))
            FAILS.setdefault(ip, []).append(time.time())
            err = 'Benutzername oder Passwort falsch ❌'
    return render_template('login.html', err=err)


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    with db() as c:
        year = current_year(c)
        years = c.execute('SELECT * FROM school_years ORDER BY id DESC').fetchall()
        progress = {s['key']: {'counts': {}, 'pct': 0} for s in STAGES}
        if year:
            rows = c.execute('SELECT stage,status,COUNT(*) n FROM checklist WHERE school_year_id=? GROUP BY stage,status',
                             (year['id'],))
            for r in rows:
                if r['stage'] in progress:
                    progress[r['stage']]['counts'][r['status']] = r['n']
            for p in progress.values():
                k = p['counts']
                base = sum(k.values()) - k.get('entfaellt', 0)
                p['pct'] = round((k.get('erledigt', 0) + 0.5 * k.get('teilweise', 0)) / base * 100) if base else 0
    return render_template('dashboard.html', stages=STAGES, progress=progress, year=year, years=years)


@app.route('/klasse/<stage>')
@login_required
def klasse(stage):
    if stage not in STAGE_KEYS:
        abort(404)
    meta = next(s for s in STAGES if s['key'] == stage)
    items, evals, refs = [], [], {}
    with db() as c:
        year = current_year(c)
        if year:
            q = ' WHERE school_year_id=? AND stage=? ORDER BY id'
            items = c.execute('SELECT * FROM checklist' + q, (year['id'], stage)).fetchall()
            evals = c.execute('SELECT * FROM evaluations' + q, (year['id'], stage)).fetchall()
            refs = {r['qkey']: r['answer'] for r in c.execute(
                'SELECT qkey,answer FROM reflections WHERE school_year_id=? AND stage=?', (year['id'], stage))}
    return render_template('klasse.html', stage=stage, meta=meta, year=year, items=items, evals=evals,
                           refs=refs, rq=REFLECTION_QUESTIONS, icons=STATUS_ICON)


@app.post('/api/checklist')
@login_required
def api_checklist():
    d = request.get_json(silent=True) or {}
    if d.get('status') not in STATUS:
        abort(400)
    try:
        item_id = int(d.get('id'))
    except (TypeError, ValueError):
        abort(400)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    with db() as c:
        n = c.execute('UPDATE checklist SET status=?, note=?, updated_by=?, updated_at=? WHERE id=?',
                      (d['status'], clip(d.get('note')), g.user['username'], now, item_id)).rowcount
    if not n:
        abort(404)
    return jsonify(ok=True, updated_at=now)


@app.post('/api/evaluation')
@login_required
def api_evaluation():
    d = request.get_json(silent=True) or {}
    try:
        eid = int(d.get('id'))
    except (TypeError, ValueError):
        abort(400)
    with db() as c:
        n = c.execute('UPDATE evaluations SET done=?, result=? WHERE id=?',
                      (1 if d.get('done') else 0, clip(d.get('result')), eid)).rowcount
    if not n:
        abort(404)
    return jsonify(ok=True)


@app.post('/api/reflection')
@login_required
def api_reflection():
    d = request.get_json(silent=True) or {}
    try:
        year_id = int(d.get('year_id'))
    except (TypeError, ValueError):
        abort(400)
    with db() as c:
        n = c.execute('UPDATE reflections SET answer=? WHERE school_year_id=? AND stage=? AND qkey=?',
                      (clip(d.get('answer')), year_id, str(d.get('stage')), str(d.get('qkey')))).rowcount
    if not n:
        abort(404)
    return jsonify(ok=True)


@app.post('/api/theme')
@login_required
def api_theme():
    theme = (request.get_json(silent=True) or {}).get('theme')
    if theme not in THEMES:
        abort(400)
    with db() as c:
        c.execute('UPDATE users SET theme=? WHERE id=?', (theme, g.user['id']))
    return jsonify(ok=True)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        f = request.form
        with db() as c:
            me = c.execute('SELECT password_hash FROM users WHERE id=?', (g.user['id'],)).fetchone()
            if not check_password_hash(me['password_hash'], f.get('old_pw', '')):
                flash('Altes Passwort ist falsch ❌')
            elif len(f.get('new_pw', '')) < MIN_PW or f.get('new_pw') != f.get('new_pw2'):
                flash('Neues Passwort: mindestens %d Zeichen, beide Eingaben gleich ❌' % MIN_PW)
            else:
                c.execute('UPDATE users SET password_hash=? WHERE id=?',
                          (generate_password_hash(f['new_pw']), g.user['id']))
                flash('Passwort geändert ✅')
        return redirect(url_for('settings'))
    return render_template('settings.html', themes=THEMES)


def list_docs():
    out = []
    for root, _, files in os.walk(DOCS_DIR):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in DOC_EXT:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, DOCS_DIR).replace(os.sep, '/')
                out.append({'rel': rel, 'icon': DOC_EXT[ext], 'size_kb': round(os.path.getsize(full) / 1024, 1)})
    return sorted(out, key=lambda d: d['rel'])


@app.route('/downloads')
@login_required
def downloads():
    return render_template('downloads.html', docs=list_docs())


@app.route('/docs/<path:rel>')
@login_required
def serve_doc(rel):
    if os.path.splitext(rel)[1].lower() not in DOC_EXT:
        abort(404)
    return send_from_directory(DOCS_DIR, rel, as_attachment=True)


def csv_safe(v):
    s = '' if v is None else str(v)
    return "'" + s if s[:1] in ('=', '+', '-', '@', '\t', '\r') else s


def export_rows(stage):
    if stage not in STAGE_KEYS:
        abort(404)
    with db() as c:
        year = current_year(c)
        if not year:
            abort(400, 'Kein Schuljahr angelegt')
        rows = c.execute('SELECT item_code,item_title,hours,status,note,updated_by,updated_at FROM checklist '
                         'WHERE school_year_id=? AND stage=? ORDER BY id', (year['id'], stage)).fetchall()
    return year, rows


@app.route('/export/<stage>.csv')
@login_required
def export_csv(stage):
    year, rows = export_rows(stage)
    out = io.StringIO()
    w = csv.writer(out, delimiter=';')
    w.writerow(['Schuljahr', 'UV', 'Titel', 'Stunden', 'Status', 'Notiz', 'Bearbeitet von', 'Bearbeitet am'])
    for r in rows:
        w.writerow([csv_safe(x) for x in (year['label'], r['item_code'], r['item_title'], r['hours'],
                                          r['status'], r['note'], r['updated_by'], r['updated_at'])])
    return app.response_class(out.getvalue().encode('utf-8-sig'), mimetype='text/csv',
                              headers={'Content-Disposition': 'attachment; filename=sport_%s.csv' % stage})


@app.route('/export/<stage>.json')
@login_required
def export_json(stage):
    year, rows = export_rows(stage)
    with db() as c:
        evals = [dict(r) for r in c.execute('SELECT area,instrument,done,result FROM evaluations '
                                            'WHERE school_year_id=? AND stage=?', (year['id'], stage))]
        refl = [dict(r) for r in c.execute('SELECT qkey,answer FROM reflections WHERE school_year_id=? AND stage=?',
                                           (year['id'], stage))]
    resp = jsonify(stage=stage, school_year=year['label'], checklist=[dict(r) for r in rows],
                   evaluations=evals, reflections=refl)
    resp.headers['Content-Disposition'] = 'attachment; filename=sport_%s.json' % stage
    return resp


@app.route('/export/backup.db')
@admin_required
def backup():
    src = sqlite3.connect(DB_PATH)
    mem = sqlite3.connect(':memory:')
    try:
        src.backup(mem)
        data = mem.serialize()
    finally:
        mem.close()
        src.close()
    return app.response_class(data, mimetype='application/octet-stream',
                              headers={'Content-Disposition': 'attachment; filename=schulcurri_backup.db'})


@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    if request.method == 'POST':
        f = request.form
        act = f.get('action')
        try:
            with db() as c:
                if act in ('add_year', 'copy_year'):
                    label = f.get('label', '').strip()[:20]
                    if not label:
                        raise ValueError('Bezeichnung fehlt')
                    src = int(f['src_id']) if act == 'copy_year' else None
                    if src is not None and not c.execute('SELECT 1 FROM school_years WHERE id=?', (src,)).fetchone():
                        raise ValueError('Quell-Schuljahr nicht gefunden')
                    new_id = c.execute('INSERT INTO school_years(label) VALUES(?)', (label,)).lastrowid
                    seed_year(c, new_id)
                    if src is not None:
                        sub = ('(SELECT s.%s FROM checklist s WHERE s.school_year_id=? AND s.stage=checklist.stage '
                               'AND s.item_code=checklist.item_code)')
                        c.execute('UPDATE checklist SET status=COALESCE(' + sub % 'status' + ', status), '
                                  'note=COALESCE(' + sub % 'note' + ', note) WHERE school_year_id=?',
                                  (src, src, new_id))
                    if not c.execute('SELECT 1 FROM school_years WHERE active=1').fetchone():
                        c.execute('UPDATE school_years SET active=1 WHERE id=?', (new_id,))
                    audit(c, act, label)
                    flash('Schuljahr %s angelegt ✅' % label)
                elif act == 'activate_year':
                    c.execute('UPDATE school_years SET active=0')
                    c.execute('UPDATE school_years SET active=1 WHERE id=?', (int(f['year_id']),))
                    audit(c, act, f['year_id'])
                    flash('Aktives Schuljahr gesetzt ✅')
                elif act == 'add_user':
                    name, pw = f.get('username', '').strip().lower(), f.get('password', '')
                    role = f.get('role') if f.get('role') in ('teacher', 'admin') else 'teacher'
                    if not USERNAME_RE.match(name):
                        raise ValueError('Benutzername: 3-32 Zeichen a-z, 0-9, _ . -')
                    if len(pw) < MIN_PW:
                        raise ValueError('Passwort: mindestens %d Zeichen' % MIN_PW)
                    c.execute('INSERT INTO users(username,display_name,password_hash,role) VALUES(?,?,?,?)',
                              (name, f.get('display_name', '').strip()[:60] or name, generate_password_hash(pw), role))
                    audit(c, act, name)
                    flash('Benutzer %s angelegt 👤' % name)
                elif act == 'toggle_user':
                    uid = int(f['user_id'])
                    if uid == g.user['id']:
                        raise ValueError('Das eigene Konto kann nicht deaktiviert werden')
                    c.execute('UPDATE users SET active=1-active WHERE id=?', (uid,))
                    audit(c, act, uid)
                elif act == 'reset_pw':
                    if len(f.get('new_password', '')) < MIN_PW:
                        raise ValueError('Passwort: mindestens %d Zeichen' % MIN_PW)
                    c.execute('UPDATE users SET password_hash=? WHERE id=?',
                              (generate_password_hash(f['new_password']), int(f['user_id'])))
                    audit(c, act, f['user_id'])
                    flash('Passwort zurückgesetzt 🔑')
        except sqlite3.IntegrityError:
            flash('Eintrag existiert bereits ❌')
        except (ValueError, KeyError) as e:
            flash('Fehler: %s ❌' % e)
        return redirect(url_for('admin'))
    with db() as c:
        users = c.execute('SELECT * FROM users ORDER BY id').fetchall()
        years = c.execute('SELECT y.*, (SELECT COUNT(*) FROM checklist c WHERE c.school_year_id=y.id) items '
                          'FROM school_years y ORDER BY y.id DESC').fetchall()
        log = c.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 40').fetchall()
    return render_template('admin.html', users=users, years=years, log=log)


init_db()

if __name__ == '__main__':
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '8080')))
