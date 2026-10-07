# Telegram-Anbindung: Meldungen, Befehle und Inline-Buttons (nur Standardbibliothek)
# Rollen: Admin = fest per TELEGRAM_ADMIN_CHAT_ID, User = per Einladung vom Admin (oder fest per TELEGRAM_CHAT_ID)
import html
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.request

from flask import abort, jsonify, request

log = logging.getLogger('schulcurri.telegram')
SECRET_RE = re.compile(r'^[A-Za-z0-9_-]{1,256}$')
INVITE_HOURS = 48
HELP = ('<b>Befehle</b>\n/menu - Menü mit Buttons\n/status - Fortschritt je Klasse\n'
        '/offen [Klasse] - offene Unterrichtsvorhaben, z. B. /offen 7/8\n'
        '/id - Chat-ID anzeigen\n/hilfe - diese Hilfe')
HELP_ADMIN = '\n/einladen - Einladungslink für einen neuen User\n/user - User verwalten'

TG_SCHEMA = """
CREATE TABLE IF NOT EXISTS tg_users(
  chat_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  added_by TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS tg_invites(
  code TEXT PRIMARY KEY,
  created_by TEXT,
  expires_at REAL NOT NULL,
  used_by TEXT);
"""


class TelegramError(ValueError):
    pass


def esc(v):
    return html.escape(str(v), quote=False)


def kb(rows):
    return {'inline_keyboard': [[{'text': t, 'callback_data': d} for t, d in row] for row in rows]}


