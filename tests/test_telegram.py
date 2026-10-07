import os
import re
import sys

import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), '..', 'app')


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ADMIN_PASSWORD', 'testpass123')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', '123:TESTTOKEN')
    monkeypatch.setenv('TELEGRAM_ADMIN_CHAT_ID', '7')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', '42')
    monkeypatch.setenv('PUBLIC_URL', 'https://curri.example.org')
    monkeypatch.syspath_prepend(APP_DIR)
    for name in ('server', 'curriculum', 'telegram_bot'):
        sys.modules.pop(name, None)
    import server
    server.app.config['TESTING'] = True
    server.tg.async_send = False
    server.sent = []

    def fake_call(method, payload=None, timeout=8):
        server.sent.append((method, payload))
        return {'username': 'curribot'} if method == 'getMe' else {}

    server.tg.call = fake_call
    return server


def make_year(env):
    with env.db() as c:
        yid = c.execute('INSERT INTO school_years(label, active) VALUES(?, 1)', ('2026/27',)).lastrowid
        env.seed_year(c, yid)


def token(client, path='/login'):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


def login(client):
    return client.post('/login', data={'username': 'admin', 'password': 'testpass123', 'csrf_token': token(client)})


def msg(chat, text, name='Test'):
    return {'message': {'chat': {'id': chat}, 'from': {'first_name': name}, 'text': text}}


def cb(chat, data):
    return {'callback_query': {'id': 'cb1', 'data': data, 'message': {'message_id': 9, 'chat': {'id': chat}}}}


def post(env, client, update, secret=True):
    headers = {'X-Telegram-Bot-Api-Secret-Token': env.tg.secret()} if secret else {}
    return client.post('/telegram/webhook', json=update, headers=headers)


def sends(env, chat):
    return [p['text'] for m, p in env.sent if m == 'sendMessage' and str(p['chat_id']) == str(chat)]


def edits(env, chat):
    return [p['text'] for m, p in env.sent if m == 'editMessageText' and str(p['chat_id']) == str(chat)]


def answers(env):
    return [p for m, p in env.sent if m == 'answerCallbackQuery']


def tg_users(env):
    with env.db() as c:
        return [r['chat_id'] for r in c.execute('SELECT chat_id FROM tg_users ORDER BY chat_id')]


def invite(env, client, chat=7):
    post(env, client, cb(chat, 'a:inv'))
    return re.search(r'start=([A-Za-z0-9_-]+)', edits(env, chat)[-1]).group(1)


def test_webhook_requires_secret(env):
    c = env.app.test_client()
    assert post(env, c, msg(42, '/status'), secret=False).status_code == 403
    bad = c.post('/telegram/webhook', json={}, headers={'X-Telegram-Bot-Api-Secret-Token': 'falsch'})
    assert bad.status_code == 403
    assert post(env, c, msg(42, '/status')).status_code == 200


def test_id_answers_everyone_but_strangers_get_nothing_else(env):
    c = env.app.test_client()
    post(env, c, msg(999, '/id'))
    assert '999' in sends(env, 999)[0]
    post(env, c, msg(999, '/status'))
    assert len(sends(env, 999)) == 1
    post(env, c, msg(999, '/start'))
    assert 'Kein Zugriff' in sends(env, 999)[1]


def test_user_gets_status_with_buttons(env):
    make_year(env)
    c = env.app.test_client()
    post(env, c, msg(42, '/status@curribot'))
    assert '2026/27' in sends(env, 42)[0]
    markup = [p for m, p in env.sent if m == 'sendMessage' and str(p['chat_id']) == '42'][0]['reply_markup']
    assert 's' in {b['callback_data'] for row in markup['inline_keyboard'] for b in row}


def test_button_click_edits_message(env):
    make_year(env)
    c = env.app.test_client()
    post(env, c, cb(42, 'o:5'))
    assert 'Klasse 5' in edits(env, 42)[0] and 'Klasse 6' not in edits(env, 42)[0]
    assert answers(env)[0]['callback_query_id'] == 'cb1' and 'show_alert' not in answers(env)[0]
    post(env, c, cb(42, 'o:78'))
    assert 'Klasse 7/8' in edits(env, 42)[1]


def test_stranger_click_is_rejected(env):
    c = env.app.test_client()
    post(env, c, cb(999, 'a:inv'))
    assert edits(env, 999) == []
    assert answers(env)[0]['show_alert'] is True
    assert tg_users(env) == []


