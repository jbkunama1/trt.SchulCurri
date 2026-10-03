# 🏅 trt.SchulCurri – Schulcurriculum Sport (Realschule BW)

Jahresplanung **Sport, Klassen 5–10**, Realschule Baden-Württemberg, nach **Bildungsplan 2016 (Sek I)**. Gedacht als Grundlage für die Fachkonferenz-Abstimmung und als **Übergabedokument** ans Folgejahr.

🌐 **Live (GitHub Pages):** https://jbkunama1.github.io/trt.SchulCurri/

> ⚠️ **Status: Entwurf zur Abstimmung.** Stundenzahlen und Inhalte für Kl. 5/6 und Kl. 10 orientieren sich an den Beispielcurricula des Landesinstituts für Schulentwicklung (schule-bw.de). Kl. 7/8 und Kl. 9 sind Vorschläge im Rahmen der Bildungsplan-Regeln. Vor dem Beschluss bitte gegen die Originale in [docs/quellen.md](docs/quellen.md) prüfen.

## 📦 Inhalt

| Pfad | Inhalt |
|------|--------|
| `index.html` | GitHub-Pages-Seite: Präsentation, Jahresplanung je Klasse, abhakbare Checklisten (Browser-Speicher), Druckansicht |
| `curriculum/` | Jahresplanung je Klassenstufe als Markdown (`kl5.md` … `kl10.md`) + `regeln.md` |
| `vorlagen/` | Leere Jahrestabellen zum Ausdrucken/Ausfüllen (Übergabe ans Folgejahr) |
| `docs/quellen.md` | Quellen und Prüfhinweise |

## 📐 Eckdaten

| Klasse | Wochenstd. | Std./Jahr | Kerncurriculum | Schulcurriculum |
|--------|-----------|-----------|----------------|-----------------|
| 5 | 3 | 105 | 78 | 27 |
| 6 | 3 | 105 | 92 | 13 |
| 7/8 | 2 | 70 | 54 | 16 |
| 9 | 2 | 70 | 54 | 16 |
| 10 | 2 | 70 | 54 | 16 |

Struktur: ca. 75 % Kerncurriculum (verbindlich) + 25 % Schulcurriculum (Freiräume).

## 🌐 GitHub Pages aktivieren

`Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main / (root)`

Die Seite ist ein einzelnes statisches `index.html` (kein Build nötig, `.nojekyll` liegt bei).

## 🛠️ Roadmap

- [x] Basics: Inhalte, README, GitHub-Pages-Index
- [ ] Webapp (Flask + SQLite) mit Benutzerverwaltung, Admin, Export
- [ ] Container (Dockerfile / docker-compose für Portainer)
- [ ] CI: Docker-Build per GitHub Actions

Eine frühere Webapp-Variante liegt in [jbkunama1/trt.SportCurri](https://github.com/jbkunama1/trt.SportCurri).

## ⚖️ Hinweis

Inhalte basieren auf dem öffentlichen Bildungsplan 2016 Baden-Württemberg. Für schulische Zwecke frei nutzbar.
