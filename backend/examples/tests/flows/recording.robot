*** Settings ***
Library    Browser

*** Test Cases ***
Recording 21
    New Browser    headless=False
    New Page    https://www.heise.de/    wait_until=domcontentloaded
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Go To    https://www.heise.de/
    Scroll To Element    # WARNING: no selector captured    page
    Click    text=KI löst 60 Jahre altes Mathe-Problem mit neuem Ansatz
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
    Scroll To Element    # WARNING: no selector captured    page
