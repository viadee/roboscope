*** Settings ***
Library           Browser

*** Variables ***
${HEADLESS}       false

*** Test Cases ***
Recording 23
    New Browser    chromium    headless=${HEADLESS}
    New Context
    New Page    https://www.heise.de/    wait_until=domcontentloaded
    Go To    https://www.heise.de/
    Click    text=Developer
