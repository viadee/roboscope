import type { DocsContent } from '../types'

const de: DocsContent = [
  {
    id: 'getting-started',
    title: 'Erste Schritte',
    icon: '\u{1F680}',
    subsections: [
      {
        id: 'getting-started-overview',
        title: 'Was ist mateoX?',
        content: `
<p>
  <strong>mateoX</strong> ist ein webbasiertes Test-Management-Tool f\u00FCr
  <em>Robot Framework</em>. Es erm\u00F6glicht Teams, ihre automatisierten Tests
  zentral zu verwalten, auszuf\u00FChren und auszuwerten \u2014 ohne Kommandozeile,
  direkt im Browser.
</p>
<h4>Kernfunktionen im \u00DCberblick</h4>
<ul>
  <li><strong>Git-Integration</strong> \u2014 Repositories klonen, synchronisieren und durchsuchen</li>
  <li><strong>Integrierter Editor</strong> \u2014 Robot-Dateien direkt im Browser bearbeiten</li>
  <li><strong>Testausf\u00FChrung</strong> \u2014 Runs starten, \u00FCberwachen und abbrechen</li>
  <li><strong>Report-Analyse</strong> \u2014 Ergebnisse mit Pass/Fail-Statistiken und HTML-Reports</li>
  <li><strong>Umgebungsverwaltung</strong> \u2014 Python-Environments und Pakete verwalten</li>
  <li><strong>Rollenbasierte Zugriffskontrolle</strong> \u2014 Vier Rollen mit abgestuften Berechtigungen</li>
</ul>`,
        tip: 'mateoX eignet sich besonders f\u00FCr Teams, die Robot Framework einsetzen und eine zentrale Oberfl\u00E4che f\u00FCr Testverwaltung und -ausf\u00FChrung ben\u00F6tigen.'
      },
      {
        id: 'getting-started-login',
        title: 'Anmeldung',
        content: `
<p>
  Nach dem Start der Anwendung gelangen Sie zur Login-Seite. Beim ersten Start
  wird automatisch ein Administrator-Konto angelegt:
</p>
<table>
  <thead>
    <tr><th>Feld</th><th>Wert</th></tr>
  </thead>
  <tbody>
    <tr><td>E-Mail</td><td><code>admin@mateox.local</code></td></tr>
    <tr><td>Passwort</td><td><code>admin123</code></td></tr>
  </tbody>
</table>
<p>
  Geben Sie die Zugangsdaten ein und klicken Sie auf <strong>Anmelden</strong>.
  Nach erfolgreicher Authentifizierung werden Sie zum Dashboard weitergeleitet.
</p>
<p>
  <strong>Wichtig:</strong> \u00C4ndern Sie das Standard-Passwort umgehend nach der
  ersten Anmeldung \u00FCber die Einstellungen.
</p>`,
        tip: 'Die Sitzung bleibt \u00FCber ein JWT-Token aktiv. Bei Inaktivit\u00E4t werden Sie automatisch abgemeldet und zur Login-Seite weitergeleitet.'
      },
      {
        id: 'getting-started-layout',
        title: 'Aufbau der Oberfl\u00E4che',
        content: `
<p>
  Die mateoX-Oberfl\u00E4che besteht aus drei Hauptbereichen:
</p>
<ol>
  <li>
    <strong>Sidebar (links)</strong> \u2014 Die Navigation zu allen Bereichen der Anwendung.
    Sie kann \u00FCber den Hamburger-Button ein- und ausgeklappt werden
    (Breite: 250\u202Fpx ausgeklappt, 60\u202Fpx eingeklappt).
  </li>
  <li>
    <strong>Header (oben)</strong> \u2014 Zeigt den aktuellen Bereich, den angemeldeten
    Benutzer und bietet Zugriff auf Schnellaktionen wie Abmelden.
  </li>
  <li>
    <strong>Inhaltsbereich (Mitte)</strong> \u2014 Der Hauptarbeitsbereich, in dem
    Repositories, Tests, Reports und alle weiteren Inhalte dargestellt werden.
  </li>
</ol>
<p>
  Das Design orientiert sich am <em>mateo-automation.com</em>-Branding mit den
  Hauptfarben Teal (<code>#3CB5A1</code>) und Gold (<code>#DFAA40</code>)
  auf dunklem Navy-Hintergrund in der Sidebar.
</p>`
      },
      {
        id: 'getting-started-roles',
        title: 'Rollen & Berechtigungen',
        content: `
<p>
  mateoX verwendet ein hierarchisches Rollenmodell. Jede h\u00F6here Rolle erbt
  s\u00E4mtliche Berechtigungen der darunterliegenden Stufen.
</p>
<table>
  <thead>
    <tr>
      <th>Rolle</th>
      <th>Stufe</th>
      <th>Berechtigungen</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Viewer</strong></td>
      <td>0</td>
      <td>Dashboard, Reports und Statistiken einsehen</td>
    </tr>
    <tr>
      <td><strong>Runner</strong></td>
      <td>1</td>
      <td>Zus\u00E4tzlich: Tests ausf\u00FChren, Runs abbrechen</td>
    </tr>
    <tr>
      <td><strong>Editor</strong></td>
      <td>2</td>
      <td>Zus\u00E4tzlich: Repositories verwalten, Dateien bearbeiten, Umgebungen konfigurieren</td>
    </tr>
    <tr>
      <td><strong>Admin</strong></td>
      <td>3</td>
      <td>Zus\u00E4tzlich: Benutzerverwaltung, App-Einstellungen, alle Reports l\u00F6schen</td>
    </tr>
  </tbody>
</table>
<p>
  Die Rollenzuweisung erfolgt durch einen Administrator unter
  <strong>Einstellungen \u2192 Benutzerverwaltung</strong>.
</p>`,
        tip: 'Die Hierarchie lautet: Viewer < Runner < Editor < Admin. Ein Admin kann alles, was ein Editor kann, und mehr.'
      }
    ]
  },
  {
    id: 'dashboard',
    title: 'Dashboard',
    icon: '\u{1F4CA}',
    subsections: [
      {
        id: 'dashboard-overview',
        title: '\u00DCbersicht',
        content: `
<p>
  Das Dashboard ist die Startseite nach der Anmeldung und bietet einen
  kompakten \u00DCberblick \u00FCber den aktuellen Stand Ihrer Testautomatisierung.
  Alle Kennzahlen werden beim Laden der Seite in Echtzeit berechnet.
</p>
<p>
  Die Seite gliedert sich in drei Abschnitte: <strong>KPI-Karten</strong>,
  <strong>Letzte Ausf\u00FChrungen</strong> und <strong>Repository-\u00DCbersicht</strong>.
</p>`
      },
      {
        id: 'dashboard-kpis',
        title: 'KPI-Karten',
        content: `
<p>
  Am oberen Rand des Dashboards werden vier Kennzahlen als Karten dargestellt:
</p>
<table>
  <thead>
    <tr><th>Karte</th><th>Beschreibung</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Runs (30 Tage)</strong></td>
      <td>Gesamtzahl der Testl\u00E4ufe in den letzten 30 Tagen</td>
    </tr>
    <tr>
      <td><strong>Erfolgsquote</strong></td>
      <td>Anteil der erfolgreichen Runs in Prozent (30-Tage-Zeitraum)</td>
    </tr>
    <tr>
      <td><strong>Durchschn. Laufzeit</strong></td>
      <td>Mittlere Ausf\u00FChrungsdauer aller abgeschlossenen Runs</td>
    </tr>
    <tr>
      <td><strong>Aktive Repos</strong></td>
      <td>Anzahl der eingebundenen Git-Repositories</td>
    </tr>
  </tbody>
</table>
<p>
  Die Karten sind farblich codiert und zeigen bei \u00C4nderungen gegen\u00FCber dem
  vorherigen Zeitraum einen Trend-Indikator an.
</p>`
      },
      {
        id: 'dashboard-recent-runs',
        title: 'Letzte Ausf\u00FChrungen',
        content: `
<p>
  Unterhalb der KPI-Karten befindet sich eine Tabelle mit den j\u00FCngsten
  Testl\u00E4ufen. Jede Zeile zeigt:
</p>
<ul>
  <li><strong>Status-Badge</strong> \u2014 Farbige Kennzeichnung (passed, failed, running, pending, error, cancelled, timeout)</li>
  <li><strong>Repository-Name</strong> \u2014 Welches Repository ausgef\u00FChrt wurde</li>
  <li><strong>Zielpfad</strong> \u2014 Die ausgef\u00FChrte Datei oder das Verzeichnis</li>
  <li><strong>Dauer</strong> \u2014 Wie lange der Run gedauert hat</li>
  <li><strong>Zeitstempel</strong> \u2014 Wann der Run gestartet wurde</li>
</ul>
<p>
  Ein Klick auf eine Zeile navigiert direkt zur <strong>Ausf\u00FChrungs-Detailseite</strong>
  des jeweiligen Runs.
</p>`
      },
      {
        id: 'dashboard-repos',
        title: 'Repository-\u00DCbersicht',
        content: `
<p>
  Die Repository-\u00DCbersicht zeigt alle eingebundenen Repositories als kompakte
  Karten. Jede Karte enth\u00E4lt:
</p>
<ul>
  <li>Den Repository-Namen und die URL</li>
  <li>Den aktiven Branch</li>
  <li>Den Zeitpunkt der letzten Synchronisation</li>
  <li>Einen Schnellzugriff zum \u00D6ffnen im Explorer</li>
</ul>
<p>
  Von hier aus k\u00F6nnen Sie mit einem Klick direkt in den
  <strong>Explorer</strong> eines Repositories wechseln.
</p>`,
        tip: 'Wenn noch keine Repositories angelegt sind, wird stattdessen eine Anleitung zum Hinzuf\u00FCgen angezeigt.'
      }
    ]
  },
  {
    id: 'repositories',
    title: 'Repositories',
    icon: '\u{1F4C1}',
    subsections: [
      {
        id: 'repositories-overview',
        title: '\u00DCbersicht',
        content: `
<p>
  Unter <strong>Repositories</strong> verwalten Sie die Git-Quellen Ihrer
  Robot-Framework-Tests. mateoX klont Repositories lokal und h\u00E4lt sie
  synchron, damit Tests stets gegen den aktuellen Stand ausgef\u00FChrt werden.
</p>
<p>
  Die Repository-Seite zeigt eine Liste aller hinzugef\u00FCgten Repositories mit
  Name, URL, Branch, Sync-Status und Aktionen.
</p>`
      },
      {
        id: 'repositories-add-git',
        title: 'Git-Repository hinzuf\u00FCgen',
        content: `
<p>
  Klicken Sie auf <strong>Repository hinzuf\u00FCgen</strong>, um ein neues
  Git-Repository einzubinden. Folgende Angaben sind erforderlich:
</p>
<ol>
  <li><strong>Repository-URL</strong> \u2014 Die HTTPS- oder SSH-URL des Git-Repositories (z.\u202FB. <code>https://github.com/org/tests.git</code>)</li>
  <li><strong>Branch</strong> \u2014 Der zu klonende Branch (Standard: <code>main</code>)</li>
  <li><strong>Name</strong> (optional) \u2014 Ein benutzerdefinierter Anzeigename</li>
</ol>
<p>
  Nach dem Klick auf <strong>Speichern</strong> wird das Repository im Hintergrund
  geklont. Der Fortschritt ist \u00FCber den Sync-Status erkennbar.
</p>
<p>
  <strong>Berechtigung:</strong> Zum Hinzuf\u00FCgen ist mindestens die Rolle
  <em>Editor</em> erforderlich.
</p>`,
        tip: 'F\u00FCr private Repositories \u00FCber SSH stellen Sie sicher, dass der SSH-Schl\u00FCssel auf dem Server hinterlegt ist.'
      },
      {
        id: 'repositories-sync',
        title: 'Synchronisation & Auto-Sync',
        content: `
<p>
  Repositories k\u00F6nnen jederzeit manuell synchronisiert werden, um den
  neuesten Stand vom Remote zu holen:
</p>
<ul>
  <li><strong>Manueller Sync</strong> \u2014 Klicken Sie auf das Sync-Symbol neben dem Repository. Ein <code>git pull</code> wird ausgef\u00FChrt.</li>
  <li><strong>Auto-Sync</strong> \u2014 Wenn aktiviert, wird das Repository vor jeder Testausf\u00FChrung automatisch synchronisiert.</li>
</ul>
<p>
  Der Sync-Status zeigt den Zeitpunkt der letzten erfolgreichen Synchronisation
  an. Bei Fehlern (z.\u202FB. Merge-Konflikte) wird eine Warnung angezeigt.
</p>`
      },
      {
        id: 'library-check',
        title: 'Library-Check (Paket-Manager)',
        content: `
<p>
  Der <strong>Library-Check</strong> scannt die <code>.robot</code>- und
  <code>.resource</code>-Dateien eines Repositories nach <code>Library</code>-Imports
  und pr\u00FCft, ob die entsprechenden Python-Pakete in einer ausgew\u00E4hlten
  Umgebung installiert sind.
</p>
<h4>Verwendung</h4>
<ol>
  <li>Klicken Sie auf der <strong>Repositories</strong>-Seite auf den <strong>Library-Check</strong>-Button einer Repository-Karte.</li>
  <li>W\u00E4hlen Sie eine <strong>Umgebung</strong> aus dem Dropdown (vorbelegt mit der Standard-Umgebung des Repositories).</li>
  <li>Klicken Sie auf <strong>Scannen</strong>.</li>
</ol>
<h4>Ergebnisse</h4>
<p>Die Scan-Ergebnisse zeigen eine Tabelle mit jeder Library und ihrem Status:</p>
<ul>
  <li><strong>Installiert</strong> (gr\u00FCn) \u2014 Das PyPI-Paket ist in der Umgebung installiert, mit Versionsanzeige.</li>
  <li><strong>Fehlt</strong> (rot) \u2014 Die Library wird in Testdateien verwendet, ist aber nicht installiert. Ein <strong>Installieren</strong>-Button erm\u00F6glicht die Ein-Klick-Installation.</li>
  <li><strong>Built-in</strong> (grau) \u2014 Die Library geh\u00F6rt zur Robot Framework Standardbibliothek (z.B. Collections, String, BuiltIn).</li>
</ul>
<h4>Fehlende Libraries installieren</h4>
<p>
  Klicken Sie auf <strong>Installieren</strong> neben einer fehlenden Library oder nutzen Sie
  <strong>Alle fehlenden installieren</strong> f\u00FCr die Batch-Installation.
</p>
<h4>Standard-Umgebung</h4>
<p>
  Jedem Repository kann eine <strong>Standard-Umgebung</strong> zugewiesen werden.
  Diese wird beim \u00D6ffnen des Library-Check-Dialogs automatisch vorausgew\u00E4hlt.
</p>`,
        tip: 'F\u00FChren Sie nach dem Klonen eines neuen Repositories einen Library-Check durch, um alle ben\u00F6tigten Abh\u00E4ngigkeiten zu identifizieren.'
      },
      {
        id: 'repositories-environment',
        title: 'Projekt-Umgebung',
        content: `
<p>
  Jedem Projekt kann eine <strong>Standard-Umgebung</strong> zugeordnet werden.
  Diese wird automatisch bei Testausf\u00FChrungen und im Library-Check-Dialog
  vorausgew\u00E4hlt.
</p>
<h4>Umgebung ausw\u00E4hlen</h4>
<p>
  Auf der <strong>Projekte</strong>-Seite zeigt jede Projektkarte ein Dropdown zur
  Umgebungsauswahl. W\u00E4hlen Sie eine Umgebung aus der Liste \u2014 die \u00C4nderung
  wird sofort gespeichert.
</p>
<p>
  Wenn eine systemweite Standard-Umgebung konfiguriert ist, wird diese beim
  Hinzuf\u00FCgen neuer Projekte automatisch vorausgew\u00E4hlt.
</p>`,
        tip: 'Weisen Sie jedem Projekt die korrekte Umgebung zu, um Fehler durch fehlende Bibliotheken zu vermeiden.'
      },
      {
        id: 'repositories-bulk',
        title: 'Bulk-Auswahl & L\u00F6schen',
        content: `
<p>
  F\u00FCr die Verwaltung mehrerer Repositories gleichzeitig steht eine
  Bulk-Auswahl zur Verf\u00FCgung:
</p>
<ol>
  <li>Aktivieren Sie die Checkboxen neben den gew\u00FCnschten Repositories</li>
  <li>Nutzen Sie die Sammel-Aktionen in der Toolbar (z.\u202FB. <strong>Alle synchronisieren</strong> oder <strong>Ausgew\u00E4hlte l\u00F6schen</strong>)</li>
</ol>
<p>
  Beim L\u00F6schen wird sowohl der Datenbankeintrag als auch das lokale
  Verzeichnis entfernt. <strong>Dieser Vorgang kann nicht r\u00FCckg\u00E4ngig gemacht
  werden.</strong>
</p>`,
        tip: 'Gel\u00F6schte Repositories k\u00F6nnen jederzeit erneut hinzugef\u00FCgt werden \u2014 sie werden dann frisch geklont.'
      }
    ]
  },
  {
    id: 'explorer',
    title: 'Explorer',
    icon: '\u{1F50D}',
    subsections: [
      {
        id: 'explorer-overview',
        title: 'Dateibaum-Navigation',
        content: `
<p>
  Der <strong>Explorer</strong> bietet einen Dateimanager f\u00FCr Ihre
  Repository-Inhalte. Links wird der Dateibaum als aufklappbare
  Verzeichnisstruktur dargestellt, rechts der Inhalt der ausgew\u00E4hlten Datei.
</p>
<ul>
  <li>W\u00E4hlen Sie zun\u00E4chst ein Repository aus der Dropdown-Liste oben</li>
  <li>Klicken Sie auf Ordner, um sie auf- oder zuzuklappen</li>
  <li>Klicken Sie auf eine Datei, um sie im Editor-Bereich zu \u00F6ffnen</li>
  <li>Im Kopfbereich des Dateibaums wird die <strong>Gesamtanzahl der Testf\u00E4lle</strong> \u00FCber alle <code>.robot</code>-Dateien angezeigt. Verzeichnisse zeigen zudem ein Badge mit ihrer individuellen Testanzahl.</li>
</ul>
<p>
  <code>.robot</code>-Dateien werden durch ein spezielles Symbol hervorgehoben
  und bieten zus\u00E4tzliche Funktionen wie das direkte Ausf\u00FChren einzelner Tests.
</p>
<h4>Localhost-Funktionen</h4>
<p>
  Wenn Sie mateoX \u00FCber <code>localhost</code> aufrufen, stehen zus\u00E4tzliche Funktionen zur Verf\u00FCgung:
</p>
<ul>
  <li><strong>Projektordner \u00F6ffnen</strong> &mdash; Ein Ordner-Button im Kopfbereich des Dateibaums \u00F6ffnet das Projektverzeichnis im System-Dateibrowser (Finder, Windows Explorer oder Nautilus).</li>
  <li><strong>Im Dateibrowser \u00F6ffnen</strong> &mdash; Jedes Verzeichnis im Baum hat einen Ordner-Button, um es direkt im Dateibrowser zu \u00F6ffnen.</li>
  <li><strong>Absoluter Pfad</strong> &mdash; Bei ausgew\u00E4hlten Dateien wird der vollst\u00E4ndige Dateisystempfad unterhalb der Breadcrumb-Navigation angezeigt.</li>
</ul>`
      },
      {
        id: 'explorer-file-operations',
        title: 'Dateien erstellen, umbenennen & l\u00F6schen',
        content: `
<p>
  \u00DCber das Kontextmen\u00FC (Rechtsklick) oder die Toolbar-Buttons k\u00F6nnen Sie
  Dateien und Ordner verwalten:
</p>
<table>
  <thead>
    <tr><th>Aktion</th><th>Beschreibung</th><th>Rolle</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Neue Datei</strong></td>
      <td>Erstellt eine neue Datei im aktuellen Verzeichnis</td>
      <td>Editor+</td>
    </tr>
    <tr>
      <td><strong>Neuer Ordner</strong></td>
      <td>Erstellt ein neues Unterverzeichnis</td>
      <td>Editor+</td>
    </tr>
    <tr>
      <td><strong>Umbenennen</strong></td>
      <td>Benennt die ausgew\u00E4hlte Datei oder den Ordner um</td>
      <td>Editor+</td>
    </tr>
    <tr>
      <td><strong>L\u00F6schen</strong></td>
      <td>Entfernt die Datei oder den Ordner (mit Best\u00E4tigung)</td>
      <td>Editor+</td>
    </tr>
  </tbody>
</table>
<p>
  \u00C4nderungen werden direkt im lokalen Repository-Verzeichnis auf dem Server
  gespeichert. Beachten Sie, dass diese \u00C4nderungen <em>nicht</em> automatisch
  in das Remote-Repository zur\u00FCckgeschrieben werden.
</p>`
      },
      {
        id: 'explorer-editor',
        title: 'CodeMirror-Editor',
        content: `
<p>
  Beim \u00D6ffnen einer Datei wird rechts ein vollwertiger Code-Editor
  (basierend auf <em>CodeMirror</em>) angezeigt. Er bietet:
</p>
<ul>
  <li><strong>Syntax-Highlighting</strong> f\u00FCr Robot Framework, Python, YAML, JSON und weitere Formate</li>
  <li><strong>Zeilennummern</strong> f\u00FCr einfache Orientierung</li>
  <li><strong>Automatische Einr\u00FCckung</strong> passend zum Dateityp</li>
  <li><strong>Suchen & Ersetzen</strong> mit Tastenkombination <code>Ctrl+F</code> / <code>Cmd+F</code></li>
</ul>
<p>
  \u00C4nderungen werden \u00FCber den <strong>Speichern</strong>-Button oder mit
  <code>Ctrl+S</code> / <code>Cmd+S</code> persistiert.
</p>`,
        tip: 'Der Editor erkennt .robot-Dateien und hebt Keywords, Variablen und Testf\u00E4lle farblich hervor.'
      },
      {
        id: 'explorer-search',
        title: 'Dateisuche',
        content: `
<p>
  Am oberen Rand des Explorers befindet sich ein Suchfeld, mit dem Sie
  Dateien innerhalb des ausgew\u00E4hlten Repositories suchen k\u00F6nnen.
  Die Suche filtert den Dateibaum in Echtzeit nach dem eingegebenen
  Suchbegriff.
</p>
<p>
  Die Suche durchsucht sowohl Dateinamen als auch Verzeichnisnamen.
  Treffer werden im Dateibaum hervorgehoben.
</p>`
      },
      {
        id: 'explorer-run-tests',
        title: 'Einzelne Tests ausf\u00FChren',
        content: `
<p>
  Bei ge\u00F6ffneten <code>.robot</code>-Dateien k\u00F6nnen Sie einzelne
  Testf\u00E4lle direkt aus dem Explorer heraus starten:
</p>
<ol>
  <li>\u00D6ffnen Sie eine <code>.robot</code>-Datei im Editor</li>
  <li>Die erkannten Testf\u00E4lle werden aufgelistet</li>
  <li>Klicken Sie auf das <strong>Ausf\u00FChren</strong>-Symbol neben einem Testfall</li>
  <li>Der Run wird gestartet und Sie k\u00F6nnen den Fortschritt auf der Ausf\u00FChrungs-Seite verfolgen</li>
</ol>
<p>
  Alternativ k\u00F6nnen Sie die gesamte Datei ausf\u00FChren, indem Sie den
  <strong>Alle ausf\u00FChren</strong>-Button in der Toolbar verwenden.
</p>`,
        tip: 'F\u00FCr die Testausf\u00FChrung ist mindestens die Rolle Runner erforderlich.'
      }
    ]
  },
  {
    id: 'execution',
    title: 'Ausf\u00FChrung',
    icon: '\u25B6\uFE0F',
    subsections: [
      {
        id: 'execution-new-run',
        title: 'Neuen Run starten',
        content: `
<p>
  Um einen neuen Testlauf zu starten, klicken Sie auf
  <strong>Neuer Run</strong> auf der Ausf\u00FChrungs-Seite. Im Dialog
  konfigurieren Sie:
</p>
<table>
  <thead>
    <tr><th>Feld</th><th>Beschreibung</th><th>Pflicht</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Repository</strong></td>
      <td>Das Repository, aus dem Tests ausgef\u00FChrt werden sollen</td>
      <td>Ja</td>
    </tr>
    <tr>
      <td><strong>Zielpfad</strong></td>
      <td>Datei oder Verzeichnis relativ zum Repository-Root (z.\u202FB. <code>tests/login.robot</code>)</td>
      <td>Ja</td>
    </tr>
    <tr>
      <td><strong>Timeout</strong></td>
      <td>Maximale Laufzeit in Sekunden (Standard: 3600)</td>
      <td>Nein</td>
    </tr>
  </tbody>
</table>
<p>
  Nach dem Start wird der Run in die Warteschlange eingereiht. Da mateoX mit
  einem einzelnen Worker arbeitet (<code>max_workers=1</code>), werden Runs
  nacheinander in FIFO-Reihenfolge abgearbeitet.
</p>`,
        tip: 'Wenn Auto-Sync aktiviert ist, wird das Repository vor der Ausf\u00FChrung automatisch auf den neuesten Stand gebracht.'
      },
      {
        id: 'execution-status-table',
        title: 'Run-Status-Tabelle',
        content: `
<p>
  Die Haupttabelle zeigt alle Testl\u00E4ufe mit folgenden Spalten:
</p>
<ul>
  <li><strong>Status</strong> \u2014 Farbiger Badge: <code>pending</code> (grau), <code>running</code> (blau), <code>passed</code> (gr\u00FCn), <code>failed</code> (rot), <code>error</code> (orange), <code>cancelled</code> (grau), <code>timeout</code> (gelb)</li>
  <li><strong>Repository</strong> \u2014 Name des verwendeten Repositories</li>
  <li><strong>Zielpfad</strong> \u2014 Ausgef\u00FChrte Datei oder Verzeichnis</li>
  <li><strong>Gestartet</strong> \u2014 Zeitpunkt des Run-Starts</li>
  <li><strong>Dauer</strong> \u2014 Bisherige oder endg\u00FCltige Laufzeit</li>
  <li><strong>Aktionen</strong> \u2014 Details anzeigen, Abbrechen, Wiederholen</li>
</ul>
<p>
  Die Tabelle aktualisiert sich \u00FCber WebSocket in Echtzeit \u2014 laufende Runs
  wechseln ihren Status ohne Neuladen der Seite.
</p>`
      },
      {
        id: 'execution-details',
        title: 'Run-Details & Ausgabe',
        content: `
<p>
  Klicken Sie auf einen Run, um die Detailansicht zu \u00F6ffnen. Hier sehen Sie:
</p>
<ul>
  <li><strong>Metadaten</strong> \u2014 Repository, Zielpfad, Timeout, gestartet von, Start-/Endzeit</li>
  <li><strong>stdout</strong> \u2014 Die Standardausgabe des Robot-Framework-Prozesses (Live-Streaming bei laufenden Runs)</li>
  <li><strong>stderr</strong> \u2014 Fehlermeldungen und Warnungen</li>
</ul>
<p>
  Bei laufenden Runs wird die Ausgabe per WebSocket in Echtzeit aktualisiert.
  Die Konsole scrollt automatisch zum Ende, sofern Sie nicht manuell
  nach oben gescrollt haben.
</p>`
      },
      {
        id: 'execution-cancel-retry',
        title: 'Abbrechen & Wiederholen',
        content: `
<p>
  Laufende und wartende Runs k\u00F6nnen \u00FCber verschiedene Wege gesteuert werden:
</p>
<h4>Einzelnen Run abbrechen</h4>
<p>
  Klicken Sie auf das <strong>Abbrechen</strong>-Symbol in der Aktionsspalte.
  Der Run erh\u00E4lt den Status <code>cancelled</code>.
</p>
<h4>Alle Runs abbrechen</h4>
<p>
  Der Button <strong>Alle abbrechen</strong> bricht s\u00E4mtliche laufenden und
  wartenden Runs auf einmal ab. Diese Funktion steht Benutzern mit der
  Rolle <em>Runner</em> oder h\u00F6her zur Verf\u00FCgung.
</p>
<h4>Run wiederholen</h4>
<p>
  \u00DCber den <strong>Wiederholen</strong>-Button wird ein neuer Run mit identischen
  Parametern (Repository, Zielpfad, Timeout) gestartet. Der urspr\u00FCngliche
  Run bleibt im Verlauf erhalten.
</p>`,
        tip: 'Abgebrochene Runs erzeugen keine Reports. Wenn der Prozess bereits Teilergebnisse geschrieben hat, werden diese nicht verarbeitet.'
      }
    ]
  },
  {
    id: 'reports',
    title: 'Reports',
    icon: '\u{1F4CB}',
    subsections: [
      {
        id: 'reports-list',
        title: 'Report-Liste',
        content: `
<p>
  Die Report-Seite zeigt alle verf\u00FCgbaren Testergebnisse in einer
  \u00FCbersichtlichen Tabelle. F\u00FCr jeden Report werden angezeigt:
</p>
<ul>
  <li><strong>Status-Badge</strong> \u2014 Gesamtergebnis (passed/failed)</li>
  <li><strong>Repository & Zielpfad</strong> \u2014 Herkunft des Runs</li>
  <li><strong>Tests bestanden / fehlgeschlagen</strong> \u2014 Numerische Zusammenfassung</li>
  <li><strong>Dauer</strong> \u2014 Gesamtlaufzeit</li>
  <li><strong>Erstellt am</strong> \u2014 Zeitstempel</li>
</ul>
<p>
  Die Liste kann nach Status gefiltert und nach jeder Spalte sortiert werden.
  Ein Klick auf einen Report \u00F6ffnet die Detailansicht.
</p>`
      },
      {
        id: 'reports-detail',
        title: 'Report-Detail',
        content: `
<p>
  Die Detailansicht eines Reports gliedert sich in drei Tabs:
</p>
<h4>Tab 1: Zusammenfassung</h4>
<p>
  Kompakte \u00DCbersicht mit Gesamtergebnis, Anzahl bestandener und
  fehlgeschlagener Tests, Gesamtdauer und Fehlerdetails.
</p>
<h4>Tab 2: HTML Report</h4>
<p>
  Der von Robot Framework generierte HTML-Report wird in einem eingebetteten
  Frame dargestellt. Dieser enth\u00E4lt die vollst\u00E4ndige interaktive Ansicht
  mit Suiten-, Test- und Keyword-Details.
</p>
<h4>Tab 3: XML-Ansicht</h4>
<p>
  Die rohe <code>output.xml</code>-Datei kann hier eingesehen werden. Diese
  ist n\u00FCtzlich f\u00FCr Debugging-Zwecke oder zur automatisierten
  Weiterverarbeitung.
</p>`
      },
      {
        id: 'reports-download',
        title: 'ZIP-Download',
        content: `
<p>
  Jeder Report kann als ZIP-Archiv heruntergeladen werden. Das Archiv enth\u00E4lt:
</p>
<ul>
  <li><code>report.html</code> \u2014 Der HTML-Report</li>
  <li><code>log.html</code> \u2014 Das detaillierte Log</li>
  <li><code>output.xml</code> \u2014 Die maschinenlesbare Ausgabe</li>
  <li>Gegebenenfalls weitere Artefakte (Screenshots etc.)</li>
</ul>
<p>
  Klicken Sie auf den <strong>Download</strong>-Button in der Report-Detail-
  oder der Report-Listen-Ansicht.
</p>`,
        tip: 'Die ZIP-Datei eignet sich ideal zum Archivieren oder Teilen von Ergebnissen mit Teammitgliedern, die keinen mateoX-Zugang haben.'
      },
      {
        id: 'reports-delete-all',
        title: 'Alle Reports l\u00F6schen',
        content: `
<p>
  Administratoren k\u00F6nnen \u00FCber den Button <strong>Alle l\u00F6schen</strong>
  s\u00E4mtliche Reports auf einmal entfernen. Vor der L\u00F6schung erscheint ein
  Best\u00E4tigungsdialog.
</p>
<p>
  <strong>Achtung:</strong> Diese Aktion l\u00F6scht alle Report-Dateien und
  Datenbankeintr\u00E4ge unwiderruflich. Laden Sie wichtige Reports vorher als
  ZIP herunter.
</p>
<p>
  <strong>Berechtigung:</strong> Nur Benutzer mit der Rolle <em>Admin</em>
  k\u00F6nnen diese Aktion ausf\u00FChren.
</p>`
      }
    ]
  },
  {
    id: 'statistics',
    title: 'Statistiken',
    icon: '\u{1F4C8}',
    subsections: [
      {
        id: 'statistics-overview',
        title: '\u00DCbersicht',
        content: `
<p>
  Die Statistik-Seite bietet vertiefte Analysen \u00FCber Ihre Testergebnisse
  hinweg. Sie hilft dabei, Trends zu erkennen, problematische Tests zu
  identifizieren und die Gesamtqualit\u00E4t der Testautomatisierung zu bewerten.
</p>
<p>
  Alle Diagramme und Kennzahlen reagieren auf die gew\u00E4hlten Filter und
  aktualisieren sich dynamisch.
</p>`
      },
      {
        id: 'statistics-filters',
        title: 'Zeitraum- & Repository-Filter',
        content: `
<p>
  Am oberen Rand stehen zwei Filter zur Verf\u00FCgung:
</p>
<h4>Zeitraum-Filter</h4>
<p>
  W\u00E4hlen Sie den Auswertungszeitraum aus folgenden Optionen:
</p>
<ul>
  <li><strong>7 Tage</strong> \u2014 Letzte Woche</li>
  <li><strong>14 Tage</strong> \u2014 Letzte zwei Wochen</li>
  <li><strong>30 Tage</strong> \u2014 Letzter Monat (Standard)</li>
  <li><strong>90 Tage</strong> \u2014 Letztes Quartal</li>
  <li><strong>1 Jahr</strong> \u2014 Letztes Jahr</li>
</ul>
<h4>Repository-Filter</h4>
<p>
  Filtern Sie die Statistiken nach einem bestimmten Repository oder lassen
  Sie <em>Alle Repositories</em> ausgew\u00E4hlt, um aggregierte Daten zu sehen.
</p>`
      },
      {
        id: 'statistics-kpis',
        title: 'KPI-Karten & Erfolgsquote',
        content: `
<p>
  Die KPI-Karten auf der Statistik-Seite zeigen detailliertere Kennzahlen als
  auf dem Dashboard:
</p>
<ul>
  <li><strong>Gesamte Runs</strong> \u2014 Anzahl der Runs im gew\u00E4hlten Zeitraum</li>
  <li><strong>Erfolgsquote</strong> \u2014 Prozentsatz der bestandenen Runs</li>
  <li><strong>\u00D8 Laufzeit</strong> \u2014 Durchschnittliche Ausf\u00FChrungsdauer</li>
  <li><strong>Fehlgeschlagene Tests</strong> \u2014 Gesamtzahl einzigartiger fehlgeschlagener Tests</li>
</ul>
<h4>Erfolgsquote \u00FCber Zeit</h4>
<p>
  Ein Liniendiagramm zeigt die Entwicklung der Erfolgsquote \u00FCber den
  gew\u00E4hlten Zeitraum. So l\u00E4sst sich auf einen Blick erkennen, ob die
  Testqualit\u00E4t steigt oder f\u00E4llt.
</p>`
      },
      {
        id: 'statistics-trends',
        title: 'Pass/Fail-Trend',
        content: `
<p>
  Das Pass/Fail-Trend-Diagramm stellt als gestapeltes Balkendiagramm
  die t\u00E4gliche Verteilung von bestandenen und fehlgeschlagenen Runs dar.
</p>
<ul>
  <li><strong>Gr\u00FCne Balken</strong> \u2014 Anzahl bestandener Runs pro Tag</li>
  <li><strong>Rote Balken</strong> \u2014 Anzahl fehlgeschlagener Runs pro Tag</li>
</ul>
<p>
  Dieses Diagramm hilft dabei, Spitzen von Fehlschl\u00E4gen zu identifizieren
  und mit Ereignissen (Deployments, Code-\u00C4nderungen) zu korrelieren.
</p>`
      },
      {
        id: 'statistics-flaky',
        title: 'Flaky-Test-Erkennung',
        content: `
<p>
  Die Flaky-Test-Erkennung identifiziert Tests, die ein instabiles Verhalten
  aufweisen \u2014 also abwechselnd bestehen und fehlschlagen, ohne dass sich der
  Testcode ge\u00E4ndert hat.
</p>
<p>
  Ein Test gilt als <em>flaky</em>, wenn er im gew\u00E4hlten Zeitraum sowohl
  Pass- als auch Fail-Ergebnisse hatte. Die Tabelle zeigt:
</p>
<table>
  <thead>
    <tr><th>Spalte</th><th>Beschreibung</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>Testname</strong></td><td>Vollqualifizierter Name des Tests</td></tr>
    <tr><td><strong>Pass-Rate</strong></td><td>Anteil der erfolgreichen L\u00E4ufe</td></tr>
    <tr><td><strong>Wechsel</strong></td><td>Anzahl der Status-Wechsel (Pass \u2192 Fail oder umgekehrt)</td></tr>
    <tr><td><strong>Gesamtl\u00E4ufe</strong></td><td>Anzahl der L\u00E4ufe im Zeitraum</td></tr>
  </tbody>
</table>`,
        tip: 'Flaky Tests untergraben das Vertrauen in die Testautomatisierung. Priorisieren Sie deren Stabilisierung, um verl\u00E4ssliche Ergebnisse zu erhalten.'
      },
      {
        id: 'statistics-refresh',
        title: 'Aktualisieren & Datenaktualit\u00E4t',
        content: `
<p>
  Statistikdaten k\u00F6nnen veralten, wenn neue Testl\u00E4ufe abgeschlossen werden.
  Ein Hinweis-Banner erscheint oben auf der Seite, wenn die Daten seit l\u00E4ngerer
  Zeit nicht aktualisiert wurden.
</p>
<h4>Manuelles Aktualisieren</h4>
<p>
  Klicken Sie auf den <strong>Aktualisieren</strong>-Button, um alle KPI-Karten,
  Diagramme und Tabellen mit den neuesten Daten neu zu laden.
</p>
<h4>\u00DCbersicht & Tiefenanalyse</h4>
<p>
  Die Statistik-Seite ist in zwei Tabs unterteilt:
</p>
<ul>
  <li><strong>\u00DCbersicht</strong> \u2014 KPI-Karten, Erfolgsquoten-Chart, Pass/Fail-Trend und Flaky-Test-Erkennung.</li>
  <li><strong>Tiefenanalyse</strong> \u2014 On-Demand-Analyse von Keyword-Analytik, Testqualit\u00E4t, Wartungsindikatoren und Quellcode-Analyse. W\u00E4hlen Sie KPIs aus und starten Sie eine Analyse f\u00FCr tiefere Einblicke.</li>
</ul>
<h4>Quellcode-Analyse (Neu)</h4>
<p>
  Wenn ein Projekt ausgew\u00E4hlt ist, stehen zwei zus\u00E4tzliche KPIs in der Kategorie <em>Quellcode-Analyse</em> zur Verf\u00FCgung:
</p>
<ul>
  <li><strong>Quellcode-Testanalyse</strong> \u2014 Analysiert Ihre <code>.robot</code>-Quelldateien direkt: Testf\u00E4lle pro Datei, durchschnittliche Zeilen und Keyword-Schritte pro Test, meistverwendete Keywords und Datei\u00FCbersicht.</li>
  <li><strong>Quellcode-Bibliotheksimporte</strong> \u2014 Zeigt, welche Robot-Framework-Bibliotheken in Ihren <code>.robot</code>- und <code>.resource</code>-Dateien importiert werden, wie viele Dateien jede Bibliothek nutzen und deren Verteilung.</li>
</ul>
<p>
  Diese KPIs funktionieren unabh\u00E4ngig von Ausf\u00FChrungsreports \u2014 sie analysieren die Quelldateien auf der Festplatte, sodass Sie Einblicke erhalten, noch bevor Tests ausgef\u00FChrt werden.
</p>
<h4>Bibliotheksverteilung (Korrektur)</h4>
<p>
  Der KPI <em>Bibliotheksverteilung</em> (in der Kategorie Keyword-Analyse) l\u00F6st Bibliotheksnamen f\u00FCr bekannte Robot-Framework-Keywords nun korrekt auf. Zuvor wurden viele Keywords als \u201EUnknown\u201C angezeigt, da die <code>output.xml</code> nicht immer das Library-Attribut enth\u00E4lt. Das System verwendet jetzt ein integriertes Mapping von \u00FCber 500 Keywords zu ihren Bibliotheken (BuiltIn, Collections, SeleniumLibrary, Browser, RequestsLibrary etc.).
</p>`,
        tip: 'Nutzen Sie die Tiefenanalyse, um Keyword-Laufzeiten, Assertion-Dichte und Fehlermuster in Ihren Testsuiten zu untersuchen. W\u00E4hlen Sie ein Projekt, um die Quellcode-Analyse-KPIs zu aktivieren.'
      }
    ]
  },
  {
    id: 'environments',
    title: 'Umgebungen',
    icon: '\u2699\uFE0F',
    subsections: [
      {
        id: 'environments-overview',
        title: '\u00DCbersicht',
        content: `
<p>
  Unter <strong>Umgebungen</strong> verwalten Sie die Python-Laufzeitumgebungen,
  in denen Ihre Robot-Framework-Tests ausgef\u00FChrt werden. Jede Umgebung ist
  ein isoliertes <em>Virtual Environment</em> (venv) mit eigenen Paketen
  und Umgebungsvariablen.
</p>
<p>
  So k\u00F6nnen Sie verschiedene Projekte mit unterschiedlichen Bibliotheksversionen
  parallel betreiben, ohne dass es zu Konflikten kommt.
</p>`
      },
      {
        id: 'environments-create',
        title: 'Umgebung erstellen',
        content: `
<p>
  Klicken Sie auf <strong>Neue Umgebung</strong> und geben Sie einen
  aussagekr\u00E4ftigen Namen ein (z.\u202FB. <code>projekt-a-rf7</code>).
  mateoX erstellt daraufhin ein neues Python-venv im konfigurierten
  Verzeichnis (<code>~/.mateox/venvs/</code>).
</p>
<p>
  Nach der Erstellung ist das venv sofort verf\u00FCgbar und kann mit Paketen
  best\u00FCckt werden. Robot Framework wird <em>nicht</em> automatisch
  installiert \u2014 f\u00FCgen Sie es bei Bedarf manuell hinzu.
</p>
<p>
  <strong>Berechtigung:</strong> Mindestens <em>Editor</em> erforderlich.
</p>`
      },
      {
        id: 'environments-packages',
        title: 'Pakete installieren',
        content: `
<p>
  Im Bereich <strong>Pakete</strong> einer Umgebung k\u00F6nnen Sie
  Python-Pakete installieren und verwalten:
</p>
<h4>Beliebte RF-Bibliotheken</h4>
<p>
  Eine vorkuratierte Liste g\u00E4ngiger Robot-Framework-Bibliotheken steht
  zur Schnellinstallation bereit:
</p>
<ul>
  <li><code>robotframework</code> \u2014 Kern-Framework</li>
  <li><code>robotframework-browser</code> \u2014 Browser-Automatisierung (Playwright)</li>
  <li><code>robotframework-seleniumlibrary</code> \u2014 Selenium-basierte Webtests</li>
  <li><code>robotframework-requests</code> \u2014 HTTP/REST-API-Tests</li>
  <li><code>robotframework-datadriver</code> \u2014 Datengetriebene Tests</li>
  <li><code>robotframework-databaselibrary</code> \u2014 Datenbank-Tests</li>
</ul>
<h4>PyPI-Suche</h4>
<p>
  \u00DCber das Suchfeld k\u00F6nnen Sie beliebige Pakete aus dem Python Package
  Index (PyPI) suchen und installieren. Geben Sie den Paketnamen ein,
  w\u00E4hlen Sie die gew\u00FCnschte Version und klicken Sie auf
  <strong>Installieren</strong>.
</p>`,
        tip: 'Installieren Sie immer eine konkrete Version (z. B. robotframework==7.1), um reproduzierbare Testergebnisse sicherzustellen.'
      },
      {
        id: 'environments-variables',
        title: 'Umgebungsvariablen',
        content: `
<p>
  Jede Umgebung kann mit eigenen Umgebungsvariablen konfiguriert werden.
  Diese werden beim Starten eines Runs an den Robot-Framework-Prozess
  \u00FCbergeben.
</p>
<p>
  Typische Anwendungsf\u00E4lle:
</p>
<ul>
  <li><code>BROWSER</code> \u2014 Standard-Browser f\u00FCr Webtests (z.\u202FB. <code>chromium</code>, <code>firefox</code>)</li>
  <li><code>BASE_URL</code> \u2014 Basis-URL der zu testenden Anwendung</li>
  <li><code>API_KEY</code> \u2014 Authentifizierungs-Token f\u00FCr API-Tests</li>
  <li><code>HEADLESS</code> \u2014 Ob der Browser im Headless-Modus laufen soll</li>
</ul>
<p>
  Variablen werden als Schl\u00FCssel-Wert-Paare angelegt und k\u00F6nnen jederzeit
  bearbeitet oder gel\u00F6scht werden.
</p>`
      },
      {
        id: 'environments-clone-delete',
        title: 'Klonen & L\u00F6schen',
        content: `
<p>
  Bestehende Umgebungen k\u00F6nnen geklont werden, um schnell Varianten zu
  erstellen:
</p>
<ul>
  <li><strong>Klonen</strong> \u2014 Erstellt eine Kopie der Umgebung mit allen installierten Paketen und Variablen. Das neue venv erh\u00E4lt einen eigenen Namen.</li>
  <li><strong>L\u00F6schen</strong> \u2014 Entfernt die Umgebung inklusive aller Pakete und Variablen. Dieser Vorgang kann nicht r\u00FCckg\u00E4ngig gemacht werden.</li>
</ul>
<p>
  Bevor eine Umgebung gel\u00F6scht wird, pr\u00FCfen Sie, ob noch Repositories
  oder Runs auf sie verweisen. Andernfalls k\u00F6nnte es bei zuk\u00FCnftigen
  Ausf\u00FChrungen zu Fehlern kommen.
</p>`,
        tip: 'Klonen eignet sich hervorragend, um eine stabile Umgebung zu sichern, bevor Sie Paket-Updates testen.'
      }
    ]
  },
  {
    id: 'settings',
    title: 'Einstellungen',
    icon: '\u{1F527}',
    subsections: [
      {
        id: 'settings-overview',
        title: '\u00DCbersicht',
        content: `
<p>
  Der Bereich <strong>Einstellungen</strong> ist ausschlie\u00DFlich f\u00FCr
  Administratoren zug\u00E4nglich und dient der Verwaltung von Benutzern und
  Systemkonfigurationen.
</p>
<p>
  In der Navigation wird der Men\u00FCpunkt nur angezeigt, wenn der angemeldete
  Benutzer die Rolle <em>Admin</em> besitzt.
</p>`
      },
      {
        id: 'settings-user-management',
        title: 'Benutzerverwaltung',
        content: `
<p>
  Die Benutzertabelle zeigt alle registrierten Konten mit folgenden Angaben:
</p>
<ul>
  <li><strong>Name</strong> \u2014 Anzeigename des Benutzers</li>
  <li><strong>E-Mail</strong> \u2014 Login-Adresse</li>
  <li><strong>Rolle</strong> \u2014 Zugewiesene Berechtigungsstufe</li>
  <li><strong>Status</strong> \u2014 Aktiv oder deaktiviert</li>
  <li><strong>Erstellt am</strong> \u2014 Registrierungsdatum</li>
</ul>
<h4>Neuen Benutzer erstellen</h4>
<p>
  Klicken Sie auf <strong>Benutzer hinzuf\u00FCgen</strong> und f\u00FCllen Sie
  das Formular aus:
</p>
<ol>
  <li><strong>Name</strong> \u2014 Vor- und Nachname</li>
  <li><strong>E-Mail</strong> \u2014 Muss eindeutig sein</li>
  <li><strong>Passwort</strong> \u2014 Mindestens 6 Zeichen</li>
  <li><strong>Rolle</strong> \u2014 Viewer, Runner, Editor oder Admin</li>
</ol>`
      },
      {
        id: 'settings-roles',
        title: 'Rollenzuweisung',
        content: `
<p>
  Die Rolle eines Benutzers kann jederzeit \u00FCber das Bearbeiten-Formular
  ge\u00E4ndert werden:
</p>
<ol>
  <li>Klicken Sie auf das <strong>Bearbeiten</strong>-Symbol neben dem Benutzer</li>
  <li>W\u00E4hlen Sie die neue Rolle aus dem Dropdown</li>
  <li>Speichern Sie die \u00C4nderung</li>
</ol>
<p>
  Die neue Rolle wird sofort wirksam. Beim n\u00E4chsten API-Aufruf des
  betroffenen Benutzers wird das aktualisierte Rechte-Set gepr\u00FCft.
</p>
<p>
  <strong>Hinweis:</strong> Ein Admin kann sich selbst nicht herabstufen.
  Es muss immer mindestens ein aktiver Administrator im System verbleiben.
</p>`
      },
      {
        id: 'settings-activate-deactivate',
        title: 'Benutzer aktivieren & deaktivieren',
        content: `
<p>
  Anstatt Benutzer zu l\u00F6schen, k\u00F6nnen sie deaktiviert werden. Deaktivierte
  Benutzer:
</p>
<ul>
  <li>K\u00F6nnen sich nicht mehr anmelden</li>
  <li>Behalten ihre historischen Daten (Runs, Reports)</li>
  <li>K\u00F6nnen jederzeit wieder aktiviert werden</li>
</ul>
<p>
  Schalten Sie den Status-Toggle in der Benutzertabelle um, um einen
  Benutzer zu aktivieren oder zu deaktivieren.
</p>`,
        tip: 'Deaktivieren statt L\u00F6schen ist empfehlenswert, da so die Nachvollziehbarkeit gewahrt bleibt (z. B. wer welchen Run gestartet hat).'
      },
      {
        id: 'settings-delete-user',
        title: 'Benutzer l\u00F6schen',
        content: `
<p>
  Falls ein Benutzerkonto vollst\u00E4ndig entfernt werden soll, klicken Sie
  auf das <strong>L\u00F6schen</strong>-Symbol und best\u00E4tigen Sie den Vorgang.
</p>
<p>
  Beachten Sie:
</p>
<ul>
  <li>Das L\u00F6schen ist <strong>unwiderruflich</strong></li>
  <li>Referenzen in bestehenden Runs und Reports bleiben als verwaiste Eintr\u00E4ge erhalten</li>
  <li>Der aktuell angemeldete Benutzer kann nicht gel\u00F6scht werden</li>
  <li>Der letzte verbleibende Admin kann nicht gel\u00F6scht werden</li>
</ul>`
      },
      {
        id: 'settings-password-reset',
        title: 'Passwort zur\u00FCcksetzen',
        content: `
<p>
  Administratoren k\u00F6nnen das Passwort eines Benutzers direkt \u00FCber die
  Benutzerverwaltung zur\u00FCcksetzen:
</p>
<ol>
  <li>Navigieren Sie zu <strong>Einstellungen \u2192 Benutzer</strong>.</li>
  <li>Klicken Sie auf den Button <strong>Passwort zur\u00FCcksetzen</strong> in der entsprechenden Zeile.</li>
  <li>Geben Sie das neue Passwort ein (mindestens 6 Zeichen).</li>
  <li>Klicken Sie auf <strong>Passwort setzen</strong>.</li>
</ol>
<p>
  Die \u00C4nderung wird sofort wirksam. Bestehende Sitzungen des Benutzers
  bleiben aktiv, aber beim n\u00E4chsten Login wird das neue Passwort ben\u00F6tigt.
</p>`,
        tip: 'Kommunizieren Sie das neue Passwort auf einem sicheren Kanal an den Benutzer.'
      }
    ]
  },
  {
    id: 'advanced',
    title: 'Erweitert',
    icon: '\u{1F4A1}',
    subsections: [
      {
        id: 'advanced-websocket',
        title: 'WebSocket-Live-Updates',
        content: `
<p>
  mateoX nutzt <strong>WebSocket-Verbindungen</strong> f\u00FCr Echtzeit-Updates
  in der Oberfl\u00E4che. Folgende Bereiche profitieren davon:
</p>
<ul>
  <li><strong>Ausf\u00FChrungs-Seite</strong> \u2014 Run-Status wechselt live ohne Neuladen (pending \u2192 running \u2192 passed/failed)</li>
  <li><strong>Run-Details</strong> \u2014 stdout/stderr wird w\u00E4hrend der Ausf\u00FChrung in Echtzeit gestreamt</li>
  <li><strong>Dashboard</strong> \u2014 KPIs aktualisieren sich nach Abschluss eines Runs</li>
</ul>
<p>
  Die WebSocket-Verbindung wird beim Betreten einer Seite automatisch aufgebaut
  und beim Verlassen geschlossen. Bei Verbindungsabbruch versucht der Client
  automatisch, die Verbindung wiederherzustellen.
</p>
<p>
  Das Composable <code>useWebSocket</code> stellt die Verbindungslogik f\u00FCr
  alle Views bereit.
</p>`
      },
      {
        id: 'advanced-shortcuts',
        title: 'Tastenkombinationen',
        content: `
<p>
  mateoX unterst\u00FCtzt verschiedene Tastenkombinationen f\u00FCr effizientes
  Arbeiten:
</p>
<table>
  <thead>
    <tr><th>Tastenkombination</th><th>Aktion</th><th>Bereich</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><code>Ctrl+S</code> / <code>Cmd+S</code></td>
      <td>Datei speichern</td>
      <td>Explorer-Editor</td>
    </tr>
    <tr>
      <td><code>Ctrl+F</code> / <code>Cmd+F</code></td>
      <td>Suche \u00F6ffnen</td>
      <td>Explorer-Editor</td>
    </tr>
    <tr>
      <td><code>Escape</code></td>
      <td>Modal / Dialog schlie\u00DFen</td>
      <td>\u00DCberall</td>
    </tr>
    <tr>
      <td><code>Ctrl+Enter</code> / <code>Cmd+Enter</code></td>
      <td>Formular absenden</td>
      <td>Dialoge</td>
    </tr>
  </tbody>
</table>
<p>
  Modale Dialoge lassen sich au\u00DFerdem durch Klicken auf den Hintergrund
  (Backdrop) schlie\u00DFen.
</p>`
      },
      {
        id: 'advanced-tips',
        title: 'Tipps f\u00FCr effizientes Arbeiten',
        content: `
<p>
  Die folgenden Empfehlungen helfen Ihnen, mateoX optimal zu nutzen:
</p>
<h4>Repository-Organisation</h4>
<ul>
  <li>Strukturieren Sie Ihre Tests in logische Unterverzeichnisse (z.\u202FB. <code>tests/api/</code>, <code>tests/ui/</code>)</li>
  <li>Verwenden Sie sprechende Dateinamen f\u00FCr Ihre <code>.robot</code>-Dateien</li>
  <li>Aktivieren Sie Auto-Sync, damit Tests stets aktuell sind</li>
</ul>
<h4>Umgebungen verwalten</h4>
<ul>
  <li>Erstellen Sie separate Umgebungen f\u00FCr verschiedene Projekte</li>
  <li>Pinnen Sie Paketversionen, um reproduzierbare Ergebnisse zu erzielen</li>
  <li>Klonen Sie eine funktionierende Umgebung, bevor Sie Updates durchf\u00FChren</li>
</ul>
<h4>Reports auswerten</h4>
<ul>
  <li>Nutzen Sie die Statistik-Seite, um Trends \u00FCber l\u00E4ngere Zeitr\u00E4ume zu erkennen</li>
  <li>Priorisieren Sie Flaky Tests \u2014 sie verdecken echte Fehler</li>
  <li>Laden Sie wichtige Reports als ZIP herunter, bevor Sie alte Daten bereinigen</li>
</ul>`
      },
      {
        id: 'advanced-troubleshooting',
        title: 'Fehlerbehebung',
        content: `
<p>
  Bei Problemen mit mateoX k\u00F6nnen die folgenden Schritte helfen:
</p>
<h4>Login schl\u00E4gt fehl</h4>
<ul>
  <li>Pr\u00FCfen Sie, ob das Backend unter <code>http://localhost:8000</code> erreichbar ist</li>
  <li>Stellen Sie sicher, dass die Datenbank migriert wurde (<code>make db-upgrade</code>)</li>
  <li>Setzen Sie das Admin-Passwort zur\u00FCck, indem Sie die Datenbank neu initialisieren</li>
</ul>
<h4>Git-Clone oder Sync fehlgeschlagen</h4>
<ul>
  <li>\u00DCberpr\u00FCfen Sie die Repository-URL auf Tippfehler</li>
  <li>Stellen Sie sicher, dass der Server Zugriff auf das Repository hat (SSH-Key oder HTTPS-Credentials)</li>
  <li>Pr\u00FCfen Sie die Netzwerkverbindung des Servers</li>
</ul>
<h4>Runs bleiben im Status "pending" h\u00E4ngen</h4>
<ul>
  <li>Der Worker verarbeitet jeweils nur einen Run. Warten Sie, bis der aktuelle Run abgeschlossen ist.</li>
  <li>Pr\u00FCfen Sie die Backend-Logs auf Fehler (<code>make docker-logs</code> oder direkte Konsolenausgabe)</li>
  <li>Starten Sie das Backend bei Bedarf neu, um den Task-Executor zur\u00FCckzusetzen</li>
</ul>
<h4>WebSocket-Verbindung bricht ab</h4>
<ul>
  <li>Die Verbindung wird automatisch wiederhergestellt. Laden Sie die Seite manuell neu, falls das nicht funktioniert.</li>
  <li>Pr\u00FCfen Sie, ob ein Reverse Proxy (z.\u202FB. Nginx) WebSocket-Verbindungen korrekt weiterleitet</li>
</ul>`,
        tip: 'Die Swagger-API-Dokumentation unter http://localhost:8000/api/v1/docs ist ein wertvolles Werkzeug zum Debugging von API-Problemen.'
      },
      {
        id: 'advanced-api',
        title: 'API-Zugriff',
        content: `
<p>
  mateoX stellt eine vollst\u00E4ndige REST-API unter <code>/api/v1/</code> bereit.
  Alle Funktionen der Oberfl\u00E4che sind auch programmatisch nutzbar.
</p>
<h4>Authentifizierung</h4>
<p>
  Die API nutzt JWT-Bearer-Tokens. Fordern Sie ein Token \u00FCber den
  Login-Endpunkt an:
</p>
<p>
  <code>POST /api/v1/auth/login</code> mit <code>{"email": "...", "password": "..."}</code>
</p>
<p>
  Das erhaltene Token senden Sie als <code>Authorization: Bearer &lt;token&gt;</code>
  Header mit jeder Anfrage.
</p>
<h4>Wichtige Endpunkte</h4>
<table>
  <thead>
    <tr><th>Endpunkt</th><th>Beschreibung</th></tr>
  </thead>
  <tbody>
    <tr><td><code>GET /api/v1/repos</code></td><td>Alle Repositories auflisten</td></tr>
    <tr><td><code>POST /api/v1/runs</code></td><td>Neuen Run starten</td></tr>
    <tr><td><code>GET /api/v1/reports</code></td><td>Reports auflisten</td></tr>
    <tr><td><code>GET /api/v1/stats/kpis</code></td><td>KPI-Daten abrufen</td></tr>
  </tbody>
</table>
<p>
  Die vollst\u00E4ndige API-Dokumentation mit allen Endpunkten, Parametern und
  Antwortformaten finden Sie in der interaktiven
  <strong>Swagger UI</strong> unter <code>/api/v1/docs</code>.
</p>`
      }
    ]
  },

  // ─── Rechtliches & Info ─────────────────────────────────────────
  {
    id: 'legal',
    title: 'Rechtliches & Info',
    icon: 'info',
    subsections: [
      {
        id: 'legal-footer',
        title: 'Footer',
        content: `
<p>
  Am unteren Rand jeder Seite befindet sich ein Footer mit folgenden Informationen:
</p>
<ul>
  <li>Der <strong>Copyright-Hinweis</strong> der viadee Unternehmensberatung AG.</li>
  <li>Ein Link zur <strong>mateo-automation.com</strong>-Website.</li>
  <li>Ein Link zum <strong>Impressum</strong>.</li>
</ul>`
      },
      {
        id: 'legal-imprint',
        title: 'Impressum',
        content: `
<p>
  Die <strong>Impressum</strong>-Seite enth\u00E4lt die gesetzlich vorgeschriebenen
  Angaben gem\u00E4\u00DF \u00A7 5 TMG f\u00FCr die <em>viadee Unternehmensberatung AG</em>:
  Firmenadresse, Kontaktdaten, Vorstand, Handelsregistereintrag und
  Umsatzsteuer-Identifikationsnummer.
</p>
<p>
  Erreichbar \u00FCber den Footer-Link oder direkt unter <code>/imprint</code>.
</p>`
      }
    ]
  }
]

export default de
