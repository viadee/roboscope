*** Settings ***
Documentation    End-to-end smoke test for viadee.de:
...              - akzeptiert das Cookie-Banner
...              - prueft die Suchfunktion (Header-Suche, Trefferseite)
...              - besucht jede Leistungs-Seite und verifiziert die H1
...              - liest alle offenen Stellen aus /karriere/jobs/ und schreibt sie in eine Excel-Datei
...              Macht regelmaessig Screenshots ueber das Browser-Library Keyword "Take Screenshot".
Library          Browser    timeout=30s
Library          Collections
Library          OperatingSystem
Library          String
Library          ExcelSage
Suite Setup      Open Viadee Homepage
Suite Teardown   Close Browser

*** Variables ***
${HEADLESS}              true
${BASE_URL}              https://www.viadee.de
${SEARCH_TERM}           Cloud
${COOKIE_WAIT_SECONDS}   12
${EXCEL_OUTPUT}          ${OUTPUT_DIR}${/}viadee_karriere.xlsx
@{LEISTUNGEN}
...                      bpm-prozessautomatisierung
...                      quality-engineering
...                      organisationsentwicklung
...                      softwareentwicklung-und-architektur
...                      projektmanagement
...                      business-analyse
...                      data-ai
...                      cloud-architektur-und-plattformen
...                      it-sicherheit

*** Test Cases ***
Suche Auf viadee.de Liefert Treffer
    [Documentation]    Oeffnet die Header-Suche, tippt ${SEARCH_TERM} ein und prueft, dass Live-Treffer im Overlay erscheinen.
    ...                Die Suche ist JS-basiert (Alpine.js) und rendert Ergebnisse inline (kein URL-Wechsel).
    Take Screenshot    fullPage=True
    Open Search Overlay
    Take Screenshot    fullPage=False
    Eingabe Tippen Stabil    input[name="search"]    ${SEARCH_TERM}
    Take Screenshot    fullPage=True
    ${value_attr}=    Get Property    input[name="search"]    value
    Log    Suchwert im Input: '${value_attr}'
    Should Be Equal As Strings    ${value_attr}    ${SEARCH_TERM}    Eingabe wurde nicht vollstaendig uebernommen
    Keyboard Key    press    Enter
    Sleep    1000ms
    Take Screenshot    fullPage=True
    ${overlay_links}=    Get Element Count    [x-show="searchOpen"] a[href]
    Log    Treffer-Links im Such-Overlay: ${overlay_links}
    Should Be True    ${overlay_links} > 0    Keine Treffer im Such-Overlay nach Eingabe von "${SEARCH_TERM}"

Alle Leistungen Sind Erreichbar
    [Documentation]    Besucht jede Leistungs-Seite aus dem Nav und prueft, dass die H1 nicht leer ist.
    FOR    ${slug}    IN    @{LEISTUNGEN}
        Log    Pruefe Leistung: ${slug}
        Go To    ${BASE_URL}/leistungen/${slug}/
        Wait For Load State    domcontentloaded    timeout=20s
        Wait For Elements State    h1    visible    timeout=15s
        ${h1}=    Get Text    h1
        Should Not Be Empty    ${h1}    Leere H1 auf /leistungen/${slug}/
        Log    OK: ${slug} -> ${h1}
        Take Screenshot    fullPage=False
    END

