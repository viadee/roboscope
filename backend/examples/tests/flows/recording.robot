*** Settings ***
Library    Browser

*** Variables ***
${HEADLESS}    false

*** Test Cases ***
Recording 52
    New Browser    chromium    headless=${HEADLESS}
    New Context
    New Page    http://www.wastedmaniacs.com/    wait_until=domcontentloaded
    # RBSCOPE: dropped Click — no selector captured (cmd.id=274a59b8f1c8)
    Click    xpath=//a[normalize-space()="Bio"]    # rbs:c312d100b2c5
    Click    text="Thomas"    # rbs:7196de460051
    Click    text="Musik" >> nth=0    # rbs:e937a5ab89a3
