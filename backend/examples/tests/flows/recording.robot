*** Settings ***
Library           Browser

*** Variables ***
${HEADLESS}       false

*** Test Cases ***
Recording 22
    New Browser    chromium    headless=${HEADLESS}
    New Context
    New Page    https://www.heise.de/    wait_until=domcontentloaded
    Scroll To Element    # WARNING: no selector captured    page
    Click    text=KI löst 60 Jahre altes Mathe-Problem mit neuem Ansatz
    Go To    https://www.heise.de/news/Kreativer-Loesungsweg-KI-loest-60-Jahre-altes-Erd-s-Problem-11275796.html
