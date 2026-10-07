# 🏅 trt.SchulCurri – Schulcurriculum Sport (Realschule BW)

Jahresplanung **Sport, Klassen 5–10**, Realschule Baden-Württemberg, nach **Bildungsplan 2016 (Sek I)**: Inhalte als Markdown, statische Seite für GitHub Pages und eine Webapp (Flask + SQLite) für das Fachkollegium, optional mit Telegram-Anbindung.

🌐 **Statische Seite (GitHub Pages):** https://jbkunama1.github.io/trt.SchulCurri/

> ⚠️ **Status: Entwurf zur Abstimmung.** Kl. 5/6 und Kl. 10 orientieren sich an den Beispielcurricula des Landesinstituts (schule-bw.de), Kl. 7/8 und Kl. 9 sind Vorschläge. Vor dem Beschluss gegen die Originale in [docs/quellen.md](docs/quellen.md) prüfen.

## 📦 Inhalt

| Pfad | Inhalt |
|------|--------|
| `index.html` | GitHub-Pages-Seite (Präsentation, Planung, Checklisten im Browser-Speicher) |
| `curriculum/`, `vorlagen/`, `docs/` | Planung je Klasse, leere Jahrestabelle, Quellen, [Telegram-Anleitung](docs/telegram.md) |
| `app/` | Webapp: `server.py`, `curriculum.py` (Datenquelle), `telegram_bot.py`, `templates/`, `static/` |
| `tests/` | pytest-Tests (Rechte, CSRF, Export, Curriculum-Summen, Telegram) |
| `Dockerfile`, `docker-compose.yml` | Container für Portainer |
| `.github/workflows/docker.yml` | CI: Tests, danach Image nach GHCR |

## 📐 Eckdaten

| Klasse | Std./Jahr | Kerncurriculum | Schulcurriculum | Quelle |
|--------|-----------|----------------|-----------------|--------|
| 5 | 105 | 78 | 27 | Beispielcurriculum |
| 6 | 105 | 92 | 13 | Beispielcurriculum |
| 7/8 | 70 | 54 | 16 | Vorschlag |
| 9 | 70 | 54 | 16 | Vorschlag |
| 10 | 70 | 54 | 16 | Beispielcurriculum |

## 🐳 Webapp starten

**Mit Docker (Portainer-Stack oder CLI):**

```bash
git clone https://github.com/jbkunama1/trt.SchulCurri.git && cd trt.SchulCurri
docker compose up -d --build
docker logs schulcurri   # zeigt beim ersten Start das erzeugte Admin-Passwort
```

Alternativ das fertige Image ziehen: `docker compose pull`. Das Paket auf GHCR ist standardmäßig privat; unter *Packages → trt.schulcurri → Package settings* auf *Public* stellen oder per `docker login ghcr.io` anmelden.

**Ohne Docker:**

```bash
pip install -r app/requirements.txt
cd app && python server.py     # http://127.0.0.1:8080
```

### Konfiguration (Umgebungsvariablen)

| Variable | Bedeutung | Standard |
|----------|-----------|----------|
| `ADMIN_PASSWORD` | Passwort des ersten Admins (nur beim allerersten Start) | zufällig, im Container-Log |
| `SECRET_KEY` | Session-Schlüssel | wird in `/data/.secret_key` erzeugt |
| `COOKIE_SECURE` | `1` = Cookies nur über HTTPS | `0` |
| `TRUST_PROXY` | `1` = `X-Forwarded-*` eines Reverse-Proxys auswerten | `0` |
| `DATA_DIR` | Ablage der SQLite-Datei `schulcurri.db` | `app/data`, im Container `/data` |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `PUBLIC_URL`, `TELEGRAM_WEBHOOK_SECRET` | Telegram, siehe [docs/telegram.md](docs/telegram.md) | leer = aus |

Hinter Cloudflare/Reverse-Proxy mit HTTPS: `COOKIE_SECURE=1` und `TRUST_PROXY=1` setzen. Die App spricht selbst kein TLS.

## 📲 Telegram (optional)

Meldungen bei erledigten Unterrichtsvorhaben und neuen Schuljahren sowie die Befehle `/status`, `/offen [Klasse]` und `/id`. Einrichtung, Sicherheit und Grenzen: [docs/telegram.md](docs/telegram.md).

## 🔐 Sicherheit (Stand der Umsetzung)

- Passwörter als Hash (werkzeug), Mindestlänge 8, Login-Drosselung (5 Fehlversuche je 5 Minuten und IP)
- CSRF-Token für alle POST-Anfragen außer dem Telegram-Webhook, der ein eigenes Secret im Header prüft; strikte Content-Security-Policy ohne Inline-JS
- Deaktivierte Benutzer verlieren sofort den Zugriff; Admin-Routen nur für Rolle `admin`
- CSV-Export gegen Formel-Injektion abgesichert; Backup nur für Admins
- Container läuft als Nicht-Root-Benutzer
- Grenzen: keine 2FA, kein Passwort-Reset per Mail (Reset durch Admin), Login-Drosselung nur im Arbeitsspeicher

## 🛠️ Roadmap

- [x] Basics: Inhalte, README, GitHub-Pages-Index
- [x] Webapp mit Benutzerverwaltung, Admin, Export, Themes
- [x] Container und CI-Build
- [x] Telegram-Anbindung (Benachrichtigungen, Befehle)
- [ ] Webapp im Betrieb testen (Portainer), Rückmeldungen der Fachschaft einarbeiten
- [ ] Stundenzahlen gegen die Beispielcurricula abgleichen

## ⚖️ Hinweis

Inhalte basieren auf dem öffentlichen Bildungsplan 2016 Baden-Württemberg. Für schulische Zwecke frei nutzbar.