class Bot:
    def __init__(self, data_dir, db, current_year, progress, stages):
        self.data_dir = data_dir
        self.db = db
        self.current_year = current_year
        self.progress = progress
        self.stages = stages
        self.async_send = True
        self._username = None

    def ensure_schema(self, con):
        con.executescript(TG_SCHEMA)

    # Konfiguration: wird bei jedem Zugriff aus der Umgebung gelesen
    def token(self):
        return os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()

    def _ids(self, var):
        return [x.strip() for x in os.environ.get(var, '').split(',') if x.strip()]

    def admins(self):
        # Admins sind fest hinterlegt und müssen private Chats sein (positive IDs)
        return [x for x in self._ids('TELEGRAM_ADMIN_CHAT_ID') if x.isdigit()]

    def static_chats(self):
        return self._ids('TELEGRAM_CHAT_ID')

    def db_users(self):
        try:
            with self.db() as c:
                return [dict(r) for r in c.execute('SELECT chat_id,name FROM tg_users ORDER BY created_at, chat_id')]
        except sqlite3.Error:
            return []

    def users(self):
        out = []
        for cid in self.admins() + self.static_chats() + [u['chat_id'] for u in self.db_users()]:
            if cid not in out:
                out.append(cid)
        return out

    def is_admin(self, chat_id):
        return str(chat_id) in self.admins()

    def is_user(self, chat_id):
        return str(chat_id) in self.users()

    def public_url(self):
        return os.environ.get('PUBLIC_URL', '').strip().rstrip('/')

    def status(self):
        return {'token': bool(self.token()), 'admins': len(self.admins()), 'chats': len(self.users()),
                'public_url': self.public_url()}

    def secret(self):
        env = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '').strip()
        if SECRET_RE.match(env):
            return env
        path = os.path.join(self.data_dir, '.telegram_secret')
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(secrets.token_urlsafe(32))
            os.chmod(path, 0o600)
        with open(path) as f:
            return f.read().strip()

    # Zugriff auf die Bot-API; Fehlermeldungen enthalten nie die URL (= Token)
    def call(self, method, payload=None, timeout=8):
        req = urllib.request.Request('https://api.telegram.org/bot%s/%s' % (self.token(), method),
                                     data=json.dumps(payload or {}).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                data = json.load(e)
            except ValueError:
                data = {'ok': False, 'description': 'HTTP %d' % e.code}
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise TelegramError('Verbindung fehlgeschlagen (%s)' % type(e).__name__)
        if not data.get('ok'):
            raise TelegramError(data.get('description', 'unbekannter Fehler'))
        return data.get('result')

    def _send_one(self, chat_id, text, markup=None):
        payload = {'chat_id': chat_id, 'text': text[:4000], 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        if markup:
            payload['reply_markup'] = markup
        self.call('sendMessage', payload)

    def send(self, text, chat_ids=None, markup=None):
        ids = self.users() if chat_ids is None else chat_ids
        if not self.token() or not ids:
            return False
        ok = True
        for cid in ids:
            try:
                self._send_one(cid, text, markup)
            except Exception as e:  # Zustellfehler duerfen die App nie stoeren
                log.warning('Telegram sendMessage an %s fehlgeschlagen: %s', cid, e)
                ok = False
        return ok

    def _run(self, fn, *args):
        if self.async_send:
            threading.Thread(target=fn, args=args, daemon=True).start()
        else:
            fn(*args)

    def notify(self, text):
        # Fortschrittsmeldungen: an alle User (Admins sind immer auch User)
        ids = self.users()
        if self.token() and ids:
            self._run(self.send, text, ids)

    def notify_admin(self, text):
        # Verwaltungsmeldungen: nur an Admins
        ids = self.admins()
        if self.token() and ids:
            self._run(self.send, text, ids)

    # Hilfsfunktionen fuer Buttons und Texte
    def help_text(self, chat_id):
        return HELP + (HELP_ADMIN if self.is_admin(chat_id) else '')

    def menu_markup(self, chat_id):
        rows = [[('📊 Status', 's'), ('📋 Offen', 'o')]]
        if self.is_admin(chat_id):
            rows.append([('🛡️ Admin', 'a')])
        return kb(rows)

    def stage_key(self, arg):
        a = re.sub(r'(?i)klasse|kl\.?|\s|\.', '', arg).replace('/', '')
        if a in ('7', '8', '78'):
            a = '78'
        return a if a in [s['key'] for s in self.stages] else None

    def _status(self):
        with self.db() as c:
            year = self.current_year(c)
            if not year:
                return 'Noch kein Schuljahr angelegt.'
            prog = self.progress(c, year['id'])
        lines = ['<b>Schuljahr %s</b>' % esc(year['label'])]
        for s in self.stages:
            p = prog[s['key']]
            k = p['counts']
            lines.append('%s %s: %d %% (✅ %d · 🔶 %d · ⬜ %d)' % (
                s['emoji'], esc(s['label']), p['pct'], k.get('erledigt', 0), k.get('teilweise', 0), k.get('offen', 0)))
        return '\n'.join(lines)

    def _offen_text(self, key=None):
        with self.db() as c:
            year = self.current_year(c)
            if not year:
                return 'Noch kein Schuljahr angelegt.'
            rows = c.execute('SELECT stage,item_code,item_title,hours,status FROM checklist '
                             'WHERE school_year_id=? AND status IN (?,?) ORDER BY id',
                             (year['id'], 'offen', 'teilweise')).fetchall()
        lines = ['<b>Offen im Schuljahr %s</b>' % esc(year['label'])]
        for s in self.stages:
            if key and s['key'] != key:
                continue
            items = [r for r in rows if r['stage'] == s['key']]
            lines.append('<b>%s %s</b>' % (s['emoji'], esc(s['label'])))
            if not items:
                lines.append('🎉 alles erledigt')
            for r in items:
                icon = '🔶' if r['status'] == 'teilweise' else '⬜'
                lines.append('%s %s · %s (%d Std.)' % (icon, esc(r['item_code']), esc(r['item_title']), r['hours']))
        return '\n'.join(lines)

    def bot_username(self):
        if not self._username:
            self._username = (self.call('getMe') or {}).get('username')
        if not self._username:
            raise TelegramError('Bot-Name unbekannt')
        return self._username

    # Einladungen
    def create_invite(self, created_by):
        code = secrets.token_urlsafe(9)
        with self.db() as c:
            c.execute('DELETE FROM tg_invites WHERE expires_at<?', (time.time(),))
            c.execute('INSERT INTO tg_invites(code,created_by,expires_at) VALUES(?,?,?)',
                      (code, str(created_by), time.time() + INVITE_HOURS * 3600))
        return code

    def redeem(self, code, chat_id, name):
        with self.db() as c:
            n = c.execute('UPDATE tg_invites SET used_by=? WHERE code=? AND used_by IS NULL AND expires_at>?',
                          (str(chat_id), code, time.time())).rowcount
            if not n:
                return False
            by = c.execute('SELECT created_by FROM tg_invites WHERE code=?', (code,)).fetchone()['created_by']
            c.execute('INSERT OR REPLACE INTO tg_users(chat_id,name,added_by) VALUES(?,?,?)',
                      (str(chat_id), name[:40], by))
        return True

    def remove_user(self, chat_id):
        with self.db() as c:
            return c.execute('DELETE FROM tg_users WHERE chat_id=?', (str(chat_id),)).rowcount

    # Bildschirme: liefern (Text, Buttons) oder None bei fehlendem Zugriff
    def screen(self, chat_id, data):
        if not self.is_user(chat_id):
            return None
        menu = self.menu_markup(chat_id)
        if data == 'm':
            return ('<b>🏅 Schulcurriculum Sport</b>\nWas möchtest du sehen?', menu)
        if data == 's':
            return (self._status(), kb([[('🔄 Aktualisieren', 's'), ('⬅️ Menü', 'm')]]))
        if data == 'o':
            btns = [('%s %s' % (s['emoji'], s['label'].replace('Klasse ', '')), 'o:' + s['key']) for s in self.stages]
            rows = [btns[i:i + 3] for i in range(0, len(btns), 3)]
            rows.append([('📋 Alle', 'o:all'), ('⬅️ Menü', 'm')])
            return ('<b>📋 Offene Unterrichtsvorhaben</b>\nWelche Klasse?', kb(rows))
        if data.startswith('o:'):
            key = data[2:]
            if key != 'all' and key not in [s['key'] for s in self.stages]:
                return ('Klasse unbekannt.', menu)
            return (self._offen_text(None if key == 'all' else key),
                    kb([[('🔄 Aktualisieren', data), ('📋 Klassen', 'o')], [('⬅️ Menü', 'm')]]))
        if data == 'a' or data.startswith('a:'):
            if not self.is_admin(chat_id):
                return ('⛔ Nur für Admins.', menu)
            return self._admin_screen(chat_id, data)
        return ('Unbekannte Aktion.', menu)

    def _admin_screen(self, chat_id, data):
        back = [('⬅️ Admin', 'a')]
        if data == 'a':
            return ('<b>🛡️ Admin</b>',
                    kb([[('➕ Einladung', 'a:inv'), ('👥 User', 'a:users')],
                        [('🔌 Webhook', 'a:wh'), ('⬅️ Menü', 'm')]]))
        if data == 'a:inv':
            code = self.create_invite(chat_id)
            try:
                body = 'Link zum Weiterleiten:\n%s' % esc('https://t.me/%s?start=%s' % (self.bot_username(), code))
            except TelegramError:
                body = 'Der neue User schickt dem Bot:\n<code>/start %s</code>' % esc(code)
            return ('<b>➕ Einladung</b>\n%s\n\nGültig %d Std., einmal verwendbar, nur in privaten Chats.' % (body, INVITE_HOURS),
                    kb([[('➕ Noch eine', 'a:inv'), back[0]]]))
        if data == 'a:users':
            lines = ['<b>👥 User</b>']
            for a in self.admins():
                lines.append('🛡️ %s (Admin, fest)' % esc(a))
            for s in self.static_chats():
                if s not in self.admins():
                    lines.append('📌 %s (fest in TELEGRAM_CHAT_ID)' % esc(s))
            rows = []
            users = self.db_users()
            for u in users:
                lines.append('👤 %s · %s' % (esc(u['name']), esc(u['chat_id'])))
                rows.append([('🗑️ ' + u['name'][:20], 'a:del:' + u['chat_id'])])
            if not users:
                lines.append('Noch keine eingeladenen User.')
            rows.append([('➕ Einladung', 'a:inv'), back[0]])
            return ('\n'.join(lines), kb(rows))
        if data.startswith('a:del:') or data.startswith('a:rm:'):
            _, action, uid = data.split(':', 2)
            if not uid.isdigit():
                return ('Ungültige ID.', kb([back]))
            name = next((u['name'] for u in self.db_users() if u['chat_id'] == uid), None)
            if name is None:
                return ('User nicht gefunden.', kb([[('👥 User', 'a:users')]]))
            if action == 'del':
                return ('User <b>%s</b> (%s) wirklich entfernen?' % (esc(name), esc(uid)),
                        kb([[('✅ Ja, entfernen', 'a:rm:' + uid), ('Abbrechen', 'a:users')]]))
            self.remove_user(uid)
            return ('User <b>%s</b> entfernt.' % esc(name), kb([[('👥 User', 'a:users')]]))
        if data == 'a:wh':
            try:
                i = self.call('getWebhookInfo') or {}
                text = 'URL: %s\nWartende Updates: %s\nLetzter Fehler: %s' % (
                    esc(i.get('url') or '-'), esc(i.get('pending_update_count', 0)),
                    esc(i.get('last_error_message') or 'keiner'))
            except TelegramError as e:
                text = 'Fehler: %s' % esc(e)
            return ('<b>🔌 Webhook</b>\n' + text, kb([[('🔄 Aktualisieren', 'a:wh'), back[0]]]))
        return ('Unbekannte Aktion.', kb([back]))

    # Eingehende Nachrichten und Button-Klicks
    def handle_message(self, msg):
        chat_id = (msg.get('chat') or {}).get('id')
        text = (msg.get('text') or '').strip()
        if chat_id is None or not text.startswith('/'):
            return None
        parts = text.split()
        cmd = parts[0].split('@')[0].lower()
        arg = parts[1] if len(parts) > 1 else ''
        if cmd == '/id':
            return ('Deine Chat-ID: <code>%s</code>' % esc(chat_id), None)
        if cmd == '/start' and arg and not self.is_user(chat_id):
            name = (msg.get('from') or {}).get('first_name') or 'User'
            if int(chat_id) > 0 and self.redeem(arg, chat_id, name):
                self.notify_admin('👤 <b>%s</b> (%s) hat die Einladung eingelöst' % (esc(name), esc(chat_id)))
                return ('✅ <b>Willkommen!</b> Du bekommst jetzt Meldungen zum Schulcurriculum Sport.',
                        self.menu_markup(chat_id))
            return ('Die Einladung ist ungültig oder abgelaufen.', None)
        if not self.is_user(chat_id):
            return ('⛔ Kein Zugriff. Bitte den Admin um eine Einladung.', None) if cmd == '/start' else None
        if cmd in ('/start', '/menu'):
            return self.screen(chat_id, 'm')
        if cmd == '/status':
            return self.screen(chat_id, 's')
        if cmd == '/offen':
            if not arg:
                return self.screen(chat_id, 'o')
            key = self.stage_key(' '.join(parts[1:]))
            return self.screen(chat_id, 'o:' + key) if key else ('Klasse nicht erkannt. Beispiele: /offen 5, /offen 7/8', None)
        if cmd == '/einladen' and self.is_admin(chat_id):
            return self.screen(chat_id, 'a:inv')
        if cmd == '/user' and self.is_admin(chat_id):
            return self.screen(chat_id, 'a:users')
        if cmd in ('/hilfe', '/help'):
            return (self.help_text(chat_id), self.menu_markup(chat_id))
        return ('Unbekannter Befehl.\n' + self.help_text(chat_id), self.menu_markup(chat_id))

    def _answer_cb(self, cq_id, res, chat_id, message_id):
        try:
            payload = {'callback_query_id': cq_id}
            if not res:
                payload.update({'text': 'Kein Zugriff', 'show_alert': True})
            self.call('answerCallbackQuery', payload)
        except TelegramError as e:
            log.warning('answerCallbackQuery fehlgeschlagen: %s', e)
        if res:
            try:
                self.call('editMessageText', {'chat_id': chat_id, 'message_id': message_id, 'text': res[0][:4000],
                                              'parse_mode': 'HTML', 'disable_web_page_preview': True,
                                              'reply_markup': res[1]})
            except TelegramError as e:
                if 'not modified' not in str(e):
                    log.warning('editMessageText fehlgeschlagen: %s', e)

    def handle_update(self, upd):
        cq = upd.get('callback_query')
        if cq:
            msg = cq.get('message') or {}
            chat_id = (msg.get('chat') or {}).get('id')
            res = self.screen(chat_id, cq.get('data') or '') if chat_id is not None else None
            self._run(self._answer_cb, cq.get('id'), res, chat_id, msg.get('message_id'))
            return
        msg = upd.get('message')
        if msg:
            res = self.handle_message(msg)
            chat_id = (msg.get('chat') or {}).get('id')
            if res and chat_id is not None:
                self._run(self.send, res[0], [str(chat_id)], res[1])

    # Aktionen aus dem Admin-Bereich der Webapp
    def admin_action(self, act):
        if not self.token():
            raise TelegramError('TELEGRAM_BOT_TOKEN ist nicht gesetzt')
        if act == 'tg_test':
            ids = self.users()
            if not ids:
                raise TelegramError('Kein Empfänger: TELEGRAM_ADMIN_CHAT_ID setzen (Chat-ID per /id im Bot-Chat erfragen)')
            for cid in ids:
                self._send_one(cid, '🧪 <b>Testnachricht</b> aus dem Schulcurriculum-Manager')
            return 'Testnachricht gesendet 📲'
        if act == 'tg_set_webhook':
            url = self.public_url()
            if not url.startswith('https://'):
                raise TelegramError('PUBLIC_URL muss mit https:// beginnen')
            self.call('setWebhook', {'url': url + '/telegram/webhook', 'secret_token': self.secret(),
                                     'allowed_updates': ['message', 'callback_query'], 'drop_pending_updates': True})
            return 'Webhook gesetzt: %s/telegram/webhook ✅' % url
        if act == 'tg_delete_webhook':
            self.call('deleteWebhook', {'drop_pending_updates': True})
            return 'Webhook entfernt'
        if act == 'tg_info':
            i = self.call('getWebhookInfo') or {}
            return 'Webhook: %s · wartende Updates: %s · letzter Fehler: %s' % (
                i.get('url') or '-', i.get('pending_update_count', 0), i.get('last_error_message') or 'keiner')
        raise TelegramError('Unbekannte Aktion')

    def register(self, app):
        app.extensions['telegram'] = self
        bot = self

        @app.post('/telegram/webhook')
        def telegram_webhook():
            sent = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
            if not bot.token() or not secrets.compare_digest(sent.encode(), bot.secret().encode()):
                abort(403)
            try:
                bot.handle_update(request.get_json(silent=True) or {})
            except Exception:  # sonst wiederholt Telegram das Update endlos
                log.exception('Telegram-Update konnte nicht verarbeitet werden')
            return jsonify(ok=True)