Karriere Eintraege Werden In Excel Geschrieben
    [Documentation]    Besucht /karriere/jobs/, sammelt jeden Job (Titel + Link) und schreibt sie in ${EXCEL_OUTPUT}.
    Go To    ${BASE_URL}/karriere/jobs/
    Wait For Load State    domcontentloaded    timeout=20s
    Wait For Elements State    main    visible    timeout=15s
    Take Screenshot    fullPage=True
    ${jobs}=    Sammle Karriere Eintraege
    Length Should Be At Least    ${jobs}    1
    Schreibe Eintraege Mit ExcelSage    ${jobs}    ${EXCEL_OUTPUT}
    File Should Exist    ${EXCEL_OUTPUT}
    ${count}=    Get Length    ${jobs}
    ${expected_rows}=    Evaluate    ${count} + 1                                   # +1 fuer Header
    # ExcelSage haelt nach Close Workbook keinen Zustand mehr -- fuer die
    # Assertions die Datei erneut oeffnen, pruefen, wieder schliessen.
    Open Workbook    workbook_name=${EXCEL_OUTPUT}
    Row Count Should Be    ${expected_rows}    sheet_name=Karriere    message=Excel-Sheet enthaelt nicht die erwarteten Datenzeilen (inkl. Header)
    Cell Value Should Be    A1    title    sheet_name=Karriere
    Cell Value Should Be    B1    url      sheet_name=Karriere
    Close Workbook
    Log    Excel geschrieben: ${EXCEL_OUTPUT} (${count} Eintraege)
    Take Screenshot    fullPage=False

*** Keywords ***
Open Viadee Homepage
    New Browser    chromium    headless=${HEADLESS}
    New Context    locale=de-DE    viewport={"width": 1440, "height": 900}
    New Page    ${BASE_URL}/    wait_until=domcontentloaded
    Wait For Load State    domcontentloaded    timeout=20s
    Accept Cookies If Present
    Wait For Elements State    header    visible    timeout=15s

Accept Cookies If Present
    [Documentation]    Wartet aktiv bis zu ${COOKIE_WAIT_SECONDS}s darauf, dass das Cookie-Banner
    ...                (Usercentrics oder generisch) erscheint, und klickt es weg.
    ...                Usercentrics laedt asynchron und kann erst Sekunden nach domcontentloaded auftauchen.
    @{candidates}=    Create List
    ...    button:has-text("Alles akzeptieren")
    ...    button:has-text("Alle akzeptieren")
    ...    button:has-text("Alle annehmen")
    ...    button:has-text("Akzeptieren")
    ...    button:has-text("Zustimmen")
    ...    button#cookiescript_accept
    ...    \#cookiescript_accept
    FOR    ${i}    IN RANGE    ${COOKIE_WAIT_SECONDS}
        FOR    ${sel}    IN    @{candidates}
            ${cnt}=    Get Element Count    ${sel}
            IF    ${cnt} == 0    CONTINUE
            ${visible}=    Run Keyword And Return Status    Wait For Elements State    ${sel} >> nth=0    visible    timeout=500ms
            IF    not ${visible}    CONTINUE
            ${clicked}=    Run Keyword And Return Status    Click    ${sel} >> nth=0
            IF    not ${clicked}    CONTINUE
            Sleep    600ms
            Log    Cookie-Banner via ${sel} akzeptiert.
            RETURN
        END
        Sleep    1s
    END
    Log    Kein Cookie-Banner innerhalb ${COOKIE_WAIT_SECONDS}s erschienen.

Open Search Overlay
    [Documentation]    Aktiviert die Header-Suche (Lupe). Der Trigger ist ein Button mit data-component-navbar="search-toggle".
    ...                Wartet anschliessend, bis Alpine.js die Transition + den Auto-Fokus auf das Input-Feld abgeschlossen hat.
    Go To    ${BASE_URL}/
    Wait For Load State    domcontentloaded    timeout=20s
    Wait For Elements State    header    visible    timeout=15s
    # Usercentrics laedt asynchron -- noch einmal absichern, dass das Banner weg ist.
    Accept Cookies If Present
    Wait For Elements State    button[data-component-navbar="search-toggle"]    visible    timeout=10s
    Click    button[data-component-navbar="search-toggle"]
    Wait For Elements State    input[name="search"]    visible    timeout=10s
    # Modal-Transition (~300ms) + setTimeout(focus, 100) im Bundle abwarten
    Sleep    600ms

