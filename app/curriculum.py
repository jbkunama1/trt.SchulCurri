# Curriculum-Daten Sport, Realschule BW (BP 2016): einzige Datenquelle der Webapp.
# source 'Beispielcurriculum' = an schule-bw.de orientiert (vor Beschluss gegen die PDFs pruefen),
# source 'Vorschlag' = eigener Vorschlag der Fachschaft.
STAGES = [
    {'key': '5', 'label': 'Klasse 5', 'emoji': '🎒', 'hours': 105, 'kc': 78, 'sc': 27, 'source': 'Beispielcurriculum'},
    {'key': '6', 'label': 'Klasse 6', 'emoji': '🧢', 'hours': 105, 'kc': 92, 'sc': 13, 'source': 'Beispielcurriculum'},
    {'key': '78', 'label': 'Klasse 7/8', 'emoji': '🏐', 'hours': 70, 'kc': 54, 'sc': 16, 'source': 'Vorschlag'},
    {'key': '9', 'label': 'Klasse 9', 'emoji': '🚴', 'hours': 70, 'kc': 54, 'sc': 16, 'source': 'Vorschlag'},
    {'key': '10', 'label': 'Klasse 10', 'emoji': '🏸', 'hours': 70, 'kc': 54, 'sc': 16, 'source': 'Beispielcurriculum'},
]
STAGE_KEYS = [s['key'] for s in STAGES]

CURRICULUM = {
    '5': [
        ('UV 1', '🎮 Spielen', 'Spielfähigkeit entwickeln, Regeln selbst festlegen und überwachen, Fairplay', 18),
        ('UV 2', '🏃 Laufen, Springen, Werfen', 'Kondition und Spiel grundlegend entwickeln', 12),
        ('UV 3', '🤸 Bewegen an Geräten', 'Bewegungssicherheit und -vielfalt erwerben', 15),
        ('UV 4', '💃 Tanzen, Gestalten, Darstellen', 'Rhythmisch bewegen (nur Kl. 5 oder 6)', 12),
        ('UV 5', '💪 Fitness entwickeln', 'Grundlagen der Trainingsprinzipien', 12),
        ('WP 1', '🥋 Kämpfen (Wahlpflicht)', 'Ringen und Raufen vorwiegend am Boden', 9),
        ('SC', '🌟 Schulcurriculum', 'Schulturniere, Trendsport, Ergänzungen', 27),
    ],
    '6': [
        ('UV 1', '🎮 Spielen', 'Spielfähigkeit vertiefen, verbindliches Regelhandeln', 24),
        ('UV 2', '🏃 Laufen, Springen, Werfen', 'Anlauftechniken, Sprung, Wurf', 18),
        ('UV 3', '🤸 Bewegen an Geräten', 'Bewegungssicherheit und -vielfalt vertiefen', 18),
        ('UV 4', '🏊 Bewegen im Wasser', 'Grundlagen, Schwimmtechniken (nur Kl. 5 oder 6)', 16),
        ('UV 5', '💪 Fitness entwickeln', 'Ebenen der Belastungssteuerung', 8),
        ('WP 1', '🥋 Kämpfen (Wahlpflicht)', 'Ringen und Raufen vorwiegend im Stand', 8),
        ('SC', '🌟 Schulcurriculum', 'Schulspezifische Akzente', 13),
    ],
    '78': [
        ('UV 1', '🏐 Spielen vertieft', 'z. B. Badminton / Volleyball / Fußball', 18),
        ('UV 2', '💪 Fitness entwickeln', 'Ausdauer, Kraft, Herzfrequenz, Trainingsprinzipien', 18),
        ('UV 3', '🕺 Tanzen, Gestalten, Darstellen', 'Choreografie, Videoanalyse, Präsentation', 18),
        ('SC', '🌟 Schulcurriculum', 'Projekttag, Klettern, JtfO, Turniere', 16),
    ],
    '9': [
        ('UV 1', '🏀 Komplexes Sportspiel', 'Taktik, Positionsspiel, Schiedsrichterrolle', 18),
        ('UV 2', '🚴 Fahren, Rollen, Gleiten (Wahlpflicht)', 'Fahrrad/Inlines, Regeln, Umweltverträglichkeit', 16),
        ('UV 3', '🕹️ Spielen alternativ', 'Fan-/Trendspiele, Schulhofsport beleben', 12),
        ('UV 4', '🤸 Gestalten / Fitness', 'Bewegungen neu zusammensetzen', 8),
        ('SC', '🌟 Schulcurriculum', 'Kooperation Vereine, Schnupperangebote', 16),
    ],
    '10': [
        ('UV 1', '🏸 Badminton', 'Rückschlagspiel, Wettkampf, Turnierorganisation', 18),
        ('UV 2', '🧭 Orientierungslauf', 'Karte, Kompass, Gelände', 18),
        ('UV 3', '🏋️ Fitness entwickeln', 'Individuelles Fitnessprogramm, Punch & Kick', 18),
        ('SC', '🌟 Schulcurriculum', 'Zusatzangebote, Training mit Trainingsplan', 16),
    ],
}

EVALUATIONS = {
    '5': [('Technik', 'Beobachtungsbogen Ballspiele'), ('Leichtathletik', 'Zeiten und Weiten'),
          ('Turnen', 'Geräte-Checkliste'), ('Sozialverhalten', 'Fairplay-Bogen'), ('Fitness', 'Basis-Tests')],
    '6': [('Spielen', 'Technik- und Regelcheck'), ('Schwimmen', 'Schwimmabzeichen-Stand'),
          ('Turnen', 'Sicherungsaufgaben und Gerätekür'), ('Sozialverhalten', 'Verbindliches Regelhandeln'),
          ('Fitness', 'Belastungssteuerung (Puls)')],
    '78': [('Sportspiel', 'Technik-Check'), ('Fitness', 'HF-Messung, Zirkelprotokoll'),
           ('Tanzen', 'Choreografie-Präsentation'), ('Reflexion', 'Trainingsprotokoll, Selbstbewertung'),
           ('Sozialverhalten', 'Fairplay und Teambewertung')],
    '9': [('Sportspiel', 'Taktikverständnis, Schiedsrichterleistung'), ('Fahren/Rollen/Gleiten', 'Tourenplanung, Regelwissen'),
          ('Gestalten', 'Kür nach ästhetischen Kriterien'), ('Fitness', 'Trainingsplan-Umsetzung'),
          ('Reflexion', 'Trainings-/Ernährungsprotokoll')],
    '10': [('Badminton', 'Spielauswertung, Turnierleitung'), ('Orientierungslauf', 'Kartenarbeit, Laufzeit'),
           ('Fitness', 'Individuelles Programm und Umsetzung'), ('Sozialverhalten', 'Organisation, Teamfähigkeit'),
           ('Reflexion', 'Selbsteinschätzung, Zielüberprüfung')],
}

REFLECTION_QUESTIONS = [
    ('gut', 'Was lief gut?'),
    ('schwer', 'Was war zu schwer / zu leicht?'),
    ('aendern', 'Welche UV ändern wir nächstes Jahr?'),
    ('tipps', 'Tipps für die Kollegin / den Kollegen:'),
]
