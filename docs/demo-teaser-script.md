# RoboScope Teaser Video — 30 Sekunden

## Meta

- **Laenge**: max. 30 Sekunden
- **Audio**: Epische Instrumental-Musik (kein Voice-Over)
- **Stil**: Schnelle Schnitte, plakative Feature-Overlays, kinetische Typografie
- **Zweck**: Social Media (LinkedIn, Twitter/X, GitHub README)
- **Aufloesung**: 1920x1080, 30fps

## Musik-Empfehlung

- Stil: Cinematischer Build-up, electronic/orchestral hybrid
- Tempo: Langsamer Aufbau (0-10s), Peak (10-25s), Resolve (25-30s)
- Beispiel-Stichworte fuer lizenzfreie Suche: "epic technology trailer", "cinematic corporate"
- Quellen: Artlist, Epidemic Sound, Pixabay Music (kostenlos)

## Overlay-Effekte

### Kinetische Typografie
- Text fliegt Wort fuer Wort ein (0.1s pro Wort)
- Schrift: Bold, 48-72px, weiss auf dunklem Hintergrund
- Glow-Effekt auf Schluesselwoertern (Steel Blue #3B7DD8)

### UI-Showcases
- Schnelle Zoom-Ins auf Features (0.5s pro Schnitt)
- Leichter Ken-Burns-Effekt (langsames Zoom/Pan auf Screenshots)
- Ueberblendung mit Motion Blur zwischen Szenen

### Branding
- RoboScope Logo (Navy #1A2D50) als Wasserzeichen unten-rechts
- Finale Karte: Logo zentriert, GitHub-URL darunter

---

## Zeitablauf

| Zeit | Bild | Overlay-Text | Effekt |
|------|------|-------------|--------|
| 0:00–0:02 | Schwarzer Hintergrund | "What if..." | Fade-in, einzelne Worte |
| 0:02–0:04 | Schwarzer Hintergrund | "...testing was effortless?" | Kinetisch, Wort fuer Wort |
| 0:04–0:06 | Dashboard (Zoom-in auf KPIs) | — | Ken Burns, Musik baut auf |
| 0:06–0:08 | Explorer Code-Editor | "EDIT" | Grosser Text, Slide-in rechts |
| 0:08–0:10 | Visual Editor | "VISUALIZE" | Grosser Text, Slide-in links |
| 0:10–0:12 | Flow Editor (Graph) | "FLOW" | Grosser Text, Scale-up Mitte |
| 0:12–0:14 | Execution-Tabelle (Runs) | "EXECUTE" | Flash-Cut, Musik-Peak |
| 0:14–0:15 | Reports-Detail | "ANALYZE" | Schneller Schnitt |
| 0:15–0:17 | Stats Deep Analysis KPIs | "15 KPIs" | Zahlen zaehlen hoch |
| 0:17–0:19 | Settings AI-Provider | "AI-POWERED" | Glow-Effekt auf "AI" |
| 0:19–0:21 | Settings API-Tokens | "ENTERPRISE-READY" | Bold, Stamp-Effekt |
| 0:21–0:23 | Settings Webhooks | "CI/CD INTEGRATION" | Slide-in unten |
| 0:23–0:25 | Environments Paketliste | "FULL CONTROL" | Scale-up |
| 0:25–0:28 | Schwarzer Hintergrund | "RoboScope" (gross) | Logo Reveal, epischer Drop |
| 0:28–0:30 | Schwarzer Hintergrund | "Open Source / github.com/viadee/roboscope" | Fade-in, Musik endet |

---

## Playwright-Test-Ablauf fuer Teaser

Der Teaser wird aus den gleichen Playwright-Aufnahmen geschnitten. Der Test navigiert schnell durch alle Views und macht pro Szene einen 2-Sekunden-Clip:

1. Dashboard (2s)
2. Explorer > Code Tab (2s)
3. Explorer > Visual Tab (2s)
4. Explorer > Flow Tab (2s)
5. Execution Runs (2s)
6. Report Detail (2s)
7. Stats > Deep Analysis (2s)
8. Settings > AI (2s)
9. Settings > API Tokens (2s)
10. Settings > Webhooks (2s)
11. Environments (2s)
12. Dashboard (Finale, 2s)

Die Text-Overlays und Effekte werden in Post-Production hinzugefuegt (da kinetische Typografie und Motion-Blur nicht per DOM-Injection moeglich sind).

## Post-Production Tools

- **Schnitt**: DaVinci Resolve (kostenlos), Final Cut Pro, oder ffmpeg fuer automatisierte Cuts
- **Titel/Effekte**: DaVinci Resolve Fusion, After Effects, oder Motion
- **Musik-Sync**: Beat-Marker setzen, Schnitte auf Beats ausrichten