Eingabe Tippen Stabil
    [Arguments]    ${selector}    ${text}
    [Documentation]    Setzt ${text} robust in das Feld ${selector}.
    ...                Verwendet Fill Text (atomar, statt Type Text), prueft den Inhalt nach dem
    ...                Debounce-Tick und versucht es bei Bedarf erneut. Das fixt das Race mit dem
    ...                Alpine-Auto-Fokus, der einzelne Tastenanschlaege verschluckte.
    FOR    ${attempt}    IN RANGE    3
        Click    ${selector}
        Fill Text    ${selector}    ${EMPTY}
        Fill Text    ${selector}    ${text}
        Sleep    1200ms
        ${value}=    Get Property    ${selector}    value
        IF    "${value}" == "${text}"    RETURN
        Log    Versuch ${attempt}: Wert war "${value}", erwartet "${text}" -- erneut versuchen
    END
    Fail    Konnte "${text}" nach 3 Versuchen nicht stabil in ${selector} eingeben

Sammle Karriere Eintraege
    [Documentation]    Liest alle Job-Karten aus /karriere/jobs/ und gibt sie als Liste von Dicts (title, url) zurueck.
    ...                Eine Karte ist [data-component="job-card"] mit innerer <a> (Link) und <h3> (Titel).
    Wait For Elements State    [data-component="job-card"] >> nth=0    visible    timeout=15s
    ${count}=    Get Element Count    [data-component="job-card"]
    Log    Gefundene Job-Karten: ${count}
    Should Be True    ${count} > 0    Keine Job-Karten auf der Seite gefunden
    @{entries}=    Create List
    &{seen}=    Create Dictionary
    FOR    ${i}    IN RANGE    ${count}
        ${card}=    Set Variable    [data-component="job-card"] >> nth=${i}
        ${title_ok}    ${title}=    Run Keyword And Ignore Error    Get Text    ${card} >> h3
        ${href_ok}    ${href}=    Run Keyword And Ignore Error    Get Property    ${card} >> a    href
        IF    "${title_ok}" != "PASS" or "${href_ok}" != "PASS"    CONTINUE
        ${title}=    Convert To String    ${title}
        ${title}=    Strip String    ${title}
        ${href}=    Convert To String    ${href}
        IF    "${title}" == "" or "${title}" == "None"    CONTINUE
        IF    "${href}" == "" or "${href}" == "None"    CONTINUE
        ${key}=    Set Variable    ${title}|${href}
        ${dup}=    Run Keyword And Return Status    Dictionary Should Contain Key    ${seen}    ${key}
        IF    ${dup}    CONTINUE
        Set To Dictionary    ${seen}    ${key}=1
        &{row}=    Create Dictionary    title=${title}    url=${href}
        Append To List    ${entries}    ${row}
    END
    ${n}=    Get Length    ${entries}
    Log    Extrahierte einzigartige Eintraege: ${n}
    RETURN    ${entries}

Length Should Be At Least
    [Arguments]    ${collection}    ${minimum}
    ${len}=    Get Length    ${collection}
    Should Be True    ${len} >= ${minimum}    Sammlung enthaelt nur ${len} Eintraege, erwartet mindestens ${minimum}

Schreibe Eintraege Mit ExcelSage
    [Arguments]    ${entries}    ${path}
    [Documentation]    Schreibt ${entries} (Liste von Dicts mit Keys 'title' + 'url') als .xlsx unter ${path}.
    ...                Verwendet die ExcelSage-Library: Create Workbook + Append Row + Save + Close.
    ${dir}=    Evaluate    __import__('os').path.dirname(r"${path}") or "."
    Create Directory    ${dir}
    ${header}=    Create List    title    url
    @{sheet_data}=    Create List    ${header}
    Create Workbook    workbook_name=${path}    overwrite_if_exists=${True}    sheet_data=${sheet_data}
    Rename Sheet    old_name=Sheet    new_name=Karriere
    FOR    ${entry}    IN    @{entries}
        ${row}=    Create List    ${entry}[title]    ${entry}[url]
        Append Row    row_data=${row}    sheet_name=Karriere
    END
    Save Workbook
    Close Workbook

Should Contain Any
    [Arguments]    ${haystack}    @{needles}
    FOR    ${needle}    IN    @{needles}
        ${ok}=    Run Keyword And Return Status    Should Contain    ${haystack}    ${needle}
        IF    ${ok}    RETURN
    END
    Fail    "${haystack}" enthaelt keinen der Werte ${needles}
