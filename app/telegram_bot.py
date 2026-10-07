# Telegram-Anbindung: Benachrichtigungen und Bot-Befehle (nur Standardbibliothek)
import html
import json
import logging
import os
import re
import secrets
import threading
import urllib.error
import urllib.request

from flask import abort, jsonify, request

log = logging.getLogger('schulcurri.telegram')
SECRET_RE = re.compile(r'^[A-Za-z0-9_-]{1,256}$')
HELP = ('<b>Befehle</b>\n/status - Fortschritt je Klasse\n'
        '/offen [Klasse] - offene Unterrichtsvorhaben, z. B. /offen 7/8\n'
        '/id - Chat-ID anzeigen\n/hilfe - diese Hilfe')


class TelegramError(ValueError):
    pass


def esc(v):
    return html.escape(str(v), quote=False)


class Bot:
    def __init__(self, data_dir, db, current_year, progress, stages):
        self.data_dir = data_dir
        self.db = db
        self.current_year = current_year
        self.progress = progress
        self.stages = stages
        self.async_send = True

    # Konfiguration: wird bei jedem Zugriff aus der Umgebung gelesen
    def token(self):
        return os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()

    def chats(self):
        return [x.strip() for x in os.environ.get('TELEGRAM_CHAT_ID', '').split(',') if x.strip()]

    def public_url(self):
        return os.environ.get('PUBLIC_URL', '').strip().rstrip('/')

    def enabled(self):
        return bool(self.token() and self.chats())

    def status(self):
        return {'token': bool(self.token()), 'chats': len(self.chats()), 'public_url': self.public_url()}

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

    def _send_one(self, chat_id, text):
        self.call('sendMessage', {'chat_id': chat_id, 'text': text[:4000], 'parse_mode': 'HTML',
                                  'disable_web_page_preview': True})

    def send(self, text, chat_ids=None):
        ids = self.chats() if chat_ids is None else chat_ids
        if not self.token() or not ids:
            return False
        ok = True
        for cid in ids:
            try:
                self._send_one(cid, text)
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
        if self.enabled():
            self._run(self.send, text)

    # Bot-Befehle
    def stage_key(self, arg):
        a = re.sub(r'(?i)klasse|kl\.?|\s|\.', '', arg).replace('/', '')
        if a in ('7', '8', '78'):
            a = '78'
        return a if a in [s['key'] for s in self.stages] else None

    def handle_command(self, text, chat_id):
        parts = text.split()
        cmd = parts[0].split('@')[0].lower()
        arg = ' '.join(parts[1:])
        if cmd == '/id':
            return 'Deine Chat-ID: <code>%s</code>\nTrage sie in TELEGRAM_CHAT_ID ein.' % esc(chat_id)
        if str(chat_id) not in self.chats():
            return None
        if cmd in ('/start', '/hilfe', '/help'):
            return HELP
        if cmd == '/status':
            return self._status()
        if cmd == '/offen':
            return self._offen(arg)
        return 'Unbekannter Befehl.\n' + HELP

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

    def _offen(self, arg):
        key = None
        if arg:
            key = self.stage_key(arg)
            if key is None:
                return 'Klasse nicht erkannt. Beispiele: /offen 5, /offen 7/8'
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

    # Aktionen aus dem Admin-Bereich
    def admin_action(self, act):
        if not self.token():
            raise TelegramError('TELEGRAM_BOT_TOKEN ist nicht gesetzt')
        if act == 'tg_test':
            if not self.chats():
                raise TelegramError('TELEGRAM_CHAT_ID ist nicht gesetzt (Chat-ID per /id im Bot-Chat erfragen)')
            for cid in self.chats():
                self._send_one(cid, '🧪 <b>Testnachricht</b> aus dem Schulcurriculum-Manager')
            return 'Testnachricht gesendet 📲'
        if act == 'tg_set_webhook':
            url = self.public_url()
            if not url.startswith('https://'):
                raise TelegramError('PUBLIC_URL muss mit https:// beginnen')
            self.call('setWebhook', {'url': url + '/telegram/webhook', 'secret_token': self.secret(),
                                     'allowed_updates': ['message'], 'drop_pending_updates': True})
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
            msg = (request.get_json(silent=True) or {}).get('message') or {}
            chat_id = (msg.get('chat') or {}).get('id')
            text = (msg.get('text') or '').strip()
            if chat_id is not None and text.startswith('/'):
                reply = bot.handle_command(text, chat_id)
                if reply:
                    bot._run(bot.send, reply, [str(chat_id)])
            return jsonify(ok=True)
