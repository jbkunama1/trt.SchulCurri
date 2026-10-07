# 📲 Telegram-Anbindung

Die Webapp kann (optional) Meldungen an einen Telegram-Chat oder eine Gruppe senden und auf Bot-Befehle antworten. Ohne `TELEGRAM_BOT_TOKEN` bleibt alles aus.

## Was passiert

| Ereignis | Nachricht |
|----------|-----------|
| Ein Unterrichtsvorhaben wird auf ✅ erledigt gesetzt (nur beim Wechsel, nicht bei jedem Speichern) | Klasse, UV, Benutzername, Fortschritt der Klasse |
| Schuljahr angelegt, kopiert oder aktiviert | Schuljahr und Benutzername |

Befehle (nur in Chats aus `TELEGRAM_CHAT_ID`, außer `/id`):

| Befehl | Antwort |
|--------|---------|
| `/status` | Fortschritt je Klasse (Prozent und Anzahl erledigt/teilweise/offen) |
| `/offen` oder `/offen 7/8` | Offene und teilweise erledigte Unterrichtsvorhaben, optional für eine Klasse |
| `/id` | Chat-ID des aktuellen Chats (antwortet jedem, der den Bot anschreibt) |
| `/hilfe` | Befehlsübersicht |

## Einrichtung

1. In Telegram mit `@BotFather` einen Bot anlegen (`/newbot`) und den **Token** notieren.
2. In der Compose-Datei bzw. im Portainer-Stack setzen: `TELEGRAM_BOT_TOKEN`, `PUBLIC_URL` (z. B. `https://curri.example.org`, muss `https://` sein und von außen erreichbar). `TELEGRAM_CHAT_ID` bleibt zunächst leer. Stack neu starten.
3. In der Webapp als Admin: *Administration → Telegram → Webhook setzen*, danach *Status prüfen*.
4. Dem Bot in Telegram `/id` schicken (oder den Bot in eine Gruppe einladen und dort `/id` senden). Gruppen-IDs sind negativ.
5. Die ID in `TELEGRAM_CHAT_ID` eintragen (mehrere durch Komma getrennt), Stack neu starten, *Testnachricht* senden.

## Konfiguration

| Variable | Bedeutung |
|----------|-----------|
| `TELEGRAM_BOT_TOKEN` | Token von BotFather |
| `TELEGRAM_CHAT_ID` | Erlaubte Chat-IDs (Komma-getrennt). Nur diese Chats erhalten Meldungen und dürfen `/status` und `/offen` nutzen. |
| `PUBLIC_URL` | Öffentliche Basis-URL der Webapp für den Webhook |
| `TELEGRAM_WEBHOOK_SECRET` | Optional, nur `A-Z a-z 0-9 _ -`, 1–256 Zeichen. Leer = wird erzeugt und in `/data/.telegram_secret` gespeichert. |

## Sicherheit und Datenschutz

- Der Webhook `/telegram/webhook` akzeptiert nur Anfragen mit dem Header `X-Telegram-Bot-Api-Secret-Token`, der dem gesetzten Secret entspricht (Vergleich in konstanter Zeit). Alles andere erhält 403.
- Der Token steht nie in Fehlermeldungen oder Logs der App.
- Nachrichten enthalten nur Klassenfortschritt, UV-Titel und den **Benutzernamen** der bearbeitenden Person. Keine Notizen, keine Schülerdaten. In Gruppen sehen alle Mitglieder diese Benutzernamen.
- `/id` ist absichtlich offen, damit die Einrichtung funktioniert. Es gibt nur die eigene Chat-ID zurück.
- Der Webhook muss über HTTPS erreichbar sein. Telegram unterstützt dafür die Ports 443, 80, 88 und 8443.

## Grenzen

- Keine Warteschlange und keine Wiederholung: Ist Telegram nicht erreichbar, geht die Meldung verloren (Warnung im Container-Log).
- Meldungen werden in einem Hintergrund-Thread gesendet; der Speichervorgang wartet nicht darauf.
- Es gibt keine automatische Wochenzusammenfassung. `/status` liefert den aktuellen Stand auf Abruf.

## Fehlersuche

- *Administration → Telegram → Status prüfen* zeigt die eingetragene URL, wartende Updates und den letzten Fehler von Telegram.
- Typische Antworten von Telegram beim Testen: `chat not found` heißt, dass der Bot den Chat nicht kennt (im privaten Chat zuerst *Start* drücken, bei Gruppen den Bot einladen). `bot was blocked by the user` heißt, dass der Bot blockiert wurde.
- Bleibt `/id` ohne Antwort, ist meist `PUBLIC_URL` falsch, der Webhook nicht gesetzt oder der Reverse-Proxy leitet `/telegram/webhook` nicht an die App weiter.
