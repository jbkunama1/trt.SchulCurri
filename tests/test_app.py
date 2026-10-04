import os
import re
import sys

import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), '..', 'app')


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ADMIN_PASSWORD', 'testpass123')
    monkeypatch.syspath_prepend(APP_DIR)
    for name in ('server', 'curriculum'):
        sys.modules.pop(name, None)
    import server
    server.app.config['TESTING'] = True
    return server


def token(client, path='/login'):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


def login(client, user='admin', pw='testpass123'):
    return client.post('/login', data={'username': user, 'password': pw, 'csrf_token': token(client)})


def post(client, path, data):
    data = dict(data, csrf_token=token(client, '/'))
    return client.post(path, data=data, follow_redirects=True)


def test_curriculum_hours_add_up(env):
    import curriculum
    for s in curriculum.STAGES:
        assert sum(i[3] for i in curriculum.CURRICULUM[s['key']]) == s['hours'], s['key']
        assert s['kc'] + s['sc'] == s['hours']


def test_health_and_login_required(env):
    c = env.app.test_client()
    assert c.get('/health').get_json() == {'status': 'ok'}
    assert c.get('/').status_code == 302
    assert c.post('/api/checklist', json={}).status_code in (400, 401)


def test_csrf_enforced_on_login(env):
    c = env.app.test_client()
    assert c.post('/login', data={'username': 'admin', 'password': 'testpass123'}).status_code == 400


def test_login_wrong_password(env):
    c = env.app.test_client()
    r = c.post('/login', data={'username': 'admin', 'password': 'falsch', 'csrf_token': token(c)})
    assert 'falsch' in r.get_data(as_text=True)
    assert c.get('/').status_code == 302


def test_year_checklist_and_export(env):
    c = env.app.test_client()
    assert login(c).status_code == 302
    post(c, '/admin', {'action': 'add_year', 'label': '2026/27'})
    html = c.get('/klasse/5').get_data(as_text=True)
    assert 'Spielen' in html
    with env.db() as con:
        item = con.execute('SELECT id FROM checklist WHERE stage=? ORDER BY id', ('5',)).fetchone()['id']
    hdr = {'X-CSRF-Token': token(c, '/')}
    assert c.post('/api/checklist', json={'id': item, 'status': 'erledigt', 'note': '=1+1'}, headers=hdr).status_code == 200
    assert c.post('/api/checklist', json={'id': item, 'status': 'kaputt', 'note': ''}, headers=hdr).status_code == 400
    assert c.post('/api/checklist', json={'id': 99999, 'status': 'offen', 'note': ''}, headers=hdr).status_code == 404
    csv_text = c.get('/export/5.csv').get_data(as_text=True)
    assert "'=1+1" in csv_text
    assert c.get('/export/xyz.csv').status_code == 404
    assert c.get('/export/5.json').get_json()['school_year'] == '2026/27'


def test_teacher_cannot_open_admin(env):
    admin = env.app.test_client()
    login(admin)
    post(admin, '/admin', {'action': 'add_user', 'username': 'lehrer1', 'display_name': 'L1',
                           'password': 'geheim1234', 'role': 'teacher'})
    teacher = env.app.test_client()
    assert login(teacher, 'lehrer1', 'geheim1234').status_code == 302
    assert teacher.get('/admin').status_code == 403
    assert teacher.get('/export/backup.db').status_code == 403
    assert admin.get('/export/backup.db').status_code == 200


def test_deactivated_user_loses_access(env):
    admin = env.app.test_client()
    login(admin)
    post(admin, '/admin', {'action': 'add_user', 'username': 'lehrer2', 'display_name': 'L2',
                           'password': 'geheim1234', 'role': 'teacher'})
    teacher = env.app.test_client()
    login(teacher, 'lehrer2', 'geheim1234')
    assert teacher.get('/').status_code == 200
    with env.db() as con:
        uid = con.execute('SELECT id FROM users WHERE username=?', ('lehrer2',)).fetchone()['id']
    post(admin, '/admin', {'action': 'toggle_user', 'user_id': str(uid)})
    assert teacher.get('/').status_code == 302