def test_user_cannot_use_admin_buttons(env):
    c = env.app.test_client()
    post(env, c, cb(42, 'a:inv'))
    assert 'Nur für Admins' in edits(env, 42)[0]
    with env.db() as con:
        assert con.execute('SELECT COUNT(*) FROM tg_invites').fetchone()[0] == 0
    post(env, c, msg(42, '/einladen'))
    assert 'Unbekannter Befehl' in sends(env, 42)[0]


def test_admin_invites_user_who_joins_once(env):
    make_year(env)
    c = env.app.test_client()
    code = invite(env, c)
    post(env, c, msg(555, '/start ' + code, name='Anna'))
    assert any('Willkommen' in t for t in sends(env, 555))
    assert any('Anna' in t for t in sends(env, 7))
    assert tg_users(env) == ['555']
    post(env, c, msg(556, '/start ' + code))
    assert 'ungültig' in sends(env, 556)[0]
    assert tg_users(env) == ['555']
    post(env, c, msg(555, '/status'))
    assert any('2026/27' in t for t in sends(env, 555))


def test_invite_cannot_be_redeemed_in_group_or_after_expiry(env):
    c = env.app.test_client()
    code = invite(env, c)
    post(env, c, msg(-100123, '/start ' + code))
    assert tg_users(env) == []
    with env.db() as con:
        con.execute('UPDATE tg_invites SET expires_at=0')
    post(env, c, msg(555, '/start ' + code))
    assert tg_users(env) == []


def test_admin_removes_user_with_confirmation(env):
    c = env.app.test_client()
    post(env, c, msg(555, '/start ' + invite(env, c), name='Anna'))
    post(env, c, cb(7, 'a:del:555'))
    assert 'wirklich entfernen' in edits(env, 7)[-1] and tg_users(env) == ['555']
    post(env, c, cb(7, 'a:rm:555'))
    assert 'entfernt' in edits(env, 7)[-1] and tg_users(env) == []
    before = len(sends(env, 555))
    post(env, c, msg(555, '/status'))
    assert len(sends(env, 555)) == before


def test_group_ids_cannot_be_admin(env, monkeypatch):
    monkeypatch.setenv('TELEGRAM_ADMIN_CHAT_ID', '7,-100,abc')
    assert env.tg.admins() == ['7']


def test_notifications_reach_users_but_admin_events_only_admins(env):
    make_year(env)
    c = env.app.test_client()
    login(c)
    with env.db() as con:
        item = con.execute('SELECT id FROM checklist WHERE stage=? ORDER BY id', ('5',)).fetchone()['id']
    hdr = {'X-CSRF-Token': token(c, '/')}
    payload = {'id': item, 'status': 'erledigt', 'note': ''}
    assert c.post('/api/checklist', json=payload, headers=hdr).status_code == 200
    assert len(sends(env, 42)) == 1 and len(sends(env, 7)) == 1
    assert c.post('/api/checklist', json=payload, headers=hdr).status_code == 200
    assert len(sends(env, 42)) == 1
    c.post('/admin', data={'action': 'add_year', 'label': '2027/28', 'csrf_token': token(c, '/admin')})
    assert any('2027/28' in t for t in sends(env, 7))
    assert not any('2027/28' in t for t in sends(env, 42))


def test_admin_page_and_test_message(env):
    c = env.app.test_client()
    login(c)
    assert 'Telegram' in c.get('/admin').get_data(as_text=True)
    c.post('/admin', data={'action': 'tg_test', 'csrf_token': token(c, '/admin')})
    assert any('Testnachricht' in t for t in sends(env, 42))
    c.post('/admin', data={'action': 'tg_set_webhook', 'csrf_token': token(c, '/admin')})
    hook = [p for m, p in env.sent if m == 'setWebhook'][0]
    assert 'callback_query' in hook['allowed_updates'] and hook['url'].endswith('/telegram/webhook')


def test_without_token_nothing_is_sent(env, monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN')
    make_year(env)
    c = env.app.test_client()
    login(c)
    with env.db() as con:
        item = con.execute('SELECT id FROM checklist ORDER BY id').fetchone()['id']
    hdr = {'X-CSRF-Token': token(c, '/')}
    assert c.post('/api/checklist', json={'id': item, 'status': 'erledigt', 'note': ''}, headers=hdr).status_code == 200
    assert env.sent == []
    assert post(env, c, msg(42, '/status')).status_code == 403
