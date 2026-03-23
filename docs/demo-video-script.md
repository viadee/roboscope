# RoboScope Demo Video — Skript, Voice-Over & Overlay-Spezifikation

## Meta

- **Zielgruppe**: QA-Leads, Testmanager, Entwickler, die Robot Framework einsetzen oder evaluieren
- **Laenge**: ca. 4:45 Minuten
- **Ton**: Professionell, aber zugaenglich. Kein Marketing-Sprech, sondern "Kollege zeigt Kollegen ein Tool"
- **Sprache**: Deutsch (mit englischen Fachbegriffen wo ueblich)
- **Format**: Screencast mit Voice-Over + Overlay-Textboxen
- **Aufloesung**: 1920x1080, 30fps
- **TTS-Script**: Siehe `docs/demo-tts-script.txt` (separierte Datei fuer TTS-Engine)
- **Teaser**: Siehe `docs/demo-teaser-script.md` (30s Teaser-Konzept)

## Overlay-Design-System

### Szenen-Titel-Box (Scene Title)
- **Position**: Oben-Mitte, 80px vom oberen Rand
- **Stil**: Halbtransparenter Navy-Hintergrund (#1A2D50 / 90% Opazitaet), abgerundete Ecken (12px)
- **Schrift**: 28px, bold, weiss (#FFFFFF)
- **Animation**: Fade-in (0.5s), verbleibt 4s, Fade-out (0.5s)
- **Padding**: 16px 32px

### Feature-Highlight-Box (Feature Tag)
- **Position**: Unten-Links, 40px vom unteren Rand, 40px vom linken Rand
- **Stil**: Steel Blue Hintergrund (#3B7DD8), abgerundete Ecken (8px)
- **Schrift**: 18px, semibold, weiss
- **Animation**: Slide-in von links (0.3s), verbleibt 3s, Slide-out nach links (0.3s)
- **Padding**: 10px 20px

### Info-Callout (Callout)
- **Position**: Kontextabhaengig — neben dem relevanten UI-Element
- **Stil**: Weisser Hintergrund, 2px Amber-Border (#D4883E), Schatten
- **Schrift**: 16px, regular, dunkelgrau (#1A1D2E)
- **Pfeil**: Zeigt auf das referenzierte UI-Element
- **Animation**: Scale-in (0.3s), verbleibt 2.5s, Fade-out (0.3s)

---

## Szene 1 — Intro & Problem (0:00–0:25)

**Dauer**: 25 Sekunden

**Bildschirm**: Login-Seite von RoboScope (statisch, kein Chaos-Schnitt noetig — die App spricht fuer sich)

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 0:00 | "RoboScope" | Scene Title | Mitte |
| 0:02 | "Test Management for Robot Framework" | Feature Tag | Unten-Mitte |
| 0:08 | "Open Source  /  Self-Hosted  /  Offline-Faehig" | Feature Tag | Unten-Mitte |

**Voice-Over** (TTS-Abschnitt 1):
> Robot Framework ist grossartig fuer Testautomatisierung — aber das Drumherum ist es oft nicht. Git-Repos klonen, Environments aufsetzen, Tests starten, Reports finden, Ergebnisse vergleichen — alles manuelle Schritte, die Zeit kosten und fehleranfaellig sind. RoboScope bringt das alles unter ein Dach. Open Source, Self-Hosted, und in unter einer Minute startbar.

**Aktionen im Playwright-Test**:
1. Navigiere zu `/login`
2. Warte 2s (Overlay einblenden)
3. Zeige Login-Form
4. Warte bis Overlay-Texte angezeigt wurden (insgesamt ~10s)

---

## Szene 2 — Login & Dashboard (0:25–0:45)

**Dauer**: 20 Sekunden

**Bildschirm**: Login durchfuehren, dann Dashboard mit KPIs

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 0:25 | "Dashboard — Alles auf einen Blick" | Scene Title | Oben-Mitte |
| 0:30 | "KPI-Cards: Tests, Erfolgsquote, Trends" | Callout | Neben KPI-Cards |
| 0:37 | "4 Rollen: Viewer < Runner < Editor < Admin" | Feature Tag | Unten-Links |

**Voice-Over** (TTS-Abschnitt 2):
> Nach dem Start begruesst uns das Dashboard. Hier sehen wir auf einen Blick: Wie viele Tests laufen, wie die Erfolgsquote aussieht, und ob es Trends gibt, die Aufmerksamkeit brauchen. RoboScope hat ein Rollensystem — vom Viewer, der nur liest, bis zum Admin, der alles konfiguriert.

**Aktionen im Playwright-Test**:
1. Fuehre Login via API durch (Token-Injection)
2. Navigiere zu `/dashboard`
3. Warte auf KPI-Cards geladen
4. Langsam ueber KPI-Cards hovern (Maus-Highlight)
5. Scroll leicht nach unten zu "Letzte Ausfuehrungen"

---

## Szene 3 — Projekte & Git-Integration (0:45–1:15)

**Dauer**: 30 Sekunden

**Bildschirm**: Repos/Projekte-View, Projektkarten mit Git-Info

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 0:45 | "Git-Integration — Projekte aus Repositories" | Scene Title | Oben-Mitte |
| 0:52 | "Branch-Switching direkt in der UI" | Callout | Neben Branch-Dropdown |
| 1:00 | "Environment-Zuordnung pro Projekt" | Callout | Neben Environment-Dropdown |

**Voice-Over** (TTS-Abschnitt 3):
> Projekte werden direkt aus Git-Repositories angelegt. URL eingeben, Branch waehlen — fertig. RoboScope klont das Repo und haelt es synchron. Jedes Projekt kann einer Umgebung zugeordnet werden. Branches lassen sich direkt in der UI wechseln.

**Aktionen im Playwright-Test**:
1. Navigiere zu `/repos`
2. Warte auf Projektkarten
3. Hover ueber ein Projekt (zeige Details)
4. Klicke auf Branch-Dropdown (oeffne, nicht wechseln)
5. Klicke auf Environment-Dropdown (oeffne, nicht wechseln)
6. Klicke auf "Explorer" Link einer Projektkarte

---

## Szene 4 — Explorer & Editoren (1:15–2:00)

**Dauer**: 45 Sekunden (laengste Szene — 3 Editoren zu zeigen)

**Bildschirm**: Explorer mit Dateibaum, dann Code/Visual/Flow Editor Tabs

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 1:15 | "3 Editoren — Code, Visual, Flow" | Scene Title | Oben-Mitte |
| 1:22 | "Dateibaum mit Testanzahl pro Ordner" | Callout | Neben Dateibaum |
| 1:30 | "Visual Editor: Strukturierte Bearbeitung" | Feature Tag | Unten-Links |
| 1:40 | "Flow Editor: Grafischer Testablauf" | Feature Tag | Unten-Links |
| 1:48 | "Keyword-Palette: Drag & Drop" | Callout | Neben Palette |

**Voice-Over** (TTS-Abschnitt 4):
> Im Explorer sehen wir die komplette Projektstruktur. Robot-Dateien lassen sich direkt bearbeiten — entweder als Code, oder im Visual Editor, der Settings, Variablen und Testfaelle strukturiert darstellt. Und dann gibt es den Flow-Editor: Testfaelle werden als grafischer Ablauf dargestellt. Keyword-Nodes, Kontrollstrukturen wie IF und FOR — alles visuell. Neue Keywords lassen sich per Drag and Drop aus der Palette hinzufuegen. Alle drei Ansichten sind synchron.

**Aktionen im Playwright-Test**:
1. Oeffne eine `.robot`-Datei im Dateibaum
2. Zeige Code-Editor (3s)
3. Klicke auf "Visual Editor" Tab (3s, scrolle durch Sections)
4. Klicke auf "Flow" Tab (zeige Graph, 5s)
5. Oeffne Keyword-Palette (Klick auf Palette-Toggle)
6. Warte 3s (Palette sichtbar)

---

## Szene 5 — Testausfuehrung (2:00–2:35)

**Dauer**: 35 Sekunden

**Bildschirm**: Explorer "Run" Button, dann Execution-View mit laufendem Test

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 2:00 | "Live-Ausfuehrung mit WebSocket" | Scene Title | Oben-Mitte |
| 2:08 | "Ein-Klick-Start aus dem Explorer" | Callout | Neben Run-Button |
| 2:18 | "Status-Badges: passed / failed / running" | Callout | Neben Status-Spalte |
| 2:25 | "Docker + lokale Ausfuehrung" | Feature Tag | Unten-Links |

**Voice-Over** (TTS-Abschnitt 5):
> Tests starten mit einem Klick. Der Output wird live per WebSocket gestreamt — kein Polling, kein Warten. RoboScope unterstuetzt sowohl lokale Ausfuehrung als auch Docker-Container. Die Ausfuehrungstabelle zeigt alle Runs mit Status, Dauer und Umgebung. Laufende Tests lassen sich jederzeit abbrechen.

**Aktionen im Playwright-Test**:
1. Navigiere zu `/runs`
2. Zeige Ausfuehrungstabelle (3s)
3. Warte auf vorhandene Runs (zeige Status-Badges)
4. Scrolle durch die Tabelle

---

## Szene 6 — Environments & Package Manager (2:35–3:05)

**Dauer**: 30 Sekunden

**Bildschirm**: Environments-View mit Paketliste und Library-Check

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 2:35 | "Package Manager — Environments im Griff" | Scene Title | Oben-Mitte |
| 2:42 | "Installierte Pakete auf einen Blick" | Callout | Neben Paketliste |
| 2:52 | "Library-Check: Fehlende Pakete erkennen" | Feature Tag | Unten-Links |

**Voice-Over** (TTS-Abschnitt 6):
> Umgebungen werden vollstaendig in RoboScope verwaltet. Virtuelle Environments erstellen, Pakete installieren, Variablen setzen — alles ueber die UI. Besonders praktisch: der Library-Check. Er scannt die Robot-Dateien nach importierten Libraries und zeigt sofort, welche Pakete fehlen — mit One-Click-Installation.

**Aktionen im Playwright-Test**:
1. Navigiere zu `/environments`
2. Klicke auf eine Umgebung (Detail-Ansicht)
3. Zeige Paketliste (3s)
4. Scrolle zu Variablen-Section (2s)

---

## Szene 7 — Reports & Analyse (3:05–3:40)

**Dauer**: 35 Sekunden

**Bildschirm**: Reports-Liste, Report-Detail, Stats Deep Analysis

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 3:05 | "Reports & Tiefenanalyse" | Scene Title | Oben-Mitte |
| 3:12 | "Automatisches Parsing von output.xml" | Callout | Neben Report-Liste |
| 3:22 | "15 KPIs in 5 Kategorien" | Feature Tag | Unten-Links |
| 3:30 | "Keyword Analytics / Test Quality / Maintenance" | Feature Tag | Unten-Links |

**Voice-Over** (TTS-Abschnitt 7):
> Nach jedem Testlauf wird der Report automatisch geparst und gespeichert. Die Detail-Ansicht zeigt Ergebnisse, Dauer und Fehler — und den originalen HTML-Report. Fuer tiefere Einblicke gibt es die Tiefenanalyse: 15 KPIs in fuenf Kategorien — von Keyword-Haeufigkeit ueber Flaky-Detection bis zur Test-Komplexitaet.

**Aktionen im Playwright-Test**:
1. Navigiere zu `/reports` (eigentlich keine direkte Route — Reports sind in /runs verlinkt)
2. Navigiere zu `/stats`
3. Zeige Overview-Tab (3s)
4. Klicke auf "Deep Analysis" Tab
5. Zeige KPI-Ergebnisse (5s, scrollen)

---

## Szene 8 — KI-Features (3:40–4:05)

**Dauer**: 25 Sekunden

**Bildschirm**: Settings > AI Provider Tab

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 3:40 | "KI-gestuetzte Fehleranalyse" | Scene Title | Oben-Mitte |
| 3:47 | "4 Provider: OpenAI, Anthropic, Ollama, OpenRouter" | Feature Tag | Unten-Links |
| 3:55 | ".roboscope YAML -> .robot Generierung" | Feature Tag | Unten-Links |

**Voice-Over** (TTS-Abschnitt 8):
> RoboScope kann optional mit einem LLM verbunden werden — OpenAI, Anthropic, Ollama oder OpenRouter. Damit lassen sich fehlgeschlagene Tests automatisch analysieren: Root-Cause, Muster-Erkennung und konkrete Fix-Vorschlaege. Und fuer Teams, die Tests aus Spezifikationen generieren wollen, gibt es das roboscope-Format: Eine YAML-Beschreibung, aus der per KI vollstaendige Robot-Framework-Tests entstehen.

**Aktionen im Playwright-Test**:
1. Navigiere zu `/settings`
2. Klicke auf AI-Tab
3. Zeige Provider-Konfiguration (5s)

---

## Szene 9 — Enterprise-Features (4:05–4:25)

**Dauer**: 20 Sekunden

**Bildschirm**: Settings > API Tokens, Webhooks, dann Audit-Log

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 4:05 | "Enterprise-Ready" | Scene Title | Oben-Mitte |
| 4:08 | "API-Tokens fuer CI/CD" | Feature Tag | Unten-Links |
| 4:13 | "Webhooks + Audit-Log" | Feature Tag | Unten-Links |
| 4:18 | "Git-Push -> automatischer Testlauf" | Feature Tag | Unten-Links |

**Voice-Over** (TTS-Abschnitt 9):
> Fuer den Unternehmenseinsatz bietet RoboScope API-Tokens fuer CI/CD-Integration, Webhooks fuer Benachrichtigungen bei Testlauf-Ereignissen, ein vollstaendiges Audit-Log, und Scheduling fuer wiederkehrende Testlaeufe. Git-Webhooks ermoeglichen automatische Testausfuehrung bei jedem Push — direkt aus GitHub oder GitLab.

**Aktionen im Playwright-Test**:
1. Klicke auf "API Tokens" Tab (3s)
2. Klicke auf "Webhooks" Tab (3s)
3. Klicke auf "Audit Log" Tab (3s)

---

## Szene 10 — Outro (4:25–4:45)

**Dauer**: 20 Sekunden

**Bildschirm**: Zurueck zum Dashboard, dann Schluss-Overlay

| Zeitpunkt | Overlay | Typ | Position |
|-----------|---------|-----|----------|
| 4:25 | "Open Source — Self-Hosted — Offline-Faehig" | Scene Title | Mitte |
| 4:32 | "github.com/viadee/roboscope" | Feature Tag | Mitte (gross) |
| 4:38 | "Probiert es aus!" | Feature Tag | Mitte |

**Voice-Over** (TTS-Abschnitt 10):
> RoboScope ist Open Source und laeuft ueberall — lokal, im Docker, oder auf dem eigenen Server. Kein Cloud-Zwang, keine versteckten Kosten. Alle Details, die Installationsanleitung und den Quellcode findet ihr auf GitHub unter viadee slash roboscope. Probiert es aus — wir freuen uns auf euer Feedback.

**Aktionen im Playwright-Test**:
1. Navigiere zurueck zu `/dashboard`
2. Zeige Schluss-Overlays
3. Warte 5s (Abspann)

---

## Aufnahme-Hinweise

### Vorbereitung der Demo-Instanz
- Frische Instanz mit Examples-Projekt + seeded Demo-Daten
- Mindestens 3–4 vergangene Runs mit gemischten Ergebnissen (passed/failed)
- Eine Umgebung mit installierten Paketen (robotframework, Browser)
- Einen AI-Provider konfiguriert (fuer Szene 8)
- Ein Audit-Log mit Eintraegen (automatisch durch Seed-Aktionen)

### Screencast-Einstellungen
- Aufloesung: 1920x1080
- Playwright recordVideo: { size: { width: 1920, height: 1080 } }
- Sidebar ausgeklappt (Standard)
- Sprache: Englisch (localStorage lang=en)

### Overlay-Injection via Playwright
- Overlays werden per `page.evaluate()` als DOM-Elemente injiziert
- CSS-Animationen (fade-in/out, slide) via injiziertem Stylesheet
- Jedes Overlay hat eine feste Anzeigedauer, danach wird es entfernt
- Die Overlay-Logik ist im Playwright-Test als `showOverlay()` Helper gekapselt

### Post-Production
- TTS-Audio aus `demo-tts-script.txt` generieren (z.B. ElevenLabs, Azure TTS, macOS `say`)
- Video + Audio in Schnittprogramm zusammenfuehren
- Optional: Zoom-Ins auf kleine UI-Details
- Szenenuebergaenge: Einfache Ueberblendung (0.3s cross-dissolve)
- Untertitel empfohlen (fuer LinkedIn/Social Media ohne Ton)
