# 📲 Telegram-Anbindung

Die Webapp kann (optional) Meldungen per Telegram senden und über Inline-Buttons bedient werden. Ohne `TELEGRAM_BOT_TOKEN` bleibt alles aus.

## Rollen

| Rolle | Wie festgelegt | Darf |
|-------|----------------|------|
| **Admin** | fest in `TELEGRAM_ADMIN_CHAT_ID` (nur private Chats, positive IDs) | alles, was User dürfen, plus Einladungen erzeugen, User entfernen, Webhook-Status sehen, Verwaltungsmeldungen erhalten |
| **User** | vom Admin per Einladungslink angelegt (gespeichert in der Datenbank) oder fest in `TELEGRAM_CHAT_ID` (z. B. eine Gruppe) | Meldungen erhalten, `/status`, `/offen`, Menü |
| Fremde | alle anderen | nur `/id` (liefert die eigene Chat-ID) |

Admins werden nie über den Bot angelegt, sondern nur in der Konfiguration. Eine Gruppen-ID (negativ) in `TELEGRAM_ADMIN_CHAT_ID` wird ignoriert, damit nicht jedes Gruppenmitglied Admin wird.

## Was passiert

| Ereignis | Empfänger |
|----------|-----------|
| Ein Unterrichtsvorhaben wird auf ✅ erledigt gesetzt (nur beim Wechsel) | alle User und Admins |
| Schuljahr angelegt, kopiert oder aktiviert | nur Admins |
| Ein User löst eine Einladung ein | nur Admins |

## Bedienung

`/menu` (oder `/start`) zeigt die Buttons:

- **📊 Status**: Fortschritt je Klasse, mit 🔄 Aktualisieren
- **📋 Offen**: Klassenauswahl (🎒 5, 🧢 6, 🏐 7/8, 🚴 9, 🏸 10 oder Alle), mit 🔄 Aktualisieren
- **🛡️ Admin** (nur Admins): ➕ Einladung, 👥 User (entfernen mit Rückfrage), 🔌 Webhook-Status

Buttons ersetzen die bestehende Nachricht, der Chat bleibt übersichtlich. Die Textbefehle funktionieren weiterhin: `/status`, `/offen [Klasse]` (z. B. `/offen 7/8`), `/id`, `/hilfe`, für Admins zusätzlich `/einladen` und `/user`.

## User anlegen (durch den Admin)

1. Im Bot: `/menu` → 🛡️ Admin → ➕ Einladung (oder `/einladen`).
2. Den erzeugten Link `https://t.me/<Bot>?start=<Code>` an die Person schicken.
3. Die Person öffnet den Link und drückt *Start*. Der Admin erhält eine Meldung.

Eine Einladung gilt 48 Stunden, ist einmal verwendbar und kann nur in einem privaten Chat eingelöst werden. Entfernen: 🛡️ Admin → 👥 User → Name → „Ja, entfernen“. Fest konfigurierte Chats lassen sich nur in der Konfiguration ändern.

## Einrichtung

1. In Telegram mit `@BotFather` einen Bot anlegen (`/newbot`) und den **Token** notieren.
2. Im Portainer-Stack setzen: `TELEGRAM_BOT_TOKEN` und `PUBLIC_URL` (z. B. `https://curri.example.org`, muss `https://` sein und von außen erreichbar). Stack neu starten.
3. In der Webapp als Admin: *Administration → Telegram → Webhook setzen*, danach *Status prüfen*. Nach einem Update dieser Funktion den Webhook erneut setzen, sonst kommen Button-Klicks nicht an.
4. Dem Bot in einem privaten Chat `/id` schicken und die Zahl in `TELEGRAM_ADMIN_CHAT_ID` eintragen (mehrere Admins durch Komma getrennt). Stack neu starten, *Testnachricht* senden.

## Konfiguration

| Variable | Bedeutung |
|----------|-----------|
| `TELEGRAM_BOT_TOKEN` | Token von BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | Admin-Chat-IDs, Komma-getrennt, nur Ziffern |
| `TELEGRAM_CHAT_ID` | Optional: feste User-Chats, auch Gruppen (negative IDs) |
| `PUBLIC_URL` | Öffentliche Basis-URL der Webapp für den Webhook |
| `TELEGRAM_WEBHOOK_SECRET` | Optional, nur `A-Z a-z 0-9 _ -`, 1–256 Zeichen. Leer = wird erzeugt und in `/data/.telegram_secret` gespeichert. |

## Sicherheit und Datenschutz

- Der Webhook `/telegram/webhook` akzeptiert nur Anfragen mit dem Header `X-Telegram-Bot-Api-Secret-Token`, der dem Secret entspricht (Vergleich in konstanter Zeit). Alles andere erhält 403.
- Jeder Button-Klick prüft die Berechtigung neu auf dem Server. Ein User, der eine Admin-Aktion auslöst (z. B. durch eine weitergeleitete Nachricht), bekommt „Nur für Admins“.
- Einladungs-Codes sind zufällig, einmalig und laufen ab. Die Datenbank speichert pro eingeladenem User nur Chat-ID, Vorname laut Telegram, wer eingeladen hat und das Datum.
- Der Token steht nie in Fehlermeldungen oder Logs der App.
- Meldungen enthalten Klassenfortschritt, UV-Titel und den **Benutzernamen** der Webapp-Person. Keine Notizen, keine Schülerdaten. In Gruppen sehen alle Mitglieder diese Benutzernamen.
- `/id` ist absichtlich offen und liefert nur die eigene Chat-ID.
- Der Webhook muss über HTTPS erreichbar sein (Ports 443, 80, 88 oder 8443).

## Grenzen

- Telegram-User sind nicht mit Webapp-Konten verknüpft. Wird ein Webapp-Konto deaktiviert, ändert das nichts an Telegram; User dort entfernt der Admin im Bot.
- Keine Warteschlange und keine Wiederholung: Ist Telegram nicht erreichbar, geht die Meldung verloren (Warnung im Container-Log).
- Meldungen werden in einem Hintergrund-Thread gesendet; der Speichervorgang wartet nicht darauf.

## Fehlersuche

- *Administration → Telegram → Status prüfen* oder im Bot 🛡️ Admin → 🔌 Webhook zeigen URL, wartende Updates und den letzten Fehler von Telegram.
- `chat not found` beim Test heißt, dass der Bot den Chat nicht kennt (im privaten Chat zuerst *Start* drücken). `bot was blocked by the user` heißt, dass der Bot blockiert wurde.
- Bleibt `/id` ohne Antwort, ist meist `PUBLIC_URL` falsch, der Webhook nicht gesetzt oder der Reverse-Proxy leitet `/telegram/webhook` nicht an die App weiter.
- Buttons reagieren nicht: Webhook nach dem Update erneut setzen (er muss `callback_query` zustellen).
