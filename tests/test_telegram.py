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
        return {}

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


def hook(env, client, text, chat=42, secret=True):
    headers = {'X-Telegram-Bot-Api-Secret-Token': env.tg.secret()} if secret else {}
    return client.post('/telegram/webhook', json={'message': {'chat': {'id': chat}, 'text': text}}, headers=headers)


def messages(env, chat):
    return [p['text'] for m, p in env.sent if m == 'sendMessage' and p['chat_id'] == chat]


def test_webhook_requires_secret(env):
    c = env.app.test_client()
    assert hook(env, c, '/status', secret=False).status_code == 403
    bad = c.post('/telegram/webhook', json={}, headers={'X-Telegram-Bot-Api-Secret-Token': 'falsch'})
    assert bad.status_code == 403
    assert hook(env, c, '/status').status_code == 200


def test_id_command_answers_any_chat(env):
    c = env.app.test_client()
    assert hook(env, c, '/id', chat=999).status_code == 200
    assert '999' in messages(env, '999')[0]


def test_status_only_for_allowed_chat(env):
    make_year(env)
    c = env.app.test_client()
    hook(env, c, '/status', chat=999)
    assert messages(env, '999') == []
    hook(env, c, '/status@curribot', chat=42)
    text = messages(env, '42')[0]
    assert '2026/27' in text and 'Klasse 5' in text


def test_offen_lists_open_items(env):
    make_year(env)
    c = env.app.test_client()
    hook(env, c, '/offen 5')
    text = messages(env, '42')[0]
    assert 'UV 1' in text and 'Klasse 5' in text and 'Klasse 6' not in text
    hook(env, c, '/offen 7/8')
    assert 'Klasse 7/8' in messages(env, '42')[1]


def test_done_status_notifies_once(env):
    make_year(env)
    c = env.app.test_client()
    login(c)
    with env.db() as con:
        item = con.execute('SELECT id FROM checklist WHERE stage=? ORDER BY id', ('5',)).fetchone()['id']
    hdr = {'X-CSRF-Token': token(c, '/')}
    payload = {'id': item, 'status': 'erledigt', 'note': ''}
    assert c.post('/api/checklist', json=payload, headers=hdr).status_code == 200
    assert len(messages(env, '42')) == 1 and 'erledigt' in messages(env, '42')[0]
    assert c.post('/api/checklist', json=payload, headers=hdr).status_code == 200
    assert len(messages(env, '42')) == 1


def test_admin_test_message_and_page(env):
    c = env.app.test_client()
    login(c)
    assert 'Telegram' in c.get('/admin').get_data(as_text=True)
    c.post('/admin', data={'action': 'tg_test', 'csrf_token': token(c, '/admin')})
    assert any('Testnachricht' in t for t in messages(env, '42'))


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
    assert hook(env, c, '/status').status_code == 403
